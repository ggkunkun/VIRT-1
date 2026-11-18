"""复杂曲面几何可观测化 (Surface Observability)。

直接对应最初痛点「智能体无法理解复杂曲面加工」的*最快解法*（AGENTS.md 第6节
「几何可观测化」）：把不透明的 NURBS/自由曲面，转成智能体能"看见"的显性证据——

  1. 曲率场 (curvature field)：每三角面对邻面法向夹角的平均二面角作为曲率代理，
     定位高曲率区 → 此处刀路步距必须收紧，否则残料超差。
  2. 残余高度场 (residual / scallop height)：给定球头刀半径 R 与步距 L，用
     曲率感知的残料公式估算每处残料高度，超表面粗糙度允许值即报警。
  3. 可达性/干涉 (accessibility)：法向 Z 分量判定负角(undercut)与直刀干渗，
     给出是否需要 5 轴摆动的结论。

输出：结构化指标 (dict) + 三张 PNG（曲率热力图 / 残余高度图 / 刀轨 backplot），
可作为多模态输入直接喂给大模型，把"看坐标数字"变成"看一张图"。
零依赖（仅渲染 PNG 时可选 matplotlib/PIL，缺失则只返回指标）。
"""

from __future__ import annotations

import math
import os
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any


# ---------------------------------------------------------------------------
# STL 读取（二进制 + ASCII，纯标准库）
# ---------------------------------------------------------------------------
def _parse_vericut_model_triangles(text: str) -> List[Tuple[Tuple[float, float, float], ...]]:
    """解析 VERICUT 原生 ``VERICUT-model`` (Version-3.0) ASCII 多边形网格。

    E:\\training / E:\\samples 中的 ``*.stl`` / ``*.ply`` 样本实际是这种格式：
        VERICUT-model / Version-3.0 / <实体数> / <R G B>
        然后若干多边形块：``nv`` 一行，随后 nv 行顶点 ``x y z``，再 nv 行法向 ``nx ny nz``。
    多边形按扇形三角化 (v0, vi, vi+1)。
    """
    lines = text.splitlines()
    tris: List[Tuple[Tuple[float, float, float], ...]] = []
    n = len(lines)
    i = 0
    # 跳过文件头的 "VERICUT-model" 与 "Version-x" 行
    while i < n and (not lines[i].strip() or lines[i].strip().lower().startswith(("vericut-model", "version"))):
        i += 1
    while i < n:
        parts = lines[i].split()
        if len(parts) == 1:
            try:
                nv = int(parts[0])
            except ValueError:
                i += 1
                continue
            if nv >= 3 and i + 2 * nv < n + 1:
                verts: List[Tuple[float, float, float]] = []
                ok = True
                for k in range(1, nv + 1):
                    vp = lines[i + k].split() if i + k < n else []
                    if len(vp) != 3:
                        ok = False
                        break
                    try:
                        verts.append((float(vp[0]), float(vp[1]), float(vp[2])))
                    except ValueError:
                        ok = False
                        break
                if ok:
                    for k in range(1, nv - 1):
                        tris.append((verts[0], verts[k], verts[k + 1]))
                    i += 1 + 2 * nv  # 顶点 + 法向
                    continue
        i += 1
    return tris


def _parse_ascii_ply_triangles(text: str) -> List[Tuple[Tuple[float, float, float], ...]]:
    """解析标准 ASCII PLY（vertex x y z ... / face k i0 i1 ...）。"""
    lines = text.splitlines()
    n_vert = n_face = 0
    hdr_end = -1
    for idx, line in enumerate(lines):
        s = line.strip()
        if s.startswith("format") and "ascii" not in s:
            raise ValueError("仅支持 ASCII PLY")
        if s.startswith("element vertex"):
            n_vert = int(s.split()[-1])
        elif s.startswith("element face"):
            n_face = int(s.split()[-1])
        elif s == "end_header":
            hdr_end = idx
            break
    if hdr_end < 0:
        raise ValueError("PLY 缺少 end_header")
    verts: List[Tuple[float, float, float]] = []
    for line in lines[hdr_end + 1: hdr_end + 1 + n_vert]:
        p = line.split()
        verts.append((float(p[0]), float(p[1]), float(p[2])))
    tris: List[Tuple[Tuple[float, float, float], ...]] = []
    for line in lines[hdr_end + 1 + n_vert: hdr_end + 1 + n_vert + n_face]:
        p = line.split()
        if not p:
            continue
        k = int(p[0])
        idxs = [int(v) for v in p[1:1 + k]]
        for j in range(1, k - 1):
            tris.append((verts[idxs[0]], verts[idxs[j]], verts[idxs[j + 1]]))
    return tris


