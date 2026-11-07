#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic synthetic engineering-drawing PNGs for the multimodal dimension.

Every image carries ground truth that this script itself records into
``data/benchmark/virtu_eval_v1/images/ground_truth.json``.  No randomness is
uncontrolled (all ``random.Random`` instances are explicitly seeded), no
network, no external assets — re-running reproduces byte-identical semantics.

Usage:  .venv/Scripts/python.exe scripts/make_multimodal_images.py
"""
from __future__ import annotations

import json
import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "data", "benchmark", "virtu_eval_v1", "images")

ARIAL = r"C:/Windows/Fonts/arial.ttf"
COURIER = r"C:/Windows/Fonts/cour.ttf"
SIMHEI = r"C:/Windows/Fonts/simhei.ttf"

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)


def fnt(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def canvas(w: int = 900, h: int = 620, bg=WHITE):
    img = Image.new("RGB", (w, h), bg)
    return img, ImageDraw.Draw(img)


def border(d, w=900, h=620):
    d.rectangle((10, 10, w - 10, h - 10), outline=BLACK, width=2)


def leader(d, x1, y1, x2, y2):
    d.line((x1, y1, x2, y2), fill=BLACK, width=2)


def cell(d, x, y, cw, ch, label=None, fnt_=None):
    d.rectangle((x, y, x + cw, y + ch), outline=BLACK, width=2)
    if label is not None:
        bb = d.textbbox((0, 0), label, font=fnt_)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        d.text((x + (cw - tw) / 2 - bb[0], y + (ch - th) / 2 - bb[1]), label, font=fnt_, fill=BLACK)


# ---------------------------------------------------------------- GD&T symbols
def sym_position(d, cx, cy, r=13):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=BLACK, width=2)
    d.line((cx - r, cy, cx + r, cy), fill=BLACK, width=2)
    d.line((cx, cy - r, cx, cy + r), fill=BLACK, width=2)


def sym_flatness(d, cx, cy):
    # parallelogram (flatness frame symbol)
    p = [(cx - 16, cy + 10), (cx - 4, cy - 10), (cx + 16, cy - 10), (cx + 4, cy + 10)]
    d.line(p + [p[0]], fill=BLACK, width=2)


def sym_concentricity(d, cx, cy):
    d.ellipse((cx - 14, cy - 14, cx + 14, cy + 14), outline=BLACK, width=2)
    d.ellipse((cx - 7, cy - 7, cx + 7, cy + 7), outline=BLACK, width=2)


# ------------------------------------------------------------------ builders
def img_dim_diameter():
    img, d = canvas()
    border(d)
    # shaft side view
    d.rectangle((250, 260, 650, 340), outline=BLACK, width=2)
    leader(d, 300, 300, 350, 160)
    d.text((360, 130), "Ø30h7", font=fnt(ARIAL, 46), fill=BLACK)
    d.text((250, 380), "单位 mm", font=fnt(SIMHEI, 22), fill=BLACK)
    return img, {
        "title": "直径尺寸标注",
        "callouts": ["Ø30h7"],
        "facts": {"nominal_diameter_mm": 30, "tolerance_class": "h7", "class_type": "轴公差带"},
    }


def img_dim_tolerance():
    img, d = canvas()
    border(d)
    d.line((200, 250, 200, 350), fill=BLACK, width=2)
    d.line((700, 250, 700, 350), fill=BLACK, width=2)
    d.line((200, 300, 700, 300), fill=BLACK, width=2)
    d.text((360, 200), "60±0.1", font=fnt(ARIAL, 50), fill=BLACK)
    d.text((200, 380), "单位 mm", font=fnt(SIMHEI, 22), fill=BLACK)
    return img, {
        "title": "线性尺寸带公差",
        "callouts": ["60±0.1"],
        "facts": {"nominal_mm": 60, "deviation_mm": 0.1, "max_mm": 60.1, "min_mm": 59.9},
    }


def img_dim_radius():
    img, d = canvas()
    border(d)
    d.rectangle((250, 220, 650, 400), outline=BLACK, width=2)
    d.arc((250, 280, 370, 400), start=180, end=270, fill=BLACK, width=2)
    leader(d, 330, 300, 420, 170)
    d.text((430, 140), "R5", font=fnt(ARIAL, 48), fill=BLACK)
    d.text((250, 430), "未注圆角见标注  单位 mm", font=fnt(SIMHEI, 22), fill=BLACK)
    return img, {"title": "圆角半径标注", "callouts": ["R5"], "facts": {"radius_mm": 5}}


def img_thread():
    img, d = canvas()
    border(d)
    d.text((200, 120), "螺纹标注", font=fnt(SIMHEI, 30), fill=BLACK)
    d.rectangle((200, 220, 700, 300), outline=BLACK, width=2)
    for x in range(220, 700, 40):
        d.line((x, 220, x + 20, 300), fill=BLACK, width=1)
    leader(d, 450, 250, 450, 380)
    d.text((280, 400), "M8×1.25-6H", font=fnt(ARIAL, 52), fill=BLACK)
    return img, {
        "title": "螺纹标注",
        "callouts": ["M8×1.25-6H"],
        "facts": {"thread": "M8", "pitch_mm": 1.25, "tolerance_class": "6H", "class_type": "内螺纹公差带"},
    }


def img_gdt_position():
    img, d = canvas()
    border(d)
    f = fnt(ARIAL, 30)
    x, y, cw, ch = 150, 230, 90, 60
    d.rectangle((x, y, x + cw, y + ch), outline=BLACK, width=2)
    sym_position(d, x + cw / 2, y + ch / 2, r=16)
    cell(d, x + cw, y, cw, ch, "Ø0.3", f)
    cell(d, x + 2 * cw, y, cw, ch, "A", f)
    cell(d, x + 3 * cw, y, cw, ch, "B", f)
    cell(d, x + 4 * cw, y, cw, ch, "C", f)
    leader(d, x + cw / 2, y + ch, 500, 450)
    d.text((505, 435), "基准A", font=fnt(SIMHEI, 24), fill=BLACK)
    d.text((150, 120), "形位公差框格（左起第1格为公差项目符号）", font=fnt(SIMHEI, 24), fill=BLACK)
    return img, {
        "title": "位置度公差框格",
        "callouts": ["Ø0.3", "A", "B", "C"],
        "facts": {"gdt_type": "位置度", "tolerance_mm": 0.3, "tolerance_zone": "直径0.3", "datums": ["A", "B", "C"]},
    }


def img_gdt_flatness():
    img, d = canvas()
    border(d)
    x, y, cw, ch = 200, 240, 90, 60
    d.rectangle((x, y, x + cw, y + ch), outline=BLACK, width=2)
    sym_flatness(d, x + cw / 2, y + ch / 2)
    cell(d, x + cw, y, cw, ch, "0.05", fnt(ARIAL, 30))
    leader(d, x + cw / 2, y + ch, 350, 420)
    d.line((200, 420, 600, 420), fill=BLACK, width=2)
    return img, {
        "title": "平面度公差框格",
        "callouts": ["0.05"],
        "facts": {"gdt_type": "平面度", "tolerance_mm": 0.05, "datums": []},
    }


def img_gdt_concentricity():
    img, d = canvas()
    border(d)
    x, y, cw, ch = 200, 240, 90, 60
    d.rectangle((x, y, x + cw, y + ch), outline=BLACK, width=2)
    sym_concentricity(d, x + cw / 2, y + ch / 2)
    cell(d, x + cw, y, cw, ch, "Ø0.1", fnt(ARIAL, 28))
    cell(d, x + 2 * cw, y, cw, ch, "A", fnt(ARIAL, 28))
    leader(d, x + cw / 2, y + ch, 300, 420)
    d.text((305, 405), "基准A", font=fnt(SIMHEI, 24), fill=BLACK)
    return img, {
        "title": "同轴度公差框格",
        "callouts": ["Ø0.1", "A"],
        "facts": {"gdt_type": "同轴度", "tolerance_mm": 0.1, "datum": "A"},
    }


def img_roughness():
    img, d = canvas()
    border(d)
    # surface-texture symbol: check-like two strokes on a bar
    d.line((380, 400, 440, 300), fill=BLACK, width=3)
    d.line((440, 300, 470, 340), fill=BLACK, width=3)
    d.line((330, 400, 570, 400), fill=BLACK, width=3)
    d.text((380, 220), "Ra 1.6", font=fnt(ARIAL, 42), fill=BLACK)
    d.text((330, 440), "表面粗糙度符号（其余面 Ra 6.3）", font=fnt(SIMHEI, 22), fill=BLACK)
    return img, {
        "title": "表面粗糙度符号",
        "callouts": ["Ra 1.6", "Ra 6.3"],
        "facts": {"primary_ra_um": 1.6, "remaining_ra_um": 6.3},
    }


def img_stepped_shaft():
    img, d = canvas()
    border(d)
    cy = 310
    # flange Ø40 x 12 wide, shaft Ø25, overall length 50 (scaled 6 px/mm)
    fl_x0, fl_x1 = 180, 252
    sh_x1 = 480
    fh, sh = 120, 75  # half heights
    d.rectangle((fl_x0, cy - fh, fl_x1, cy + fh), outline=BLACK, width=2)
    d.rectangle((fl_x1, cy - sh, sh_x1, cy + sh), outline=BLACK, width=2)
    # groove on shaft near flange, width 8 mm -> 48 px
    gx0, gx1 = 300, 348
    d.line((gx0, cy - sh, gx0, cy - sh + 20), fill=BLACK, width=2)
    d.line((gx1, cy - sh, gx1, cy - sh + 20), fill=BLACK, width=2)
    # dimension: overall length 50 below
    dy = cy + fh + 60
    d.line((fl_x0, dy, sh_x1, dy), fill=BLACK, width=2)
    d.text((300, dy + 8), "50", font=fnt(ARIAL, 30), fill=BLACK)
    # Ø40 left
    d.line((fl_x0 - 40, cy - fh, fl_x0 - 40, cy + fh), fill=BLACK, width=2)
    d.text((fl_x0 - 110, cy - 18), "Ø40", font=fnt(ARIAL, 30), fill=BLACK)
    # Ø25 right
    d.line((sh_x1 + 30, cy - sh, sh_x1 + 30, cy + sh), fill=BLACK, width=2)
    d.text((sh_x1 + 42, cy - 18), "Ø25", font=fnt(ARIAL, 30), fill=BLACK)
    # groove width 8 above
    d.line((gx0, cy - sh - 40, gx1, cy - sh - 40), fill=BLACK, width=2)
    d.text((306, cy - sh - 75), "8", font=fnt(ARIAL, 28), fill=BLACK)
    d.text((180, 520), "阶梯轴（退刀槽）  单位 mm", font=fnt(SIMHEI, 24), fill=BLACK)
    return img, {
        "title": "阶梯轴轮廓与尺寸",
        "callouts": ["Ø40", "Ø25", "50", "8"],
        "facts": {
            "flange_dia_mm": 40,
            "shaft_dia_mm": 25,
            "overall_length_mm": 50,
            "groove_width_mm": 8,
        },
    }


def img_title_block():
    img, d = canvas()
    border(d)
    f_cjk, f_lat = fnt(SIMHEI, 26), fnt(ARIAL, 26)
    x0, y0, cw, ch = 150, 150, 600, 70
    rows = [
        ("零件名称", "法兰盘", f_cjk),
        ("图号", "DWG-2026-118", f_lat),
        ("材料", "45钢", f_cjk),
        ("数量", "120", f_lat),
        ("日期", "2026-10-31", f_lat),
    ]
    d.text((x0, y0 - 60), "标题栏", font=fnt(SIMHEI, 30), fill=BLACK)
    for i, (k, v, f_) in enumerate(rows):
        y = y0 + i * ch
        d.rectangle((x0, y, x0 + 180, y + ch), outline=BLACK, width=2)
        d.rectangle((x0 + 180, y, x0 + cw, y + ch), outline=BLACK, width=2)
        d.text((x0 + 30, y + 20), k, font=f_cjk, fill=BLACK)
        d.text((x0 + 210, y + 20), v, font=f_, fill=BLACK)
    return img, {
        "title": "标题栏",
        "callouts": ["法兰盘", "DWG-2026-118", "45钢", "120", "2026-10-31"],
        "facts": {"part_name": "法兰盘", "drawing_no": "DWG-2026-118", "material": "45钢", "quantity": 120, "date": "2026-10-31"},
    }


def img_bolt_circle():
    img, d = canvas()
    border(d)
    cx, cy, r = 420, 310, 150  # BCD Ø64 scaled
    # dashed pitch circle
    for a in range(0, 360, 6):
        x1 = cx + r * math.cos(math.radians(a))
        y1 = cy + r * math.sin(math.radians(a))
        x2 = cx + r * math.cos(math.radians(a + 3))
        y2 = cy + r * math.sin(math.radians(a + 3))
        d.line((x1, y1, x2, y2), fill=BLACK, width=2)
    for k in range(6):
        ang = math.radians(k * 60)
        hx, hy = cx + r * math.cos(ang), cy + r * math.sin(ang)
        d.ellipse((hx - 18, hy - 18, hx + 18, hy + 18), outline=BLACK, width=2)
    d.text((150, 80), "6×Ø9 均布", font=fnt(ARIAL, 40), fill=BLACK)
    d.text((150, 500), "分布圆 Ø64", font=fnt(ARIAL, 34), fill=BLACK)
    return img, {
        "title": "螺栓孔分布圆",
        "callouts": ["6×Ø9", "Ø64"],
        "facts": {"hole_count": 6, "hole_dia_mm": 9, "bolt_circle_dia_mm": 64, "pattern": "均布"},
    }


def img_cutting_table():
    img, d = canvas()
    border(d)
    headers = ["刀具号", "主轴转速 r/min", "每齿进给 mm/z", "齿数"]
    values = ["T0202", "800", "0.10", "4"]
    x0, y0, cw, ch = 100, 180, 700, 80
    colw = [150, 200, 200, 150]
    d.text((x0, y0 - 80), "切削参数表", font=fnt(SIMHEI, 32), fill=BLACK)
    x = x0
    for i, h in enumerate(headers):
        d.rectangle((x, y0, x + colw[i], y0 + ch), outline=BLACK, width=2)
        d.text((x + 12, y0 + 24), h, font=fnt(SIMHEI, 20), fill=BLACK)
        x += colw[i]
    x = x0
    for i, v in enumerate(values):
        d.rectangle((x, y0 + ch, x + colw[i], y0 + 2 * ch), outline=BLACK, width=2)
        d.text((x + colw[i] / 2 - 30, y0 + ch + 24), v, font=fnt(ARIAL, 26), fill=BLACK)
        x += colw[i]
    d.text((x0, y0 + 2 * ch + 30), "进给速度 F 未填，需自行计算", font=fnt(SIMHEI, 22), fill=BLACK)
    return img, {
        "title": "切削参数表",
        "callouts": ["T0202", "800", "0.10", "4"],
        "facts": {"tool_no": "T0202", "spindle_rpm": 800, "feed_per_tooth_mm": 0.10, "teeth": 4, "feed_rate": "未给出(=0.10*4*800=320 mm/min)"},
    }


def img_rotated_thread():
    img, d = canvas()
    border(d)
    d.text((180, 100), "标注文字相对图纸旋转了90度（逆时针）", font=fnt(SIMHEI, 24), fill=BLACK)
    txt = Image.new("RGB", (360, 90), WHITE)
    td = ImageDraw.Draw(txt)
    td.text((10, 10), "M12×1.75", font=fnt(ARIAL, 54), fill=BLACK)
    txt = txt.rotate(90, expand=True, fillcolor=WHITE)
    img.paste(txt, (520, 180))
    return img, {
        "title": "旋转90度的螺纹标注",
        "callouts": ["M12×1.75"],
        "facts": {"thread": "M12", "pitch_mm": 1.75, "rotation_deg": 90},
    }


def img_lowcontrast_small():
    bg, fg = (205, 205, 205), (150, 150, 150)
    img, d = canvas(bg=bg)
    d.rectangle((10, 10, 890, 610), outline=fg, width=2)
    d.text((350, 290), "12.7±0.05", font=fnt(COURIER, 20), fill=fg)
    d.text((300, 240), "低对比度小字体标注", font=fnt(SIMHEI, 16), fill=fg)
    return img, {
        "title": "低对比度小字线性尺寸",
        "callouts": ["12.7±0.05"],
        "facts": {"nominal_mm": 12.7, "deviation_mm": 0.05},
        "difficulty": "低对比(205/150灰阶)+小号Courier字体(20px)",
    }


def img_noisy_code():
    img, d = canvas()
    d.text((320, 260), "Ø20H7", font=fnt(ARIAL, 56), fill=BLACK)
    rng = random.Random(7)
    px = img.load()
    for _ in range(6000):
        x, y = rng.randrange(12, 888), rng.randrange(12, 608)
        px[x, y] = (rng.choice((0, 90, 160, 200, 255)),) * 3
    img = img.filter(ImageFilter.GaussianBlur(0.8))
    return img, {
        "title": "噪点/压缩退化孔径标注",
        "callouts": ["Ø20H7"],
        "facts": {"nominal_diameter_mm": 20, "tolerance_class": "H7", "class_type": "孔公差带"},
        "difficulty": "椒盐噪点6000px(seed=7)+高斯模糊0.8",
    }


def img_ambiguous_illegible():
    img, d = canvas()
    d.text((300, 250), "Ø", font=fnt(ARIAL, 90), fill=BLACK)
    d.text((330, 260), "25", font=fnt(ARIAL, 70), fill=(120, 120, 120))
    d.text((360, 240), "H8", font=fnt(ARIAL, 60), fill=(80, 80, 80))
    rng = random.Random(13)
    for _ in range(60):
        x1, y1 = rng.randrange(60, 840), rng.randrange(60, 560)
        x2, y2 = rng.randrange(60, 840), rng.randrange(60, 560)
        d.line((x1, y1, x2, y2), fill=BLACK, width=rng.choice((1, 2, 3)))
    img = img.filter(ImageFilter.GaussianBlur(7))
    return img, {
        "title": "故意不可辨认的标注",
        "callouts": [],
        "facts": {"readable": False},
        "expected_behaviour": "文字重叠+重度模糊+划线干扰，不存在可读真值；正确行为是声明无法辨认（拒绝臆造数值）",
    }


def img_ambiguous_no_datum():
    img, d = canvas()
    border(d)
    x, y, cw, ch = 180, 250, 90, 60
    d.rectangle((x, y, x + cw, y + ch), outline=BLACK, width=2)
    sym_position(d, x + cw / 2, y + ch / 2, r=16)
    cell(d, x + cw, y, cw, ch, "Ø0.3", fnt(ARIAL, 28))
    # two intentionally EMPTY datum cells (frame border only)
    cell(d, x + 2 * cw, y, cw, ch)
    cell(d, x + 3 * cw, y, cw, ch)
    leader(d, x + cw / 2, y + ch, 350, 430)
    d.text((180, 120), "形位公差框格（后两格空白）", font=fnt(SIMHEI, 24), fill=BLACK)
    return img, {
        "title": "缺基准的位置度框格",
        "callouts": ["Ø0.3"],
        "facts": {"gdt_type": "位置度", "tolerance_mm": 0.3, "datums": []},
        "expected_behaviour": "基准格为空，无法确定基准体系；正确行为是声明基准缺失/歧义，不得臆造基准A/B/C",
    }


BUILDERS = [
    ("dim_diameter.png", img_dim_diameter),
    ("dim_tolerance.png", img_dim_tolerance),
    ("dim_radius.png", img_dim_radius),
    ("thread_m8.png", img_thread),
    ("gdt_position.png", img_gdt_position),
    ("gdt_flatness.png", img_gdt_flatness),
    ("gdt_concentricity.png", img_gdt_concentricity),
    ("surface_roughness.png", img_roughness),
    ("stepped_shaft.png", img_stepped_shaft),
    ("title_block.png", img_title_block),
    ("bolt_circle.png", img_bolt_circle),
    ("cutting_table.png", img_cutting_table),
    ("rotated_thread.png", img_rotated_thread),
    ("lowcontrast_small.png", img_lowcontrast_small),
    ("noisy_code.png", img_noisy_code),
    ("ambiguous_illegible.png", img_ambiguous_illegible),
    ("ambiguous_no_datum.png", img_ambiguous_no_datum),
]


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    gt = {}
    for fname, builder in BUILDERS:
        img, meta = builder()
        path = os.path.join(OUT_DIR, fname)
        img.save(path, format="PNG")
        # self-verification: re-open and sanity-check the written file
        with Image.open(path) as chk:
            chk.verify()
        re_img = Image.open(path)
        assert re_img.size[0] > 100 and re_img.size[1] > 100, f"{fname} too small"
        size = os.path.getsize(path)
        assert size > 1000, f"{fname} suspiciously small ({size} bytes)"
        gt[fname] = meta
        print(f"  wrote {fname:28s} {re_img.size[0]}x{re_img.size[1]} {size} bytes")
    gt_path = os.path.join(OUT_DIR, "ground_truth.json")
    with open(gt_path, "w", encoding="utf-8") as f:
        json.dump(gt, f, ensure_ascii=False, indent=2, sort_keys=True)
    print(f"ground_truth.json: {len(gt)} images -> {gt_path}")


if __name__ == "__main__":
    main()
