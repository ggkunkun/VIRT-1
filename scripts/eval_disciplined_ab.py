"""A/B the disciplined Virtu artifact against a frozen baseline raw.jsonl.

The script refuses to start while another evaluation chain or runner is active.
It then acquires a lock, generates the requested cases on the new tag, and grades
both the raw response and the serving-cleaned response (thinking hygiene +
strict-format compiler).  The baseline is read from an existing raw.jsonl, so the
comparison uses the same case ids and criteria without spending GPU twice.

Example (run only when the host is idle):

    .venv/Scripts/python.exe scripts/eval_disciplined_ab.py \
        --model virtu-disciplined:v1 \
        --baseline runs/eval/fullboard_20261105_0930/board7__comprehensive/raw.jsonl \
        --dims instruction,generalization,reasoning,boundary,knowledge,generation,toolcall \
        --out runs/eval/disciplined_20261105
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
from collections import defaultdict
from statistics import mean

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from virtu_eval.arms import OllamaNativeArm  # noqa: E402
from virtu_eval.graders import score_case  # noqa: E402
from virtu_eval.provenance import (  # noqa: E402
    RunIdentity, metrics_from_raw, render_table, seal_leg, sha256_file, verify_seal,
)
from virtu_eval.runner import build_messages, git_sha, load_cases  # noqa: E402
from virtu_omni.serving.answer_pipeline import clean_served_answer  # noqa: E402

DEFAULT_BASELINE = os.path.join(
    ROOT, "runs/eval/fullboard_20261105_0930/board7__comprehensive/raw.jsonl")
DEFAULT_TOOLS = os.path.join(
    ROOT, "runs/eval/fullboard_20261105_0930/board7__comprehensive/manifest.json")


def log(msg: str) -> None:
    line = f"{dt.datetime.now().astimezone().isoformat(timespec='seconds')} {msg}"
    print(line, flush=True)


def _ps_lines() -> list[str]:
    cmd = ("Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" "
           "| Select-Object -ExpandProperty CommandLine")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=30).stdout
    except Exception:
        return []
    return [x for x in out.splitlines() if x.strip()]


def foreign_activity(own_script: str) -> list[str]:
    """Real evaluators only.

    Measured pitfall 1: a probe whose command line merely *mentions* runner.py (a
    Get-CimInstance one-liner) is not an evaluator; counting it makes the quiet gate
    wait on its own caller forever.
    Measured pitfall 2: this box runs two evaluation harnesses - ``virtu_eval/runner.py``
    and a standalone ``virtu_eval.py`` driven through the bridge by another agent.
    Matching only the first one declared the host quiet while 60 GPU cases were in flight.
    """
    hits = []
    for line in _ps_lines():
        if own_script.lower() in line.lower():
            continue
        low = line.lower()
        if "get-ciminstance" in low or "-x utf8 -c" in low or "-c " in low:
            continue
        if "virtu_eval" in low or ("run_chain" in low and ".py" in low):
            hits.append(line[:160])
    return hits


def loaded_models() -> list[str]:
    try:
        out = subprocess.run(["ollama", "ps"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=30).stdout
    except Exception:
        return []
    return [line.split()[0] for line in out.splitlines()[1:] if line.strip()]


def host_is_quiet(own_script: str) -> tuple[bool, str]:
    hits = foreign_activity(own_script)
    if hits:
        return False, f"foreign evaluator: {hits[0]}"
    models = loaded_models()
    if models:
        return False, f"ollama has loaded model(s): {models}"
    return True, "quiet"


def wait_for_quiet(own_script: str, max_wait_s: int, hold_s: int) -> bool:
    deadline = time.monotonic() + max_wait_s
    quiet_since = None
    polls = 0
    while time.monotonic() < deadline:
        polls += 1
        ok, why = host_is_quiet(own_script)
        if ok:
            quiet_since = quiet_since or time.monotonic()
            if time.monotonic() - quiet_since >= hold_s:
                return True
        else:
            if quiet_since is not None:
                log(f"quiet gate reset: {why}")
            quiet_since = None
        if not ok or polls % 4 == 0:
            elapsed = int(time.monotonic() - (deadline - max_wait_s))
            log(f"quiet gate: {why} | elapsed {elapsed}s of {max_wait_s}s")
        time.sleep(30)
    return False


def acquire_lock(path: str) -> bool:
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            pid = int(open(path, encoding="utf-8").read().split()[0])
        except Exception:
            pid = None
        if pid and _pid_alive(pid):
            return False
        os.unlink(path)
        return acquire_lock(path)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(f"{os.getpid()} {dt.datetime.now().isoformat()}\n")
    return True


def _pid_alive(pid: int) -> bool:
    try:
        out = subprocess.run(["tasklist", "//FI", f"PID eq {pid}"],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=20).stdout
        return str(pid) in out
    except Exception:
        return False


def load_tools(path: str) -> list:
    if not path or not os.path.exists(path):
        return []
    doc = json.load(open(path, encoding="utf-8"))
    return (doc.get("arm") or doc).get("tools") or []


def load_baseline(path: str) -> dict:
    out = {}
    if not path or not os.path.exists(path):
        return out
    for line in open(path, encoding="utf-8"):
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("case_id") and not r.get("gen", {}).get("error"):
            out[r["case_id"]] = r
    return out


def summarize(rows: list[dict], baseline: dict) -> dict:
    dims = defaultdict(lambda: {"n": 0, "raw": [], "clean": [], "base": [],
                                "chars_before": 0, "chars_after": 0,
                                "loops": 0, "think": 0, "empty": 0,
                                "latency": [], "tokens": []})
    paired = []
    for r in rows:
        d = r["dimension"]
        s = dims[d]
        s["n"] += 1
        s["raw"].append(r["score_raw"])
        s["clean"].append(r["score_clean"])
        s["chars_before"] += r["pipeline"]["chars_before"]
        s["chars_after"] += r["pipeline"]["chars_after"]
        s["loops"] += int(r["pipeline"]["loop_trimmed"])
        s["think"] += int(r["pipeline"]["think_removed"])
        s["empty"] += int(not (r["gen"].get("text") or "").strip())
        if r["gen"].get("elapsed_s"):
            s["latency"].append(r["gen"]["elapsed_s"])
        if r["gen"].get("completion_tokens"):
            s["tokens"].append(r["gen"]["completion_tokens"])
        if r["case_id"] in baseline:
            b = baseline[r["case_id"]]
            s["base"].append(b["score"])
            paired.append((r["case_id"], d, b["score"], r["score_raw"], r["score_clean"]))
    out = {"dims": {}, "paired": len(paired), "paired_mean_delta_clean": 0.0}
    all_delta = []
    for d, s in dims.items():
        clean_mean = mean(s["clean"]) if s["clean"] else 0.0
        raw_mean = mean(s["raw"]) if s["raw"] else 0.0
        base_mean = mean(s["base"]) if s["base"] else None
        out["dims"][d] = {
            "n": s["n"],
            "baseline_mean": round(base_mean, 2) if base_mean is not None else None,
            "raw_mean": round(raw_mean, 2),
            "clean_mean": round(clean_mean, 2),
            "delta_clean_vs_baseline": round(clean_mean - base_mean, 2)
            if base_mean is not None else None,
            "chars_before": s["chars_before"],
            "chars_after": s["chars_after"],
            "char_saving": round(1 - s["chars_after"] / s["chars_before"], 3)
            if s["chars_before"] else 0.0,
            "loops_trimmed": s["loops"],
            "think_removed": s["think"],
            "empty_responses": s["empty"],
            "latency_mean_s": round(mean(s["latency"]), 2) if s["latency"] else None,
            "tokens_mean": round(mean(s["tokens"]), 1) if s["tokens"] else None,
        }
        if base_mean is not None:
            all_delta.extend(x[4] - x[2] for x in paired if x[1] == d)
    if all_delta:
        out["paired_mean_delta_clean"] = round(mean(all_delta), 2)
    out["improved"] = sum(1 for x in paired if x[4] > x[2] + 0.01)
    out["worse"] = sum(1 for x in paired if x[4] < x[2] - 0.01)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="virtu-disciplined:v1")
    ap.add_argument("--case-dir", default="data/benchmark/virtu_eval_v1")
    ap.add_argument("--dims", default="instruction,generalization,reasoning,boundary,"
                                     "knowledge,generation,toolcall")
    ap.add_argument("--limit-per-dim", type=int, default=0)
    ap.add_argument("--out", default="")
    ap.add_argument("--baseline", default=DEFAULT_BASELINE)
    ap.add_argument("--tools-manifest", default=DEFAULT_TOOLS)
    ap.add_argument("--num-ctx", type=int, default=8192)
    ap.add_argument("--token-floor", type=int, default=512)
    ap.add_argument("--quiet-wait", type=int, default=7200)
    ap.add_argument("--quiet-hold", type=int, default=120)
    ap.add_argument("--no-wait", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    case_dir = args.case_dir if os.path.isabs(args.case_dir) else os.path.join(ROOT, args.case_dir)
    dims = [x.strip() for x in args.dims.split(",") if x.strip()]
    cases = load_cases(case_dir, dims=dims, limit_per_dim=args.limit_per_dim or None)
    if not cases:
        log("no cases selected")
        return 2
    out_dir = args.out or os.path.join(
        ROOT, "runs/eval", "disciplined_" + dt.datetime.now().strftime("%Y%m%d_%H%M%S"))
    if not os.path.isabs(out_dir):
        out_dir = os.path.join(ROOT, out_dir)
    os.makedirs(out_dir, exist_ok=True)
    raw_path = os.path.join(out_dir, "raw.jsonl")
    lock_path = os.path.join(out_dir, ".lock")
    log(f"selected {len(cases)} cases in {dims}; out={out_dir}")

    if args.dry_run:
        for c in cases:
            print(c["id"])
        return 0

    if not args.no_wait and not wait_for_quiet(os.path.abspath(__file__),
                                               args.quiet_wait, args.quiet_hold):
        log("host did not become quiet; refusing to collide")
        return 3
    if not args.no_wait and not acquire_lock(lock_path):
        log("another disciplined A/B holds the lock")
        return 4
    if not args.no_wait:
        ok, why = host_is_quiet(os.path.abspath(__file__))
        if not ok:
            log(f"host became busy again: {why}")
            return 3

    identity = RunIdentity.capture(
        model_ids=[args.model],
        case_dirs=[case_dir],
        extra={
            "baseline": os.path.relpath(args.baseline, ROOT) if args.baseline else None,
            "baseline_sha256": sha256_file(args.baseline) if args.baseline and
            os.path.exists(args.baseline) else None,
            "sampling": {"temperature": 0.0, "top_p": 0.95, "seed": 1234,
                         "token_floor": args.token_floor, "num_ctx": args.num_ctx,
                         "think": False},
            "pipeline": ["virtu_omni.serving.output_hygiene",
                         "virtu_omni.serving.output_compiler"],
        },
    )
    if not identity.artifacts.get(args.model, {}).get("present"):
        log(f"model tag {args.model} is not present in the Ollama store")
        return 2
    identity.write(os.path.join(out_dir, "run_identity.json"))

    tools = load_tools(args.tools_manifest)
    arm = OllamaNativeArm(args.model, base_url="http://127.0.0.1:11434",
                          num_ctx=args.num_ctx, think=False, retries=1, timeout=600,
                          tools=tools, tools_dimensions=["toolcall"])
    baseline = load_baseline(args.baseline)
    manifest = {
        "started": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "git_sha": git_sha(),
        "model_id": args.model,
        "run_id": identity.run_id,
        "served_layers": arm.served_layers,
        "sampling": {"temperature": 0.0, "top_p": 0.95, "seed": 1234,
                     "max_tokens_cap": None, "token_floor": args.token_floor,
                     "num_ctx": args.num_ctx, "think": False},
        "pipeline": {"hygiene": "virtu_omni.serving.output_hygiene",
                     "compiler": "virtu_omni.serving.output_compiler"},
        "case_dir": case_dir,
        "case_file_sha256": {f: sha256_file(os.path.join(case_dir, f))
                             for f in sorted(os.listdir(case_dir)) if f.endswith(".jsonl")},
        "n_cases": len(cases),
        "case_ids": [c["id"] for c in cases],
        "baseline": args.baseline,
        "baseline_n": len(baseline),
    }
    json.dump(manifest, open(os.path.join(out_dir, "manifest.json"), "w",
                             encoding="utf-8"), ensure_ascii=False, indent=2)

    done = set()
    rows = []
    if os.path.exists(raw_path):
        for line in open(raw_path, encoding="utf-8"):
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("case_id"):
                rows.append(r)
            if r.get("verdict") != "transport_error":
                done.add(r.get("case_id"))

    fh = open(raw_path, "a", encoding="utf-8")
    try:
        for i, case in enumerate(cases, 1):
            if case["id"] in done:
                continue
            max_tokens = max(int(case.get("max_tokens", 512)), args.token_floor)
            messages = build_messages(case)
            tools_for_case = tools if case.get("dimension") == "toolcall" else None
            gen = arm.generate(messages, max_tokens=max_tokens, temperature=0.0,
                               top_p=0.95, seed=1234, images=case.get("images"),
                               tools=tools_for_case)
            raw_text = gen.get("text") or ""
            verdict = "transport_error" if gen.get("error") else "ok"
            score_raw = score_case(raw_text, case["criteria"]) if raw_text else {"score": 0.0}
            cleaned = clean_served_answer(case["prompt"], raw_text)
            score_clean = score_case(cleaned.text, case["criteria"]) if cleaned.text else {"score": 0.0}
            row = {
                "case_id": case["id"],
                "dimension": case["dimension"],
                "tier": case.get("tier"),
                "prompt": case["prompt"],
                "response_raw": raw_text,
                "response_clean": cleaned.text,
                "score_raw": score_raw["score"],
                "score_clean": score_clean["score"],
                "score": score_clean["score"],
                "criteria_raw": score_raw.get("criteria"),
                "criteria_clean": score_clean.get("criteria"),
                "pipeline": cleaned.to_dict(),
                "gen": {k: v for k, v in gen.items() if k != "text"},
                "verdict": verdict,
            }
            rows.append(row)
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
            log(f"[{i}/{len(cases)}] {case['id']:20s} raw={row['score_raw']:6.1f} "
                f"clean={row['score_clean']:6.1f} "
                f"{(gen.get('completion_tokens') or 0):4d}tok "
                f"{gen.get('elapsed_s') or 0:5.1f}s "
                f"{'ERR ' + str(gen.get('error'))[:60] if gen.get('error') else ''}")
    finally:
        fh.close()
        try:
            os.unlink(lock_path)
        except OSError:
            pass

    moved = identity.drift()
    seal_leg(out_dir, owner="eval_disciplined_ab")
    verify_seal(out_dir)
    publishable = not moved
    metrics_error = None
    metrics = []
    if publishable:
        try:
            metrics = metrics_from_raw(raw_path, run_id=identity.run_id,
                                       planned=len(cases), require_row_identity=True)
        except Exception as exc:  # noqa: BLE001 - a broken gate must not publish
            metrics_error = str(exc)
            publishable = False

    summary = summarize(rows, baseline)
    summary["finished"] = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    summary["run_id"] = identity.run_id
    summary["publishable"] = publishable
    summary["identity_drift"] = moved
    summary["metrics_error"] = metrics_error
    summary["metrics_table"] = render_table(metrics) if metrics else "(not measured)"
    json.dump(summary, open(os.path.join(out_dir, "summary.json"), "w",
                            encoding="utf-8"), ensure_ascii=False, indent=2)
    lines = ["# Disciplined arm A/B", "",
             f"- model: `{args.model}`",
             f"- run_id: `{identity.run_id}`",
             f"- publishable: `{publishable}`",
             f"- identity drift: `{moved}`",
             f"- metrics error: `{metrics_error}`",
             f"- baseline: `{args.baseline}`",
             f"- paired cases: {summary['paired']}",
             f"- improved: {summary['improved']} / worse: {summary['worse']}",
             f"- mean clean delta: {summary['paired_mean_delta_clean']:+.2f}", "",
             "| dim | n | baseline | raw | clean | delta | char save | loops | empty |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for d, s in sorted(summary["dims"].items()):
        lines.append(f"| {d} | {s['n']} | {s['baseline_mean']} | {s['raw_mean']} | "
                     f"{s['clean_mean']} | {s['delta_clean_vs_baseline']:+} | "
                     f"{s['char_saving']:.1%} | {s['loops_trimmed']} | {s['empty_responses']} |")
    lines += ["", "## Provenance", "", summary["metrics_table"]]
    open(os.path.join(out_dir, "summary.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    log(f"done: {summary['paired']} paired, improved={summary['improved']} "
        f"worse={summary['worse']} mean_delta={summary['paired_mean_delta_clean']:+.2f} "
        f"publishable={publishable}")
    return 0 if publishable else 5


if __name__ == "__main__":
    raise SystemExit(main())
