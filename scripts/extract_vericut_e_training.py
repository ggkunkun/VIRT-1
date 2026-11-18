#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""extract_vericut_e_training.py — 确定性解析 E:\\training 全部 VERICUT 9.6 资产。

产出：data/sft/vericut_e_training/extracted_facts.json
遵循 AGENTS.md §5 / §8 测量宪法：
  - 所有字段来自真实 XML / NC / SWP / TBL / PDF 文件实算解析（basis = parser_verified）
  - 记录每个源文件的 sha256 与相对路径，零虚构日志与数值
  - PDF 抽取需 PyMuPDF (`pymupdf`)，可用 Python312 运行本脚本生成 JSON 缓存，
    后续语料构造与测试在 .venv 中毫秒级纯 JSON 消费。
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SRC = Path(r"E:\training")
DEFAULT_OUT = ROOT / "data" / "sft" / "vericut_e_training" / "extracted_facts.json"

NC_EXTS = ("*.mcd", "*.nc", "*.eia", "*.sub", "*.spf", "*.mpf", "*.min", "*.tap")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 16):
            h.update(chunk)
    return h.hexdigest()


def _text(elem: Optional[ET.Element], tag: str, default: str = "") -> str:
    if elem is None:
        return default
    node = elem.find(tag)
    if node is None or node.text is None:
        return default
    return node.text.strip()


def _float(val: Any) -> Optional[float]:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def parse_vcproject(path: Path, src_root: Path) -> Dict[str, Any]:
    tree = ET.parse(path)
    root = tree.getroot()
    unit = root.attrib.get("Unit", "")
    setups = []
    for setup in root.findall("./Setup"):
        sname = setup.attrib.get("Name", "")
        sactive = setup.attrib.get("Active", "on")
        comps = []
        build = setup.find("Build")
        if build is not None:
            for comp in build.findall(".//Component"):
                ctype = comp.attrib.get("Type")
                cname = comp.attrib.get("Name", "")
                files = [
                    f.text.strip()
                    for f in comp.findall("./*/File") + comp.findall("./File")
                    if f.text and f.text.strip()
                ]
                # Deduplicate while keeping order
                seen = set()
                uniq_files = []
                for fl in files:
                    if fl not in seen:
                        seen.add(fl)
                        uniq_files.append(fl)
                if ctype in {"fixture", "stock", "design"} or uniq_files:
                    blocks = [dict(b.attrib) for b in comp.findall("./Block")]
                    cyls = [dict(c.attrib) for c in comp.findall("./Cylinder")]
                    comp_item: Dict[str, Any] = {
                        "name": cname,
                        "type": ctype or "",
                        "files": uniq_files,
                    }
                    if blocks:
                        comp_item["blocks"] = blocks
                    if cyls:
                        comp_item["cylinders"] = cyls
                    comps.append(comp_item)

        ncs = []
        for ncp in setup.findall("./NCPrograms/NCProgram"):
            nf = _text(ncp, "File")
            if nf:
                ncs.append({
                    "file": nf,
                    "use": ncp.attrib.get("Use", "on"),
                    "filter": ncp.attrib.get("Filter", "off"),
                })

        work_offsets = []
        gcode = setup.find("GCode")
        gcode_cfg = dict(gcode.attrib) if gcode is not None else {}
        if gcode is not None:
            for tbl in gcode.findall("Table"):
                tname = tbl.attrib.get("Name", "")
                if "Offset" in tname:
                    for row in tbl.findall("Row"):
                        vals = [v.text.strip() if v.text else "" for v in row.findall("Value")]
                        if vals:
                            work_offsets.append({
                                "table": tname,
                                "index": row.attrib.get("Index", ""),
                                "subindex": row.attrib.get("SubIndex", ""),
                                "system": _text(row, "System"),
                                "values": vals[:6],
                            })

        tool_el = setup.find("Tool")
        tool_cfg = {}
        if tool_el is not None:
            for k in (
                "Change", "Control", "HolderStockCollisionOnOff",
                "HolderFixtureCollisionOnOff", "CutterFixtureCollision",
                "ShankPlungeError", "Gouge", "Tol", "Excess", "Minimum",
            ):
                if k in tool_el.attrib:
                    tool_cfg[k] = tool_el.attrib[k]

        motion_el = setup.find("Motion")
        motion_cfg = {}
        if motion_el is not None:
            for k in ("Fast", "SpinCheck", "SpindleOn", "LimitsCheck", "CheckCoolant", "Cycle"):
                if k in motion_el.attrib:
                    motion_cfg[k] = motion_el.attrib[k]

        mach_el = setup.find("Machine")
        mach_file = _text(mach_el, "File")
        coll_el = mach_el.find("Collision") if mach_el is not None else None
        trav_el = mach_el.find("Travel") if mach_el is not None else None
        coll_cfg = dict(coll_el.attrib) if coll_el is not None else {}
        if coll_el is not None:
            coll_cfg["between_count"] = len(coll_el.findall("Between"))
        trav_cfg = dict(trav_el.attrib) if trav_el is not None else {}

        opt_el = setup.find("Optimization")
        opt_cfg = {}
        if opt_el is not None:
            opt_cfg["material"] = _text(opt_el, "Material")
            opt_cfg["output_file"] = _text(opt_el, "OutputFile")
            s_el = opt_el.find("Settings")
            l_el = opt_el.find("Learn")
            if s_el is not None:
                opt_cfg["settings"] = dict(s_el.attrib)
            if l_el is not None:
                opt_cfg["learn"] = dict(l_el.attrib)

        setups.append({
            "name": sname,
            "active": sactive,
            "machine_file": mach_file,
            "machine_up": mach_el.attrib.get("Up", "") if mach_el is not None else "",
            "control_file": _text(setup.find("Control"), "File"),
            "tool_library": _text(setup.find("ToolMan"), "Library"),
            "assembly_library": _text(setup.find("AssemblyMan"), "Library"),
            "components": comps,
            "nc_programs": ncs,
            "work_offsets": work_offsets,
            "gcode_cfg": gcode_cfg,
            "tool_cfg": tool_cfg,
            "motion_cfg": motion_cfg,
            "collision_cfg": coll_cfg,
            "travel_cfg": trav_cfg,
            "optimization_cfg": opt_cfg,
        })

    return {
        "rel_path": os.path.relpath(path, src_root).replace("\\", "/"),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "root_tag": root.tag,
        "version": root.attrib.get("Version", ""),
        "unit": unit,
        "log_file": _text(root, "Log"),
        "setups": setups,
    }


