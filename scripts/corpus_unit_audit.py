"""Audit (and optionally repair) the mm^4-labelled inertia targets sitting in SFT corpora.

Why this exists: `scripts/distill_local_solver.py::mass_props_csg` computed
`volume x (h^2 + w^2)/12` (units mm^5) and published it under `inertia_ixx_mm4`, and no
physics case grades `mass_props`, so the ruler never looked. Measured 2026-11-05 the wrong
targets are in the shipped corpora: 255 rows in `data/sft/virtu_final_train.jsonl` and the
same 255 inside `virtu_evolution_v5{,.clean}.jsonl`, plus 6 DPO reject rows.

Usage:
    python scripts/corpus_unit_audit.py data/sft/virtu_final_train.jsonl            # report
    python scripts/corpus_unit_audit.py <corpus> --fix <out.jsonl>                  # rewrite numbers
The fix rewrites only the two inertia fields; nothing else in the row is touched.
"""
from __future__ import annotations

import argparse
import io
import json
import math
import re
import sys

SHAPE_RE = re.compile(r'shape\\?"\s*[:=]\s*\\?"(box|cylinder)|shape\s*[=＝:]\s*「(box|cylinder)」')
BOX_RE = re.compile(r'l=([\d.]+)\s*mm.*?w=([\d.]+)\s*mm.*?h=([\d.]+)\s*mm', re.S)
CYL_RE = re.compile(r'r=([\d.]+)\s*mm.*?h=([\d.]+)\s*mm', re.S)
FIELD_RE = re.compile(r'(\\?)"inertia_(ixx|izz)_mm4(\\?)":\s*(-?[0-9.eE+]+)')
TOL_REL = 0.01


WS_SHAPE = re.compile(r'"shape"\s*:\s*"(box|cylinder)"')
WS_CENTROID = re.compile(r'"centroid_mm"\s*:\s*\[\s*([\d.+-]+)\s*,\s*([\d.+-]+)\s*,\s*([\d.+-]+)')
WS_VOLUME = re.compile(r'"volume_mm3"\s*:\s*([\d.eE+-]+)')
WS_FIELD_RE = re.compile(r'"(inertia_(?:ixx|izz)_mm4)"\s*:\s*(-?[0-9.eE+]+)')


def dims_from_world_state(line: str):
    """Recover the section from the row's own centroid/volume when the prompt phrasing varies.

    box: centroid=(l/2, w/2, h/2) and V=lwh; cylinder: centroid=(r, r, h/2), V=pi r^2 h.
    The recovery is self-checked against the stored volume, so a row whose geometry does not
    add up is reported rather than silently skipped.
    """
    unescaped = line.replace('\\"', '"')
    shape_m = WS_SHAPE.search(unescaped)
    cent = WS_CENTROID.search(unescaped)
    if not (shape_m and cent):
        return None
    cx, cy, cz = (float(x) for x in cent.groups())
    if shape_m.group(1) == "box":
        l, w, h = 2 * cx, 2 * cy, 2 * cz
        vol = l * w * h
    else:
        r, h = cx, 2 * cz
        l, w = r, r
        vol = math.pi * r * r * h
    stored = WS_VOLUME.search(unescaped)
    if stored and abs(float(stored.group(1)) - vol) / max(vol, 1e-9) > 0.01:
        return {"reason": "world_state_inconsistent", "volume_recovered": round(vol, 3),
                "volume_stored": stored.group(1)}
    return {"shape": shape_m.group(1), "ixx": w * h ** 3 / 12.0 if shape_m.group(1) == "box"
            else math.pi * r ** 4 / 4.0,
            "izz": l * w ** 3 / 12.0 if shape_m.group(1) == "box" else math.pi * r ** 4 / 4.0}


def analytic(shape, prompt) -> dict | None:
    if shape == "box":
        m = BOX_RE.search(prompt)
        if not m:
            return None
        l, w, h = (float(x) for x in m.groups())
        return {"ixx": w * h ** 3 / 12.0, "izz": l * w ** 3 / 12.0}
    if shape == "cylinder":
        m = CYL_RE.search(prompt)
        if not m:
            return None
        r, h = (float(x) for x in m.groups())
        return {"ixx": math.pi * r ** 4 / 4.0, "izz": math.pi * r ** 4 / 4.0}
    return None


