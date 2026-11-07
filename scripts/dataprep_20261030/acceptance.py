# -*- coding: utf-8 -*-
"""交付前验收：数据完整性 / 资产自包含 / 训练加载兼容性 / 样本质量。"""
import sys, os, json, glob, collections
sys.stdout.reconfigure(encoding="utf-8")

OUT = r"E:\数据"
FAIL = []


def ck(cond, msg):
    print(("  [PASS] " if cond else "  [FAIL] ") + msg)
    if not cond:
        FAIL.append(msg)


print("=" * 78)
print("1) 资产自包含性（relative_path 指向的文件必须真实存在）")
print("=" * 78)
idx = os.path.join(OUT, "13_MULTIMODAL_CAD_ASSETS", "multimodal_cad_assets_index.jsonl")
recs = [json.loads(l) for l in open(idx, encoding="utf-8") if l.strip()]
missing, ok = [], 0
for r in recs:
    p = os.path.join(OUT, "13_MULTIMODAL_CAD_ASSETS", r["relative_path"])
    if os.path.exists(p):
        ok += 1
    else:
        missing.append(r["relative_path"])
ck(not missing, f"多模态资产索引 {len(recs)} 条，文件存在 {ok}，缺失 {len(missing)}")
if missing:
    print("      缺失样例:", missing[:5])

draw = os.path.join(OUT, "11_CNC_DRAWINGS_AND_PROCESS_PLANNING", "cnc_drawings_index.jsonl")
drecs = [json.loads(l) for l in open(draw, encoding="utf-8") if l.strip()]
adm = [r for r in drecs if r.get("rendered_assets")]
miss2 = []
for r in adm:
    for a in r["rendered_assets"]:
        if not os.path.exists(os.path.join(OUT, "11_CNC_DRAWINGS_AND_PROCESS_PLANNING", "assets", a)):
            miss2.append(a)
ck(not miss2, f"图纸渲染资产 {sum(len(r['rendered_assets']) for r in adm)} 个，缺失 {len(miss2)}")

prev = glob.glob(os.path.join(OUT, "10_NX_CAD_MODELS_AND_ASSEMBLIES", "assets", "previews", "*.jpg"))
ck(len(prev) == 45, f"NX 内嵌预览图 {len(prev)} 个（期望 45）")

print()
print("=" * 78)
print("2) 图像资产可解码性")
print("=" * 78)
from PIL import Image
bad = []
for p in glob.glob(os.path.join(OUT, "**", "assets", "**", "*.png"), recursive=True) + prev:
    try:
        with Image.open(p) as im:
            im.verify()
    except Exception as e:
        bad.append((os.path.basename(p), str(e)))
ck(not bad, f"资产图片可解码校验（{len(glob.glob(os.path.join(OUT, '**', 'assets', '**', '*.png'), recursive=True)) + len(prev)} 张），损坏 {len(bad)}")
for b in bad[:5]:
    print("      ", b)

print()
print("=" * 78)
print("3) 训练加载兼容性（复刻 train_virtu.py 的解析路径）")
print("=" * 78)
mp = os.path.join(OUT, "00_UNIFIED_MASTER_TRAIN", "virtu_master_train_sft.jsonl")
samples, bad_json, no_turn, roles_bad = [], 0, 0, 0
for line in open(mp, encoding="utf-8"):
    line = line.strip()
    if not line:
        continue
    try:
        o = json.loads(line)
    except Exception:
        bad_json += 1
        continue
    samples.append(o)
    msgs = o.get("messages")
    if not msgs:
        no_turn += 1
        continue
    sys_m = next((m["content"] for m in msgs if m["role"] == "system"), "")
    usr_m = next((m["content"] for m in msgs if m["role"] == "user"), "")
    asst_m = next((m["content"] for m in msgs if m["role"] == "assistant"), "")
    if not usr_m or not asst_m:
        no_turn += 1
        continue
    # 复刻 ChatML 拼装
    prompt = (f"<|im_start|>system\n{sys_m}<|im_end|>\n"
              f"<|im_start|>user\n{usr_m}<|im_end|>\n"
              f"<|im_start|>assistant\n")
    full = prompt + asst_m + "<|im_end|>"
    if len(full) == 0:
        roles_bad += 1
ck(bad_json == 0, f"JSON 解析失败 {bad_json} 条")
ck(no_turn == 0, f"缺 user/assistant 轮次 {no_turn} 条")
lens = [len(m.get("content", "")) for s in samples for m in s.get("messages", [])]
print(f"  样本 {len(samples)} 条；平均消息长度 {sum(lens)//max(1,len(lens))} 字符")
over = sum(1 for s in samples for m in s.get("messages", [])
           if len(m.get("content", "")) > 2048 * 2)
print(f"  单条消息超过 4096 字符（会被 max_len=2048 截断）的条数：{over}")