def parse_tls(path: Path, src_root: Path) -> Dict[str, Any]:
    root = ET.parse(path).getroot()
    tools = []
    # Top-level tools sit directly under <Tools>/Tool
    parent = root.find("Tools")
    candidates = parent.findall("Tool") if parent is not None else root.findall("./Tool")
    for t in candidates:
        tid = t.attrib.get("ID", "")
        units = t.attrib.get("Units", "")
        desc = _text(t, "Description")
        ttype = _text(t, "Type")
        gp_el = t.find("GagePoint")
        gp = {
            "x": _float(_text(gp_el, "X")),
            "y": _float(_text(gp_el, "Y")),
            "z": _float(_text(gp_el, "Z")),
        } if gp_el is not None else None

        cutter_info: Dict[str, Any] = {}
        cutter_el = t.find("Cutter")
        if cutter_el is not None:
            for ch in list(cutter_el):
                if ch.tag in {"Apt", "Insert", "Tap", "Probe", "AdditiveBead", "Model"}:
                    cutter_info["subtype"] = ch.tag
                    cutter_info["spec_type"] = ch.attrib.get("Type", "")
                    for fld in ("D", "R", "E", "F", "A", "B", "H", "FluteLength",
                                "ShankDiameter", "TeethCount", "P1", "P2", "P3", "P4",
                                "Thickness", "SpindleDirection"):
                        val = _text(ch, fld)
                        if val:
                            num = _float(val)
                            cutter_info[fld] = num if num is not None else val
                    break

        holders = []
        holder_el = t.find("Holder")
        if holder_el is not None:
            for h_el in list(holder_el):
                if h_el.tag == "SOR":
                    zs = [_float(z.text) for z in h_el.findall("./Pt/Z") + h_el.findall("./PT/Z") + h_el.findall("./Z") if z.text]
                    xs = [_float(x.text) for x in h_el.findall("./Pt/X") + h_el.findall("./PT/X") + h_el.findall("./X") if x.text]
                    zs = [z for z in zs if z is not None]
                    xs = [x for x in xs if x is not None]
                    if zs or xs:
                        holders.append({
                            "id": h_el.attrib.get("ID", ""),
                            "parent_id": h_el.attrib.get("ParentID", ""),
                            "z_min": min(zs) if zs else None,
                            "z_max": max(zs) if zs else None,
                            "max_radius": max(abs(x) for x in xs) if xs else None,
                        })
                elif h_el.tag in {"STL", "Model", "Sweep", "Cone", "Cylinder", "Block"}:
                    hf = _text(h_el, "File")
                    holders.append({
                        "id": h_el.attrib.get("ID", h_el.tag),
                        "parent_id": h_el.attrib.get("ParentID", ""),
                        "tag": h_el.tag,
                        "file": hf,
                    })

        tools.append({
            "id": tid,
            "units": units,
            "description": desc,
            "type": ttype or cutter_info.get("subtype", ""),
            "coolant_thru": _text(t, "CoolantThru"),
            "gage_point": gp,
            "cutter": cutter_info,
            "holders": holders,
        })

    return {
        "rel_path": os.path.relpath(path, src_root).replace("\\", "/"),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "version": root.attrib.get("Version", ""),
        "tool_count": len(tools),
        "tools": tools,
    }


