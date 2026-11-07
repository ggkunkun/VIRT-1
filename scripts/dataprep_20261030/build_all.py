# -*- coding: utf-8 -*-
"""
Virtu 数据集构建 · 主流程
================================
把 D:\\新图纸\\图纸(2) 与 D:\\新图纸\\图纸(3) 处理成高质量训练数据，
输出到 E:\\数据，并同步更新 DATASET_MANIFEST.json / README.md /
00_UNIFIED_MASTER_TRAIN。

用法：
    python build_all.py                # 全量构建
    python build_all.py --dry-run      # 只抽取不落盘
"""
from __future__ import annotations

import os
import sys
import glob
import json
import re
import shutil
import argparse
import datetime
import collections

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import extractors as X
import sft_gen as S

SRC2 = r"D:\新图纸\图纸(2)"
SRC3 = r"D:\新图纸\图纸(3)"
OUT = r"E:\数据"

M10 = "10_NX_CAD_MODELS_AND_ASSEMBLIES"
M11 = "11_CNC_DRAWINGS_AND_PROCESS_PLANNING"
M12 = "12_WORLD_SKILLS_ASSESSMENT_AND_TASKS"
M13 = "13_MULTIMODAL_CAD_ASSETS"

DATE = datetime.date.today().isoformat()


def log(*a):
    print(*a, flush=True)


def section(t):
    log("")
    log("=" * 78)
    log(t)
    log("=" * 78)


# ==========================================================================
# Stage 1 — NX 模型
# ==========================================================================

def build_nx_models(dry=False):
    section("STAGE 1 · NX .prt 模型解析")
    out_dir = os.path.join(OUT, M10)
    prev_dir = os.path.join(out_dir, "assets", "previews")
    prts = sorted(glob.glob(os.path.join(SRC2, "*.prt")))
    records, sft_model, sft_assy = [], [], []

    for p in prts:
        try:
            m = X.parse_nx_prt(p, "图纸(2)",
                               preview_dir=None if dry else prev_dir)
        except Exception as exc:
            log(f"  [FAIL] {os.path.basename(p)}: {exc}")
            continue
        d = m.to_dict()
        records.append(d)
        try:
            sft_model.append(S.gen_nx_model_understanding(d))
            if d["is_assembly"] and d["component_count"]:
                sft_assy.append(S.gen_nx_assembly(d))
        except Exception as exc:
            log(f"  [SFT FAIL] {d['filename']}: {exc}")

    parts = [r for r in records if not r["is_assembly"]]
    assys = [r for r in records if r["is_assembly"]]
    log(f"  模型总数 {len(records)}（零件 {len(parts)} / 装配体 {len(assys)}）")
    log(f"  含内嵌预览图 {sum(1 for r in records if r['has_embedded_preview'])} 张")
    log(f"  含 Parasolid 实体 {sum(1 for r in records if r['has_parasolid_geometry'])} 个")
    log(f"  SFT：模型理解 {len(sft_model)} 条 / 装配结构 {len(sft_assy)} 条")

    if not dry:
        os.makedirs(out_dir, exist_ok=True)
        X.write_jsonl(os.path.join(out_dir, "nx_models_index.jsonl"), records)
        X.write_jsonl(os.path.join(out_dir, "nx_model_understanding_sft.jsonl"), sft_model)
        X.write_jsonl(os.path.join(out_dir, "nx_assembly_structure_sft.jsonl"), sft_assy)
        # 部件级 BOM 反查表
        bom = collections.defaultdict(list)
        for r in assys:
            for c in r["component_parts"]:
                bom[c].append(r["filename"])
        X.write_json(os.path.join(out_dir, "nx_assembly_bom_index.json"), {
            "description": "装配体→组件引用反查表（由 .prt 内部组件引用记录构建）",
            "assembly_count": len(assys),
            "component_usage": {k: sorted(set(v)) for k, v in sorted(bom.items())},
        })
    return {"records": records, "sft_model": sft_model, "sft_assy": sft_assy}


# ==========================================================================
# Stage 2 — 工程图
# ==========================================================================

# 中文教学图样（带标题栏/技术要求/参数表）
CN_TRAINING = [
    ("6ae32f2aaf59f02dfd231957_CIMCO-钻铣复合练习件-CE-M02", "CE-M02", "CIMCO Edit 8"),
    ("6ae32f2aaf59f02dfd231957_UG-车削轴练习件-UG-T03", "UG-T03", "UG NX 12 车削编程"),
    ("6ae32f2aaf59f02dfd231957_VERICUT-三轴铣削练习件-VC-M01", "VC-M01", "VERICUT 9.x"),
]
# 英文练习图（多视图 + 3D 渲染）
EN_PRACTICE = [f"CAD-CAM-RENDER-3D-Practice-Drawing-{n}" for n in
               (221, 222, 224, 226, 229, 230, 232)]
