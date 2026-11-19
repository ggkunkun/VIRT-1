# -*- coding: utf-8 -*-
"""
AutoCAD 2026 简体中文专业能力体系 - 智能体查询引擎
数据源：官方 CUIX (R25.1/chs) + acad.pgp + Autodesk 官网 2026 功能说明。
设计目标：本地检索，单次查询 <1 秒，返回精准结构化结果。
用法：
  python query_engine.py "LINE"          # 查命令
  python query_engine.py "L"             # 查别名（返回 LINE 等）
  python query_engine.py "怎么标注直径"   # 场景问答
  python query_engine.py --scene "机械"  # 领域工作流
  python query_engine.py --fix "文字乱码" # 故障排查
  python query_engine.py --new           # 2026 新特性
"""
import os, sys, json, time, re

BASE = os.path.dirname(os.path.abspath(__file__))
_cache = {}


def load(name):
    if name not in _cache:
        with open(os.path.join(BASE, name), encoding="utf-8") as f:
            _cache[name] = json.load(f)
    return _cache[name]


def norm(s):
    return re.sub(r"\s+", "", str(s)).strip().upper()


def query_command(q):
    """查命令/别名：返回完整四维度信息"""
    idx = load("command_index.json")
    qn = norm(q)
    results = []
    # 精确命令名
    rec = idx["commands"].get(qn)
    if rec:
        results.append(rec)
    # 别名反查
    for a, cs in idx["alias_index"].items():
        if norm(a) == qn:
            for c in cs:
                if c in idx["commands"] and idx["commands"][c] not in results:
                    r = dict(idx["commands"][c]); r["_matched_alias"] = a
                    results.append(r)
    # 中文名模糊
    if not results:
        for c, r in idx["commands"].items():
            if q.upper() in (r.get("name_zh", "") + r.get("help_zh", "")).upper():
                results.append(r)
                if len(results) >= 12:
                    break
    return results


# 场景同义词：自然语言 -> 命令名（官方命令）
SCENE_SYNONYMS = {
    "直径": ["DIMDIAMETER"], "半径": ["DIMRADIUS"], "角度": ["DIMANGULAR"],
    "线性标注": ["DIMLINEAR"], "标注": ["DIMLINEAR", "DIMALIGNED", "DIMDIAMETER", "DIMRADIUS"],
    "文字": ["TEXT", "MTEXT"], "写字": ["TEXT", "MTEXT"], "多行文字": ["MTEXT"],
    "删除": ["ERASE"], "擦除": ["ERASE"], "移动": ["MOVE"], "复制": ["COPY"],
    "修剪": ["TRIM"], "延伸": ["EXTEND"], "偏移": ["OFFSET"], "镜像": ["MIRROR"],
    "旋转": ["ROTATE"], "缩放": ["SCALE"], "打印": ["PLOT"], "出图": ["PLOT"],
    "填充": ["HATCH"], "剖面线": ["HATCH"], "图层": ["LAYER"], "块": ["BLOCK", "INSERT"],
    "插入块": ["INSERT"], "创建块": ["BLOCK"], "外部参照": ["XREF", "XATTACH"],
    "引线": ["MLEADER", "LEADER"], "表格": ["TABLE"], "坐标": ["ID", "DIST"],
    "距离": ["DIST"], "面积": ["AREA"], "分解": ["EXPLODE"], "圆角": ["FILLET"],
    "倒角": ["CHAMFER"], "阵列": ["ARRAY"], "样条": ["SPLINE"], "多段线": ["PLINE"],
    "约束": ["GEOMCONSTRAINT", "DIMCONSTRAINT"], "渲染": ["RENDER"], "材质": ["MATERIAL"],
    "三维": ["EXTRUDE", "REVOLVE", "BOX"], "拉伸": ["EXTRUDE"], "旋转建模": ["REVOLVE"],
    "保存": ["QSAVE", "SAVEAS"], "撤销": ["U", "UNDO"], "重做": ["REDO"],
}


def query_scene(q):
    """场景问答：自然语言 -> 命令，按同义词 + 名称/功能模糊检索"""
    idx = load("command_index.json")
    mp = load("command_function_scene_map.json")
    out = []
    seen = set()
    # 1) 同义词直接映射（最高优先级）
    for kw, cmds in SCENE_SYNONYMS.items():
        if kw in q:
            for c in cmds:
                if c in idx["commands"] and c not in seen:
                    r = idx["commands"][c]
                    out.append({"command": c, "name_zh": r["name_zh"], "function": r["help_zh"],
                                "module_name": "", "aliases": r["aliases"], "scenes": []})
                    seen.add(c)
    # 2) 中文名/功能包含匹配
    qclean = q.replace("怎么", "").replace("如何", "").replace("命令", "").strip()
    for m in mp["mappings"]:
        if m["command"] in seen:
            continue
        hay = m["name_zh"] + m["function"]
        if qclean and qclean in hay:
            out.append(m); seen.add(m["command"])
    # 3) 单字关键词兜底
    if not out:
        for ch in re.findall(r"[\u4e00-\u9fff]", q):
            for m in mp["mappings"]:
                if ch in m["name_zh"] and m["command"] not in seen:
                    out.append(m); seen.add(m["command"]); break
    return out[:20]