def parse_mch(path: Path, src_root: Path) -> Dict[str, Any]:
    root = ET.parse(path).getroot()
    unit = root.attrib.get("Unit", "")
    machine_name = root.attrib.get("Machine", "")
    subroutines = [f.text.strip() for f in root.findall("./Subroutines/File") if f.text and f.text.strip()]
    components = []
    for comp in root.findall(".//Component"):
        cname = comp.attrib.get("Name", "")
        ctype = comp.attrib.get("Type", "")
        attach = _text(comp, "Attach")
        subsys = comp.attrib.get("Subsystem", "1")
        pos_el = comp.find("Position")
        pos = dict(pos_el.attrib) if pos_el is not None else {}
        link_el = comp.find("Link")
        link = dict(link_el.attrib) if link_el is not None else {}
        components.append({
            "name": cname,
            "type": ctype,
            "subsystem": subsys,
            "attach": attach,
            "position": pos,
            "link": link,
        })

    # Trace attach hierarchy strings
    by_name = {c["name"]: c for c in components if c["name"]}
    paths = {}
    for c in components:
        cname = c["name"]
        if not cname or c["type"] not in {"tool", "attach", "spindle", "rotary", "linear"}:
            continue
        chain = [cname]
        cur = c
        seen = {cname}
        while cur.get("attach") and cur["attach"] in by_name and cur["attach"] not in seen:
            parent_name = cur["attach"]
            chain.append(parent_name)
            seen.add(parent_name)
            cur = by_name[parent_name]
        paths[cname] = " -> ".join(reversed(chain))

    return {
        "rel_path": os.path.relpath(path, src_root).replace("\\", "/"),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "machine_name": machine_name,
        "unit": unit,
        "subroutines": subroutines,
        "components": components,
        "kinematic_paths": paths,
    }


