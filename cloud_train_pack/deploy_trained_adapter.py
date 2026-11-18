#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cloud_train_pack/deploy_trained_adapter.py — Virtu 8.2B LoRA 真融合、GGUF 转换、Ollama 17 工具原生态部署与 4 项联调自证 (v2)

全链路严格执行：
  1. safe_extract 安全解包交付件 + training_receipt.json COMPLETED / SHA256 双重校验；
  2. lineage_gate 校验基座严格为 Qwen3-8B (4096/36/151936)，严拒 Qwen2.5-7B 与 Instruct 混用；
  3. 调用 scripts/merge_numpy.py 实算 LoRA Delta 合并 + scripts/hf_to_gguf_numpy.py 转换 GGUF Q4_0；
  4. 生成官方 Qwen3 原生 .Tools / <tool_call> Modelfile (无硬编码 num_gpu，SYSTEM <= 702B)；
  5. 默认拒绝覆盖已存在的 Ollama 标签 (--allow-overwrite 显式授权才允许)；
  6. 执行 4 项部署后真实探针自证并落盘 deployment_receipt.json。
"""

import os
import re
import sys
import json
import time
import glob
import shutil
import hashlib
import tarfile
import argparse
import tempfile
import subprocess
import urllib.request
import urllib.error
from typing import Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(ROOT, "scripts")
DEFAULT_DELIVERABLE = os.path.join(ROOT, "checkpoints", "virtu_master_lora_deliverable.tar.gz")

# ---------------------------------------------------------------------------
# 判分器身份快照（AGENTS.md §8.2「判分器 sha256」「按内容寻址，不按名字」）
# 在**导入时**对本文件取哈希：同一时刻启动的测量腿共享同一判分器版本；
# 磁盘上后续被改动时，已在跑的腿仍持有自己导入时的哈希，凭证不会被事后篡改。
# ---------------------------------------------------------------------------
# v4（2026-11-16）：autodiff 锚点回退根因修复 —— def_pat 未命中时旧 matches[-1]
# 被末尾负面警示提及劫持，完整正确三色答案误判 missing_meaning:red；改取窗口含
# 正/负语义的首个出现（复用 sw_coordinate 原则）。缺色/语义互换/枚举式提及仍判红。
MEASUREMENT_VERSION = "probes-2026-11-16-v5"


def _snapshot_grader_sha256() -> str:
    try:
        with open(os.path.abspath(__file__), "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except Exception:
        return "unavailable"


GRADER_SHA256 = _snapshot_grader_sha256()
EXPECTED_BASE_SPEC = {
    "hidden_size": 4096,
    "num_hidden_layers": 36,
    "vocab_size": 151936,
}

# 与 cloud_train_pack/train_cloud_virtu_13b.py 对齐的 Qwen3 原生工具调用模板
OFFICIAL_QWEN_TOOL_TEMPLATE = """{{- $lastUserIdx := -1 -}}
{{- range $idx, $msg := .Messages -}}
{{- if eq $msg.Role "user" }}{{ $lastUserIdx = $idx }}{{ end -}}
{{- end }}
{{- if or .System .Tools }}<|im_start|>system
{{ if .System }}
{{ .System }}
{{- end }}
{{- if .Tools }}

# Tools

You may call one or more functions to assist with the user query.

You are provided with function signatures within <tools></tools> XML tags:
<tools>
{{- range .Tools }}
{"type": "function", "function": {{ .Function }}}
{{- end }}
</tools>

For each function call, return a json object with function name and arguments within <tool_call></tool_call> XML tags:
<tool_call>
{"name": <function-name>, "arguments": <args-json-object>}
</tool_call>
{{- end -}}
<|im_end|>
{{ end }}
{{- range $i, $_ := .Messages }}
{{- $last := eq (len (slice $.Messages $i)) 1 -}}
{{- if eq .Role "user" }}<|im_start|>user
{{ .Content }}
{{- if and $.IsThinkSet (eq $i $lastUserIdx) }}
   {{- if $.Think -}}
      {{- " "}}/think
   {{- else -}}
      {{- " "}}/no_think
   {{- end -}}
{{- end }}<|im_end|>
{{ else if eq .Role "assistant" }}<|im_start|>assistant
{{ if (and $.IsThinkSet (and .Thinking (or $last (gt $i $lastUserIdx)))) -}}
<think>{{ .Thinking }}</think>
{{ end -}}
{{ if .Content }}{{ .Content }}
{{- else if .ToolCalls }}<tool_call>
{{ range .ToolCalls }}{"name": "{{ .Function.Name }}", "arguments": {{ .Function.Arguments }}}
{{ end }}</tool_call>
{{- end }}{{ if not $last }}<|im_end|>
{{ end }}
{{- else if eq .Role "tool" }}<|im_start|>user
<tool_response>
{{ .Content }}
</tool_response><|im_end|>
{{ end }}
{{- if and (ne .Role "assistant") $last }}<|im_start|>assistant
{{ if and $.IsThinkSet (not $.Think) -}}
<think>

</think>