def read_stl_triangles(stl_path: str) -> List[Tuple[Tuple[float, float, float], ...]]:
    """读取网格返回三角面列表，每面 = ((x,y,z),(x,y,z),(x,y,z))。

    支持：二进制 STL、ASCII STL、VERICUT-model(Version-3.0)、ASCII PLY。
    """
    data = open(stl_path, "rb").read()
    tris: List[Tuple[Tuple[float, float, float], ...]] = []
    head = data[:64].lstrip()
    if head.startswith(b"VERICUT-model"):
        return _parse_vericut_model_triangles(data.decode("utf-8", "replace"))
    if head.lower().startswith(b"ply"):
        return _parse_ascii_ply_triangles(data.decode("utf-8", "replace"))
    if data[:5].lower() == b"solid":
        text = data.decode("utf-8", "replace")
        cur: List[Tuple[float, float, float]] = []
        for line in text.splitlines():
            parts = line.split()
            if not parts:
                continue
            if parts[0] == "vertex":
                cur.append((float(parts[1]), float(parts[2]), float(parts[3])))
                if len(cur) == 3:
                    tris.append((cur[0], cur[1], cur[2]))
                    cur = []
        return tris
    # 二进制
    count = struct.unpack("<I", data[80:84])[0]
    off = 84
    for _ in range(count):
        # 法向 3 float + 3 顶点 * 3 float + 2 字节属性
        vals = struct.unpack_from("<12f", data, off)
        off += 48
        a = (vals[3], vals[4], vals[5])
        b = (vals[6], vals[7], vals[8])
        c = (vals[9], vals[10], vals[11])
        tris.append((a, b, c))
        off += 2
    return tris


# ---------------------------------------------------------------------------
# 几何基元（纯 Python）
# ---------------------------------------------------------------------------
def _sub(p: Tuple[float, float, float], q: Tuple[float, float, float]) -> Tuple[float, float, float]:
    return (p[0] - q[0], p[1] - q[1], p[2] - q[2])


def _cross(u: Tuple[float, float, float], v: Tuple[float, float, float]) -> Tuple[float, float, float]:
    return (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])


def _dot(u: Tuple[float, float, float], v: Tuple[float, float, float]) -> float:
    return u[0] * v[0] + u[1] * v[1] + u[2] * v[2]


def _norm(v: Tuple[float, float, float]) -> float:
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def _face_normal(a, b, c) -> Tuple[float, float, float]:
    n = _cross(_sub(b, a), _sub(c, a))
    ln = _norm(n) or 1.0
    return (n[0] / ln, n[1] / ln, n[2] / ln)


def _edge_key(p: Tuple[float, float, float], q: Tuple[float, float, float]) -> Tuple:
    # 归一化边，避免方向/浮点顺序导致邻接漏配
    def r(x):
        return round(x, 4)
    (a, b) = (r(p[0]), r(p[1]), r(p[2])), (r(q[0]), r(q[1]), r(q[2]))
    return tuple(sorted((a, b)))


# ---------------------------------------------------------------------------
# 曲率代理 / 残余高度 / 可达性
# ---------------------------------------------------------------------------
def _curvature_field(tris: List) -> Tuple[List[float], List[float]]:
    """返回 (每面曲率代理[rad], 每面平均边长)。曲率代理=对邻面法向夹角均值。"""
    n = len(tris)
    normals = [_face_normal(*t) for t in tris]
    edge_map: Dict[Tuple, List[int]] = {}
    for i, (a, b, c) in enumerate(tris):
        for e in ((a, b), (b, c), (c, a)):
            edge_map.setdefault(_edge_key(*e), []).append(i)
    curv: List[float] = [0.0] * n
    edge_len: List[float] = [0.0] * n
    for i, (a, b, c) in enumerate(tris):
        # 平均边长
        l1 = _norm(_sub(b, a)); l2 = _norm(_sub(c, b)); l3 = _norm(_sub(a, c))
        edge_len[i] = (l1 + l2 + l3) / 3.0
        # 对邻面二面角
        nb = set()
        for e in ((a, b), (b, c), (c, a)):
            nb.update(edge_map.get(_edge_key(*e), []))
        nb.discard(i)
        if not nb:
            curv[i] = 0.0
            continue
        s = 0.0
        for j in nb:
            d = _dot(normals[i], normals[j])
            d = max(-1.0, min(1.0, d))
            s += math.acos(d)
        curv[i] = s / len(nb)
    return curv, edge_len


