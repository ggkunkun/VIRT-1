# -*- coding: utf-8 -*-
"""统一 STEP 装配体/零件 BOM 提取器（纯标准库，无第三方依赖）。

覆盖 AP203(CONFIG_CONTROL_DESIGN) 与 AP214(AUTOMOTIVE_DESIGN)，自动探测编码
(GBK/UTF-8) 与 AP 版本，输出结构化 BOM：
  - 零件名（按文件编码正确解码，含中文）
  - 层级父子树（NAUO / PRODUCT_DEFINITION_USAGE）
  - 每个零件的实体数 / 面数 / 命名特征 / 包围盒
  - 装配体子零件摆放 4x4 位姿
  - AP 版本 + 编码 + 是否装配体

导出：JSON / Markdown / 紧凑 DSL / to_prompt_context()（大模型 prompt 注入）。
目标：把 8000 行 STEP 噪声几何压成 ~12 行模型可懂的结构描述，解决
「13.63B 模型读不懂装配体」的表征问题（P0 解法）。

实体解析层沿用 step_assembly_extractor.py 中已在 AP203 装配体上验证过的
raw 模型（含复杂实体 #id =( TYPE(...) ...) 支持）。
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 底层解析（沿用已验证实现，见 step_assembly_extractor.py）
# ---------------------------------------------------------------------------

ENTITY_RE = re.compile(rb'#(\d+)\s*=')


def to_str(b) -> str:
    """bytes -> str（GBK 优先），str 原样返回。"""
    if isinstance(b, str):
        return b
    for enc in ('gbk', 'gb18030', 'utf-8'):
        try:
            return b.decode(enc)
        except Exception:
            pass
    return b.decode('latin-1', errors='replace')


def detect_type(raw) -> str:
    """兼容 bytes / str；STEP 复杂实体 #id =( TYPE(...) ...) 需关键词特判。"""
    if isinstance(raw, bytes):
        if b'REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION' in raw:
            return 'REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION'
        mm = re.match(rb'^[\s(]*([A-Z][A-Z0-9_]*)', raw)
        return mm.group(1).decode('ascii') if mm else 'UNKNOWN'
    if 'REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION' in raw:
        return 'REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION'
    mm = re.match(r'^[\s(]*([A-Z][A-Z0-9_]*)', raw)
    return mm.group(1) if mm else 'UNKNOWN'


def parse_entities(data: bytes) -> Dict[int, bytes]:
    """扫描所有 #id = 实体，返回 {id: raw_bytes}（raw 含类型名与最外层括号内容）。
    括号平衡扫描同时兼容简单实体与 #id =( TYPE(...) ...) 复杂实体。"""
    entities: Dict[int, bytes] = {}
    for m in ENTITY_RE.finditer(data):
        eid = int(m.group(1))
        start = m.end()
        depth, i, instr, quote, n = 0, start, False, None, len(data)
        started = False
        while i < n:
            c = data[i:i + 1]
            if instr:
                if c == quote:
                    instr = False
            else:
                if c == b"'":
                    instr, quote = True, c
                elif c == b'(':
                    depth += 1
                    started = True
                elif c == b')':
                    depth -= 1
                    if started and depth == 0:
                        break
            i += 1
        # 闭括号本身也属于实体：切片必须含 data[i]，否则再序列化会缺右括号
        entities[eid] = data[start:i + 1] if i < n else data[start:i]
    return entities


def strip_outer(s: str) -> str:
    """剥掉实体首部类型名与最外层括号，返回内部顶层参数字符串。"""
    s = s.strip()
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
    return s[idx + 1:i]


def split_top(s) -> List[str]:
    """按顶层逗号切分参数（忽略字符串内的逗号与嵌套括号）。"""
    if isinstance(s, bytes):
        s = to_str(s)
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
            depth += 1
            cur += ch
        elif ch == ')':
            depth -= 1
            cur += ch
        elif ch == ',' and depth == 0:
            out.append(cur.strip())
            cur = ''
        else:
            cur += ch
    if cur.strip() != '' or out:
        out.append(cur.strip())
    return out


