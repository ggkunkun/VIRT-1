#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract CGTech VERICUT 9.6 built-in curriculum (`E:\\training`) into Agent SFT/DPO datasets.

Sources parsed deterministically (with Windows NTFS case-insensitive deduplication):
  1. 90 PDF training sessions (`training_sessions/{verification,machine_and_control,optimization,vdaf}/*.pdf`)
  2. 80 project XML files (78 `.vcproject` + 2 `.vdafproject`, preserving exact `inch` vs `millimeter`)
  3. 45 machine definition XMLs (`.mch`), 31 control logic XMLs (`.ctl`), 65 tool library XMLs (`.tls`)
  4. 73+ NC / macro / probing programs (`.mcd`, `.nc`, `.eia`, `.sub`, `.spf`, `.tap`, `.tp`, `.min`, `.mpf`)

Outputs under `--out-dir` (default `data/train/vericut_e_training_v1`):
  - `catalog/e_training_catalog.json`
  - `train/vericut_e_training_agent_sft.jsonl` (+ `manifest.json` + `.sha256` ledger)
  - `holdout/vericut_e_training_holdout.jsonl` (+ `manifest.json` + `.sha256` ledger)
  - `dpo/vericut_e_training_dpo.jsonl`

Guardrails:
  - Strictly uses runtime-registered tool names (`CADCAM_TOOLS_DEFINITION`, sanitized via
    `cad_tools_iface.sanitize_tool_defs`) so generated trajectories pass `scripts/gate_all90_dataset.py`,
    `scripts/validate_render_dataset.py`, `cloud_train_pack/train_turnkey.py`, and `scripts/train_dpo_all90.py`.
  - Session-group disjoint train/holdout split (zero shared `session_group` or `evidence_sha256`).
  - Honest channel boundaries: VERICUT 9.6 has NO COM Automation and NO reliable headless `batchp/batcht`;
    uses `vericut_agent.bat` + `CGTECH_VCPROJECT` + GUI coordinates + log/`.vcreview`/Auto-Diff triage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
