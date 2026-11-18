#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic evidence-grounded extractor for the three external CAD/CAM datasets.

Sources (strictly read-only):
  1. e:\\迅雷下载\\100台3C、锂电自动化设备量产图纸
  2. e:\\迅雷下载\\分享数模20-77套UG夹具图档
  3. e:\\迅雷下载\\建模练习图纸

Outputs (inside workspace):
  data/sft/six_software_real_assets/extracted_facts.json
  data/sft/six_software_real_assets/extracted_facts.json.sha256

Run under Python 3.12 (pymupdf, openpyxl, rapidocr_onnxruntime, OCP available):
  C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python312\\python.exe \\
      scripts/extract_six_software_real_assets.py --max-ocr 160 --workers 4
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import time
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR1 = Path(r"e:\迅雷下载\100台3C、锂电自动化设备量产图纸")
DEFAULT_DIR2 = Path(r"e:\迅雷下载\分享数模20-77套UG夹具图档")
DEFAULT_DIR3 = Path(r"e:\迅雷下载\建模练习图纸")
DEFAULT_UG_INSPECT = Path(
    r"E:\BaiduNetdiskDownload\NX 12.0.2.9\NX12.2.9waigua\NX12.2.9\NX\NXBIN\ug_inspect.exe"
)
DEFAULT_OUT_DIR = ROOT / "data" / "sft" / "six_software_real_assets"