# 纯矢量工程图（无文字层）
VECTOR_ONLY = [
    "Ethan_control_block_dwg1", "Ethan_GP_assembly_dwg1", "Ethan_ILA-09_dwg1",
    "Ethan_ILA-12_dwg1", "Ethan_latch_handle_a_dwg1", "Ethan_link_arm_dwg1",
    "Ethan_prop_shaft_dwg1", "Ethan_tri_cap_assy_dwg1",
]


def build_drawings(dry=False):
    section("STAGE 2 · 二维工程图解析（PDF / SVG）")
    out_dir = os.path.join(OUT, M11)
    asset_dir = os.path.join(out_dir, "assets")
    records, sft_read, sft_proc, sft_tree = [], [], [], []

    pdfs = sorted(glob.glob(os.path.join(SRC2, "*.pdf")))
    for p in pdfs:
        base = os.path.splitext(os.path.basename(p))[0]
        try:
            a = X.analyze_drawing_pdf(p)
        except Exception as exc:
            log(f"  [FAIL] {base}: {exc}")
            continue
        a["source_file"] = os.path.basename(p)
        a["source_dir"] = "图纸(2)"
        a["sha256"] = X.sha256_file(p)
        a["size_bytes"] = os.path.getsize(p)
        # 分类
        stem = base
        if any(stem.startswith(c) for c, _, _ in CN_TRAINING):
            a["drawing_class"] = "cn_cnc_training"
            a["cnc_platform"] = next(p_ for c, _, p_ in CN_TRAINING if stem.startswith(c))
        elif any(stem.startswith(c) for c in EN_PRACTICE):
            a["drawing_class"] = "en_multiview_practice"
        elif any(stem.startswith(c) for c in VECTOR_ONLY):
            a["drawing_class"] = "vector_only_cad"
        else:
            a["drawing_class"] = "other"
        if stem.startswith("a924b8632c50ff45"):
            a["drawing_class"] = "raster_only"
        # 图号 / 图题
        m = re.search(r"PRACTICE\s*DRAWING\s*[-–]\s*(\d+)", a["full_text"], re.I)
        if m:
            a["drawing_title"] = f"PRACTICE DRAWING - {m.group(1)}"
        m = re.search(r"(\d+)\s*THRU\s*ALL", a["full_text"], re.I)
        # 矢量统计（首页）
        if a["pages"]:
            a["vector_stats"] = a["pages"][0]["vector_stats"]
        records.append(a)

        # 渲染为 PNG 资产
        if not dry:
            try:
                r = X.render_pdf_page(p, os.path.join(asset_dir, base + ".png"), dpi=150)
                a["rendered_assets"] = r["rendered"]
            except Exception as exc:
                a["rendered_assets"] = []
                log(f"  [RENDER FAIL] {base}: {exc}")

        try:
            if a["drawing_class"] in ("cn_cnc_training", "en_multiview_practice"):
                sft_read.append(S.gen_drawing_reading(a))
            if a["drawing_class"] in ("cn_cnc_training", "en_multiview_practice"):
                sft_tree.append(S.gen_feature_tree(a))
            if a["drawing_class"] == "cn_cnc_training":
                sft_proc.append(S.gen_process_plan(a))
        except Exception as exc:
            log(f"  [SFT FAIL] {base}: {exc}")

    # SVG 矢量母版
    svg_records = []
    for p in sorted(glob.glob(os.path.join(SRC2, "*.svg"))):
        base = os.path.splitext(os.path.basename(p))[0]
        try:
            import pymupdf
            doc = pymupdf.open(p)
            pg = doc[0]
            ws = X.page_words(pg)
            regions = X.locate_regions(pg, ws)
            rec = {
                "source_file": os.path.basename(p),
                "source_dir": "图纸(2)",
                "sha256": X.sha256_file(p),
                "size_bytes": os.path.getsize(p),
                "drawing_class": "cn_cnc_training_svg_master",
                "sheet_size_pt": [round(pg.rect.width, 2), round(pg.rect.height, 2)],
                "title_block": X.extract_title_block(pg, ws),
                "tech_requirements": X.extract_tech_requirements(pg, ws),
                "param_table": X.extract_param_table(pg, ws),
                "dimension_callouts": X.extract_dimension_callouts(pg, ws, regions),
                "vector_stats": X.analyze_vector_page(pg),
                "view_labels": sorted(set(regions.get("view_labels", []))),
                "word_count": len(ws),
            }
            doc.close()
            svg_records.append(rec)
            if not dry:
                X.render_svg(p, os.path.join(asset_dir, base + ".png"), dpi=150)
        except Exception as exc:
            log(f"  [FAIL SVG] {base}: {exc}")

    log(f"  PDF 图纸 {len(records)} 张；SVG 母版 {len(svg_records)} 个")
    log(f"  SFT：识读 {len(sft_read)} 条 / 特征树 {len(sft_tree)} 条 / "
        f"工艺规划 {len(sft_proc)} 条")

    if not dry:
        X.write_jsonl(os.path.join(out_dir, "cnc_drawings_index.jsonl"), records)
        X.write_jsonl(os.path.join(out_dir, "cnc_drawings_svg_master_index.jsonl"),
                      svg_records)
        X.write_jsonl(os.path.join(out_dir, "drawing_reading_sft.jsonl"), sft_read)
        X.write_jsonl(os.path.join(out_dir, "drawing_to_feature_tree_sft.jsonl"),
                      sft_tree)
        X.write_jsonl(os.path.join(out_dir, "machining_process_planning_sft.jsonl"),
                      sft_proc)
        # 尺寸特征清单（汇总所有图纸的标注类型）
        checklist = collections.defaultdict(list)
        for r in records + svg_records:
            for d in r.get("dimension_callouts", []):
                checklist[d["type"]].append({
                    "drawing": r["source_file"],
                    "text": d["text"], "qty": d.get("qty"),
                })
        X.write_json(os.path.join(out_dir, "drawing_dimension_taxonomy.json"), {
            "description": "全部新图纸的标注类型统计与实例（供标注规范/校验规则使用）",
            "by_type": {k: {"count": len(v), "examples": v[:30]}
                        for k, v in sorted(checklist.items())},
        })
    return {"records": records, "svg": svg_records,
            "sft_read": sft_read, "sft_tree": sft_tree, "sft_proc": sft_proc}