def parse_ctl(path: Path, src_root: Path) -> Dict[str, Any]:
    root = ET.parse(path).getroot()
    css_el = root.find("ConstSurfSpeed")
    words_summary = {}
    important = {"#", "G", "M", "T", "S", "F", "H", "D", "X", "Y", "Z", "A", "B", "C",
                 "G43", "G43.4", "TRAORI", "DO", "END", "WHILE", "GOTO", "IF", "RTCP", "M6", "M98"}
    all_word_names = []
    macro_words = []
    func_words = []
    for w in root.findall("./Words/Word"):
        wname = w.attrib.get("Name", "")
        wtype = w.attrib.get("Type", "")
        if wname:
            all_word_names.append(wname)
            if wtype == "function_call":
                func_words.append(wname)
            if wname in important or wtype in {"variable_tag"}:
                val = w.find("Value")
                words_summary[wname] = {
                    "type": wtype,
                    "inch_fmt": val.attrib.get("InchFormat", "") if val is not None else "",
                    "metric_fmt": val.attrib.get("MetricFormat", "") if val is not None else "",
                }
            if wname in {"WHILE", "DO", "END", "GOTO", "IF", "#"}:
                macro_words.append(wname)

    comment = _text(root, "COMMENT")
    # Collect G/M code tables/events concisely
    events = []
    for g_el in root.findall(".//Event")[:40]:
        if g_el.attrib:
            events.append(dict(list(g_el.attrib.items())[:5]))

    return {
        "rel_path": os.path.relpath(path, src_root).replace("\\", "/"),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "unit": root.attrib.get("Unit", ""),
        "comment": comment,
        "max_rpm": css_el.attrib.get("MaxRPM") if css_el is not None else None,
        "word_count": len(all_word_names),
        "macro_support": sorted(set(macro_words)),
        "function_words": sorted(set(func_words))[:20],
        "key_words": words_summary,
    }


def parse_swp(path: Path, src_root: Path) -> Dict[str, Any]:
    raw_txt = path.read_text(encoding="utf-8", errors="replace").strip()
    info: Dict[str, Any] = {
        "rel_path": os.path.relpath(path, src_root).replace("\\", "/"),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "format": "unknown",
    }
    if raw_txt.startswith("<"):
        root = ET.fromstring(raw_txt)
        swp = root.find("SWEEP") if root.tag != "SWEEP" else root
        if swp is None:
            swp = root.find(".//SWEEP")
        if swp is not None:
            zmin = _float(swp.attrib.get("Zmin"))
            zmax = _float(swp.attrib.get("Zmax"))
            pts = []
            for pt in swp.findall("PT"):
                xv = _float(_text(pt, "X"))
                yv = _float(_text(pt, "Y"))
                if xv is not None and yv is not None:
                    pts.append((xv, yv))
            info.update({
                "format": "xml_sweep",
                "z_min": zmin,
                "z_max": zmax,
                "length": round(zmax - zmin, 6) if (zmin is not None and zmax is not None) else None,
                "pt_count": len(pts),
                "x_bounds": [min(p[0] for p in pts), max(p[0] for p in pts)] if pts else None,
                "y_bounds": [min(p[1] for p in pts), max(p[1] for p in pts)] if pts else None,
            })
    elif raw_txt.startswith("VERICUT-model"):
        lines = [ln.strip() for ln in raw_txt.splitlines() if ln.strip()]
        pts = []
        zs = []
        for ln in lines[2:]:
            toks = ln.split()
            if len(toks) == 2:
                a, b = _float(toks[0]), _float(toks[1])
                if a is not None and b is not None:
                    pts.append((a, b))
            elif len(toks) == 1:
                v = _float(toks[0])
                if v is not None:
                    zs.append(v)
        info.update({
            "format": "ascii_sweep_v51",
            "version_line": lines[1] if len(lines) > 1 else "",
            "z_candidates": zs[:4],
            "pt_count": len(pts),
            "x_bounds": [min(p[0] for p in pts), max(p[0] for p in pts)] if pts else None,
            "y_bounds": [min(p[1] for p in pts), max(p[1] for p in pts)] if pts else None,
        })
    return info


