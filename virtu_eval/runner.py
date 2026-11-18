"""Runner: execute a case set against a model arm and emit traceable artifacts.

Output layout (per arm, per run dir)::

    <out>/manifest.json   input fingerprint: git sha, case-file hashes, arm spec, sampling params
    <out>/raw.jsonl       one record per case: prompt, raw response, per-criterion evidence
    <out>/results.json    aggregated dimension / tier scores

Resume is by case id from ``raw.jsonl`` (append-only; never rewritten in place),
so an interrupted run continues instead of duplicating work.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from virtu_eval.arms import build_arm  # noqa: E402
from virtu_eval.graders import score_case  # noqa: E402
from virtu_eval import provenance as P  # noqa: E402

DIM_ORDER = ["reasoning", "knowledge", "instruction", "generation",
             "multimodal", "generalization", "boundary", "toolcall"]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def git_sha():
    try:
        return subprocess.check_output(["git", "-C", os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                        "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def load_cases(case_dir, dims=None, tiers=None, limit_per_dim=None, sample_per_tier=None,
               case_ids=None):
    cases = []
    files = sorted(f for f in os.listdir(case_dir) if f.endswith(".jsonl"))
    for fname in files:
        dim_from_name = fname[:-6]
        path = os.path.join(case_dir, fname)
        bucket = []
        with open(path, encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                rec["_source_file"] = fname
                rec["_line"] = line_no
                if rec.get("dimension") != dim_from_name:
                    raise ValueError(f"{fname}:{line_no} dimension={rec.get('dimension')!r} "
                                     f"conflicts with file name {dim_from_name!r}")
                if dims and rec["dimension"] not in dims:
                    continue
                if tiers and rec.get("tier") not in tiers:
                    continue
                if case_ids is not None and rec["id"] not in case_ids:
                    continue
                bucket.append(rec)
        if sample_per_tier:
            taken = {}
            kept = []
            for rec in bucket:
                t = rec.get("tier")
                if taken.get(t, 0) < sample_per_tier.get(t, 0):
                    taken[t] = taken.get(t, 0) + 1
                    kept.append(rec)
            bucket = kept
        elif limit_per_dim:
            bucket = bucket[:int(limit_per_dim)]
        cases.extend(bucket)
    return cases


def build_messages(case):
    msgs = []
    if case.get("system"):
        msgs.append({"role": "system", "content": case["system"]})
    for m in case.get("context") or []:
        msgs.append({"role": m["role"], "content": m["content"]})
    msgs.append({"role": "user", "content": case["prompt"]})
    return msgs


def classify(case, gen, scored):
    """Failure taxonomy - separates 'model got it wrong' from 'we never asked it'."""
    if gen.get("error"):
        return "transport_error"
    text = (gen.get("text") or "").strip()
    if not text:
        return "empty_response"
    if scored["all_passed"]:
        return "pass"
    if scored["none_passed"]:
        return "fail_all_criteria"
    if gen.get("finish_reason") == "length":
        return "partial_truncated"
    return "partial"


def median_of(values):
    """逐题取中位数。传输错误与空回答已经被剔除，这里只剩真实作答。"""
    return statistics.median(values)


def load_case_ids(path):
    if not path:
        return None
    ids = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                ids.add(line if not line.startswith("{") else json.loads(line)["id"])
    if not ids:
        raise SystemExit(f"[FATAL] 题单 {path} 是空的 —— 空题单不得当成「全选」放行")
    return ids


def tools_gate(arm_spec, cases):
    """toolcall 维必须真的把工具面暴露出去，否则量的是"没给工具"却照样出数。

    2026-11-06 实测复现：arms 里写了 `tools_dimensions` 但没有 `tools` 时，30 道 toolcall
    题三臂全部 24/30 零分、维度均值一模一样（16.67），当时它被当成一次正常评测成绩引用了。
    判据空转必须由闸拦住，而不是靠人记得去看分布。

    复现历史腿可以显式豁免（VIRTU_ALLOW_TOOLSLESS_TOOLCALL=1），豁免会被写进 manifest，
    于是"这条腿没给工具"变成随证据归档的事实，而不是要回头才能发现的坑。
    """
    tc = [c for c in (cases or []) if c.get("dimension") == "toolcall"]
    if not tc:
        return {"applicable": False, "toolcall_cases": 0, "schema_exposed": None,
                "verdict": "not_applicable"}
    exposed = bool((arm_spec or {}).get("tools"))
    waived = os.environ.get("VIRTU_ALLOW_TOOLSLESS_TOOLCALL", "") not in ("", "0", "false")
    if exposed:
        return {"applicable": True, "toolcall_cases": len(tc), "schema_exposed": True,
                "verdict": "ok"}
    if waived:
        return {"applicable": True, "toolcall_cases": len(tc), "schema_exposed": False,
                "verdict": "waived_by_env",
                "note": "VIRTU_ALLOW_TOOLSLESS_TOOLCALL 已设：本腿不含工具 schema，"
                        "toolcall 分数不得当作工具能力引用"}
    raise ValueError(
        f"toolcall 判据空转闸：这 {len(tc)} 道题要求模型调用工具，但臂 "
        f"{(arm_spec or {}).get('model_id') or (arm_spec or {}).get('model_path')} 没有暴露任何 "
        f"tools schema。要么在 arms.json 里补 tools，要么设 "
        f"VIRTU_ALLOW_TOOLSLESS_TOOLCALL=1 明确豁免（豁免会写进 manifest）。")


def _arm_model_ids(arm_spec):
    """臂规格里可被 RunIdentity.capture 按内容寻址的构件标识。

    ollama/http 臂用 model_id，hf 臂用 model_path/adapter_path。capture 对库里
    找不到的标识只记 present=False，不会抛异常，因此新机/离线起腿照样能封指纹。
    """
    ids = []
    for key in ("model_id", "model_path", "adapter_path"):
        val = (arm_spec or {}).get(key)
        if isinstance(val, str) and val:
            ids.append(val)
    return ids


def _write_json_atomic(path, doc):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _finalize_identity(out_dir, identity_path, manifest_path, manifest,
                       legacy, dry, identity):
    """收腿：identity.drift() 非空即整腿作废，绝不写 results.json。

    - drift 非空：manifest 标 status=voided / failed、追加 drift_log.jsonl、
      显式标记 results.json 被抑制。本函数从不创建也从不改写 results.json，
      所以漂移腿没有任何分数文件出炉。
    - legacy：旧腿无 identity.json，不补造、不判漂移、不崩，保持 basis=partial。
    - dry：演练不写身份、不判漂移。
    """
    if dry or legacy:
        if legacy:
            manifest["status"] = manifest.get("status") or "completed_legacy"
            manifest["attribution_basis"] = "partial"
            _write_json_atomic(manifest_path, manifest)
        return
    if identity is None:
        # fail closed：没有身份就不该走到这里，绝不静默当成一条正常腿。
        raise ValueError(f"{out_dir}: 缺少 identity.json，无法核对本腿归因")
    drift = identity.drift()
    if drift:
        manifest["status"] = "voided"
        manifest["failed"] = True
        manifest["void_reason"] = "identity_drift"
        manifest["attribution_basis"] = "voided"
        manifest["drift"] = drift
        manifest["results_json"] = "suppressed_due_to_drift"
        log = os.path.join(out_dir, "drift_log.jsonl")
        with open(log, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "run_id": identity.run_id,
                "event": "identity_drift",
                "drift": drift,
                "action": "void_leg; results.json suppressed",
            }, ensure_ascii=False) + "\n")
        print(f"[VOIDED] {out_dir}: 身份漂移 {drift} —— 本腿分数作废，不写 results.json",
              flush=True)
    else:
        manifest["status"] = "completed"
    _write_json_atomic(manifest_path, manifest)


def run(case_dir, arm_spec, out_dir, dims=None, tiers=None, limit_per_dim=None,
        sample_per_tier=None, temperature=0.0, seed=1234, max_tokens_cap=None,
        cap_by_tier=None, token_floor=None, dry=False, repeats=1, case_ids_file=None):
    os.makedirs(out_dir, exist_ok=True)
    # A dry run must never populate raw.jsonl: those synthetic records would be
    # resumed later and silently skip real generation for the same arm.
    raw_path = os.path.join(out_dir, "dry_run.jsonl" if dry else "raw.jsonl")

    done = {}
    existing_manifest = None
    manifest_path = os.path.join(out_dir, "dry_manifest.json" if dry else "manifest.json")
    if not dry and os.path.exists(raw_path):
        with open(raw_path, encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                try:
                    r = json.loads(line)
                    case_id = r.get("case_id")
                    if not isinstance(case_id, str) or not case_id:
                        raise ValueError("missing case_id")
                    if case_id in done:
                        raise ValueError(f"duplicate case_id {case_id}")
                    # Infra blips (backend unreachable / empty) are not model
                    # answers. Never treat them as "done" so a rerun retries them
                    # instead of permanently scoring a transport failure.
                    if r.get("verdict") in ("transport_error", "empty_response"):
                        continue
                    done[case_id] = r
                except (json.JSONDecodeError, ValueError, TypeError, AttributeError) as exc:
                    raise ValueError(f"Cannot resume from malformed raw.jsonl line {line_no}: {exc}") from exc
    if os.path.exists(manifest_path):
        with open(manifest_path, encoding="utf-8") as f:
            existing_manifest = json.load(f)

    case_ids = load_case_ids(case_ids_file)
    cases = load_cases(case_dir, dims, tiers, limit_per_dim, sample_per_tier, case_ids)
    if case_ids:
        missing = sorted(case_ids - {c["id"] for c in cases})
        if missing:
            raise SystemExit(f"[FATAL] 题单里有 {len(missing)} 个 id 在用例集中不存在：{missing[:5]}")
    harness_files = {
        "runner.py": __file__,
        "arms.py": os.path.join(os.path.dirname(__file__), "arms.py"),
        "graders.py": os.path.join(os.path.dirname(__file__), "graders.py"),
    }
    # --- P0-B 归因链：起腿用 RunIdentity.capture() 把构件/用例/判分器按内容寻址 ---
    # 旧腿（有 manifest/raw 却从未 capture 过）不补造、不崩，走 legacy 分支并显式
    # 标 basis=partial；resume 自己起过的腿直接 read，避免 run_id 在续跑时漂移。
    case_hashes = {f: sha256_file(os.path.join(case_dir, f))
                   for f in sorted(os.listdir(case_dir)) if f.endswith(".jsonl")}
    identity_path = os.path.join(out_dir, "identity.json")
    legacy = (not dry and (bool(done) or existing_manifest is not None)
              and not os.path.exists(identity_path))
    if existing_manifest is not None and existing_manifest.get("status") == "voided":
        raise ValueError(f"{out_dir}: 本腿已因身份漂移作废（status=voided），拒绝续跑")
    identity = None
    if dry:
        # 演练不产生真实证据：不写 identity.json，收腿也跳过 drift。
        pass
    elif legacy:
        identity = None
    elif os.path.exists(identity_path):
        identity = P.RunIdentity.read(identity_path)
    else:
        # 用例 sha256 走 extra 而不是 case_dirs：provenance.drift() 对 cases 用
        # (ROOT/data/benchmark).rglob(name) 取首个同名文件比对，本仓有 9 份同名
        # boundary.jsonl，会把一条正常腿误判成"用例集已被改动"而作废。这里把用例
        # 指纹固定进 extra（仍进 run_id 哈希）与 manifest.case_file_sha256，drift()
        # 则专注检测它真正可靠的 Ollama 层摘要与判分器 sha256（标签重指向/换尺）。
        identity = P.RunIdentity.capture(
            model_ids=_arm_model_ids(arm_spec),
            case_dirs=(),
            ruler_files=("virtu_eval/graders.py", "virtu_eval/runner.py",
                         "virtu_eval/arms.py"),
            extra={"temperature": temperature, "seed": seed,
                   "repeats": int(repeats), "max_tokens_cap": max_tokens_cap,
                   "token_floor": token_floor,
                   "case_dir": case_dir, "case_file_sha256": case_hashes})
        identity.write(identity_path)
    manifest = {
        "git_sha": git_sha(),
        "harness_source_sha256": {name: sha256_file(path)
                                  for name, path in harness_files.items()},
        "arm": {k: v for k, v in arm_spec.items() if k != "api_key"},
        "sampling": {"temperature": temperature, "seed": seed, "max_tokens_cap": max_tokens_cap,
                     "cap_by_tier": cap_by_tier, "token_floor": token_floor,
                     "sample_per_tier": sample_per_tier},
        "case_dir": case_dir,
        "case_file_sha256": case_hashes,
        "tools_gate": tools_gate(arm_spec, cases),
        "repeats": int(repeats),
        "n_cases_selected": len(cases),
        "selected_case_ids": [case["id"] for case in cases],
        "harness": "virtu_eval v1",
        # P0-B：内容指纹写进 manifest，分数才回答得出"哪段字节产生了你"。
        "run_id": (identity.run_id if identity is not None
                   else (existing_manifest or {}).get("run_id")),
        "attribution_basis": ("partial" if legacy else
                              ("partial" if dry else "measured")),
        "identity_legacy": bool(legacy),
        "identity_file": "identity.json" if identity is not None else None,
    }
    if done and existing_manifest is None:
        raise ValueError("Cannot resume raw.jsonl without its original manifest.json")
    if existing_manifest is not None:
        fingerprint_keys = ("git_sha", "harness_source_sha256", "arm", "sampling", "case_dir",
                            "case_file_sha256", "n_cases_selected", "selected_case_ids", "harness")
        changed = [key for key in fingerprint_keys
                   if existing_manifest.get(key) != manifest.get(key)]
        if changed:
            raise ValueError(f"Refusing to resume with a different evaluation fingerprint: {changed}")
    manifest["started"] = (existing_manifest or {}).get(
        "started", time.strftime("%Y-%m-%d %H:%M:%S"))
    manifest["n_already_done"] = len(done)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"[manifest] {manifest['n_cases_selected']} cases selected, "
          f"{len(done)} already recorded, git={manifest['git_sha']}", flush=True)

    remaining = [c for c in cases if c["id"] not in done]
    arm = None if (dry or not remaining) else build_arm(arm_spec)
    if arm is not None and not dry:
        arm.load()

    fh = open(raw_path, "w" if dry else "a", encoding="utf-8")
    n = 0
    try:
        for case in cases:
            cid = case["id"]
            if cid in done:
                continue
            max_tokens = int(case.get("max_tokens", 512))
            if cap_by_tier and case.get("tier") in cap_by_tier:
                max_tokens = min(max_tokens, int(cap_by_tier[case["tier"]]))
            if max_tokens_cap:
                max_tokens = min(max_tokens, int(max_tokens_cap))
            if token_floor:
                # Applied last on purpose: the per-case budget is authored into the
                # case file, and neither --cap-by-tier nor --max-tokens-cap can raise
                # it - only a floor can. Measured 2026-11-01: the base arm wants
                # 323-397 completion tokens on boundary/knowledge/reasoning but those
                # cases are authored at 256/448, so 21/30 boundary records truncated
                # and the dimension scored on 30% of its own sample. The value lands in
                # the manifest fingerprint, so runs on different rulers cannot be
                # compared by accident.
                max_tokens = max(max_tokens, int(token_floor))
            rec = {"case_id": cid, "dimension": case["dimension"], "tier": case.get("tier"),
                   "tags": case.get("tags", []), "prompt": case["prompt"],
                   "gold": case.get("gold"), "max_tokens": max_tokens}
            if dry:
                rec.update({"response": None, "score": None, "verdict": "dry_run",
                            "criteria": [], "gen": {"error": None}})
            else:
                # 同一 seed 下重复问 repeats 次。同臂复测实测会改变分数
                # （σ_复测 MoE 8.84 / 稠密 23.57，1/8 题会变，最大变 25 分），
                # 单发分数的配对差里混着这份噪声；逐题中位数把它压下去。
                reps = []
                for _rep in range(max(1, int(repeats))):
                    try:
                        messages = build_messages(case)
                        g = arm.generate(messages, max_tokens=max_tokens,
                                         temperature=temperature, seed=seed,
                                         images=case.get("images"),
                                         tools=arm.tools_for(case))
                    except Exception as exc:  # noqa: BLE001 - one bad case must not kill a multi-hour sweep
                        g = {"text": "", "error": f"{type(exc).__name__}:{exc}", "elapsed_s": None,
                             "prompt_tokens": None, "completion_tokens": None,
                             "finish_reason": None, "peak_vram_gb": None,
                             "arm": getattr(arm, "label", "?")}
                    reps.append(g)
                gen = next((g for g in reps if (g.get("text") or g.get("tool_calls"))
                            and not g.get("error")), reps[0])
                text = gen.get("text") or ""
                actual_tool_calls = gen.get("tool_calls")
                if not text.strip() and actual_tool_calls:
                    calls = actual_tool_calls
                    parsed_calls = []
                    for c in calls:
                        fn = c.get("function", {})
                        args = fn.get("arguments", {})
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except Exception:
                                pass
                        parsed_calls.append({"tool": fn.get("name", ""), "arguments": args})
                    if len(parsed_calls) == 1:
                        text = json.dumps(parsed_calls[0], ensure_ascii=False)
                    else:
                        text = json.dumps(parsed_calls, ensure_ascii=False)
                    gen["text"] = text

                if int(repeats or 1) > 1:
                    # 逐判据评分后再取中位数，并复用"中位数那一答"的完整判分结果 ——
                    # 这样上报的 response / criteria 证据 / verdict 三者自洽，
                    # 而不是拼一个没有 all_passed 字段的假 scored 让 classify() 当场 KeyError。
                    rep_rows, rep_errors = [], 0
                    for g in reps:
                        if g.get("error"):
                            rep_errors += 1
                            continue
                        try:
                            sc = score_case(g.get("text") or "", case["criteria"])
                        except Exception as exc:  # noqa: BLE001 - 判分器坏了要留在证据里
                            rep_errors += 1
                            g = dict(g)
                            g["score_error"] = f"{type(exc).__name__}:{exc}"
                            continue
                        rep_rows.append((float(sc["score"]), g, sc))
                    if not rep_rows:
                        scored = {"score": 0.0, "criteria": [], "all_passed": False,
                                  "none_passed": True}
                        gen = dict(gen)
                        gen["score_error"] = "all repeats failed"
                        scored["repeats_detail"] = {"scores": [], "errors": rep_errors,
                                                    "changed": False}
                    else:
                        med = median_of([r[0] for r in rep_rows])
                        pick = min(rep_rows, key=lambda r: (abs(r[0] - med), -r[0]))
                        _, gen, scored = pick
                        scored = dict(scored)
                        scored["repeats_detail"] = {
                            "scores": [r[0] for r in rep_rows], "median": med,
                            "errors": rep_errors,
                            "changed": len({r[0] for r in rep_rows}) > 1,
                            "reported_is_median_rep": True}
                        text = gen.get("text") or ""
                        actual_tool_calls = gen.get("tool_calls")
                else:
                    try:
                        scored = score_case(text, case["criteria"])
                    except Exception as exc:  # noqa: BLE001 - malformed criteria must abort loudly
                        scored = {"score": 0.0, "criteria": [], "all_passed": False,
                                  "none_passed": True}
                        gen = dict(gen)
                        gen["score_error"] = f"{type(exc).__name__}:{exc}"
                rec.update({"response": text, "reasoning": gen.get("reasoning"),
                            "score": scored["score"], "criteria": scored["criteria"],
                            "verdict": classify(case, gen, scored),
                            "tool_calls": actual_tool_calls,
                            "native_tool_call": bool(actual_tool_calls and arm.tools_for(case)),
                            "repeats": int(repeats or 1),
                            "repeats_detail": scored.get("repeats_detail"),
                            "gen": {k: v for k, v in gen.items() if k != "text"}})
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            n += 1
            if n % 10 == 0 or rec["verdict"] in ("transport_error", "empty_response"):
                print(f"  [{n}] {cid} {rec['verdict']} score={rec['score']}", flush=True)
    finally:
        fh.close()
        if arm is not None:
            arm.unload()
    print(f"[done] {n} new records -> {raw_path}", flush=True)
    # 收腿：核对起腿时封存的身份，漂移即整腿作废（status=voided、drift_log.jsonl，
    # 且不写 results.json）。legacy 旧腿与 dry 演练由 _finalize_identity 内部处理。
    _finalize_identity(out_dir, identity_path, manifest_path, manifest,
                       legacy, dry, identity)
    return raw_path


def _parse_kv_spec(text):
    out = {}
    for part in (text or "").split(","):
        part = part.strip()
        if not part:
            continue
        k, _, v = part.partition("=")
        out[k.strip()] = int(v)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--case-dir", default="data/benchmark/virtu_eval_v1")
    p.add_argument("--arms-config", default="virtu_eval/arms.json")
    p.add_argument("--arm", required=True, help="key into arms-config")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--dims", default="", help="comma separated subset")
    p.add_argument("--tiers", default="", help="comma separated subset")
    p.add_argument("--limit-per-dim", type=int, default=0)
    p.add_argument("--sample-per-tier", default="", help="e.g. easy=3,medium=6,hard=3")
    p.add_argument("--cap-by-tier", default="", help="e.g. easy=128,medium=256,hard=448")
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--seed", type=int, default=1234)
    p.add_argument("--max-tokens-cap", type=int, default=0)
    p.add_argument("--token-floor", type=int, default=0,
                   help="raise every case budget to at least N tokens. The authored"
                        " per-case caps can only be lowered, and a quarter of a"
                        " 210-case run measured truncated at those budgets")
    p.add_argument("--repeats", type=int, default=1,
                   help="同 seed 重问次数，逐题取中位数；1 与历史腿完全等价")
    p.add_argument("--case-ids-file", default=None,
                   help="题单（每行一个 id，或 jsonl），用于只测有判别力的题")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    arms = json.load(open(a.arms_config, encoding="utf-8"))
    if a.arm not in arms:
        raise SystemExit(f"arm {a.arm!r} not in {a.arms_config}; have {list(arms)}")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    run(os.path.join(root, a.case_dir), arms[a.arm], os.path.join(root, a.out_dir),
        dims=[x for x in a.dims.split(",") if x],
        tiers=[x for x in a.tiers.split(",") if x],
        limit_per_dim=a.limit_per_dim or None,
        sample_per_tier=_parse_kv_spec(a.sample_per_tier) or None,
        cap_by_tier=_parse_kv_spec(a.cap_by_tier) or None,
        token_floor=a.token_floor or None,
        temperature=a.temperature, seed=a.seed,
        max_tokens_cap=a.max_tokens_cap or None, dry=a.dry_run,
        repeats=a.repeats or 1, case_ids_file=a.case_ids_file)


if __name__ == "__main__":
    main()
