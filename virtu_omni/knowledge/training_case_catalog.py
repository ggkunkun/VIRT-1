# -*- coding: utf-8 -*-
"""VERICUT 官方培训库（``E:/training``）的**案例级**实测索引。

回答三类问题，全部基于文件实测，不靠文件名猜：

1. 哪些案例是**故意含错误/缺陷**的教学案例（要学员找出来/修好），哪些是正常基准案例。
   证据来自官方讲义 PDF 原文（页码 + 引文），例如 Session 3L「Find and Detect Errors」；
   以及机床文件里与讲义不符的坐标（如 103L 的 Z 轴位置 0 vs 讲义要求 32.25"）。
2. 每个案例**需要什么加工能力**：车床 / 三轴 / 四轴 / 五轴定位(3+2) / 五轴联动 / 车铣复合。
   优先实测 NC 程序（模态运动 + 旋转轴字 + 车削循环），再用机床 ``.mch`` 的
   ``Component Type=linear/rotary`` 交叉核对；``RotarySpin="on"`` 属于主轴自转，不算第四轴。
3. 每条结论都带 ``source_path`` / ``sha256`` / ``basis``，可回溯、可复算。

宪法约束（AGENTS.md §5 / §8）：
* 没有实测证据就写 ``unclassified`` / ``no_evidence``，不得把「看起来像」写成 ``measured``；
* 加密的 ``.xmch`` 读不出轴配置时必须标 ``encrypted_unreadable``，不得臆造轴数；
* 「正确案例」只表示**官方讲义把它当正常工作流程使用、且未发现故意缺陷证据**，
  本次没有重跑 VERICUT 仿真，不得据此宣称「已仿真验证无错误」。

用法::

    from virtu_omni.knowledge.training_case_catalog import build_catalog, query_cases
    catalog = build_catalog(Path("E:/training"))
    query_cases(catalog, capability="5axis")
"""

from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

DEFAULT_ROOT = Path("E:/training")
SCHEMA_VERSION = "1.0.0"
DEFAULT_INDEX_PATH = (
    Path(__file__).resolve().parents[2] / "knowledge_base" / "training_case_index.json"
)
DEFAULT_VERIFICATION_PATH = (
    Path(__file__).resolve().parents[2] / "knowledge_base" / "error_case_verification.json"
)

MACHINE_EXT = {".mch", ".xmch"}
NC_EXT = {".mcd", ".nc", ".eia", ".sub", ".mpf", ".spf", ".tap", ".min"}
PROJECT_EXT = {".vcproject"}
VDAF_EXT = {".vdafproject"}

LINEAR_AXES = set("XYZUVW")
ROTARY_AXES = set("ABC")
AXIS_ORDER = "XYZUVWABC"

# 轴字边界：字母前不能是字母/下划线/引号/#（排除 _GET_A1 / 'B100000' / #A1），
# 但**允许**紧跟在数字后（紧凑 G 代码 ``Y-177.8A-90.`` 必须能抽到）。
AXIS_WORD = re.compile(r"(?<![A-Za-z_'\"#])([XYZABCUVW])\s*([-+]?\d*\.?\d+)", re.I)
G_WORD = re.compile(r"G\s*(\d+(?:\.\d+)?)", re.I)
# 宏/控制流行：轴字可能只是变量名或宏参数，不参与运动学取证。
NON_MOTION_LINE = re.compile(
    r"(\$|\bIF\b|\bWHILE\b|\bAND\b|\bOR\b|B_AND|^\s*;|^\s*//)", re.I
)
MACRO_CALL = re.compile(r"\b(G65|G66|MCALL|CALL|CYCLE|CYCL|L\d{2,})\b", re.I)
# 注意：G70 在很多培训程序里是「英寸模式」（如 ``G40 G17 G90 G70``），不是车削循环；
# 单独一个 G70/G71 也可能是 Haas 螺栓孔圆弧循环。因此只认 G71/G72 的 P…Q… 组合，
# 其余 G73-G76 仅在车床/车铣系列里才当作车削证据。
TURN_CYCLE = re.compile(r"G\s*7[1-6](?![0-9])", re.I)
THREAD_CYCLE = re.compile(r"G\s*3[23](?![0-9])", re.I)
TURN_PQ = re.compile(r"G\s*7[12][^;\n]*\bP\s*\d+[^;\n]*\bQ\s*\d+", re.I)
OPENED_FILE = re.compile(r"opened file ([A-Za-z0-9_.\-]+\.(?:vcproject|vdafproject))", re.I)
SESSION_ID = re.compile(r"Session\s+([0-9]+[A-Za-z]*)", re.I)
FILE_REF = re.compile(r"\.(mch|xmch|mcd|nc|eia|sub|mpf|spf|tap|min|ctl|tls)$", re.I)