IGNORED_SECURITY_NAMES = {"解压密码.htm", "desktop.ini", "thumbs.db"}
CAM_OP_KEYWORDS = (
    "CAVITY_MILL",
    "ZLEVEL_PROFILE",
    "PLANAR_MILL",
    "FLOOR_WALL",
    "FIXED_CONTOUR",
    "CONTOUR_AREA",
    "FACE_MILLING",
    "HOLE_MAKING",
    "SOLID_PROFILE_3D",
    "DRILL",
    "SPOT_DRILLING",
    "TAPPING",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# OLE2 CFB & PropertySet parser (SolidWorks .SLDPRT / .SLDASM / .SLDDRW)
# ---------------------------------------------------------------------------
def read_ole2_streams(path: Path, targets: set[str]) -> Dict[str, bytes]:
    """Read selected streams from an OLE2 Compound File Binary without external deps."""
    buf = path.read_bytes()
    if len(buf) < 512 or buf[:8] != b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return {}
    sec_shift = struct.unpack_from("<H", buf, 0x1E)[0]
    if sec_shift not in (9, 12):
        return {}
    sec_size = 1 << sec_shift
    max_sec = max(1, (len(buf) // sec_size) + 2)
    mini_cutoff = struct.unpack_from("<I", buf, 0x38)[0]
    first_dir = struct.unpack_from("<i", buf, 0x30)[0]
    first_mfat = struct.unpack_from("<i", buf, 0x3C)[0]
    num_fat = struct.unpack_from("<I", buf, 0x2C)[0]
    first_difat = struct.unpack_from("<i", buf, 0x44)[0]

    fat_secs = [s for s in struct.unpack_from("<109i", buf, 0x4C) if s >= 0]
    cur_difat = first_difat
    seen_difat: set[int] = set()
    while 0 <= cur_difat < max_sec and cur_difat not in seen_difat and len(fat_secs) < num_fat:
        seen_difat.add(cur_difat)
        off = (cur_difat + 1) * sec_size
        if off + sec_size > len(buf):
            break
        chunk = struct.unpack_from(f"<{sec_size // 4}i", buf, off)
        fat_secs.extend(s for s in chunk[:-1] if s >= 0)
        cur_difat = chunk[-1]
    fat_secs = fat_secs[:num_fat]

    fat: List[int] = []
    for s in fat_secs:
        off = (s + 1) * sec_size
        if off + sec_size <= len(buf):
            fat.extend(struct.unpack_from(f"<{sec_size // 4}i", buf, off))

    def read_chain(start: int, max_bytes: int = 8 * 1024 * 1024) -> bytes:
        out = bytearray()
        s = start
        seen: set[int] = set()
        while 0 <= s < len(fat) and s not in seen and len(out) < max_bytes:
            seen.add(s)
            off = (s + 1) * sec_size
            if off + sec_size > len(buf):
                break
            out.extend(buf[off : off + sec_size])
            s = fat[s]
        return bytes(out)

    dir_bytes = read_chain(first_dir, 4 * 1024 * 1024)
    if len(dir_bytes) < 128:
        return {}
    root_start, root_sz = struct.unpack_from("<iI", dir_bytes, 0x74)
    mini_stream = read_chain(root_start, min(max(root_sz, 4096), 4 * 1024 * 1024))[:root_sz] if root_start >= 0 else b""
    mfat_bytes = read_chain(first_mfat, 2 * 1024 * 1024) if first_mfat >= 0 else b""
    mfat = list(struct.unpack_from(f"<{len(mfat_bytes) // 4}i", mfat_bytes)) if mfat_bytes else []

    def read_mini(start: int, sz: int) -> bytes:
        out = bytearray()
        s = start
        seen: set[int] = set()
        while 0 <= s < len(mfat) and s not in seen and len(out) < sz:
            seen.add(s)
            off = s * 64
            if off + 64 > len(mini_stream):
                break
            out.extend(mini_stream[off : off + 64])
            s = mfat[s]
        return bytes(out[:sz])

    res: Dict[str, bytes] = {}
    for i in range(0, len(dir_bytes), 128):
        ent = dir_bytes[i : i + 128]
        if len(ent) < 128:
            break
        nlen = struct.unpack_from("<H", ent, 0x40)[0]
        if ent[0x42] != 2:
            continue
        name = ent[: max(0, min(nlen, 64) - 2)].decode("utf-16le", errors="ignore")
        if name not in targets:
            continue
        ss = struct.unpack_from("<i", ent, 0x74)[0]
        sz = struct.unpack_from("<I", ent, 0x78)[0]
        if sz == 0:
            continue
        if sz < mini_cutoff:
            res[name] = read_mini(ss, sz)
        else:
            res[name] = read_chain(ss, min(sz + sec_size, 8 * 1024 * 1024))[:sz]
    return res


def _decode_oledata(raw_b: bytes, cp: str) -> str:
    stripped = raw_b.rstrip(b"\x00")
    if not stripped:
        return ""
    for enc in (cp, "utf-8", "cp936", "cp950", "cp1252"):
        try:
            s = stripped.decode(enc)
            # Heuristic: reject classic UTF-8 misdecoded as cp950/cp936 gibberish when utf-8 succeeds
            if enc != "utf-8":
                try:
                    u = stripped.decode("utf-8")
                    if any("\u4e00" <= c <= "\u9fff" for c in u) and enc in ("cp1252", "cp950"):
                        continue
                except UnicodeDecodeError:
                    pass
            return s.strip()
        except UnicodeDecodeError:
            continue
    return stripped.decode(cp, errors="replace").strip()


def parse_ole_propset(raw: bytes) -> Dict[str, Any]:
    """Parse MS-OLEPS PropertySet stream with codepage-first pass."""
    if len(raw) < 48:
        return {}
    num_sec = struct.unpack_from("<I", raw, 0x18)[0]
    out: Dict[str, Any] = {}
    for si in range(min(num_sec, 4)):
        sec_off_pos = 0x1C + si * 20 + 16
        if sec_off_pos + 4 > len(raw):
            continue
        sec_off = struct.unpack_from("<I", raw, sec_off_pos)[0]
        if sec_off + 8 > len(raw):
            continue
        _sec_sz, nprops = struct.unpack_from("<II", raw, sec_off)
        entries: List[Tuple[int, int]] = []
        for pi in range(min(nprops, 256)):
            pbase = sec_off + 8 + pi * 8
            if pbase + 8 > len(raw):
                break
            pid, rel_off = struct.unpack_from("<II", raw, pbase)
            entries.append((pid, sec_off + rel_off))

        # Pass 1: find codepage (pid == 1)
        cp = "cp936"
        cp_map = {65001: "utf-8", 936: "cp936", 950: "cp950", 1252: "cp1252"}
        for pid, off in entries:
            if pid == 1 and off + 8 <= len(raw):
                vtype = struct.unpack_from("<I", raw, off)[0]
                if vtype == 2:
                    raw_cp = struct.unpack_from("<H", raw, off + 4)[0]
                    cp = cp_map.get(raw_cp, cp)

        prop_names: Dict[int, str] = {}
        props: Dict[int, Any] = {}
        for pid, off in entries:
            if pid == 0:
                if off + 4 > len(raw):
                    continue
                cnt = struct.unpack_from("<I", raw, off)[0]
                p = off + 4
                for _ in range(min(cnt, 256)):
                    if p + 8 > len(raw):
                        break
                    dpid, nch = struct.unpack_from("<II", raw, p)
                    p += 8
                    if p + nch > len(raw):
                        break
                    nm = _decode_oledata(raw[p : p + nch], cp)
                    prop_names[dpid] = nm
                    p += nch
                break

        for pid, off in entries:
            if pid in (0, 1) or off + 8 > len(raw):
                continue
            vtype = struct.unpack_from("<I", raw, off)[0]
            val: Any = None
            if vtype == 30:  # VT_LPSTR
                nch = struct.unpack_from("<I", raw, off + 4)[0]
                if off + 8 + nch <= len(raw):
                    val = _decode_oledata(raw[off + 8 : off + 8 + nch], cp)
            elif vtype == 31:  # VT_LPWSTR
                nch = struct.unpack_from("<I", raw, off + 4)[0]
                if off + 8 + nch * 2 <= len(raw):
                    val = raw[off + 8 : off + 8 + nch * 2].decode("utf-16le", errors="replace").rstrip("\x00").strip()
            elif vtype == 2:
                val = struct.unpack_from("<h", raw, off + 4)[0]
            elif vtype == 3:
                val = struct.unpack_from("<i", raw, off + 4)[0]
            elif vtype == 5:
                val = struct.unpack_from("<d", raw, off + 4)[0]
            elif vtype == 11:
                val = bool(struct.unpack_from("<H", raw, off + 4)[0])
            if val is not None and val != "":
                key = prop_names.get(pid, f"pid_{pid}")
                if si == 0:
                    std_map = {
                        "pid_2": "title",
                        "pid_3": "subject",
                        "pid_4": "author",
                        "pid_5": "keywords",
                        "pid_6": "comments",
                        "pid_8": "last_saved_by",
                        "pid_9": "revision",
                    }
                    key = std_map.get(key, key)
                out[key] = val
    return out


_SW_REF_RE = re.compile(
    r"([A-Za-z0-9_\-\u4e00-\u9fff()（）\[\] .]{2,110}\.(?:SLDPRT|SLDASM|sldprt|sldasm))"
)


_SW_PATH_U16_RE = re.compile(
    r"(?:[A-Za-z]:\\|Documents\\)[^\x00-\x1f\"*?<>|]{2,140}\.(?:SLDPRT|SLDASM|sldprt|sldasm)"
)


def extract_sw_header2_refs(raw: bytes, self_name: str, full_file_bytes: Optional[bytes] = None) -> List[str]:
    """Extract clean referenced .SLDPRT/.SLDASM filenames from Header2 or full UTF-16LE path table."""
    refs: List[str] = []
    seen: set[str] = set()
    self_low = self_name.lower()
    if full_file_bytes:
        u16_full = full_file_bytes.decode("utf-16le", errors="ignore")
        for m in _SW_PATH_U16_RE.finditer(u16_full):
            base = m.group(0).replace("/", "\\").split("\\")[-1].strip()
            if (
                base
                and 5 <= len(base) <= 90
                and base.lower() != self_low
                and not any(ord(c) < 32 for c in base)
                and base.lower() not in seen
            ):
                seen.add(base.lower())
                refs.append(base)
                if len(refs) >= 80:
                    return refs
    if raw:
        for text in (
            raw.decode("utf-16le", errors="ignore"),
            raw.decode("ascii", errors="ignore"),
        ):
            for m in _SW_REF_RE.finditer(text):
                item = m.group(1).strip().strip("\\/")
                base = item.replace("/", "\\").split("\\")[-1].strip()
                if (
                    not base
                    or len(base) < 5
                    or len(base) > 90
                    or base.lower() == self_low
                    or any(ord(c) < 32 for c in base)
                ):
                    continue
                low = base.lower()
                if low not in seen:
                    seen.add(low)
                    refs.append(base)
                if len(refs) >= 80:
                    return refs
    return refs


def parse_solidworks_ole2(path: Path) -> Dict[str, Any]:
    """Extract verified metadata from a single OLE2 SolidWorks file."""
    streams = read_ole2_streams(
        path,
        {
            "\x05DocumentSummaryInformation",
            "\x05SummaryInformation",
            "Header2",
            "ISolidWorksInformation",
        },
    )
    dsi = parse_ole_propset(streams.get("\x05DocumentSummaryInformation", b""))
    si = parse_ole_propset(streams.get("\x05SummaryInformation", b""))

    # Filter raw unnamed pid_* keys, unresolved SolidWorks tag echoes & empty placeholders
    clean_props: Dict[str, Any] = {}
    for k, v in dsi.items():
        if k.startswith("pid_"):
            continue
        if isinstance(v, str) and v.startswith('"SW-'):
            continue
        if isinstance(v, str) and not v.strip():
            continue
        if isinstance(v, str) and v.strip() in {"“图样名称”", "“图样代号”", "- 无 -"}:
            continue
        clean_props[k] = v

    summary_clean = {
        k: v
        for k, v in si.items()
        if not k.startswith("pid_") and isinstance(v, str) and v.strip()
    }

    # Check if ISolidWorksInformation contains the 14-float mass-properties vector
    # AND cross-verify vector[5] (mass_kg) against DocumentSummaryInformation Weight/质量 if present.
    mass_props = None
    isi = streams.get("ISolidWorksInformation", b"")
    if isi:
        m = re.search(rb"((?:-?\d+\.\d{6},\s*){13}-?\d+\.\d{6})", isi)
        if m:
            nums = [float(x) for x in m.group(1).decode("ascii").split(",")]
            if len(nums) == 14:
                vol_m3, area_m2, mass_kg = nums[3], nums[4], nums[5]
                declared_wt = clean_props.get("Weight") or clean_props.get("质量") or clean_props.get("单重")
                wt_matches = False
                if declared_wt is not None:
                    try:
                        wt_f = float(str(declared_wt).strip())
                        wt_matches = abs(wt_f - mass_kg) <= max(0.005, 0.02 * abs(mass_kg))
                    except ValueError:
                        wt_matches = False
                if vol_m3 > 0 and area_m2 > 0 and mass_kg > 0 and (wt_matches or path.suffix.lower() == ".sldasm"):
                    mass_props = {
                        "com_m": [round(nums[0], 6), round(nums[1], 6), round(nums[2], 6)],
                        "volume_cm3": round(vol_m3 * 1e6, 4),
                        "surface_area_cm2": round(area_m2 * 1e4, 4),
                        "mass_kg": round(mass_kg, 6),
                        "cross_verified_weight_prop": wt_matches,
                    }

    refs: List[str] = []
    if path.suffix.lower() in (".sldasm", ".slddrw"):
        raw_bytes = path.read_bytes() if path.stat().st_size <= 32 * 1024 * 1024 else None
        refs = extract_sw_header2_refs(streams.get("Header2", b""), path.name, full_file_bytes=raw_bytes)

    return {
        "custom_properties": clean_props,
        "summary": summary_clean,
        "mass_properties": mass_props,
        "referenced_models": refs,
    }


# ---------------------------------------------------------------------------
# Dir 1 extractors: BOM XLSX, IGES + PDF pairs, STEP assembly, PNG
# ---------------------------------------------------------------------------
def extract_bom_xlsx(xlsx_path: Path, dir1: Path) -> Dict[str, Any]:
    import openpyxl

    wb = openpyxl.load_workbook(xlsx_path, data_only=True, read_only=True)
    sheets_out: List[Dict[str, Any]] = []
    for name in wb.sheetnames:
        ws = wb[name]
        raw_rows: List[List[str]] = []
        for row in ws.iter_rows(values_only=True):
            vals = [("" if c is None else str(c).strip()) for c in row]
            if any(vals):
                # Trim trailing empty columns
                while vals and vals[-1] == "":
                    vals.pop()
                raw_rows.append(vals)
        if not raw_rows:
            continue
        # Detect header row (first row with >=3 non-empty cells containing typical BOM column names)
        hdr_idx = -1
        for i, r in enumerate(raw_rows[:5]):
            joined = " ".join(r)
            if any(tok in joined for tok in ("图号", "型号", "名称", "材料", "数量")):
                hdr_idx = i
                break
        if hdr_idx == -1:
            continue
        headers = raw_rows[hdr_idx]
        # Skip leading blank cells uniformly
        lead = 0
        while lead < len(headers) and headers[lead] == "":
            lead += 1
        headers = headers[lead:]
        items: List[Dict[str, str]] = []
        for r in raw_rows[hdr_idx + 1 :]:
            sliced = r[lead:]
            row_dict = {}
            for col_i, hname in enumerate(headers):
                if not hname:
                    continue
                val = sliced[col_i] if col_i < len(sliced) else ""
                if val:
                    row_dict[hname] = val
            if row_dict and (row_dict.get("图号") or row_dict.get("型号") or row_dict.get("名称")):
                items.append(row_dict)
        if items:
            sheets_out.append({
                "sheet_name": name,
                "headers": [h for h in headers if h],
                "row_count": len(items),
                "rows": items,
            })
    return {
        "rel_path": str(xlsx_path.relative_to(dir1)),
        "sha256": sha256_file(xlsx_path),
        "sheets": sheets_out,
        "basis": "parser_verified",
    }


def _iges_global_meta(igs_path: Path) -> Dict[str, Any]:
    g_chunks: List[str] = []
    with open(igs_path, "r", encoding="gb18030", errors="replace") as f:
        for line in f:
            if len(line) >= 73 and line[72] == "G":
                g_chunks.append(line[:72].rstrip())
    g_str = "".join(g_chunks)
    # IGES delimiter-separated global params; standard comma/semicolon
    parts = g_str.split(",")
    orig_sw = None
    unit_name = "unknown"
    unit_flag = None
    for tok in parts[:18]:
        m_h = re.match(r"^\d+H(.+)$", tok.strip())
        if m_h and not orig_sw and ("SLD" in m_h.group(1).upper() or "." in m_h.group(1)):
            orig_sw = m_h.group(1)
        if m_h and m_h.group(1).upper() in ("MM", "INCH", "M", "CM"):
            unit_name = "mm" if m_h.group(1).upper() == "MM" else m_h.group(1).lower()
    m_uf = re.search(r",(\d+),(\d+H(?:MM|INCH|M|CM))", g_str)
    if m_uf:
        unit_flag = int(m_uf.group(1))
    return {"orig_model_name": orig_sw, "unit": unit_name, "unit_flag": unit_flag, "raw_global": g_str[:240]}


def measure_iges_part(igs_path: Path, dir1: Path) -> Dict[str, Any]:
    from OCP.IGESControl import IGESControl_Reader
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_SOLID, TopAbs_SHELL, TopAbs_FACE, TopAbs_EDGE
    from OCP.TopoDS import TopoDS
    from OCP.BRepAdaptor import BRepAdaptor_Surface, BRepAdaptor_Curve
    from OCP.GeomAbs import (
        GeomAbs_Plane, GeomAbs_Cylinder, GeomAbs_Cone, GeomAbs_Sphere,
        GeomAbs_Torus, GeomAbs_BSplineSurface, GeomAbs_Circle, GeomAbs_Line,
    )
    from OCP.GProp import GProp_GProps
    from OCP.BRepGProp import BRepGProp

    gmeta = _iges_global_meta(igs_path)
    rdr = IGESControl_Reader()
    st = rdr.ReadFile(str(igs_path))
    if st != IFSelect_RetDone:
        return {"rel_path": str(igs_path.relative_to(dir1)), "sha256": sha256_file(igs_path), "read_ok": False}
    rdr.TransferRoots()
    shape = rdr.OneShape()

    bx = Bnd_Box()
    BRepBndLib.Add_s(shape, bx)
    mn, mx = bx.CornerMin(), bx.CornerMax()
    dx = round(mx.X() - mn.X(), 3)
    dy = round(mx.Y() - mn.Y(), 3)
    dz = round(mx.Z() - mn.Z(), 3)
    dims_sorted = sorted([dx, dy, dz])

    def _count(kind) -> int:
        exp = TopExp_Explorer(shape, kind)
        n = 0
        while exp.More():
            n += 1
            exp.Next()
        return n

    n_solids = _count(TopAbs_SOLID)
    n_shells = _count(TopAbs_SHELL)
    n_edges = _count(TopAbs_EDGE)

    surf_counts = Counter()
    cyl_radii: set[float] = set()
    f_exp = TopExp_Explorer(shape, TopAbs_FACE)
    n_faces = 0
    while f_exp.More():
        n_faces += 1
        face = TopoDS.Face(f_exp.Current())
        adap = BRepAdaptor_Surface(face)
        stype = adap.GetType()
        if stype == GeomAbs_Plane:
            surf_counts["plane"] += 1
        elif stype == GeomAbs_Cylinder:
            surf_counts["cylinder"] += 1
            cyl_radii.add(round(adap.Cylinder().Radius(), 3))
        elif stype == GeomAbs_Cone:
            surf_counts["cone"] += 1
        elif stype == GeomAbs_Sphere:
            surf_counts["sphere"] += 1
        elif stype == GeomAbs_Torus:
            surf_counts["torus"] += 1
        elif stype == GeomAbs_BSplineSurface:
            surf_counts["bspline"] += 1
        else:
            surf_counts["other"] += 1
        f_exp.Next()

    circle_radii: set[float] = set()
    n_lines = 0
    e_exp = TopExp_Explorer(shape, TopAbs_EDGE)
    while e_exp.More():
        edge = TopoDS.Edge(e_exp.Current())
        cadap = BRepAdaptor_Curve(edge)
        ct = cadap.GetType()
        if ct == GeomAbs_Circle:
            circle_radii.add(round(cadap.Circle().Radius(), 3))
        elif ct == GeomAbs_Line:
            n_lines += 1
        e_exp.Next()

    s_props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(shape, s_props)
    area_mm2 = round(s_props.Mass(), 2)

    vol_mm3: Optional[float] = None
    if n_solids > 0:
        v_props = GProp_GProps()
        BRepGProp.VolumeProperties_s(shape, v_props)
        vm = v_props.Mass()
        if vm > 0:
            vol_mm3 = round(vm, 2)

    # Heuristic geometry classification based purely on measured dimensions/topology
    min_d, mid_d, max_d = dims_sorted
    if n_solids > 1 or (max_d > 500 and min_d > 80):
        kind = "weldment_or_subassembly"
    elif min_d <= 8.0 and mid_d >= 15.0:
        kind = "sheet_metal_plate"
    elif surf_counts.get("cylinder", 0) >= 2 and abs(mid_d - min_d) <= 2.0:
        kind = "shaft_or_rod"
    else:
        kind = "formed_bracket_or_machined"

    drawing_id = igs_path.stem.strip()
    return {
        "drawing_id": drawing_id,
        "rel_path": str(igs_path.relative_to(dir1)),
        "sha256": sha256_file(igs_path),
        "read_ok": True,
        "unit": gmeta["unit"],
        "orig_model_name": gmeta["orig_model_name"],
        "bbox_mm": {"dx": dx, "dy": dy, "dz": dz},
        "sorted_dims_mm": dims_sorted,
        "n_solids": n_solids,
        "n_shells": n_shells,
        "n_faces": n_faces,
        "n_edges": n_edges,
        "n_line_edges": n_lines,
        "surface_types": dict(surf_counts),
        "cylinder_radii_mm": sorted(cyl_radii)[:20],
        "circle_radii_mm": sorted(circle_radii)[:20],
        "surface_area_mm2": area_mm2,
        "volume_mm3": vol_mm3,
        "shape_class": kind,
        "basis": "measured_occt",
    }


def extract_pdf_drawing(pdf_path: Path, dir1: Path) -> Dict[str, Any]:
    import pymupdf

    doc = pymupdf.open(str(pdf_path))
    pages: List[Dict[str, Any]] = []
    all_lines: List[str] = []
    for i, page in enumerate(doc):
        w_mm = round(page.rect.width * 25.4 / 72.0, 1)
        h_mm = round(page.rect.height * 25.4 / 72.0, 1)
        text = page.get_text("text") or ""
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        all_lines.extend(lines)
        pages.append({
            "page": i + 1,
            "paper_size_mm": [w_mm, h_mm],
            "text_lines": lines[:80],
        })

    # Clean drawing id from filename like "BZJ-A-01 - 图纸4(2).pdf"
    stem = pdf_path.stem
    m_id = re.match(r"^(BZJ-[A-Za-z0-9\-]+?)(?:\s*-\s*图纸.*)?$", stem)
    drawing_id = m_id.group(1) if m_id else stem

    # Extract numeric dimension tokens cleanly
    num_tokens: List[float] = []
    seen_num: set[float] = set()
    for ln in all_lines:
        for tok in re.findall(r"\b\d+(?:\.\d+)?\b", ln):
            v = float(tok)
            if v not in seen_num and 0.05 <= v <= 5000.0:
                seen_num.add(v)
                num_tokens.append(v)

    notes = [ln for ln in all_lines if any(k in ln for k in ("技术要求", "未注", "表面", "折弯", "毛刺", "孔", "公差", "RAL", "A3"))]
    return {
        "drawing_id": drawing_id,
        "rel_path": str(pdf_path.relative_to(dir1)),
        "sha256": sha256_file(pdf_path),
        "page_count": len(doc),
        "pages": pages,
        "extracted_numbers": sorted(num_tokens)[:60],
        "notes_or_reqs": notes[:20],
        "basis": "parser_verified",
    }


def extract_step_assembly_summary(step_path: Path, dir1: Path) -> Dict[str, Any]:
    """Fast streaming GB18030 STEP AP203/214 BOM & placement summary."""
    header_lines: List[str] = []
    units: List[str] = []
    products: Dict[int, str] = {}
    pd_to_form: Dict[int, int] = {}
    form_to_prod: Dict[int, int] = {}
    nauo_edges: List[Tuple[int, int]] = []
    breps: List[str] = []

    in_hdr = False
    re_id_head = re.compile(r"^#(\d+)\s*=\s*(.+)$")
    with open(step_path, "r", encoding="gb18030", errors="replace") as f:
        for raw_ln in f:
            s = raw_ln.strip()
            if s == "HEADER;":
                in_hdr = True
                continue
            if s == "ENDSEC;":
                in_hdr = False
                continue
            if in_hdr:
                if len(header_lines) < 16:
                    header_lines.append(s)
                continue
            if "LENGTH_UNIT" in s or "PLANE_ANGLE_UNIT" in s:
                if len(units) < 8:
                    units.append(s[:120])
            if not s.startswith("#"):
                continue
            m = re_id_head.match(s)
            if not m:
                continue
            eid = int(m.group(1))
            rhs = m.group(2)
            if rhs.startswith("PRODUCT (") or rhs.startswith("PRODUCT("):
                mp = re.search(r"PRODUCT\s*\(\s*'([^']*)'", rhs)
                if mp:
                    products[eid] = mp.group(1)
            elif rhs.startswith("PRODUCT_DEFINITION_FORMATION"):
                refs = [int(x) for x in re.findall(r"#(\d+)", rhs)]
                if refs:
                    form_to_prod[eid] = refs[-1]
            elif rhs.startswith("PRODUCT_DEFINITION (") or rhs.startswith("PRODUCT_DEFINITION("):
                refs = [int(x) for x in re.findall(r"#(\d+)", rhs)]
                if refs:
                    pd_to_form[eid] = refs[0]
            elif rhs.startswith("NEXT_ASSEMBLY_USAGE_OCCURRENCE"):
                refs = [int(x) for x in re.findall(r"#(\d+)", rhs)]
                if len(refs) >= 2:
                    nauo_edges.append((refs[0], refs[1]))
            elif rhs.startswith("MANIFOLD_SOLID_BREP"):
                mb = re.search(r"MANIFOLD_SOLID_BREP\s*\(\s*'([^']*)'", rhs)
                breps.append(mb.group(1) if mb else "")

    def prod_name_for_pd(pd: int) -> str:
        fm = pd_to_form.get(pd)
        pr = form_to_prod.get(fm) if fm is not None else None
        return products.get(pr, f"pd#{pd}") if pr is not None else f"pd#{pd}"

    parent_children: Dict[str, Counter] = defaultdict(Counter)
    all_parents: set[str] = set()
    all_children: set[str] = set()
    for p_pd, c_pd in nauo_edges:
        pn = prod_name_for_pd(p_pd)
        cn = prod_name_for_pd(c_pd)
        # Strip "-Part-NNN" / "_asm-..." suffix lightly only for summary grouping
        all_parents.add(pn)
        all_children.add(cn)
        base_cn = re.sub(r"\.sldasm-Part-\d+$", "", cn, flags=re.I)
        parent_children[pn][base_cn] += 1

    roots = sorted(all_parents - all_children)
    length_unit = "mm" if any(".MILLI." in u and ".METRE." in u for u in units) else "unknown"
    tree_summary = {
        k: dict(v.most_common(40))
        for k, v in sorted(parent_children.items(), key=lambda kv: -sum(kv[1].values()))[:25]
    }
    return {
        "rel_path": str(step_path.relative_to(dir1)),
        "sha256": sha256_file(step_path),
        "size_bytes": step_path.stat().st_size,
        "header_snippet": " ".join(header_lines)[:400],
        "length_unit": length_unit,
        "product_count": len(products),
        "nauo_instance_count": len(nauo_edges),
        "solid_brep_count": len(breps),
        "root_assemblies": roots[:10],
        "sample_products": list(products.values())[:25],
        "hierarchy_grouped": tree_summary,
        "basis": "parser_verified",
    }


def extract_automation_dir1(dir1: Path, use_ocr_for_png: bool = True) -> Dict[str, Any]:
    """Walk Directory 1, deduplicate by SHA256, and extract OLE2/BOM/IGES/PDF/STEP."""
    by_sha: Dict[str, Dict[str, Any]] = {}
    projects: Dict[str, Dict[str, Any]] = {}
    ignored_locks = 0
    ignored_security = 0
    ole2_parts: List[Dict[str, Any]] = []
    ole2_asms: List[Dict[str, Any]] = []
    ole2_drws: List[Dict[str, Any]] = []
    bom_tables: List[Dict[str, Any]] = []
    iges_map: Dict[str, Dict[str, Any]] = {}
    pdf_map: Dict[str, Dict[str, Any]] = {}
    step_list: List[Dict[str, Any]] = []
    png_list: List[Dict[str, Any]] = []

    ocr_engine = None
    if use_ocr_for_png:
        from rapidocr_onnxruntime import RapidOCR
        ocr_engine = RapidOCR()

    for p in sorted(dir1.rglob("*")):
        if not p.is_file():
            continue
        low_name = p.name.lower()
        if low_name in IGNORED_SECURITY_NAMES:
            ignored_security += 1
            continue
        if p.name.startswith("~$"):
            ignored_locks += 1
            continue

        rel = str(p.relative_to(dir1))
        proj = p.relative_to(dir1).parts[0]
        p_info = projects.setdefault(
            proj,
            {
                "project": proj,
                "total_files": 0,
                "unique_sha256": set(),
                "ext_counts": Counter(),
                "ole2_count": 0,
                "encrypted_enc4_count": 0,
            },
        )
        ext = p.suffix.lower()
        p_info["total_files"] += 1
        p_info["ext_counts"][ext] += 1

        sha = sha256_file(p)
        p_info["unique_sha256"].add(sha)
        if sha in by_sha:
            by_sha[sha]["duplicate_paths"].append(rel)
            continue

        with open(p, "rb") as fh:
            hdr8 = fh.read(8)

        rec_base = {"rel_path": rel, "project": proj, "ext": ext, "sha256": sha, "size_bytes": p.stat().st_size, "duplicate_paths": []}
        by_sha[sha] = rec_base

        if ext in (".sldprt", ".sldasm", ".slddrw"):
            if hdr8 == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
                p_info["ole2_count"] += 1
                meta = parse_solidworks_ole2(p)
                sw_item = {
                    "rel_path": rel,
                    "project": proj,
                    "ext": ext,
                    "sha256": sha,
                    "size_bytes": rec_base["size_bytes"],
                    **meta,
                    "basis": "parser_verified",
                }
                if ext == ".sldprt":
                    ole2_parts.append(sw_item)
                elif ext == ".sldasm":
                    ole2_asms.append(sw_item)
                else:
                    ole2_drws.append(sw_item)
            elif hdr8[4:8] == b"\x00\x00\x00\x04":
                p_info["encrypted_enc4_count"] += 1
        elif ext == ".xlsx" and "bom" in low_name:
            bom_tables.append(extract_bom_xlsx(p, dir1))
        elif ext == ".igs":
            im = measure_iges_part(p, dir1)
            im["project"] = proj
            iges_map[im["drawing_id"]] = im
        elif ext == ".pdf":
            pm = extract_pdf_drawing(p, dir1)
            pm["project"] = proj
            pdf_map[pm["drawing_id"]] = pm
        elif ext in (".step", ".stp"):
            st = extract_step_assembly_summary(p, dir1)
            st["project"] = proj
            step_list.append(st)
        elif ext == ".png":
            from PIL import Image
            import cv2, numpy as np

            with Image.open(p) as im_pil:
                w, h = im_pil.size
            ocr_texts: List[str] = []
            if ocr_engine is not None:
                arr = cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)
                if arr is not None:
                    res, _ = ocr_engine(arr)
                    ocr_texts = [r[1] for r in (res or []) if r and len(r) > 1]
            png_list.append({
                "rel_path": rel,
                "project": proj,
                "sha256": sha,
                "size_px": [w, h],
                "ocr_texts": ocr_texts[:80],
                "basis": "ocr_verified" if ocr_texts else "parser_verified",
            })

    # Build lookup from BOM drawing_id -> BOM attributes
    bom_by_id: Dict[str, Dict[str, Any]] = {}
    for b in bom_tables:
        for s in b["sheets"]:
            for r in s["rows"]:
                did = r.get("图号")
                if did:
                    bom_by_id[did.strip()] = {"sheet": s["sheet_name"], **r}

    # Pair IGES + PDF + BOM where drawing_id matches
    paired_bzj: List[Dict[str, Any]] = []
    all_ids = sorted(set(iges_map) | set(pdf_map))
    for did in all_ids:
        ig = iges_map.get(did)
        pf = pdf_map.get(did)
        bm = bom_by_id.get(did)
        paired_bzj.append({
            "drawing_id": did,
            "bom": bm,
            "iges": ig,
            "pdf": pf,
        })

    proj_list = []
    for k in sorted(projects):
        v = projects[k]
        proj_list.append({
            "project": v["project"],
            "total_files": v["total_files"],
            "unique_sha256_count": len(v["unique_sha256"]),
            "ext_counts": dict(v["ext_counts"]),
            "ole2_count": v["ole2_count"],
            "encrypted_enc4_count": v["encrypted_enc4_count"],
        })

    return {
        "source_dir": str(dir1),
        "ignored_lock_files": ignored_locks,
        "ignored_security_files": ignored_security,
        "unique_sha256_files": len(by_sha),
        "projects": proj_list,
        "bom_tables": bom_tables,
        "paired_iges_pdf_bom": paired_bzj,
        "step_assemblies": step_list,
        "solidworks_ole2": {
            "parts_count": len(ole2_parts),
            "assemblies_count": len(ole2_asms),
            "drawings_count": len(ole2_drws),
            "parts": ole2_parts,
            "assemblies": ole2_asms,
            "drawings": ole2_drws,
        },
        "equipment_pngs": png_list,
    }


# ---------------------------------------------------------------------------
# Dir 2 extractor: NX 12 .prt fixture assemblies via ug_inspect.exe
# ---------------------------------------------------------------------------
def _parse_ug_inspect_text(txt: str) -> Dict[str, Any]:
    entities: Dict[str, int] = {}
    in_table = False
    for ln in txt.splitlines():
        if "Entity Name" in ln and "Type" in ln:
            in_table = True
            continue
        if in_table:
            if "Note:" in ln or "Part File Summary" in ln or not ln.strip():
                if entities:
                    in_table = False
                continue
            m = re.match(r"^\s*([A-Za-z0-9\.\-\s]*?)\s+(\d+)\s*$", ln)
            if m:
                ename = m.group(1).strip() or f"type_{m.group(2)}"
                entities[ename] = int(m.group(2))

    def _search(pat: str) -> Optional[str]:
        m = re.search(pat, txt, re.M)
        return m.group(1).strip() if m else None

    jt_cnt = 0
    m_jt = re.search(r"Part contains (\d+) JT bodies", txt)
    if m_jt:
        jt_cnt = int(m_jt.group(1))

    renames = re.findall(r'Part renamed from "([^"]+)"', txt)
    return {
        "release": _search(r"^Release:\s*(.+)$"),
        "last_saved_version": _search(r"^Part was last saved in:\s*(.+)$"),
        "units": _search(r"^Part units:\s*(.+)$"),
        "original_codeset": _search(r"^Part original codeset:\s*(.+)$"),
        "filed_codeset": _search(r"^Part last filed in codeset:\s*(.+)$"),
        "parasolid_version": _search(r"^Parasolid Version:\s*(.+)$"),
        "jt_bodies_count": jt_cnt,
        "rename_history": renames[:10],
        "entity_types": entities,
    }


def _parse_ug_inspect_rm(txt: str) -> Dict[str, Any]:
    om_name = None
    m_om = re.search(r"^OM file name:\s*(.+)$", txt, re.M)
    if m_om:
        om_name = m_om.group(1).strip()
    orig_dir = None
    m_dir = re.search(r"\(found in ([^)]+)\)", txt)
    if m_dir:
        orig_dir = m_dir.group(1).strip()
    m_time = re.search(r"^Time of saving:\s*(.+)$", txt, re.M)
    return {
        "om_file_name": om_name,
        "original_directory": orig_dir,
        "save_time": m_time.group(1).strip() if m_time else None,
    }


def extract_nx_fixtures_dir2(dir2: Path, ug_inspect_exe: Path) -> Dict[str, Any]:
    """Deduplicate NX .prt files and inspect via ug_inspect.exe + clean binary CAM tokens."""
    by_sha: Dict[str, Dict[str, Any]] = {}
    ignored_lnk = 0
    total_prt = 0

    for p in sorted(dir2.rglob("*")):
        if not p.is_file():
            continue
        if p.suffix.lower() == ".lnk":
            ignored_lnk += 1
            continue
        if p.suffix.lower() != ".prt":
            continue
        total_prt += 1
        rel = str(p.relative_to(dir2))
        sha = sha256_file(p)
        if sha in by_sha:
            by_sha[sha]["duplicate_paths"].append(rel)
            continue

        raw = p.read_bytes()
        if not ug_inspect_exe.exists():
            raise FileNotFoundError(f"ug_inspect.exe not found at {ug_inspect_exe}")
        pr1 = subprocess.run([str(ug_inspect_exe), str(p)], capture_output=True, timeout=20)
        pr2 = subprocess.run([str(ug_inspect_exe), "-rm", str(p)], capture_output=True, timeout=20)
        t1 = pr1.stdout.decode("utf-8", errors="replace")
        t2 = pr2.stdout.decode("utf-8", errors="replace")
        info = _parse_ug_inspect_text(t1)
        rm_info = _parse_ug_inspect_rm(t2)

        cam_ops = [kw for kw in CAM_OP_KEYWORDS if kw.encode("ascii") in raw]
        # Clean CJK phrases found with valid UTF-8 framing (>=3 CJK chars surrounded by ASCII delim/null)
        clean_utf8_chunks = []
        seen_cjk: set[str] = set()
        for m in re.finditer(rb"[\x00\t\n -~]([\xe4-\xe9][\x80-\xbf]{2}){3,12}[\x00\t\n -~]", raw[:2_000_000]):
            sub = m.group(0)[1:-1]
            try:
                s = sub.decode("utf-8")
                s.encode("gb2312")  # filter random binary UTF-8 collisions outside common GB2312 chars
                if all("\u4e00" <= c <= "\u9fff" for c in s) and s not in seen_cjk:
                    seen_cjk.add(s)
                    clean_utf8_chunks.append(s)
                    if len(clean_utf8_chunks) >= 12:
                        break
            except UnicodeError:
                continue

        ents = info["entity_types"]
        by_sha[sha] = {
            "rel_path": rel,
            "sha256": sha,
            "size_bytes": len(raw),
            "duplicate_paths": [],
            **info,
            **rm_info,
            "has_solid": "Solid" in ents,
            "has_drawing": "Drawing" in ents or "Drafting entities" in ents,
            "has_dimensions": "Dimensions" in ents,
            "has_cam_operations": "Machining operation" in ents or bool(cam_ops),
            "has_cam_tools": "Machining tool" in ents,
            "has_cam_setup": "Machining setup" in ents,
            "has_assembly_occurrences": "Occurrence" in ents or "Reference set" in ents,
            "cam_operation_keywords": cam_ops,
            "clean_cjk_labels": clean_utf8_chunks,
            "basis": "parser_verified",
        }

    return {
        "source_dir": str(dir2),
        "total_prt_files": total_prt,
        "unique_prt_count": len(by_sha),
        "ignored_lnk_files": ignored_lnk,
        "fixtures": list(by_sha.values()),
    }


# ---------------------------------------------------------------------------
# Dir 3 extractor: 图纸.docx competition problems + JPG blueprints
# ---------------------------------------------------------------------------
def extract_docx_problems(docx_path: Path, dir3: Path) -> List[Dict[str, Any]]:
    from PIL import Image
    import io

    ns = {
        "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
        "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        "v": "urn:schemas-microsoft-com:vml",
    }
    with zipfile.ZipFile(docx_path) as zf:
        doc_xml = zf.read("word/document.xml")
        rels_xml = zf.read("word/_rels/document.xml.rels")
        rels_root = ET.fromstring(rels_xml)
        rid_map = {el.attrib["Id"]: el.attrib["Target"] for el in rels_root if el.attrib.get("Id")}
        root = ET.fromstring(doc_xml)

        events: List[Tuple[str, List[str]]] = []
        for p in root.findall(".//w:p", ns):
            txt = "".join(x.text or "" for x in p.findall(".//w:t", ns)).strip()
            imgs: List[str] = []
            for blip in p.findall(".//a:blip", ns):
                rid = blip.attrib.get(f"{{{ns['r']}}}embed")
                if rid and rid in rid_map:
                    imgs.append(rid_map[rid])
            for im in p.findall(".//v:imagedata", ns):
                rid = im.attrib.get(f"{{{ns['r']}}}id")
                if rid and rid in rid_map:
                    imgs.append(rid_map[rid])
            if txt or imgs:
                events.append((txt, imgs))

        # Group sequentially into sessions & problems
        problems: List[Dict[str, Any]] = []
        cur_session = "未知届"
        cur_id: Optional[str] = None
        cur_texts: List[str] = []
        cur_imgs: List[str] = []

        def _flush():
            if not cur_id and not cur_texts:
                return
            joined = " ".join(cur_texts)
            # Parse explicit A=110, B=30 ... (only '=' bindings, record raw_param_text separately for typos like A-72)
            params: Dict[str, float] = {}
            for m_kv in re.finditer(r"([A-Z])\s*=\s*([-+]?\d+(?:\.\d+)?)", joined):
                params[m_kv.group(1)] = float(m_kv.group(2))
            img_meta = []
            for rel_im in cur_imgs:
                z_entry = f"word/{rel_im.lstrip('/')}"
                if z_entry in zf.namelist():
                    ib = zf.read(z_entry)
                    with Image.open(io.BytesIO(ib)) as pil_im:
                        iw, ih = pil_im.size
                    img_meta.append({
                        "archive_member": z_entry,
                        "sha256": sha256_bytes(ib),
                        "size_px": [iw, ih],
                    })
            problems.append({
                "session": cur_session,
                "problem_id": cur_id or f"DOCX_ITEM_{len(problems)+1}",
                "raw_text": joined,
                "parsed_params": params,
                "images": img_meta,
                "source_file": str(docx_path.relative_to(dir3)),
                "basis": "parser_verified",
            })

        id_re = re.compile(r"(?:^|[^A-Za-z0-9_])(\d*D\d{2}[_-][A-Za-z0-9_-]+)")
        sess_re = re.compile(r"(第[一二三四五六七八九十百0-9]+届.*)")
        for txt, imgs in events:
            ms = sess_re.match(txt)
            if ms and "参数" not in txt and not id_re.search(txt):
                _flush()
                cur_id = None
                cur_texts = []
                cur_imgs = []
                cur_session = ms.group(1).strip()
                continue
            mid = id_re.search(txt)
            if mid:
                _flush()
                cur_id = mid.group(1)
                cur_texts = [txt]
                cur_imgs = list(imgs)
            else:
                if txt:
                    cur_texts.append(txt)
                cur_imgs.extend(imgs)
        _flush()
    return [pr for pr in problems if pr["parsed_params"] or pr["images"]]


def _ocr_worker(path_str: str) -> Tuple[str, List[str]]:
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    import cv2
    import numpy as np
    from rapidocr_onnxruntime import RapidOCR

    global _PROC_OCR
    if "_PROC_OCR" not in globals() or _PROC_OCR is None:
        _PROC_OCR = RapidOCR()
    im = cv2.imdecode(np.fromfile(path_str, dtype=np.uint8), cv2.IMREAD_COLOR)
    if im is None:
        return path_str, []
    h, w = im.shape[:2]
    sc = min(1.0, 960.0 / max(h, w))
    if sc < 1.0:
        im = cv2.resize(im, (int(w * sc), int(h * sc)))
    res, _ = _PROC_OCR(im)
    texts = [str(r[1]).strip() for r in (res or []) if r and len(r) > 1 and str(r[1]).strip()]
    return path_str, texts


_PROC_OCR = None


def extract_modeling_exercises_dir3(
    dir3: Path,
    ocr_cache_path: Path,
    max_ocr: int = 160,
    workers: int = 4,
    skip_ocr: bool = False,
) -> Dict[str, Any]:
    from PIL import Image, UnidentifiedImageError

    docx_files = sorted(dir3.rglob("*.docx"))
    docx_problems: List[Dict[str, Any]] = []
    for df in docx_files:
        docx_problems.extend(extract_docx_problems(df, dir3))

    by_sha: Dict[str, Dict[str, Any]] = {}
    for p in sorted(dir3.rglob("*.jpg")):
        rel = str(p.relative_to(dir3))
        sha = sha256_file(p)
        if sha in by_sha:
            by_sha[sha]["duplicate_paths"].append(rel)
            continue
        w: Optional[int] = None
        h: Optional[int] = None
        image_readable = True
        actual_container = "image"
        try:
            with Image.open(p) as im:
                w, h = im.size
        except (UnidentifiedImageError, OSError):
            image_readable = False
            with open(p, "rb") as fh:
                hdr = fh.read(8)
            actual_container = "ole2_masquerading_as_jpg" if hdr == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" else f"unreadable:{hdr[:4].hex()}"
        m_idx = re.search(r"\((\d+)\)", p.stem)
        by_sha[sha] = {
            "rel_path": rel,
            "full_path": str(p),
            "sha256": sha,
            "file_index": int(m_idx.group(1)) if m_idx else None,
            "width_px": w,
            "height_px": h,
            "image_readable": image_readable,
            "actual_container": actual_container,
            "size_bytes": p.stat().st_size,
            "duplicate_paths": [],
        }

    unique_jpgs = sorted(
        by_sha.values(),
        key=lambda x: (x["file_index"] is None, x["file_index"] or 0, x["rel_path"]),
    )
    readable_jpgs = [x for x in unique_jpgs if x["image_readable"]]

    # Load incremental OCR cache keyed by sha256
    ocr_cache: Dict[str, List[str]] = {}
    if ocr_cache_path.exists():
        try:
            ocr_cache = json.loads(ocr_cache_path.read_text(encoding="utf-8"))
        except Exception:
            ocr_cache = {}

    # Deterministic stratified selection over readable images only
    if skip_ocr:
        targets = []
    elif max_ocr <= 0 or max_ocr >= len(readable_jpgs):
        targets = readable_jpgs
    else:
        step = len(readable_jpgs) / float(max_ocr)
        targets = [readable_jpgs[int(i * step)] for i in range(max_ocr)]

    pending = [x for x in targets if x["sha256"] not in ocr_cache]
    if pending:
        print(f"[OCR] Running RapidOCR on {len(pending)}/{len(targets)} stratified JPGs (workers={workers})...", flush=True)
        path_to_sha = {x["full_path"]: x["sha256"] for x in pending}
        with ProcessPoolExecutor(max_workers=max(1, workers)) as ex:
            futs = [ex.submit(_ocr_worker, fp) for fp in path_to_sha]
            done = 0
            for fut in as_completed(futs):
                fp, texts = fut.result()
                ocr_cache[path_to_sha[fp]] = texts
                done += 1
                if done % 40 == 0:
                    ocr_cache_path.parent.mkdir(parents=True, exist_ok=True)
                    ocr_cache_path.write_text(json.dumps(ocr_cache, ensure_ascii=False), encoding="utf-8")
                    print(f"[OCR] progress {done}/{len(pending)}", flush=True)
        ocr_cache_path.parent.mkdir(parents=True, exist_ok=True)
        ocr_cache_path.write_text(json.dumps(ocr_cache, ensure_ascii=False), encoding="utf-8")

    # Strip internal full_path before writing facts, attach cached OCR results
    clean_jpgs: List[Dict[str, Any]] = []
    ocr_nonempty = 0
    for item in unique_jpgs:
        out = {k: v for k, v in item.items() if k != "full_path"}
        if item["sha256"] in ocr_cache:
            toks = ocr_cache[item["sha256"]]
            dims = []
            for t in toks:
                for m_d in re.finditer(r"(?:SR|R|M|Ø|Φ|0)?\s*\d+(?:\.\d+)?(?:\s*[xX×]\s*\d+)?", t):
                    s_tok = m_d.group(0).strip()
                    if s_tok:
                        dims.append(s_tok)
            out["ocr_texts"] = toks[:40]
            out["ocr_dimension_tokens"] = dims[:25]
            out["basis"] = "ocr_verified"
            if toks:
                ocr_nonempty += 1
        else:
            out["basis"] = "parser_verified"
        clean_jpgs.append(out)

    return {
        "source_dir": str(dir3),
        "docx_files": [str(f.relative_to(dir3)) for f in docx_files],
        "docx_problems_count": len(docx_problems),
        "docx_problems": docx_problems,
        "unique_jpg_count": len(clean_jpgs),
        "ocr_inspected_count": sum(1 for x in clean_jpgs if "ocr_texts" in x),
        "ocr_nonempty_count": ocr_nonempty,
        "jpg_exercises": clean_jpgs,
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Extract verified facts from the 3 industrial CAD/CAM directories")
    ap.add_argument("--dir1", default=str(DEFAULT_DIR1))
    ap.add_argument("--dir2", default=str(DEFAULT_DIR2))
    ap.add_argument("--dir3", default=str(DEFAULT_DIR3))
    ap.add_argument("--ug-inspect", default=str(DEFAULT_UG_INSPECT))
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    ap.add_argument("--max-ocr", type=int, default=160, help="Stratified OCR count on Dir3 JPGs (0 = all)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--skip-ocr", action="store_true")
    args = ap.parse_args(argv)

    t0 = time.time()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("[1/3] Extracting Dir 1 (Automation equipment OLE2/BOM/IGES/PDF/STEP)...", flush=True)
    d1 = extract_automation_dir1(Path(args.dir1), use_ocr_for_png=not args.skip_ocr)
    print(f"      Done in {time.time()-t0:.1f}s: {d1['unique_sha256_files']} unique files, "
          f"OLE2={d1['solidworks_ole2']['parts_count']}p/{d1['solidworks_ole2']['assemblies_count']}a/{d1['solidworks_ole2']['drawings_count']}d, "
          f"IGES/PDF pairs={len(d1['paired_iges_pdf_bom'])}", flush=True)

    t1 = time.time()
    print("[2/3] Extracting Dir 2 (UG/NX 12 fixture .prt via ug_inspect)...", flush=True)
    d2 = extract_nx_fixtures_dir2(Path(args.dir2), Path(args.ug_inspect))
    print(f"      Done in {time.time()-t1:.1f}s: {d2['unique_prt_count']} unique NX .prt fixtures", flush=True)

    t2 = time.time()
    print("[3/3] Extracting Dir 3 (图纸.docx + 3D建模练习图1500例)...", flush=True)
    d3 = extract_modeling_exercises_dir3(
        Path(args.dir3),
        ocr_cache_path=out_dir / "ocr_cache.json",
        max_ocr=args.max_ocr,
        workers=args.workers,
        skip_ocr=args.skip_ocr,
    )
    print(f"      Done in {time.time()-t2:.1f}s: docx_problems={d3['docx_problems_count']}, "
          f"unique_jpg={d3['unique_jpg_count']}, ocr_inspected={d3['ocr_inspected_count']}", flush=True)

    facts = {
        "schema_version": "six_software_real_assets.v1",
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "extraction_elapsed_s": round(time.time() - t0, 2),
        "automation_equipment": d1,
        "nx_fixtures": d2,
        "modeling_exercises": d3,
    }
    out_json = out_dir / "extracted_facts.json"
    out_json.write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")
    out_sha = sha256_file(out_json)
    (out_dir / "extracted_facts.json.sha256").write_text(f"{out_sha}  extracted_facts.json\n", encoding="utf-8")
    print(f"[DONE] Wrote {out_json} ({out_json.stat().st_size:,} B, sha256={out_sha[:16]}...)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
