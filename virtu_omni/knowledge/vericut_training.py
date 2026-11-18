# -*- coding: utf-8 -*-
"""VERICUT 官方培训资产 -> 可验证的结构化知识记录。

只读解析 CGTech VERICUT 9.6 Training Sessions（默认 ``E:/training``），把工程
XML、控制器/刀具库、NC 程序、培训讲义 PDF、几何资产转换成可供
``ContinualLearningPipeline`` 摄入的知识记录。

宪法约束（AGENTS.md §8 测量宪法）：
* ``content`` 必须是**从文件里实测抽取**的内容，禁止「系统遵循 GB/ISO 国标…」
  这类模板套话；没有可抽字段的文件不产出记录。
* 每条记录带 ``source_path`` / ``source_sha256`` / ``source_type`` /
  ``evidence``（结构化实测字段）/ ``basis=measured``，可回溯、可复算。
* 纯标准库 + 可选 ``pymupdf``（缺库时 PDF 跳过并在 stats 里记原因，不伪造）。
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

DEFAULT_ROOT = Path("E:/training")

PROJECT_EXT = {".vcproject"}
XML_CONFIG_EXT = {".ctl", ".tls", ".vcfm", ".xml", ".xmch", ".vctemplate"}
NC_EXT = {".mcd", ".nc", ".eia", ".sub"}
PDF_EXT = {".pdf"}
GEOMETRY_EXT = {".stl", ".ply", ".xply", ".stp", ".igs", ".fxt", ".swp", ".str", ".sor", ".stk"}
MACHINE_EXT = {".mch"}
TEXT_CONFIG_EXT = {".def", ".vcpost", ".ini"}
SKIP_EXT = {".png", ".jpg", ".jpeg", ".log", ".bak_stepreverse"}

SESSION_DIR_CATEGORY = {
    "machine_and_control": "machine_and_control",
    "optimization": "optimization",
    "verification": "verification",
    "vdaf": "vdaf",
}

_PDF_CHUNK_PAGES = 4
_PDF_CHUNK_CHARS = 1800
_MAX_EVIDENCE_ITEMS = 24


@dataclass
class KnowledgeRecord:
    """一条实测知识。``content`` 是喂给向量库与 SFT 的正文。"""

    topic: str
    content: str
    category: str
    source_path: str
    source_sha256: str
    source_type: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    basis: str = "measured"

    def record_id(self) -> str:
        return hashlib.sha256(
            f"{self.source_sha256}|{self.topic}".encode("utf-8")
        ).hexdigest()[:20]

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["record_id"] = self.record_id()
        return d


@dataclass
class ScanStats:
    files_seen: int = 0
    by_extension: Dict[str, int] = field(default_factory=dict)
    records_by_type: Dict[str, int] = field(default_factory=dict)
    pdf_pages: int = 0
    pdf_unavailable_reason: str = ""
    geometry_bbox_samples: int = 0
    skipped: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _clip(text: str, limit: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[:limit] + "…"


def _category_of(path: Path, root: Path) -> str:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        parts = path.parts
    for part in parts:
        if part in SESSION_DIR_CATEGORY:
            return SESSION_DIR_CATEGORY[part]
    if len(parts) > 1 and parts[0] == "training_models":
        return "training_models"
    return "project_assets"


def _mk(record_type: str, topic: str, content: str, path: Path, root: Path,
        digest: str, evidence: Dict[str, Any]) -> KnowledgeRecord:
    return KnowledgeRecord(
        topic=topic,
        content=content,
        category=_category_of(path, root),
        source_path=str(path).replace("\\", "/"),
        source_sha256=digest,
        source_type=record_type,
        evidence=evidence,
        basis="measured",
    )


# --------------------------------------------------------------------------- XML
def _attr_files(root: ET.Element) -> List[str]:
    out: List[str] = []
    for node in root.iter():
        for key, value in node.attrib.items():
            if key.lower() in {"file", "filename", "name", "controlfile", "machinefile"} \
                    and value and re.search(r"\.[A-Za-z0-9]{2,6}$", value):
                out.append(value)
        if node.tag == "File" and node.text and re.search(r"\.[A-Za-z0-9]{2,6}$", node.text.strip()):
            out.append(node.text.strip())
    # 去重保序
    return list(dict.fromkeys(out))[:_MAX_EVIDENCE_ITEMS]


def parse_project(path: Path, root: Path, digest: str) -> List[KnowledgeRecord]:
    """抽 VcProject 的真实配置：版本/单位、关联的机床/控制器/NC/模型、Auto-Diff 门限。"""
    try:
        node = ET.parse(path).getroot()
    except ET.ParseError as exc:
        return []
    unit = node.attrib.get("Unit", "")
    version = node.attrib.get("Version", "")
    files = _attr_files(node)

    autodiff = node.find("AutoDiff")
    ad: Dict[str, Any] = {}
    if autodiff is not None:
        ad["attributes"] = dict(autodiff.attrib)
        solid = autodiff.find("Solid")
        if solid is not None:
            ad["solid_gouge_tol"] = (solid.find("Gouge").attrib if solid.find("Gouge") is not None else {})
            ad["solid_excess_tol"] = (solid.find("Excess").attrib if solid.find("Excess") is not None else {})
        surface = autodiff.find("Surface")
        if surface is not None:
            ad["surface_gouge_levels"] = [g.attrib.get("Value") for g in surface.findall("Gouge")]
            ad["surface_excess_levels"] = [g.attrib.get("Value") for g in surface.findall("Excess")]

    cuts = [c.attrib for c in node.iter("Cut")][:_MAX_EVIDENCE_ITEMS]
    feeds = [f.attrib for f in node.iter("Feed")][:_MAX_EVIDENCE_ITEMS]
    components = [c.attrib for c in node.iter("Component")][:_MAX_EVIDENCE_ITEMS]

    lines = [
        f"VERICUT 工程 {path.name}（版本 {version}，单位 {unit}）的实测配置。",
        f"关联文件：{', '.join(files) if files else '（无）'}。",
    ]
    if ad:
        lines.append(
            "Auto-Diff 配置：" + json.dumps(
                {k: v for k, v in ad.items() if k != "attributes"},
                ensure_ascii=False)[:600]
        )
        lines.append("Auto-Diff 属性：" + json.dumps(ad["attributes"], ensure_ascii=False)[:400])
    if cuts:
        lines.append("切削参数节点（Cut）：" + json.dumps(cuts[:6], ensure_ascii=False)[:600])
    if feeds:
        lines.append("进给节点（Feed）：" + json.dumps(feeds[:6], ensure_ascii=False)[:400])
    if components:
        lines.append("组件节点（Component）：" + json.dumps(components[:6], ensure_ascii=False)[:400])

    evidence = {
        "vericut_version": version,
        "unit": unit,
        "referenced_files": files,
        "autodiff": ad,
        "cut_nodes": len(list(node.iter("Cut"))),
        "feed_nodes": len(list(node.iter("Feed"))),
        "component_nodes": len(list(node.iter("Component"))),
        "gouge_nodes": len(list(node.iter("Gouge"))),
        "excess_nodes": len(list(node.iter("Excess"))),
    }
    return [_mk("vericut_project", f"VERICUT 工程配置 {path.name}",
                "\n".join(lines), path, root, digest, evidence)]


def parse_xml_config(path: Path, root: Path, digest: str) -> List[KnowledgeRecord]:
    """抽 .ctl / .tls / .vcfm 等 XML 的真实字段。"""
    try:
        node = ET.parse(path).getroot()
    except ET.ParseError:
        return []
    tag = node.tag
    attrs = dict(node.attrib)
    tools = []
    for t in node.iter("Tool"):
        desc = t.findtext("Description") or ""
        tools.append({
            "id": t.attrib.get("ID"),
            "units": t.attrib.get("Units"),
            "description": _clip(desc, 80),
            "type": t.findtext("Type") or "",
        })
        if len(tools) >= _MAX_EVIDENCE_ITEMS:
            break
    gage = [g.attrib for g in node.iter("GagePoint")][:6]
    comments = [_clip(c.text or "", 200) for c in node.iter("COMMENT") if (c.text or "").strip()][:4]
    coeffs = [c.attrib for c in node.iter("Coefficients")][:4]

    lines = [f"VERICUT 配置文件 {path.name}：根元素 <{tag}>，属性 {json.dumps(attrs, ensure_ascii=False)}。"]
    if comments:
        lines.append("文件注释（版本/修订来源）：" + " | ".join(comments))
    if tools:
        lines.append(f"刀具库共检出 {len(tools)} 把（示例）：" +
                     json.dumps(tools[:8], ensure_ascii=False)[:800])
    if gage:
        lines.append("刀尖测量点 GagePoint：" + json.dumps(gage, ensure_ascii=False)[:300])
    if coeffs:
        lines.append("Force 材料系数条目：" + json.dumps(
            [{k: v for k, v in c.items() if k != "Encoding"} for c in coeffs],
            ensure_ascii=False)[:500])

    evidence = {
        "root_tag": tag,
        "root_attributes": attrs,
        "tool_count": len(list(node.iter("Tool"))),
        "tool_samples": tools,
        "gage_points": gage,
        "comments": comments,
        "force_material_entries": len(coeffs),
    }
    kind = "tool_library" if tools else "vericut_xml_config"
    return [_mk(kind, f"VERICUT {tag} 配置 {path.name}",
                "\n".join(lines), path, root, digest, evidence)]


# --------------------------------------------------------------------------- NC
# NC 里 G/M 常连写（如 ``G90G0X5.`` / ``S1400M3``），不能用 \b 词边界，
# 否则紧跟在前一个字母/数字后的代码会被整段漏掉。
_GCODE_RE = re.compile(r"([GMTFS])\s*(\d+(?:\.\d+)?)", re.I)


def parse_nc_program(path: Path, root: Path, digest: str) -> List[KnowledgeRecord]:
    """抽真实 G/M/T/S/F 代码与坐标，不臆造工艺解释。"""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    codes: Dict[str, List[str]] = {}
    for ln in lines:
        if ln.startswith("%"):
            continue
        # 括号注释里也会出现 G43-G28 这类说明文字，不算执行代码。
        code_line = re.sub(r"\([^)]*\)", " ", ln)
        for letter, value in _GCODE_RE.findall(code_line):
            codes.setdefault(letter.upper(), []).append(value)
    counts = {k: len(v) for k, v in codes.items()}
    uniq_g = sorted(set(codes.get("G", [])), key=lambda x: float(x) if x.replace(".", "", 1).isdigit() else 0)
    uniq_m = sorted(set(codes.get("M", [])), key=lambda x: float(x) if x.replace(".", "", 1).isdigit() else 0)
    comments = [ln for ln in lines if ln.startswith("(")][:8]
    first_moves = [ln for ln in lines if not ln.startswith("(") and not ln.startswith("%")][:12]

    if not codes and not comments:
        return []
    body = [
        f"NC 程序 {path.name} 实测共 {len(lines)} 行，代码计数 {json.dumps(counts, ensure_ascii=False)}。",
        f"出现的 G 代码：{', '.join('G' + g for g in uniq_g[:30]) or '（无）'}。",
        f"出现的 M 代码：{', '.join('M' + m for m in uniq_m[:20]) or '（无）'}。",
        "程序注释：" + (" | ".join(comments) if comments else "（无）"),
        "开头运动行：" + " ; ".join(first_moves),
    ]
    evidence = {
        "line_count": len(lines),
        "code_counts": counts,
        "unique_g": uniq_g[:40],
        "unique_m": uniq_m[:30],
        "tool_numbers": sorted(set(codes.get("T", [])))[:20],
        "spindle_speeds": sorted(set(codes.get("S", [])))[:20],
        "feeds": sorted(set(codes.get("F", [])))[:20],
        "comments": comments,
        "first_moves": first_moves,
    }
    return [_mk("nc_program", f"NC 程序 {path.name}", "\n".join(body),
                path, root, digest, evidence)]


# --------------------------------------------------------------------------- PDF
def _pdf_chunks(path: Path, pages_per_chunk: int) -> Tuple[List[Tuple[int, int, str]], int]:
    try:
        import pymupdf  # type: ignore
    except ImportError:
        try:
            import fitz as pymupdf  # type: ignore
        except ImportError:
            return [], -1
    doc = pymupdf.open(str(path))
    try:
        total = len(doc)
        chunks: List[Tuple[int, int, str]] = []
        for start in range(0, total, pages_per_chunk):
            end = min(total, start + pages_per_chunk)
            parts = []
            for i in range(start, end):
                try:
                    parts.append(doc[i].get_text())
                except Exception:
                    continue
            text = _clip("\n".join(parts), _PDF_CHUNK_CHARS)
            if text.strip():
                chunks.append((start + 1, end, text))
        return chunks, total
    finally:
        doc.close()


def parse_pdf(path: Path, root: Path, digest: str,
              pages_per_chunk: int = _PDF_CHUNK_PAGES) -> Tuple[List[KnowledgeRecord], int, bool]:
    chunks, total = _pdf_chunks(path, pages_per_chunk)
    if total == -1:
        return [], 0, False
    session = re.search(r"Session\s+([0-9]+[A-Za-z]*)", path.name)
    session_id = session.group(1) if session else ""
    title = re.sub(r"\.pdf$", "", path.name, flags=re.I)
    records: List[KnowledgeRecord] = []
    for start, end, text in chunks:
        topic = f"VERICUT 官方培训 {title} p{start}-{end}"
        content = (
            f"【VERICUT 9.6 官方培训讲义】{title}（第 {start}-{end} 页 / 共 {total} 页）。\n"
            f"课程类别：{_category_of(path, root)}。"
            f"{('课程编号 Session ' + session_id + '。') if session_id else ''}\n"
            f"讲义原文摘录：\n{text}"
        )
        evidence = {
            "session": session_id,
            "title": title,
            "page_start": start,
            "page_end": end,
            "total_pages": total,
            "chars": len(text),
        }
        records.append(_mk("official_session_pdf", topic, content, path, root, digest, evidence))
    return records, total, True


# --------------------------------------------------------------------------- geometry
def stl_bbox(path: Path) -> Optional[Dict[str, Any]]:
    """纯标准库解析二进制/ASCII STL 包围盒与三角面数。"""
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if len(raw) < 84:
        return None
    is_ascii = raw[:5].lower() == b"solid" and b"facet normal" in raw[:2048]
    coords: List[Tuple[float, float, float]] = []
    tris = 0
    if is_ascii:
        for m in re.finditer(rb"vertex\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)", raw):
            coords.append((float(m.group(1)), float(m.group(2)), float(m.group(3))))
        tris = len(coords) // 3
    else:
        try:
            tris = struct.unpack_from("<I", raw, 80)[0]
        except struct.error:
            return None
        if tris > 5_000_000 or 84 + tris * 50 > len(raw) + 50:
            return None
        for i in range(tris):
            off = 84 + i * 50 + 12
            if off + 36 > len(raw):
                break
            for j in range(3):
                coords.append(struct.unpack_from("<3f", raw, off + j * 12))
    if not coords:
        return None
    mins = [min(c[k] for c in coords) for k in range(3)]
    maxs = [max(c[k] for c in coords) for k in range(3)]
    # 单位取自文件本身：STL 头不含单位信息，VERICUT 样例既有 inch 也有 mm，
    # 因此字段名不带 mm，绝不臆断（AGENTS.md §8 量纲核验）。
    return {
        "triangles": tris,
        "unit": "unknown_from_stl",
        "bbox_min": [round(v, 3) for v in mins],
        "bbox_max": [round(v, 3) for v in maxs],
        "extent": [round(maxs[k] - mins[k], 3) for k in range(3)],
    }


def _ply_vertex_count(path: Path) -> Optional[int]:
    try:
        with path.open("rb") as f:
            head = f.read(4096)
    except OSError:
        return None
    m = re.search(rb"element\s+vertex\s+(\d+)", head)
    return int(m.group(1)) if m else None


def build_geometry_summary(paths: List[Path], root: Path) -> Tuple[List[KnowledgeRecord], int]:
    """几何资产不逐条灌库（286 STL + 193 PLY 会淹没语义检索），聚合为一条统计知识。"""
    if not paths:
        return [], 0
    samples: List[Dict[str, Any]] = []
    total_tris = 0
    counted = 0
    for p in paths:
        if p.suffix.lower() == ".stl":
            box = stl_bbox(p)
            if box:
                counted += 1
                total_tris += int(box["triangles"])
                if len(samples) < 18:
                    samples.append({"file": p.name, **box})
        elif p.suffix.lower() in {".ply", ".xply"}:
            n = _ply_vertex_count(p)
            if n:
                counted += 1
                if len(samples) < 18:
                    samples.append({"file": p.name, "vertices": n})
    by_ext: Dict[str, int] = {}
    for p in paths:
        by_ext[p.suffix.lower()] = by_ext.get(p.suffix.lower(), 0) + 1
    content = (
        f"【聚合统计记录，非单一文件】VERICUT 官方培训几何资产共 {len(paths)} 个文件，"
        f"按类型 {json.dumps(by_ext, ensure_ascii=False)}。"
        f"可解析包围盒/顶点数的 {counted} 个；STL 三角面合计 {total_tris}。"
        f"STL 文件头不含单位信息，字段 unit=unknown_from_stl，不臆断 mm/inch。\n"
        f"实测样本（文件名 / 包围盒 / 面数）：{json.dumps(samples, ensure_ascii=False)[:1600]}"
    )
    evidence = {"file_count": len(paths), "by_extension": by_ext,
                "parsed_count": counted, "stl_triangles_total": total_tris,
                "samples": samples}
    digest = hashlib.sha256("|".join(sorted(p.name for p in paths)).encode("utf-8")).hexdigest()
    anchor = root / "_geometry_assets_summary"
    return [_mk("geometry_assets", "VERICUT 培训几何资产实测统计", content,
                anchor, root, digest, evidence)], counted


# --------------------------------------------------------------------------- misc text
def parse_text_config(path: Path, root: Path, digest: str) -> List[KnowledgeRecord]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith(";")]
    if not lines:
        return []
    macros = [ln for ln in lines if re.match(r"^(CGTECH_MACRO|DEF|#\d|G\d|M\d)", ln, re.I)][:12]
    content = (
        f"VERICUT 配置/宏文件 {path.name} 共 {len(lines)} 行有效文本。\n"
        f"开头：{' | '.join(lines[:10])}\n"
        f"关键宏/定义：{' | '.join(macros) if macros else '（无）'}"
    )
    evidence = {"line_count": len(lines), "macro_lines": macros, "head": lines[:10]}
    return [_mk("vericut_text_config", f"VERICUT 宏/配置 {path.name}",
                content, path, root, digest, evidence)]


# --------------------------------------------------------------------------- scan
def scan(root: Path = DEFAULT_ROOT, *, pages_per_chunk: int = _PDF_CHUNK_PAGES,
         max_files: Optional[int] = None) -> Tuple[List[KnowledgeRecord], ScanStats]:
    """只读扫描培训库，返回 (记录, 统计)。``max_files`` 用于冒烟测试。"""
    root = Path(root)
    stats = ScanStats()
    records: List[KnowledgeRecord] = []
    geometry: List[Path] = []
    if not root.is_dir():
        stats.errors.append(f"training root not found: {root}")
        return records, stats

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        ext = path.suffix.lower()
        stats.by_extension[ext] = stats.by_extension.get(ext, 0) + 1
        stats.files_seen += 1
        if max_files and stats.files_seen > max_files:
            break
        if ext in SKIP_EXT:
            stats.skipped["unsupported_binary"] = stats.skipped.get("unsupported_binary", 0) + 1
            continue
        try:
            if ext in GEOMETRY_EXT or ext in MACHINE_EXT:
                geometry.append(path)
                continue
            digest = sha256_file(path)
            produced: List[KnowledgeRecord] = []
            if ext in PROJECT_EXT:
                produced = parse_project(path, root, digest)
            elif ext in XML_CONFIG_EXT:
                produced = parse_xml_config(path, root, digest)
            elif ext in NC_EXT:
                produced = parse_nc_program(path, root, digest)
            elif ext in PDF_EXT:
                produced, pages, ok = parse_pdf(path, root, digest, pages_per_chunk)
                if ok:
                    stats.pdf_pages += pages
                else:
                    stats.pdf_unavailable_reason = "pymupdf/fitz not installed"
                    stats.skipped["pdf_no_extractor"] = stats.skipped.get("pdf_no_extractor", 0) + 1
            elif ext in TEXT_CONFIG_EXT:
                produced = parse_text_config(path, root, digest)
            else:
                stats.skipped["other"] = stats.skipped.get("other", 0) + 1
            for r in produced:
                stats.records_by_type[r.source_type] = stats.records_by_type.get(r.source_type, 0) + 1
            records.extend(produced)
        except Exception as exc:  # noqa: BLE001 - 单文件失败不得中断整批，但必须留痕
            stats.errors.append(f"{path.name}: {type(exc).__name__}: {str(exc)[:160]}")

    geo_records, counted = build_geometry_summary(geometry, root)
    stats.geometry_bbox_samples = counted
    for r in geo_records:
        stats.records_by_type[r.source_type] = stats.records_by_type.get(r.source_type, 0) + 1
    records.extend(geo_records)
    return records, stats


def records_to_jsonl(records: Iterable[KnowledgeRecord], out_path: Path) -> int:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out_path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r.to_dict(), ensure_ascii=False) + "\n")
            n += 1
    return n
