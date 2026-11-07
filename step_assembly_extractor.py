#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
STEP → 装配体 BOM / 结构树提取器 (免依赖, 支持 AP203 AP242 中文 GBK)
=========================================================================
解决痛点: CAD/CAM 领域模型(如 virtu-cad-cam 13.63B) "读不懂装配体"。
根因(已在本文件实测验证):
  1) STEP 为 GBK 编码, 中文零件名在 UTF-8 分词下全成乱码;
  2) 装配树实体(NEXT_ASSEMBLY_USAGE_OCCURRENCE)仅 4 行, 藏在 8000 行 BREP 几何末尾;
  3) 零件靠 #id 跨 8000 行隐式交叉引用, 无自然语言锚点;
  4) 几何挂在 ADVANCED_BREP_SHAPE_REPRESENTATION(representation 子类型)上,
     通过"同一 context id"与零件级 SHAPE_REPRESENTATION 关联;
  5) 子零件摆放坐标经 REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION
     -> ITEM_DEFINED_TRANSFORMATION -> AXIS2_PLACEMENT_3D 表达, 非自然语言.

本脚本把原始 STEP 转成【结构化 / UTF-8 / 人类+模型可读】的 BOM(JSON+Markdown),
让模型用 ~30 行结构描述替代 8000 行几何噪声。

用法:
  python3 step_assembly_extractor.py <input.step> [--json out.json] [--md out.md]
"""
import sys, re, json, os

def read_bytes(path):
    with open(path, 'rb') as f:
        return f.read()

def to_str(b):
    if isinstance(b, str):
        return b
    for enc in ('gbk', 'gb18030', 'utf-8'):
        try:
            return b.decode(enc)
        except Exception:
            pass
    return b.decode('latin-1', errors='replace')

ENTITY_RE = re.compile(rb'#(\d+)\s*=')

def detect_type(raw):
    # STEP 复杂实体可能形如 #id =( TYPE (...) ...); 类型不在 = 后紧贴, 需特判
    if b'REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION' in raw:
        return 'REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION'
    mm = re.match(rb'^[\s(]*([A-Z][A-Z0-9_]*)', raw)
    return mm.group(1).decode('ascii') if mm else 'UNKNOWN'

def parse_entities(data):
    entities = {}
    for m in ENTITY_RE.finditer(data):
        eid = int(m.group(1))
        start = m.end()
        # 从 = 后开始做括号平衡扫描(无论首字符是否为 '(')
        depth, i, instr, quote, n = 0, start, False, None, len(data)
        started = False
        while i < n:
            c = data[i:i+1]
            if instr:
                if c == quote:
                    instr = False
            else:
                if c == b"'":
                    instr, quote = True, c
                elif c == b'(':
                    depth += 1; started = True
                elif c == b')':
                    depth -= 1
                    if started and depth == 0:
                        break
            i += 1
        raw = data[start:i]
        entities[eid] = raw
    return entities

def strip_outer(raw):
    """剥掉实体首部类型名与最外层括号, 返回内部顶层参数字符串。
    兼容普通实体 #id = TYPE ( a, b ) 与复杂实体 #id =( TYPE (...) ...)。"""
    s = to_str(raw).strip()
    idx = s.find('(')
    if idx == -1:
        return s
    depth, i = 0, idx
    while i < len(s):
        if s[i] == '(':
            depth += 1
        elif s[i] == ')':
            depth -= 1
            if depth == 0:
                break
        i += 1
    return s[idx+1:i]

def split_top(pb):
    s = to_str(pb)
    out, depth, cur, instr, q = [], 0, '', False, None
    for ch in s:
        if instr:
            cur += ch
            if ch == q:
                instr = False
            continue
        if ch in "\"'":
            instr, q, cur = True, ch, cur + ch
        elif ch == '(':
            depth += 1; cur += ch
        elif ch == ')':
            depth -= 1; cur += ch
        elif ch == ',' and depth == 0:
            out.append(cur.strip()); cur = ''
        else:
            cur += ch
    if cur.strip() != '' or out:
        out.append(cur.strip())
    return out