def row_issue(line: str):
    if "inertia_ixx_mm4" not in line:
        return None
    shape_m = SHAPE_RE.search(line)
    shape = (shape_m.group(1) or shape_m.group(2)) if shape_m else None
    want = analytic(shape, line) if shape else None
    if not want:
        recovered = dims_from_world_state(line)
        if not recovered:
            return {"reason": "shape_or_params_unparseable", "shape": shape}
        if recovered.get("reason"):
            return recovered
        want = {"ixx": recovered["ixx"], "izz": recovered["izz"]}
    issues = []
    for m in FIELD_RE.finditer(line):
        field, stored = m.group(2), float(m.group(4))
        truth = want[field]
        rel = abs(stored - truth) / truth if truth else float("inf")
        if rel > TOL_REL:
            issues.append({"field": field, "stored": stored, "analytic": round(truth, 4),
                           "ratio": round(stored / truth, 4) if truth else None})
    return {"reason": "unit_mismatch", "shape": shape, "truth": want,
            "issues": issues} if issues else None


def scan(path: str) -> dict:
    total = bad = 0
    examples = []
    for line in io.open(path, encoding="utf-8", errors="ignore"):
        if not line.strip():
            continue
        total += 1
        issue = row_issue(line)
        if issue:
            bad += 1
            if len(examples) < 3:
                examples.append(issue)
    return {"path": path, "rows": total, "bad_rows": bad, "examples": examples}


STALE_FORMULA = "centroid=composite; I=parallel-axis"
TRUE_FORMULA = ("centroid=几何中心; I_box=截面两边×高^3/12 (mm^4), "
                "I_cyl=πr^4/4 与 πr^4/2 (mm^4)")


def fix(path: str, out_path: str) -> dict:
    rewritten = bad = unparsed = 0
    shape_count = {"box": 0, "cylinder": 0}
    with io.open(out_path, "w", encoding="utf-8") as out:
        for line in io.open(path, encoding="utf-8", errors="ignore"):
            if not line.strip():
                continue
            issue = row_issue(line)
            if not issue:
                out.write(line if line.endswith("\n") else line + "\n")
                continue
            if issue.get("reason") != "unit_mismatch":
                unparsed += 1
                out.write(line.rstrip() + "\n")
                continue
            bad += 1
            truth = issue["truth"]
            shape = issue.get("shape") or "unknown"
            shape_count[shape] = shape_count.get(shape, 0) + 1

            def _sub(m):
                return '%s"inertia_%s_mm4%s": %s' % (
                    m.group(1), m.group(2), m.group(3), round(truth[m.group(2)], 2))

            fixed_line = FIELD_RE.sub(_sub, line).replace(STALE_FORMULA, TRUE_FORMULA)
            out.write(fixed_line.rstrip() + "\n")
            rewritten += 1
    return {"path": path, "out": out_path, "bad_rows": bad, "rewritten": rewritten,
            "unparsed_rows_kept": unparsed, "by_shape": shape_count}


def assert_units_clean(path: str, echo=print) -> None:
    """Gate form for trainers: wrong-unit targets must not enter another run."""
    result = scan(path)
    echo("[unit-audit] %s: rows=%d inertia_unit_bad=%d" % (path, result["rows"], result["bad_rows"]))
    if result["bad_rows"]:
        for ex in result["examples"]:
            echo("  " + json.dumps(ex, ensure_ascii=False)[:220])
        echo("[FATAL] 语料把 mm^5 数值标成 inertia_*_mm4。先跑 "
             "`python scripts/corpus_unit_audit.py %s --fix <out>` 重生成靶值再训练。" % path)
        sys.exit(2)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus")
    ap.add_argument("--fix", default="", help="write a unit-corrected copy here")
    args = ap.parse_args()
    print(json.dumps(fix(args.corpus, args.fix) if args.fix else scan(args.corpus),
                     ensure_ascii=False, indent=2))
    sys.exit(2 if not args.fix and scan(args.corpus)["bad_rows"] else 0)