def query_workflow(domain_kw):
    wf = load("industry_workflows.json")
    out = []
    for d in wf["domains"]:
        if domain_kw in d["name"] or domain_kw in d["id"] or domain_kw in " ".join(d["standards"]):
            out.append(d)
    if not out:
        out = wf["domains"]
    return out


FIX_SYNONYMS = {
    "乱码": "文字显示为问号", "问号": "文字显示为问号", "字体": "缺失字体",
    "卡顿": "打开文件卡顿", "慢": "打开文件卡顿", "打不开": "损坏打不开",
    "损坏": "损坏打不开", "比例": "打印出图比例", "选不中": "无法选中",
    "填充没了": "填充无法显示", "标注不动": "标注不随对象变化",
}


def query_fix(symptom):
    wf = load("industry_workflows.json")
    symptom2 = symptom
    for k, v in FIX_SYNONYMS.items():
        if k in symptom2:
            symptom2 += " " + v
    # 单字 + 完整词，按命中数打分
    chars = [c for c in symptom2 if "\u4e00" <= c <= "\u9fff"]
    words = re.findall(r"[\u4e00-\u9fff]{2,}", symptom2)
    scored = []
    for t in wf["troubleshooting"]:
        hay = t["symptom"] + t["cause"]
        score = sum(1 for c in set(chars) if c in hay) + sum(2 for w in words if w in hay)
        if score > 0:
            scored.append((score, t))
    scored.sort(key=lambda x: -x[0])
    return [t for _, t in scored][:8]


def query_new_features():
    return load("features_2026.json")["new_features_2026"]


def fmt_command(r):
    lines = [f"● {r['command']}  {r.get('name_zh','')}"]
    if r.get("_matched_alias"):
        lines[0] += f"   [别名 {r['_matched_alias']} 命中]"
    if r.get("aliases"):
        lines.append(f"  别名: {', '.join(r['aliases'])}")
    if r.get("shortcuts"):
        lines.append(f"  快捷键: {', '.join(r['shortcuts'])}")
    lines.append(f"  命令行输入: {r.get('input_format', r['command'])}")
    if r.get("help_zh"):
        lines.append(f"  功能: {r['help_zh']}")
    if r.get("menu_path"):
        lines.append(f"  菜单路径: {'; '.join(r['menu_path'][:3])}")
    if r.get("ribbon_path"):
        lines.append(f"  功能区路径: {'; '.join(r['ribbon_path'][:2])}")
    if r.get("command_path"):
        lines.append(f"  命令宏: {r['command_path'][:90]}")
    if r.get("right_click_options"):
        lines.append(f"  右键选项: {', '.join(r['right_click_options'][:6])}")
    if r.get("limitation"):
        lines.append(f"  局限性: {r['limitation']}")
    return "\n".join(lines)


def main():
    t0 = time.perf_counter()
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    flag = None
    if args[0].startswith("--"):
        flag = args[0]; q = " ".join(args[1:])
    else:
        q = " ".join(args)

    if flag == "--scene":
        domains = query_workflow(q) if q else load("industry_workflows.json")["domains"]
        for d in domains:
            print(f"\n【{d['name']}】标准: {'; '.join(d['standards'][:2])}")
            print(f"  图层: {', '.join(d['layer_scheme'][:6])}")
            for wf in d["workflows"]:
                print(f"  ▸ {wf['name']}: {' → '.join(wf['steps'][:5])}")
                print(f"    关键命令: {', '.join(wf['key_commands'])}")
    elif flag == "--fix":
        for t in query_fix(q):
            print(f"\n● 现象: {t['symptom']}\n  原因: {t['cause']}\n  处置: {t['fix']}")
    elif flag == "--new":
        for f in query_new_features():
            print(f"\n● {f['name']} [{f['type']}] - {f['category']}\n  {f['desc']}\n  命令: {', '.join(f['commands']) or '通过功能区/界面调用'}")
            if f.get("command_note"):
                print(f"  说明: {f['command_note']}")
    else:
        # 默认：先按命令/别名，未命中再按场景
        res = query_command(q)
        if res:
            print(f"命中 {len(res)} 条：\n")
            for r in res[:10]:
                print(fmt_command(r) + "\n")
        else:
            scenes = query_scene(q)
            if scenes:
                print(f"场景匹配 {len(scenes)} 条命令：\n")
                for m in scenes[:12]:
                    print(f"● {m['command']} {m['name_zh']} — {m['function'][:60]} [{m['module_name']}]")
            else:
                print("未命中，请尝试命令名/别名/中文功能词，或用 --scene/--fix/--new。")
    dt = (time.perf_counter() - t0) * 1000
    print(f"\n[响应 {dt:.1f} ms]")


if __name__ == "__main__":
    main()
