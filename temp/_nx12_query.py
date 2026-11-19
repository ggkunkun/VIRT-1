# -*- coding: utf-8 -*-
import json, io, sys
from collections import defaultdict

cat = json.load(open(r"d:\Virtu模型\knowledge_base\nx12_cn\catalog\nx12_cn_commands.json", encoding="utf-8"))
cmds = cat["commands"]
out = io.StringIO()

out.write("== RIBBON TABS ==\n")
for k, v in cat["ribbon_tabs"].items():
    out.write(f"{k} -> {v}\n")

out.write("\n== TOP LEVELS ==\n")
top = defaultdict(int)
for c in cmds.values():
    for p in c["menu_paths"]:
        top[p[0] if p else "(none)"] += 1
for k, v in sorted(top.items(), key=lambda x: -x[1]):
    out.write(f"{k}: {v}\n")

out.write("\n== ACCELERATORS ==\n")
for c in cmds.values():
    if c["accelerator"]:
        out.write(f"{c['accelerator']:<36} {c['id']:<42} {c['zh']}  | {c['menu_paths'][0] if c['menu_paths'] else ''}\n")

out.write("\n== CORE IDS ==\n")
ids = """UG_FILE_NEW UG_FILE_OPEN UG_FILE_SAVE_PART UG_FILE_SAVE_AS UG_FILE_SAVE_ALL
UG_FILE_OPTIONS UG_FILE_IMPORT UG_FILE_EXPORT UG_FILE_PRINT
UG_PREFERENCES UG_PREFERENCES_OBJECT UG_PREFERENCES_USER_INTERFACE UG_PREFERENCES_CUSTOMIZE
UG_TOOLBOX_EXPRESSIONS UG_TOOLBOX_MEASURE UG_TOOLBOX_CUSTOMIZE UG_TOOLBOX_JOURNAL
UG_SKETCHER UG_SKETCHER_SKETCH UG_SKETCHER_FINISH_SKETCH UG_SKETCHER_LINE UG_SKETCHER_ARC UG_SKETCHER_CIRCLE
UG_SKETCHER_RECTANGLE UG_SKETCHER_FILLET UG_SKETCHER_TRIM UG_SKETCHER_OFFSET UG_SKETCHER_CONSTRAINT
UG_MODELING_EXTRUDED_FEATURE UG_MODELING_REVOLVED UG_MODELING_BLOCK UG_MODELING_CYLINDER
UG_MODELING_HOLE UG_MODELING_THREAD UG_MODELING_CHAMFER UG_MODELING_BLEND UG_MODELING_SHELL
UG_MODELING_DRAFT UG_MODELING_RIB UG_MODELING_EDGE_BLEND UG_MODELING_EDGE_CHAMFER
UG_MODELING_BOOLEAN UG_MODELING_UNITE UG_MODELING_SUBTRACT UG_MODELING_INTERSECT
UG_MODELING_SYNCHRONOUS UG_MODELING_MOVE_FACE UG_MODELING_DELETE_FACE UG_MODELING_REPLACE_FACE
UG_MODELING_PATTERN UG_MODELING_MIRROR UG_MODELING_FEATURE_EDIT_PARAMETERS
UG_ASSEMBLY_ADD_COMPONENT UG_ASSEMBLY_CONSTRAINT UG_ASSEMBLY_NEW_COMPONENT UG_ASSEMBLY_MIRROR
UG_ASSEMBLY_EXPLODE UG_ASSEMBLY_CLEARANCE UG_ASSEMBLY_INTERFERENCE UG_ASSEMBLY_REPORT
UG_DRAFTING_DRAWING UG_DRAFING_DRAWING UG_DRAFTING_BASE_VIEW UG_DRAFTING_PROJECTED_VIEW
UG_DRAFTING_SECTION_VIEW UG_DRAFTING_DETAIL_VIEW UG_DRAFTING_DIMENSION UG_DRAFTING_NOTE
UG_DRAFTING_GDT UG_DRAFTING_SURFACE_FINISH UG_DRAFTING_TITLE_BLOCK UG_DRAFTING_EDIT_VIEW
UG_DRAFTING_ANNOTATION UG_DRAFTING_ORTHOGRAPHIC_VIEW
UG_SMD UG_SMD_SHEET UG_SMD_FLANGE UG_SMD_BEND UG_SMD_UNBEND UG_SMD_REBEND
UG_SMD_CONTOUR_FLANGE UG_SMD_HOLE UG_SMD_NORMAL_CUTOUT
MW_MOLDWIZARD MW_PARTING MW_MOLD_BASE MW_CORE_CAVITY MW_CAVITY_LAYOUT
UG_CAM UG_CAM_CREATE_OPERATION UG_CAM_CREATE_TOOL UG_CAM_GENERATE UG_CAM_POST_PROCESS
UG_CAM_VERIFY UG_CAM_PLANAR_MILL UG_CAM_CAVITY_MILL UG_CAM_DRILL
UG_STYLER UG_FREEFORM UG_SWEPT UG_THROUGH_CURVES UG_THROUGH_CURVE_MESH UG_RULED
""".split()
seen = set()
for i in ids:
    if i in seen:
        continue
    seen.add(i)
    c = cmds.get(i)
    if not c:
        out.write(f"[MISSING] {i}\n")
    else:
        out.write(f"{i} | {c['zh']} | accel={c['accelerator']} | {c['menu_paths'][:4]}\n")

out.write("\n== KEYWORD SEARCH ==\n")
for kw in ["草图", "拉伸", "回转", "装配约束", "添加组件", "基本视图", "剖视图", "尺寸", "表面粗糙度",
           "形位公差", "钣金", "弯边", "展开", "模具", "分型", "型腔", "后处理", "平面铣", "型腔铣",
           "钻孔", "扫掠", "网格", "直纹", "缝合", "修剪", "表达式", "命令查找器", "定制", "首选项",
           "图纸页", "标题栏", "装配间隙", "爆炸", "倒斜角", "边倒圆", "抽壳", "拔模", "孔", "螺纹"]:
    hits = [(c["id"], c["zh"], c["menu_paths"][0] if c["menu_paths"] else []) for c in cmds.values()
            if kw in c["zh"] or kw in c["id"]]
    hits = hits[:12]
    out.write(f"\n-- {kw} ({len(hits)}) --\n")
    for h in hits:
        out.write(f"  {h[0]} | {h[1]} | {h[2]}\n")

open(r"d:\Virtu模型\temp\nx12_cn_query.txt", "w", encoding="utf-8").write(out.getvalue())
print("written", len(out.getvalue()))