def ref_of(tok):
    m = re.match(r'^#(\d+)$', tok.strip())
    return int(m.group(1)) if m else None

def strip_str(tok):
    tok = tok.strip()
    if len(tok) >= 2 and tok[0] in "\"'":
        return tok[1:-1]
    return tok

def main():
    if len(sys.argv) < 2:
        print("用法: python3 step_assembly_extractor.py <input.step> [--json out.json] [--md out.md]")
        sys.exit(1)
    in_path = sys.argv[1]
    json_out = md_out = None
    for k in range(2, len(sys.argv)):
        if sys.argv[k] == '--json' and k+1 < len(sys.argv):
            json_out = sys.argv[k+1]
        if sys.argv[k] == '--md' and k+1 < len(sys.argv):
            md_out = sys.argv[k+1]

    data = read_bytes(in_path)
    ents = parse_entities(data)
    print(f"[+] 解析实体总数: {len(ents)}")

    product_name = {}
    formation_to_product = {}
    pd_to_formation = {}
    pds_to_pd = {}
    sdr = {}                      # sdr_id -> (pds_id, rep_id)
    rep_ctx = {}                  # rep_id -> context_id  (SHAPE_REPRESENTATION / ADVANCED_BREP_SHAPE_REPRESENTATION)
    rep_name = {}                 # rep_id -> name(str)
    abrep_breps = {}              # abrep_id -> [brep_id,...]
    brep_name = {}                # brep_id -> name
    brep_shell = {}               # brep_id -> closed_shell_id
    closed_shell_faces = {}       # shell_id -> face_count
    rrwt = {}                     # rr_id -> (rep1, rep2, idt_id)
    idt = {}                      # idt_id -> (item1_axis2, item2_axis2)
    axis2_point = {}              # axis2_id -> cartesian_point_id
    point_coord = {}              # point_id -> (x,y,z)
    nauo = []                     # (parent_pd, child_pd)

    for eid, raw in ents.items():
        pb = strip_outer(raw)
        p = split_top(pb)
        t = detect_type(raw)
        if t == 'PRODUCT':
            product_name[eid] = strip_str(p[0]) if p else ''
        elif t in ('PRODUCT_DEFINITION_FORMATION', 'PRODUCT_DEFINITION_FORMATION_WITH_SPECIFIED_SOURCE'):
            prod = ref_of(p[2]) if len(p) > 2 else None
            if prod: formation_to_product[eid] = prod
        elif t == 'PRODUCT_DEFINITION':
            form = ref_of(p[2]) if len(p) > 2 else None
            if form: pd_to_formation[eid] = form
        elif t == 'PRODUCT_DEFINITION_SHAPE':
            pd = ref_of(p[2]) if len(p) > 2 else None
            if pd: pds_to_pd[eid] = pd
        elif t == 'SHAPE_DEFINITION_REPRESENTATION':
            pds, rep = ref_of(p[0]), ref_of(p[1])
            if pds is not None and rep is not None:
                sdr[eid] = (pds, rep)
        elif t in ('SHAPE_REPRESENTATION', 'ADVANCED_BREP_SHAPE_REPRESENTATION'):
            name = strip_str(p[0]) if p else ''
            rep_name[eid] = name
            # context 通常是最后一个参数 (#id)
            ctx = None
            for tok in reversed(p):
                ctx = ref_of(tok)
                if ctx is not None:
                    break
            if ctx is not None:
                rep_ctx[eid] = ctx
            if t == 'ADVANCED_BREP_SHAPE_REPRESENTATION' and len(p) > 1:
                inner = p[1].strip()
                if inner.startswith('(') and inner.endswith(')'):
                    inner = inner[1:-1]
                breps = [ref_of(tok) for tok in re.split(r'\s*,\s*', inner) if ref_of(tok)]
                abrep_breps[eid] = [b for b in breps if b is not None]
        elif t == 'MANIFOLD_SOLID_BREP':
            brep_name[eid] = strip_str(p[0]) if p else ''
            sh = ref_of(p[1]) if len(p) > 1 else None
            if sh: brep_shell[eid] = sh
        elif t == 'CLOSED_SHELL':
            if len(p) > 1:
                inner = p[1].strip()
                if inner.startswith('(') and inner.endswith(')'):
                    inner = inner[1:-1]
                closed_shell_faces[eid] = len([tok for tok in re.split(r'\s*,\s*', inner) if ref_of(tok)])
        elif t == 'REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION':
            # 嵌套实体: #x =( REPRESENTATION_RELATIONSHIP (..., #rep1, #rep2 ) ..._WITH_TRANSFORMATION ( #idt ) ...)
            raw_txt = to_str(raw)
            m = re.search(r'WITH_TRANSFORMATION\s*\(\s*#(\d+)\s*\)', raw_txt)
            idt_id = int(m.group(1)) if m else None
            refs = [int(x) for x in re.findall(r'#(\d+)', raw_txt)]
            rep1 = rep2 = None
            reps = [r for r in refs if r in rep_name]  # 仅 SHAPE_REPRESENTATION
            if len(reps) >= 2:
                rep1, rep2 = reps[0], reps[1]
            rrwt[eid] = (refs, idt_id)
        elif t == 'ITEM_DEFINED_TRANSFORMATION':
            i1 = ref_of(p[2]) if len(p) > 2 else None
            i2 = ref_of(p[3]) if len(p) > 3 else None
            if i1 and i2: idt[eid] = (i1, i2)
        elif t == 'AXIS2_PLACEMENT_3D':
            pt = ref_of(p[1]) if len(p) > 1 else None
            if pt is not None: axis2_point[eid] = pt
        elif t == 'CARTESIAN_POINT':
            nums = re.findall(r'-?\d+\.?\d*(?:[eE][+-]?\d+)?', ' '.join(p))
            if len(nums) >= 3:
                point_coord[eid] = tuple(round(float(x), 4) for x in nums[:3])
        elif t == 'NEXT_ASSEMBLY_USAGE_OCCURRENCE':
            parent = ref_of(p[3]) if len(p) > 3 else None
            child = ref_of(p[4]) if len(p) > 4 else None
            if parent and child:
                nauo.append((parent, child))

    # ---- PD -> 产品名 ----
    pd_name = {}
    for pd, form in pd_to_formation.items():
        prod = formation_to_product.get(form)
        pd_name[pd] = product_name.get(prod, '') if prod else ''
    # 若产品名空, 退回 rep 名
    def name_of_pd(pd):
        nm = pd_name.get(pd, '')
        if nm:
            return nm
        # 找该 PD 的 rep 名
        for sdr_id, (pds, rep) in sdr.items():
            if pds_to_pd.get(pds) == pd and rep in rep_name and rep_name[rep]:
                return rep_name[rep]
        return f"<pd#{pd}>"

    # ---- 每个 PD -> rep(SHAPE_REPRESENTATION) -> context -> ADVANCED_BREP -> breps ----
    pd_rep = {}
    for sdr_id, (pds, rep) in sdr.items():
        pd = pds_to_pd.get(pds)
        if pd is not None and rep in rep_name:  # 仅 SHAPE_REPRESENTATION(命名零件级)
            pd_rep[pd] = rep

    def geometry_of_pd(pd):
        rep = pd_rep.get(pd)
        if rep is None:
            return [], 0, []
        ctx = rep_ctx.get(rep)
        solids, faces, body_names = [], 0, []
        # 找所有 ADVANCED_BREP_SHAPE_REPRESENTATION 共享同一 context
        for ab_id, brefs in abrep_breps.items():
            if rep_ctx.get(ab_id) == ctx:
                for b in brefs:
                    if b in brep_name:
                        solids.append(b)
                        faces += closed_shell_faces.get(brep_shell.get(b, -1), 0)
                        if brep_name[b]:
                            body_names.append(brep_name[b])
        return solids, faces, body_names

    # ---- 构建树骨架 (先确定根与子零件) ----
    children_map = {}
    all_child = set()
    for parent, child in nauo:
        children_map.setdefault(parent, []).append(child)
        all_child.add(child)
    roots = [pd for pd in pd_rep if pd not in all_child] or [pd for pd in pd_name if pd not in all_child]
    root_rep = pd_rep.get(roots[0]) if roots else None

    # ---- 子零件摆放原点 (child rep -> idt -> item1 axis2 -> point) ----
    # RRWT 实体早于其引用的 SHAPE_REPRESENTATION 出现, 故在此(主循环后)解析 rep1/rep2
    rrwt_resolved = {}
    for eid, (refs, idt_id) in rrwt.items():
        reps = [r for r in refs if r in rep_name]   # 仅 SHAPE_REPRESENTATION
        rep1 = reps[0] if len(reps) >= 1 else None
        rep2 = reps[1] if len(reps) >= 2 else None
        rrwt_resolved[eid] = (rep1, rep2, idt_id)

    child_rep_to_origin = {}
    for rr_id, (r1, r2, idt_id) in rrwt_resolved.items():
        if idt_id is None:
            continue
        # 子 rep = 两个 SHAPE_REPRESENTATION 中不属于根的那个
        child_rep = None
        for r in (r1, r2):
            if r is not None and r in pd_rep.values() and r != root_rep:
                child_rep = r
                break
        if child_rep is None:
            continue
        i1, i2 = idt.get(idt_id, (None, None))
        ax = i1 if i1 is not None else i2
        pt = axis2_point.get(ax)
        coord = point_coord.get(pt) if pt is not None else None
        child_rep_to_origin[child_rep] = coord

    def build(pd):
        solids, faces, bodies = geometry_of_pd(pd)
        rep = pd_rep.get(pd)
        origin = child_rep_to_origin.get(rep) if rep is not None else None
        node = {
            "pd_id": pd,
            "name": name_of_pd(pd),
            "solids": len(solids),
            "faces": faces,
            "bodies": bodies,
            "placement": list(origin) if origin else None,
            "children": [build(c) for c in children_map.get(pd, [])]
        }
        return node

    trees = [build(r) for r in roots]

    # 根节点通常无实体(装配容器); 统计
    summary = {
        "file": os.path.basename(in_path),
        "encoding_note": "文件为 GBK 编码; 已按 GBK 正确解码中文名",
        "schema": "AP203 CONFIG_CONTROL_DESIGN",
        "entity_count": len(ents),
        "product_count": len(product_name),
        "assembly_links": len(nauo),
        "tree": trees
    }

    def md_of(node, depth=0):
        pad = "  " * depth
        origin = f"  摆放=({node['placement'][0]},{node['placement'][1]},{node['placement'][2]})" if node['placement'] else ""
        line = f"{pad}- **{node['name']}**  (pd#{node['pd_id']}, 实体数={node['solids']}, 面数={node['faces']}{origin})"
        out = [line]
        if node['bodies']:
            out.append(f"{pad}    - 实体: " + "; ".join(node['bodies']))
        for c in node['children']:
            out.extend(md_of(c, depth+1))
        return out

    md = ["# 装配体 BOM: " + summary['file'], "",
          f"- 实体总数: {summary['entity_count']} | 零件数: {summary['product_count']} | 装配关联: {summary['assembly_links']}",
          "", "## 结构树", ""]
    for t in trees:
        md.extend(md_of(t))
    md_text = "\n".join(md) + "\n"

    print(md_text)
    if json_out:
        with open(json_out, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"[+] 写出 JSON: {json_out}")
    if md_out:
        with open(md_out, 'w', encoding='utf-8') as f:
            f.write(md_text)
        print(f"[+] 写出 Markdown: {md_out}")

if __name__ == '__main__':
    main()
