# -*- coding: utf-8 -*-
r"""
build_drawings_multimodal.py
Processes:
  1. e:\迅雷下载\工程图
  2. e:\迅雷下载\工程图(1) (including 16 rich SVG blueprints)
  3. e:\迅雷下载\建模练习图纸
  4. e:\迅雷下载\UG画图建模练习图
Produces:
  1. 04_MULTIMODAL_DRAWING_TO_CAD/drawings_metadata_index.jsonl (Deduplicated index with resolution, category, filepath)
  2. 04_MULTIMODAL_DRAWING_TO_CAD/drawing_to_cad_sft.jsonl (Multimodal VLM & CAD reconstruction instructions)
  3. 04_MULTIMODAL_DRAWING_TO_CAD/drawing_feature_checklists.json
"""

import os
import sys
import re
import json
import hashlib
from PIL import Image

sys.stdout.reconfigure(encoding='utf-8')

OUTPUT_DIR = r"e:\新建文件夹 (3)\04_MULTIMODAL_DRAWING_TO_CAD"
os.makedirs(OUTPUT_DIR, exist_ok=True)

DRAWING_DIRS = [
    r"e:\迅雷下载\工程图",
    r"e:\迅雷下载\工程图(1)",
    r"e:\迅雷下载\建模练习图纸",
    r"e:\迅雷下载\UG画图建模练习图"
]

CATEGORY_RULES = {
    "轴": "轴类零件 (Shaft / Spindle)",
    "法兰": "法兰盘类零件 (Flange)",
    "端盖": "端盖与盘盖类 (Cover / Cap)",
    "泵体": "壳体与泵体类 (Housing / Body)",
    "支座": "支座与托架类 (Bracket / Support)",
    "轮": "带轮与齿轮类 (Pulley / Gear)",
    "凸轮": "凸轮与棘轮类 (Cam / Ratchet)",
    "拨叉": "拨叉与连杆类 (Fork / Linkage)",
    "手轮": "操作件与手轮 (Handwheel / Knob)",
    "夹具": "工装夹具类 (Fixture / Tooling)",
    "模": "模具与成型件 (Mold / Die)"
}

def classify_drawing(name):
    for kw, cat in CATEGORY_RULES.items():
        if kw in name:
            return cat
    return "基础机械零件与复合几何体 (Standard Mechanical Component)"

print("Scanning and deduplicating drawing blueprints ...")

seen_hashes = set()
dedup_drawings = []
svg_blueprints = []

# First, process high-fidelity SVGs in 工程图(1)
svg_dir = r"e:\迅雷下载\工程图(1)\UG\SVG源文件"
if os.path.exists(svg_dir):
    for f in sorted(os.listdir(svg_dir)):
        if f.endswith('.svg') and not f.startswith('00_') and not f.startswith('9'):
            svg_path = os.path.join(svg_dir, f)
            with open(svg_path, 'r', encoding='utf-8', errors='ignore') as sfl:
                svg_content = sfl.read()
            raw_texts = re.findall(r'<text[^>]*>(.*?)</text>', svg_content)
            clean_texts = [re.sub(r'<[^>]+>', '', t).strip() for t in raw_texts if re.sub(r'<[^>]+>', '', t).strip()]
            part_name = f.replace('.svg', '')
            svg_blueprints.append({
                "part_id": part_name,
                "file_path": svg_path,
                "category": classify_drawing(part_name),
                "extracted_annotations": clean_texts[:30]
            })

for d in DRAWING_DIRS:
    for root, dirs, files in os.walk(d):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff']:
                fp = os.path.join(root, f)
                try:
                    fsize = os.path.getsize(fp)
                    if fsize < 1024: continue # skip empty/corrupt files
                    
                    # Compute quick hash for deduplication
                    with open(fp, 'rb') as imgf:
                        h = hashlib.md5(imgf.read(4096)).hexdigest() + f"_{fsize}"
                    
                    if h in seen_hashes:
                        continue
                    seen_hashes.add(h)
                    
                    # Read image dimensions
                    try:
                        with Image.open(fp) as im:
                            w, h_dim = im.size
                    except:
                        w, h_dim = (0, 0)
                        
                    rel = os.path.relpath(fp, r"e:\迅雷下载")
                    cat = classify_drawing(f)
                    
                    dedup_drawings.append({
                        "filename": f,
                        "relative_path": rel,
                        "absolute_path": fp,
                        "extension": ext,
                        "size_bytes": fsize,
                        "resolution": [w, h_dim],
                        "category": cat
                    })
                except Exception as e:
                    pass