_CODE_TOKEN_RE = re.compile(r"([GMTgm][0-9]+(?:\.[0-9]+)?)|([XYZABCUVWxyzabcuvw][-+]?[0-9]*\.?[0-9]+)|([SFsf][0-9]+(?:\.[0-9]+)?)")


def parse_nc(path: Path, src_root: Path) -> Dict[str, Any]:
    txt = path.read_text(encoding="utf-8", errors="replace")
    lines = txt.splitlines()
    g_codes = set()
    m_codes = set()
    t_codes = []
    s_vals = []
    f_vals = []
    g49_lines = []
    g28_lines = []
    has_g20 = False
    has_g21 = False
    has_rtcp = False
    for idx, line in enumerate(lines, 1):
        up = line.upper()
        # Strip (...) comments for code extraction
        clean = re.sub(r"\([^)]*\)", " ", up).split(";")[0]
        if not clean.strip():
            continue
        for gm in re.findall(r"\bG0*([0-9]+(?:\.[0-9]+)?)", clean):
            code = "G" + gm
            g_codes.add(code)
            if gm == "20":
                has_g20 = True
            elif gm == "21":
                has_g21 = True
            elif gm in {"43.4", "43.5"}:
                has_rtcp = True
            elif gm == "49":
                g49_lines.append(idx)
            elif gm == "28":
                g28_lines.append(idx)
        if "TRAORI" in clean:
            has_rtcp = True
        for mm in re.findall(r"\bM0*([0-9]+)", clean):
            m_codes.add("M" + mm)
        for tm in re.findall(r"\bT([0-9]+(?:\.[0-9]+)?)", clean):
            if tm not in t_codes:
                t_codes.append(tm)
        for sm in re.findall(r"\bS([0-9]+(?:\.[0-9]+)?)", clean):
            v = _float(sm)
            if v is not None:
                s_vals.append(v)
        for fm in re.findall(r"\bF([0-9]+(?:\.[0-9]+)?)", clean):
            v = _float(fm)
            if v is not None:
                f_vals.append(v)

    return {
        "rel_path": os.path.relpath(path, src_root).replace("\\", "/"),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "ext": path.suffix.lower(),
        "line_count": len(lines),
        "unit_modal": "inch (G20)" if has_g20 and not has_g21 else ("mm (G21)" if has_g21 and not has_g20 else ("mixed" if (has_g20 and has_g21) else "unspecified")),
        "has_rtcp": has_rtcp,
        "tools": t_codes[:25],
        "g_codes": sorted(g_codes)[:40],
        "m_codes": sorted(m_codes)[:30],
        "max_rpm": max(s_vals) if s_vals else None,
        "min_feed": min(f_vals) if f_vals else None,
        "max_feed": max(f_vals) if f_vals else None,
        "g49_lines": g49_lines,
        "g28_lines": g28_lines,
        "head_lines": [ln for ln in lines[:18] if ln.strip()],
    }


def read_tbl(path: Path) -> List[Dict[str, str]]:
    out = []
    if not path.exists():
        return out
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("!"):
                continue
            parts = [p.strip() for p in s.split(";")]
            if len(parts) >= 4:
                out.append({
                    "title": parts[0],
                    "pdf_rel": parts[1].replace("\\", "/"),
                    "project": parts[2],
                    "category_id": parts[3],
                })
    return out


