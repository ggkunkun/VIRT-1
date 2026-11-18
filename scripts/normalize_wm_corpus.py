#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""世界模型 SFT 语料规范化（可复现、可审计、幂等）。

修四类落盘缺陷（2026-11-08 实测）：
  1. world_state 内层混入非契约键：_solver / 嵌套 world_state / invalid / reason /
     expected_action / blueprint_dims_mm / n_dims → 解码 schema 的
     additionalProperties:false 会把整条样本判非法。
  2. 重复 assistant 答案 → 虚增训练权重。
  3. collision 族标签按旧 AND 判据生成，与修复后的求解器（gouge 也是充分条件）
     冲突 → 用 wm_verifier.recompute 按 scenario 重派生判定字段。
  4. tolerance 族旧标签的 fit/fit_class 双阈值不一致 → 用 wm_gate 统一口径。

不做的事：不删样本、不改题面、不改数值靶值。所有被移动的键都保留在
verification / metadata 里，信息不丢失。

用法：
  python scripts/normalize_wm_corpus.py --dry-run
  python scripts/normalize_wm_corpus.py --apply --report benchmarks/WM_CORPUS_NORMALIZE_2026-11-08.json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import wm_contract as C  # noqa: E402
import wm_gate as G  # noqa: E402
import wm_schema as S  # noqa: E402
import wm_verifier as V  # noqa: E402

CORPUS_GLOB = os.path.join(ROOT, "data", "sft", "virtu_worldmodel*.jsonl")
WS_KEYS = set(S._ws_props())
TOP_KEYS = set(S.wide_schema()["properties"])
LIFT_TO_TOP = ("invalid", "reason")
CANONICAL_GATES = {
    gk: set(gvals)
    for spec in C.KEY_SCHEMA.values()
    for gk, gvals in (spec.get("gates") or {}).items()
}


def _normalize_answer(ans, scenario):
    """返回 (新答案, 动作清单)。只动 world_state 内层的非法键与可重派生的判定。"""
    actions = []
    if not isinstance(ans, dict):
        return ans, actions
    out = dict(ans)
    ws = out.get("world_state")
    if not isinstance(ws, dict):
        return out, actions
    ws = dict(ws)

    # 1) 错放进内层的顶层键提升
    for k in LIFT_TO_TOP:
        if k in ws:
            out.setdefault(k, ws.pop(k))
            actions.append(f"lift:{k}")
    nested = ws.pop("world_state", None)
    if nested is not None:
        if isinstance(nested, dict):
            for k, v in nested.items():
                ws.setdefault(k, v)
            actions.append("flatten:nested_world_state")
        else:
            out.setdefault("world_state", nested)
            actions.append("lift:world_state_null")

    # 2) 非契约键归档，不丢弃信息
    for k in sorted(set(ws) - WS_KEYS):
        v = ws.pop(k)
        if k == "_solver":
            ver = dict(out.get("verification") or {})
            ver["_solver"] = v
            out["verification"] = ver
            actions.append("archive:_solver")
        elif k == "expected_action":
            meta = dict(out.get("metadata") or {})
            meta["expected_action"] = v
            out["metadata"] = meta
            actions.append("archive:expected_action")
        else:
            ver = dict(out.get("verification") or {})
            ver.setdefault("extra", {})[k] = v
            out["verification"] = ver
            actions.append(f"archive:{k}")

    # 3) 顶层非法键归档（保留语义，避免 json_schema 解码期被掐）
    for k in sorted(set(out) - TOP_KEYS):
        if k == "scenario":  # scenario 是语料侧的元信息，允许保留在记录外层
            continue
        meta = dict(out.get("metadata") or {})
        meta[k] = out.pop(k)
        out["metadata"] = meta
        actions.append(f"archive_top:{k}")

    # 4) 闸门枚举值统一为契约短字面（如 FOS>=1.5_pass -> pass, pass_cut_negative -> pass）
    for k, v in list(ws.items()):
        if isinstance(v, str) and k in CANONICAL_GATES:
            nv = C.normalize_gate(k, v)
            if nv != v and nv in CANONICAL_GATES[k]:
                ws[k] = nv
                actions.append(f"gate_enum:{k}")

    # 5) 按求解器重派生判定字段（只对带 scenario 的样本，数值靶值一律不动）
    task = (scenario or {}).get("task")
    if task == "collision" and scenario:
        ref = V.recompute(scenario)
        for k in ("safe_plane_z_mm", "rapid_min_z_mm", "stock_top_z_mm",
                  "collision_risk", "gouge", "autodiff"):
            if k in ref and ws.get(k) != ref[k]:
                ws[k] = ref[k]
                actions.append(f"relabel:{k}")
    elif task == "tolerance" and "fit_clearance_mm" in ws:
        fixed = G.normalize(dict(ws))
        for k in ("tolerance_fit", "fit_class", "tolerance_pass"):
            if k in fixed and ws.get(k) != fixed[k]:
                ws[k] = fixed[k]
                actions.append(f"relabel:{k}")

    out["world_state"] = ws
    return out, actions


