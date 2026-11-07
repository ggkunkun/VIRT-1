"""Model arms for the Virtu capability evaluation.

One ``generate(messages)`` interface over three backends:

* ``hf_local``    - transformers, 4-bit NF4, optional LoRA adapter on top of the
                    base. Measures the *trained artifact*.
* ``hf_vision``   - Qwen3-VL image+text channel (the multimodal leg).
* ``http_openai`` - an OpenAI-compatible endpoint (the deployed bridge).

Each call returns raw text plus transport metadata (latency, token counts,
finish reason, peak VRAM) so a low capability score can always be told apart
from an infrastructure failure.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import time
import urllib.error
import urllib.request


def _media_path(path: str) -> str:
    if os.path.isabs(path):
        return path
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, path.replace("/", os.sep))


def _b64_data_url(path: str) -> str:
    path = _media_path(path)
    mime = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as f:
        return f"data:{mime};base64,{base64.b64encode(f.read()).decode('ascii')}"


def _b64_raw(path: str) -> str:
    with open(_media_path(path), "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")

def _strip_think(text: str) -> str:
    """剥离模型自造的 <think>…</think> 块（含空块）。

    MoE 标签模板实测会重新打开思考块，预填模板无效（P0-4 结论），
    只能在客户端剥离；只删标签内内容，不动正文。
    """
    if not text or "<think" not in text.lower():
        return text
    cleaned = re.sub(r"<think[^>]*>.*?</think\s*>", "", text, flags=re.S | re.I)
    cleaned = re.sub(r"</?think[^>]*>", "", cleaned, flags=re.I)
    return cleaned.strip()


def _format_tool_calls(tool_calls):
    if not tool_calls:
        return ""
    formatted = []
    for tc in tool_calls:
        fn = tc.get("function") or {}
        args = fn.get("arguments", {})
        if isinstance(args, str):
            try:
                import json
                args = json.loads(args)
            except Exception:
                pass
        formatted.append({"tool": fn.get("name"), "arguments": args})
    import json
    if len(formatted) == 1:
        return json.dumps(formatted[0], ensure_ascii=False)
    return json.dumps(formatted, ensure_ascii=False)



class HFLocalArm:
    """Text arm served by locally loaded weights."""

    kind = "hf_local"

    def __init__(self, model_path, adapter_path=None, quant="nf4",
                 device="cuda", max_seq_len=2048, dtype="bfloat16",
                 double_quant=True, attn="sdpa", merge_adapter=False,
                 tools=None, tools_dimensions=None, think=None, strip_think=True):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.model_path = os.path.join(root, model_path) if not os.path.isabs(model_path) else model_path
        self.adapter_path = os.path.join(root, adapter_path) if adapter_path and not os.path.isabs(adapter_path) else adapter_path
        self.quant = quant
        self.device = device
        self.max_seq_len = max_seq_len
        self.dtype = dtype
        self.double_quant = double_quant
        self.attn = attn
        self.merge_adapter = merge_adapter
        self.tools = tools
        self.tools_dimensions = tools_dimensions
        self.think = think
        self.strip_think = strip_think
        self._llm = None
        self._tok = None
        base_label = os.path.basename(model_path.rstrip("/").rstrip("\\"))
        adapter_name = os.path.basename(adapter_path.rstrip("/").rstrip("\\")) if adapter_path else ""
        self.label = base_label if not adapter_path else f"{base_label}+{adapter_name}"

    def tools_for(self, case):
        """Tool schema to expose for this case (None = no tools)."""
        if not self.tools:
            return None
        dims = self.tools_dimensions
        if dims and case.get("dimension") not in dims:
            return None
        return self.tools

    def load(self):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self._tok = AutoTokenizer.from_pretrained(self.model_path, trust_remote_code=True)
        if self._tok.pad_token_id is None:
            self._tok.pad_token = self._tok.eos_token
        kwargs = {"device_map": self.device if self.device != "cpu" else None}
        import inspect
        dtype_kw = "dtype" if "dtype" in inspect.signature(
            AutoModelForCausalLM.from_pretrained).parameters else "torch_dtype"
        kwargs[dtype_kw] = getattr(torch, self.dtype)
        if self.quant == "nf4":
            from transformers import BitsAndBytesConfig
            kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_use_double_quant=bool(self.double_quant))
        if self.attn:
            kwargs["attn_implementation"] = self.attn
        llm = AutoModelForCausalLM.from_pretrained(self.model_path, trust_remote_code=True, **kwargs)
        if self.adapter_path:
            from peft import PeftModel
            llm = PeftModel.from_pretrained(llm, self.adapter_path)
            if self.merge_adapter:
                llm = llm.merge_and_unload()
        llm.eval()
        self._llm = llm
        return self

    def unload(self):
        import gc
        import torch
        self._llm = None
        self._tok = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()

    def generate(self, messages, max_tokens=512, temperature=0.0, top_p=1.0, seed=1234,
                 images=None, tools=None):
        import torch
        from transformers import set_seed

        if self._llm is None:
            self.load()
        set_seed(seed)
        t0 = time.perf_counter()
        chat_template_kwargs = {"add_generation_prompt": True, "tokenize": False}
        if self.think is False:
            chat_template_kwargs["enable_thinking"] = False
        try:
            text_ids = self._tok.apply_chat_template(messages, **chat_template_kwargs)
        except Exception:
            text_ids = self._tok.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
        enc = self._tok(text_ids, return_tensors="pt", add_special_tokens=False).to(self._llm.device)
        in_len = int(enc["input_ids"].shape[1])
        do_sample = temperature > 0
        gen_kwargs = {"max_new_tokens": int(max_tokens), "do_sample": do_sample,
                      "pad_token_id": self._tok.pad_token_id}
        if do_sample:
            gen_kwargs.update({"temperature": float(temperature), "top_p": float(top_p)})
        with torch.no_grad():
            out = self._llm.generate(**enc, **gen_kwargs)
        gen = out[0][in_len:]
        out_len = int(gen.shape[0])
        raw = self._tok.decode(gen, skip_special_tokens=True)

        thinking = ""
        content = raw
        fell_back = False
        if "<think>" in raw:
            if "</think>" in raw:
                m = re.search(r"<think>(.*?)</think>", raw, flags=re.DOTALL)
                if m:
                    thinking = m.group(1).strip()
                content = _strip_think(raw)
            else:
                thinking = re.sub(r"^.*?<think>", "", raw, flags=re.DOTALL).strip()
                content = _strip_think(raw)
            if not content and thinking:
                content, fell_back = thinking, True
        elif self.strip_think:
            content = _strip_think(content)

        peak = torch.cuda.max_memory_allocated() / 1024 ** 3 if torch.cuda.is_available() else 0.0
        return {"text": content, "reasoning": thinking, "fell_back_to_thinking": fell_back,
                "elapsed_s": round(time.perf_counter() - t0, 3),
                "prompt_tokens": in_len, "completion_tokens": out_len,
                "finish_reason": "length" if out_len >= int(max_tokens) else "stop",
                "peak_vram_gb": round(peak, 2), "error": None, "arm": self.label}


class HFVisionArm(HFLocalArm):
    """Image+text arm through the same 4-bit loader path, driven by AutoProcessor."""

    kind = "hf_vision"

    def load(self):
        import torch
        from transformers import AutoProcessor
        try:
            from transformers import Qwen3VLForConditionalGeneration as VisionModelClass
        except ImportError:
            try:
                from transformers import AutoModelForImageTextToText as VisionModelClass
            except ImportError:
                from transformers import AutoModelForVision2Seq as VisionModelClass

        kwargs = {"device_map": self.device if self.device != "cpu" else None}
        import inspect
        dtype_kw = "dtype" if "dtype" in inspect.signature(VisionModelClass.from_pretrained).parameters else "torch_dtype"
        kwargs[dtype_kw] = getattr(torch, self.dtype, torch.float16)
        if self.quant == "nf4":
            from transformers import BitsAndBytesConfig
            kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=bool(self.double_quant))
        try:
            llm = VisionModelClass.from_pretrained(self.model_path, trust_remote_code=True, local_files_only=True, low_cpu_mem_usage=True, **kwargs)
        except Exception:
            from transformers import AutoModel
            llm = AutoModel.from_pretrained(self.model_path, trust_remote_code=True, local_files_only=True, low_cpu_mem_usage=True, **kwargs)
        llm.eval()
        self._llm = llm
        self._proc = AutoProcessor.from_pretrained(self.model_path, trust_remote_code=True, local_files_only=True)
        self._tok = getattr(self._proc, "tokenizer", None)
        return self

    def generate(self, messages, max_tokens=512, temperature=0.0, top_p=1.0, seed=1234,
                 images=None, tools=None):
        import os as _os
        import torch
        from PIL import Image
        from transformers import set_seed

        if self._llm is None:
            self.load()
        set_seed(seed)
        t0 = time.perf_counter()
        root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
        paths = [p if _os.path.isabs(p) else _os.path.join(root, p.replace("/", _os.sep))
                 for p in (images or [])]
        if paths:
            content = ([{"type": "image", "image": _os.path.abspath(p).replace("\\", "/")}
                        for p in paths]
                       + [{"type": "text", "text": messages[-1]["content"]}])
            conv = [{"role": "user", "content": content}]
        else:
            conv = messages
        text_ids = self._proc.apply_chat_template(conv, add_generation_prompt=True, tokenize=False)
        pil = [Image.open(p).convert("RGB") for p in paths]
        enc = self._proc(text=[text_ids], images=pil or None, return_tensors="pt",
                         padding=True).to(self._llm.device)
        in_len = int(enc["input_ids"].shape[1])
        pad_id = getattr(self._tok, "pad_token_id", None) or getattr(self._proc, "pad_token_id", None) or getattr(self._llm.config, "pad_token_id", None)
        with torch.no_grad():
            out = self._llm.generate(**enc, max_new_tokens=int(max_tokens), do_sample=False,
                                     pad_token_id=pad_id)
        gen = out[0][in_len:]
        if self._tok is not None:
            raw = self._tok.decode(gen, skip_special_tokens=True)
        else:
            raw = self._proc.batch_decode([gen], skip_special_tokens=True)[0]
        peak = torch.cuda.max_memory_allocated() / 1024 ** 3
        return {"text": raw, "elapsed_s": round(time.perf_counter() - t0, 3),
                "prompt_tokens": in_len, "completion_tokens": int(gen.shape[0]),
                "finish_reason": "length" if int(gen.shape[0]) >= int(max_tokens) else "stop",
                "peak_vram_gb": round(peak, 2), "error": None, "arm": self.label,
                "n_images": len(pil)}


class HttpOpenAIArm:
    """Deployed endpoint arm (the WorkBuddy bridge or any OpenAI-compatible host)."""

    kind = "http_openai"

    def __init__(self, base_url, model_id, api_key=None, retries=2, timeout=240,
                 tools=None, tools_dimensions=None):
        self.base = base_url.rstrip("/")
        self.model_id = model_id
        self.api_key = (api_key or os.environ.get("VIRTU_EVAL_API_KEY")
                        or os.environ.get("VIRTU_API_KEY"))
        self.retries = int(retries)
        self.timeout = int(timeout)
        self.tools = tools
        self.tools_dimensions = tools_dimensions
        self.label = f"http:{self.model_id}@{self.base}"
        self._opener = None
        if any(host in self.base for host in ("127.0.0.1", "localhost", "[::1]")):
            self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            if not self.api_key:
                # The local bridge is intentionally fail-closed. Read its strong
                # token through the existing ACL-protected helper, never a blank key.
                from bridges.bridge_security import ensure_bridge_token
                self.api_key = ensure_bridge_token()

    def tools_for(self, case):
        """Tool schema to expose for this case (None = no tools)."""
        if not self.tools:
            return None
        dims = self.tools_dimensions
        if dims and case.get("dimension") not in dims:
            return None
        return self.tools

    def load(self):
        return self

    def unload(self):
        return None

    def generate(self, messages, max_tokens=512, temperature=0.0, top_p=1.0, seed=1234,
                 images=None, tools=None):
        payload = {"model": self.model_id, "messages": [], "temperature": temperature,
                   "max_tokens": max_tokens, "top_p": top_p, "stream": False}
        if tools:
            payload["tools"] = tools
        if images:
            content = [{"type": "image_url", "image_url": {"url": _b64_data_url(p)}} for p in images]
            content.append({"type": "text", "text": messages[-1]["content"]})
            payload["messages"] = [{"role": "user", "content": content}]
        else:
            payload["messages"] = messages
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        last_err = None
        for attempt in range(self.retries + 1):
            t0 = time.perf_counter()
            try:
                req = urllib.request.Request(self.base + "/chat/completions", data=body,
                                             headers=headers, method="POST")
                opener = self._opener.open if self._opener is not None else urllib.request.urlopen
                with opener(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8", "replace"))
                choices = data.get("choices") or []
                msg = (choices[0].get("message") or {}) if choices else {}
                usage = data.get("usage") or {}
                content = msg.get("content") or ""
                if not content and msg.get("tool_calls"):
                    content = _format_tool_calls(msg["tool_calls"])
                return {"text": content,
                        "reasoning": msg.get("reasoning_content"),
                        "tool_calls": msg.get("tool_calls"),
                        "elapsed_s": round(time.perf_counter() - t0, 3),
                        "prompt_tokens": usage.get("prompt_tokens"),
                        "completion_tokens": usage.get("completion_tokens"),
                        "finish_reason": choices[0].get("finish_reason") if choices else None,
                        "served_model": data.get("model"),
                        "peak_vram_gb": None, "error": None, "arm": self.label,
                        "attempts": attempt + 1}
            except urllib.error.HTTPError as e:
                last_err = f"http_{e.code}:{e.read().decode('utf-8', 'replace')[:200]}"
            except Exception as e:  # noqa: BLE001
                last_err = f"{type(e).__name__}:{e}"
            time.sleep(1.5 * (attempt + 1))
        return {"text": "", "elapsed_s": None, "prompt_tokens": None,
                "completion_tokens": None, "finish_reason": None, "peak_vram_gb": None,
                "error": last_err, "arm": self.label, "attempts": self.retries + 1}


class OllamaNativeArm:
    """Local Ollama ``/api/chat`` arm - the deployed GGUF artifact, measured as served.

    Ollama 0.40 rejects the OpenAI-compatible ``/v1/chat/completions`` route, so
    this arm talks to the native endpoint. It bypasses ``HTTP_PROXY`` because the
    host proxy would otherwise swallow calls to ``127.0.0.1``.

    Tags on this box are mutable: measured 2026-11-05, `virtu-comprehensive:latest`
    was re-created mid-leg onto a different system/template layer, and `virtu-master`,
    `virtu-ties-v1` and `virtu-test-tool` all became aliases of one manifest. A score
    quoted against a tag name is therefore unfalsifiable unless the serving layers are
    captured with it, so ``served_layers`` is recorded once per arm and attached to
    every generation.
    """

    kind = "ollama_native"

    def __init__(self, model_id, base_url="http://127.0.0.1:11434", num_ctx=4096,
                 think=False, retries=1, timeout=300, tools=None, tools_dimensions=None,
                 strip_think=False, num_gpu=None):
        self.model_id = model_id
        self.base = base_url.rstrip("/")
        self.num_ctx = int(num_ctx)
        # Load-time placement. Only forwarded when pinned: leaving it unset keeps ollama's own
        # default, so existing legs are unaffected. Pinning also DISABLES llama.cpp's auto-fit,
        # so an over-large value crashes the server instead of degrading: measured 2026-11-07,
        # the 13.63B MoE at num_gpu=30/ctx4096 asked for 6580 MiB against 5080 MiB free and took
        # llama-server down with it. Derive the ceiling from free VRAM (mem_budget.max_offload_layers)
        # rather than hardcoding 22/30 -- both were over the safe split at today's desktop load.
        self.num_gpu = None if num_gpu is None else int(num_gpu)
        self.think = think
        self.strip_think = bool(strip_think)
        self.retries = int(retries)
        self.timeout = int(timeout)
        self.tools = tools
        self.tools_dimensions = tools_dimensions
        self.label = f"ollama:{self.model_id}"
        self.served_layers = self._read_layers()
        self.tools_supported = None
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _read_layers(self):
        """Resolve the tag to its model/template/system/params layer digests, offline.

        Reads BOTH manifest layouts: this box's current store is
        ``manifests-v2/ollama.com/library`` while the older
        ``manifests/registry.ollama.ai/library`` still exists. Reading only the old
        one returned "manifest missing" for every tag, silently disabling the
        served-layer attribution the I0-I4 identity gates rely on. The params layer
        media type ends in ``.params`` (not ``.parameters``), which the old loop also
        never matched.
        """
        from virtu_eval import mem_budget as mb
        home = os.path.expanduser("~")
        root = next((p for p in (os.environ.get("OLLAMA_MODELS"),
                                 os.path.join(home, ".ollama", "models"),
                                 r"E:\ollama\models") if p and os.path.isdir(p)), None)
        if root is None:
            return {"error": "no ollama model store found"}
        try:
            _path, doc, _root = mb._manifest_for_tag(self.model_id, root)
        except Exception as exc:  # noqa: BLE001
            return {"error": f"{type(exc).__name__}:{exc}"}
        out = {}
        for layer in doc.get("layers", []):
            media = layer.get("mediaType", "")
            for kind in ("model", "template", "system", "adapter", "params", "parameters"):
                if media.endswith("." + kind):
                    key = "parameters" if kind == "params" else kind
                    out[key] = layer.get("digest", "")
                    out[key + "_bytes"] = layer.get("size")
        out["manifest_digest"] = doc.get("config", {}).get("digest", "")
        return out

    def tools_for(self, case):
        """Expose the tool schema only where it is being measured.

        Injecting tools into every prompt would change how all the other
        dimensions behave, so the schema is scoped by dimension.
        """
        if not self.tools:
            return None
        dims = self.tools_dimensions
        if dims and case.get("dimension") not in dims:
            return None
        return self.tools

    def load(self):
        # A local leg competes for this box's 6 GiB VRAM / 15.7 GiB RAM; a remote
        # leg does not, so the budget gate only applies to a loopback endpoint.
        # Refusing here is the point: an over-fit used to crash llama-server and
        # orphan a runner still holding ~5.9 GiB VRAM and ~9 GiB commit.
        from urllib.parse import urlsplit
        host = (urlsplit(self.base).hostname or "").lower()
        if host in ("127.0.0.1", "localhost", "::1"):
            from virtu_eval import mem_budget as mb
            env = mb.require_headroom()
            try:
                facts = mb.facts_for_tag(self.model_id)
            except mb.BudgetError:
                facts = None  # the client's store may differ from the server's
            if facts is not None:
                # An unpinned num_gpu inherits the tag's baked PARAMETER value, not
                # full offload; assuming full offload would over-refuse MoE legs.
                eff_gpu = self.num_gpu
                if eff_gpu is None:
                    try:
                        eff_gpu = mb.params_for_tag(self.model_id).get("num_gpu")
                    except mb.BudgetError:
                        eff_gpu = None
                if eff_gpu is None:
                    # Placement unknown => ollama auto-fits, so only budget the host.
                    verdict = mb.check(mb.project(facts, self.num_ctx, 0), env=env)
                    verdict["reasons"] = [r for r in verdict["reasons"]
                                          if not r.startswith("vram")]
                    verdict["ok"] = not verdict["reasons"]
                else:
                    verdict = mb.check(mb.project(facts, self.num_ctx, eff_gpu), env=env)
                if not verdict["ok"]:
                    try:
                        ceiling = mb.max_offload_layers(facts, self.num_ctx, env=env)
                    except mb.BudgetError:
                        ceiling = None
                    raise mb.BudgetError(
                        "arm %s does not fit this box: %s (safe num_gpu ceiling at "
                        "num_ctx=%d is %s; pin it in the arm spec or free VRAM/commit)"
                        % (self.model_id, "; ".join(verdict["reasons"]), self.num_ctx,
                           ceiling))
        return self

    def unload(self):
        return None

    def generate(self, messages, max_tokens=512, temperature=0.0, top_p=1.0, seed=1234,
                 images=None, tools=None):
        msgs = []
        for m in messages:
            item = {"role": m["role"], "content": m["content"]}
            if images and m["role"] == "user" and m is messages[-1]:
                item["images"] = [_b64_raw(p) for p in images]
            msgs.append(item)
        payload = {"model": self.model_id, "messages": msgs, "stream": False,
                   "think": bool(self.think),
                   "options": {"temperature": float(temperature), "top_p": float(top_p),
                               "num_predict": int(max_tokens), "num_ctx": self.num_ctx,
                               "seed": int(seed)}}
        if self.num_gpu is not None:
            payload["options"]["num_gpu"] = self.num_gpu
        tools_requested = bool(tools)
        headers = {"Content-Type": "application/json"}
        last_err = None
        dropped_tools = False
        for attempt in range(self.retries + 1):
            payload = dict(payload)
            payload.pop("tools", None)
            if tools_requested and self.tools_supported is not False:
                payload["tools"] = tools
            elif tools_requested:
                dropped_tools = True
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            t0 = time.perf_counter()
            try:
                req = urllib.request.Request(self.base + "/api/chat", data=body,
                                             headers=headers, method="POST")
                with self._opener.open(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8", "replace"))
                msg = data.get("message") or {}
                content = msg.get("content") or ""
                thinking = msg.get("thinking") or ""
                # Qwen3 templates can route the whole answer into the reasoning
                # block.  A non-empty generation must never be scored as empty.
                fell_back = False
                if not content and thinking:
                    content, fell_back = thinking, True
                if not content and msg.get("tool_calls"):
                    content, fell_back = _format_tool_calls(msg["tool_calls"]), True
                if self.strip_think:
                    content = _strip_think(content)
                    thinking = _strip_think(thinking)
                eval_count = data.get("eval_count")
                eval_s = (data.get("eval_duration") or 0) / 1e9
                return {"text": content,
                        "reasoning": thinking,
                        "elapsed_s": round(time.perf_counter() - t0, 3),
                        "prompt_tokens": data.get("prompt_eval_count"),
                        "completion_tokens": eval_count,
                        "finish_reason": data.get("done_reason") or ("stop" if data.get("done") else None),
                        "tok_per_s": round(eval_count / eval_s, 1) if eval_count and eval_s else None,
                        "served_model": data.get("model"),
                        "content_was_empty": not bool(msg.get("content")),
                        "fell_back_to_thinking": fell_back,
                        "tool_calls": msg.get("tool_calls"),
                        "peak_vram_gb": None, "error": None, "arm": self.label,
                        "attempts": attempt + 1,
                        "served_layers": self.served_layers,
                        "tools_requested": tools_requested,
                        "tools_supported": self.tools_supported,
                        "tools_dropped_for_json_protocol": dropped_tools}
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")
                last_err = f"http_{e.code}:{detail[:200]}"
                # Measured 2026-11-05: virtu-comprehensive/virtu-master carry a
                # {{ .Prompt }} template with no tool branch, so Ollama answers every
                # tools-bearing request with 400 "does not support tools" - a whole
                # toolcall dimension became 30 identical transport errors. Degrade to
                # the JSON-text protocol that artifact's own system prompt requires,
                # cache the capability, and record the drop in the row.
                if e.code == 400 and tools_requested and "support tools" in detail:
                    self.tools_supported = False
                    continue
                time.sleep(1.5 * (attempt + 1))
            except Exception as e:  # noqa: BLE001
                last_err = f"{type(e).__name__}:{e}"
                time.sleep(1.5 * (attempt + 1))
        return {"text": "", "elapsed_s": None, "prompt_tokens": None,
                "completion_tokens": None, "finish_reason": None, "peak_vram_gb": None,
                "error": last_err, "arm": self.label, "attempts": self.retries + 1,
                "served_layers": self.served_layers,
                "tools_supported": self.tools_supported}


def build_arm(spec: dict):
    kind = spec["kind"]
    if kind == "hf_local":
        return HFLocalArm(spec["model_path"], spec.get("adapter_path"),
                          quant=spec.get("quant", "nf4"), device=spec.get("device", "cuda"),
                          dtype=spec.get("dtype", "bfloat16"),
                          double_quant=spec.get("double_quant", True),
                          attn=spec.get("attn", "sdpa"),
                          merge_adapter=spec.get("merge_adapter", False),
                          tools=spec.get("tools"),
                          tools_dimensions=spec.get("tools_dimensions"))
    if kind == "hf_vision":
        return HFVisionArm(spec["model_path"], spec.get("adapter_path"),
                           quant=spec.get("quant", "nf4"), device=spec.get("device", "cuda"),
                           tools=spec.get("tools"),
                           tools_dimensions=spec.get("tools_dimensions"))
    if kind == "http_openai":
        return HttpOpenAIArm(spec["base_url"], spec["model_id"], spec.get("api_key"),
                             retries=spec.get("retries", 2), timeout=spec.get("timeout", 240),
                             tools=spec.get("tools"),
                             tools_dimensions=spec.get("tools_dimensions"))
    if kind == "ollama_native":
        return OllamaNativeArm(spec["model_id"], spec.get("base_url", "http://127.0.0.1:11434"),
                               num_ctx=spec.get("num_ctx", 4096),
                               think=spec.get("think", False),
                               retries=spec.get("retries", 1),
                               timeout=spec.get("timeout", 300),
                               tools=spec.get("tools"),
                               tools_dimensions=spec.get("tools_dimensions"),
                               strip_think=spec.get("strip_think", False),
                               num_gpu=spec.get("num_gpu"))
    raise ValueError(f"unknown arm kind {kind!r}")