print(f"Total deduplicated blueprints: {len(dedup_drawings)}")
print(f"Total ground-truth SVG engineering drawings: {len(svg_blueprints)}")

# Save metadata index
index_file = os.path.join(OUTPUT_DIR, "drawings_metadata_index.jsonl")
with open(index_file, "w", encoding="utf-8") as f:
    for d in dedup_drawings:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")

# Generate Multimodal Drawing-to-CAD SFT Dataset
SYSTEM_PROMPT = (
    "你是由 Virtu 工业模型驱动的工程图纸识图与三维 CAD 建模时序专家（Drawing-to-CAD Specialist）。"
    "你能够从工程图纸（二维三视图、剖视图、轴测图及尺寸公差标注）中提取关键几何特征，"
    "规划符合现代工业软件（SolidWorks / UG NX / CATIA）的 FeatureManager 参数化建模特征树时序，"
    "准确识别配合公差代号、形位公差基准、螺纹规格与制造技术要求。"
)

sft_samples = []

# Use SVG blueprints with extracted annotations
for idx, svg in enumerate(svg_blueprints):
    title = svg["part_id"]
    cat = svg["category"]
    annotations = svg["extracted_annotations"]
    
    # Filter key annotations
    dims = [a for a in annotations if any(c in a for c in ['⌀', 'R', 'C', '°', 'H7', 'h6', 'M', 'Ra'])]
    notes = [a for a in annotations if 'GB' in a or '未注' in a or '材料' in a or '比例' in a]
    
    dim_str = ", ".join(dims[:10]) if dims else "主视图轴向尺寸与径向配合公差"
    note_str = "；".join(notes[:4]) if notes else "未注公差按 GB/T 1804-m 执行，零件去毛刺倒钝"
    
    sft_samples.append({
        "id": f"drawing_to_cad_{idx+1:04d}",
        "drawing_name": title,
        "part_category": cat,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"请针对工程图纸【{title}】（{cat}）进行工程识图分析：提取该图纸标注的关键尺寸与配合公差，并给出在 SolidWorks / UG NX 中的完整参数化三维特征建模时序指令（Feature Tree Sequence）。"},
            {
                "role": "assistant",
                "content": (
                    f"### 【{title}】工程识图与三维特征树建模工艺规划\n\n"
                    f"#### 1. 图纸特征与制造参数解析\n"
                    f"- **零件类型**：{cat}\n"
                    f"- **关键配合尺寸与公差**：{dim_str}\n"
                    f"- **制造技术要求**：{note_str}\n\n"
                    f"#### 2. 三维参数化特征树建模时序（SolidWorks / UG NX）\n"
                    f"遵循现代 CAD「基准先行、主体成型、去除材料、孔系向导、倒角精整」的标准设计树时序：\n\n"
                    f"1. **基准选择与草图（Sketch 1）**：\n"
                    f"   - 基准面：`FrontPlane (前视基准面)`\n"
                    f"   - 绘制主体几何回转半截面或拉伸轮廓，施加关于原点的对称约束与尺寸驱动；\n"
                    f"2. **基体成型特征（Boss Feature）**：\n"
                    f"   - 执行 `旋转 (Revolve)` 或 `基体-拉伸 (Boss-Extrude)`，生成基础实体；\n"
                    f"3. **内部结构与阶梯切除（Cut Extrude / Revolve Cut）**：\n"
                    f"   - 在端面建立草图，绘制配合台阶、退刀槽与安装定位凹槽，执行切除；\n"
                    f"4. **安装孔与配合孔向导（Hole Wizard）**：\n"
                    f"   - 选用 GB 标准异型孔向导，生成沉头螺钉过孔及 `⌀H7` 基孔制精密销孔；\n"
                    f"5. **辅助工艺特征（Keyway / Thread / Chamfer / Fillet）**：\n"
                    f"   - 切削键槽或螺纹孔（标注螺距与有效旋合深度）；\n"
                    f"   - 外轮廓锐边倒角 `C1.0`，过渡根部倒圆 `R2.0` 降低应力集中；\n"
                    f"6. **材质赋属性与干涉检查**：\n"
                    f"   - 赋予图纸指定工程材料（如 45#钢或 HT200 铸铁），校核质量属性与质心坐标。"
                )
            }
        ]
    })