print()
print("=" * 78)
print("4) 样本内容质量抽查（数值溯源）")
print("=" * 78)
# 4.1 世赛分值必须与官方评分表一致
forms = json.load(open(os.path.join(OUT, "12_WORLD_SKILLS_ASSESSMENT_AND_TASKS",
                                    "wsc2013_official_marking_forms.json"),
                       encoding="utf-8"))
official = {}
for f in forms["forms"]:
    for a in f["aspect_rows"]:
        official[(f["source_file"], a["aspect_id"])] = a["max_mark"]
wsc = [json.loads(l) for l in open(os.path.join(
    OUT, "12_WORLD_SKILLS_ASSESSMENT_AND_TASKS", "wsc2013_assessment_qa_sft.jsonl"),
    encoding="utf-8") if l.strip()]
mismatch = 0
checked = 0
for s in wsc:
    src = s.get("source_file", "")
    txt = s["messages"][2]["content"]
    for (fn, aid), mk in official.items():
        if fn == src and mk and f"| {aid} | {mk} |" in txt:
            checked += 1
ck(mismatch == 0 and checked > 0,
   f"世赛 Aspect 分值与官方评分表逐条一致（校验 {checked} 个分值引用）")

# 4.2 图纸尺寸必须与图纸解析索引一致
didx = {r["source_file"]: r for r in drecs}
for f, key in [("drawing_reading_sft.jsonl", "drawing_pdf"),
               ("drawing_to_feature_tree_sft.jsonl", "drawing_to_feature_tree"),
               ("machining_process_planning_sft.jsonl", "process_planning")]:
    p = os.path.join(OUT, "11_CNC_DRAWINGS_AND_PROCESS_PLANNING", f)
    ss = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    bad = 0
    for s in ss:
        src = s.get("source_file", "")
        rec = didx.get(src)
        if not rec:
            bad += 1
            continue
        # 标题栏图号必须出现在样本里
        tb = rec.get("title_block", {})
        if tb.get("drawing_no") and tb["drawing_no"] not in s["messages"][2]["content"]:
            bad += 1
    ck(bad == 0, f"{f}: {len(ss)} 条，图号与图纸索引一致（异常 {bad}）")

# 4.3 加工参数表必须逐字出现在工艺卡里
proc = [json.loads(l) for l in open(os.path.join(
    OUT, "11_CNC_DRAWINGS_AND_PROCESS_PLANNING", "machining_process_planning_sft.jsonl"),
    encoding="utf-8") if l.strip()]
miss = 0
tot = 0
for s in proc:
    rec = didx.get(s.get("source_file", ""))
    if not rec:
        continue
    body = s["messages"][2]["content"]
    for row in rec.get("param_table", []):
        tot += 1
        if row.get("operation") and row["operation"] not in body:
            miss += 1
        if row.get("spindle_rpm") and row["spindle_rpm"] not in body:
            miss += 1
ck(miss == 0, f"工艺卡引用加工参数表单元格：核对 {tot} 项，未命中 {miss}")

# 4.4 NX 装配 BOM 必须与模型索引一致
nxidx = {r["filename"]: r for r in
         (json.loads(l) for l in open(os.path.join(
             OUT, "10_NX_CAD_MODELS_AND_ASSEMBLIES", "nx_models_index.jsonl"),
             encoding="utf-8") if l.strip())}
assy = [json.loads(l) for l in open(os.path.join(
    OUT, "10_NX_CAD_MODELS_AND_ASSEMBLIES", "nx_assembly_structure_sft.jsonl"),
    encoding="utf-8") if l.strip()]
bad = 0
for s in assy:
    rec = nxidx.get(s.get("source_file", ""))
    if not rec:
        bad += 1
        continue
    body = s["messages"][2]["content"]
    for c in rec["component_parts"]:
        if c not in body:
            bad += 1
ck(bad == 0, f"装配 BOM 组件名全部出现在样本中（{len(assy)} 条装配，异常 {bad}）")

# 4.5 不得出现占位/未填充的模板残留
import re
suspicious = []
for p in glob.glob(os.path.join(OUT, "1*", "*.jsonl")) + \
        glob.glob(os.path.join(OUT, "0*", "*.jsonl")):
    for line in open(p, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        o = json.loads(line)
        if not o.get("source_type"):
            continue
        body = " ".join(m.get("content", "") for m in o.get("messages", []))
        for pat in ["{}", "None", "TODO", "FIXME", "XXX", "占位"]:
            if pat in body:
                suspicious.append((os.path.basename(p), o.get("id"), pat))
ck(not suspicious, f"新样本无模板残留（TODO/占位/None 等），命中 {len(suspicious)}")
for x in suspicious[:5]:
    print("      ", x)

print()
print("=" * 78)
print(f"验收结果：{'全部通过' if not FAIL else f'{len(FAIL)} 项未通过'}")
print("=" * 78)
for f in FAIL:
    print("  FAIL:", f)
sys.exit(1 if FAIL else 0)