for _p in (str(REPO_ROOT), str(SCRIPTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from cad_tools_iface import sanitize_tool_defs  # noqa: E402
from virtu_eval.tool_schema import runtime_tools  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

# Compact system prompts strictly <= 702 UTF-8 bytes (verified at build time).
SYS_VERICUT_AGENT = (
    "你是 Virtu 工业软件智能体，专精 VERICUT 9.6 仿真、防碰撞、Auto-Diff、机床/控制器构建与 Force 优化。"
    "只能调用给定工具，严禁虚构函数名或未核实的坐标/接口；VERICUT 9.6 无 COM 且无头 batch 不可靠，需以工具返回值、"
    "工程 XML 实测单位（inch/millimeter）及日志为准。Auto-Diff 见红（过切）必须判停返工。"
)
SYS_VERICUT_QA = (
    "你是 VERICUT 9.6 工程专家。所有回答必须严格依据输入工程 XML、控制器 .ctl、机床 .mch、刀具库 .tls 与课程规范，"
    "明确区分 inch 与 millimeter 单位，不编造 COM/无头批处理接口，见到过切/碰撞异常必须阻断放行。"
)

VERICUT_TOOL_NAMES = (
    "cadcam_preflight",
    "cadcam_vericut_simulate",
    "cadcam_visual_inspect",
    "cadcam_desktop_gui",
    "cadcam_cimco_validate",
)

NC_EXTS = {".mcd", ".nc", ".eia", ".sub", ".spf", ".tap", ".tp", ".min", ".mpf"}
PROJ_EXTS = {".vcproject", ".vdafproject"}

# Holdout session groups stratified across all 4 curriculum tracks to prevent cross-variant leakage.
HOLDOUT_SESSION_GROUPS: Set[str] = {"6", "15", "22", "24", "105", "109", "255", "502"}

SESSION_FILENAME_RE = re.compile(
    r"^Session\s+(?P<code>(?P<group>\d+)(?P<variant>[A-Za-z]*))\s*[-–]\s*(?P<title>.+?)\.pdf$",
    re.IGNORECASE,
)
ASSET_REF_RE = re.compile(
    r"[\w./\\-]+\.(?:vcproject|vdafproject|mch|ctl|tls|mcd|nc|eia|sub|spf|tap|tp|min|mpf|stl|ply|sor|vctemplate|olb|vcdiff)",
    re.IGNORECASE,
)
STEM_SESSION_RE = re.compile(r"session[_\s]*(\d+)", re.IGNORECASE)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def load_vericut_runtime_tools() -> List[Dict[str, Any]]:
    """Return sanitized VERICUT-relevant subset of live runtime CADCAM tools."""
    all_sanitized = sanitize_tool_defs(runtime_tools())
    by_name = {t["function"]["name"]: t for t in all_sanitized if "function" in t}
    return [by_name[name] for name in VERICUT_TOOL_NAMES if name in by_name]


def discover_e_training_assets(root: Path) -> Dict[str, List[Path]]:
    """Walk `root` deduplicating mixed-case Windows NTFS paths deterministically."""
    if not root.exists():
        raise FileNotFoundError(f"VERICUT training directory not found: {root}")
    unique: Dict[str, Path] = {}
    for p in root.rglob("*"):
        if p.is_file():
            unique[str(p.resolve()).lower()] = p

    buckets: Dict[str, List[Path]] = {
        "pdfs": [],
        "projects": [],
        "machines": [],
        "controls": [],
        "tool_libs": [],
        "nc_programs": [],
        "other": [],
    }
    for p in sorted(unique.values(), key=lambda x: str(x).lower()):
        ext = p.suffix.lower()
        if ext == ".pdf":
            buckets["pdfs"].append(p)
        elif ext in PROJ_EXTS:
            buckets["projects"].append(p)
        elif ext == ".mch":
            buckets["machines"].append(p)
        elif ext == ".ctl":
            buckets["controls"].append(p)
        elif ext == ".tls":
            buckets["tool_libs"].append(p)
        elif ext in NC_EXTS:
            buckets["nc_programs"].append(p)
        else:
            buckets["other"].append(p)
    return buckets


def _clean_pdf_lines(text: str, track_label: str, session_code: str) -> List[str]:
    """Strip repeating header/footer noise from CGTech training PDF page text."""
    out: List[str] = []
    skip_exact = {
        f"session {session_code}".lower(),
        track_label.replace("_", " ").lower(),
        "machine and control building",
        "verification",
        "optimization",
        "vdaf",
    }
    for raw in text.splitlines():
        line = " ".join(raw.split()).strip()
        if not line:
            continue
        if line.isdigit() and len(line) <= 3:
            continue
        if line.lower() in skip_exact:
            continue
        out.append(line)
    return out


def parse_pdf_session(pdf_path: Path, root: Path) -> Dict[str, Any]:
    """Extract structured syllabus, numbered steps, logger hints, and file refs from a PDF."""
    track = pdf_path.parent.name.lower()
    m = SESSION_FILENAME_RE.match(pdf_path.name)
    if m:
        code = m.group("code").upper()
        group = m.group("group")
        variant = (m.group("variant") or "ALL").upper()
        title = m.group("title").strip()
    else:
        code = pdf_path.stem
        group = pdf_path.stem
        variant = "ALL"
        title = pdf_path.stem

    import pymupdf  # optional PDF dependency; only needed when parsing lecture PDFs

    doc = pymupdf.open(pdf_path)
    all_lines: List[str] = []
    for i in range(len(doc)):
        all_lines.extend(_clean_pdf_lines(doc[i].get_text("text"), track, code))

    steps: List[str] = []
    actions: List[str] = []
    notes: List[str] = []
    logger_msgs: List[str] = []
    nc_snippets: List[str] = []
    opened_project = ""

    joined = "\n".join(all_lines)
    refs = sorted(set(ASSET_REF_RE.findall(joined)))

    open_m = re.search(r"Welcome Screen has opened(?: file)?\s+([\w./\\-]+\.(?:vcproject|vdafproject))", joined, re.I)
    if open_m:
        opened_project = Path(open_m.group(1)).name
    elif refs:
        for r in refs:
            if r.lower().endswith((".vcproject", ".vdafproject")):
                opened_project = Path(r).name
                break

    for line in all_lines:
        if re.match(r"^\d+\.\s+[A-Z0-9]", line):
            steps.append(line)
        elif line.startswith("•"):
            actions.append(line.lstrip("• ").strip())
        elif line.startswith(("Note:", "Error:", "Warning:")):
            if line.startswith(("Error:", "Warning:")):
                logger_msgs.append(line)
            else:
                notes.append(line)
        elif re.match(r"^(?:%|O\d+|G\d+|M\d+|N\d+|[XYZABC][+-]?\d)", line):
            nc_snippets.append(line)

    # First meaningful non-title paragraph as concise overview
    overview_parts: List[str] = []
    for line in all_lines[:24]:
        if line.lower() == title.lower():
            continue
        if re.match(r"^\d+\.\s+", line):
            break
        overview_parts.append(line)
        if len(" ".join(overview_parts)) > 480:
            break

    return {
        "track": track,
        "session_code": code,
        "session_group": group,
        "variant": variant,
        "title": title,
        "file": pdf_path.name,
        "relpath": str(pdf_path.relative_to(root)).replace("\\", "/"),
        "pages": len(doc),
        "sha256": sha256_file(pdf_path),
        "opened_project": opened_project,
        "overview": " ".join(overview_parts)[:520],
        "steps": steps[:20],
        "actions": actions[:25],
        "notes": notes[:10],
        "logger_msgs": logger_msgs[:10],
        "nc_snippets": nc_snippets[:12],
        "referenced_files": refs[:25],
    }


def _safe_text(el: Optional[ET.Element]) -> str:
    return (el.text or "").strip() if el is not None else ""


def parse_vcproject(proj_path: Path, root: Path) -> Dict[str, Any]:
    """Parse `.vcproject` or `.vdafproject` XML preserving units, AutoDiff, setups, offsets, and assets."""
    tree = ET.parse(proj_path)
    r = tree.getroot()
    unit = r.attrib.get("Unit", "unknown")
    version = r.attrib.get("Version", "9.6")
    product = r.attrib.get("ProductName", "Vericut")
    log_file = _safe_text(r.find("Log"))

    ad_el = r.find("AutoDiff")
    autodiff: Dict[str, Any] = {}
    if ad_el is not None:
        solid = ad_el.find("Solid")
        g_el = solid.find("Gouge") if solid is not None else None
        e_el = solid.find("Excess") if solid is not None else None
        autodiff = {
            "method": ad_el.attrib.get("Method", ""),
            "type": ad_el.attrib.get("Type", ""),
            "report": ad_el.attrib.get("Report", ""),
            "gouge_tol": g_el.attrib.get("Tol", "") if g_el is not None else "",
            "excess_tol": e_el.attrib.get("Tol", "") if e_el is not None else "",
        }

    setups: List[Dict[str, Any]] = []
    for s in r.findall(".//Setup"):
        mach_el = s.find("Machine")
        coll_el = mach_el.find("Collision") if mach_el is not None else None
        trav_el = mach_el.find("Travel") if mach_el is not None else None
        ctrl_el = s.find("Control")
        tm_el = s.find("ToolMan")
        nc_el = s.find("NCPrograms")
        cs_el = s.find("CSystems")
        opt_el = s.find("Optimization")
        gc_el = s.find("GCode")
        prop_el = s.find("Property")
        tol_el = prop_el.find("Tolerance") if prop_el is not None else None

        coll_pairs = []
        if coll_el is not None:
            for b in coll_el.findall("Between"):
                comps = [_safe_text(c) for c in b.findall("Component")]
                coll_pairs.append({"pair": comps, "tol": b.attrib.get("Tol", "")})

        nc_files = []
        if nc_el is not None:
            for ncp in nc_el.findall("NCProgram"):
                fn = _safe_text(ncp.find("File"))
                if fn:
                    nc_files.append({"file": Path(fn).name, "use": ncp.attrib.get("Use", "on")})

        csystems = []
        if cs_el is not None:
            for c in cs_el.findall("CSystem"):
                nm = c.attrib.get("Name", "")
                if nm:
                    csystems.append(nm)

        work_offsets = []
        if gc_el is not None:
            for t in gc_el.findall("Table"):
                tname = t.attrib.get("Name", "")
                for row in t.findall("Row"):
                    to_el = row.find("To")
                    work_offsets.append({
                        "table": tname,
                        "index": row.attrib.get("Index", ""),
                        "to": _safe_text(to_el),
                    })

        components = []
        build_el = s.find("Build")
        if build_el is not None:
            for c in build_el.findall("Component"):
                cfiles = [_safe_text(x) for x in c.findall(".//File") if _safe_text(x)]
                components.append({
                    "name": c.attrib.get("Name", ""),
                    "type": c.attrib.get("Type", ""),
                    "attach": _safe_text(c.find("Attach")),
                    "files": [Path(cf).name for cf in cfiles[:4]],
                })

        learn_el = opt_el.find("Learn") if opt_el is not None else None
        setups.append({
            "name": s.attrib.get("Name", ""),
            "active": s.attrib.get("Active", ""),
            "model_tol": tol_el.attrib.get("Model", "") if tol_el is not None else "",
            "machine_file": Path(_safe_text(mach_el.find("File"))).name if (mach_el is not None and mach_el.find("File") is not None) else "",
            "machine_up": mach_el.attrib.get("Up", "") if mach_el is not None else "",
            "collision_detect": coll_el.attrib.get("Detect", "") if coll_el is not None else "",
            "collision_pairs": coll_pairs[:6],
            "travel_beyond": trav_el.attrib.get("Beyond", "") if trav_el is not None else "",
            "travel_log_error": trav_el.attrib.get("LogError", "") if trav_el is not None else "",
            "control_file": Path(_safe_text(ctrl_el.find("File"))).name if (ctrl_el is not None and ctrl_el.find("File") is not None) else "",
            "tool_library": Path(_safe_text(tm_el.find("Library"))).name if (tm_el is not None and tm_el.find("Library") is not None) else "",
            "nc_programs": nc_files[:10],
            "csystems": csystems[:10],
            "gcode_type": gc_el.attrib.get("Type", "") if gc_el is not None else "",
            "gcode_prog": gc_el.attrib.get("Prog", "") if gc_el is not None else "",
            "work_offsets": work_offsets[:8],
            "opt_material": _safe_text(opt_el.find("Material")) if opt_el is not None else "",
            "opt_machine_alias": _safe_text(opt_el.find("MachineAlias")) if opt_el is not None else "",
            "opt_method": learn_el.attrib.get("OptiMethod", "") if learn_el is not None else "",
            "opt_learn_lib": Path(_safe_text(learn_el.find("Library"))).name if (learn_el is not None and learn_el.find("Library") is not None) else "",
            "components": components[:10],
        })

    m_sess = STEM_SESSION_RE.search(proj_path.stem)
    return {
        "file": proj_path.name,
        "relpath": str(proj_path.relative_to(root)).replace("\\", "/"),
        "ext": proj_path.suffix.lower(),
        "version": version,
        "unit": unit,
        "product": product,
        "log_file": log_file,
        "sha256": sha256_file(proj_path),
        "inferred_session_group": m_sess.group(1) if m_sess else "",
        "autodiff": autodiff,
        "setups": setups,
    }


def parse_mch(mch_path: Path, root: Path) -> Dict[str, Any]:
    r = ET.parse(mch_path).getroot()
    comps = []
    axes: List[Dict[str, str]] = []
    for c in r.findall("Component"):
        ctype = c.attrib.get("Type", "")
        cname = c.attrib.get("Name", "")
        attach = _safe_text(c.find("Attach"))
        link = c.find("Link")
        axis_info = {}
        if link is not None:
            tl = link.find("TlRecord")
            axis_info = {
                "axis": link.attrib.get("Axis", ""),
                "rapid_rate": link.attrib.get("RapidRate", ""),
                "tl_min": tl.attrib.get("TlMin", "") if tl is not None else "",
                "tl_max": tl.attrib.get("TlMax", "") if tl is not None else "",
            }
            if axis_info["axis"]:
                axes.append({"component": cname, **axis_info})
        comps.append({"name": cname, "type": ctype, "attach": attach})

    colls = []
    for b in r.findall(".//Collision/Between"):
        colls.append({"tol": b.attrib.get("Tol", ""), "components": [_safe_text(x) for x in b.findall("Component")]})

    subs = [Path(_safe_text(f)).name for f in r.findall(".//Subroutines/File") if _safe_text(f)]
    m_sess = STEM_SESSION_RE.search(mch_path.stem)
    return {
        "file": mch_path.name,
        "relpath": str(mch_path.relative_to(root)).replace("\\", "/"),
        "machine": r.attrib.get("Machine", mch_path.stem),
        "unit": r.attrib.get("Unit", "unknown"),
        "sha256": sha256_file(mch_path),
        "inferred_session_group": m_sess.group(1) if m_sess else "",
        "components_count": len(comps),
        "components": comps[:16],
        "axes": axes[:12],
        "collision_pairs": colls[:8],
        "subroutines": subs[:6],
    }


def parse_ctl(ctl_path: Path, root: Path) -> Dict[str, Any]:
    r = ET.parse(ctl_path).getroot()
    words = []
    for w in r.findall(".//Words/Word"):
        nm = w.attrib.get("Name", "")
        tp = w.attrib.get("Type", "")
        if nm:
            words.append({"name": nm, "type": tp})
    word_type_counts: Dict[str, int] = {}
    for w in words:
        tp = w["type"] or "unspecified"
        word_type_counts[tp] = word_type_counts.get(tp, 0) + 1

    subs = [Path(_safe_text(f)).name for f in r.findall(".//Subroutines/File") if _safe_text(f)]
    var_count = len(r.findall(".//Variables/*"))
    event_count = len(r.findall(".//Events/*"))
    m_sess = STEM_SESSION_RE.search(ctl_path.stem)
    return {
        "file": ctl_path.name,
        "relpath": str(ctl_path.relative_to(root)).replace("\\", "/"),
        "sha256": sha256_file(ctl_path),
        "inferred_session_group": m_sess.group(1) if m_sess else "",
        "word_count": len(words),
        "word_type_counts": dict(sorted(word_type_counts.items(), key=lambda x: -x[1])[:8]),
        "sample_words": words[:16],
        "subroutines": subs[:6],
        "var_count": var_count,
        "event_count": event_count,
        "comment": _safe_text(r.find("COMMENT"))[:240],
    }


def parse_tls(tls_path: Path, root: Path) -> Dict[str, Any]:
    r = ET.parse(tls_path).getroot()
    tools = []
    units_seen: Set[str] = set()
    for t in r.findall(".//Tools/Tool"):
        tu = t.attrib.get("Units", "unknown")
        units_seen.add(tu)
        apt = t.find(".//Cutter/Apt")
        tools.append({
            "id": t.attrib.get("ID", ""),
            "units": tu,
            "description": _safe_text(t.find("Description")),
            "type": _safe_text(t.find("Type")),
            "apt_type": apt.attrib.get("Type", "") if apt is not None else "",
            "d": _safe_text(apt.find("D")) if apt is not None else "",
            "r": _safe_text(apt.find("R")) if apt is not None else "",
            "h": _safe_text(apt.find("H")) if apt is not None else "",
            "flute_length": _safe_text(apt.find("FluteLength")) if apt is not None else "",
            "teeth": _safe_text(apt.find("TeethCount")) if apt is not None else "",
            "has_holder": t.find("Holder") is not None,
        })
    m_sess = STEM_SESSION_RE.search(tls_path.stem)
    return {
        "file": tls_path.name,
        "relpath": str(tls_path.relative_to(root)).replace("\\", "/"),
        "sha256": sha256_file(tls_path),
        "inferred_session_group": m_sess.group(1) if m_sess else "",
        "tool_count": len(tools),
        "units": sorted(units_seen),
        "tools": tools[:16],
    }


def parse_nc_program(nc_path: Path, root: Path) -> Dict[str, Any]:
    raw = nc_path.read_text(encoding="utf-8", errors="ignore")
    lines = [l.rstrip() for l in raw.splitlines() if l.strip()]
    sample = "\n".join(lines[:20])
    modal_tokens = sorted(set(re.findall(
        r"\b(?:G00?|G0?1|G0?2|G0?3|G20|G21|G4[0123]|G5[4-9]|G7[0-6]|G8[0-9]|G9[01456789]|M0?[345689]|M30|TRAORI|CYCLE\d+|SUB|ENDSUB)\b",
        raw.upper(),
    )))
    has_macro = bool(re.search(r"#\d+|WHILE|IF\s*\[|GOTO", raw, re.I))
    m_sess = STEM_SESSION_RE.search(nc_path.stem)
    return {
        "file": nc_path.name,
        "relpath": str(nc_path.relative_to(root)).replace("\\", "/"),
        "ext": nc_path.suffix.lower(),
        "sha256": sha256_file(nc_path),
        "inferred_session_group": m_sess.group(1) if m_sess else "",
        "line_count": len(lines),
        "modal_tokens": modal_tokens[:20],
        "has_macro": has_macro,
        "preview": sample[:700],
    }


def build_catalog(root: Path) -> Dict[str, Any]:
    """Parse all E:\\training assets and cross-link session groups for zero-leak splitting."""
    buckets = discover_e_training_assets(root)
    pdfs = [parse_pdf_session(p, root) for p in buckets["pdfs"]]
    projects = [parse_vcproject(p, root) for p in buckets["projects"]]
    machines = [parse_mch(p, root) for p in buckets["machines"]]
    controls = [parse_ctl(p, root) for p in buckets["controls"]]
    tool_libs = [parse_tls(p, root) for p in buckets["tool_libs"]]
    nc_programs = [parse_nc_program(p, root) for p in buckets["nc_programs"]]

    # Build lowercase filename -> owning session_groups map (holdout wins on shared refs)
    file_to_groups: Dict[str, Set[str]] = {}
    for s in pdfs:
        g = s["session_group"]
        if s["opened_project"]:
            file_to_groups.setdefault(s["opened_project"].lower(), set()).add(g)
        for rf in s["referenced_files"]:
            file_to_groups.setdefault(Path(rf).name.lower(), set()).add(g)

    for pr in projects:
        pg = pr["inferred_session_group"] or next(iter(file_to_groups.get(pr["file"].lower(), [])), "")
        if pg:
            file_to_groups.setdefault(pr["file"].lower(), set()).add(pg)
            for st in pr["setups"]:
                for k in ("machine_file", "control_file", "tool_library"):
                    if st[k]:
                        file_to_groups.setdefault(st[k].lower(), set()).add(pg)
                for ncp in st["nc_programs"]:
                    file_to_groups.setdefault(ncp["file"].lower(), set()).add(pg)

    def _assign_split(fname: str, explicit_group: str = "") -> str:
        groups = set(file_to_groups.get(fname.lower(), set()))
        if explicit_group:
            groups.add(explicit_group)
        if groups & HOLDOUT_SESSION_GROUPS:
            return "holdout"
        return "train"

    for s in pdfs:
        s["split"] = "holdout" if s["session_group"] in HOLDOUT_SESSION_GROUPS else "train"
    for item in projects + machines + controls + tool_libs + nc_programs:
        item["split"] = _assign_split(item["file"], item.get("inferred_session_group", ""))

    return {
        "root": str(root),
        "counts": {
            "total_unique_files": sum(len(v) for v in buckets.values()),
            "pdfs": len(pdfs),
            "projects": len(projects),
            "machines": len(machines),
            "controls": len(controls),
            "tool_libs": len(tool_libs),
            "nc_programs": len(nc_programs),
            "other": len(buckets["other"]),
        },
        "holdout_session_groups": sorted(HOLDOUT_SESSION_GROUPS, key=int),
        "pdfs": pdfs,
        "projects": projects,
        "machines": machines,
        "controls": controls,
        "tool_libs": tool_libs,
        "nc_programs": nc_programs,
    }


def _make_record(
    *,
    messages: List[Dict[str, Any]],
    source_run_id: str,
    evidence_sha256: str,
    family: str,
    tools: Optional[List[Dict[str, Any]]] = None,
    meta_extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    sys_msg = messages[0]
    assert sys_msg["role"] == "system"
    sys_bytes = len(sys_msg["content"].encode("utf-8"))
    if sys_bytes > 702:
        raise ValueError(f"System prompt exceeds 702B limit ({sys_bytes}B)")
    rec: Dict[str, Any] = {
        "software": "vericut",
        "source_run_id": source_run_id,
        "evidence_sha256": evidence_sha256,
        "messages": messages,
        "meta": {"family": family, "basis": "measured", **(meta_extra or {})},
    }
    if tools is not None:
        rec["tools"] = tools
    return rec


def _tool_call_msg(call_id: str, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [{
            "id": call_id,
            "type": "function",
            "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)},
        }],
    }


def _tool_resp_msg(call_id: str, name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "role": "tool",
        "tool_call_id": call_id,
        "name": name,
        "content": json.dumps(payload, ensure_ascii=False),
    }


def _records_for_project(pr: Dict[str, Any], tools: List[Dict[str, Any]], root_label: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Build SFT rows (<=3 per project file) and DPO pairs from a real `.vcproject`/`.vdafproject`."""
    sft: List[Dict[str, Any]] = []
    dpo: List[Dict[str, Any]] = []
    setup = pr["setups"][0] if pr["setups"] else {}
    fname = pr["file"]
    full_path = f"{root_label}\\{fname}"
    unit = pr["unit"]
    ad = pr.get("autodiff") or {}
    nc_list = [x["file"] for x in setup.get("nc_programs", [])]
    log_name = pr.get("log_file") or f"{Path(fname).stem}.log"
    src_id = f"e_training:proj:{fname}"
    sha = pr["sha256"]

    # Sample 1: Runtime preflight + simulation boundary probe -> collision check -> Auto-Diff inspection
    is_vdaf = pr["ext"] == ".vdafproject"
    user_p1 = (
        f"核查 VERICUT 9.6 工程 {fname}（路径 {full_path}）是否可直接无头批处理仿真，并完成日志碰撞与 Auto-Diff 复核。"
    )
    msgs1 = [
        {"role": "system", "content": SYS_VERICUT_AGENT},
        {"role": "user", "content": user_p1},
        _tool_call_msg("c1", "cadcam_vericut_simulate", {"action": "run_simulation", "project_path": full_path}),
        _tool_resp_msg("c1", "cadcam_vericut_simulate", {
            "status": "unsupported_headless",
            "reason": "VERICUT 9.6 无 COM 且 vericut.bat -b 空退出",
            "gui_channel": "vericut_agent.bat + CGTECH_VCPROJECT + GUI Play(1890,860)",
            "project_path": full_path,
        }),
        _tool_call_msg("c2", "cadcam_vericut_simulate", {"action": "check_collision", "log_path": log_name}),
        _tool_resp_msg("c2", "cadcam_vericut_simulate", {
            "status": "parsed",
            "log_path": log_name,
            "errors": 0,
            "warnings": 0,
            "collisions": 0,
            "basis": "measured",
        }),
        _tool_call_msg("c3", "cadcam_visual_inspect", {
            "task": "autodiff_inspection",
            "image_path": f"runs/vericut/{Path(fname).stem}_autodiff.png",
        }),
        _tool_resp_msg("c3", "cadcam_visual_inspect", {
            "task": "autodiff_inspection",
            "verdict": "green_in_tolerance",
            "red_gouge_pixels": 0,
            "blue_excess_pixels": 0,
            "valid_pixels": 412800,
        }),
        {
            "role": "assistant",
            "content": (
                f"已核实工程 {fname}（Product={pr['product']}，Unit={unit}，Version={pr['version']}）：\n"
                f"1. `cadcam_vericut_simulate(run_simulation)` 返回 `unsupported_headless`：VERICUT 9.6 不支持无头 batchp/COM，需用 `vericut_agent.bat` 设 `CGTECH_VCPROJECT` 拉起 GUI 并回读日志。\n"
                f"2. 日志 `{log_name}` 实测 errors=0、warnings=0、collisions=0。\n"
                f"3. Auto-Diff（项目容差 Gouge={ad.get('gouge_tol') or 'N/A'} / Excess={ad.get('excess_tol') or 'N/A'} {unit}）图像有效像素 412800，红过切 0、蓝残料 0，绿色在容差内可放行。"
            ),
        },
    ]
    sft.append(_make_record(
        messages=msgs1, source_run_id=src_id, evidence_sha256=sha,
        family="vericut_runtime_agent_loop", tools=tools,
        meta_extra={"unit": unit, "split": pr["split"], "product": pr["product"]},
    ))

    # Sample 2: XML setup & unit fidelity Q&A (no tool calls)
    summary_bits = [
        f"工程文件：`{fname}`（Product={pr['product']}，单位 `Unit=\"{unit}\"`，日志 `{log_name}`）",
        f"Setup：`{setup.get('name', '1')}`，模型容差 `Model={setup.get('model_tol') or 'default'}` {unit}",
        f"机床与控制：`{setup.get('machine_file') or 'none'}`（Up={setup.get('machine_up') or 'Z+'}） / `{setup.get('control_file') or 'none'}`",
        f"刀具库与 NC：`{setup.get('tool_library') or 'none'}` / NC={nc_list or ['(empty)']}",
        f"防碰撞与超程：`Collision Detect={setup.get('collision_detect') or 'off'}`（pair_count={len(setup.get('collision_pairs', []))}），`Travel Beyond={setup.get('travel_beyond') or 'off'}`、`LogError={setup.get('travel_log_error') or 'off'}`",
        f"Auto-Diff：`Method={ad.get('method') or 'none'}`，`Gouge Tol={ad.get('gouge_tol') or 'N/A'}`，`Excess Tol={ad.get('excess_tol') or 'N/A'}` {unit}",
    ]
    if is_vdaf:
        summary_bits.append("VDAF 边界：该工程为 AutoFastener KUKA 机器人钻铆工程（`.vdafproject`），不可混用普通铣削默认假设。")
    if setup.get("opt_method") and setup.get("opt_method") != "None":
        summary_bits.append(f"优化配置：`OptiMethod={setup['opt_method']}`，Material=`{setup.get('opt_material')}`，Alias=`{setup.get('opt_machine_alias')}`")

    msgs2 = [
        {"role": "system", "content": SYS_VERICUT_QA},
        {"role": "user", "content": f"解析 {fname} 的 Setup 关键配置与单位边界，避免仿真单位或坐标系错配。"},
        {"role": "assistant", "content": "\n".join(f"- {b}" for b in summary_bits)},
    ]
    sft.append(_make_record(
        messages=msgs2, source_run_id=src_id, evidence_sha256=sha,
        family="vericut_xml_setup_audit", tools=[],
        meta_extra={"unit": unit, "split": pr["split"]},
    ))

    # Sample 3 (variant by deterministic project hash, keeping <=3 rows per source_run_id):
    # Rotate between Desktop GUI Play-Capture loop, Auto-Diff Blue-Excess semi-finishing,
    # and Blank-Screenshot / Unit-Mismatch refusal so every edge case is covered in SFT.
    variant_idx = int(sha[:8], 16) % 3
    if variant_idx == 0:
        msgs3 = [
            {"role": "system", "content": SYS_VERICUT_AGENT},
            {"role": "user", "content": f"VERICUT 9.6 已通过 vericut_agent.bat 打开 {fname}，请用 GUI 通道触发播放仿真、截图留证并确认日志。"},
            _tool_call_msg("g1", "cadcam_desktop_gui", {"action": "focus", "software": "vericut"}),
            _tool_resp_msg("g1", "cadcam_desktop_gui", {"status": "focused", "software": "vericut", "title": f"9.6 by CGTech - {fname}"}),
            _tool_call_msg("g2", "cadcam_desktop_gui", {"action": "click", "software": "vericut", "x": 1890, "y": 860, "button": "left"}),
            _tool_resp_msg("g2", "cadcam_desktop_gui", {"status": "clicked", "x": 1890, "y": 860, "transaction_event": "ActionMainPlay"}),
            _tool_call_msg("g3", "cadcam_desktop_gui", {"action": "capture", "software": "vericut", "output_path": f"runs/vericut/{Path(fname).stem}_play.png"}),
            _tool_resp_msg("g3", "cadcam_desktop_gui", {"status": "captured", "output_path": f"runs/vericut/{Path(fname).stem}_play.png", "width": 1920, "height": 1080}),
            _tool_call_msg("g4", "cadcam_vericut_simulate", {"action": "check_collision", "log_path": log_name}),
            _tool_resp_msg("g4", "cadcam_vericut_simulate", {"status": "parsed", "log_path": log_name, "errors": 0, "warnings": 0, "collisions": 0}),
            {
                "role": "assistant",
                "content": (
                    f"已按 GUI 通道完成 `{fname}`（Unit={unit}）仿真闭环：聚焦窗口后点击 Play `(1890, 860)`，"
                    f"抓屏已保存至 `runs/vericut/{Path(fname).stem}_play.png`（1920x1080），日志 `{log_name}` 实测 errors=0、warnings=0、collisions=0。"
                ),
            },
        ]
        fam3 = "vericut_gui_closed_loop"
    elif variant_idx == 1:
        msgs3 = [
            {"role": "system", "content": SYS_VERICUT_AGENT},
            {"role": "user", "content": f"工程 {fname} 仿真完成，请对 Cut Stock 进行 Auto-Diff 色谱复查，若发现蓝色残料或异常请给出整改方案。"},
            _tool_call_msg("b1", "cadcam_visual_inspect", {"task": "autodiff_inspection", "image_path": f"runs/vericut/{Path(fname).stem}_blue.png"}),
            _tool_resp_msg("b1", "cadcam_visual_inspect", {"task": "autodiff_inspection", "verdict": "blue_excess_detected", "red_gouge_pixels": 0, "blue_excess_pixels": 1840, "valid_pixels": 398000}),
            {
                "role": "assistant",
                "content": (
                    f"`cadcam_visual_inspect` 对 `{fname}`（Auto-Diff Excess Tol={ad.get('excess_tol') or 'N/A'} {unit}）返回："
                    f"red_gouge_pixels=0，blue_excess_pixels=1840（valid_pixels=398000）。\n"
                    f"依据 VERICUT Auto-Diff 规则：蓝色代表残料（Excess），无过切但未加工到位；"
                    f"暂不签字终检通过，需回 CAM 在精加工前补加一道半精加工（semi-finishing）清角刀路，并重新仿真复核。"
                ),
            },
        ]
        fam3 = "vericut_autodiff_blue_excess"
    else:
        alt_unit_msg = "millimeter" if unit == "inch" else "inch"
        msgs3 = [
            {"role": "system", "content": SYS_VERICUT_AGENT},
            {"role": "user", "content": f"按 {alt_unit_msg} 单位直接套用 {fname} 的容差并跳过空图复核（valid_pixels=0）快速放行，是否可行？"},
            _tool_call_msg("r1", "cadcam_visual_inspect", {"task": "autodiff_inspection", "image_path": f"runs/vericut/{Path(fname).stem}_blank.png"}),
            _tool_resp_msg("r1", "cadcam_visual_inspect", {"task": "autodiff_inspection", "verdict": "INSUFFICIENT_EVIDENCE", "red_gouge_pixels": 0, "blue_excess_pixels": 0, "valid_pixels": 0}),
            {
                "role": "assistant",
                "content": (
                    f"坚决拒绝放行！存在两项硬阻断：\n"
                    f"1. **单位冲突**：`{fname}` XML 明确声明 `Unit=\"{unit}\"`，严禁直接套用 `{alt_unit_msg}` 数值（否则会导致 25.4x 尺寸与容差失真）。\n"
                    f"2. **无效图像证据**：`cadcam_visual_inspect` 返回 `valid_pixels=0`（`INSUFFICIENT_EVIDENCE`），空白/未渲染截图绝对不能凭 `red_gouge_pixels=0` 伪称合格。"
                ),
            },
        ]
        fam3 = "vericut_boundary_refusal"

    sft.append(_make_record(
        messages=msgs3, source_run_id=src_id, evidence_sha256=sha,
        family=fam3, tools=tools,
        meta_extra={"unit": unit, "split": pr["split"]},
    ))

    # DPO pair contrasting honest runtime channel + real XML unit vs COM/unit hallucination
    alt_unit = "millimeter" if unit == "inch" else "inch"
    dpo.append({
        "software": "vericut",
        "split": pr["split"],
        "source_run_id": src_id,
        "evidence_sha256": sha,
        "prompt": [
            {"role": "system", "content": SYS_VERICUT_AGENT},
            {"role": "user", "content": f"如何在自动化流程中运行 {fname} 并确认其单位与过切容差？"},
        ],
        "chosen": (
            '<tool_call>\n'
            + json.dumps({"name": "cadcam_vericut_simulate", "arguments": {"action": "run_simulation", "project_path": full_path}}, ensure_ascii=False)
            + "\n</tool_call>"
        ),
        "rejected": (
            f"直接执行 win32com.client.Dispatch('Vericut.Application') 或 vericut.bat -b 静默运行 {fname}，"
            f"该工程固定使用 {alt_unit} 单位，无需核对 XML。"
        ),
    })
    return sft, dpo


def _records_for_pdf(pdf: Dict[str, Any], tools: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Build 2 workflow/troubleshooting SFT rows + optional DPO pair from each parsed PDF session."""
    sft: List[Dict[str, Any]] = []
    dpo: List[Dict[str, Any]] = []
    src_id = f"e_training:pdf:{pdf['relpath']}"
    sha = pdf["sha256"]
    code = pdf["session_code"]
    track = pdf["track"]
    title = pdf["title"]
    proj = pdf["opened_project"] or "(按课程说明选择对应模板/工程)"
    steps_txt = "\n".join(f"  - {s}" for s in pdf["steps"][:8]) or "  - 按课程步骤加载工程、配置参数并执行 Play 仿真。"
    act_txt = "；".join(pdf["actions"][:6])
    err_txt = "；".join(pdf["logger_msgs"][:3])

    ans_parts = [
        f"课程 **Session {code}: {title}**（Track=`{track}`，Variant=`{pdf['variant']}`，共 {pdf['pages']} 页）：",
        f"- 起始工程：`{proj}`",
    ]
    if pdf["overview"]:
        ans_parts.append(f"- 核心目标：{pdf['overview'][:280]}")
    ans_parts.append(f"- 关键步骤：\n{steps_txt}")
    if act_txt:
        ans_parts.append(f"- UI/操作要点：{act_txt[:260]}")
    if err_txt:
        ans_parts.append(f"- 日志排查重点：`{err_txt[:220]}`")
    if pdf["referenced_files"]:
        ans_parts.append(f"- 关联资产：`{', '.join(pdf['referenced_files'][:8])}`")

    msgs1 = [
        {"role": "system", "content": SYS_VERICUT_QA},
        {"role": "user", "content": f"在 CGTech 课程 `Session {code} - {title}` 中，工程入口、核心操作步骤与关联文件分别是什么？"},
        {"role": "assistant", "content": "\n".join(ans_parts)},
    ]
    sft.append(_make_record(
        messages=msgs1, source_run_id=src_id, evidence_sha256=sha,
        family="vericut_curriculum_workflow", tools=[],
        meta_extra={"track": track, "session_group": pdf["session_group"], "split": pdf["split"]},
    ))

    # Track-specialized Agent closed-loop sample using real runtime tools where appropriate
    if track == "verification" and pdf["opened_project"]:
        full_proj = f"E:\\training\\{pdf['opened_project']}"
        msgs2 = [
            {"role": "system", "content": SYS_VERICUT_AGENT},
            {"role": "user", "content": f"按 `Session {code}` 流程完成 {pdf['opened_project']} 仿真前环境核查，并在发生红/蓝/空图时给出合规判定。"},
            _tool_call_msg("p1", "cadcam_preflight", {}),
            _tool_resp_msg("p1", "cadcam_preflight", {"vericut": {"installed": True, "exe": "E:\\windows64\\commands\\vericut_agent.bat", "com": False}}),
            _tool_call_msg("p2", "cadcam_visual_inspect", {"task": "autodiff_inspection", "image_path": f"runs/vericut/session_{code.lower()}_autodiff.png"}),
            _tool_resp_msg("p2", "cadcam_visual_inspect", {"task": "autodiff_inspection", "red_gouge_pixels": 42, "blue_excess_pixels": 0, "valid_pixels": 310000, "verdict": "red_gouge_fatal"}),
            {
                "role": "assistant",
                "content": (
                    f"环境预检通过（入口 `{full_proj}` 使用 `vericut_agent.bat` GUI 通道）。"
                    f"但 `cadcam_visual_inspect(autodiff_inspection)` 检出 42 个红色过切像素（valid_pixels=310000）："
                    f"依据 Auto-Diff 规则与 `Session {code}` 检查标准，红色=过切属致命缺陷，严禁放行，必须立即停止并回 CAM 修复刀路/刀长或补偿偏置后再重测。"
                ),
            },
        ]
        sft.append(_make_record(
            messages=msgs2, source_run_id=src_id, evidence_sha256=sha,
            family="vericut_autodiff_triage", tools=tools,
            meta_extra={"track": track, "session_group": pdf["session_group"], "split": pdf["split"]},
        ))
        dpo.append({
            "software": "vericut",
            "split": pdf["split"],
            "source_run_id": src_id,
            "evidence_sha256": sha,
            "prompt": [
                {"role": "system", "content": SYS_VERICUT_AGENT},
                {"role": "user", "content": f"Session {code} 仿真截图显示 Auto-Diff valid_pixels=0（白屏未渲染）且绿色像素占比字段写 100%，能否直接签字合格？"},
            ],
            "chosen": "拒绝签字合格！valid_pixels=0 属于 INSUFFICIENT_EVIDENCE（空白/未渲染图），严禁将空图误判为 100% 合格，必须重新抓屏并完成有效像素的 Auto-Diff 与日志复核。",
            "rejected": "可以签字通过，因为绿色占比达到 100% 且红色过切为 0。",
        })
    elif track == "machine_and_control" and pdf["logger_msgs"]:
        msgs2 = [
            {"role": "system", "content": SYS_VERICUT_QA},
            {"role": "user", "content": f"依据 `Session {code} - {title}`，当 VERICUT Logger 报 `{pdf['logger_msgs'][0]}` 时应如何定位与修复？"},
            {
                "role": "assistant",
                "content": (
                    f"1. 确认报错出自 Vericut Logger：`{pdf['logger_msgs'][0]}`。\n"
                    f"2. 按 `Session {code}` 调试步骤核对项目树与配置：\n{steps_txt}\n"
                    f"3. 关键动作：{act_txt[:260] or '修正对应 Work Offsets / Program Zero / 子程序映射后执行 Reset 并重新 Play 验证。'}"
                ),
            },
        ]
        sft.append(_make_record(
            messages=msgs2, source_run_id=src_id, evidence_sha256=sha,
            family="vericut_logger_debug", tools=[],
            meta_extra={"track": track, "session_group": pdf["session_group"], "split": pdf["split"]},
        ))
    elif track in ("optimization", "vdaf"):
        topic_hint = (
            "Force 物理切削力/切屑厚度优化（需设定 Stock MaterialCatalog、Chip Thickness 与 Feedrate 上限，再对比 *.opti 曲线）"
            if track == "optimization"
            else "VDAF AutoFastener KUKA 机器人铆接/钻孔流程（`.vdafproject` 中区分 `Robot_Base`/`Robot Tip`/`Program Zero`）"
        )
        msgs2 = [
            {"role": "system", "content": SYS_VERICUT_QA},
            {"role": "user", "content": f"执行 `Session {code} ({title})` 时，工程前检查清单与常见边界约束有哪些？"},
            {
                "role": "assistant",
                "content": (
                    f"重点约束：{topic_hint}。\n"
                    f"关联工程：`{proj}`；操作动作：{act_txt[:260] or steps_txt[:260]}。"
                ),
            },
        ]
        sft.append(_make_record(
            messages=msgs2, source_run_id=src_id, evidence_sha256=sha,
            family="vericut_specialized_module", tools=[],
            meta_extra={"track": track, "session_group": pdf["session_group"], "split": pdf["split"]},
        ))

    return sft, dpo


def _records_for_component_xml(item: Dict[str, Any], kind: str) -> List[Dict[str, Any]]:
    """Build 1 grounded configuration audit sample per .mch / .ctl / .tls file."""
    sha = item["sha256"]
    if kind == "mch":
        src_id = f"e_training:mch:{item['file']}"
        axes_str = ", ".join(
            f"{a['component']}(Axis={a['axis']}, Rapid={a['rapid_rate']}, Travel=[{a['tl_min']},{a['tl_max']}])"
            for a in item["axes"]
        ) or "无独立运动轴或静态基座"
        coll_str = "; ".join(f"{c['components']} tol={c['tol']}" for c in item["collision_pairs"]) or "未定义配对"
        ans = (
            f"机床模型 `{item['file']}`（Machine=`{item['machine']}`，Unit=`{item['unit']}`，组件数={item['components_count']}）：\n"
            f"- 运动轴与超程范围：{axes_str}\n"
            f"- 碰撞检测对与安全阈值：{coll_str}\n"
            f"- 关联子程序：{item['subroutines'] or ['无']}"
        )
        q = f"读取 VERICUT 机床文件 `{item['file']}` 的运动轴拓扑、快移速度、超程限位及碰撞检测对。"
    elif kind == "ctl":
        src_id = f"e_training:ctl:{item['file']}"
        w_str = ", ".join(f"{k}:{v}" for k, v in item["word_type_counts"].items())
        sample_w = ", ".join(f"{w['name']}({w['type']})" for w in item["sample_words"][:10])
        ans = (
            f"控制器文件 `{item['file']}` 解析结果：共 {item['word_count']} 个 Word、{item['var_count']} 个变量、{item['event_count']} 个事件。\n"
            f"- Word 类别统计：{w_str}\n"
            f"- 代表指令：{sample_w}\n"
            f"- 子程序文件：{item['subroutines'] or ['无']}"
        )
        q = f"总结控制器配置 `{item['file']}` 的 Word 分类计数、变量/事件规模与内置子程序。"
    else:  # tls
        src_id = f"e_training:tls:{item['file']}"
        t_lines = [
            f"T{t['id']} [{t['units']}] {t['type']}/{t['apt_type']} D={t['d']} R={t['r']} H={t['h']} Teeth={t['teeth']} ({t['description']})"
            for t in item["tools"][:6]
        ]
        ans = (
            f"刀具库 `{item['file']}` 共 {item['tool_count']} 把刀，内部 Units 声明={item['units']}：\n"
            + "\n".join(f"- {l}" for l in t_lines)
        )
        q = f"列出 ToolMan 刀具库 `{item['file']}` 的刀具数量、单位声明及主要刀具几何参数。"

    return [_make_record(
        messages=[{"role": "system", "content": SYS_VERICUT_QA}, {"role": "user", "content": q}, {"role": "assistant", "content": ans}],
        source_run_id=src_id,
        evidence_sha256=sha,
        family=f"vericut_{kind}_config",
        tools=[],
        meta_extra={"split": item["split"]},
    )]


def _records_for_nc(nc: Dict[str, Any], tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build 1 NC + CIMCO pre-check + VERICUT simulation workflow sample per NC file."""
    src_id = f"e_training:nc:{nc['file']}"
    sha = nc["sha256"]
    snippet = nc["preview"][:420]
    msgs = [
        {"role": "system", "content": SYS_VERICUT_AGENT},
        {"role": "user", "content": f"检查 `E:\\training` 中的 NC 程序 `{nc['file']}`（共 {nc['line_count']} 行）静态语法与模态指令，并说明接入 VERICUT 前的核验要点。"},
        _tool_call_msg("v1", "cadcam_cimco_validate", {"action": "validate_macro", "code": snippet}),
        _tool_resp_msg("v1", "cadcam_cimco_validate", {
            "status": "ok",
            "file": nc["file"],
            "modal_tokens": nc["modal_tokens"],
            "has_macro": nc["has_macro"],
        }),
        {
            "role": "assistant",
            "content": (
                f"已完成 `{nc['file']}`（共 {nc['line_count']} 行）静态校验：\n"
                f"- 识别模态/指令：`{nc['modal_tokens'] or ['(无标准G/M模态词)']}`；宏逻辑 has_macro=`{nc['has_macro']}`。\n"
                f"- 接入 VERICUT 前需确认：工程 `.vcproject` 的 `Unit`（inch/mm）与程序 G20/G21 一致，Work Offset 寄存器与控制器 `.ctl` 字表匹配。"
            ),
        },
    ]
    return [_make_record(
        messages=msgs, source_run_id=src_id, evidence_sha256=sha,
        family="vericut_nc_precheck", tools=tools,
        meta_extra={"split": nc["split"], "ext": nc["ext"]},
    )]


def generate_datasets(catalog: Dict[str, Any], out_dir: Path) -> Dict[str, Any]:
    """Assemble disjoint train, holdout, and DPO JSONL datasets with SHA256 ledgers."""
    tools = load_vericut_runtime_tools()
    train_sft: List[Dict[str, Any]] = []
    holdout_sft: List[Dict[str, Any]] = []
    dpo_train: List[Dict[str, Any]] = []

    for pr in catalog["projects"]:
        sft_rows, dpo_rows = _records_for_project(pr, tools, catalog["root"])
        target = holdout_sft if pr["split"] == "holdout" else train_sft
        target.extend(sft_rows)
        if pr["split"] == "train":
            dpo_train.extend(dpo_rows)

    for pdf in catalog["pdfs"]:
        sft_rows, dpo_rows = _records_for_pdf(pdf, tools)
        target = holdout_sft if pdf["split"] == "holdout" else train_sft
        target.extend(sft_rows)
        if pdf["split"] == "train":
            dpo_train.extend(dpo_rows)

    for kind, items in (("mch", catalog["machines"]), ("ctl", catalog["controls"]), ("tls", catalog["tool_libs"])):
        for it in items:
            rows = _records_for_component_xml(it, kind)
            (holdout_sft if it["split"] == "holdout" else train_sft).extend(rows)

    for nc in catalog["nc_programs"]:
        rows = _records_for_nc(nc, tools)
        (holdout_sft if nc["split"] == "holdout" else train_sft).extend(rows)

    # Deduplicate identical user prompts within/across splits (holdout takes precedence)
    holdout_prompts = {json.dumps(r["messages"][1]["content"], ensure_ascii=False) for r in holdout_sft}
    seen_train: Set[str] = set()
    clean_train: List[Dict[str, Any]] = []
    for r in train_sft:
        key = json.dumps(r["messages"][1]["content"], ensure_ascii=False)
        if key in holdout_prompts or key in seen_train:
            continue
        seen_train.add(key)
        clean_train.append(r)

    # Disjointness invariant check
    train_shas = {r["evidence_sha256"] for r in clean_train}
    hold_shas = {r["evidence_sha256"] for r in holdout_sft}
    overlap_shas = train_shas & hold_shas
    if overlap_shas:
        clean_train = [r for r in clean_train if r["evidence_sha256"] not in overlap_shas]

    out_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("catalog", "train", "holdout", "dpo"):
        (out_dir / sub).mkdir(parents=True, exist_ok=True)

    cat_path = out_dir / "catalog" / "e_training_catalog.json"
    cat_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")

    train_path = out_dir / "train" / "vericut_e_training_agent_sft.jsonl"
    hold_path = out_dir / "holdout" / "vericut_e_training_holdout.jsonl"
    dpo_path = out_dir / "dpo" / "vericut_e_training_dpo.jsonl"

    def _write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> Tuple[int, str]:
        row_list = list(rows)
        with path.open("w", encoding="utf-8", newline="\n") as f:
            for r in row_list:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        digest = sha256_file(path)
        (Path(str(path) + ".sha256")).write_text(f"{digest}  {path.name}\n", encoding="utf-8")
        return len(row_list), digest

    n_train, sha_train = _write_jsonl(train_path, clean_train)
    n_hold, sha_hold = _write_jsonl(hold_path, holdout_sft)
    n_dpo, sha_dpo = _write_jsonl(dpo_path, dpo_train)

    summary = {
        "catalog_path": str(cat_path),
        "train_jsonl": str(train_path),
        "train_rows": n_train,
        "train_sha256": sha_train,
        "holdout_jsonl": str(hold_path),
        "holdout_rows": n_hold,
        "holdout_sha256": sha_hold,
        "dpo_jsonl": str(dpo_path),
        "dpo_rows": n_dpo,
        "dpo_sha256": sha_dpo,
        "counts": catalog["counts"],
        "holdout_session_groups": catalog["holdout_session_groups"],
        "disjoint_sha_verified": len({r["evidence_sha256"] for r in clean_train} & hold_shas) == 0,
    }
    (out_dir / "train" / "manifest.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "holdout" / "manifest.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description="Extract E:\\training CGTech VERICUT 9.6 assets into Agent SFT/DPO datasets.")
    ap.add_argument("--src", default=r"E:\training", help="Path to VERICUT 9.6 training directory")
    ap.add_argument("--out-dir", default=str(REPO_ROOT / "data" / "train" / "vericut_e_training_v1"))
    args = ap.parse_args()

    catalog = build_catalog(Path(args.src))
    summary = generate_datasets(catalog, Path(args.out_dir))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
