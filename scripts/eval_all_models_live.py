"""对 Ollama 模型库内的**每一个**模型执行一次真实、可归因的能力测评。

设计约束（AGENTS.md §8 测量宪法）：
  1. 分数只能来自本脚本当场调用模型得到的原始响应，绝不引用任何历史常量；
  2. 被测对象按内容寻址：记录 Ollama manifest digest / served_layers，标签只是别名；
  3. 判分器唯一权威 = virtu_eval.graders.score_case（直接 import，不重写规则）；
  4. 每条腿写完立即封缄（provenance.seal_leg），证据被改写必须可检出；
  5. 覆盖不全、传输失败、身份缺失一律 fail-closed，写「未测」而不是补分。

口径（写进每份 manifest，跨模型完全一致）：
  * 用例：data/benchmark/virtu_eval_v1，7 个文本维度，每维 1 道 easy 题
  * 采样：temperature=0, seed=1234, num_predict<=96, num_ctx=1024, think=false
  * 工具：不注入 tools schema（toolcall 维按纯文本 JSON 协议判分，不得与历史
    16 工具 schema 腿直接比较），豁免事实写进 manifest.tools_gate
  * 多模态维未测：需要视觉通道，本轮 Ollama 库无 VL 标签

用法：
  python scripts/eval_all_models_live.py                     # 全库
  python scripts/eval_all_models_live.py --only qwen3:8b,virtu-moe-14b:latest
  python scripts/eval_all_models_live.py --per-dim 2        # 每维 2 题
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from virtu_eval import provenance as P  # noqa: E402
from virtu_eval import report as R  # noqa: E402
from virtu_eval import runner as RUNNER  # noqa: E402
from virtu_eval.arms import build_arm  # noqa: E402
from virtu_eval.graders import score_case  # noqa: E402
import urllib.error  # noqa: E402

TEXT_DIMS = ["reasoning", "knowledge", "instruction", "generation",
             "generalization", "boundary", "toolcall"]
EMBED_HINTS = ("embed", "bge-", "nomic-")
CASE_DIR = os.path.join(ROOT, "data", "benchmark", "virtu_eval_v1")
GRADER_PATH = os.path.join(ROOT, "virtu_eval", "graders.py")
RUNNER_PATH = os.path.join(ROOT, "virtu_eval", "runner.py")
API = os.environ.get("VIRTU_OLLAMA_API", "http://127.0.0.1:11434")


def sha256_file(path):
    return P.sha256_file(path)


def opener():
    # 本机透明代理会吞掉 127.0.0.1，必须显式绕过
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def list_models():
    op = opener()
    with op.open(API + "/api/tags", timeout=10) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data.get("models", [])


def case_hashes(case_dir=None):
    d = case_dir or CASE_DIR
    return {f: sha256_file(os.path.join(d, f))
            for f in sorted(os.listdir(d)) if f.endswith(".jsonl")}


def call_ollama(tag, messages, max_tokens, args, served_layers, keep_alive="20m"):
    """直连 /api/chat；保留 keep_alive 避免每题重新加载模型（实测每次 load 5s+）。

    只做传输与元数据，不重写任何判分逻辑；served_layers 由仓库的
    OllamaNativeArm._read_layers() 解析 manifest 得到，保证按内容寻址。
    """
    payload = {
        "model": tag, "messages": messages, "stream": False, "think": False,
        "keep_alive": keep_alive,
        "options": {"temperature": 0.0, "top_p": 1.0, "seed": 1234,
                    "num_predict": int(max_tokens), "num_ctx": int(args.num_ctx),
                    "repeat_penalty": 1.15},
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(API + "/api/chat", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.perf_counter()
    try:
        with opener().open(req, timeout=args.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
    except Exception as exc:  # noqa: BLE001 - 传输失败必须如实落盘，不补分
        return {"text": "", "error": f"{type(exc).__name__}:{str(exc)[:200]}",
                "elapsed_s": round(time.perf_counter() - t0, 3),
                "served_layers": served_layers, "arm": f"ollama:{tag}"}
    msg = data.get("message") or {}
    content = msg.get("content") or ""
    thinking = msg.get("thinking") or ""
    if not content and thinking:
        content = thinking
    if not content and msg.get("tool_calls"):
        content = json.dumps(msg.get("tool_calls"), ensure_ascii=False)
    eval_count = data.get("eval_count")
    eval_s = (data.get("eval_duration") or 0) / 1e9
    return {
        "text": content, "reasoning": thinking,
        "elapsed_s": round(time.perf_counter() - t0, 3),
        "prompt_tokens": data.get("prompt_eval_count"),
        "completion_tokens": eval_count,
        "finish_reason": data.get("done_reason") or ("stop" if data.get("done") else None),
        "tok_per_s": round(eval_count / eval_s, 1) if eval_count and eval_s else None,
        "load_duration_s": round((data.get("load_duration") or 0) / 1e9, 3),
        "served_model": data.get("model"),
        "served_layers": served_layers,
        "arm": f"ollama:{tag}", "error": None,
    }


def unload_model(tag):
    """一条腿跑完释放显存，避免 30+ 个构件堆积把 llama-server 拖垮。"""
    payload = json.dumps({"model": tag, "keep_alive": 0}).encode("utf-8")
    req = urllib.request.Request(API + "/api/generate", data=payload,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with opener().open(req, timeout=20) as resp:
            resp.read()
    except Exception:  # noqa: BLE001 - 卸载失败不影响已封缄证据，只记环境事实
        return False
    return True


def run_id_for(tag, digest, cases, params, case_dir=None):
    blob = json.dumps({"tag": tag, "digest": digest,
                       "cases": [c["id"] for c in cases],
                       "case_hashes": case_hashes(case_dir),
                       "grader": sha256_file(GRADER_PATH),
                       "runner": sha256_file(RUNNER_PATH),
                       "client": sha256_file(__file__),
                       "params": params}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def safe_dir(tag):
    return tag.replace(":", "_").replace("/", "_").replace("\\", "_")


def load_done(raw_path):
    done = set()
    if not os.path.exists(raw_path):
        return done
    for line in open(raw_path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        # 传输失败不算完成，重跑时必须重试
        if rec.get("verdict") not in ("transport_error", "empty_response"):
            done.add(rec.get("case_id"))
    return done


def evaluate_one(tag, meta, cases, out_dir, args):
    """真实调用一个模型，逐题落盘。返回 (status, detail)。"""
    os.makedirs(out_dir, exist_ok=True)
    raw_path = os.path.join(out_dir, "raw.jsonl")
    manifest_path = os.path.join(out_dir, "manifest.json")
    sample = {t: args.per_dim for t in args.tiers.split(",") if t.strip()}
    params = {"num_ctx": args.num_ctx, "max_tokens": args.max_tokens,
              "temperature": 0.0, "seed": 1234, "think": False,
              "tools": "none (text JSON protocol)", "sample_per_tier": sample,
              "tiers": args.tiers, "per_dim": args.per_dim}
    digest = meta.get("digest") or "unknown"
    rid = run_id_for(tag, digest, cases, params, case_dir=args.case_dir)

    manifest = {
        "run_id": rid,
        "harness": "virtu_eval v1 / live_all_models driver",
        "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "model_tag": tag,
        "model_digest": digest,
        "model_aliases": meta.get("aliases", [tag]),
        "model_size_bytes": meta.get("size"),
        "arm": {"kind": "ollama_native", "base_url": API, "num_ctx": args.num_ctx,
                "think": False, "retries": 0, "timeout": args.timeout,
                "strip_think": True, "tools": None},
        "sampling": params,
        "case_dir": os.path.relpath(args.case_dir, ROOT),
        "case_file_sha256": case_hashes(args.case_dir),
        "grader_sha256": sha256_file(GRADER_PATH),
        "runner_sha256": sha256_file(RUNNER_PATH),
        "client": {"file": "scripts/eval_all_models_live.py",
                   "sha256": sha256_file(__file__),
                   "endpoint": "/api/chat", "keep_alive": "20m",
                   "note": "直连 Ollama，判分仍由 virtu_eval.graders.score_case 执行；"
                           "served_layers 取自 OllamaNativeArm._read_layers()"},
        "selected_case_ids": [c["id"] for c in cases],
        "n_cases_selected": len(cases),
        "tools_gate": {
            "applicable": True,
            "schema_exposed": False,
            "verdict": "waived_text_json_protocol",
            "note": "toolcall 用例的判分锚定响应文本中的 JSON 字面量；本轮未注入工具 "
                    "schema，分数不得当作原生 tool-calling 能力、也不得与历史 16 工具腿比较",
        },
        "unmeasured_dimensions": {
            "multimodal": "需要视觉通道；本轮 Ollama 库无 VL 标签，未测",
        },
    }
    if os.path.exists(manifest_path):
        old = json.load(open(manifest_path, encoding="utf-8"))
        for key in ("run_id", "case_file_sha256", "grader_sha256", "sampling",
                    "selected_case_ids", "model_digest"):
            if old.get(key) != manifest.get(key):
                return "failed", {"reason": f"manifest fingerprint changed ({key}); "
                                            "refusing to mix two runs in one leg"}
        manifest["started"] = old.get("started", manifest["started"])
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    done = load_done(raw_path)
    remaining = [c for c in cases if c["id"] not in done]
    if not remaining:
        return "resumed", {"run_id": rid, "rows": len(done)}

    spec = dict(manifest["arm"])
    spec["model_id"] = tag
    try:
        # 借仓库实现解析 Ollama manifest 层指纹；不调用 arm.load()，让 Ollama
        # 自己按当前显存 auto-fit，避免预算闸把能跑的构件一律拒之门外。
        served = build_arm(spec).served_layers or {}
    except Exception as exc:  # noqa: BLE001
        return "failed", {"reason": f"identity capture: {type(exc).__name__}: {str(exc)[:200]}",
                          "run_id": rid}
    if not served or served.get("error"):
        return "failed", {"reason": f"无 served_layers 内容指纹: {served}", "run_id": rid}
    consecutive_errors = 0
    t0 = time.time()
    with open(raw_path, "a", encoding="utf-8") as fh:
        for case in remaining:
            max_tokens = min(int(case.get("max_tokens", 512)), args.max_tokens)
            try:
                gen = call_ollama(tag, RUNNER.build_messages(case), max_tokens, args, served)
            except Exception as exc:  # noqa: BLE001
                gen = {"text": "", "error": f"{type(exc).__name__}:{exc}",
                       "served_layers": served}
            text = (gen.get("text") or "").strip()
            try:
                scored = score_case(text, case["criteria"])
            except Exception as exc:  # noqa: BLE001 - 判分器异常必须显式落盘
                scored = {"score": 0.0, "criteria": [], "all_passed": False,
                          "none_passed": True, "score_error": f"{type(exc).__name__}:{exc}"}
            verdict = RUNNER.classify(case, gen, scored)
            rec = {
                "case_id": case["id"], "dimension": case["dimension"],
                "tier": case.get("tier"), "tags": case.get("tags", []),
                "score": scored["score"], "criteria": scored["criteria"],
                "verdict": verdict, "response": text,
                "gen": {k: v for k, v in gen.items() if k != "text"},
                "run_id": rid, "model_tag": tag, "model_digest": digest,
            }
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            if verdict == "transport_error":
                consecutive_errors += 1
            else:
                consecutive_errors = 0
            print(f"    [{case['id']}] {verdict} score={rec['score']} "
                  f"elapsed={gen.get('elapsed_s')}s", flush=True)
            if consecutive_errors >= 2:
                print("    ! 连续 2 次传输失败，提前中止该腿（fail-closed）", flush=True)
                break
    elapsed = round(time.time() - t0, 1)
    unload_model(tag)

    rows = [json.loads(l) for l in open(raw_path, encoding="utf-8") if l.strip()]
    # 宪法 §2/§6：腿跑完时被测构件必须还是起腿时那份字节
    try:
        now = {m["name"]: m.get("digest") for m in list_models()}
        if now.get(tag) and meta.get("digest") and now[tag] != meta["digest"]:
            return "failed", {"reason": f"artifact drift: {tag} digest 在腿内从 "
                                        f"{meta['digest'][:12]} 变成 {now[tag][:12]}，本腿作废",
                              "run_id": rid, "elapsed_s": elapsed}
    except Exception as exc:  # noqa: BLE001 - 查不到快照不能当作无漂移放行
        return "failed", {"reason": f"drift check unavailable: {type(exc).__name__}:{exc}",
                          "run_id": rid}
    # 完整性闸门直接复用仓库唯一实现，不在本脚本另立一套判据
    gate = R.gate(manifest, rows, 0)
    if not gate["valid"] or gate["recorded_cases"] != len(cases):
        return "failed", {"reason": f"gate_invalid: {gate}", "run_id": rid,
                          "elapsed_s": elapsed}
    try:
        P.seal_leg(out_dir, owner="eval_all_models_live")
    except Exception as exc:  # noqa: BLE001
        return "failed", {"reason": f"seal: {type(exc).__name__}:{exc}", "run_id": rid}
    aggregate = R.aggregate(rows)
    return "measured", {
        "run_id": rid, "elapsed_s": elapsed, "gate": gate,
        "raw_sha256": sha256_file(raw_path),
        "served_layers": served,
        "served_layer_coverage": sum(1 for r in rows
                                     if (r.get("gen") or {}).get("served_layers")) / len(rows),
        "dimensions": {d: {"score": v["score"], "n": v["n_valid"]}
                       for d, v in aggregate["dimensions"].items()},
        "overall_weighted": aggregate["overall_weighted"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", default=os.path.join(ROOT, "runs", "eval", "all_models_live_v2_20261107"))
    ap.add_argument("--case-dir", default=CASE_DIR, help="用例目录（默认为 data/benchmark/virtu_eval_v1）")
    ap.add_argument("--only", default="", help="逗号分隔的模型标签子集")
    ap.add_argument("--per-dim", type=int, default=1)
    ap.add_argument("--tiers", default="easy,medium", help="逗号分隔，每个 tier 取 per-dim 道")
    ap.add_argument("--max-tokens", type=int, default=128)
    ap.add_argument("--num-ctx", type=int, default=1024)
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--force", action="store_true", help="重跑已完成的腿（换 out-root，不覆盖证据）")
    args = ap.parse_args()

    models = list_models()
    # 按内容寻址：同一个 digest 的多个标签只测一次，别名全部记录
    by_digest = {}
    for m in models:
        key = m.get("digest") or m.get("name")
        if key not in by_digest:
            by_digest[key] = dict(m, aliases=[])
        by_digest[key]["aliases"].append(m.get("name"))
    entries = []
    for meta in by_digest.values():
        primary = meta["aliases"][0]
        caps = meta.get("capabilities") or []
        # 以 Ollama 自报能力为准；没有 capabilities 字段时回退到名字启发式
        is_text = ("completion" in caps) if caps else not any(
            h in primary.lower() for h in EMBED_HINTS)
        if not is_text:
            entries.append((primary, meta, "skipped",
                            {"reason": f"no completion capability (capabilities={caps})"}))
        else:
            entries.append((primary, meta, "pending", {"capabilities": caps}))
    if args.only:
        wanted = {x.strip() for x in args.only.split(",") if x.strip()}
        entries = [e for e in entries
                   if wanted & set(e[1]["aliases"]) or e[0] in wanted]

    sample = {t: args.per_dim for t in args.tiers.split(",") if t.strip()}
    cases = RUNNER.load_cases(args.case_dir, dims=TEXT_DIMS, sample_per_tier=sample)
    if not cases:
        raise SystemExit("[FATAL] 空用例集，不得放行")
    print(f"[cases] {len(cases)} 道，dims={TEXT_DIMS}，sample={sample}", flush=True)
    print(f"[models] {len(entries)} 个唯一构件（{sum(1 for e in entries if e[2]=='skipped')} 个 embedding 跳过）",
          flush=True)

    os.makedirs(args.out_root, exist_ok=True)
    summary_path = os.path.join(args.out_root, "summary.json")
    summary = json.load(open(summary_path, encoding="utf-8")) if os.path.exists(summary_path) else {}
    summary.setdefault("meta", {
        "generated_by": "scripts/eval_all_models_live.py",
        "case_dir": os.path.relpath(args.case_dir, ROOT),
        "case_file_sha256": case_hashes(args.case_dir),
        "grader_sha256": sha256_file(GRADER_PATH),
        "runner_sha256": sha256_file(RUNNER_PATH),
        "dims": TEXT_DIMS, "unmeasured_dims": ["multimodal"],
        "scoring_contract": ("case=命中权重/总权重x100; dim=有效用例得分算术平均; "
                             "overall=sum(维度分x维度权重)/sum(权重); "
                             "transport_error/dry_run 不计入均值，其余判据照实计分"),
        "params": {"per_dim": args.per_dim, "tiers": args.tiers, "sample": sample,
                   "max_tokens": args.max_tokens, "num_ctx": args.num_ctx,
                   "temperature": 0.0, "seed": 1234, "timeout": args.timeout},
        "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "ollama_endpoint": API,
    })
    summary.setdefault("models", {})
    summary.setdefault("snapshots", [])
    summary["snapshots"].append({
        "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "phase": "start",
        "tags": {m["name"]: m.get("digest") for m in models},
    })
    summary["meta"]["last_update"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")

    for idx, (tag, meta, status, detail) in enumerate(entries, 1):
        print(f"[{idx}/{len(entries)}] {tag} aliases={meta['aliases']}", flush=True)
        if status == "skipped":
            summary["models"][tag] = {"status": status, "detail": detail,
                                      "aliases": meta["aliases"], "digest": meta.get("digest")}
        elif summary["models"].get(tag, {}).get("status") == "measured" and not args.force:
            print("    already measured, skip", flush=True)
        else:
            t0 = time.time()
            status, detail = evaluate_one(tag, meta, cases,
                                          os.path.join(args.out_root, safe_dir(tag)), args)
            summary["models"][tag] = {
                "status": status, "detail": detail, "aliases": meta["aliases"],
                "digest": meta.get("digest"), "size_bytes": meta.get("size"),
                "leg_dir": os.path.relpath(os.path.join(args.out_root, safe_dir(tag)), ROOT),
                "wall_s": round(time.time() - t0, 1),
            }
            print(f"    -> {status} ({summary['models'][tag]['wall_s']}s)", flush=True)
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

    counts = {}
    for v in summary["models"].values():
        counts[v["status"]] = counts.get(v["status"], 0) + 1
    try:
        summary["snapshots"].append({
            "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "phase": "end",
            "tags": {m["name"]: m.get("digest") for m in list_models()},
        })
    except Exception:  # noqa: BLE001
        pass
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print("[final]", counts, "->", summary_path, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
