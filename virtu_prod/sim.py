# -*- coding: utf-8 -*-
"""NC 解析 + 运动学扫掠 + 碰撞/过切/超程/节拍 实测。

口径（诚实边界）：
  * 碰撞是“刀尖轨迹 + 刀轴（B/C 反解）+ 刀具/刀柄圆柱”对工件坐标系下夹具/毛坯/设计网格的
    最近距离实测，采样步长可配；不是 VERICUT 的逐帧布尔材料去除。
  * 超程按机床直线轴行程（刀尖点）与 B/C 硬限位判定；B/C 旋转后的机床坐标用
    R_B(B)·R_C(C)·(p_work + (0,0,stock_top)) 计算（转台式 B/C，B 在外、C 在内）。
  * 节拍由路径长度 / 进给 + 快移 + 换刀时间推导，不含机床加减速与换刀确认耗时。
"""
from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import trimesh

_WORD = re.compile(r"([A-Za-z])\s*=?\s*([+-]?\d+(?:\.\d+)?)")
_ORI = re.compile(r"([ABC])3=([+-]?\d+(?:\.\d+)?)")
_COMMENT = re.compile(r"\(([^)]*)\)|;([^\n]*)")


def _strip_comments(line: str) -> Tuple[str, str]:
    comments = []
    for m in _COMMENT.finditer(line):
        comments.append(m.group(1) if m.group(1) is not None else m.group(2))
    code = _COMMENT.sub("", line)
    return code.strip(), " ".join(c.strip() for c in comments if c)


@dataclass
class Move:
    kind: str
    x: float
    y: float
    z: float
    b: float
    c: float
    i: Optional[float] = None
    j: Optional[float] = None
    f: Optional[float] = None
    line: int = 0
    op: str = ""
    tool: Optional[str] = None


@dataclass
class Parsed:
    dialect: str
    moves: List[Move] = field(default_factory=list)
    ops: List[Dict] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    stats: Dict = field(default_factory=dict)
    raw: str = ""


def parse(text: str, dialect: str) -> Parsed:
    p = Parsed(dialect=dialect, raw=text)
    motion = 0
    absolute = True
    x = y = z = 0.0
    b = c = 0.0
    feed: Optional[float] = None
    tool: Optional[str] = None
    current_op = "PROGRAM"
    rtcp = False
    comp = False
    spindle = False
    tool_changes = 0
    for ln, raw in enumerate(text.splitlines(), 1):
        code, comment = _strip_comments(raw)
        if not code or code.startswith("%"):
            continue
        if comment:
            m = re.search(r"===\s*([A-Z0-9\-]+)\s*:", comment)
            if m:
                current_op = m.group(1)
                p.ops.append({"op": current_op, "start_line": ln})
            if "TCPM ON" in comment:
                rtcp = True
        if "TRAORI" in code:
            rtcp = True
        if "TRAFOOF" in code:
            rtcp = False
        ori = dict((k, float(v)) for k, v in _ORI.findall(code))
        code2 = _ORI.sub("", code)
        words = [(k.upper(), float(v)) for k, v in _WORD.findall(code2)]
        wd: Dict[str, float] = {}
        gs: List[float] = []
        ms: List[str] = []
        for k, v in words:
            if k == "G":
                gs.append(v)
            elif k == "M":
                ms.append(f"M{int(v):02d}")
            else:
                wd[k] = v
        if "T" in wd:
            tool = f"T{int(wd['T'])}"
            if "M06" in ms or "M6" in code.replace(" ", ""):
                tool_changes += 1
        for g in gs:
            gi = int(g)
            if g in (0.0, 1.0, 2.0, 3.0):
                motion = gi
            elif g == 43.0:
                comp = True
            elif g == 43.4:
                comp = True
                rtcp = True
            elif g == 49.0:
                comp = False
                rtcp = False
            elif g == 91.0:
                absolute = False
            elif g == 90.0:
                absolute = True
        if "M03" in ms or "M04" in ms:
            spindle = True
        if "M05" in ms:
            spindle = False
        if "F" in wd:
            feed = wd["F"]
        if "G28" in code or "G53" in code:
            continue
        if not any(k in wd for k in ("X", "Y", "Z", "B", "C")):
            continue
        nx = (x + wd["X"]) if (not absolute and "X" in wd) else wd.get("X", x)
        ny = (y + wd["Y"]) if (not absolute and "Y" in wd) else wd.get("Y", y)
        nz = (z + wd["Z"]) if (not absolute and "Z" in wd) else wd.get("Z", z)
        nb = (b + wd["B"]) if (not absolute and "B" in wd) else wd.get("B", b)
        nc = (c + wd["C"]) if (not absolute and "C" in wd) else wd.get("C", c)
        has_xy = "X" in wd or "Y" in wd
        if motion in (1, 2, 3) and not spindle:
            p.errors.append(f"L{ln}: 切削进给时主轴未启动")
        if motion in (1, 2, 3) and feed is None:
            p.errors.append(f"L{ln}: 切削进给无 F")
        kind = {0: "rapid", 1: "feed", 2: "arc_cw", 3: "arc_ccw"}[motion]
        p.moves.append(Move(kind, nx, ny, nz, nb, nc,
                            wd.get("I"), wd.get("J"), feed, ln, current_op, tool))
        x, y, z, b, c = nx, ny, nz, nb, nc
    p.stats["lines"] = len(text.splitlines())
    p.stats["moves"] = len(p.moves)
    p.stats["rtcp_used"] = rtcp
    p.stats["ops"] = [o["op"] for o in p.ops]
    p.stats["tool_changes"] = tool_changes
    return p