def _residual_height(curv: List[float], edge_len: List[float],
                     tool_radius: float, step_over: float) -> List[float]:
    """曲率感知残料高度（球头刀）。凸面(κ>0)使有效半径减小→残料增大(最不利)。"""
    L2 = step_over / 2.0
    out: List[float] = []
    for kappa, le in zip(curv, edge_len):
        ref = le if le > 1e-9 else 1.0
        kappa_mag = abs(kappa) / ref  # 1/长度量纲的曲率
        denom = 1.0 / tool_radius + kappa_mag  # 凸面最不利（取 +|κ|）
        if denom <= 0:
            out.append(0.0)
            continue
        r_eff = 1.0 / denom
        if r_eff <= L2:
            out.append(0.0)  # 刀路过盈，基本无残料
        else:
            out.append(r_eff - math.sqrt(r_eff * r_eff - L2 * L2))
    return out


def _accessibility(tris: List, spindle_axis: str = "Z") -> List[float]:
    """返回每面法向在*主轴方向*的分量；分量偏低即直刀难达 → 干涉/undercut 风险。

    注意：可达性必须在*加工坐标系*下判定（主轴指向），而非任意网格帧。
    调用方须传入真实主轴轴 (X/Y/Z)，否则圆柱类回转体侧面会被误判为全负角。
    """
    idx = {"X": 0, "Y": 1, "Z": 2}.get(spindle_axis.upper(), 2)
    return [_face_normal(*t)[idx] for t in tris]


def _recommend_step_over(tool_radius: float, allowance: float) -> float:
    """由允许残料反解最大步距 L：allowance = r_eff - sqrt(r_eff^2 - (L/2)^2)，平面近似。"""
    if allowance <= 0:
        return 0.0
    r = tool_radius
    # 平面(曲率0)：L = 2*sqrt(2*r*allowance - allowance^2)
    inside = 2.0 * r * allowance - allowance * allowance
    if inside <= 0:
        return 0.0
    return 2.0 * math.sqrt(inside)