# 讲义里的「故意缺陷」证据。每条都必须能把「学员要发现/修正什么」说清楚。
# 第三项是可选的**适用范围**正则（针对讲义标题），避免把通用提示误判成缺陷案例。
DEFECT_PATTERNS: Tuple[Tuple[str, re.Pattern, Optional[re.Pattern]], ...] = (
    ("session_title", re.compile(r"find and detect errors", re.I), None),
    ("session_title", re.compile(r"basic debugging tools", re.I), None),
    ("pdf_quote", re.compile(r"will stop at the first error", re.I), None),
    ("pdf_quote", re.compile(r"Notice the collisions?, this tool is to[o]? short", re.I), None),
    ("pdf_quote", re.compile(r"stopped at line #?\d+ due to a collision", re.I), None),
    ("pdf_quote", re.compile(r"stopped at error on line #?\d+", re.I), None),
    ("pdf_quote", re.compile(r"another collision between", re.I), None),
    # AUTO-DIFF 报出偏差只有在 AUTODIFF 课程里才是「故意缺陷」；
    # Additive 课程也会报偏差，那是增材工艺固有偏差，不是错误案例。
    ("pdf_quote", re.compile(r"some errors have been detected", re.I), re.compile(r"autodiff", re.I)),
    ("pdf_quote", re.compile(r"component and model are not located correctly", re.I), None),
    ("pdf_quote", re.compile(r"Optimization values which are incorrect", re.I), None),
)

# 资产名/用途已明确是碰撞检测演示的独立样例。
DEFECT_ASSET_HINTS = ("detect_collision",)

CAPABILITY_LABELS = {
    "turning": "车床（车削，X/Z 为主）",
    "milling_3axis": "普通三轴联动铣削",
    "milling_4axis": "四轴（单旋转轴）",
    "milling_5axis_positioning": "五轴定位（3+2，需五轴机床但非联动）",
    "milling_5axis_simultaneous": "五轴联动（同一进给块内 ≥2 旋转轴）",
    "mill_turn": "车铣复合",
    "robotics_vdaf": "机器人/VDAF（非 CNC 主轴切削）",
    "models_only": "仅模型/工装操作，无 NC 切削",
    "unclassified": "证据不足，未判定",
}

CAPABILITY_GROUPS = {
    "turning": {"turning"},
    "3axis": {"milling_3axis"},
    "4axis": {"milling_4axis"},
    "5axis": {"milling_5axis_positioning", "milling_5axis_simultaneous"},
    "5axis_positioning": {"milling_5axis_positioning"},
    "5axis_simultaneous": {"milling_5axis_simultaneous"},
    "mill_turn": {"mill_turn"},
    "robotics": {"robotics_vdaf"},
}

ERROR_TYPE_LABELS = {
    "nc_error_collision": "NC 程序错误/碰撞",
    "nc_config_error": "NC 偏置/配置错误",
    "tool_setup_error": "刀具长度/装夹错误",
    "setup_defect": "机床模型偏置故意放错",
    "data_defect": "刀库优化数据错误",
    "vdaf_error_collision": "VDAF 碰撞/工艺错误",
    "collision_demo": "碰撞检测演示",
    "other_error": "其他错误案例",
}