def _tool_axis(b: float, c: float) -> np.ndarray:
    br, cr = math.radians(b), math.radians(c)
    return np.array([-math.sin(br) * math.cos(cr), math.sin(br) * math.sin(cr), math.cos(br)])


def _arc_points(m: Move, prev: Move, step_mm: float) -> Tuple[np.ndarray, float]:
    cx, cy = prev.x + (m.i or 0.0), prev.y + (m.j or 0.0)
    r0 = math.hypot(prev.x - cx, prev.y - cy)
    a0 = math.atan2(prev.y - cy, prev.x - cx)
    a1 = math.atan2(m.y - cy, m.x - cx)
    if abs(m.x - prev.x) < 1e-9 and abs(m.y - prev.y) < 1e-9:
        a1 = a0 + (2 * math.pi if m.kind == "arc_cw" else -2 * math.pi)
    elif m.kind == "arc_cw":
        while a1 >= a0:
            a1 -= 2 * math.pi
    else:
        while a1 <= a0:
            a1 += 2 * math.pi
    arc_len = abs(a1 - a0) * r0 + abs(m.z - prev.z)
    n = max(2, min(4000, int(arc_len / max(step_mm, 0.1)) + 2))
    t = np.linspace(0.0, 1.0, n)
    ang = a0 + (a1 - a0) * t
    xs = cx + r0 * np.cos(ang)
    ys = cy + r0 * np.sin(ang)
    zs = prev.z + (m.z - prev.z) * t
    return np.column_stack([xs, ys, zs]), arc_len