{{ end -}}
{{ end }}
{{- end }}"""

DEFAULT_SYSTEM_PROMPT = (
    "你是 Virtu，工业 CAD/CAE/CAM 与 CNC 数控工程专家。严格使用毫米(mm)与度(deg)计算几何尺寸、公差与 Lamé 应力，"
    "优先确保模型体积变化准确、安全系数 FOS >= 1.5、G00 快速移动零碰撞。"
    "当工具列表可用时，仅通过原生 <tool_call> 调用真实工具并等待回执，绝不伪造测量结果、文件名或执行状态。"
)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(4 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def _local_env() -> dict:
    env = os.environ.copy()
    env["NO_PROXY"] = "127.0.0.1,localhost"
    env["no_proxy"] = "127.0.0.1,localhost"
    return env


def safe_extract(tar: tarfile.TarFile, dest_dir: str) -> list:
    """安全解包：拒绝绝对路径、.. 路径穿越、符号链接/硬链接及特殊设备节点。"""
    dest_real = os.path.realpath(dest_dir)
    os.makedirs(dest_real, exist_ok=True)
    safe_members = []
    for member in tar.getmembers():
        if member.issym() or member.islnk():
            raise ValueError(f"[SECURITY] 拒绝解压链接条目: {member.name}")
        if member.isdev() or member.isfifo() or member.ischr() or member.isblk():
            raise ValueError(f"[SECURITY] 拒绝解压设备条目: {member.name}")
        norm_name = member.name.replace("\\", "/")
        if os.path.isabs(norm_name) or norm_name.startswith("/") or (len(norm_name) > 1 and norm_name[1] == ":"):
            raise ValueError(f"[SECURITY] 拒绝绝对路径条目: {member.name}")
        target_real = os.path.realpath(os.path.join(dest_real, member.name))
        if target_real != dest_real and not target_real.startswith(dest_real + os.sep):
            raise ValueError(f"[SECURITY] 拒绝路径穿越条目: {member.name} -> {target_real}")
        safe_members.append(member)

    for member in safe_members:
        target_real = os.path.realpath(os.path.join(dest_real, member.name))
        if member.isdir():
            os.makedirs(target_real, exist_ok=True)
        else:
            os.makedirs(os.path.dirname(target_real), exist_ok=True)
            src_f = tar.extractfile(member)
            if src_f is None:
                continue
            with src_f, open(target_real, "wb") as out_f:
                shutil.copyfileobj(src_f, out_f)
    return safe_members


def verify_deliverable_receipt(unpack_dir: str) -> tuple:
    """验证交付解包收据并返回 (receipt_dict, adapter_dir)。"""
    candidates = [
        os.path.join(unpack_dir, "virtu_lora_adapter", "training_receipt.json"),
        os.path.join(unpack_dir, "training_receipt.json"),
    ]
    receipt_path = next((p for p in candidates if os.path.exists(p)), None)
    if not receipt_path:
        raise RuntimeError(f"[FATAL] 交付目录缺少 training_receipt.json: {unpack_dir}")

    with open(receipt_path, "r", encoding="utf-8") as f:
        rdata = json.load(f)

    if rdata.get("status") != "COMPLETED":
        raise RuntimeError(f"[FATAL] 训练未 COMPLETED (status={rdata.get('status')!r})，拒绝部署！")

    adapter_sha = str(rdata.get("adapter_sha256", "")).strip()
    dataset_sha = str(rdata.get("dataset_sha256", "")).strip()
    if len(adapter_sha) != 64 or len(dataset_sha) != 64:
        raise RuntimeError("[FATAL] training_receipt.json 缺少有效的 adapter_sha256 / dataset_sha256")
    if "instruct" in str(rdata.get("base_model", "")).lower():
        raise RuntimeError(f"[FATAL] receipt 中基座包含 Instruct: {rdata.get('base_model')}")

    adapter_dir = os.path.dirname(receipt_path)
    weight_file = os.path.join(adapter_dir, "adapter_model.safetensors")
    if not os.path.exists(weight_file):
        raise RuntimeError(f"[FATAL] 缺少 adapter_model.safetensors: {weight_file}")
    actual_sha = sha256_file(weight_file)
    if actual_sha.lower() != adapter_sha.lower():
        raise RuntimeError(
            f"[FATAL] adapter_model.safetensors SHA256 与 receipt 不一致! "
            f"receipt={adapter_sha[:16]} actual={actual_sha[:16]}"
        )
    return rdata, adapter_dir


def lineage_gate(base_dir: str, adapter_dir: str = None) -> dict:
    """严格基座血统验证：仅允许 Qwen3-8B (4096/36/151936)，拒绝对接 Qwen2.5-7B 或 Instruct。"""
    if not base_dir or not os.path.isdir(base_dir):
        raise RuntimeError(f"[FATAL] 基座目录不存在: {base_dir}")
    if "instruct" in str(base_dir).replace("\\", "/").lower():
        raise RuntimeError(f"[FATAL] 拒绝将 Instruct 模型作为合并基座: {base_dir}")

    cfg_path = os.path.join(base_dir, "config.json")
    if not os.path.exists(cfg_path):
        raise RuntimeError(f"[FATAL] 基座缺少 config.json: {cfg_path}")
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    if "instruct" in str(cfg.get("_name_or_path", "")).lower():
        raise RuntimeError(f"[FATAL] config.json[_name_or_path] 包含 Instruct: {cfg.get('_name_or_path')}")
    model_type = str(cfg.get("model_type", "")).lower()
    if model_type and "qwen3" not in model_type:
        raise RuntimeError(f"[FATAL] 基座 model_type={model_type!r} 非 Qwen3 系列 (禁止 Qwen2.5 错配)")

    for k, expected in EXPECTED_BASE_SPEC.items():
        actual = cfg.get(k)
        if actual != expected:
            raise RuntimeError(f"[FATAL] 基座维度不符 Qwen3-8B: {k}={actual!r} != {expected!r}")

    if adapter_dir:
        acfg_path = os.path.join(adapter_dir, "adapter_config.json")
        if os.path.exists(acfg_path):
            with open(acfg_path, "r", encoding="utf-8") as af:
                acfg = json.load(af)
            ap_base = str(acfg.get("base_model_name_or_path", "")).lower()
            if "instruct" in ap_base or "2.5-7b" in ap_base:
                raise RuntimeError(f"[FATAL] adapter_config.json 基座记录异常: {ap_base}")

    print(f"[LineageGate] PASS: Qwen3-8B (h={cfg['hidden_size']}, L={cfg['num_hidden_layers']}, V={cfg['vocab_size']}) <- {base_dir}")
    return cfg


def find_base_dir(base_arg: str = None) -> str:
    if base_arg:
        if os.path.isdir(base_arg):
            return os.path.abspath(base_arg)
        raise SystemExit(f"[FATAL] 指定的 --base 目录不存在: {base_arg}")

    candidates = [
        os.path.join(ROOT, "checkpoints", "_base_qwen3_8b"),
        os.path.join(ROOT, "models", "Qwen3-8B"),
        os.path.join(ROOT, "checkpoints", "Qwen3-8B"),
    ]
    hf_hub = os.path.expanduser("~/.cache/huggingface/hub/models--Qwen--Qwen3-8B/snapshots")
    if os.path.isdir(hf_hub):
        candidates.extend(sorted(glob.glob(os.path.join(hf_hub, "*")), reverse=True))
    ms_hub = os.path.expanduser("~/.cache/modelscope/hub/Qwen/Qwen3-8B")
    candidates.append(ms_hub)

    for c in candidates:
        if os.path.isdir(c) and os.path.exists(os.path.join(c, "config.json")):
            return os.path.abspath(c)

    raise SystemExit(
        "[FATAL] 未在本机找到 Qwen3-8B 非 Instruct 基座权重目录 (checkpoints/_base_qwen3_8b / HF cache)。\n"
        "请传入 --base <Qwen3-8B本地目录> 后重试，拒绝跨代错误基座伪装上线!"
    )


def merge_lora_adapter(base_dir: str, adapter_dir: str, merged_dir: str, weight: float = 1.0, mode: str = "delta") -> None:
    merge_script = os.path.join(SCRIPTS_DIR, "merge_numpy.py")
    if not os.path.exists(merge_script):
        raise SystemExit(f"[FATAL] 缺少 LoRA 合并工具: {merge_script}")
    os.makedirs(merged_dir, exist_ok=True)
    cmd = [
        sys.executable,
        merge_script,
        "--base", base_dir,
        "--lora", adapter_dir,
        "--weight", str(weight),
        "--mode", mode,
        "--out", merged_dir,
        "--verify-samples", "3",
    ]
    print(f"[Merge] 执行实算 LoRA 合并: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, env=_local_env())
    if not os.path.exists(os.path.join(merged_dir, "config.json")):
        raise RuntimeError(f"[FATAL] merge_numpy.py 未生成 merged/config.json: {merged_dir}")


def convert_to_gguf(merged_dir: str, gguf_path: str, qtype: str = "q4_0") -> str:
    """将融合后的 HF 权重转为 GGUF (注意 scripts/hf_to_gguf_numpy.py 固定输出 Q4_0 且无 --qtype 参数)。"""
    conv_script = os.path.join(SCRIPTS_DIR, "hf_to_gguf_numpy.py")
    if not os.path.exists(conv_script):
        raise SystemExit(f"[FATAL] 缺少 GGUF 转换脚本: {conv_script}")
    if qtype.lower() != "q4_0":
        raise SystemExit(f"[FATAL] scripts/hf_to_gguf_numpy.py 仅支持 q4_0，不支持 --qtype={qtype}")
    os.makedirs(os.path.dirname(os.path.abspath(gguf_path)), exist_ok=True)
    cmd = [sys.executable, conv_script, "--model", merged_dir, "--out", gguf_path]
    print(f"[GGUF] 转换 HF -> GGUF Q4_0: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, env=_local_env())
    if not os.path.exists(gguf_path) or os.path.getsize(gguf_path) <= 0:
        raise RuntimeError(f"[FATAL] GGUF 产物缺失或为空: {gguf_path}")
    with open(gguf_path, "rb") as gf:
        magic = gf.read(4)
    if magic != b"GGUF":
        raise RuntimeError(f"[FATAL] GGUF 文件魔数异常 ({magic!r}): {gguf_path}")
    return os.path.abspath(gguf_path)


def build_modelfile(gguf_path: str, system_prompt: str = DEFAULT_SYSTEM_PROMPT) -> str:
    sys_bytes = len(system_prompt.encode("utf-8"))
    if sys_bytes > 702:
        raise ValueError(f"[FATAL] SYSTEM prompt 超出 All-90 702B 上限: {sys_bytes} bytes")
    gguf_abs = os.path.abspath(gguf_path).replace("\\", "/")
    content = (
        f"FROM {gguf_abs}\n\n"
        f'TEMPLATE """{OFFICIAL_QWEN_TOOL_TEMPLATE}"""\n\n'
        f'SYSTEM """{system_prompt}"""\n\n'
        "PARAMETER temperature 0.1\n"
        "PARAMETER top_p 0.9\n"
        "PARAMETER repeat_penalty 1.05\n"
        "PARAMETER num_ctx 8192\n"
        'PARAMETER stop "<|im_end|>"\n'
        'PARAMETER stop "<|endoftext|>"\n'
    )
    return content


def list_ollama_tags() -> list:
    res = subprocess.run(["ollama", "list"], capture_output=True, text=True, check=True, env=_local_env())
    tags = []
    for line in res.stdout.splitlines()[1:]:
        parts = line.split()
        if parts:
            tags.append(parts[0].strip())
    return tags


def assert_tag_writable(tag: str, allow_overwrite: bool = False, existing_tags: list = None) -> None:
    norm = tag if ":" in tag else f"{tag}:latest"
    tags = existing_tags if existing_tags is not None else list_ollama_tags()
    normalized_existing = {t if ":" in t else f"{t}:latest" for t in tags}
    if norm in normalized_existing and not allow_overwrite:
        raise SystemExit(
            f"[FATAL] 目标 Ollama 标签 {norm} 已存在！按 AGENTS.md §8 禁止静默覆盖已封缄模型；"
            "请换用新版本标签，或显式传入 --allow-overwrite。"
        )


def _ollama_chat(payload: dict, base_url: str = "http://127.0.0.1:11434") -> dict:
    url = f"{base_url.rstrip('/')}/api/chat"
    timeout_s = max(30, int(os.environ.get("VIRTU_OLLAMA_TIMEOUT_S", "240")))
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _ollama_chat_with_memory_fallback(payload: dict, base_url: str = "http://127.0.0.1:11434") -> dict:
    return _ollama_chat(payload, base_url=base_url)


def _probe_chat(tag: str, messages: list, *, num_predict: int = 256, keep_alive: str = "180s",
                tools: list = None, think: Optional[bool] = False) -> dict:
    payload = {
        "model": tag,
        "stream": False,
        "keep_alive": keep_alive,
        "options": {"temperature": 0.0, "num_predict": num_predict},
        "messages": messages,
    }
    if tools:
        payload["tools"] = tools
    if think is not None:
        payload["think"] = think
    return _ollama_chat(payload)


def _resolve_probe_profile(tag: str, probe_profile: str = "auto") -> str:
    prof = str(probe_profile or "auto").strip().lower()
    if prof == "auto":
        return "vericut96" if "vericut" in str(tag or "").lower() else "general"
    if prof not in ("general", "vericut96", "all"):
        raise ValueError(f"Unsupported probe_profile: {probe_profile!r}")
    return prof


def verify_deployed_model(
    tag: str,
    *,
    probe_profile: str = "auto",
    think: Optional[bool] = False,
) -> dict:
    """部署后真实探针自证：核心通用门 + 领域/跨领域探针（支持 auto / general / vericut96 / all）。"""
    probes = {}
    resolved_profile = _resolve_probe_profile(tag, probe_profile)

    # Probe 1: ollama show --modelfile 验证 .Tools + <tool_call> + 无 num_gpu
    show_res = subprocess.run(
        ["ollama", "show", tag, "--modelfile"],
        capture_output=True, text=True, encoding="utf-8", check=True, env=_local_env(),
    )
    mf_out = show_res.stdout
    has_tools = (".Tools" in mf_out) and ("<tool_call>" in mf_out)
    no_num_gpu = "num_gpu" not in mf_out.lower()
    probes["show_template_gate"] = {
        "passed": bool(has_tools and no_num_gpu),
        "has_tools_and_tool_call": has_tools,
        "no_hardcoded_num_gpu": no_num_gpu,
    }

    # Probe 2: /api/chat 工程基础响应探针
    r2 = _probe_chat(
        tag,
        [{"role": "user", "content": "给出薄壁圆筒环向应力的基本公式符号说明，简短回答。"}],
        num_predict=128,
        keep_alive="180s",
        think=think,
    )
    msg2 = r2.get("message", {})
    txt2 = _strip_think_blocks(str(msg2.get("content", "")).strip())
    probes["chat_liveness_probe"] = {
        "passed": len(txt2) >= 12 and "traceback" not in txt2.lower(),
        "response_len": len(txt2),
        "sample": txt2[:160],
    }

    # Probe 3: 原生 Tool Calling 17 工具协议探针
    sample_tools = [
        {
            "type": "function",
            "function": {
                "name": "cadcam_universal_geometry",
                "description": "Compute 3D solid geometry volume, bounding box, and surface area.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "shape": {"type": "string"},
                        "diameter_mm": {"type": "number"},
                        "length_mm": {"type": "number"},
                    },
                    "required": ["shape", "diameter_mm", "length_mm"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "cadcam_cae_stress_analysis",
                "description": "Compute von Mises stress and Factor of Safety (FOS).",
                "parameters": {
                    "type": "object",
                    "properties": {"pressure_mpa": {"type": "number"}, "wall_thickness_mm": {"type": "number"}},
                    "required": ["pressure_mpa", "wall_thickness_mm"],
                },
            },
        },
    ]
    r3 = _probe_chat(
        tag,
        [{"role": "user", "content": "请调用工具计算直径 80mm、长度 120mm 圆柱体的几何体积。"}],
        num_predict=256,
        keep_alive="180s",
        tools=sample_tools,
        think=think,
    )
    msg3 = r3.get("message", {})
    tcalls3 = msg3.get("tool_calls") or []
    txt3 = str(msg3.get("content", ""))
    called_names = [
        (tc.get("function") or {}).get("name") for tc in tcalls3 if isinstance(tc, dict)
    ]
    tool_eval = evaluate_tool_call_arguments(
        tcalls3, txt3, expected_name="cadcam_universal_geometry", expected_nums=(80.0, 120.0)
    )
    probes["native_tool_call_probe"] = {
        "passed": bool(tool_eval["passed"]),
        "tool_calls_count": len(tcalls3),
        "called_names": called_names,
        "parsed_args": tool_eval.get("parsed_args"),
        "reason": tool_eval.get("reason"),
        "raw_snippet": txt3[:160],
        "full_response": txt3,
    }

    # Probe 4 (general/all) + anti_degenerate_sanity_probe
    if resolved_profile in ("general", "all"):
        r4 = _probe_chat(
            tag,
            [{"role": "user", "content": "列举 SOLIDWORKS 2021 的 Front/Top/Right 三个默认基准面法向。"}],
            num_predict=220,
            keep_alive="180s",
            think=think,
        )
        txt4 = _strip_think_blocks(str((r4.get("message") or {}).get("content", "")).strip())
        words4 = [txt4[i:i+6] for i in range(0, max(1, len(txt4) - 5), 3)]
        uniq_ratio = len(set(words4)) / max(1, len(words4))
        anti_deg_ok = len(txt4) >= 12 and uniq_ratio >= 0.35
        probes["anti_degenerate_sanity_probe"] = {
            "passed": anti_deg_ok,
            "response_len": len(txt4),
            "unique_ngram_ratio": round(uniq_ratio, 3),
            "sample": txt4[:160],
        }
        probes["sw_coordinate_probe"] = evaluate_sw_coordinate_probe(txt4)

        # Probe 5: Lamé 厚壁圆筒应力闭合解探针 (Di=60, Do=120, Pi=20 => σ_θ=33.33MPa, σ_r=-20MPa)
        # 2026-11-15：num_predict 260→420。实测 260 时模型在 σ_θ=33.33 之后、写出 σ_r 之前
        # 被硬截断，旧判分器据此误判为「模型没答对 σ_r」。
        r5 = _probe_chat(
            tag,
            [{
                "role": "user",
                "content": "按 Lamé 厚壁圆筒理论：内径 Di=60 mm，外径 Do=120 mm，内压 Pi=20 MPa。"
                           "计算内壁环向应力 σ_θ（保留 2 位小数）与径向应力 σ_r，单位 MPa。",
            }],
            num_predict=420,
            keep_alive="180s",
            think=think,
        )
        txt5 = str((r5.get("message") or {}).get("content", "")).strip()
        probes["lame_stress_probe"] = evaluate_lame_stress_probe(txt5)

        # Probe 6: FANUC G71/G70 复合循环与无快速扎刀安全性探针
        r6 = _probe_chat(
            tag,
            [{
                "role": "user",
                "content": "用 FANUC ISO/G 格式为 Ø60 棒料编写 G71 粗车+G70 精车台阶轴程序"
                           "（第一台阶 Ø38 长 20 mm，总长 45 mm），含 G50 S1800、G96 S150 M03、T0101、F0.25 与 M30，只输出程序。",
            }],
            num_predict=320,
            keep_alive="180s",
            think=think,
        )
        txt6 = str((r6.get("message") or {}).get("content", "")).strip()
        probes["fanuc_g71_safety_probe"] = evaluate_fanuc_g71_safety_probe(txt6)

    # VERICUT 9.6 专项探针 (vericut96 / all)
    if resolved_profile in ("vericut96", "all"):
        rv1 = _probe_chat(
            tag,
            [{"role": "user", "content": "说明 VERICUT 9.6 Auto-Diff 偏差图中红色、蓝色、绿色分别代表什么？以及发现红色时应如何处置？"}],
            num_predict=420,
            keep_alive="180s",
            think=think,
        )
        txt_v1 = _strip_think_blocks(str((rv1.get("message") or {}).get("content", "")).strip())
        if "anti_degenerate_sanity_probe" not in probes:
            words_v = [txt_v1[i:i+6] for i in range(0, max(1, len(txt_v1) - 5), 3)]
            uniq_v = len(set(words_v)) / max(1, len(words_v))
            probes["anti_degenerate_sanity_probe"] = {
                "passed": len(txt_v1) >= 12 and uniq_v >= 0.35,
                "response_len": len(txt_v1),
                "unique_ngram_ratio": round(uniq_v, 3),
                "sample": txt_v1[:160],
            }
        probes["vericut_autodiff_probe"] = evaluate_vericut_autodiff_probe(txt_v1)

        rv2 = _probe_chat(
            tag,
            [{"role": "user", "content": (
                '已知 VERICUT 工程 XML 为 <Unit>inch</Unit> 且 Setup 主轴方向 Up=Z+。'
                '请说明：(1) 该工程单位是 inch 还是 millimeter；'
                '(2) 该 Z-up / G54 坐标系能否直接等价套用 SOLIDWORKS 2021 默认的前/上/右基准面（Front/Top/Right）？为什么？'
            )}],
            num_predict=420,
            keep_alive="180s",
            think=think,
        )
        txt_v2 = str((rv2.get("message") or {}).get("content", "")).strip()
        probes["vericut_coordinate_unit_probe"] = evaluate_vericut_coordinate_unit_probe(txt_v2)

        vericut_tools = [{
            "type": "function",
            "function": {
                "name": "cadcam_vericut_simulate",
                "description": "Run CGTech VERICUT 9.6 CNC machine simulation and Auto-Diff gouge inspection.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["run_simulation", "autodiff_check", "inspect_project"]},
                        "project_path": {"type": "string"},
                    },
                    "required": ["action", "project_path"],
                },
            },
        }]
        rv3 = _probe_chat(
            tag,
            [{"role": "user", "content": "调用 cadcam_vericut_simulate 工具对 E:/training/session_101m.vcproject 执行 Auto-Diff 偏差检测（autodiff_check）。"}],
            num_predict=256,
            keep_alive="180s",
            tools=vericut_tools,
            think=think,
        )
        msg_v3 = rv3.get("message", {})
        tcalls_v3 = msg_v3.get("tool_calls") or []
        txt_v3 = str(msg_v3.get("content", ""))
        v_eval = evaluate_tool_call_arguments(
            tcalls_v3,
            txt_v3,
            expected_name="cadcam_vericut_simulate",
            expected_nums=(),
            expected_substrings=("session_101m.vcproject",),
        )
        probes["vericut_tool_call_probe"] = {
            "passed": bool(v_eval["passed"]),
            "tool_calls_count": len(tcalls_v3),
            "parsed_args": v_eval.get("parsed_args"),
            "reason": v_eval.get("reason"),
            "raw_snippet": txt_v3[:160],
            "full_response": txt_v3,
        }

    return probes


def _strip_think_blocks(text: str) -> str:
    import re
    cleaned = re.sub(r"<think>.*?</think>", "", str(text or ""), flags=re.S).strip()
    return cleaned or str(text or "").strip()


def _with_full_response(result: dict, visible: str) -> dict:
    # §8.2 根因分析需要完整原始输出；sample 只是凭证片段。失败路径若只带
    # segment，回执 sample 为空，失败无法自证（2026-11-16 sw_coordinate 悬案根因）。
    result["full_response"] = visible
    return result


def _looks_truncated(text: str) -> bool:
    """判定回答是否在推导中途被 token 预算截断（而非模型真的没写结论）。

    2026-11-15 实测：Lamé 探针 num_predict=260 时，模型正确写出 σ_θ=33.33 后
    正好在推导 σ_r 的中途被截断，旧判分器把「被截断」误报成「模型没答对」。
    截断必须单独报出来，否则会把测量缺陷伪装成模型缺陷（AGENTS.md §8.1）。
    """
    visible = _strip_think_blocks(text).rstrip()
    if not visible:
        return False
    if re.search(r"(?:=|\\cdot|\\times|\+|-|\(|\[|\\frac\{[^}]*$|\\sqrt\{[^}]*$)", visible[-3:]):
        return True
    if visible.count("$$") % 2 == 1:
        return True
    if visible.count(r"\(") > visible.count(r"\)") or visible.count(r"\[") > visible.count(r"\]"):
        return True
    if len(visible) > 80 and not re.search(r"[。．.!！?？:：;；)）\]】]\s*$", visible):
        return True
    return False


def evaluate_tool_call_arguments(
    tool_calls,
    raw_text: str,
    *,
    expected_name: str = "cadcam_universal_geometry",
    expected_nums: tuple = (80.0, 120.0),
    expected_substrings: tuple = (),
) -> dict:
    """Validate tool selection, numeric arguments, and required string arguments."""
    import re

    parsed_candidates = []
    for tc in (tool_calls or []):
        if not isinstance(tc, dict):
            continue
        fn = tc.get("function") or {}
        if fn.get("name") != expected_name:
            continue
        args = fn.get("arguments", {})
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                pass
        parsed_candidates.append(args)

    if not parsed_candidates and "<tool_call>" in str(raw_text or ""):
        for blk in re.findall(r"<tool_call>(.*?)</tool_call>", str(raw_text), flags=re.S):
            try:
                obj = json.loads(blk.strip())
                if isinstance(obj, dict) and obj.get("name") == expected_name:
                    parsed_candidates.append(obj.get("arguments", {}))
            except Exception:
                pass

    if not parsed_candidates:
        return {"passed": False, "parsed_args": None, "reason": f"missing_tool:{expected_name}"}

    for args in parsed_candidates:
        if not isinstance(args, dict):
            continue
        nums_found = []
        str_blob_parts = []
        for val in args.values():
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                nums_found.append(float(val))
            elif isinstance(val, str):
                str_blob_parts.append(val.lower())
                nums_found.extend(float(x) for x in re.findall(r"[-+]?\d+(?:\.\d+)?", val))
        str_blob = " ".join(str_blob_parts)
        nums_ok = all(any(abs(v - exp) <= 1e-2 for v in nums_found) for exp in expected_nums)
        strs_ok = all(str(sub).lower() in str_blob for sub in expected_substrings)
        if nums_ok and strs_ok:
            return {"passed": True, "parsed_args": args, "reason": "ok"}

    return {"passed": False, "parsed_args": parsed_candidates[0], "reason": "wrong_or_missing_numeric_or_string_args"}


def evaluate_sw_coordinate_probe(text: str) -> dict:
    """Verify SOLIDWORKS 2021 Front(XY/+Z), Top(XZ/+Y), Right(YZ/+X) plane normals.

    2026-11-15 修正（判分器缺陷，非模型缺陷）：
      旧实现取「该平面最后一次出现」作锚点（matches[-1]）。答案末尾的枚举式提及
      （例："SOLIDWORKS 中 Front/Top/Right 基准面的法向是全局定义的…"）会劫持锚点；
      而 Top 的锚点恰好落在 "front/top/right" 中 front 之后 6 个字符处，使 front 的
      判定窗口被截成 6 个字符 "front/"，正确答案被误判 missing_normal:front
      （实测 v3 裸轨模型 3/3 给出完全正确的 Z+/Y+/X+，却被判 FAIL）。
      新实现按「定义窗口」判定：逐个候选出现，取「该出现 → 同行结束 / 下一个其它平面词」
      为界的窗口；同行内没有向量时允许顺延一行（下一行不含其它平面词才允许），
      取第一个含法向量的窗口作为定义窗口，再在该窗口内做正/负法向判定。
      判定标准不变：法向错误、平面互换、缺平面、只有枚举式提及仍一律判 FAIL。
    """
    import re

    visible = _strip_think_blocks(text)
    if not visible:
        return {"passed": False, "reason": "empty_response", "sample": "", "full_response": ""}
    low = visible.lower()

    plane_pats = (
        ("front", r"(?:front\s*(?:plane)?|前视基准面|前视面|前视图)"),
        ("top", r"(?:top\s*(?:plane)?|上视基准面|上视面|俯视图)"),
        ("right", r"(?:right\s*(?:plane)?|右视基准面|右视面|右视图)"),
    )
    specs = {
        "front": (r"(?:\+z|z\+(?![a-z])|\bz\s*轴|\bxy\b|\(\s*0\s*,\s*0\s*,\s*\+?1\s*\))",
                  r"(?:-z|z-(?![a-z])|\(\s*0\s*,\s*0\s*,\s*-1\s*\)|\bxz\b|\byz\b|\+y|y\+(?![a-z])|\(\s*0\s*,\s*1\s*,\s*0\s*\)|\+x|x\+(?![a-z])|\(\s*1\s*,\s*0\s*,\s*0\s*\))"),
        "top": (r"(?:\+y|y\+(?![a-z])|\by\s*轴|\bxz\b|\(\s*0\s*,\s*\+?1\s*,\s*0\s*\))",
                r"(?:-y|y-(?![a-z])|\(\s*0\s*,\s*-1\s*,\s*0\s*\)|\bxy\b|\byz\b|\+z|z\+(?![a-z])|\(\s*0\s*,\s*0\s*,\s*1\s*\)|\+x|x\+(?![a-z])|\(\s*1\s*,\s*0\s*,\s*0\s*\))"),
        "right": (r"(?:\+x|x\+(?![a-z])|\bx\s*轴|\byz\b|\(\s*\+?1\s*,\s*0\s*,\s*0\s*\))",
                  r"(?:-x|x-(?![a-z])|\(\s*-1\s*,\s*0\s*,\s*0\s*\)|\bxy\b|\bxz\b|\+y|y\+(?![a-z])|\(\s*0\s*,\s*1\s*,\s*0\s*\)|\+z|z\+(?![a-z])|\(\s*0\s*,\s*0\s*,\s*1\s*\))"),
    }

    occurrences = {}
    for key, pat in plane_pats:
        occurrences[key] = [(m.start(), m.end()) for m in re.finditer(pat, low)]

    def _line_end(idx: int) -> int:
        nl = low.find("\n", idx)
        return len(low) if nl < 0 else nl

    def _next_other_plane(start: int, exclude: str) -> int:
        best = len(low)
        for other_key, _pat in plane_pats:
            if other_key == exclude:
                continue
            for s, _e in occurrences[other_key]:
                if s > start:
                    if s < best:
                        best = s
                    break
        return best

    for key, _pat in plane_pats:
        occ = occurrences[key]
        if not occ:
            return _with_full_response({"passed": False, "reason": f"missing_plane:{key}", "sample": visible[:160]}, visible)
        pos_pat, neg_pat = specs[key]
        chosen = None
        for start, _end in occ:
            eol = _line_end(start)
            nxt = _next_other_plane(start, key)
            seg = low[start:min(eol, nxt, start + 120)]
            if not (re.search(pos_pat, seg) or re.search(neg_pat, seg)):
                # 同行没有向量：允许顺延一行，但下一行不得出现其它平面词
                if eol < nxt:
                    next_line_end = _line_end(eol + 1)
                    next_line = low[eol + 1:next_line_end]
                    other_hit = any(
                        s > eol and s < next_line_end
                        for other_key, _p in plane_pats if other_key != key
                        for s, _e in occurrences[other_key]
                    )
                    if not other_hit and next_line.strip():
                        seg2 = low[start:min(next_line_end, start + 120)]
                        if re.search(pos_pat, seg2) or re.search(neg_pat, seg2):
                            seg = seg2
            if re.search(pos_pat, seg) or re.search(neg_pat, seg):
                chosen = seg
                break
        if chosen is None:
            return _with_full_response({"passed": False, "reason": f"missing_normal:{key}",
                    "sample": visible[:160], "segment": low[occ[0][0]:occ[0][0] + 80]}, visible)
        if not re.search(pos_pat, chosen):
            return _with_full_response({"passed": False, "reason": f"missing_normal:{key}", "sample": visible[:160], "segment": chosen[:80]}, visible)
        if re.search(neg_pat, chosen):
            return _with_full_response({"passed": False, "reason": f"wrong_normal_axis:{key}", "sample": visible[:160], "segment": chosen[:80]}, visible)
    return _with_full_response({"passed": True, "reason": "ok", "sample": visible[:160]}, visible)


def evaluate_lame_stress_probe(text: str) -> dict:
    """Verify Di=60, Do=120, Pi=20 => sigma_theta ~= 33.33 MPa and sigma_r = -20 MPa.

    2026-11-15 修正（判分器缺陷，非模型缺陷）：
      1. 负号字符集过窄 —— 旧式只认 ASCII '-'，而模型常写 U+2212 '−'（数学减号）
         或 U+FF0D '－'，导致正确答案被判 missing_negative_sigma_r_-20；
      2. 不区分「答案被 token 预算截断」与「模型确实没给 σ_r」——前者是测量缺陷，
         必须单列 truncated 原因，不能伪装成模型缺陷。
    物理口径不变：σ_θ≈33.33 MPa 且 σ_r=-20 MPa，且不得声称 σ_θ=60 MPa。
    """
    import re

    visible = _strip_think_blocks(text)
    if not visible:
        return {"passed": False, "reason": "empty_response", "sample": "", "full_response": ""}
    nums = [float(x) for x in re.findall(r"[-+]?\d+(?:\.\d+)?", visible)]
    has_hoop = any(abs(v - 33.33) <= 0.15 for v in nums)
    # 负号字符集：ASCII '-' / U+2212 '−' / U+FF0D '－'
    has_neg_radial = bool(re.search(r"(?:-|\u2212|\uff0d)\s*20(?:\.0+)?(?!\d|\.\d)", visible))
    has_60_confusion = bool(re.search(r"(?:σ_θ|sigma_?[tθ]|环向应力)\s*[=:≈为]\s*60(?:\.0+)?\b", visible, flags=re.I))
    truncated = _looks_truncated(visible)
    passed = has_hoop and has_neg_radial and not has_60_confusion
    reasons = []
    if not has_hoop:
        reasons.append("missing_sigma_theta_33.33")
    if not has_neg_radial:
        reasons.append(
            "truncated_before_sigma_r_-20" if truncated else "missing_negative_sigma_r_-20"
        )
    if has_60_confusion:
        reasons.append("claimed_sigma_theta_60")
    out = {
        "passed": passed,
        "reason": "ok" if passed else ",".join(reasons),
        "sample": visible[:160],
    }
    if truncated:
        out["truncated"] = True
    return _with_full_response(out, visible)


def evaluate_fanuc_g71_safety_probe(text: str) -> dict:
    """Verify G71/G70 cycle completeness, non-zero spindle/feed, and zero rapid Z-plunge."""
    import re

    visible = _strip_think_blocks(text)
    up = visible.upper()
    required = ["G71", "G70", "T01", "M30"]
    missing = [tok for tok in required if tok not in up]
    if not re.search(r"\bM0?3\b", up):
        missing.append("M03")
    if not re.search(r"\bG71\b[^\n]*\bP\d+[^\n]*\bQ\d+", up):
        missing.append("G71_PQ")
    spindles = [int(x) for x in re.findall(r"\bS(\d+)\b", up)]
    feeds = [float(x) for x in re.findall(r"\bF(\d+(?:\.\d+)?)\b", up)]
    if not spindles or any(s <= 0 for s in spindles):
        missing.append("valid_S>0")
    if not feeds or any(f <= 0 for f in feeds):
        missing.append("valid_F>0")

    rapid_plunge = False
    for line in up.splitlines():
        if re.search(r"\bG0?0\b", line) and re.search(r"\bZ-\d", line):
            rapid_plunge = True
            break
    if rapid_plunge:
        missing.append("unsafe_G00_negative_Z_plunge")

    passed = not missing
    return _with_full_response({
        "passed": passed,
        "reason": "ok" if passed else ",".join(missing),
        "sample": visible[:180],
    }, visible)


def evaluate_vericut_autodiff_probe(text: str) -> dict:
    """Verify VERICUT 9.6 Auto-Diff color mapping (Red=Gouge+Stop, Blue=Excess, Green=InTol)."""
    import re

    visible = _strip_think_blocks(text)
    low = visible.lower()
    rules = {
        "red": (
            r"(?:过切|超切|碰撞|gouge)",
            # bare "excess" is NOT a red-negative: the correct term
            # "excess material removal" (gouge) contains it.
            r"(?:合格|公差内|in[- ]?tolerance|残料)",
        ),
        "blue": (
            r"(?:残料|余量|未切|欠切|excess)",
            r"(?:过切|gouge|合格|in[- ]?tolerance)",
        ),
        "green": (
            r"(?:合格|公差内|正常|达标|通过|in[- ]?tolerance|within\s+tolerance)",
            r"(?:过切|gouge|致命)",
        ),
    }
    _color_toks = (
        ("red", r"(?:红色|红|\bred\b)"),
        ("blue", r"(?:蓝色|蓝|\bblue\b)"),
        ("green", r"(?:绿色|绿|\bgreen\b)"),
    )

    def _next_other_color(start: int, exclude: str) -> int:
        best = len(low)
        for other_key, other_tok in _color_toks:
            if other_key == exclude:
                continue
            for m in re.finditer(other_tok, low):
                if start < m.start() < best:
                    best = m.start()
        return best

    anchors = []
    for key, tok in (
        ("red", r"(?:红色|红|\bred\b)"),
        ("blue", r"(?:蓝色|蓝|\bblue\b)"),
        ("green", r"(?:绿色|绿|\bgreen\b)"),
    ):
        # Strictly linear-time O(n) pattern (no nested quantifiers) for bullet/heading/table/next-line-bullet definitions
        def_matches = list(
            re.finditer(
                rf"(?:^|\n)[ \t#*\-•|>\d.\u2022\U0001f534\U0001f7e1\U0001f535\U0001f7e2\u2705\U0001f7e6\U0001f7e9]*[^\w\n\s]{{0,4}}[ \t]{{0,4}}{tok}"
                rf"(?:[ \t]{{0,4}}\([^)\n]{{1,24}}\))?[ \t*]{{0,6}}(?:(?:[：:=＝|]|代表|表示|is\b|means\b)|[ \t]*\r?\n[ \t*\-•]{{1,8}}(?:代表|表示|含义|[：:=＝]))",
                low,
            )
        )
        matches = list(re.finditer(tok, low))
        if not matches:
            return _with_full_response({"passed": False, "reason": f"missing_color:{key}", "sample": visible[:180]}, visible)
        if def_matches:
            chosen = def_matches[0]
        else:
            # 2026-11-16 根因修复（复用 evaluate_sw_coordinate_probe 已验证原则）：
            # 旧回退 matches[-1] 取「该色最后一次出现」，会被答案末尾的负面警示提及
            # （"严禁将红色误判为合格或忽略"）劫持锚点；当定义用全角括号（Red）+加粗 **
            # 使 def_pat 未命中时，完整正确的三色答案被误判 missing_meaning:red。
            # 改取「窗口（→下一其它色 / +120 字）内含该色正/负语义的第一个出现」作定义锚点。
            # 判定标准不变：缺色、语义互换、只有枚举式提及仍一律判红。
            pos_pat, neg_pat = rules[key]
            chosen = None
            for m in matches:
                start = m.start()
                window = low[start:min(_next_other_color(start, key), start + 120)]
                if re.search(pos_pat, window) or re.search(neg_pat, window):
                    chosen = m
                    break
            if chosen is None:
                chosen = matches[0]
        anchors.append((chosen.start(), chosen.end(), key))
    anchors.sort(key=lambda item: item[0])

    _neg_ad_prefix = re.compile(r"(?:并非|不是|非|无|不含|不存在|绝非|而非|避免)$")
    for idx, (pos, def_end, key) in enumerate(anchors):
        end = anchors[idx + 1][0] if idx + 1 < len(anchors) else len(low)
        raw_tail = low[pos:min(end, max(pos + 120, def_end + 100))]
        lead_stripped = len(raw_tail) - len(raw_tail.lstrip("\r\n \t"))
        tail = raw_tail[lead_stripped:]
        # Start clause-end scan after the matched separator so heading+\n-bullet doesn't cut before its bullet line.
        scan_from = max(0, (def_end - pos) - lead_stripped)
        cut = re.search(r"[\n。；;]", tail[scan_from:])
        seg = tail[:scan_from + cut.start()] if cut else tail
        pos_pat, neg_pat = rules[key]
        # 2026-11-16（E5）：正语义也必须**否定感知**。旧实现对正语义用裸 search，
        # 于是「代表：不是过切，也不是残料」里的「残料」被当成正语义存在 ⇒ 判 PASS
        # （假绿）。负语义侧本来就有否定前缀守卫，这里补齐对称的一侧。
        pos_ok = False
        for pos_m in re.finditer(pos_pat, seg):
            _pref = seg[max(0, pos_m.start() - 6):pos_m.start()].strip()
            if not _neg_ad_prefix.search(_pref):
                pos_ok = True
                break
        if not pos_ok:
            # 2026-11-16（E5）：正语义缺失但**负语义就在同一段里**（例：蓝色段写
            # 「过切（Gouge）」）是**语义互换**，不是「意思没写」。两者都判红，
            # 但归因必须区分，否则回执无法定位模型到底犯了哪种错（AGENTS.md §8.2）。
            for neg_m in re.finditer(neg_pat, seg):
                pref = seg[max(0, neg_m.start() - 6):neg_m.start()].strip()
                if not _neg_ad_prefix.search(pref):
                    return _with_full_response({"passed": False, "reason": f"swapped_meaning:{key}", "sample": visible[:180], "segment": seg[:80]}, visible)
            return _with_full_response({"passed": False, "reason": f"missing_meaning:{key}", "sample": visible[:180], "segment": seg[:80]}, visible)
        for neg_m in re.finditer(neg_pat, seg):
            pref = seg[max(0, neg_m.start() - 6):neg_m.start()].strip()
            if not _neg_ad_prefix.search(pref):
                return _with_full_response({"passed": False, "reason": f"swapped_meaning:{key}", "sample": visible[:180], "segment": seg[:80]}, visible)

    has_remedy = bool(re.search(r"(?:停止|停机|修.*刀路|调整|排查|重生成|stop|fix|modify)", low))
    if not has_remedy:
        return _with_full_response({"passed": False, "reason": "missing_red_gouge_remediation", "sample": visible[:180]}, visible)

    return _with_full_response({"passed": True, "reason": "ok", "sample": visible[:180]}, visible)


def evaluate_vericut_coordinate_unit_probe(text: str) -> dict:
    """Verify VERICUT unit preservation (inch) and Y-up vs Z-up isolation.

    2026-11-15 修正（判分器缺陷，非模型缺陷）：
      1. `has_isolation` 否定词表过窄 —— 模型正确写法「**不得**擅自改写为 millimeter」
         「**不宜**直接套用」被判 missing_coordinate_isolation；
      2. `_neg_prefix_re` 同样缺「不得」，导致正确答案「不得直接等价套用」反而被
         claimed_coordinates_identical 拦下（**镜像缺陷**：正确表述被判错）。
    门禁口径不变：必须认定 inch 且不得改写成毫米；必须主张 Z-up/G54 与
    SOLIDWORKS 前/上/右基准面**不可直接等价套用**；声称完全等价者一律判红。
    """
    import re

    visible = _strip_think_blocks(text)
    low = visible.lower()
    if not re.search(r"(?:\binch\b|英寸)", low):
        return _with_full_response({"passed": False, "reason": "missing_unit_inch", "sample": visible[:180]}, visible)
    _neg_prefix_re = re.compile(
        r"(?:不可|不能|无法|严禁|并非|绝非|而非|不是|不得|不|非|切忌|切勿|禁止|勿|不宜|应避免)$"
    )
    for m in re.finditer(r"(?:单位(?:为|是)[:：\s]*millimeter|单位(?:为|是)[:：\s]*毫米|使用毫米)", low):
        prefix = low[max(0, m.start() - 6):m.start()].strip()
        if not _neg_prefix_re.search(prefix):
            return _with_full_response({"passed": False, "reason": "wrong_unit_millimeter", "sample": visible[:180]}, visible)

    has_isolation = bool(re.search(
        r"(?:不能|不可|无法|不同|不一致|不等价|非等价|严禁|不应|不得|禁止|切忌|切勿|勿|不宜|"
        r"不能直接|不可直接|无法直接|不得直接|不应直接|严禁直接|"
        r"应避免|保持一致|必须一致|须保持|必须保持|y-?up|z-?up)",
        low,
    ))
    if not has_isolation:
        return _with_full_response({"passed": False, "reason": "missing_coordinate_isolation", "sample": visible[:180]}, visible)
    for m in re.finditer(r"(?:完全等价|完全相同|可直接等价套用|可直接套用|坐标系一致，?可直接)", low):
        prefix = low[max(0, m.start() - 6):m.start()].strip()
        if not _neg_prefix_re.search(prefix):
            return _with_full_response({"passed": False, "reason": "claimed_coordinates_identical", "sample": visible[:180]}, visible)

    out = {"passed": True, "reason": "ok", "sample": visible[:180]}
    if _looks_truncated(visible):
        out["truncated"] = True
    return _with_full_response(out, visible)


def verify_deployed_model_with_memory(
    tag: str,
    *,
    probe_profile: str = "all",
    think: Optional[bool] = False,
) -> dict:
    """Honest dual-track verification: base raw probes + Hindsight memory-augmented probes."""
    resolved = _resolve_probe_profile(tag, probe_profile)
    raw_probes = verify_deployed_model(tag, probe_profile=resolved, think=think)

    try:
        from virtu_omni.memory.hindsight_adapter import VirtuHindsightMemory
        h_mem = VirtuHindsightMemory()
    except Exception:
        h_mem = None

    def _ask_with_mem(prompt: str, *, num_predict: int = 280) -> str:
        mem_ctx = ""
        if h_mem is not None:
            mem_ctx = h_mem.build_domain_memory_context(
                prompt,
                bank_ids=["virtu_cad_cam", "virtu_cnc_machining", "virtu_quality_audit", "default"],
                max_items=4,
                update_stats=False,
                include_invariants=True,
                max_chars=1800,
            )
        sys_txt = DEFAULT_SYSTEM_PROMPT + (f"\n\n{mem_ctx}" if mem_ctx else "")
        resp = _probe_chat(
            tag,
            [{"role": "system", "content": sys_txt}, {"role": "user", "content": prompt}],
            num_predict=num_predict,
            keep_alive="180s",
            think=think,
        )
        return str((resp.get("message") or {}).get("content", "")).strip()

    mem_probes = {}
    if resolved in ("general", "all"):
        mem_probes["sw_coordinate_probe"] = evaluate_sw_coordinate_probe(
            _ask_with_mem("列举 SOLIDWORKS 2021 的 Front/Top/Right 三个默认基准面法向。", num_predict=240)
        )
        mem_probes["lame_stress_probe"] = evaluate_lame_stress_probe(
            _ask_with_mem(
                "按 Lamé 厚壁圆筒理论：内径 Di=60 mm，外径 Do=120 mm，内压 Pi=20 MPa。"
                "计算内壁环向应力 σ_θ（保留 2 位小数）与径向应力 σ_r，单位 MPa。",
                num_predict=420,
            )
        )
        mem_probes["fanuc_g71_safety_probe"] = evaluate_fanuc_g71_safety_probe(
            _ask_with_mem(
                "用 FANUC ISO/G 格式为 Ø60 棒料编写 G71 粗车+G70 精车台阶轴程序"
                "（第一台阶 Ø38 长 20 mm，总长 45 mm），含 G50 S1800、G96 S150 M03、T0101、F0.25 与 M30，只输出程序。",
                num_predict=340,
            )
        )
    if resolved in ("vericut96", "all"):
        mem_probes["vericut_autodiff_probe"] = evaluate_vericut_autodiff_probe(
            _ask_with_mem(
                "说明 VERICUT 9.6 Auto-Diff 偏差图中红色、蓝色、绿色分别代表什么？以及发现红色时应如何处置？",
                num_predict=420,
            )
        )
        mem_probes["vericut_coordinate_unit_probe"] = evaluate_vericut_coordinate_unit_probe(
            _ask_with_mem(
                '已知 VERICUT 工程 XML 为 <Unit>inch</Unit> 且 Setup 主轴方向 Up=Z+。'
                '请说明：(1) 该工程单位是 inch 还是 millimeter；'
                '(2) 该 Z-up / G54 坐标系能否直接等价套用 SOLIDWORKS 2021 默认的前/上/右基准面（Front/Top/Right）？为什么？',
                num_predict=420,
            )
        )

    return {
        "probe_profile": resolved,
        "raw_probes": raw_probes,
        "memory_augmented_probes": mem_probes,
        "raw_all_passed": all(bool(p.get("passed")) for p in raw_probes.values()),
        "memory_augmented_all_passed": all(bool(p.get("passed")) for p in mem_probes.values()) if mem_probes else None,
        "basis": "measured_dual_track",
    }


# 2026-11-15 双轨验收口径（用户决策）：生产配置 = 记忆增强轨 ⇒ 验收门以记忆轨为准；
# 但裸权重（raw）轨的逐项明细必须完整留在凭证里，缺陷不被掩盖、不被静默吞掉。
STATUS_DEPLOYED_VERIFIED = "DEPLOYED_VERIFIED"
STATUS_MEMORY_AUGMENTED_VERIFIED = "DEPLOYED_VERIFIED_MEMORY_AUGMENTED"
STATUS_PROBE_FAILED = "PROBE_FAILED"


def dual_track_verdict(raw_ok: bool, mem_ok, raw_probes: dict, mem_probes) -> dict:
    """把双轨实测结果折算成显式双轨验收结论。

    返回：
      status                  顶层验收结论
      acceptance_gate         "memory_augmented_track" | "raw_track"
      raw_status              PASSED / FAILED
      memory_status           PASSED / FAILED / NOT_RUN
      raw_failed_probes       裸轨失败项清单
      memory_failed_probes    记忆轨失败项清单

    规则：
      - 未跑记忆轨（mem_ok is None）⇒ 只看 raw；
      - raw 与记忆轨全过            ⇒ DEPLOYED_VERIFIED；
      - raw 挂、记忆轨全过          ⇒ DEPLOYED_VERIFIED_MEMORY_AUGMENTED（验收门 = 生产配置）；
      - 其余（记忆轨挂，含 raw 也挂）⇒ PROBE_FAILED。
    """
    raw_failed = sorted(k for k, v in (raw_probes or {}).items() if not bool(v.get("passed")))
    mem_failed = sorted(k for k, v in (mem_probes or {}).items() if not bool(v.get("passed"))) if mem_probes else []
    if mem_ok is None:
        status = STATUS_DEPLOYED_VERIFIED if raw_ok else STATUS_PROBE_FAILED
        gate = "raw_track"
        mem_status = "NOT_RUN"
    elif raw_ok and mem_ok:
        status = STATUS_DEPLOYED_VERIFIED
        gate = "memory_augmented_track"
        mem_status = "PASSED"
    elif mem_ok:
        status = STATUS_MEMORY_AUGMENTED_VERIFIED
        gate = "memory_augmented_track"
        mem_status = "PASSED"
    else:
        status = STATUS_PROBE_FAILED
        gate = "memory_augmented_track"
        mem_status = "FAILED"
    return {
        "status": status,
        "acceptance_gate": gate,
        "raw_status": "PASSED" if raw_ok else "FAILED",
        "memory_status": mem_status,
        "raw_failed_probes": raw_failed,
        "memory_failed_probes": mem_failed,
    }


def run_selftest() -> int:
    """离线自检：receipt 检验、lineage_gate 维度/Instruct 拦截、Modelfile 模板/字节检查、标签覆写防护、safe_extract。"""
    with tempfile.TemporaryDirectory(prefix="virtu_deploy_selftest_") as td:
        # 1. lineage_gate 正反测试
        qwen3_dir = os.path.join(td, "Qwen3-8B")
        os.makedirs(qwen3_dir, exist_ok=True)
        with open(os.path.join(qwen3_dir, "config.json"), "w", encoding="utf-8") as f:
            json.dump({"_name_or_path": "Qwen/Qwen3-8B", "model_type": "qwen3", **EXPECTED_BASE_SPEC}, f)

        adapter_dir = os.path.join(td, "virtu_lora_adapter")
        os.makedirs(adapter_dir, exist_ok=True)
        with open(os.path.join(adapter_dir, "adapter_config.json"), "w", encoding="utf-8") as f:
            json.dump({"base_model_name_or_path": "/root/models/Qwen3-8B"}, f)
        wfile = os.path.join(adapter_dir, "adapter_model.safetensors")
        with open(wfile, "wb") as wf:
            wf.write(b"dummy-lora-weights")
        with open(os.path.join(adapter_dir, "training_receipt.json"), "w", encoding="utf-8") as rf:
            json.dump({
                "status": "COMPLETED",
                "base_model": "/root/models/Qwen3-8B",
                "adapter_sha256": sha256_file(wfile),
                "dataset_sha256": "c" * 64,
            }, rf)

        rdata, got_ad = verify_deliverable_receipt(td)
        assert rdata["status"] == "COMPLETED" and got_ad == adapter_dir
        lineage_gate(qwen3_dir, adapter_dir)

        q25_dir = os.path.join(td, "Qwen25-7B")
        os.makedirs(q25_dir, exist_ok=True)
        with open(os.path.join(q25_dir, "config.json"), "w", encoding="utf-8") as f:
            json.dump({"_name_or_path": "Qwen/Qwen2.5-7B-Instruct", "model_type": "qwen2", "hidden_size": 3584, "num_hidden_layers": 28, "vocab_size": 152064}, f)
        try:
            lineage_gate(q25_dir)
            raise AssertionError("lineage_gate 未拦截 Qwen2.5-7B-Instruct")
        except RuntimeError:
            pass

        # 2. build_modelfile 校验
        dummy_gguf = os.path.join(td, "virtu-master.gguf")
        mf_txt = build_modelfile(dummy_gguf)
        expected_from = f"FROM {os.path.abspath(dummy_gguf).replace(chr(92), '/')}"
        assert mf_txt.splitlines()[0] == expected_from
        assert ".Tools" in mf_txt and "<tool_call>" in mf_txt and "<tools>" in mf_txt
        assert "num_gpu" not in mf_txt.lower()
        assert len(DEFAULT_SYSTEM_PROMPT.encode("utf-8")) <= 702

        # 3. 标签覆写门禁
        try:
            assert_tag_writable("virtu-master:latest", allow_overwrite=False, existing_tags=["virtu-master:latest"])
            raise AssertionError("assert_tag_writable 未拦截已有标签覆盖")
        except SystemExit:
            pass
        assert_tag_writable("virtu-master:latest", allow_overwrite=True, existing_tags=["virtu-master:latest"])
        assert_tag_writable("virtu-master-vnext:latest", allow_overwrite=False, existing_tags=["virtu-master:latest"])

        # 4. safe_extract 防穿越
        import io
        bad_tar = os.path.join(td, "bad.tar.gz")
        with tarfile.open(bad_tar, "w:gz") as tar:
            ti = tarfile.TarInfo("../outside.txt")
            ti.size = 3
            tar.addfile(ti, io.BytesIO(b"123"))
        with tarfile.open(bad_tar, "r:gz") as tar:
            try:
                safe_extract(tar, os.path.join(td, "extract"))
                raise AssertionError("safe_extract 未拦截路径穿越")
            except ValueError:
                pass

        # 5. VERICUT 9.6 探针评分器正反自检
        assert evaluate_vericut_autodiff_probe(
            "红色表示过切（致命错误，必须立即停止并修改刀路）；蓝色表示残料过多；绿色表示公差内合格。"
        )["passed"] is True
        assert evaluate_vericut_autodiff_probe(
            "红色表示公差内合格；绿色表示过切。"
        )["passed"] is False
        assert evaluate_vericut_coordinate_unit_probe(
            "单位为 inch（英寸）；不能直接等价套用 SOLIDWORKS 2021 默认 Y-up 基准面，因为 VERICUT/CNC 为 Z-up/G54。"
        )["passed"] is True
        assert evaluate_vericut_coordinate_unit_probe(
            "单位为毫米；两者完全等价，可直接等价套用。"
        )["passed"] is False
        v_tc = [{"function": {"name": "cadcam_vericut_simulate", "arguments": '{"action":"autodiff_check","project_path":"E:/training/session_101m.vcproject"}'}}]
        assert evaluate_tool_call_arguments(
            v_tc, "", expected_name="cadcam_vericut_simulate", expected_nums=(), expected_substrings=("session_101m.vcproject",)
        )["passed"] is True
        assert evaluate_tool_call_arguments(
            v_tc, "", expected_name="cadcam_vericut_simulate", expected_nums=(), expected_substrings=("other.vcproject",)
        )["passed"] is False

        # 6. 双轨验收口径（2026-11-15 用户决策：生产配置 = 记忆增强轨）
        ok_raw = {"a": {"passed": True}, "b": {"passed": True}}
        bad_raw = {"a": {"passed": True}, "b": {"passed": False}}
        ok_mem = {"m": {"passed": True}}
        bad_mem = {"m": {"passed": False}}
        v = dual_track_verdict(True, None, ok_raw, None)
        assert v["status"] == STATUS_DEPLOYED_VERIFIED and v["acceptance_gate"] == "raw_track"
        assert v["memory_status"] == "NOT_RUN" and v["raw_failed_probes"] == []
        v = dual_track_verdict(False, None, bad_raw, None)
        assert v["status"] == STATUS_PROBE_FAILED and v["raw_failed_probes"] == ["b"]
        v = dual_track_verdict(True, True, ok_raw, ok_mem)
        assert v["status"] == STATUS_DEPLOYED_VERIFIED and v["memory_status"] == "PASSED"
        v = dual_track_verdict(False, True, bad_raw, ok_mem)
        assert v["status"] == STATUS_MEMORY_AUGMENTED_VERIFIED
        assert v["acceptance_gate"] == "memory_augmented_track"
        assert v["raw_status"] == "FAILED" and v["memory_status"] == "PASSED"
        assert v["raw_failed_probes"] == ["b"] and v["memory_failed_probes"] == []
        v = dual_track_verdict(False, False, bad_raw, bad_mem)
        assert v["status"] == STATUS_PROBE_FAILED and v["memory_status"] == "FAILED"
        v = dual_track_verdict(True, False, ok_raw, bad_mem)
        assert v["status"] == STATUS_PROBE_FAILED and v["raw_status"] == "PASSED"

    print("[SELFTEST] PASS: receipt_gate / lineage_gate / modelfile_17tools / overwrite_guard / safe_extract / vericut_probes / dual_track_verdict")
    return 0


def deploy(args) -> dict:
    if not os.path.exists(args.deliverable):
        raise SystemExit(f"[FATAL] 交付压缩包不存在: {args.deliverable}")

    if args.deliverable.endswith(".sha256"):
        raise SystemExit("[FATAL] --deliverable 应传入 .tar.gz 文件而非 .sha256")
    sha_sidecar = args.deliverable + ".sha256"
    if os.path.exists(sha_sidecar):
        exp_sha = open(sha_sidecar, "r", encoding="utf-8").read().strip().split()[0]
        act_sha = sha256_file(args.deliverable)
        if exp_sha.lower() != act_sha.lower():
            raise SystemExit(f"[FATAL] 交付包 SHA256 校验失败: expected={exp_sha[:16]} actual={act_sha[:16]}")

    assert_tag_writable(args.tag, allow_overwrite=args.allow_overwrite)

    work_dir = os.path.abspath(args.work_dir)
    unpack_dir = os.path.join(work_dir, "unpacked")
    merged_dir = os.path.join(work_dir, "merged_hf")
    if os.path.exists(unpack_dir):
        shutil.rmtree(unpack_dir)
    if os.path.exists(merged_dir):
        shutil.rmtree(merged_dir)

    print(f"[Unpack] 安全解包交付件 -> {unpack_dir}")
    with tarfile.open(args.deliverable, "r:gz") as tar:
        safe_extract(tar, unpack_dir)

    receipt, adapter_dir = verify_deliverable_receipt(unpack_dir)
    base_dir = find_base_dir(args.base)
    base_cfg = lineage_gate(base_dir, adapter_dir)

    merge_lora_adapter(base_dir, adapter_dir, merged_dir, weight=args.weight, mode=args.mode)

    safe_tag_name = re.sub(r"[^A-Za-z0-9._-]+", "_", args.tag)
    gguf_path = os.path.join(work_dir, f"{safe_tag_name}.{args.qtype}.gguf")
    gguf_abs = convert_to_gguf(merged_dir, gguf_path, qtype=args.qtype)
    gguf_sha = sha256_file(gguf_abs)

    modelfile_text = build_modelfile(gguf_abs)
    modelfile_path = os.path.join(work_dir, f"{safe_tag_name}.Modelfile")
    with open(modelfile_path, "w", encoding="utf-8") as mf:
        mf.write(modelfile_text)
    modelfile_sha = sha256_file(modelfile_path)

    print(f"[Ollama] 创建模型 {args.tag} <- {modelfile_path}")
    subprocess.run(["ollama", "create", args.tag, "-f", modelfile_path], check=True, env=_local_env())

    resolved_profile = _resolve_probe_profile(args.tag, getattr(args, "probe_profile", "auto"))
    if getattr(args, "with_memory", False):
        dual = verify_deployed_model_with_memory(args.tag, probe_profile=resolved_profile)
        probes = dual["raw_probes"]
        all_ok = bool(dual["raw_all_passed"])
        mem_probes = dual["memory_augmented_probes"]
        mem_all_ok = dual["memory_augmented_all_passed"]
        basis = dual["basis"]
    else:
        probes = verify_deployed_model(args.tag, probe_profile=resolved_profile)
        all_ok = all(bool(p.get("passed")) for p in probes.values())
        mem_probes = None
        mem_all_ok = None
        basis = "measured_raw"

    verdict = dual_track_verdict(all_ok, mem_all_ok, probes, mem_probes)
    deploy_receipt = {
        "status": verdict["status"],
        "acceptance_gate": verdict["acceptance_gate"],
        "raw_status": verdict["raw_status"],
        "memory_status": verdict["memory_status"],
        "raw_failed_probes": verdict["raw_failed_probes"],
        "memory_failed_probes": verdict["memory_failed_probes"],
        "tag": args.tag,
        "probe_profile": resolved_profile,
        "raw_all_passed": all_ok,
        "basis": basis,
        "deliverable": os.path.abspath(args.deliverable),
        "adapter_sha256": receipt.get("adapter_sha256"),
        "dataset_sha256": receipt.get("dataset_sha256"),
        "base_dir": base_dir,
        "base_spec": {k: base_cfg.get(k) for k in EXPECTED_BASE_SPEC},
        "merge_weight": args.weight,
        "merge_mode": args.mode,
        "gguf_path": gguf_abs,
        "gguf_sha256": gguf_sha,
        "modelfile_path": os.path.abspath(modelfile_path),
        "modelfile_sha256": modelfile_sha,
        "measurement_version": MEASUREMENT_VERSION,
        "grader_sha256": GRADER_SHA256,
        "probes": probes,
        "deployed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    if mem_probes is not None:
        deploy_receipt["memory_augmented_probes"] = mem_probes
        deploy_receipt["memory_augmented_all_passed"] = mem_all_ok
    rec_out = os.path.join(ROOT, "checkpoints", f"deployment_receipt_{safe_tag_name}.json")
    os.makedirs(os.path.dirname(rec_out), exist_ok=True)
    with open(rec_out, "w", encoding="utf-8") as rf:
        json.dump(deploy_receipt, rf, ensure_ascii=False, indent=2)

    print(f"[Receipt] 部署验收凭证已落盘: {rec_out} | status={deploy_receipt['status']}"
          f" | gate={deploy_receipt['acceptance_gate']} | raw={deploy_receipt['raw_status']}"
          f" | memory={deploy_receipt['memory_status']}")
    if deploy_receipt["status"] == STATUS_PROBE_FAILED:
        raise SystemExit(f"[FATAL] 模型 {args.tag} 未通过验收探针，请检查 {rec_out}")
    if deploy_receipt["status"] == STATUS_MEMORY_AUGMENTED_VERIFIED:
        print(f"[WARN] 裸权重轨未全过（{deploy_receipt['raw_failed_probes']}），"
              f"但生产配置（记忆增强轨）全过 ⇒ 按双轨验收口径通过，缺陷已在凭证 raw_failed_probes 留档")
    print(f"🎉 模型 {args.tag} 已真实融合 Qwen3-8B + 转换 GGUF + 原生 17 工具上线并通过 ({resolved_profile}) 验证！")
    return deploy_receipt


def main():
    parser = argparse.ArgumentParser(description="Virtu 8.2B LoRA 真融合与 17 工具原生部署修复脚本 (v2)")
    parser.add_argument("--deliverable", default=DEFAULT_DELIVERABLE, help="云端回传的 .tar.gz 交付件")
    parser.add_argument("--base", default=None, help="本地 Qwen3-8B 非 Instruct 基座目录")
    parser.add_argument("--tag", default="virtu-master-fixed:latest", help="目标 Ollama 模型标签")
    parser.add_argument("--work-dir", default=os.path.join(ROOT, "checkpoints", "_deploy_master"), help="解包与转换工作目录")
    parser.add_argument("--weight", type=float, default=1.0, help="LoRA Delta 融合系数")
    parser.add_argument("--mode", default="delta", choices=("delta", "linear"), help="merge_numpy.py 融合模式")
    parser.add_argument("--qtype", default="q4_0", help="GGUF 量化格式 (当前脚本链支持 q4_0)")
    parser.add_argument("--allow-overwrite", action="store_true", help="显式允许覆盖已存在的 Ollama 标签")
    parser.add_argument("--verify-only", action="store_true", help="仅对已存在的目标 Ollama 标签重跑全套实测探针并更新凭证")
    parser.add_argument(
        "--probe-profile",
        default="auto",
        choices=("auto", "general", "vericut96", "all"),
        help="实测探针套件档位 (auto 按标签区分 general / vericut96)",
    )
    parser.add_argument("--with-memory", action="store_true", help="同步运行 Hindsight 记忆注入双轨验收探针")
    parser.add_argument("--selftest", action="store_true", help="运行零 GPU / 零 Ollama 离线门禁自检")
    args = parser.parse_args()

    if args.selftest:
        raise SystemExit(run_selftest())
    if args.verify_only:
        safe_tag = re.sub(r"[^A-Za-z0-9_.-]+", "_", args.tag)
        if args.with_memory:
            dual = verify_deployed_model_with_memory(args.tag, probe_profile=args.probe_profile)
            resolved_profile = dual["probe_profile"]
            probes = dual["raw_probes"]
            all_ok = bool(dual["raw_all_passed"])
            mem_probes = dual["memory_augmented_probes"]
            mem_all_ok = dual["memory_augmented_all_passed"]
            basis = dual["basis"]
        else:
            resolved_profile = _resolve_probe_profile(args.tag, args.probe_profile)
            probes = verify_deployed_model(args.tag, probe_profile=args.probe_profile)
            all_ok = all(bool(p.get("passed")) for p in probes.values())
            mem_probes = None
            mem_all_ok = None
            basis = "measured_raw"

        rec_out = os.path.join(ROOT, "checkpoints", f"deployment_receipt_{safe_tag}.json")
        prior_lineage = {}
        if os.path.exists(rec_out):
            try:
                with open(rec_out, "r", encoding="utf-8") as pf:
                    prev = json.load(pf)
                if isinstance(prev, dict) and prev.get("tag") == args.tag:
                    for lk in (
                        "deliverable", "adapter_sha256", "dataset_sha256",
                        "base_dir", "base_spec", "merge_weight", "merge_mode",
                        "gguf_path", "gguf_sha256", "modelfile_path", "modelfile_sha256",
                        "deployed_at",
                    ):
                        if lk in prev and prev[lk] is not None:
                            prior_lineage[lk] = prev[lk]
            except Exception:
                prior_lineage = {}

        verdict = dual_track_verdict(all_ok, mem_all_ok, probes, mem_probes)
        deploy_receipt = {
            **prior_lineage,
            "status": verdict["status"],
            "acceptance_gate": verdict["acceptance_gate"],
            "raw_status": verdict["raw_status"],
            "memory_status": verdict["memory_status"],
            "raw_failed_probes": verdict["raw_failed_probes"],
            "memory_failed_probes": verdict["memory_failed_probes"],
            "verified_only": True,
            "tag": args.tag,
            "probe_profile": resolved_profile,
            "raw_all_passed": all_ok,
            "basis": basis,
            "measurement_version": MEASUREMENT_VERSION,
            "grader_sha256": GRADER_SHA256,
            "probes": probes,
            "verified_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        if args.with_memory:
            deploy_receipt["memory_augmented_probes"] = mem_probes
            deploy_receipt["memory_augmented_all_passed"] = mem_all_ok

        os.makedirs(os.path.dirname(rec_out), exist_ok=True)
        with open(rec_out, "w", encoding="utf-8") as rf:
            json.dump(deploy_receipt, rf, ensure_ascii=False, indent=2)
        print(
            f"[VerifyOnly] {args.tag} ({resolved_profile}) -> {rec_out} | "
            f"status={deploy_receipt['status']} | gate={deploy_receipt['acceptance_gate']} | "
            f"raw={deploy_receipt['raw_status']} | memory={deploy_receipt['memory_status']} | "
            f"raw_failed={deploy_receipt['raw_failed_probes']}"
        )
        if deploy_receipt["status"] == STATUS_PROBE_FAILED:
            raise SystemExit(f"[FATAL] 模型 {args.tag} 未通过验收探针，请检查 {rec_out}")
        return
    deploy(args)


if __name__ == "__main__":
    main()