def ref_of(tok: str) -> Optional[int]:
    m = re.match(r'^#(\d+)$', tok.strip())
    return int(m.group(1)) if m else None


def strip_str(tok: str) -> str:
    tok = tok.strip()
    if len(tok) >= 2 and tok[0] in "\"'":
        return tok[1:-1]
    return tok


# ---------------------------------------------------------------------------
# 编码 / AP 探测
# ---------------------------------------------------------------------------

def detect_encoding(data: bytes) -> str:
    try:
        data.decode('utf-8')
        return 'utf-8'
    except UnicodeDecodeError:
        pass
    try:
        data.decode('gbk')
        return 'gbk'
    except UnicodeDecodeError:
        return 'latin-1'


def detect_ap(data: bytes) -> str:
    # 注意：SolidWorks 导出常见 "FILE_SCHEMA (( '...' ))"（FILE_SCHEMA 与 (( 间有空格），
    # 也有 "FILE_SCHEMA(('...')" 紧贴写法，故用 \s* 兼容两种。
    head = data[:4000]
    m = re.search(rb"FILE_SCHEMA\s*\(\(\s*'([^']+)'", head)
    if m:
        s = m.group(1).decode('latin-1', 'ignore')
        if '10303 203' in s or 'CONFIG_CONTROL_DESIGN' in s:
            return 'AP203'
        if '10303 214' in s or 'AUTOMOTIVE_DESIGN' in s:
            return 'AP214'
        if '10303 242' in s or 'AP242' in s or 'MANAGED_MODEL_BASED' in s:
            return 'AP242'
    # 兜底：FILE_DESCRIPTION (( 'STEP AP203' )) / 'AP214' 等
    d = re.search(rb"FILE_DESCRIPTION\s*\(\(\s*'([^']+)'", head)
    if d:
        s = d.group(1).decode('latin-1', 'ignore').upper()
        if 'AP203' in s or '203' in s:
            return 'AP203'
        if 'AP214' in s or '214' in s:
            return 'AP214'
        if 'AP242' in s or '242' in s:
            return 'AP242'
    return 'UNKNOWN'


BREP_TYPES = {'MANIFOLD_SOLID_BREP', 'BREP_WITH_VOIDS', 'FACETED_BREP'}


# ---------------------------------------------------------------------------
# StepBOM
# ---------------------------------------------------------------------------