def sample_path(parsed: Parsed, step_mm: float = 1.0) -> Dict:
    """返回逐点：世界坐标(work+stock_top? 由调用方加) + B/C + 行号 + 操作 + 进给。"""
    pts: List[Tuple[float, float, float, float, float, float, int, str, str]] = []
    length_by_op: Dict[str, float] = {}
    time_by_op: Dict[str, float] = {}
    cut_time_by_op: Dict[str, float] = {}
    total_len = 0.0
    prev: Optional[Move] = None
    for m in parsed.moves:
        if prev is None:
            prev = m
            continue
        if m.kind in ("arc_cw", "arc_ccw"):
            arr, seg_len = _arc_points(m, prev, step_mm)
        else:
            d = np.array([m.x - prev.x, m.y - prev.y, m.z - prev.z])
            seg_len = float(np.linalg.norm(d))
            n = max(2, int(seg_len / max(step_mm, 0.1)) + 2)
            t = np.linspace(0.0, 1.0, n)
            arr = np.column_stack([prev.x + d[0] * t, prev.y + d[1] * t, prev.z + d[2] * t])
        if seg_len <= 1e-9:
            prev = m
            continue
        op = m.op or "PROGRAM"
        length_by_op[op] = length_by_op.get(op, 0.0) + seg_len
        f = m.f or 100.0
        rate = 20000.0 if m.kind == "rapid" else max(f, 1.0)
        time_by_op[op] = time_by_op.get(op, 0.0) + (seg_len / rate) * 60.0
        if m.kind != "rapid":
            cut_time_by_op[op] = cut_time_by_op.get(op, 0.0) + (seg_len / rate) * 60.0
        total_len += seg_len
        for k in range(0, len(arr), max(1, len(arr) // 400)):
            px, py, pz = arr[k]
            pts.append((float(px), float(py), float(pz), m.b, m.c, seg_len, m.line,
                        op, m.tool or ""))
        prev = m
    if len(pts) > 60000:
        keep = len(pts) // 60000 + 1
        pts = pts[::keep]
    return {"points": pts, "length_by_op": length_by_op, "time_by_op": time_by_op,
            "cut_time_by_op": cut_time_by_op,
            "total_length_mm": total_len, "basis": "measured (NC parse + polyline)"}


def _resolve(path: str, extra: List[Path]) -> Optional[Path]:
    p = Path(path)
    if p.exists():
        return p
    for d in extra:
        q = d / p.name
        if q.exists():
            return q
    return None


def _load_mesh(path: Path) -> Optional[trimesh.Trimesh]:
    """先按标准网格加载；失败则按 VERICUT 文本模型格式解析（vise.ply/mandrel.ply）。"""
    try:
        return trimesh.load(str(path), force="mesh")
    except Exception:  # noqa: BLE001
        pass
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:  # noqa: BLE001
        return None
    if not lines or not lines[0].startswith("VERICUT-model"):
        return None
    verts, faces = [], []
    i = 0
    while i < len(lines):
        if lines[i].strip() == "3":
            try:
                tri = [tuple(float(x) for x in lines[i + k].split()[:3]) for k in (1, 2, 3)]
            except Exception:  # noqa: BLE001
                break
            base = len(verts)
            verts.extend(tri)
            faces.append((base, base + 1, base + 2))
            i += 7
        else:
            i += 1
    if not faces:
        return None
    return trimesh.Trimesh(vertices=np.array(verts), faces=np.array(faces), process=True)


def load_scene(project: Path) -> Dict[str, trimesh.Trimesh]:
    """从 .vcproject 读取 Fixture/Stock/Design 网格并换算到世界坐标。"""
    root = ET.parse(project).getroot()
    libs = [Path(r"E:\library"), Path(r"E:\windows64"), Path(r"E:\samples\Support_files")]
    attach = -100.0
    mfile = root.find(".//Machine/File")
    if mfile is not None and mfile.text:
        mp = _resolve(mfile.text, libs)
        if mp:
            mroot = ET.parse(mp).getroot()
            for comp in mroot.iter("Component"):
                if comp.get("Name") == "Attach":
                    pos = comp.find("Position")
                    if pos is not None and pos.get("Z"):
                        attach = float(pos.get("Z"))
    out: Dict[str, trimesh.Trimesh] = {}
    for name in ("Fixture", "Stock", "Design"):
        comp = None
        for c in root.iter("Component"):
            if c.get("Name") == name:
                comp = c
                break
        if comp is None:
            continue
        meshes = []
        seen = set()
        for poly in comp.findall("Poly"):
            f = poly.find("File")
            mm = poly.find("ModelMatrix/MatrixOrigin")
            if f is None or not f.text:
                continue
            fp = _resolve(f.text, libs + [project.parent])
            if fp is None:
                continue
            key = (str(fp), mm.get("X"), mm.get("Y"), mm.get("Z")) if mm is not None \
                else (str(fp),)
            if key in seen:
                continue
            seen.add(key)
            m = _load_mesh(fp)
            if m is None:
                continue
            if mm is not None:
                m = m.copy()
                m.apply_translation([float(mm.get("X", 0)), float(mm.get("Y", 0)),
                                     float(mm.get("Z", 0)) + attach])
            meshes.append(m)
        if meshes:
            out[name] = trimesh.util.concatenate(meshes) if len(meshes) > 1 else meshes[0]
    return out


def _closest(mesh: trimesh.Trimesh, pts: np.ndarray, chunk: int = 3000) -> np.ndarray:
    if len(pts) == 0:
        return np.zeros(0)
    out = []
    for i in range(0, len(pts), chunk):
        _, dist, _ = trimesh.proximity.closest_point(mesh, pts[i:i + chunk])
        out.append(np.asarray(dist))
    return np.concatenate(out)


def _sdf(mesh: trimesh.Trimesh, pts: np.ndarray, chunk: int = 3000) -> np.ndarray:
    """有符号间隙（+ 外部 / − 内部）。

    用 trimesh 的射线奇偶 signed_distance（+ 内部），取负号转成“间隙”。
    对多壳体（hub+cover+16 叶片）网格，奇偶法比最近面法向法稳定；已在
    已知内部/外部样本上标定（见 tests/test_production_system.py）。
    """
    if len(pts) == 0:
        return np.zeros(0)
    out = []
    for i in range(0, len(pts), chunk):
        sd = trimesh.proximity.signed_distance(mesh, pts[i:i + chunk])
        out.append(-np.asarray(sd))
    return np.concatenate(out)


def _box_sdf(pts: np.ndarray, lo, hi) -> np.ndarray:
    c = (np.asarray(lo) + np.asarray(hi)) / 2.0
    h = (np.asarray(hi) - np.asarray(lo)) / 2.0
    q = np.abs(pts - c) - h
    return np.linalg.norm(np.maximum(q, 0.0), axis=1) + \
        np.minimum(np.max(q, axis=1), 0.0)


def _cyl_sdf(pts: np.ndarray, r: float, z0: float, z1: float) -> np.ndarray:
    dr = np.hypot(pts[:, 0], pts[:, 1]) - r
    dz = np.maximum(z0 - pts[:, 2], pts[:, 2] - z1)
    return np.linalg.norm(np.maximum(np.stack([dr, dz], 1), 0.0), axis=1) + \
        np.minimum(np.maximum(dr, dz), 0.0)


# 夹具解析体（与 scripts/verify_scene_physics.py 的 scene_op1/scene_op3 同源）
FIXTURE_PRIMS = {
    "OP1": [("box", (-180.0, -180.0, -100.0), (180.0, 180.0, 70.0)),
            ("box", (-172.0, -170.0, 70.0), (-132.05, 170.0, 94.0)),
            ("box", (132.05, -170.0, 70.0), (172.0, 170.0, 94.0))],
    "OP3": [("cyl", 150.0, -100.0, -88.0),
            ("cyl", 60.0, -88.0, 48.0),
            ("cyl", 100.0, 48.0, 60.0),
            ("cyl", 38.0, 60.0, 120.0)],
}


def _fixture_sdf(station: str, pts: np.ndarray) -> np.ndarray:
    out = np.full(len(pts), np.inf)
    for prim in FIXTURE_PRIMS[station]:
        if prim[0] == "box":
            d = _box_sdf(pts, prim[1], prim[2])
        else:
            d = _cyl_sdf(pts, prim[1], prim[2], prim[3])
        out = np.minimum(out, d)
    return out


def _tool_surface(tip: np.ndarray, axis: np.ndarray, r: float, length: float,
                  n_ang: int = 6) -> np.ndarray:
    a = axis / max(float(np.linalg.norm(axis)), 1e-9)
    u = np.cross(a, np.array([0.0, 0.0, 1.0]))
    if float(np.linalg.norm(u)) < 1e-6:
        u = np.array([1.0, 0.0, 0.0])
    u = u / np.linalg.norm(u)
    v = np.cross(a, u)
    ang = np.linspace(0.0, 2 * math.pi, n_ang, endpoint=False)
    ring = np.cos(ang)[:, None] * u + np.sin(ang)[:, None] * v
    pts = [tip]
    for t in (0.0, 0.5, 1.0):
        pts.extend(tip + a * (length * t) + r * ring)
    return np.asarray(pts)


def audit(parsed: Parsed, scene: Dict[str, trimesh.Trimesh], machine: Dict,
          tool_by_id: Dict[str, dict], stock_top: float, cfg: Dict,
          station: str = "OP1") -> Dict:
    """碰撞 / 过切 / 超程 实测（刀具为圆柱体，按表面点求符号距离）。"""
    step = float(cfg.get("sample_step_mm", 2.0))
    gouge_tol = float(cfg.get("gouge_tolerance_mm", 0.05))
    holder_margin = float(cfg.get("holder_clearance_mm", 1.0))
    sp = sample_path(parsed, step)
    meta = [(b, c, line, op, tool) for *_x, b, c, _l, line, op, tool in sp["points"]]
    fixture_key = "OP3" if station == "OP3" else "OP1"
    design = scene.get("Design")
    stock = scene.get("Stock")
    default_tool = next(iter(tool_by_id.values()))

    tips = np.array([(p[0], p[1], p[2] + stock_top) for p in sp["points"]]) \
        if sp["points"] else np.zeros((0, 3))
    min_clear = {"fixture": math.inf, "design": math.inf, "design_surface": math.inf,
                 "stock_holder": math.inf}
    min_where = {}
    violations: List[Dict] = []
    checks: List[Dict] = []

    if len(tips):
        # 刀具表面点（全部采样点）用于夹具与刀柄
        all_pts = []
        for i, (px, py, pz) in enumerate(tips):
            b, c = meta[i][0], meta[i][1]
            t = tool_by_id.get(meta[i][4], default_tool)
            all_pts.append(_tool_surface(np.array([px, py, pz]), _tool_axis(b, c),
                                         t["diameter"] / 2.0, t["gauge_length"]))
        surf = np.array(all_pts)                       # (n, 19, 3)
        flat = surf.reshape(-1, 3)
        fclear = _fixture_sdf(fixture_key, flat).reshape(len(tips), -1).min(axis=1)
        i = int(np.argmin(fclear))
        min_clear["fixture"] = float(fclear[i])
        min_where["fixture"] = {"line": meta[i][2], "op": meta[i][3],
                                "world": tips[i].round(2).tolist()}
        for k in np.where(fclear < 0.0)[0][:20]:
            violations.append({"type": "FIXTURE_COLLISION", "line": meta[k][2],
                               "clearance_mm": round(float(fclear[k]), 3),
                               "world": tips[k].round(2).tolist()})

        # 设计过切：刀具表面点进入实体（符号距离为负）
        if design is not None:
            idx = np.arange(0, len(tips), 5)
            dclear = np.full(len(idx), math.inf)
            dpts = surf[idx].reshape(-1, 3)
            sd = _sdf(design, dpts)
            sd2 = sd.reshape(len(idx), -1).min(axis=1)
            dclear = sd2
            j = int(np.argmin(dclear))
            min_clear["design_surface"] = float(dclear[j])
            min_where["design"] = {"line": meta[idx[j]][2], "op": meta[idx[j]][3],
                                   "world": tips[idx[j]].round(2).tolist()}
            for k in np.where(dclear < -gouge_tol)[0][:20]:
                violations.append({"type": "DESIGN_GOUGE",
                                   "line": meta[idx[k]][2],
                                   "penetration_mm": round(float(dclear[k]), 3),
                                   "world": tips[idx[k]].round(2).tolist()})
            tip_sd = _sdf(design, tips)
            min_clear["design"] = float(tip_sd.min())
        else:
            min_clear["design"] = math.inf
            min_clear["design_surface"] = math.inf

        # 刀柄 vs 毛坯（刀柄为 gauge 之上的圆柱；毛坯按包围盒）
        if stock is not None:
            lo, hi = stock.bounds
            hpts = []
            for i in range(len(tips)):
                t = tool_by_id.get(meta[i][4], default_tool)
                axis = _tool_axis(meta[i][0], meta[i][1])
                base = tips[i] + axis * t["gauge_length"]
                hpts.append(_tool_surface(base, axis, t["holder_radius"],
                                          t["holder_length"], n_ang=6))
            hs = np.array(hpts).reshape(-1, 3)
            hclear = _box_sdf(hs, lo, hi).reshape(len(tips), -1).min(axis=1)
            min_clear["stock_holder"] = float(hclear.min())
            if min_clear["stock_holder"] < holder_margin:
                violations.append({"type": "HOLDER_STOCK_CLEARANCE",
                                   "clearance_mm": round(min_clear["stock_holder"], 3),
                                   "required_mm": holder_margin})

        # 超程（刀尖点，含 B/C 转台变换）
        travel = machine["travel_mm"]
        rb = machine["rotary_limits_deg"]
        over = 0
        for k in range(0, len(tips), max(1, len(tips) // 4000)):
            px, py, pz = tips[k]
            b, c = meta[k][0], meta[k][1]
            if not (rb["b"][0] <= b <= rb["b"][1]) or not (rb["c"][0] <= c <= rb["c"][1]):
                over += 1
                if len(violations) < 40:
                    violations.append({"type": "ROTARY_OVERTRAVEL", "line": meta[k][2],
                                       "b": b, "c": c})
            br, cr = math.radians(b), math.radians(c)
            rb_m = np.array([[math.cos(br), 0, math.sin(br)], [0, 1, 0],
                             [-math.sin(br), 0, math.cos(br)]])
            rc_m = np.array([[math.cos(cr), -math.sin(cr), 0],
                             [math.sin(cr), math.cos(cr), 0], [0, 0, 1]])
            mp = rb_m @ (rc_m @ np.array([px, py, pz]))
            if not all(travel[a][0] <= mp[i] <= travel[a][1]
                       for i, a in enumerate(("x", "y", "z"))):
                over += 1
                if len(violations) < 40:
                    violations.append({"type": "LINEAR_OVERTRAVEL", "line": meta[k][2],
                                       "machine": mp.round(2).tolist()})
        checks.append({"gate": "MACHINE-TRAVEL", "status": "PASS" if over == 0 else "FAIL",
                       "evidence": {"violations": over, "travel": travel, "rotary": rb}})

    checks.append({"gate": "FIXTURE-CLEARANCE",
                   "status": "PASS" if min_clear["fixture"] >= 0 else "FAIL",
                   "evidence": round(min_clear["fixture"], 3)
                   if math.isfinite(min_clear["fixture"]) else None,
                   "where": min_where.get("fixture")})
    checks.append({"gate": "DESIGN-GOUGE",
                   "status": "PASS" if min_clear["design"] >= -gouge_tol else "FAIL",
                   "evidence": round(min_clear["design"], 3)
                   if math.isfinite(min_clear["design"]) else None,
                   "where": min_where.get("design")})
    checks.append({"gate": "DESIGN-SURFACE",
                   "status": "PASS" if min_clear["design_surface"] >= -gouge_tol else "FAIL",
                   "evidence": round(min_clear["design_surface"], 3)
                   if math.isfinite(min_clear["design_surface"]) else None})
    checks.append({"gate": "HOLDER-STOCK",
                   "status": "PASS" if min_clear["stock_holder"] >= holder_margin else "FAIL",
                   "evidence": round(min_clear["stock_holder"], 3)
                   if math.isfinite(min_clear["stock_holder"]) else None,
                   "required": holder_margin})
    safe_min = {k: (round(v, 3) if math.isfinite(v) else None) for k, v in min_clear.items()}
    return {"checks": checks, "violations": violations, "min_clearance": safe_min,
            "samples": len(sp["points"]), "sweep": sp, "basis": "measured (swept tool surface)"}


def cycle_time(parsed: Parsed, machine: Dict, stop_s: float = 5.0) -> Dict:
    sp = sample_path(parsed, 5.0)
    per_op = {op: t for op, t in sp["time_by_op"].items()}
    changes = int(parsed.stats.get("tool_changes", 0))
    total = sum(per_op.values()) + changes * machine["tool_change_s"] \
        + len(parsed.ops) * stop_s
    return {"per_op_s": {k: round(v, 1) for k, v in per_op.items()},
            "cut_time_s": {k: round(v, 1) for k, v in sp["cut_time_by_op"].items()},
            "tool_changes": changes, "total_s": round(total, 1),
            "path_length_mm": round(sp["total_length_mm"], 1),
            "basis": "derived (length/feed + rapid + tool change + optional stop)"}