def _normalize_distilled_outputs(outputs):
    """归一 virtu_worldmodel_distilled.jsonl 中的 outputs 字典。"""
    actions = []
    if not isinstance(outputs, dict):
        return outputs, actions
    out = dict(outputs)
    for k, v in list(out.items()):
        if isinstance(v, str) and k in CANONICAL_GATES:
            nv = C.normalize_gate(k, v)
            if nv != v and nv in CANONICAL_GATES[k]:
                out[k] = nv
                actions.append(f"gate_enum:{k}")
    return out, actions


def process_file(path, apply=False):
    n = dup = changed = relabeled = 0
    seen, rows = set(), []
    action_counts = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            n += 1
            rec = json.loads(line)
            msgs = rec.get("messages") or []
            if len(msgs) < 3:
                if isinstance(rec.get("outputs"), dict):
                    new_out, acts = _normalize_distilled_outputs(rec["outputs"])
                    if acts:
                        rec["outputs"] = new_out
                        changed += 1
                        for a in acts:
                            action_counts[a] = action_counts.get(a, 0) + 1
                rows.append(json.dumps(rec, ensure_ascii=False))
                continue
            # 顺带归一 user 题面里嵌入的旧闸门草案字面量（如自纠错样本里的草案 JSON）
            u_orig = msgs[1].get("content", "")
            u_new = (u_orig.replace('"FOS>=1.5_pass"', '"pass"')
                           .replace('"FOS<1.5_FAIL"', '"fail"')
                           .replace('"pass_cut_negative"', '"pass"'))
            u_changed = (u_new != u_orig)
            if u_changed:
                msgs[1]["content"] = u_new
                action_counts["user_draft_gate_enum"] = action_counts.get("user_draft_gate_enum", 0) + 1
            original = msgs[2]["content"]
            try:
                ans = json.loads(original)
            except Exception:
                rows.append(json.dumps(rec, ensure_ascii=False))
                continue
            new_ans, acts = _normalize_answer(ans, rec.get("scenario"))
            content = json.dumps(new_ans, ensure_ascii=False)
            if content != original or u_changed:
                changed += 1
                msgs[2]["content"] = content
                for a in acts:
                    action_counts[a] = action_counts.get(a, 0) + 1
                if any(a.startswith("relabel:") for a in acts):
                    relabeled += 1
            if content in seen:
                dup += 1
                continue
            seen.add(content)
            rows.append(json.dumps(rec, ensure_ascii=False))
    if apply and (dup or changed):
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(rows) + "\n")
    return {"file": os.path.relpath(path, ROOT), "n_in": n, "n_out": len(rows),
            "duplicates_dropped": dup, "answers_normalized": changed,
            "answers_relabeled": relabeled, "actions": action_counts}


def verify(paths):
    """落盘后复核：零重复、零非法 world_state 键、零非法顶层键、零非契约闸门枚举值。"""
    bad = []
    for path in paths:
        seen = set()
        for line in open(path, encoding="utf-8"):
            if not line.strip():
                continue
            rec = json.loads(line)
            msgs = rec.get("messages") or []
            if len(msgs) < 3:
                if isinstance(rec.get("outputs"), dict):
                    for k, v in rec["outputs"].items():
                        if k in CANONICAL_GATES and v is not None and v not in CANONICAL_GATES[k]:
                            bad.append(f"{os.path.basename(path)}: bad gate {k}={v}")
                continue
            content = msgs[2]["content"]
            if content in seen:
                bad.append(f"{os.path.basename(path)}: duplicate")
            seen.add(content)
            try:
                ans = json.loads(content)
            except Exception:
                continue
            extra_top = set(ans) - TOP_KEYS
            if extra_top:
                bad.append(f"{os.path.basename(path)}: bad top keys {sorted(extra_top)}")
            ws = ans.get("world_state")
            if isinstance(ws, dict):
                extra_ws = set(ws) - WS_KEYS
                if extra_ws:
                    bad.append(f"{os.path.basename(path)}: bad ws keys {sorted(extra_ws)}")
                for k, v in ws.items():
                    if k in CANONICAL_GATES and v is not None and v not in CANONICAL_GATES[k]:
                        bad.append(f"{os.path.basename(path)}: bad gate {k}={v}")
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--report", default="")
    args = ap.parse_args()
    paths = sorted(glob.glob(CORPUS_GLOB))
    report = [process_file(p, apply=args.apply) for p in paths]
    for r in report:
        print(f"{r['file']}: {r['n_in']} -> {r['n_out']} "
              f"dup={r['duplicates_dropped']} norm={r['answers_normalized']} "
              f"relabel={r['answers_relabeled']}")
        if r["actions"]:
            top = sorted(r["actions"].items(), key=lambda x: -x[1])[:6]
            print(f"    actions: {top}")
    if args.apply:
        bad = verify(paths)
        print("[verify]", "ALL CLEAN" if not bad else f"{len(bad)} ISSUES: {bad[:8]}")
        report.append({"verify": bad})
        if args.report:
            out = os.path.join(ROOT, args.report)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            json.dump(report, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            print(f"[ok] report -> {args.report}")
        return 0 if not bad else 1
    print("[dry-run] 未写盘；加 --apply 生效")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
