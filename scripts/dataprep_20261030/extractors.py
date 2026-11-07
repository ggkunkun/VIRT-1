# -*- coding: utf-8 -*-
"""
Virtu 数据集构建 · 抽取层
================================
从 D:\\新图纸\\图纸(2) 与 D:\\新图纸\\图纸(3) 抽取结构化事实记录。

所有产出均为"从源文件中实际解析出来的字段"，不引入任何模型臆造数值，
以便后续 SFT 生成阶段可以逐条溯源。
"""
from __future__ import annotations

import io
import json
import os
import re
import struct
import hashlib
import collections
from dataclasses import dataclass, field, asdict
from typing import Any

# --------------------------------------------------------------------------
# 通用工具
# --------------------------------------------------------------------------


def sha256_file(path: str, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def write_jsonl(path: str, records: list[dict]) -> int:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(records)


def write_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def read_pdf_text(path: str) -> dict:
    """用 PyMuPDF 抽取 PDF 的文本 / 矢量路径 / 图像统计。"""
    import pymupdf

    doc = pymupdf.open(path)
    pages = []
    for pg in doc:
        try:
            drawings = pg.get_drawings()
        except Exception:
            drawings = []
        pages.append({
            "page_no": pg.number + 1,
            "width_pt": round(pg.rect.width, 2),
            "height_pt": round(pg.rect.height, 2),
            "text": pg.get_text(),
            "vector_path_count": len(drawings),
            "image_count": len(pg.get_images(full=True)),
        })
    meta = doc.metadata or {}
    out = {
        "page_count": doc.page_count,
        "metadata": {k: v for k, v in meta.items() if v},
        "pages": pages,
        "full_text": "\n".join(p["text"] for p in pages),
        "total_vector_paths": sum(p["vector_path_count"] for p in pages),
        "total_images": sum(p["image_count"] for p in pages),
    }
    doc.close()
    return out


# --------------------------------------------------------------------------
# 1. NX .prt  (SPLMSSTR 容器)
# --------------------------------------------------------------------------

# 有工程语义的特征/操作类型
_UG_FEATURE_HINTS = (
    "EXTRUDE", "HOLE", "REVOLVE", "MILL", "TURN", "MORPH", "BLEND", "CHAMFER",
    "FILLET", "DRAFT", "SHELL", "SLOT", "BLOCK", "LOFT", "SWEEP", "SECTION",
    "BODY", "DRAWING", "DRAFT", "MASS", "LAYER", "MATH", "MEASURE", "WAVE",
    "EDGE", "FACE", "CURVE", "PLANE", "POINT",
)


@dataclass
class NXModel:
    """一个 NX .prt 模型的结构化事实。"""
    filename: str
    source_dir: str
    size_bytes: int
    sha256: str
    part_name: str = ""
    is_assembly: bool = False
    parasolid_schema: str = ""
    parasolid_version: str = ""
    has_parasolid_geometry: bool = False
    has_jt_tessellation: bool = False
    has_embedded_preview: bool = False
    feature_type_census: dict = field(default_factory=dict)
    operation_counts: dict = field(default_factory=dict)
    attributes: dict = field(default_factory=dict)
    component_parts: list = field(default_factory=list)
    component_count: int = 0
    body_count: int = 0
    drawing_present: bool = False
    annotation_present: bool = False
    preview_image: str = ""          # 相对 asset 目录
    preview_size: list = field(default_factory=list)
    source_path: str = ""
    errors: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _extract_preview_jpeg(raw: bytes) -> tuple[bytes, tuple[int, int]] | tuple[None, None]:
    """
    从 .prt 中定位内嵌 JPEG 预览图（NX 在 /Root/images/preview 存放）。

    注意：部分模型里还嵌着图框/标题栏位图等其它 JPEG，
    因此不能简单取"最大的一张"——NX 的模型预览图固定为 247×185，
    这里按该特征优先选取，避免把标题栏位图当成模型预览。
    """
    from PIL import Image

    cands = []
    for m in re.finditer(rb"\xff\xd8\xff", raw):
        o = m.start()
        e = raw.find(b"\xff\xd9", o)
        if e == -1:
            continue
        blob = raw[o:e + 2]
        if len(blob) < 1500:
            continue
        try:
            im = Image.open(io.BytesIO(blob))
            im.load()
        except Exception:
            continue
        cands.append((blob, len(blob), im.size))
    if not cands:
        return None, None
    # 1) 优先：尺寸等于 NX 模型预览标准 247×185
    exact = [c for c in cands if c[2] == (247, 185)]
    if exact:
        best = exact[0]
        return best[0], best[2]
    # 2) 其次：长宽比接近 4:3 且体积较小的（小图多为缩略预览）
    def score(c):
        w, h = c[2]
        ratio = w / h if h else 0
        return (abs(ratio - 4 / 3) * 1000 + c[1])
    best = sorted(cands, key=score)[0]
    return best[0], best[2]


def parse_nx_prt(path: str, source_dir: str, preview_dir: str | None = None) -> NXModel:
    """解析 NX .prt 为结构化事实记录。"""
    import xml.etree.ElementTree as ET

    raw = open(path, "rb").read()
    fname = os.path.basename(path)
    model = NXModel(
        filename=fname,
        source_dir=source_dir,
        size_bytes=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
        source_path=os.path.abspath(path),
    )
    model.part_name = os.path.splitext(fname)[0]

    # --- ASCII 字符串池 ---
    strs = [s.decode("latin1") for s in re.findall(rb"[\x20-\x7e]{3,120}", raw)]

    # --- Parasolid 内核 schema ---
    m = re.search(rb"SCH=SCH_(\d+)_(\d+)", raw)
    if m:
        model.parasolid_schema = m.group(1).decode()
        model.parasolid_version = m.group(2).decode()
        model.has_parasolid_geometry = True

    # --- 装配体判定：含装配结构描述 / 无实体几何 ---
    assy_markers = [s for s in strs if "Assy::StructureDescription" in s]
    model.is_assembly = bool(assy_markers) and not model.has_parasolid_geometry

    # --- JT 轻量化数据 ---
    model.has_jt_tessellation = any("Facet::JT" in s for s in strs) or \
        b"Version 9.4 JT" in raw

    # --- 特征类型统计 ---
    feats = collections.Counter()
    for s in strs:
        if s.startswith("UGS::") and "::" in s[5:]:
            tail = s.split("::")[-1]
            if any(k in tail.upper() for k in _UG_FEATURE_HINTS):
                feats[tail] += 1
    model.feature_type_census = dict(sorted(feats.items(), key=lambda x: -x[1]))

    # --- 建模操作计数（EXTRUDE / HOLE PACKAGE / SIMPLE HOLE ...）---
    ops = collections.Counter()
    for s in strs:
        u = s.strip().upper()
        if u in {"EXTRUDE", "REVOLVE", "MORPH", "BLEND", "CHAMFER", "FILLET",
                 "DRAFT", "SHELL", "HOLE PACKAGE", "SIMPLE HOLE", "HOLE",
                 "MILL PLANAR", "MILL", "TURN", "LOFT", "BLOCK", "SWEEP"}:
            ops[u] += 1
    model.operation_counts = dict(sorted(ops.items(), key=lambda x: -x[1]))

    # --- 属性表（UgAttributes XML） ---
    xml_blobs = []
    for mm in re.finditer(rb"<UgAttributes", raw):
        end = raw.find(b"</UgAttributes>", mm.start())
        if end != -1:
            xml_blobs.append(raw[mm.start():end + 15].decode("utf-8", "ignore"))
    if xml_blobs:
        try:
            root = ET.fromstring(xml_blobs[0])
            for el in root.findall("Attribute"):
                title = el.get("title") or el.get("utf8title") or ""
                val = el.get("utf8value") or el.get("value") or ""
                if title:
                    model.attributes[title] = val
        except Exception as exc:                       # pragma: no cover
            model.errors.append(f"xml:{exc}")

    # --- 装配组件（BOM） ---
    if model.is_assembly:
        comps = sorted({s for s in strs
                        if re.fullmatch(r"[A-Za-z0-9_\- ]+\.prt", s)
                        and s.lower() != fname.lower()})
        model.component_parts = comps
        model.component_count = len(comps)

    # --- 实体 / 标注 ---
    model.body_count = sum(v for k, v in model.feature_type_census.items()
                           if k.upper().startswith("BODY"))
    model.drawing_present = any("Drafting::PartRoot" in s or "Drawing::Sheet" in s
                                for s in strs)
    model.annotation_present = any("Annot::" in s for s in strs)

    # --- 内嵌预览图 ---
    blob, size = _extract_preview_jpeg(raw)
    if blob:
        model.has_embedded_preview = True
        model.preview_size = list(size) if size else []
        if preview_dir:
            os.makedirs(preview_dir, exist_ok=True)
            out = os.path.join(preview_dir, f"{model.part_name}.jpg")
            with open(out, "wb") as f:
                f.write(blob)
            model.preview_image = os.path.basename(out)
    return model


# --------------------------------------------------------------------------
# 2. 二维工程图：PDF / SVG
# --------------------------------------------------------------------------

_DIM_RE = re.compile(
    r"(?:⌀|Φ|Ø|φ)\s*(\d+(?:\.\d+)?)"
    r"|(\d+(?:\.\d+)?)\s*[×xX*]\s*(\d+(?:\.\d+)?)"
    r"|\bR(\d+(?:\.\d+)?)\b"
    r"|\b(\d+(?:\.\d+)?)\s*±\s*(\d+(?:\.\d+)?)"
    r"|\b(\d+(?:\.\d+)?)\b"
)


def parse_dimension_tokens(text: str) -> dict:
    """从图纸文本中抽取尺寸族统计（直径/半径/阵列/公差/普通尺寸）。"""
    t = text.replace("\n", " ")
    out = {
        "diameters": [], "radius": [], "arrays": [], "toleranced": [], "linear": [],
    }
    for m in re.finditer(r"[⌀ΦØφ]\s*(\d+(?:\.\d+)?)(?:\s*[×xX*]\s*(\d+(?:\.\d+)?))?", t):
        v = float(m.group(1))
        out["diameters"].append(v)
    for m in re.finditer(r"(?<![\w.])R(\d+(?:\.\d+)?)", t):
        out["radius"].append(float(m.group(1)))
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*[×xX*]\s*(⌀|Φ|Ø)?\s*(\d+(?:\.\d+)?)", t):
        out["arrays"].append((float(m.group(1)), float(m.group(3))))
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*±\s*(\d+(?:\.\d+)?)", t):
        out["toleranced"].append((float(m.group(1)), float(m.group(2))))
    return out


def parse_title_block(text: str) -> dict:
    """解析中文工程图标题栏（零件名称/图号/材料/比例/数量/设计/日期/单位）。"""
    tb = {}
    pats = {
        "part_name": r"零件名称\s*\n?\s*([^\n]{1,40})",
        "drawing_no": r"图号\s*\n?\s*([^\n]{1,30})",
        "material": r"材料\s*\n?\s*([^\n]{1,30})",
        "scale": r"比例\s*\n?\s*([^\n]{1,20})",
        "quantity": r"数量\s*\n?\s*([^\n]{1,20})",
        "designer": r"(?:设计|设计教学组|制图)\s*\n?\s*([^\n]{1,30})",
        "date": r"日期\s*\n?\s*([^\n]{1,20})",
        "organization": r"单位\s*\n?\s*([^\n]{1,40})",
    }
    for k, p in pats.items():
        m = re.search(p, text)
        if m:
            tb[k] = m.group(1).strip()
    return tb


def parse_tech_requirements(text: str) -> list[str]:
    """抽取"技术要求"条目。"""
    idx = text.find("技术要求")
    if idx == -1:
        return []
    seg = text[idx + 4:]
    items = []
    for line in seg.split("\n"):
        line = line.strip()
        m = re.match(r"^(\d+)[.、]\s*(.+)$", line)
        if m and len(m.group(2)) > 8:
            items.append(f"{m.group(1)}. {m.group(2)}")
        elif len(line) > 18 and not line.startswith("加工参数"):
            items.append(line)
        if len(items) >= 20:
            break
    return items


def parse_machining_table(text: str) -> list[dict]:
    """从纯文本抽取"加工参数表"（退化路径；优先使用版面感知版本）。"""
    idx = text.find("加工参数表")
    if idx == -1:
        return []
    seg = text[idx:]
    lines = [l.strip() for l in seg.split("\n") if l.strip()]
    out, pend = [], []
    for l in lines:
        nums = re.findall(r"(\d+(?:\.\d+)?)\s*(r/min|mm/min)", l)
        if nums:
            pend.append({"rpm_feed": [f"{n} {u}" for n, u in nums]})
            continue
        if pend and len(l) > 2 and not l.startswith("加工参数"):
            out.append({"operation": l, "params": pend})
            pend = []
    return out


# --------------------------------------------------------------------------
# 2b. 版面感知抽取（基于词级坐标）
# --------------------------------------------------------------------------

def page_words(page) -> list[dict]:
    """把 PDF 页面的词级文本转成带坐标的记录。"""
    out = []
    for w in page.get_text("words"):
        out.append({
            "text": w[4],
            "x0": round(w[0], 2), "y0": round(w[1], 2),
            "x1": round(w[2], 2), "y1": round(w[3], 2),
            "cx": round((w[0] + w[2]) / 2, 2),
            "cy": round((w[1] + w[3]) / 2, 2),
        })
    return out


def cluster_rows(words: list[dict], tol: float = 6.0) -> list[list[dict]]:
    """按纵坐标把词聚成行。"""
    rows: list[list[dict]] = []
    for w in sorted(words, key=lambda x: (x["cy"], x["x0"])):
        placed = False
        for r in rows:
            if abs(r[0]["cy"] - w["cy"]) <= tol:
                r.append(w)
                placed = True
                break
        if not placed:
            rows.append([w])
    for r in rows:
        r.sort(key=lambda x: x["x0"])
    rows.sort(key=lambda r: r[0]["cy"])
    return rows


def join_row(row: list[dict], gap: float = 12.0) -> str:
    """把一行词按间隙合并成字符串（间隙小则不插空格）。"""
    parts, prev_x1 = [], None
    for w in row:
        if prev_x1 is not None and w["x0"] - prev_x1 > gap:
            parts.append(" ")
        parts.append(w["text"])
        prev_x1 = w["x1"]
    return "".join(parts).strip()


# 标题栏 / 技术要求 / 参数表的定位关键字
_TB_LABELS = ("零件名称", "图号", "材料", "比例", "数量", "设计", "日期", "单位")


# 英文图框/注释区关键词（用于把这些区域从尺寸集合中排除）
_EN_TITLE_KEYS = ("DRAWN", "CHECKED", "APPROVED", "SCALE", "MATERIAL",
                  "DESCRIPTION", "SPECIFICATION", "WEIGHT", "PART NAME",
                  "DRG.NO", "SHEET", "CCR", "TITLE")
# 说明/通用公差区关键词
_NOTE_KEYS = ("UNSPECIFIED", "TOLERANCE", "OVER", "UNDER", "DRAFT",
              "WHATSAPP", "QUERIES", "OPPORTUNIT", "ALL DIMENSIONS")


def locate_regions(page, words: list[dict]) -> dict:
    """定位图纸的标题栏 / 技术要求 / 参数表 / 图框 / 注释区。"""
    W, H = page.rect.width, page.rect.height
    tb, tech, tbl, views = [], [], [], []
    for w in words:
        t = w["text"]
        if t in _TB_LABELS and w["x0"] > W * 0.45 and w["y0"] > H * 0.72:
            tb.append(w)
        elif t == "技术要求":
            tech.append(w)
        elif t.startswith("加工参数表"):
            tbl.append(w)
        elif re.search(r"(VIEW|SECTION|DETAIL|剖视|主视图|俯视图|等轴测)", t, re.I):
            views.append(w)
    reg = {"sheet": [round(W, 2), round(H, 2)],
           "title_block_words": len(tb), "tech_req_words": len(tech),
           "param_table_words": len(tbl), "view_labels": []}
    reg["view_labels"] = [w["text"] for w in views]
    # 中文标题栏（右下矩形区）—— 仅当图纸确实带中文标题栏标签时才建立，
    # 否则英文图纸的右下角是 NOTE/公差表，用它会把整块底部误杀
    if tb:
        tb_region = [w for w in words
                      if w["x0"] > W * 0.45 and w["y0"] > H * 0.70]
        reg["title_block_box"] = [
            round(min(w["x0"] for w in tb_region) - 14, 2),
            round(min(w["y0"] for w in tb_region) - 14, 2),
            round(max(w["x1"] for w in tb_region) + 14, 2),
            round(max(w["y1"] for w in tb_region) + 14, 2),
        ]
    # 英文图框：由 DRAWN/CHECKED/SCALE 等关键词定位。
    # 关键点：这些词在页眉说明里也会出现（如顶部的 DESCRIPTION），
    # 直接取全局外接框会覆盖整张图 → 改用"关键词最密集的那一条水平带"。
    en_kw = [w for w in words if w["text"].upper() in _EN_TITLE_KEYS]
    if en_kw:
        bands = collections.Counter(round(w["cy"] / 8) for w in en_kw)
        modal_y = bands.most_common(1)[0][0] * 8
        band = [w for w in en_kw if abs(w["cy"] - modal_y) <= 26]
        if band:
            reg["en_title_block_box"] = [
                round(min(w["x0"] for w in band) - 18, 2),
                round(min(w["y0"] for w in band) - 14, 2),
                round(max(w["x1"] for w in band) + 18, 2),
                round(max(w["y1"] for w in band) + 14, 2),
            ]
    if tech:
        # 技术要求栏是整列文本，必须按"锚点右侧整列"取外接框，
        # 否则栏内靠右的长句会漏进尺寸标注集合
        anchor = max(tech, key=lambda w: w["y0"])
        col = [w for w in words
               if w["x0"] >= anchor["x0"] - 8 and anchor["y0"] - 4 <= w["y0"] <= anchor["y0"] + 340]
        reg["tech_req_box"] = [
            round(min(w["x0"] for w in col) - 8, 2),
            round(min(w["y0"] for w in col) - 8, 2),
            round(max(w["x1"] for w in col) + 8, 2),
            round(max(w["y1"] for w in col) + 8, 2),
        ]
    if tbl:
        reg["param_table_box"] = [
            round(min(w["x0"] for w in tbl) - 6, 2),
            round(min(w["y0"] for w in tbl) - 6, 2),
            round(W, 2),
            round(min(w["y0"] for w in tbl) + 170, 2),
        ]
    return reg


def _in_box(w: dict, box: list | None) -> bool:
    if not box:
        return False
    return box[0] <= w["cx"] <= box[2] and box[1] <= w["cy"] <= box[3]


_TB_KEY_MAP = {
    "零件名称": "part_name", "图号": "drawing_no", "材料": "material",
    "比例": "scale", "数量": "quantity", "设计教学组": "designer",
    "设计": "designer", "日期": "date", "单位": "organization",
}


def extract_title_block(page, words: list[dict]) -> dict:
    """
    从标题栏版块抽取键值对。

    标题栏是多列布局，同一行里会出现"标签 值 标签 值"，
    因此必须按"标签词 → 其右侧直到下一个标签词之前"的词序列来切分。
    """
    tb_words = [w for w in words
                if w["x0"] > page.rect.width * 0.45
                and w["y0"] > page.rect.height * 0.70]
    tb = {}
    for row in cluster_rows(tb_words):
        # 定位该行内的标签词下标
        label_idx = []
        for i, w in enumerate(row):
            t = w["text"].strip()
            if t.startswith("日期"):
                tb["date"] = t[2:].strip("：: ")
                continue
            if t in _TB_KEY_MAP or t in ("设计", "制图", "审核", "工艺"):
                label_idx.append((i, t))
        if not label_idx:
            continue
        for k, (i, lab) in enumerate(label_idx):
            end = label_idx[k + 1][0] if k + 1 < len(label_idx) else len(row)
            val = "".join(w["text"] for w in row[i + 1:end]).strip()
            val = val.strip("：: ")
            key = _TB_KEY_MAP.get(lab, lab)
            if lab in ("设计教学组",):
                tb["designer"] = lab
                continue
            if key == "designer" and val:
                tb["designer"] = val
            elif val:
                tb[key] = val
    return tb


def extract_tech_requirements(page, words: list[dict]) -> list[str]:
    """按版面抽取技术要求条目（右侧栏）。"""
    anchor = next((w for w in words if w["text"] == "技术要求"), None)
    if not anchor:
        return []
    x0 = anchor["x0"] - 6
    band = [w for w in words if w["x0"] >= x0 - 4 and w["y0"] > anchor["y1"]
            and w["y0"] < anchor["y1"] + 220]
    rows = cluster_rows(band)
    items = []
    for row in rows:
        line = join_row(row, gap=3)
        line = line.strip()
        if not line:
            continue
        if line.startswith("加工参数表"):
            break
        m = re.match(r"^(\d+)[.、]\s*(.+)$", line)
        if m and len(m.group(2)) > 6:
            items.append(f"{m.group(1)}. {m.group(2)}")
    return items


def extract_param_table(page, words: list[dict]) -> list[dict]:
    """按列坐标重建"加工参数表"（工序/刀具/主轴转速/进给/备注）。"""
    anchor = next((w for w in words if w["text"].startswith("加工参数表")), None)
    if not anchor:
        return []
    top = anchor["y1"]
    band = [w for w in words if w["y0"] > top and w["y0"] < top + 190
            and w["x0"] > page.rect.width * 0.5]
    rows = cluster_rows(band)
    headers, body = None, []
    for row in rows:
        line = join_row(row, gap=3)
        if "工序" in line and "刀具" in line:
            headers = row
            continue
        if headers is None:
            continue
        # 用表头 x 位置分列
        cols = {}
        for h in headers:
            for w in row:
                if abs(w["cx"] - h["cx"]) < 46:
                    cols[h["text"]] = cols.get(h["text"], "") + w["text"]
                    break
        if not cols:
            continue
        rec = {
            "operation": cols.get("工序", "").strip(),
            "tool": cols.get("刀具", "").strip(),
            "spindle_rpm": cols.get("主轴转速", "").strip(),
            "feed": cols.get("进给", "").strip(),
            "remark": cols.get("备注", "").strip(),
        }
        if rec["operation"]:
            body.append(rec)
    return body


_DIM_TOKEN_RE = re.compile(
    r"^(?:(?P<sym>[⌀ΦØφRrCcMm]|THRU|R)\s*)?"
    r"(?P<qty>\d+(?:\.\d+)?)?"
    r"(?:\s*[×xX*]\s*(?P<qty2>\d+(?:\.\d+)?))?"
    r"(?:\s*(?P<qual>[A-Z][A-Z0-9]*))?"
    r"(?:\s*±\s*(?P<tol>\d+(?:\.\d+)?))?$"
)


_MALFORMED_CHARS = ("（", "）", "(", ")", "，", ",", "；", ";", "。", ":", "：")


def classify_dimension_token(t: str) -> dict | None:
    """
    判定单个标注 token 的语义，返回结构化标注；无法判定返回 None。

    覆盖：⌀D / N×⌀D / R / N×R / C / N×C / M 螺纹 / ±公差 / 阵列数 / 角度 / 深度 / 粗糙度
    拒绝：含标点残片的半截标注（如「深12（底孔Ø14」）、纯长数字（电话）等
    """
    t = t.strip()
    if not t:
        return None
    if any(c in t for c in _MALFORMED_CHARS):
        return None                      # 半截/复合语句，不是独立标注
    qty = None
    m = re.match(r"^(\d+)\s*[×xX*]\s*(.+)$", t)
    if m:
        qty = int(m.group(1))
        t = m.group(2).strip()
    rec: dict = {"text": t, "qty": qty}

    m = re.match(r"^([⌀ΦØφ])(\d+(?:\.\d+)?)([a-zA-Z]?\d*)?", t)
    if m:
        rec["type"] = "diameter"
        rec["value"] = float(m.group(2))
        if m.group(3):
            rec["fit"] = m.group(3)
        return rec
    m = re.match(r"^(?:R)(\d+(?:\.\d+)?)", t)
    if m:
        rec["type"] = "radius"
        rec["value"] = float(m.group(1))
        return rec
    m = re.match(r"^(?:C)(\d+(?:\.\d+)?)", t)
    if m:
        rec["type"] = "chamfer"
        rec["value"] = float(m.group(1))
        return rec
    m = re.match(r"^(?:M|METRIC)(\d+(?:\.\d+)?)(?:[×xX*](\d+(?:\.\d+)?))?(?:-(\w+))?", t)
    if m:
        rec["type"] = "thread"
        rec["value"] = float(m.group(1))
        if m.group(2):
            rec["pitch"] = float(m.group(2))
        if m.group(3):
            rec["fit"] = m.group(3)
        return rec
    m = re.match(r"^(\d+(?:\.\d+)?)\s*±\s*(\d+(?:\.\d+)?)", t)
    if m:
        rec["type"] = "toleranced_linear"
        rec["nominal"] = float(m.group(1))
        rec["tolerance"] = float(m.group(2))
        return rec
    m = re.match(r"^(\d+(?:\.\d+)?)\s*°", t)
    if m:
        rec["type"] = "angle"
        rec["value"] = float(m.group(1))
        return rec
    m = re.match(r"^(?:深|DEPTH|D)\s*(\d+(?:\.\d+)?)(?:\s*±\s*(\d+(?:\.\d+)?))?", t, re.I)
    if m:
        rec["type"] = "depth"
        rec["value"] = float(m.group(1))
        if m.group(2):
            rec["tolerance"] = float(m.group(2))
        return rec
    m = re.match(r"^(?:Ra|Rz|R)(\d+(?:\.\d+)?)$", t)
    if m:
        rec["type"] = "roughness"
        rec["value"] = float(m.group(1))
        return rec
    m = re.match(r"^(\d+(?:\.\d+)?)\s*(?:THRU|通孔)$", t, re.I)
    if m:
        rec["type"] = "thru_diameter"
        rec["value"] = float(m.group(1))
        return rec
    if re.fullmatch(r"\d+(?:\.\d+)?", t):
        rec["type"] = "linear"
        rec["value"] = float(t)
        return rec
    if re.fullmatch(r"\d+(?:\.\d+)?\s*THRU\s*ALL", t, re.I):
        rec["type"] = "thru_all"
        rec["value"] = float(t.split()[0])
        return rec
    return None


def _note_row_tokens(words: list[dict]) -> set:
    """返回属于"说明/通用公差/图框"行的词 id 集合（这些行的数字不是零件尺寸）。"""
    bad = set()
    for row in cluster_rows(words):
        line = join_row(row, gap=3).upper()
        if any(k in line for k in _NOTE_KEYS):
            for w in row:
                bad.add(id(w))
    return bad


def extract_dimension_callouts(page, words: list[dict], regions: dict) -> list[dict]:
    """抽取视图区的尺寸标注（排除标题栏/技术要求/参数表/图框/说明区）。"""
    tb_box = regions.get("title_block_box")
    tech_box = regions.get("tech_req_box")
    tbl_box = regions.get("param_table_box")
    en_box = regions.get("en_title_block_box")
    view_labels = {v.upper() for v in regions.get("view_labels", [])}
    note_ids = _note_row_tokens(words)
    out = []
    for w in words:
        if _in_box(w, tb_box) or _in_box(w, tech_box) or _in_box(w, tbl_box) \
                or _in_box(w, en_box):
            continue
        if id(w) in note_ids:
            continue
        t = w["text"].strip()
        if not t or len(t) > 24:
            continue
        if t.upper() in view_labels:
            continue
        # 电话号码等长数字不是尺寸
        if re.fullmatch(r"\d{6,}", t.replace(".", "")):
            continue
        rec = classify_dimension_token(t)
        if rec is None:
            continue
        rec["x"] = w["cx"]
        rec["y"] = w["cy"]
        out.append(rec)
    return out


def extract_marking_table_rows(page, words: list[dict]) -> list[dict]:
    """
    重建世赛评分表（OMF）的 Aspect 行。

    结构：AspectID | MaxMark | AspectDescription | Requirement/NominalSize | Result | MarkAwarded
    策略：先按行聚类，再按"行首 token 命中 Aspect-ID 形态"来锚定数据行，
    避免把页眉（'Sub Criterion ID' / 'Marking Scheme'）误判成表头。
    """
    rows = cluster_rows(words)
    id_pat = re.compile(r"^[A-Z]{1,2}\d{1,2}(\.\d+)?$")
    out = []
    for r in rows:
        if not r:
            continue
        first = r[0]["text"].strip()
        if not id_pat.fullmatch(first):
            continue
        rec = {"aspect_id": first, "max_mark": "", "description": "", "requirement": ""}
        rest = r[1:]
        # 第二个 token 通常是 Max Mark
        if rest:
            m = re.fullmatch(r"\d+(\.\d+)?", rest[0]["text"].strip())
            if m:
                rec["max_mark"] = rest[0]["text"].strip()
                rest = rest[1:]
        toks = [w["text"].strip() for w in rest]
        # 末尾的"量值要求"：形如 45,32/45,31 或 Ra0.4 或 Ø52
        req_idx = None
        for i in range(len(toks) - 1, -1, -1):
            t = toks[i]
            if re.fullmatch(r"[\d.,]+/[\d.,]+", t) or re.fullmatch(r"Ra\d+(\.\d+)?", t) \
                    or re.fullmatch(r"[⌀ΦØ]\d+(\.\d+)?([a-zA-Z]\d*)?", t) \
                    or re.fullmatch(r"\d+(\.\d+)?(mm|cm)?", t):
                req_idx = i
                break
        if req_idx is not None and req_idx > 0:
            req_toks = toks[req_idx:]
            # 处理 PDF 分词导致的 "Ra 0.4" / "Ø 52" 断裂
            if req_idx > 0 and re.fullmatch(r"[\d.,]+/[\d.,]+|[\d.,]+", req_toks[0]) \
                    and re.fullmatch(r"(Ra|Rz|Ø|⌀|Φ|M|METRIC)", toks[req_idx - 1]):
                req_toks = [toks[req_idx - 1]] + req_toks
                req_idx -= 1
            rec["requirement"] = " ".join(req_toks)
            rec["description"] = " ".join(toks[:req_idx])
        else:
            rec["description"] = " ".join(toks)
        out.append(rec)
    return out


def extract_marking_form_header(page, words: list[dict]) -> dict:
    """抽取世赛评分表页眉：技能号/技能名/比赛日/子标准名/子标准ID/锁定时间。"""
    rows = cluster_rows(words)
    joined = [" ".join(w["text"] for w in r) for r in rows]
    head = {"skill_number": "", "skill_name": "", "competition_day": "",
            "sub_criterion": "", "sub_criterion_id": "",
            "marking_scheme_lock": "", "mark_entry_lock": ""}
    for line in joined:
        if line.startswith("Skill Number"):
            rest = line[len("Skill Number"):].strip()
            m = re.match(r"(\d{2})\s+Skill\s+(.+?)\s+Competition Day\s+(\d+)", rest)
            if m:
                head["skill_number"] = m.group(1)
                head["skill_name"] = m.group(2).strip()
                head["competition_day"] = m.group(3)
        elif line.startswith("Sub Criterion") and "Sub Criterion ID" in line:
            m = re.match(r"Sub Criterion\s+(.+?)\s+Sub Criterion ID\s+([A-Z]\d{1,2})", line)
            if m:
                head["sub_criterion"] = m.group(1).strip()
                head["sub_criterion_id"] = m.group(2)
        elif line.startswith("Marking Scheme Lock"):
            m = re.match(r"Marking Scheme Lock\s+(\d{2}-\d{2}-\d{4})\s+(\d{2}:\d{2}:\d{2})", line)
            if m:
                head["marking_scheme_lock"] = f"{m.group(1)} {m.group(2)}"
        elif line.startswith("Mark Entry Lock"):
            m = re.match(r"Mark Entry Lock\s+(\d{2}-\d{2}-\d{4})\s+(\d{2}:\d{2}:\d{2})", line)
            if m:
                head["mark_entry_lock"] = f"{m.group(1)} {m.group(2)}"
        elif "Maximum Mark for Sub Criterion" in line:
            m = re.match(r"([\d.,]+)\s+Maximum Mark", line)
            if m:
                head["sub_criterion_max_mark"] = m.group(1)
    return head


def parse_marking_form_pdf(path: str) -> dict:
    """解析世赛 OMF/SMF 评分表 PDF → 逐页子标准 + Aspect 行。"""
    import pymupdf

    doc = pymupdf.open(path)
    pages = []
    for pg in doc:
        ws = page_words(pg)
        pages.append({
            "page_no": pg.number + 1,
            "header": extract_marking_form_header(pg, ws),
            "aspect_rows": extract_marking_table_rows(pg, ws),
            "word_count": len(ws),
        })
    meta = doc.metadata or {}
    doc.close()
    all_aspects = []
    for p in pages:
        for a in p["aspect_rows"]:
            a = dict(a)
            a.update({k: v for k, v in p["header"].items() if v})
            all_aspects.append(a)
    subc = []
    seen = set()
    for p in pages:
        h = p["header"]
        key = (h.get("sub_criterion_id"), h.get("sub_criterion"))
        if key[0] and key not in seen:
            seen.add(key)
            subc.append({
                "sub_criterion_id": key[0],
                "sub_criterion_name": key[1],
                "max_mark": h.get("sub_criterion_max_mark", ""),
                "aspect_count": len(p["aspect_rows"]),
                "page_no": p["page_no"],
            })
    return {
        "source_file": os.path.basename(path),
        "page_count": len(pages),
        "metadata": {k: v for k, v in meta.items() if v},
        "sub_criteria": subc,
        "aspect_rows": all_aspects,
        "total_aspects": len(all_aspects),
        "pages": pages,
    }


def analyze_vector_page(page) -> dict:
    """统计矢量页的几何构成：线段数、矩形数、曲线数、包围盒、闭合轮廓数。"""
    try:
        drawings = page.get_drawings()
    except Exception:
        return {}
    kinds = collections.Counter()
    rects, curves, lines = [], 0, 0
    minx = miny = 1e18
    maxx = maxy = -1e18
    for d in drawings:
        kinds[d.get("type", "?")] += 1
        r = d.get("rect")
        if r is not None:
            rects.append((round(r.width, 2), round(r.height, 2)))
            minx, miny = min(minx, r.x0), min(miny, r.y0)
            maxx, maxy = max(maxx, r.x1), max(maxy, r.y1)
        for it in d.get("items", []):
            op = it[0]
            if op == "l":
                lines += 1
            elif op == "c":
                curves += 1
            elif op == "re":
                pass
    return {
        "path_kinds": dict(kinds),
        "rect_count": len(rects),
        "line_count": lines,
        "curve_count": curves,
        "content_bbox_pt": [round(minx, 2), round(miny, 2), round(maxx, 2), round(maxy, 2)]
        if minx < 1e18 else None,
    }


# --------------------------------------------------------------------------
# 3. WorldSkills 2013 评分表 (xlsx)
# --------------------------------------------------------------------------


def parse_marking_scheme_xlsx(path: str) -> dict:
    """解析世赛 marking_scheme.xlsx → 评分标准层级。"""
    import openpyxl

    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = []
    for r in ws.iter_rows(values_only=True):
        cells = [c for c in r if c is not None]
        if cells:
            rows.append([str(c).strip() if not isinstance(c, (int, float)) else c
                         for c in cells])
    skill = ""
    for i, r in enumerate(rows):
        if r and isinstance(r[0], str) and r[0].strip().lower() == "skill name":
            if len(r) > 1 and isinstance(r[1], str):
                skill = r[1].strip()
            elif i + 1 < len(rows) and rows[i + 1]:
                skill = str(rows[i + 1][0]).strip()
            break
    criteria = []
    for r in rows:
        if len(r) >= 3 and isinstance(r[0], str) and len(r[0]) == 1 and r[0].isalpha():
            name = re.sub(r"\s+", " ", str(r[1])).strip()
            try:
                mark = float(r[2])
            except Exception:
                mark = None
            criteria.append({"id": r[0], "name": name, "max_mark": mark})
    subcriteria = []
    for r in rows:
        if len(r) >= 2 and isinstance(r[0], str) and re.fullmatch(r"[A-Z]\d{1,2}", r[0]):
            subcriteria.append({"id": r[0], "name": str(r[1])})
    total = sum(c["max_mark"] for c in criteria if c["max_mark"] is not None)
    return {
        "source_file": os.path.basename(path),
        "skill_name": skill,
        "sheet": ws.title,
        "row_count": ws.max_row,
        "criteria": criteria,
        "sub_criteria": subcriteria,
        "criteria_total_mark": total,
    }


def parse_marking_form_pdf_legacy(path: str) -> dict:
    """（旧版纯文本路径，仅作回退；主路径见 parse_marking_form_pdf）"""
    info = read_pdf_text(path)
    text = info["full_text"]
    aspects = []
    for line in text.split("\n"):
        line = line.strip()
        m = re.match(r"^([A-Z]\d{1,2})\s+(.+)$", line)
        if m and len(m.group(2)) > 12:
            aspects.append({"aspect_id": m.group(1), "text": m.group(2)})
    marks = re.findall(r"Max Mark\s+(\d+(?:\.\d+)?)", text)
    return {
        "source_file": os.path.basename(path),
        "page_count": info["page_count"],
        "text_chars": len(text),
        "aspect_rows": aspects[:400],
        "max_marks": [float(x) for x in marks][:400],
    }


# --------------------------------------------------------------------------
# 4. 图片资产
# --------------------------------------------------------------------------


def image_stats(path: str) -> dict:
    from PIL import Image

    with Image.open(path) as im:
        w, h = im.size
        mode = im.mode
    return {"width": w, "height": h, "mode": mode,
            "aspect_ratio": round(w / h, 4) if h else None}


def render_pdf_page(pdf_path: str, out_png: str, dpi: int = 150) -> dict:
    """PDF → PNG（多页则拼接为多张，按页命名）。"""
    import pymupdf

    doc = pymupdf.open(pdf_path)
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    outs = []
    for pg in doc:
        pix = pg.get_pixmap(dpi=dpi)
        p = out_png if doc.page_count == 1 else \
            out_png.replace(".png", f"_p{pg.number + 1}.png")
        pix.save(p)
        outs.append(os.path.basename(p))
    doc.close()
    return {"rendered": outs, "dpi": dpi}


def render_svg(svg_path: str, out_png: str, dpi: int = 150) -> dict:
    """SVG → PNG（PyMuPDF 原生支持矢量 SVG）。"""
    import pymupdf

    doc = pymupdf.open(svg_path)
    pix = doc[0].get_pixmap(dpi=dpi)
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    pix.save(out_png)
    w, h = pix.width, pix.height
    doc.close()
    return {"rendered": [os.path.basename(out_png)], "dpi": dpi,
            "width": w, "height": h}


# --------------------------------------------------------------------------
# 5. 图纸整体分析（版面感知）
# --------------------------------------------------------------------------

def analyze_drawing_pdf(path: str) -> dict:
    """对一张工程图 PDF 做完整的版面感知分析。"""
    import pymupdf

    doc = pymupdf.open(path)
    pages = []
    for pg in doc:
        words = page_words(pg)
        regions = locate_regions(pg, words)
        pages.append({
            "page_no": pg.number + 1,
            "sheet_size_pt": [round(pg.rect.width, 2), round(pg.rect.height, 2)],
            "word_count": len(words),
            "regions": regions,
            "title_block": extract_title_block(pg, words),
            "tech_requirements": extract_tech_requirements(pg, words),
            "param_table": extract_param_table(pg, words),
            "dimension_callouts": extract_dimension_callouts(pg, words, regions),
            "vector_stats": analyze_vector_page(pg),
            "image_count": len(pg.get_images(full=True)),
            "text": pg.get_text(),
        })
    meta = doc.metadata or {}
    doc.close()
    full_text = "\n".join(p["text"] for p in pages)
    title_block = {}
    tech = []
    param_table = []
    dims = []
    view_labels = []
    for p in pages:
        title_block.update(p["title_block"])
        tech.extend(p["tech_requirements"])
        param_table.extend(p["param_table"])
        dims.extend(p["dimension_callouts"])
        view_labels.extend(p["regions"].get("view_labels", []))
    return {
        "source_file": os.path.basename(path),
        "page_count": len(pages),
        "metadata": {k: v for k, v in meta.items() if v},
        "title_block": title_block,
        "tech_requirements": tech,
        "param_table": param_table,
        "dimension_callouts": dims,
        "view_labels": sorted(set(view_labels)),
        "pages": pages,
        "full_text": full_text,
        "text_chars": len(full_text),
        "total_vector_paths": sum(len(p["vector_stats"].get("path_kinds", {}).items())
                                  for p in pages),
    }