REPRODUCTION_STATUS = {
    True: "reproduced",
    "attested": "attested",
    "partial": "partial",
    "inferred_only": "inferred",
    False: "not_reproduced",
    None: "unmeasured",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _clip(text: str, limit: int = 260) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[:limit] + "…"


def _axis_sort(axes: Iterable[str]) -> List[str]:
    return sorted(set(axes), key=lambda a: AXIS_ORDER.index(a) if a in AXIS_ORDER else 99)


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


# --------------------------------------------------------------------------- machine
def _kind_from_name(name: str) -> str:
    low = name.lower()
    if "kuka" in low or "robot" in low or "vdaf" in low:
        return "robot"
    if "millturn" in low or "integrex" in low or "multus" in low:
        return "mill_turn"
    if "lathe" in low or "turn" in low:
        return "lathe"
    return "unknown"


def _machine_kind(name: str, spindles: Sequence[str], turret: bool, rotary: Sequence[str]) -> str:
    low = name.lower()
    if "kuka" in low or "robot" in low or "vdaf" in low:
        return "robot"
    spindle_names = [s.lower() for s in spindles]
    has_tool_spindle = any("tool" in s for s in spindle_names)
    has_part_spindle = any(("part" in s) or ("sub" in s) for s in spindle_names)
    if has_tool_spindle and has_part_spindle:
        return "mill_turn"
    if turret and spindle_names and not has_tool_spindle:
        return "lathe"
    if spindle_names:
        return "mill"
    return "unknown"


def parse_machine(path: Path, root: Optional[Path] = None) -> Dict[str, Any]:
    """实测机床轴配置。加密/损坏文件如实标注，不猜轴数。"""
    path = Path(path)
    info: Dict[str, Any] = {
        "file": path.name,
        "path": _rel(path, root or path.parent),
        "sha256": sha256_file(path),
        "parse": "xml",
        "kind": "unknown",
        "linear_axes": [],
        "rotary_axes": [],
        "spindle_components": [],
        "turret": False,
        "notes": [],
    }
    try:
        head = path.open("rb").read(64)
    except OSError as exc:
        info.update(parse="unreadable", notes=[f"{type(exc).__name__}: {exc}"])
        return info
    if head.startswith(b"CGTech encrypted") or head[:6] == b"CGT91A":
        info.update(parse="encrypted_unreadable", kind=_kind_from_name(path.name))
        info["notes"].append("CGTech 加密文件：无法读出 Component 轴配置，kind 由文件名推断")
        return info
    try:
        node = ET.parse(path).getroot()
    except ET.ParseError as exc:
        info.update(parse=f"xml_error: {exc}", kind=_kind_from_name(path.name))
        info["notes"].append("XML 解析失败，轴配置未知")
        return info

    linear: List[str] = []
    rotary: List[str] = []
    spindles: List[str] = []
    turret = False
    for comp in node.iter("Component"):
        name = (comp.attrib.get("Name") or "").strip()
        typ = (comp.attrib.get("Type") or "").strip().lower()
        spin = (comp.attrib.get("RotarySpin") or "").strip().lower()
        up = name.upper()
        if typ == "spindle":
            spindles.append(name)
        if typ == "turret" or "turret" in name.lower():
            turret = True
        if typ not in {"linear", "rotary"} or up not in (LINEAR_AXES | ROTARY_AXES):
            continue
        if typ == "linear" and up in LINEAR_AXES:
            linear.append(up)
        elif typ == "rotary" and up in ROTARY_AXES and spin != "on":
            # RotarySpin="on" 是主轴自转（如 basic_3axes_vmill 的 C），不是第四轴。
            rotary.append(up)

    info.update(
        linear_axes=_axis_sort(linear),
        rotary_axes=_axis_sort(rotary),
        spindle_components=spindles,
        turret=turret,
        kind=_machine_kind(path.name, spindles, turret, rotary),
    )
    if not linear and not rotary:
        info["notes"].append("未检出线性/旋转轴组件（可能是空机床模板或仅含模型件）")
    return info


# --------------------------------------------------------------------------- NC
def profile_program(path: Path, root: Optional[Path] = None) -> Dict[str, Any]:
    """实测 NC 程序：模态运动 + 旋转轴字 + 车削循环。"""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {"file": path.name, "path": _rel(path, root or path.parent),
                "error": f"{type(exc).__name__}: {exc}"}
    modal: Optional[int] = None
    linear_blocks = rotary_feed_blocks = rotary_index_blocks = rotary_only_blocks = 0
    feed_axes: set = set()
    index_axes: set = set()
    all_axes: set = set()
    max_rot_in_feed = 0
    for raw in text.splitlines():
        line = re.sub(r"\([^)]*\)", " ", raw).strip()
        if not line or line.startswith("%") or NON_MOTION_LINE.search(line) \
                or MACRO_CALL.search(line):
            continue
        for g in G_WORD.findall(line):
            try:
                value = float(g)
            except ValueError:
                continue
            if value in (0.0, 1.0, 2.0, 3.0):
                modal = int(value)
        axes = {m.group(1).upper() for m in AXIS_WORD.finditer(line)}
        rot = axes & ROTARY_AXES
        lin = axes & LINEAR_AXES
        if rot:
            all_axes |= rot
            if modal in (1, 2, 3) and lin:
                rotary_feed_blocks += 1
                feed_axes |= rot
                max_rot_in_feed = max(max_rot_in_feed, len(rot))
            elif lin:
                rotary_index_blocks += 1
                index_axes |= rot
            else:
                rotary_only_blocks += 1
                index_axes |= rot
        elif lin:
            linear_blocks += 1

    cycles = sorted({re.sub(r"\s+", "", m).upper() for m in TURN_CYCLE.findall(text)})
    return {
        "file": path.name,
        "path": _rel(path, root or path.parent),
        "sha256": sha256_file(path),
        "line_count": len(text.splitlines()),
        "turning_cycles": cycles,
        "turning_pq": bool(TURN_PQ.search(text)),
        "threading": bool(THREAD_CYCLE.search(text)),
        "linear_blocks": linear_blocks,
        "rotary_feed_blocks": rotary_feed_blocks,
        "rotary_index_blocks": rotary_index_blocks,
        "rotary_only_blocks": rotary_only_blocks,
        "feed_rotary_axes": _axis_sort(feed_axes),
        "index_rotary_axes": _axis_sort(index_axes),
        "rotary_axes": _axis_sort(all_axes),
        "max_rotary_axes_in_feed_block": max_rot_in_feed,
    }


def _capability_of(
    machine: Optional[Dict[str, Any]],
    programs: Sequence[Dict[str, Any]],
    family: str,
) -> Tuple[str, str]:
    kind = (machine or {}).get("kind", "unknown")
    machine_rotary = set((machine or {}).get("rotary_axes") or [])
    usable = [p for p in programs if not p.get("error")]
    prog_rotary: set = set()
    feed_rotary: set = set()
    max_feed = 0
    turning = False
    for prog in usable:
        prog_rotary |= set(prog.get("rotary_axes") or [])
        feed_rotary |= set(prog.get("feed_rotary_axes") or [])
        max_feed = max(max_feed, int(prog.get("max_rotary_axes_in_feed_block") or 0))
        # G71/G72 必须带 P…Q… 才算车削粗车循环；单个 G70/G71 可能是英寸模式或铣削孔循环。
        turning = turning or bool(prog.get("turning_pq"))
        if family in {"lathe", "mill_turn"}:
            turning = turning or bool(prog.get("turning_cycles") or prog.get("threading"))

    if family == "vdaf" or kind == "robot":
        return "robotics_vdaf", "asset_class_measured"
    if kind == "mill_turn" or family == "mill_turn":
        return "mill_turn", "nc_program_measured" if usable else "machine_axes_measured"
    if kind == "lathe":
        if prog_rotary - {"C"}:
            return "mill_turn", "nc_program_measured"
        return "turning", "nc_program_measured" if usable else "machine_axes_measured"
    if family == "lathe" and not machine:
        # 独立车床程序（如 day2_review_program1_l.mcd）没有配套机床文件；
        # 只能按文件家族推断，明确标 inferred，不冒充实测。
        if prog_rotary - {"C"}:
            return "mill_turn", "filename_family_inferred"
        return "turning", "filename_family_inferred"
    if turning and not prog_rotary:
        return "turning", "nc_program_measured"
    if not usable:
        if len(machine_rotary) >= 2:
            return "milling_5axis_positioning", "machine_axes_measured"
        if len(machine_rotary) == 1:
            return "milling_4axis", "machine_axes_measured"
        if machine and machine.get("linear_axes"):
            return "milling_3axis", "machine_axes_measured"
        return "models_only", "no_nc_no_machine"
    if not prog_rotary:
        return "milling_3axis", "nc_program_measured"
    if len(prog_rotary) >= 2:
        if max_feed >= 2:
            return "milling_5axis_simultaneous", "nc_program_measured"
        return "milling_5axis_positioning", "nc_program_measured"
    return "milling_4axis", "nc_program_measured"


def _axis_consistency(
    machine: Optional[Dict[str, Any]],
    programs: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """NC 用到的旋转轴 vs 机床配置的旋转轴。不一致就如实报告，不悄悄改分类。"""
    nc_axes: set = set()
    for prog in programs:
        nc_axes |= set(prog.get("rotary_axes") or [])
    if not machine:
        return {"status": "unknown_no_machine", "nc_rotary_axes": _axis_sort(nc_axes),
                "machine_rotary_axes": [], "missing_in_machine": [], "unused_on_machine": []}
    if machine.get("parse") == "encrypted_unreadable":
        return {"status": "unknown_encrypted", "nc_rotary_axes": _axis_sort(nc_axes),
                "machine_rotary_axes": [], "missing_in_machine": [], "unused_on_machine": []}
    if not machine.get("linear_axes") and not machine.get("rotary_axes"):
        # 105L/105M/105MT 的 review 工程是「空机床模板」，学员要自己把轴建出来，
        # 不能当成「程序用了机床没有的轴」。
        return {"status": "machine_empty_template", "nc_rotary_axes": _axis_sort(nc_axes),
                "machine_rotary_axes": [], "missing_in_machine": [], "unused_on_machine": []}
    machine_axes = set(machine.get("rotary_axes") or [])
    missing = nc_axes - machine_axes
    unused = machine_axes - nc_axes
    if missing:
        status = "nc_uses_axes_machine_lacks"
    elif not nc_axes and machine_axes:
        status = "nc_uses_no_rotary"
    elif unused and nc_axes:
        status = "machine_has_unused_axes"
    else:
        status = "consistent"
    return {
        "status": status,
        "nc_rotary_axes": _axis_sort(nc_axes),
        "machine_rotary_axes": _axis_sort(machine_axes),
        "missing_in_machine": _axis_sort(missing),
        "unused_on_machine": _axis_sort(unused),
    }


def _family_of(case_id: str, machine: Optional[Dict[str, Any]]) -> str:
    low = case_id.lower()
    if "vdaf" in low:
        return "vdaf"
    if "millturn" in low or low.endswith("_mt") or "_mt_" in low:
        return "mill_turn"
    if low.startswith("lathe") or "_l_" in low or low.endswith("_l") or "lathe" in low:
        return "lathe"
    if low.startswith("mill"):
        return "mill"
    kind = (machine or {}).get("kind")
    return {"lathe": "lathe", "mill_turn": "mill_turn", "mill": "mill"}.get(kind, "generic")


# --------------------------------------------------------------------------- sessions
def _session_id(filename: str) -> str:
    m = SESSION_ID.search(filename)
    return m.group(1) if m else ""


def _session_title(filename: str) -> str:
    title = re.sub(r"\.pdf$", "", filename, flags=re.I)
    title = re.sub(r"^Session\s+[0-9]+[A-Za-z]*\s*[-–]\s*", "", title, flags=re.I)
    return title.strip()


def _session_hint_from_name(filename: str) -> Tuple[str, str]:
    title = _session_title(filename)
    for basis, pattern, scope in DEFECT_PATTERNS:
        if scope and not scope.search(title):
            continue
        if pattern.search(filename):
            return "error_demo", basis
    return "reference", "no_defect_evidence_in_title"


def _extract_pdf(pdf: Path) -> Tuple[List[str], List[Dict[str, Any]], bool]:
    """返回 (打开的工程, 缺陷证据, PDF 文本是否可读)。"""
    try:
        import pymupdf  # type: ignore
    except ImportError:
        try:
            import fitz as pymupdf  # type: ignore
        except ImportError:
            return [], [], False
    opened: List[str] = []
    defects: List[Dict[str, Any]] = []
    title = _session_title(pdf.name)
    try:
        doc = pymupdf.open(str(pdf))
    except Exception:  # noqa: BLE001 - 单文件失败不阻断整批
        return [], [], False
    try:
        for page in doc:
            try:
                text = " ".join(page.get_text().split())
            except Exception:  # noqa: BLE001
                continue
            for m in OPENED_FILE.finditer(text):
                if m.group(1) not in opened:
                    opened.append(m.group(1))
            for basis, pattern, scope in DEFECT_PATTERNS:
                if scope and not scope.search(title):
                    continue
                for m in pattern.finditer(text):
                    start = max(0, m.start() - 130)
                    defects.append({
                        "basis": basis,
                        "page": page.number + 1,
                        "quote": _clip(text[start:m.end() + 200]),
                    })
                    break  # 同一页同一模式只留一条
    finally:
        doc.close()
    return opened, defects, True


def scan_sessions(root: Path, *, pdf_text: bool = True) -> Tuple[List[Dict[str, Any]], bool]:
    """扫描官方讲义：会话号、标题、打开哪个工程、故意缺陷证据。"""
    root = Path(root)
    sessions: List[Dict[str, Any]] = []
    text_ok = False
    for pdf in sorted(root.rglob("*.pdf")):
        opened, defects, readable = _extract_pdf(pdf) if pdf_text else ([], [], False)
        if not pdf_text:
            status, basis = _session_hint_from_name(pdf.name)
            if status == "error_demo":
                defects = [{"basis": basis, "page": 0, "quote": _session_title(pdf.name)}]
        text_ok = text_ok or readable
        if not opened and not defects:
            # 没读到正文时退回标题判定，避免把「没读 PDF」当成「没问题」。
            status, basis = _session_hint_from_name(pdf.name)
            if status == "error_demo":
                defects = [{"basis": basis, "page": 0, "quote": _session_title(pdf.name)}]
        sessions.append({
            "session": _session_id(pdf.name),
            "title": _session_title(pdf.name),
            "pdf": _rel(pdf, root),
            "sha256": sha256_file(pdf),
            "opened_projects": opened,
            "defects": defects[:4],
            "pdf_text_read": readable,
        })
    return sessions, text_ok


# --------------------------------------------------------------------------- project refs
def project_references(path: Path) -> List[str]:
    try:
        node = ET.parse(path).getroot()
    except ET.ParseError:
        return []
    refs: List[str] = []
    for el in node.iter():
        for key, value in el.attrib.items():
            if key.lower() in {"file", "filename"} and value and FILE_REF.search(value):
                refs.append(value)
        if el.tag in {"File", "Library"} and el.text and FILE_REF.search(el.text.strip()):
            refs.append(el.text.strip())
    return list(dict.fromkeys(refs))


# --------------------------------------------------------------------------- build
def build_catalog(root: Path = DEFAULT_ROOT, *, read_pdf: bool = True) -> Dict[str, Any]:
    """只读扫描培训库，产出案例级索引。"""
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(f"training root not found: {root}")

    machines = [parse_machine(p, root) for p in sorted(root.glob("*.mch"))]
    machines += [parse_machine(p, root) for p in sorted(root.glob("*.xmch"))]
    machine_by_name = {m["file"].lower(): m for m in machines}

    program_cache: Dict[str, Dict[str, Any]] = {}

    def prog(name: str) -> Dict[str, Any]:
        key = name.lower()
        if key not in program_cache:
            path = root / name
            if path.is_file() and path.suffix.lower() in NC_EXT:
                program_cache[key] = profile_program(path, root)
            else:
                program_cache[key] = {"file": name, "missing": True}
        return program_cache[key]

    sessions, pdf_text_ok = scan_sessions(root, pdf_text=read_pdf)
    session_by_project: Dict[str, List[Dict[str, Any]]] = {}
    for sess in sessions:
        for opened in sess["opened_projects"]:
            session_by_project.setdefault(opened.lower(), []).append(sess)

    cases: List[Dict[str, Any]] = []
    referenced_programs: set = set()
    project_paths = sorted(root.glob("*.vcproject")) + sorted(root.glob("*.vdafproject"))
    for project in project_paths:
        case_id = project.stem
        case_key = project.name.lower()
        refs = project_references(project)
        machine_names = [r for r in refs if Path(r).suffix.lower() in MACHINE_EXT]
        program_names = [r for r in refs if Path(r).suffix.lower() in NC_EXT]
        referenced_programs |= {p.lower() for p in program_names}
        machine = machine_by_name.get(machine_names[0].lower()) if machine_names else None
        programs = [prog(p) for p in program_names]
        family = _family_of(case_id, machine)
        sess_list = session_by_project.get(case_key, [])
        defects: List[Dict[str, Any]] = []
        for sess in sess_list:
            for defect in sess["defects"]:
                defects.append({
                    "session": sess["session"],
                    "title": sess["title"],
                    "page": defect["page"],
                    "basis": defect["basis"],
                    "quote": defect["quote"],
                })
        if defects:
            status, status_basis = "error_demo", "pdf_quote"
        elif sess_list:
            status, status_basis = "reference", "official_session_no_defect_evidence"
        elif project.suffix.lower() in VDAF_EXT:
            status, status_basis = "unclassified", "no_session_mapping"
        else:
            status, status_basis = "reference", "asset_only_no_defect_evidence"

        capability, cap_basis = _capability_of(machine, programs, family)
        consistency = _axis_consistency(machine, programs)
        notes: List[str] = []
        if machine and machine["parse"] == "encrypted_unreadable":
            notes.append("机床为加密 .xmch，轴配置不可实测；能力判定以 NC 程序为准")
        if machine and not machine["linear_axes"] and not machine["rotary_axes"]:
            notes.append("机床文件未检出轴组件（可能为空的构建模板）")
        if not program_names:
            notes.append("工程未引用 NC 程序：能力按机床轴配置判定")
        if consistency["status"] == "nc_uses_axes_machine_lacks":
            notes.append(
                f"NC 使用旋转轴 {consistency['missing_in_machine']}，机床未配置该轴"
                "（程序/机床不一致，需复核）"
            )
        elif capability == "milling_3axis" and consistency["unused_on_machine"]:
            notes.append(
                f"机床配置有旋转轴 {consistency['unused_on_machine']}，但 NC 未使用："
                "按程序只需要三轴联动"
            )
        if project.suffix.lower() in VDAF_EXT:
            notes.append("VDAF 工程：机器人/自动钻铆单元，不按车/铣轴数分类")
        if status == "error_demo":
            notes.append("官方讲义明确要求学员发现/修正该缺陷；本索引未重跑 VERICUT")

        cases.append({
            "case_id": case_id,
            "name": project.name,
            "path": _rel(project, root),
            "sha256": sha256_file(project),
            "family": family,
            "purpose": _purpose_of(case_id),
            "status": status,
            "status_basis": status_basis,
            "defect_evidence": defects[:6],
            "sessions": [
                {"session": s["session"], "title": s["title"], "pdf": s["pdf"]}
                for s in sess_list
            ],
            "machine": {
                "file": machine["file"],
                "kind": machine["kind"],
                "parse": machine["parse"],
                "linear_axes": machine["linear_axes"],
                "rotary_axes": machine["rotary_axes"],
            } if machine else None,
            "programs": programs,
            "axis_consistency": consistency,
            "required_capability": capability,
            "capability_label": CAPABILITY_LABELS.get(capability, capability),
            "capability_basis": cap_basis,
            "notes": notes,
        })

    case_program_names = {p["file"].lower() for c in cases for p in c["programs"]}

    standalone_programs: List[Dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in NC_EXT:
            continue
        if path.suffix.lower() == ".sub":
            # 库里大量 .sub 是控制器子程序（hascnc.sub / hei530.sub 等），不是加工案例；
            # 被工程引用的 .sub 仍会作为案例的 programs 计入。
            continue
        if path.name.lower() in case_program_names:
            continue
        profile = profile_program(path, root)
        if profile.get("error"):
            continue
        low = path.stem.lower()
        if "vdaf" in low or "rotisserie" in low:
            family = "vdaf"
        elif "_mt" in low or "millturn" in low or "turn" in low \
                or "integrex" in low or "multus" in low:
            family = "mill_turn"
        elif low.endswith("_l") or low.endswith("_l1") or low.endswith("_l2") \
                or "lathe" in low or low.startswith("mazak_qtn"):
            family = "lathe"
        else:
            family = "generic"
        # 若磁盘上存在同名机床文件，就直接用它的实测轴配置（如 mazak_qtn300_650u.eia）。
        machine = next(
            (m for m in machines
             if m["file"].lower().startswith(low) or low.startswith(Path(m["file"]).stem.lower())),
            None,
        )
        capability, cap_basis = _capability_of(machine, [profile], family)
        status = "reference"
        status_basis = "sample_asset_no_defect_evidence"
        if any(h in path.stem.lower() for h in DEFECT_ASSET_HINTS):
            status, status_basis = "error_demo", "asset_purpose_inferred"
        standalone_programs.append({
            "file": path.name,
            "path": _rel(path, root),
            "sha256": profile["sha256"],
            "required_capability": capability,
            "capability_label": CAPABILITY_LABELS.get(capability, capability),
            "capability_basis": cap_basis,
            "status": status,
            "status_basis": status_basis,
            "machine": {
                "file": machine["file"],
                "kind": machine["kind"],
                "rotary_axes": machine["rotary_axes"],
            } if machine else None,
            "metrics": {k: profile[k] for k in (
                "turning_cycles", "turning_pq", "threading", "rotary_axes",
                "feed_rotary_axes", "index_rotary_axes", "rotary_feed_blocks",
                "rotary_index_blocks", "max_rotary_axes_in_feed_block", "linear_blocks")},
        })

    summary: Dict[str, Any] = {
        "cases": len(cases),
        "by_status": _count(cases, "status"),
        "by_capability": _count(cases, "required_capability"),
        "standalone_programs": len(standalone_programs),
        "machines": len(machines),
        "sessions": len(sessions),
        "error_demo_cases": [c["case_id"] for c in cases if c["status"] == "error_demo"],
        "turning_cases": [c["case_id"] for c in cases if c["required_capability"] == "turning"],
        "three_axis_cases": [c["case_id"] for c in cases if c["required_capability"] == "milling_3axis"],
        "four_axis_cases": [c["case_id"] for c in cases if c["required_capability"] == "milling_4axis"],
        "five_axis_cases": [c["case_id"] for c in cases if c["required_capability"].startswith("milling_5axis")],
        "mill_turn_cases": [c["case_id"] for c in cases if c["required_capability"] == "mill_turn"],
        "axis_conflict_cases": [
            {"case_id": c["case_id"], **c["axis_consistency"]}
            for c in cases if c["axis_consistency"]["status"] == "nc_uses_axes_machine_lacks"
        ],
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "root": str(root).replace("\\", "/"),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "method": {
            "case_unit": "每个 .vcproject / .vdafproject 计一个案例；未被工程引用的 NC 程序单列 standalone",
            "status_rule": (
                "error_demo 仅当官方讲义 PDF 原文明确给出错误/碰撞/错误数据证据，"
                "或资产名明确为碰撞检测演示；reference 表示官方按其正常工作流程使用、"
                "未发现故意缺陷证据——本次未重跑 VERICUT，不宣称已仿真验证无错误"
            ),
            "capability_rule": (
                "优先实测 NC 程序（模态 G0-G3 + 旋转轴字 + 车削循环 P/Q），"
                "再用机床 Component Type=linear/rotary 交叉核对；RotarySpin=on 不計入旋转轴"
            ),
            "pdf_text_available": pdf_text_ok,
            "verification": (
                "reference_cases_not_rerun_in_vericut; "
                "error_cases_verified_in_knowledge_base/error_case_verification.json"
            ),
        },
        "summary": summary,
        "cases": cases,
        "machines": machines,
        "sessions": sessions,
        "standalone_programs": standalone_programs,
    }


def _purpose_of(case_id: str) -> str:
    low = case_id.lower()
    if "optimization" in low:
        return "optimization"
    if "_session_10" in low or "_session_11" in low or low.startswith("session_10") \
            or low.startswith("session_11"):
        return "machine_and_control"
    if low.startswith("session_50") or "vdaf" in low:
        return "vdaf"
    if low.startswith("new_project"):
        return "template"
    m = re.search(r"session_1?([0-9]+)[lm]", low)
    if m and int(m.group(1)) <= 5 and "review" not in low:
        return "machine_building"
    return "verification_workflow"


def _count(items: Sequence[Dict[str, Any]], key: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for item in items:
        value = str(item.get(key) or "unknown")
        out[value] = out.get(value, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


# --------------------------------------------------------------------------- verification
def _error_type_of(case_id: str) -> str:
    low = case_id.lower()
    if "detect_collision" in low:
        return "collision_demo"
    if low.endswith("_day1"):
        return "nc_error_collision"
    if "debugging" in low:
        return "nc_config_error"
    if low.startswith("session_14"):
        return "tool_setup_error"
    if "_103" in low and "add_3d_models" in low:
        return "setup_defect"
    if "254" in low and "optimization" in low:
        return "data_defect"
    if low.startswith("vdaf_"):
        return "vdaf_error_collision"
    return "other_error"


def enrich_with_verification(
    catalog: Dict[str, Any],
    report_path: Path = DEFAULT_VERIFICATION_PATH,
) -> Dict[str, Any]:
    """把 ``error_case_verification.json`` 的复现结论合并进案例索引。

    只给 ``status=error_demo`` 的案例写 ``error_type`` / ``verification_status`` /
    ``reproduction``；其它案例保持原样，避免把「参考案例未重跑」混成「已验证」。
    """
    report_path = Path(report_path)
    if not report_path.is_file():
        catalog.setdefault("method", {})["verification"] = (
            "reference_cases_not_rerun_in_vericut; error_case_verification.json missing"
        )
        return catalog
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        catalog.setdefault("method", {})["verification"] = (
            f"reference_cases_not_rerun_in_vericut; verification report unreadable: {exc}"
        )
        return catalog

    by_id = {c.get("case_id"): c for c in report.get("cases", [])}

    def attach(target: Dict[str, Any], key_field: str) -> None:
        if target.get("status") != "error_demo":
            return
        case_id = target.get(key_field)
        etype = _error_type_of(str(case_id))
        target["error_type"] = etype
        target["error_type_cn"] = ERROR_TYPE_LABELS.get(etype, etype)
        item = by_id.get(case_id) or {}
        target["verification_status"] = REPRODUCTION_STATUS.get(
            item.get("reproduced"), "unmeasured")
        target["reproduction"] = {
            k: item.get(k) for k in ("method", "reproduced", "confidence", "log_path", "note")
        } if item else None

    for case in catalog.get("cases", []):
        attach(case, "case_id")
    for prog in catalog.get("standalone_programs", []):
        attach(prog, "file")

    error_cases = [c for c in catalog.get("cases", []) if c.get("status") == "error_demo"]
    error_cases += [p for p in catalog.get("standalone_programs", [])
                    if p.get("status") == "error_demo"]
    by_status: Dict[str, int] = {}
    by_type: Dict[str, int] = {}
    for item in error_cases:
        status = item.get("verification_status") or "unmeasured"
        by_status[status] = by_status.get(status, 0) + 1
        etype = item.get("error_type") or "other_error"
        by_type[etype] = by_type.get(etype, 0) + 1

    def ids(status: str) -> List[str]:
        return [i.get("case_id") or i.get("file") for i in error_cases
                if (i.get("verification_status") or "unmeasured") == status]

    repo = Path(__file__).resolve().parents[2]
    try:
        report_ref = str(report_path.resolve().relative_to(repo)).replace("\\", "/")
    except ValueError:
        report_ref = str(report_path).replace("\\", "/")

    summary = catalog.setdefault("summary", {})
    summary["error_case_verification"] = {
        "report": report_ref,
        "report_generated_at_utc": report.get("generated_at_utc"),
        "total": len(error_cases),
        "by_verification_status": dict(sorted(by_status.items(), key=lambda kv: -kv[1])),
        "by_error_type": dict(sorted(by_type.items(), key=lambda kv: -kv[1])),
        "reproduced_cases": ids("reproduced"),
        "attested_cases": ids("attested"),
        "partial_cases": ids("partial"),
        "inferred_cases": ids("inferred"),
        "not_reproduced_cases": ids("not_reproduced"),
        "unmeasured_cases": ids("unmeasured"),
    }
    catalog["verification_report"] = report_ref
    catalog.setdefault("method", {})["verification"] = (
        f"reference_cases_not_rerun_in_vericut; error_cases: "
        f"{len(ids('reproduced'))} reproduced / "
        f"{len(ids('attested'))} attested / {len(ids('partial'))} partial / "
        f"{len(ids('inferred'))} inferred / {len(ids('not_reproduced'))} not_reproduced"
    )
    return catalog


# --------------------------------------------------------------------------- query
def _infer_filters(text: str) -> Dict[str, Any]:
    low = text.lower()
    filters: Dict[str, Any] = {}
    if re.search(r"错误|缺陷|错误案例|debug|error", low):
        filters["status"] = "error_demo"
    elif re.search(r"正确|基准|正常|reference", low):
        filters["status"] = "reference"
    if re.search(r"已复现|复现成功", low):
        filters["verification_status"] = "reproduced"
    elif re.search(r"部分复现", low):
        filters["verification_status"] = "partial"
    elif re.search(r"仅推断|只是推断", low):
        filters["verification_status"] = "inferred"
    elif re.search(r"未复现|待核验", low):
        filters["verification_status"] = "not_reproduced"
    if re.search(r"五轴联动|5轴联动|simultaneous", low):
        filters["capability"] = "5axis_simultaneous"
    elif re.search(r"五轴定位|3\+2|定位五轴|5轴定位", low):
        filters["capability"] = "5axis_positioning"
    elif re.search(r"五轴|5轴|5-axis|five-axis", low):
        filters["capability"] = "5axis"
    elif re.search(r"四轴|4轴|4-axis|第四轴", low):
        filters["capability"] = "4axis"
    elif re.search(r"三轴|3轴|3-axis|普通铣", low):
        filters["capability"] = "3axis"
    elif re.search(r"车铣|mill.?turn|车铣复合", low):
        filters["capability"] = "mill_turn"
    elif re.search(r"车床|车削|lathe|turning", low):
        filters["capability"] = "turning"
    if re.search(r"机器人|vdaf", low):
        filters["capability"] = "robotics"
    return filters


def query_cases(
    catalog: Dict[str, Any],
    *,
    status: Optional[str] = None,
    capability: Optional[str] = None,
    family: Optional[str] = None,
    keyword: Optional[str] = None,
    verification_status: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """按状态 / 加工能力 / 系列 / 关键词 / 复现结论过滤案例（仅返回满足全部条件的）。"""
    wanted_caps = CAPABILITY_GROUPS.get(capability or "", {capability} if capability else set())
    rows: List[Dict[str, Any]] = []
    for case in catalog.get("cases", []):
        if status and case.get("status") != status:
            continue
        if wanted_caps and case.get("required_capability") not in wanted_caps:
            continue
        if family and case.get("family") != family:
            continue
        if verification_status and case.get("verification_status") != verification_status:
            continue
        if keyword:
            blob = json.dumps(case, ensure_ascii=False).lower()
            if keyword.lower() not in blob:
                continue
        rows.append(case)
        if len(rows) >= max(1, int(limit)):
            break
    return rows


def query_standalone(
    catalog: Dict[str, Any],
    *,
    capability: Optional[str] = None,
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    wanted_caps = CAPABILITY_GROUPS.get(capability or "", {capability} if capability else set())
    rows: List[Dict[str, Any]] = []
    for prog in catalog.get("standalone_programs", []):
        if capability and prog.get("required_capability") not in wanted_caps:
            continue
        if status and prog.get("status") != status:
            continue
        if keyword and keyword.lower() not in json.dumps(prog, ensure_ascii=False).lower():
            continue
        rows.append(prog)
        if len(rows) >= max(1, int(limit)):
            break
    return rows


def answer_query(catalog: Dict[str, Any], text: str, *, limit: int = 30) -> Dict[str, Any]:
    """自然语言查询入口：中文关键词 -> 结构化过滤；召回不到就诚实返回空。"""
    filters = _infer_filters(text)
    keyword = None
    if not filters:
        keyword = text.strip()
    cases = query_cases(catalog, limit=limit,
                        keyword=keyword or None, **filters)
    standalone = query_standalone(catalog, capability=filters.get("capability"),
                                  status=filters.get("status"),
                                  keyword=keyword or None, limit=limit)
    return {
        "query": text,
        "filters": filters,
        "cases": cases,
        "standalone_programs": standalone,
        "case_count": len(cases),
        "standalone_count": len(standalone),
        "summary": catalog.get("summary", {}),
    }


def load_catalog(path: Path = DEFAULT_INDEX_PATH) -> Optional[Dict[str, Any]]:
    path = Path(path)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