# ==========================================================================
# Stage 3 — 世赛资料
# ==========================================================================

def build_worldskills(dry=False):
    section("STAGE 3 · WorldSkills 2013 评分标准与赛题")
    out_dir = os.path.join(OUT, M12)
    asset_dir = os.path.join(out_dir, "assets")
    schemes, sft, papers = [], [], []

    # --- 3.1 xlsx 评分总表 ---
    for x in sorted(glob.glob(os.path.join(SRC3, "**", "*_marking_scheme.xlsx"),
                              recursive=True)):
        s = X.parse_marking_scheme_xlsx(x)
        s["source_path"] = os.path.abspath(x)
        s["sha256"] = X.sha256_file(x)
        schemes.append(s)
        skill = s["skill_name"]
        skill_id = "MS05" if "CAD" in skill else ("MS06" if "Turning" in skill else "MS")
        q = (f"请说明 WorldSkills Leipzig 2013 {skill} 技能的评分标准结构："
             f"有哪些顶层评分模块、各模块满分多少、下设哪些子标准？")
        aspects = []
        sft.append(S.gen_wsc_qa({"skill_id": skill_id, "topic": "criteria",
                                 "scheme": s, "aspects": [], "question": q,
                                 "source_file": os.path.basename(x)}))

    # --- 3.2 OMF/SMF 官方评分表 ---
    form_summary = []
    for f in sorted(glob.glob(os.path.join(SRC3, "**", "*.pdf"), recursive=True)):
        if "Marking_Forms" not in f:
            continue
        base = os.path.basename(f)
        try:
            mf = X.parse_marking_form_pdf(f)
        except Exception as exc:
            log(f"  [FAIL] {base}: {exc}")
            continue
        mf["source_path"] = os.path.abspath(f)
        mf["sha256"] = X.sha256_file(f)
        mf["size_bytes"] = os.path.getsize(f)
        form_summary.append(mf)
        skill_id = "MS05" if "MS05" in base else "MS06"
        # 同一子标准在 OMF / SMF 中都会出现 → 必须在 id 中带上表单种类，否则 id 冲突
        form_kind = ("OMF" if "OMF" in base.upper() else
                     "SMF" if "SMF" in base.upper() else
                     "MSF" if "MSF" in base.upper() else "FORM")
        skill = next((s["skill_name"] for s in schemes
                      if (s["skill_name"] and
                          (("CAD" in s["skill_name"] and skill_id == "MS05") or
                           ("Turning" in s["skill_name"] and skill_id == "MS06")))), "")
        for sc in mf.get("sub_criteria", []):
            aspects = [a for a in mf["aspect_rows"]
                       if a.get("sub_criterion_id") == sc["sub_criterion_id"]]
            if not aspects:
                continue
            q = (f"WorldSkills 2013 {skill} 技能中，子标准 {sc['sub_criterion_id']}"
                 f"（{sc['sub_criterion_name']}）具体按哪些 Aspect 判分？"
                 f"每项分值与尺寸/名义要求是什么？")
            sft.append(S.gen_wsc_qa({
                "skill_id": skill_id,
                "topic": f"{sc['sub_criterion_id'].lower()}_{form_kind}",
                "scheme": {"skill_name": skill, "criteria": [], "sub_criteria": [],
                           "criteria_total_mark": None},
                "aspects": aspects,
                "question": q,
                "source_file": base,
            }))
        if not dry:
            try:
                X.render_pdf_page(f, os.path.join(asset_dir, base + ".png"), dpi=150)
            except Exception:
                pass

    # --- 3.3 实际赛题图纸 ---
    for f in sorted(glob.glob(os.path.join(SRC3, "**", "*_actual.pdf"),
                              recursive=True)):
        base = os.path.basename(f)
        try:
            info = X.read_pdf_text(f)
        except Exception as exc:
            log(f"  [FAIL] {base}: {exc}")
            continue
        import pymupdf
        doc = pymupdf.open(f)
        vstats = []
        for pg in doc:
            vstats.append(X.analyze_vector_page(pg))
        doc.close()
        rec = {
            "source_file": base,
            "source_path": os.path.abspath(f),
            "sha256": X.sha256_file(f),
            "size_bytes": os.path.getsize(f),
            "page_count": info["page_count"],
            "text_chars": len(info["full_text"]),
            "vector_paths": info["total_vector_paths"],
            "images": info["total_images"],
            "vector_stats": vstats,
            "text_excerpt": " ".join(info["full_text"].split())[:600],
            "task_class": "worldskills_task_paper",
        }
        papers.append(rec)
        if not dry:
            try:
                X.render_pdf_page(f, os.path.join(asset_dir, base + ".png"), dpi=150)
            except Exception:
                pass

    log(f"  评分总表 {len(schemes)} 份；官方评分表 {len(form_summary)} 份；"
        f"实际赛题 {len(papers)} 份")
    log(f"  SFT：评分标准问答 {len(sft)} 条")

    if not dry:
        X.write_json(os.path.join(out_dir, "wsc2013_marking_schemes.json"), {
            "description": "WorldSkills Leipzig 2013 评分总表（xlsx 解析结果）",
            "schemes": schemes,
        })
        X.write_json(os.path.join(out_dir, "wsc2013_official_marking_forms.json"), {
            "description": "官方 OMF/SMF 评分表解析结果（子标准 + Aspect + 分值）",
            "forms": [{k: v for k, v in m.items() if k != "pages"} |
                      {"pages": m["pages"]} for m in form_summary],
        })
        X.write_jsonl(os.path.join(out_dir, "wsc2013_task_papers_index.jsonl"), papers)
        X.write_jsonl(os.path.join(out_dir, "wsc2013_assessment_qa_sft.jsonl"), sft)
    return {"schemes": schemes, "forms": form_summary, "papers": papers, "sft": sft}