class StepBOM:
    def __init__(self, step_path: str):
        self.path = step_path
        self.data = open(step_path, 'rb').read()
        self.encoding = detect_encoding(self.data)
        self.ap_version = detect_ap(self.data)
        self.raws = parse_entities(self.data)                 # id -> bytes
        # 按探测到的编码解码，避免 GBK 文件被误判 / UTF-8 中文被 gbk 解乱
        self.txt: Dict[int, str] = {
            eid: raw.decode(self.encoding, errors='replace') if self.encoding != 'latin-1'
            else to_str(raw)
            for eid, raw in self.raws.items()
        }

        # 索引
        self.product_name: Dict[int, str] = {}
        self.formation_to_product: Dict[int, int] = {}
        self.pd_to_formation: Dict[int, int] = {}
        self.pds_to_pd: Dict[int, int] = {}
        self.sdr: Dict[int, Tuple[int, int]] = {}
        self.rep_ctx: Dict[int, int] = {}
        self.rep_name: Dict[int, str] = {}
        self.abrep_breps: Dict[int, List[int]] = {}
        self.brep_name: Dict[int, str] = {}
        self.brep_shell: Dict[int, int] = {}
        self.closed_shell_faces: Dict[int, int] = {}
        self.rrwt: Dict[int, Tuple[List[int], Optional[int]]] = {}
        self.idt: Dict[int, Tuple[Optional[int], Optional[int]]] = {}
        self.axis2_point: Dict[int, int] = {}
        self.axis2_dirs: Dict[int, Tuple[Optional[int], Optional[int]]] = {}
        self.direction_vec: Dict[int, Tuple[float, float, float]] = {}
        self.point_coord: Dict[int, Tuple[float, float, float]] = {}
        self.nauo: List[Tuple[int, int]] = []
        self.ref_adj: Dict[int, List[int]] = {}

        self._build_index()
        # 派生
        self.pd_name = self._resolve_pd_names()
        self.pd_rep = self._resolve_pd_rep()
        self.tree = self._build_tree()

    # -- 索引构建 ---------------------------------------------------------
    def _build_index(self):
        for eid, raw in self.raws.items():
            s = self.txt[eid]
            p = split_top(strip_outer(s))
            t = detect_type(s)
            if t == 'PRODUCT':
                self.product_name[eid] = strip_str(p[0]) if p else ''
            elif t in ('PRODUCT_DEFINITION_FORMATION',
                       'PRODUCT_DEFINITION_FORMATION_WITH_SPECIFIED_SOURCE'):
                prod = ref_of(p[2]) if len(p) > 2 else None
                if prod:
                    self.formation_to_product[eid] = prod
            elif t == 'PRODUCT_DEFINITION':
                form = ref_of(p[2]) if len(p) > 2 else None
                if form:
                    self.pd_to_formation[eid] = form
            elif t == 'PRODUCT_DEFINITION_SHAPE':
                pd = ref_of(p[2]) if len(p) > 2 else None
                if pd:
                    self.pds_to_pd[eid] = pd
            elif t == 'SHAPE_DEFINITION_REPRESENTATION':
                pds, rep = ref_of(p[0]), ref_of(p[1])
                if pds is not None and rep is not None:
                    self.sdr[eid] = (pds, rep)
            elif t in ('SHAPE_REPRESENTATION', 'ADVANCED_BREP_SHAPE_REPRESENTATION'):
                self.rep_name[eid] = strip_str(p[0]) if p else ''
                ctx = None
                for tok in reversed(p):
                    ctx = ref_of(tok)
                    if ctx is not None:
                        break
                if ctx is not None:
                    self.rep_ctx[eid] = ctx
                if t == 'ADVANCED_BREP_SHAPE_REPRESENTATION' and len(p) > 1:
                    inner = p[1].strip()
                    if inner.startswith('(') and inner.endswith(')'):
                        inner = inner[1:-1]
                    breps = [ref_of(tok) for tok in re.split(r'\s*,\s*', inner) if ref_of(tok)]
                    self.abrep_breps[eid] = [b for b in breps if b is not None]
            elif t in BREP_TYPES:
                self.brep_name[eid] = strip_str(p[0]) if p else ''
                sh = ref_of(p[1]) if len(p) > 1 else None
                if sh:
                    self.brep_shell[eid] = sh
            elif t == 'CLOSED_SHELL':
                if len(p) > 1:
                    inner = p[1].strip()
                    if inner.startswith('(') and inner.endswith(')'):
                        inner = inner[1:-1]
                    self.closed_shell_faces[eid] = len(
                        [tok for tok in re.split(r'\s*,\s*', inner) if ref_of(tok)])
            elif t == 'REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION':
                m = re.search(r'WITH_TRANSFORMATION\s*\(\s*#(\d+)\s*\)', s)
                idt_id = int(m.group(1)) if m else None
                refs = [int(x) for x in re.findall(r'#(\d+)', s)]
                self.rrwt[eid] = (refs, idt_id)
            elif t == 'ITEM_DEFINED_TRANSFORMATION':
                i1 = ref_of(p[2]) if len(p) > 2 else None
                i2 = ref_of(p[3]) if len(p) > 3 else None
                if i1 and i2:
                    self.idt[eid] = (i1, i2)
            elif t == 'AXIS2_PLACEMENT_3D':
                pt = ref_of(p[1]) if len(p) > 1 else None
                if pt is not None:
                    self.axis2_point[eid] = pt
                ax = ref_of(p[2]) if len(p) > 2 else None
                rd = ref_of(p[3]) if len(p) > 3 else None
                self.axis2_dirs[eid] = (ax, rd)
            elif t == 'DIRECTION':
                nums = re.findall(r'-?\d+\.?\d*(?:[eE][+-]?\d+)?', ' '.join(p))
                if len(nums) >= 3:
                    self.direction_vec[eid] = tuple(round(float(x), 9) for x in nums[:3])
            elif t == 'CARTESIAN_POINT':
                nums = re.findall(r'-?\d+\.?\d*(?:[eE][+-]?\d+)?', ' '.join(p))
                if len(nums) >= 3:
                    self.point_coord[eid] = tuple(round(float(x), 4) for x in nums[:3])
            elif t in ('NEXT_ASSEMBLY_USAGE_OCCURRENCE', 'PRODUCT_DEFINITION_USAGE'):
                parent = ref_of(p[3]) if len(p) > 3 else None
                child = ref_of(p[4]) if len(p) > 4 else None
                if parent and child:
                    self.nauo.append((parent, child))

        # 引用邻接（包围盒 BFS 用）
        for eid, s in self.txt.items():
            self.ref_adj[eid] = [int(x) for x in re.findall(r'#(\d+)', s)]

    # -- PD 名 / PD->rep --------------------------------------------------
    def _resolve_pd_names(self) -> Dict[int, str]:
        pd_name = {}
        for pd, form in self.pd_to_formation.items():
            prod = self.formation_to_product.get(form)
            pd_name[pd] = self.product_name.get(prod, '') if prod else ''
        return pd_name

    def _name_of_pd(self, pd: int) -> str:
        nm = self.pd_name.get(pd, '')
        if nm:
            return nm
        for (_sdr, (pds, rep)) in self.sdr.items():
            if self.pds_to_pd.get(pds) == pd and self.rep_name.get(rep):
                return self.rep_name[rep]
        return f'<pd#{pd}>'

    def _resolve_pd_rep(self) -> Dict[int, int]:
        pd_rep = {}
        for (_sid, (pds, rep)) in self.sdr.items():
            pd = self.pds_to_pd.get(pds)
            if pd is not None and rep in self.rep_name:
                pd_rep[pd] = rep
        return pd_rep

    # -- 几何归属 ---------------------------------------------------------
    def _geometry_of_pd(self, pd: int) -> Tuple[List[int], int, List[str]]:
        rep = self.pd_rep.get(pd)
        if rep is None:
            return [], 0, []
        ctx = self.rep_ctx.get(rep)
        solids, faces, body_names = [], 0, []
        for ab_id, brefs in self.abrep_breps.items():
            if self.rep_ctx.get(ab_id) == ctx:
                for b in brefs:
                    if b in self.brep_name:
                        solids.append(b)
                        faces += self.closed_shell_faces.get(self.brep_shell.get(b, -1), 0)
                        if self.brep_name[b]:
                            body_names.append(self.brep_name[b])
        return solids, faces, body_names

    def _bbox_of(self, breps: List[int]) -> Optional[List[float]]:
        seen, pts = set(), []
        stack = [self.brep_shell[b] for b in breps if b in self.brep_shell]
        steps = 0
        while stack and steps < 6000:
            nxt = []
            for eid in stack:
                if eid in seen:
                    continue
                seen.add(eid)
                if eid in self.point_coord:
                    pts.append(self.point_coord[eid])
                nxt.extend(self.ref_adj.get(eid, []))
            stack = nxt
            steps += 1
        if not pts:
            return None
        xs, ys, zs = zip(*pts)
        return [min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)]

    # -- 位姿 -------------------------------------------------------------
    def _frame_of(self, axis2_id: int) -> Tuple[List[List[float]], List[float]]:
        """AXIS2_PLACEMENT_3D -> (R 3x3 行主序, 平移 mm)。
        STEP 约定 axis=局部 Z、ref_direction=局部 X；缺省 (0,0,1)/(1,0,0)。"""
        def _norm(v):
            n = math.sqrt(sum(c * c for c in v))
            return tuple(c / n for c in v) if n > 1e-12 else None

        ax, rd = self.axis2_dirs.get(axis2_id, (None, None))
        z = _norm(self.direction_vec.get(ax, (0.0, 0.0, 1.0)) if ax else (0.0, 0.0, 1.0)) \
            or (0.0, 0.0, 1.0)
        x = self.direction_vec.get(rd, (1.0, 0.0, 0.0)) if rd else (1.0, 0.0, 0.0)
        dot = sum(x[i] * z[i] for i in range(3))
        x = _norm(tuple(x[i] - dot * z[i] for i in range(3)))
        if x is None:  # ref_direction 与 axis 平行：任取正交基
            x = (1.0, 0.0, 0.0) if abs(z[0]) < 0.9 else (0.0, 1.0, 0.0)
            dot = sum(x[i] * z[i] for i in range(3))
            x = _norm(tuple(x[i] - dot * z[i] for i in range(3))) or (1.0, 0.0, 0.0)
        y = (z[1] * x[2] - z[2] * x[1],
             z[2] * x[0] - z[0] * x[2],
             z[0] * x[1] - z[1] * x[0])
        pt = self.axis2_point.get(axis2_id)
        t = list(self.point_coord.get(pt, (0.0, 0.0, 0.0))) if pt else [0.0, 0.0, 0.0]
        return [[x[0], y[0], z[0]],
                [x[1], y[1], z[1]],
                [x[2], y[2], z[2]]], t

    def _placement_between(self, child_ax: int, parent_ax: Optional[int]) -> Dict[str, Any]:
        """子件在父件坐标系下的相对位姿：inv(F2)·F1（含旋转，非纯平移）。"""
        m1, t1 = self._frame_of(child_ax)
        m2, t2 = self._frame_of(parent_ax) if parent_ax is not None else (
            [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]], [0.0, 0.0, 0.0])
        r = [[sum(m2[k][i] * m1[k][j] for k in range(3)) for j in range(3)]
             for i in range(3)]
        d = [t1[i] - t2[i] for i in range(3)]
        t = [sum(m2[k][i] * d[k] for k in range(3)) for i in range(3)]
        trace = r[0][0] + r[1][1] + r[2][2]
        angle = math.degrees(math.acos(max(-1.0, min(1.0, (trace - 1.0) / 2.0))))
        return {
            "origin_mm": [round(c, 4) for c in t],
            "matrix": [[round(r[i][j], 9) for j in range(3)] + [round(t[i], 4)]
                       for i in range(3)] + [[0.0, 0.0, 0.0, 1.0]],
            "rotation_deg": round(angle, 4),
            "identity_rotation": angle < 1e-6,
        }

    def _child_rep_origins(self) -> Dict[int, Optional[Dict[str, Any]]]:
        # 复刻旧版：RRWT 的 rep1/rep2 需在主循环之后解析（实体出现早于被引用 rep）
        all_child = {c for (_p, c) in self.nauo}
        roots = [pd for pd in self.pd_rep if pd not in all_child] or [
            pd for pd in self.pd_name if pd not in all_child]
        root_rep = self.pd_rep.get(roots[0]) if roots else None

        out: Dict[int, Optional[Dict[str, Any]]] = {}
        for _eid, (refs, idt_id) in self.rrwt.items():
            if idt_id is None:
                continue
            reps = [r for r in refs if r in self.rep_name]
            child_rep = None
            for r in reps:
                if r in self.pd_rep.values() and r != root_rep:
                    child_rep = r
                    break
            if child_rep is None:
                continue
            i1, i2 = self.idt.get(idt_id, (None, None))
            if i1 is None:
                continue
            out[child_rep] = self._placement_between(i1, i2)
        return out

    # -- 树 ---------------------------------------------------------------
    def _build_tree(self) -> List[Dict[str, Any]]:
        children_map: Dict[int, List[int]] = {}
        all_child = set()
        for parent, child in self.nauo:
            children_map.setdefault(parent, []).append(child)
            all_child.add(child)
        roots = [pd for pd in self.pd_rep if pd not in all_child] or [
            pd for pd in self.pd_name if pd not in all_child]
        origins = self._child_rep_origins()

        def build(pd: int) -> Dict[str, Any]:
            solids, faces, bodies = self._geometry_of_pd(pd)
            rep = self.pd_rep.get(pd)
            placement = origins.get(rep) if rep is not None else None
            bbox = self._bbox_of(solids)
            return {
                "pd_id": pd,
                "name": self._name_of_pd(pd),
                "solids": len(solids),
                "faces": faces,
                "bodies": bodies,
                "features": bodies,
                "bbox": [round(v, 4) for v in bbox] if bbox else None,
                "placement": placement,
                "children": [build(c) for c in children_map.get(pd, [])],
            }

        return [build(r) for r in roots]

    # -- 导出 -------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": "ok",
            "source": os.path.basename(self.path),
            "ap_version": self.ap_version,
            "encoding": self.encoding,
            "is_assembly": len(self.nauo) > 0,
            "entity_count": len(self.raws),
            "product_count": len(self.product_name),
            "component_count": len(self.nauo),
            "tree": self.tree,
        }

    def to_markdown(self) -> str:
        d = self.to_dict()
        lines = [f"# 装配体 BOM: {d['source']}", "",
                 f"- AP 版本: {d['ap_version']} | 编码: {d['encoding']} | "
                 f"实体总数: {d['entity_count']} | "
                 f"装配体: {'是' if d['is_assembly'] else '否(单零件)'} | "
                 f"零件数: {d['product_count']} | 装配关联: {d['component_count']}",
                 "", "## 结构树", ""]

        def walk(node, depth=0):
            pad = '  ' * depth
            line = f"{pad}- **{node['name']}**  (pd#{node['pd_id']}, " \
                   f"实体数={node['solids']}, 面数={node['faces']}"
            if node.get('placement') and node['placement'].get('origin_mm'):
                o = node['placement']['origin_mm']
                line += f", 摆放=({o[0]},{o[1]},{o[2]})"
            line += ")"
            out = [line]
            if node.get('features'):
                out.append(f"{pad}    - 实体: " + '; '.join(node['features']))
            if node.get('bbox'):
                b = node['bbox']
                out.append(f"{pad}    - 包围盒: [{b[0]},{b[1]},{b[2]}] ~ "
                           f"[{b[3]},{b[4]},{b[5]}]")
            for c in node['children']:
                out.extend(walk(c, depth + 1))
            return out

        for root in d['tree']:
            lines.extend(walk(root))
        return '\n'.join(lines) + '\n'

    def to_dsl(self) -> str:
        """紧凑、token 友好、模型易读的 DSL。"""
        d = self.to_dict()
        parts = [f'STEP[{d["ap_version"]}]{{ file="{d["source"]}" '
                 f'enc="{d["encoding"]}" parts={d["product_count"]} '
                 f'assembly={"true" if d["is_assembly"] else "false"} }}']

        def walk(node, depth=0):
            pad = '  ' * depth
            feat = json.dumps(node.get('features', []), ensure_ascii=False)
            g = f'{pad}PART[{node["name"]}]{{ solids={node["solids"]} ' \
                f'faces={node["faces"]} features={feat}'
            if node.get('bbox'):
                b = node['bbox']
                g += f' bbox=[{b[0]},{b[1]},{b[2]},{b[3]},{b[4]},{b[5]}]'
            g += ' }'
            if node.get('placement') and node['placement'].get('origin_mm'):
                o = node['placement']['origin_mm']
                g += f' @ T({o[0]},{o[1]},{o[2]})'
                if not node['placement'].get('identity_rotation', True):
                    g += f' R({node["placement"]["rotation_deg"]}deg)'
            if node.get('children'):
                parts.append(f'{pad}ASSEMBLY {json.dumps(node["name"], ensure_ascii=False)} {{')
                for c in node['children']:
                    walk(c, depth + 1)
                parts.append(f'{pad}}}')
            else:
                parts.append(g)

        for root in d['tree']:
            walk(root)
        return '\n'.join(parts)

    def to_prompt_context(self) -> str:
        """直接注入大模型 prompt 的结构化 + 自然语言描述。"""
        d = self.to_dict()
        if d['is_assembly']:
            head = (f"该 STEP 文件为装配体（{d['ap_version']}，编码 {d['encoding']}），"
                    f"含 {d['product_count']} 个零件、{d['component_count']} 处装配关系。"
                    f"原始文件 {d['entity_count']} 个实体，结构摘要如下：")
        else:
            head = (f"该 STEP 文件为单一零件（{d['ap_version']}，编码 {d['encoding']}），"
                    f"原始文件 {d['entity_count']} 个实体，结构摘要如下：")
        lines = [head, '', '```dsl', self.to_dsl(), '```', '', '自然语言摘要：']
        counter = [0]

        def walk(node, depth=0):
            counter[0] += 1
            pad = '  ' * depth
            feat = '、'.join([f for f in node.get('features', []) if f]) or '（无命名特征）'
            pos = ''
            if node.get('placement') and node['placement'].get('origin_mm'):
                o = node['placement']['origin_mm']
                pos = f"，摆放坐标 ({o[0]}, {o[1]}, {o[2]}) mm"
                if not node['placement'].get('identity_rotation', True):
                    pos += f"，绕自身坐标系旋转 {node['placement']['rotation_deg']}°"
            kids = node.get('children', [])
            if kids and node['solids'] == 0:
                # 装配体根容器：不作为零件描述，避免"0 实体"噪声
                lines.append(f"{pad}{counter[0]}. 装配体「{node['name']}」为总装容器，"
                             f"下含 {len(kids)} 个子零件：")
            else:
                lines.append(f"{pad}{counter[0]}. 零件「{node['name']}」由 "
                             f"{node['solids']} 个实体（共 {node['faces']} 个面）构成，"
                             f"特征：{feat}{pos}。")
            for c in kids:
                walk(c, depth + 1)

        for root in d['tree']:
            walk(root)
        return '\n'.join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    argv = argv or sys.argv[1:]
    if not argv:
        print('用法: python3 step_bom.py <file.step> [--json out.json] [--md out.md] '
              '[--dsl out.dsl] [--ctx]')
        return 1
    path = argv[0]
    opts: Dict[str, str] = {}
    show_ctx = False
    for i, a in enumerate(argv[1:], 1):
        if a in ('--json', '--md', '--dsl') and i < len(argv):
            opts[a] = argv[i + 1]
        elif a == '--ctx':
            show_ctx = True
    bom = StepBOM(path)
    d = bom.to_dict()
    print(f"[+] 解析实体总数: {d['entity_count']}")
    print(f"[+] AP={d['ap_version']} enc={d['encoding']} "
          f"assembly={d['is_assembly']} parts={d['product_count']} "
          f"links={d['component_count']}")
    print()
    print(bom.to_markdown())
    if '--json' in opts:
        with open(opts['--json'], 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        print(f"[+] 写出 JSON: {opts['--json']}")
    if '--md' in opts:
        with open(opts['--md'], 'w', encoding='utf-8') as f:
            f.write(bom.to_markdown())
        print(f"[+] 写出 Markdown: {opts['--md']}")
    if '--dsl' in opts:
        with open(opts['--dsl'], 'w', encoding='utf-8') as f:
            f.write(bom.to_dsl())
        print(f"[+] 写出 DSL: {opts['--dsl']}")
    if show_ctx:
        print(bom.to_prompt_context())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