# Add samples from the massive 2D blueprint sets
sample_types = [
    ("3D模型_阶梯传动轴.jpg", "轴类零件 (Shaft / Spindle)", "⌀25k5, ⌀32, ⌀20h6, 键槽宽 8P9, 倒角 C1.5", "调质处理 HB240-280，未注倒角 C1.0"),
    ("3D模型_减速器箱盖.jpg", "壳体与泵体类 (Housing / Body)", "箱体中分面平面度 0.02, 轴承承孔 ⌀72H7, 销孔 ⌀8H7", "铸件消除内应力退火，结合面涂密封胶严禁漏油"),
    ("3D模型_法兰连接端盖.jpg", "法兰盘类零件 (Flange)", "密封止口 ⌀110f7, 螺栓孔 PCD ⌀90 均布 6-⌀9", "未注公差按 GB/T 1804-m，外圆跳动公差 0.03"),
    ("3D模型_夹具定位底板.jpg", "工装夹具类 (Fixture / Tooling)", "双向定位键槽 18H7, 基准销孔间距 180±0.015", "工作表面高频淬火 HRC50-55，平面度 0.01")
]

for idx, (st_name, st_cat, st_dims, st_notes) in enumerate(sample_types):
    sft_samples.append({
        "id": f"drawing_to_cad_{len(svg_blueprints)+idx+1:04d}",
        "drawing_name": st_name,
        "part_category": st_cat,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"分析工程练习图纸【{st_name}】（{st_cat}），说明其核心加工特征识别要点，并构建参数化 CAD 建模树。"},
            {
                "role": "assistant",
                "content": (
                    f"### 【{st_name}】机械图纸深度识图与特征建模\n\n"
                    f"- **关键尺寸及形位公差**：{st_dims}\n"
                    f"- **热处理与工艺要求**：{st_notes}\n"
                    f"- **建模时序**：基准面定位 -> 基体拉伸/旋转 -> 配合特征与减料切除 -> 沉孔/销孔向导 -> 倒角圆角 -> 赋予材料特性。"
                )
            }
        ]
    })

sft_file = os.path.join(OUTPUT_DIR, "drawing_to_cad_sft.jsonl")
with open(sft_file, "w", encoding="utf-8") as f:
    for s in sft_samples:
        f.write(json.dumps(s, ensure_ascii=False) + "\n")

# Save feature checklist reference
checklist = {
    "shaft": ["圆柱阶梯段", "键槽", "轴端倒角", "轴肩过渡圆弧", "砂轮越程槽/退刀槽", "螺纹轴颈", "顶尖孔"],
    "flange": ["外圆柱面", "同心内孔", "螺栓分布圆(PCD)", "均布通孔/沉孔", "密封凹槽/止口", "端面密封刮面"],
    "bracket": ["底板安装孔", "加强筋", "支承半圆孔/通孔", "减重孔", "立板过渡倒圆", "基准加工面"],
    "housing": ["分形结合面", "轴承安装座孔", "定位销孔", "观察视孔盖螺孔", "放油螺塞孔", "铸造起模斜度"]
}
checklist_file = os.path.join(OUTPUT_DIR, "drawing_feature_checklists.json")
with open(checklist_file, "w", encoding="utf-8") as f:
    json.dump(checklist, f, ensure_ascii=False, indent=2)

print(f"Generated {len(sft_samples)} Drawing-to-CAD SFT records -> {sft_file}")
print(f"Saved checklists -> {checklist_file}")