# ==========================================================================
# Stage 4 — 多模态资产
# ==========================================================================

def _classify_asset(fn: str) -> str:
    low = fn.lower()
    if "wireframe" in low:
        return "cad_wireframe"
    if "drawing" in low or "sheet" in low:
        return "drawing_sheet"
    if "aigc_label" in low:
        return "aigc_label"
    if low.endswith(".jpg"):
        return "photo_reference"
    if "poster" in low:
        return "poster"
    return "cad_render"


def build_multimodal(dry=False):
    section("STAGE 4 · 多模态图像资产")
    out_dir = os.path.join(OUT, M13)
    asset_dir = os.path.join(out_dir, "assets")
    records, sft = [], []
    seen: dict[str, str] = {}
    seen_rel: dict[str, str] = {}

    srcs = []
    for root, label in ((SRC2, "图纸(2)"), (SRC3, "图纸(3)")):
        for ext in ("*.png", "*.jpg", "*.jpeg"):
            srcs += [(p, label) for p in sorted(glob.glob(os.path.join(root, "**", ext),
                                                          recursive=True))]

    for p, label in srcs:
        fn = os.path.basename(p)
        digest = X.sha256_file(p)
        try:
            st = X.image_stats(p)
        except Exception as exc:
            log(f"  [FAIL IMG] {fn}: {exc}")
            continue
        ext = os.path.splitext(fn)[1].lower()
        safe = os.path.splitext(fn)[0].replace(" ", "_")
        rel = os.path.join("assets", f"{safe}{ext}")
        dup = seen.get(digest)
        if dup:
            # 重复文件：relative_path 指向已入库的原件，保证索引里每条都能解析到实体文件
            rel = seen_rel[digest]
        rec = {
            "id": f"asset_{len(records):04d}",
            "filename": fn,
            "source_dir": label,
            "source_path": os.path.abspath(p),
            "sha256": digest,
            "size_bytes": os.path.getsize(p),
            "width": st["width"], "height": st["height"],
            "mode": st["mode"], "aspect_ratio": st["aspect_ratio"],
            "asset_class": _classify_asset(fn),
            "relative_path": rel,
            "duplicate_of": dup or "",
        }
        records.append(rec)
        if dup is None:
            seen[digest] = fn
            seen_rel[digest] = rel
            if not dry:
                os.makedirs(asset_dir, exist_ok=True)
                shutil.copy2(p, os.path.join(out_dir, rel))
            try:
                sft.append(S.gen_image_caption(rec))
            except Exception as exc:
                log(f"  [SFT FAIL IMG] {fn}: {exc}")
        # 重复文件不单独生成训练样本（避免重复采样导致过拟合）

    # .prt 内嵌预览图一并纳入多模态池
    prev_dir = os.path.join(asset_dir, "nx_prt_previews")
    n = 0
    for prt in sorted(glob.glob(os.path.join(SRC2, "*.prt"))):
        m = X.parse_nx_prt(prt, "图纸(2)", preview_dir=None if dry else prev_dir)
        if not m.has_embedded_preview:
            continue
        prev_path = os.path.join(prev_dir, f"{m.part_name}.jpg")
        pdigest = X.sha256_file(prev_path) if os.path.exists(prev_path) else ""
        rel = os.path.join("assets", "nx_prt_previews", f"{m.part_name}.jpg")
        dup = seen.get(pdigest) if pdigest else None
        rec = {
            "id": f"asset_nx_{n:03d}", "filename": f"{m.part_name}.jpg",
            "source_dir": "图纸(2)/.prt 内嵌预览",
            "source_path": os.path.abspath(prt),
            "sha256": pdigest, "size_bytes": m.size_bytes,
            "width": m.preview_size[0] if m.preview_size else 0,
            "height": m.preview_size[1] if m.preview_size else 0,
            "mode": "RGB",
            "aspect_ratio": round(m.preview_size[0] / m.preview_size[1], 4)
            if m.preview_size and m.preview_size[1] else None,
            "asset_class": "nx_prt_preview",
            "relative_path": rel, "duplicate_of": dup or "",
            "source_model": m.filename,
            "source_model_sha256": m.sha256,
        }
        records.append(rec)
        n += 1
        if pdigest and dup is None:
            seen[pdigest] = rec["filename"]
            seen_rel[pdigest] = rel
            try:
                sft.append(S.gen_image_caption(rec))
            except Exception:
                pass
        elif pdigest and dup is not None:
            rec["relative_path"] = seen_rel.get(pdigest, rel)

    uniq = len(seen)
    log(f"  图像资产 {len(records)} 个（唯一内容 {uniq}，重复 {len(records) - uniq}）")
    log(f"  SFT：图像描述 {len(sft)} 条")

    if not dry:
        X.write_jsonl(os.path.join(out_dir, "multimodal_cad_assets_index.jsonl"), records)
        X.write_jsonl(os.path.join(out_dir, "cad_image_caption_sft.jsonl"), sft)
        X.write_json(os.path.join(out_dir, "multimodal_assets_stats.json"), {
            "description": "多模态资产统计",
            "total": len(records),
            "unique_content": uniq,
            "duplicates": len(records) - uniq,
            "by_class": dict(collections.Counter(r["asset_class"] for r in records)),
            "by_source_dir": dict(collections.Counter(r["source_dir"] for r in records)),
        })
    return {"records": records, "sft": sft}