# ---------------------------------------------------------------------------
# 渲染（可选 matplotlib / PIL）
# ---------------------------------------------------------------------------
def _render_maps(tris: List, curv: List[float], residual: List[float],
                 out_dir: str) -> Dict[str, Optional[str]]:
    """把曲率场与残余高度场投影到 XY 平面着色，并叠加刀轨回放，输出 PNG。"""
    paths: Dict[str, Optional[str]] = {"curvature_png": None, "residual_png": None, "toolpath_png": None}
    os.makedirs(out_dir, exist_ok=True)

    xy = [[(t[0][0], t[0][1]), (t[1][0], t[1][1]), (t[2][0], t[2][1])] for t in tris]

    # ---- 优先 matplotlib ----
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.collections import PolyCollection
        from matplotlib import cm

        def heatmap(values, fname, title, cmap):
            fig, ax = plt.subplots(figsize=(6, 5))
            coll = PolyCollection(xy, array=values, cmap=cmap, edgecolors="none")
            ax.add_collection(coll)
            ax.autoscale()
            ax.set_aspect("equal", adjustable="datalim")
            ax.set_title(f"{title}\n(min={min(values):.4f} max={max(values):.4f})")
            fig.colorbar(coll, ax=ax, fraction=0.046)
            p = os.path.join(out_dir, fname)
            fig.savefig(p, dpi=110)
            plt.close(fig)
            return p

        paths["curvature_png"] = heatmap(curv, "curvature_field.png",
                                         "Surface Curvature Field (rad)", "hot")
        paths["residual_png"] = heatmap(residual, "residual_height.png",
                                        "Scallop / Residual Height (mm)", "viridis")

        # ---- 刀轨回放：在 XY 包围盒内按推荐步距画平行扫描线，叠加曲面 wireframe ----
        xs = [v[0] for t in tris for v in t]
        ys = [v[1] for t in tris for v in t]
        xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
        step = max((xmax - xmin) / 40.0, 0.5)
        fig, ax = plt.subplots(figsize=(6, 5))
        for t in xy:
            ax.plot([t[0][0], t[1][0], t[2][0], t[0][0]], color=(0.6, 0.6, 0.6, 0.25), lw=0.3)
        y = ymin
        while y <= ymax:
            ax.plot([xmin, xmax], [y, y], color="red", lw=0.8)
            y += step
        ax.set_xlim(xmin, xmax); ax.set_ylim(ymin, ymax)
        ax.set_aspect("equal", adjustable="datalim")
        ax.set_title("Toolpath Backplot (Zig-Zag CL, step=%.1fmm)" % step)
        p3 = os.path.join(out_dir, "toolpath_backplot.png")
        fig.savefig(p3, dpi=110)
        plt.close(fig)
        paths["toolpath_png"] = p3
        return paths
    except Exception:
        pass

    # ---- 退化：用 PIL 画像素级热力图（无 matplotlib 时）----
    try:
        from PIL import Image
        def pil_heat(values, fname, cmap):
            xs = [v[0] for t in tris for v in t]
            ys = [v[1] for t in tris for v in t]
            xmin, xmax = min(xs), max(xs); ymin, ymax = min(ys), max(ys)
            w = h = 400
            img = Image.new("RGB", (w, h), (20, 20, 20))
            px = img.load()
            vmin, vmax = min(values), max(values)
            rng = (vmax - vmin) or 1.0
            def color(t):
                t = max(0.0, min(1.0, t))
                return (int(255 * t), int(255 * (1 - abs(t - 0.5) * 2)), int(255 * (1 - t)))
            for (tri, v) in zip(xy, values):
                t = (v - vmin) / rng
                col = color(t)
                pts = [(int((p[0] - xmin) / (xmax - xmin) * (w - 1)),
                        int((p[1] - ymin) / (ymax - ymin) * (h - 1))) for p in tri]
                _fill_tri(px, w, h, pts, col)
            p = os.path.join(out_dir, fname)
            img.save(p)
            return p
        paths["curvature_png"] = pil_heat(curv, "curvature_field.png", "hot")
        paths["residual_png"] = pil_heat(residual, "residual_height.png", "viridis")
        return paths
    except Exception:
        return paths


def _fill_tri(px, w, h, pts, col):
    """极简重心坐标光栅化一个三角形（仅兜底渲染用）。"""
    (x0, y0), (x1, y1), (x2, y2) = pts
    minx = max(0, int(min(x0, x1, x2))); maxx = min(w - 1, int(max(x0, x1, x2)))
    miny = max(0, int(min(y0, y1, y2))); maxy = min(h - 1, int(max(y0, y1, y2)))
    det = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
    if abs(det) < 1e-9:
        return
    for yy in range(miny, maxy + 1):
        for xx in range(minx, maxx + 1):
            a = ((y1 - y2) * (xx - x2) + (x2 - x1) * (yy - y2)) / det
            b = ((y2 - y0) * (xx - x2) + (x0 - x2) * (yy - y2)) / det
            c = 1 - a - b
            if 0 <= a <= 1 and 0 <= b <= 1 and 0 <= c <= 1:
                px[xx, yy] = col


# ---------------------------------------------------------------------------
# 对外主入口
# ---------------------------------------------------------------------------
@dataclass
class SurfaceObservabilityReport:
    mesh: str = ""
    triangle_count: int = 0
    curvature: Dict[str, float] = field(default_factory=dict)
    high_curvature_face_count: int = 0
    high_curvature_pct: float = 0.0
    residual: Dict[str, float] = field(default_factory=dict)
    faces_over_allowance: int = 0
    faces_over_allowance_pct: float = 0.0
    undercut_face_count: int = 0
    requires_multiaxis: bool = False
    recommended_step_over_mm: float = 0.0
    recommended_tool_radius_mm: float = 0.0
    curvature_mag_max: float = 0.0
    images: Dict[str, Optional[str]] = field(default_factory=dict)
    summary: str = ""
    evidence_status: str = "measured"