def parse_pdfs(src_root: Path, tbl_rows: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    import pymupdf
    by_pdf_rel: Dict[str, List[Dict[str, str]]] = {}
    for row in tbl_rows:
        by_pdf_rel.setdefault(row["pdf_rel"].lower(), []).append(row)

    pdfs = sorted((src_root / "training_sessions").rglob("*.pdf"))
    results = []
    for p in pdfs:
        rel = os.path.relpath(p, src_root).replace("\\", "/")
        rel_sess = os.path.relpath(p, src_root / "training_sessions").replace("\\", "/").lower()
        doc = pymupdf.open(str(p))
        pages = []
        steps = []
        full_chunks = []
        for idx, page in enumerate(doc, 1):
            t = page.get_text("text")
            pages.append(t)
            full_chunks.append(t)
            for ln in t.splitlines():
                ls = ln.strip()
                if re.match(r"^\d{1,2}\.\s+[A-Z]", ls) and len(ls) > 6:
                    steps.append(ls)
        full_text = "\n".join(full_chunks)
        # Compact normalization preserving paragraph breaks
        lines_clean = [re.sub(r"\s+", " ", ln).strip() for ln in full_text.splitlines()]
        lines_clean = [ln for ln in lines_clean if ln]
        joined = "\n".join(lines_clean)

        meta_rows = by_pdf_rel.get(rel_sess, [])
        category = rel_sess.split("/")[0] if "/" in rel_sess else ""
        results.append({
            "rel_path": rel,
            "pdf_rel": rel_sess,
            "sha256": sha256_file(p),
            "bytes": p.stat().st_size,
            "category": category,
            "page_count": len(doc),
            "char_count": len(joined),
            "linked_sessions": meta_rows,
            "steps": steps[:25],
            "text_excerpt": joined[:3500],
            "full_text": joined,
        })
    return results


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="提取 E:\\training VERICUT 资产为可验证 JSON 缓存")
    ap.add_argument("--src", default=str(DEFAULT_SRC))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args(argv)

    src_root = Path(args.src)
    if not src_root.exists():
        raise SystemExit(f"[FATAL] 源目录不存在: {src_root}")

    vcps = sorted(
        list(src_root.glob("*.vcproject"))
        + list(src_root.glob("*.VcProject"))
        + list(src_root.glob("*.vdafproject")),
        key=lambda x: x.name.lower(),
    )
    # Deduplicate case-insensitive Windows glob hits
    seen_p = set()
    uniq_vcps = []
    for p in vcps:
        k = str(p).lower()
        if k not in seen_p:
            seen_p.add(k)
            uniq_vcps.append(p)

    tlss = sorted({str(p).lower(): p for p in src_root.glob("*.tls")}.values(), key=lambda x: x.name.lower())
    mchs = sorted({str(p).lower(): p for p in src_root.glob("*.mch")}.values(), key=lambda x: x.name.lower())
    ctls = sorted({str(p).lower(): p for p in src_root.glob("*.ctl")}.values(), key=lambda x: x.name.lower())
    swps = sorted({str(p).lower(): p for p in src_root.glob("*.swp")}.values(), key=lambda x: x.name.lower())
    nc_all = []
    for ext in NC_EXTS:
        nc_all.extend(src_root.glob(ext))
    ncs = sorted({str(p).lower(): p for p in nc_all}.values(), key=lambda x: x.name.lower())

    tbl_rows = (
        read_tbl(src_root / "training_sessions" / "training_index.tbl")
        + read_tbl(src_root / "training_sessions" / "vdaf_training_index.tbl")
    )

    out_data = {
        "source_root": str(src_root),
        "basis": "parser_verified",
        "counts": {
            "vcprojects": len(uniq_vcps),
            "tls": len(tlss),
            "mch": len(mchs),
            "ctl": len(ctls),
            "swp": len(swps),
            "nc": len(ncs),
            "tbl_rows": len(tbl_rows),
        },
        "training_index": tbl_rows,
        "vcprojects": [parse_vcproject(p, src_root) for p in uniq_vcps],
        "tls_libraries": [parse_tls(p, src_root) for p in tlss],
        "machines": [parse_mch(p, src_root) for p in mchs],
        "controls": [parse_ctl(p, src_root) for p in ctls],
        "sweeps": [parse_swp(p, src_root) for p in swps],
        "nc_programs": [parse_nc(p, src_root) for p in ncs],
        "pdfs": parse_pdfs(src_root, tbl_rows),
    }
    out_data["counts"]["pdfs"] = len(out_data["pdfs"])

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out_data, ensure_ascii=False, indent=2), encoding="utf-8")
    out_sha = sha256_file(out_path)
    print(json.dumps({
        "out": str(out_path),
        "sha256": out_sha,
        "counts": out_data["counts"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