# ==========================================================================
# Stage 5 — 汇总 / 清单 / README
# ==========================================================================

def integrate(results, dry=False):
    section("STAGE 5 · 汇总训练集 / 更新清单与说明")
    new_sft = []
    for key in ("sft_model", "sft_assy"):
        new_sft += results["nx"][key]
    for key in ("sft_read", "sft_tree", "sft_proc"):
        new_sft += results["drawings"][key]
    new_sft += results["wsc"]["sft"]
    new_sft += results["multimodal"]["sft"]

    # 去重（同 id）
    seen_ids, uniq = set(), []
    for s in new_sft:
        if s["id"] in seen_ids:
            continue
        seen_ids.add(s["id"])
        uniq.append(s)
    log(f"  本次新增 SFT 样本：{len(new_sft)} 条（去重后 {len(uniq)} 条）")

    if dry:
        return uniq

    # --- 5.1 写入主训练集（按 id 去重，重复执行结果幂等）---
    master_path = os.path.join(OUT, "00_UNIFIED_MASTER_TRAIN",
                               "virtu_master_train_sft.jsonl")
    existing = []
    seen_master = set()
    if os.path.exists(master_path):
        with open(master_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                oid = obj.get("id")
                if oid and oid in seen_master:
                    continue           # 跳过重复 id（幂等）
                if oid:
                    seen_master.add(oid)
                existing.append(obj)
    added = [s for s in uniq if s.get("id") not in seen_master]
    log(f"  原有主训练集 {len(existing)} 条 → 新增 {len(added)} 条 "
        f"→ 合并后 {len(existing) + len(added)} 条")

    merged = existing + added
    tmp_master = master_path + ".tmp"
    with open(tmp_master, "w", encoding="utf-8", newline="\n") as f:
        for r in merged:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp_master, master_path)

    total_chars = sum(len(m.get("content", "")) for r in merged
                      for m in r.get("messages", []))
    est_tokens = int(total_chars / 2.1)
    log(f"  合并后总字符 {total_chars:,}，预估 tokens ~{est_tokens:,}")

    # --- 5.2 更新清单 ---
    mpath = os.path.join(OUT, "DATASET_MANIFEST.json")
    with open(mpath, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    st = manifest["statistics"]
    st["unified_master_samples"] = len(merged)
    st["total_characters"] = total_chars
    st["estimated_tokens"] = est_tokens
    st.setdefault("module_breakdown", {})
    st["module_breakdown"].update({
        M10: len(results["nx"]["sft_model"]) + len(results["nx"]["sft_assy"]),
        M11: len(results["drawings"]["sft_read"]) + len(results["drawings"]["sft_tree"])
        + len(results["drawings"]["sft_proc"]),
        M12: len(results["wsc"]["sft"]),
        M13: len(results["multimodal"]["sft"]),
    })
    st["nx_prt_models_parsed"] = len(results["nx"]["records"])
    st["nx_prt_assemblies"] = sum(1 for r in results["nx"]["records"] if r["is_assembly"])
    st["cnc_drawings_parsed"] = len(results["drawings"]["records"])
    st["cnc_svg_vector_masters"] = len(results["drawings"]["svg"])
    st["worldskills_forms"] = len(results["wsc"]["forms"])
    st["worldskills_task_papers"] = len(results["wsc"]["papers"])
    st["multimodal_assets"] = len(results["multimodal"]["records"])

    def mod(mid, desc, files):
        """更新/追加模块条目。兼容两种条目 schema：id/description/files 与
        module_id/name/description/total_files/... （共存，不破坏他方写入）。"""
        for m in manifest["data_modules"]:
            key = m.get("id") or m.get("module_id")
            if key == mid:
                m["description"] = desc
                m["files"] = files
                return
        manifest["data_modules"].append({"id": mid, "description": desc,
                                         "files": files})

    mod(M10, "UG NX .prt 模型的 Parasolid 内核、特征操作、属性表与装配 BOM 结构化解析",
        ["nx_models_index.jsonl", "nx_model_understanding_sft.jsonl",
         "nx_assembly_structure_sft.jsonl", "nx_assembly_bom_index.json",
         "assets/previews/"])
    mod(M11, "数控实训工程图（中文标题栏/技术要求/加工参数表）与英文多视图练习图的"
             "版面感知解析、尺寸提取、特征树重建与工艺规划",
        ["cnc_drawings_index.jsonl", "cnc_drawings_svg_master_index.jsonl",
         "drawing_reading_sft.jsonl", "drawing_to_feature_tree_sft.jsonl",
         "machining_process_planning_sft.jsonl",
         "drawing_dimension_taxonomy.json", "assets/"])
    mod(M12, "WorldSkills Leipzig 2013 机械设计 CAD 与数控车削技能的官方评分标准"
             "（Criteria/Sub Criteria/Aspect/分值）与实际赛题图纸索引",
        ["wsc2013_marking_schemes.json", "wsc2013_official_marking_forms.json",
         "wsc2013_task_papers_index.jsonl", "wsc2013_assessment_qa_sft.jsonl",
         "assets/"])
    mod(M13, "CAD 渲染/线框/工程图/世赛预览图资产库（含 SHA256 去重标记）与图像语义描述",
        ["multimodal_cad_assets_index.jsonl", "cad_image_caption_sft.jsonl",
         "multimodal_assets_stats.json", "assets/"])

    manifest["version"] = "1.2.0"
    manifest["last_updated"] = datetime.datetime.now().astimezone().isoformat(
        timespec="seconds")
    manifest.setdefault("changelog", []).append({
        "date": DATE,
        "version": "1.2.0",
        "change": "新增 D:\\新图纸\\图纸(2) 与 D:\\新图纸\\图纸(3) 加工成果："
                  f"{M10}（45 个 NX .prt 模型）、{M11}（19 张 PDF 图纸 + 3 个 SVG 母版）、"
                  f"{M12}（世赛 2013 评分标准与赛题）、{M13}（92 个图像资产）。"
                  f"本批新增 SFT {len(uniq)} 条，全部数值均溯源自源文件解析结果。",
    })
    # 原子写入，避免并发读取到半截文件
    tmp = mpath + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    os.replace(tmp, mpath)
    log(f"  清单已更新：{mpath}")

    # --- 5.3 README 增量更新（不破坏既有内容）---
    update_readme(manifest, uniq, total_chars, est_tokens)
    return uniq


README_MARK = "## 4. 模型微调训练快速启动"


def update_readme(manifest, uniq, total_chars, est_tokens):
    """增量更新 README：刷新统计行、插入模块树条目、追加本批次说明章节。"""
    rpath = os.path.join(OUT, "README.md")
    if not os.path.exists(rpath):
        return
    with open(rpath, "r", encoding="utf-8") as f:
        txt = f.read()

    # 1) 统计表刷新
    txt = re.sub(r"(\*\*微调数据总样本数 \(SFT Samples\)\*\*\s*\|\s*\*\*)\d+( 条\*\*\|)",
                 rf"\g<1>{manifest['statistics']['unified_master_samples']}\2", txt)
    txt = re.sub(r"(\*\*文本字符总量 \(Total Characters\)\*\*\s*\|\s*\*\*)[\d,]+( 字符\*\*)",
                 rf"\g<1>{total_chars:,}\2", txt)
    txt = re.sub(r"(\*\*预估 Token 规模 \(Estimated Tokens\)\*\*\s*\|\s*\*\*)~[\d,]+( Tokens\*\*)",
                 rf"\g<1>~{est_tokens:,}\2", txt)

    # 2) 目录树中补入新模块（插到 09 之后的闭合 ``` 之前）
    tree_block = """├── 10_NX_CAD_MODELS_AND_ASSEMBLIES/      # 【NX 数模理解】.prt 内核/特征/属性/BOM 结构化解析
│   ├── nx_models_index.jsonl            # 45 个 NX 模型事实记录 (Parasolid schema、特征操作、属性表)
│   ├── nx_model_understanding_sft.jsonl # 模型解析与操作建议问答
│   ├── nx_assembly_structure_sft.jsonl  # 装配体 BOM 归类与装配工艺分析
│   ├── nx_assembly_bom_index.json       # 装配体→组件引用反查表
│   └── assets/previews/                 # 45 张内嵌模型预览图 (从 .prt 中提取)
├── 11_CNC_DRAWINGS_AND_PROCESS_PLANNING/ # 【工程图与工艺】版面感知识图、特征树重建与工艺卡
│   ├── cnc_drawings_index.jsonl         # 19 张图纸版面解析 (标题栏/技术要求/加工参数表/尺寸)
│   ├── cnc_drawings_svg_master_index.jsonl # 3 个 SVG 矢量母版解析
│   ├── drawing_reading_sft.jsonl        # 图纸识读与尺寸分类汇总
│   ├── drawing_to_feature_tree_sft.jsonl# 二维图 → 三维参数化特征树重建时序
│   ├── machining_process_planning_sft.jsonl # 装夹/坐标系/工序/刀具/校验工艺卡
│   ├── drawing_dimension_taxonomy.json  # 标注类型统计与实例
│   └── assets/                          # 图纸 150dpi 渲染 PNG
├── 12_WORLD_SKILLS_ASSESSMENT_AND_TASKS/ # 【世赛考评】评分标准与实际赛题
│   ├── wsc2013_marking_schemes.json     # xlsx 评分总表 (Criteria/满分)
│   ├── wsc2013_official_marking_forms.json # 官方 OMF/SMF 评分表 (Sub Criteria/Aspect/分值)
│   ├── wsc2013_task_papers_index.jsonl  # 9 份实际赛题图纸索引
│   ├── wsc2013_assessment_qa_sft.jsonl  # 评分标准与判分要求问答
│   └── assets/                          # 官方评分表与赛题渲染 PNG
└── 13_MULTIMODAL_CAD_ASSETS/            # 【多模态资产】CAD 图像库与图文对齐
    ├── multimodal_cad_assets_index.jsonl# 92 个图像资产 (SHA256 去重与重复标记)
    ├── cad_image_caption_sft.jsonl      # 图像语义描述问答
    ├── multimodal_assets_stats.json     # 资产分类统计
    └── assets/                          # 图像资产 (含 .prt 内嵌预览图)
"""
    if "10_NX_CAD_MODELS_AND_ASSEMBLIES/" not in txt:
        # 找到目录树代码块的结束位置
        idx = txt.find("```", txt.find("e:\\数据\\"))
        end = txt.find("\n", idx)
        if end != -1:
            txt = txt[:end + 1] + tree_block + txt[end + 1:]

    # 3) 追加本批次章节
    st = manifest["statistics"]
    section_txt = f"""
---

## 5. 新图纸批次加工说明（D:\\新图纸\\图纸(2) 与 图纸(3)）

| 项目 | 数值 |
| :--- | :--- |
| NX .prt 模型解析 | {st.get('nx_prt_models_parsed', 0)} 个（零件 {st.get('nx_prt_models_parsed', 0) - st.get('nx_prt_assemblies', 0)} / 装配体 {st.get('nx_prt_assemblies', 0)}） |
| CNC 工程图解析 | {st.get('cnc_drawings_parsed', 0)} 张 PDF + {st.get('cnc_svg_vector_masters', 0)} 个 SVG 矢量母版 |
| 世赛资料解析 | {st.get('worldskills_forms', 0)} 份官方评分表 + {st.get('worldskills_task_papers', 0)} 份实际赛题 |
| 多模态图像资产 | {st.get('multimodal_assets', 0)} 个（含 SHA256 去重标记） |
| **本批新增 SFT 样本** | **{len(uniq)} 条** |

### 加工方法与质量约定

1. **NX .prt（Siemens PLM Structured Storage 容器）**：直接解析容器内的 Parasolid 内核 schema
   （`SCH=SCH_<id>_<ver>`）、建模操作名（EXTRUDE / HOLE PACKAGE / SIMPLE HOLE 等）、
   `UgAttributes` 属性表 XML、装配体组件引用记录，以及 `/Root/images/preview` 内嵌 JPEG 预览图。
2. **工程图 PDF / SVG**：采用**版面感知**解析——先取词级坐标，再按标题栏/技术要求/参数表的
   版面区域分离文本，用列坐标重建「加工参数表」，用标注符号语义分类尺寸
   （直径/半径/倒角/螺纹/带公差线性/深度/粗糙度/阵列系数）。
3. **世赛评分表**：xlsx 用 openpyxl 解析；官方 OMF/SMF 用行聚类 + Aspect-ID 形态锚定
   重建 `Aspect | Max Mark | Description | Requirement` 四列。
4. **多模态资产**：全部图片复制入库（数据集自包含，不依赖外部路径），
   按 SHA256 标记重复文件，重复件不重复生成训练样本以避免过拟合。

### 数据可信度约定（重要）

- **所有工程数值均溯源自源文件解析结果**，回答中出现的直径、转速、进给、公差、
  评分分值都可在对应模块的索引文件中逐条回查。
- **图纸未标注的要素一律显式写明「图面未标注，需回查三维模型」**，
  不以推测值填充（`grounded: true` 标记该批样本）。
- `.prt` 内嵌预览图为 NX 内部缩略图（247×185），仅用于形态判读，
  **不可用于尺寸量取**；精确尺寸需由随附工程图或三维模型提供。
"""
    if "## 5. 新图纸批次加工说明" not in txt:
        txt = txt.rstrip() + "\n" + section_txt
    else:
        # 已存在则只刷新本批样本数与各项统计，避免与实际值脱节
        txt = re.sub(r"(\*\*本批新增 SFT 样本\*\*\s*\|\s*\*\*)\d+( 条\*\*)",
                     rf"\g<1>{len(uniq)}\2", txt)
        txt = re.sub(r"(\| NX \.prt 模型解析 \| )\d+( 个)",
                     rf"\g<1>{st.get('nx_prt_models_parsed', 0)}\2", txt)
        txt = re.sub(r"(\| CNC 工程图解析 \| )\d+( 张)",
                     rf"\g<1>{st.get('cnc_drawings_parsed', 0)}\2", txt)
        txt = re.sub(r"(\| 世赛资料解析 \| )\d+( 份)",
                     rf"\g<1>{st.get('worldskills_forms', 0)}\2", txt)
        txt = re.sub(r"(\| 多模态图像资产 \| )\d+( 个)",
                     rf"\g<1>{st.get('multimodal_assets', 0)}\2", txt)

    tmp = rpath + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(txt)
    os.replace(tmp, rpath)
    log(f"  README 已增量更新：{rpath}")


# ==========================================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    log(f"Virtu 数据集构建 · {DATE}")
    log(f"源目录：{SRC2} / {SRC3}")
    log(f"输出目录：{OUT}")

    results = {
        "nx": build_nx_models(args.dry_run),
        "drawings": build_drawings(args.dry_run),
        "wsc": build_worldskills(args.dry_run),
        "multimodal": build_multimodal(args.dry_run),
    }
    new = integrate(results, args.dry_run)

    section("完成")
    log(f"本次新增 SFT 样本：{len(new)} 条")
    if not args.dry_run:
        log(f"主训练集：{os.path.join(OUT, '00_UNIFIED_MASTER_TRAIN', 'virtu_master_train_sft.jsonl')}")


if __name__ == "__main__":
    main()