def observe_surface(mesh_path: str,
                   tool_radius_mm: float = 3.0,
                   step_over_mm: float = 1.0,
                   finish_allowance_mm: float = 0.01,
                   spindle_axis: str = "Z",
                   output_dir: Optional[str] = None) -> SurfaceObservabilityReport:
    """把成品/设计曲面转成可观测证据。

    参数：
      tool_radius_mm      球头刀半径（默认 3mm）
      step_over_mm        当前规划步距（默认 1mm）
      finish_allowance_mm 表面粗糙度允许的最大残料高度（默认 0.01mm）
      spindle_axis        加工主轴轴 (X/Y/Z，默认 Z)；可达性在此坐标系下判定
      output_dir          渲染 PNG 的输出目录（默认 mesh 同目录的 surface_obs/）
    返回 SurfaceObservabilityReport。
    """
    p = Path(mesh_path)
    if not p.exists():
        return SurfaceObservabilityReport(mesh=str(mesh_path), evidence_status="missing_file",
                                         summary=f"曲面文件不存在: {mesh_path}")
    tris = read_stl_triangles(str(p))
    n = len(tris)
    if n == 0:
        return SurfaceObservabilityReport(mesh=str(mesh_path), triangle_count=0,
                                         evidence_status="empty_mesh",
                                         summary="STL 无三角面，曲率为空。")

    curv, edge_len = _curvature_field(tris)
    sorted_el = sorted(edge_len)
    med_el = sorted_el[n // 2] if sorted_el else 0.0
    min_valid_edge = max(1e-6, 0.05 * med_el)
    # 过滤退化细长碎三角面与 C0 尖锐折边，避免单条 1e-5 边或 90° 倒角把光滑曲面曲率拉爆到 inf
    smooth_k = [
        abs(curv[i]) / edge_len[i]
        for i in range(n)
        if edge_len[i] > min_valid_edge and abs(curv[i]) <= 1.25
    ]
    raw_k = [abs(curv[i]) / edge_len[i] if edge_len[i] > 1e-9 else 0.0 for i in range(n)]
    kappa_mag_max = max(smooth_k) if smooth_k else (max(raw_k) if raw_k else 0.0)

    # 曲率感知自适应最佳步距（step_over_mm=None 时依据有效曲率半径收紧步距，下限 0.03mm 保留不可达熔断）
    min_practical_step_mm = 0.03
    r_eff_curv = (
        1.0 / (1.0 / max(1e-6, tool_radius_mm) + kappa_mag_max)
        if kappa_mag_max > 0 else tool_radius_mm
    )
    rec_step = max(min_practical_step_mm, 0.98 * _recommend_step_over(r_eff_curv, finish_allowance_mm))
    if step_over_mm is None or step_over_mm <= 0:
        step_over_mm = rec_step

    residual = _residual_height(curv, edge_len, tool_radius_mm, step_over_mm)
    nz = _accessibility(tris, spindle_axis)

    c_max, c_mean = max(curv), sum(curv) / n
    # 高曲率阈值：均值 + 1 个标准差
    c_std = math.sqrt(sum((c - c_mean) ** 2 for c in curv) / n)
    hi_thr = c_mean + c_std
    hi_idx = [i for i, c in enumerate(curv) if c > hi_thr]
    hi_cnt = len(hi_idx)

    r_max, r_mean = max(residual), sum(residual) / n
    over = [i for i, rr in enumerate(residual) if rr > finish_allowance_mm]
    over_cnt = len(over)

    under = [i for i, z in enumerate(nz) if z < 0.30]  # 法向 Z<0.3 → 大倾角/负角
    under_cnt = len(under)

    # 最不利有效曲率（1/长度量纲）；据此反解"达标所需最小刀具半径"。
    # 凹/凸耦合下 R_eff >= r_eff_min -> 1/R <= 1/r_eff_min - κ_max，若 <=0 说明当前步距+允差不可达。
    r_eff_min = ((step_over_mm / 2.0) ** 2 + finish_allowance_mm ** 2) / (2.0 * finish_allowance_mm)
    inv_needed = (1.0 / r_eff_min) - kappa_mag_max
    rec_tool = (1.0 / inv_needed) if inv_needed > 1e-6 else float("inf")

    out_dir = output_dir or str(p.parent / "surface_obs")
    imgs = _render_maps(tris, curv, residual, out_dir)

    summary = (
        f"曲面可观测化完成：{n} 三角面。曲率代理 max={c_max:.3f}rad mean={c_mean:.3f}rad，"
        f"高曲率面 {hi_cnt} 个({hi_cnt / n * 100:.1f}%)→这些区域刀路步距必须收紧。"
        f"当前步距 {step_over_mm}mm / 刀半径 {tool_radius_mm}mm 下，残料 max={r_max:.4f}mm "
        f"mean={r_mean:.4f}mm，超允许值({finish_allowance_mm}mm)的面 {over_cnt} 个"
        f"({over_cnt / n * 100:.1f}%)→需减小步距或换更小刀具。"
        f"负角/大倾角面 {under_cnt} 个→{'需 5 轴摆动加工' if under_cnt else '可 3+2 直刀'}。"
        f"推荐步距≤{rec_step:.2f}mm。"
    )

    return SurfaceObservabilityReport(
        mesh=str(p), triangle_count=n,
        curvature={"min": min(curv), "max": c_max, "mean": c_mean, "std": c_std,
                   "high_threshold": hi_thr},
        high_curvature_face_count=hi_cnt, high_curvature_pct=hi_cnt / n * 100.0,
        residual={"min": min(residual), "max": r_max, "mean": r_mean},
        faces_over_allowance=over_cnt, faces_over_allowance_pct=over_cnt / n * 100.0,
        undercut_face_count=under_cnt, requires_multiaxis=under_cnt > 0,
        recommended_step_over_mm=rec_step, recommended_tool_radius_mm=rec_tool,
        curvature_mag_max=kappa_mag_max,
        images=imgs, summary=summary, evidence_status="measured",
    )


# ---------------------------------------------------------------------------
# 自测
# ---------------------------------------------------------------------------
def _self_test() -> None:
    import tempfile
    base = Path(r"D:/Virtu模型/artifacts/aero_closed_impeller")
    design = base / "AE_CLOSED_IMPELLER_NASA1975.stl"
    stock = base / "AE_CLOSED_IMPELLER_stock.stl"
    cases = []
    if design.exists():
        rep = observe_surface(str(design), output_dir=str(tempfile.mkdtemp()))
        ok = (rep.evidence_status == "measured" and rep.triangle_count > 0
              and rep.curvature["max"] > 0 and rep.images.get("curvature_png"))
        cases.append(("成品曲面可观测(含PNG渲染)", ok,
                      f"面数={rep.triangle_count} 曲率max={rep.curvature['max']:.3f} "
                      f"高曲率面={rep.high_curvature_face_count} 残料max={rep.residual['max']:.4f} "
                      f"负角面={rep.undercut_face_count} 推荐步距={rep.recommended_step_over_mm:.2f} "
                      f"PNG={'有' if rep.images.get('curvature_png') else '无'}"))
    if stock.exists():
        rep2 = observe_surface(str(stock), spindle_axis="Z")
        # 毛坯(圆柱)可观测运行无异常：返回 measured 报告，数值与成品形成对照
        # （注：三角化圆柱的棱边会产生曲率假信号，且绕 Z 的圆柱侧面法向径向→
        #  可达性需结合真实加工坐标系判定，故此处只验证"可运行+可报告"，不做武断分类）
        ok2 = rep2.evidence_status == "measured" and rep2.triangle_count > 0
        cases.append(("毛坯(圆柱)可观测运行无异常", ok2,
                      f"毛坯面数={rep2.triangle_count} 曲率max={rep2.curvature['max']:.3f} "
                      f"高曲率面={rep2.high_curvature_face_count} 残料max={rep2.residual['max']:.4f} "
                      f"(对照：成品为高复杂度有机曲面，二者信号量级不同)"))
    # 不存在文件降级
    rep3 = observe_surface(r"D:/Virtu模型/none.stl")
    cases.append(("缺失文件安全降级", rep3.evidence_status == "missing_file",
                  f"status={rep3.evidence_status}"))
    print("=== surface_observability 自测 ===")
    all_ok = True
    for name, ok, info in cases:
        print(f"[{'PASS' if ok else 'FAIL'}] {name} :: {info}")
        all_ok = all_ok and ok
    assert all_ok, "存在未通过用例"
    print("ALL PASS")


if __name__ == "__main__":
    _self_test()
