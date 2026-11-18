# -*- coding: utf-8 -*-
"""离线材料去除 + Auto-Diff 验证器（不依赖 VERICUT GUI）。

原理：
  1. 解析五轴 NC（G90 绝对、G43.4 RTCP：X/Y/Z=刀尖点，B/C 定刀轴）
  2. 用刀具扫掠体（T1 D16 平底 / T2 D8 球头）从毛坯体素中切除材料
  3. 加工结果与 CAD 设计体素比对，统计过切(gouge)/残留(excess)/余量
  4. 输出截面红蓝绿图 + 结构化 JSON 报告

刀轴约定（与 impeller_cam_from_geometry.py 完全一致）：
  d = (sinB·cosC, -sinB·sinC, cosB)   指向刀柄
  球头刀占据区 = 球心 c = tip + R·d 半径 R 的扫掠胶囊

用体素法（默认 1mm），完全 numpy 向量化，可复跑。
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

import numpy as np
import trimesh

ART = Path(r"D:\Virtu模型\artifacts\aero_closed_impeller")
OUTDIR = ART

# 刀具（与 CAM 脚本一致）
TOOLS = {
    1: {"name": "D16 flat endmill", "R": 8.0, "type": "flat"},
    2: {"name": "D8 ball / D5 neck / reach70", "R": 4.0, "type": "ball"},
}


# ---------- 1. NC 解析 ----------
TOKEN = re.compile(r"([A-Z])\s*(-?\d+(?:\.\d+)?)")


def parse_nc(path: Path):
    """返回刀尖运动段列表 [(x,y,z,b,c,gcode,tool,feed,lineno), ...]。"""
    moves = []
    tool = 2
    cur = {"X": 0.0, "Y": 0.0, "Z": 0.0, "B": 0.0, "C": 0.0}
    modal_g = "G00"
    for ln, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("(") or line.startswith("%"):
            continue
        # 去掉行内注释 ( ... )
        line = re.sub(r"\([^)]*\)", "", line).strip()
        if not line:
            continue
        toks = TOKEN.findall(line.upper())
        if not toks:
            continue
        d = {k: float(v) for k, v in toks}
        # 换刀
        if "T" in d and "M06" in line:
            tool = int(d["T"])
        # G 代码（取本行第一个 Gxx）
        gs = [k for k, v in toks if k == "G"]
        for g in ("G00", "G01", "G02", "G03"):
            num = str(int(g[1:]))
            if any(t[0] == "G" and float(t[1]) == float(num) for t in toks):
                modal_g = g
                break
        # 更新坐标（绝对 G90）
        new = dict(cur)
        for ax in ("X", "Y", "Z", "B", "C"):
            if ax in d:
                new[ax] = d[ax]

        if modal_g in ("G01", "G02", "G03"):
            def emit(p0, p1, b, c, g, feed):
                moves.append({
                    "p0": tuple(p0), "p1": tuple(p1),
                    "b": b, "c": c, "g": g, "tool": tool,
                    "feed": feed, "line": ln,
                })

            if modal_g == "G01":
                moved = any(abs(new[k] - cur[k]) > 1e-6 for k in ("X", "Y", "Z"))
                if moved:
                    emit((cur["X"], cur["Y"], cur["Z"]),
                         (new["X"], new["Y"], new["Z"]),
                         new["B"], new["C"], modal_g, d.get("F", 0.0))
            else:
                # G02/G03 圆弧：起点=终点的整圆不能被 moved 判据跳过。
                # 用 I/J 圆心按角度采样成小线段，Z 线性插值。
                cx = cur["X"] + d.get("I", 0.0)
                cy = cur["Y"] + d.get("J", 0.0)
                r0 = math.hypot(cur["X"] - cx, cur["Y"] - cy)
                r1 = math.hypot(new["X"] - cx, new["Y"] - cy)
                if r0 > 1e-6:
                    a0 = math.atan2(cur["Y"] - cy, cur["X"] - cx)
                    a1 = math.atan2(new["Y"] - cy, new["X"] - cx)
                    full = (abs(a1 - a0) < 1e-6 and abs(new["X"] - cur["X"]) < 1e-6
                            and abs(new["Y"] - cur["Y"]) < 1e-6)
                    if modal_g == "G02":  # clockwise: 角度递减
                        while a1 >= a0:
                            a1 -= 2 * math.pi
                    else:                  # G03 ccw: 角度递增
                        while a1 <= a0:
                            a1 += 2 * math.pi
                    if full:
                        a1 = a0 + (2 * math.pi if modal_g == "G03" else -2 * math.pi)
                    nseg = max(2, int(abs(a1 - a0) / math.radians(6)) + 1)
                    prev = (cur["X"], cur["Y"], cur["Z"])
                    for i in range(1, nseg + 1):
                        t = i / nseg
                        ang = a0 + (a1 - a0) * t
                        rad = r0 + (r1 - r0) * t
                        pt = (cx + rad * math.cos(ang),
                              cy + rad * math.sin(ang),
                              cur["Z"] + (new["Z"] - cur["Z"]) * t)
                        emit(prev, pt, new["B"], new["C"], modal_g, d.get("F", 0.0))
                        prev = pt
        cur = new
    return moves


# ---------- 2. 体素化（奇偶射线，numpy，快） ----------
def voxelize(mesh, xs, ys, zs):
    nx, ny, nz = len(xs), len(ys), len(zs)
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    px, py = X.ravel(), Y.ravel()
    n = len(px)
    MAXH = 64
    zh = np.full((n, MAXH), np.inf)
    cnt = np.zeros(n, np.int32)
    tris = np.asarray(mesh.triangles, dtype=float)
    eps = 1e-10
    for tri in tris:
        (ax, ay, az), (bx, by, bz), (cx, cy, cz) = tri
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < eps:
            continue
        l1 = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / den
        l2 = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / den
        l3 = 1.0 - l1 - l2
        m = (l1 >= -eps) & (l2 >= -eps) & (l3 >= -eps)
        idx = np.nonzero(m)[0]
        if idx.size == 0:
            continue
        zint = l1[idx] * az + l2[idx] * bz + l3[idx] * cz
        slot = cnt[idx]
        ok = slot < MAXH
        if ok.any():
            zh[idx[ok], slot[ok]] = zint[ok]
        cnt[idx] += 1
    vol = np.zeros((nx, ny, nz), bool)
    for k, zc in enumerate(zs):
        vol[:, :, k] = (np.count_nonzero(zh < zc, axis=1) % 2 == 1).reshape(nx, ny)
    return vol


def tool_axis_deg(b, c):
    bb, cc = math.radians(b), math.radians(c)
    return np.array([math.sin(bb) * math.cos(cc),
                     -math.sin(bb) * math.sin(cc),
                     math.cos(bb)])


def carve_segment(removed, c0, c1, R, xs, ys, zs):
    """在体素网格中标记球心从 c0 扫到 c1、半径 R 的胶囊覆盖体素。"""
    lo = np.minimum(c0, c1) - R - 1
    hi = np.maximum(c0, c1) + R + 1
    i0 = int(np.searchsorted(xs, lo[0])); i1 = int(np.searchsorted(xs, hi[0]))
    j0 = int(np.searchsorted(ys, lo[1])); j1 = int(np.searchsorted(ys, hi[1]))
    k0 = int(np.searchsorted(zs, lo[2])); k1 = int(np.searchsorted(zs, hi[2]))
    i0, j0, k0 = max(i0, 0), max(j0, 0), max(k0, 0)
    i1, j1, k1 = min(i1, len(xs)), min(j1, len(ys)), min(k1, len(zs))
    if i1 <= i0 or j1 <= j0 or k1 <= k0:
        return
    # 低内存：按分量累加平方距离，避免构造 (nx,ny,nz,3) 的 4D 临时数组
    gx = xs[i0:i1][:, None, None]
    gy = ys[j0:j1][None, :, None]
    gz = zs[k0:k1][None, None, :]
    v = c1 - c0
    vv = float(v @ v)
    if vv < 1e-9:
        d2 = (gx - c0[0])**2 + (gy - c0[1])**2 + (gz - c0[2])**2
    else:
        dot = (gx - c0[0]) * v[0] + (gy - c0[1]) * v[1] + (gz - c0[2]) * v[2]
        t = np.clip(dot / vv, 0.0, 1.0)
        dx = gx - (c0[0] + t * v[0])
        dy = gy - (c0[1] + t * v[1])
        dz = gz - (c0[2] + t * v[2])
        d2 = dx*dx + dy*dy + dz*dz
        del dot, t, dx, dy, dz
    removed[i0:i1, j0:j1, k0:k1] |= (d2 <= R * R)


# ---------- 3. 主流程 ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nc", default=str(ART / "AE_CLOSED_IMPELLER_5AXIS_FIXED.nc"))
    ap.add_argument("--stock", default=str(ART / "AE_CLOSED_IMPELLER_stock.stl"))
    ap.add_argument("--design", default=str(ART / "AE_CLOSED_IMPELLER_NASA1975.stl"))
    ap.add_argument("--pitch", type=float, default=1.0)
    ap.add_argument("--max-moves", type=int, default=0, help="0=all")
    a = ap.parse_args()

    pitch = a.pitch
    stock = trimesh.load(a.stock)
    design = trimesh.load(a.design)
    bmin = np.minimum(stock.bounds[0], design.bounds[0]) - 2
    bmax = np.maximum(stock.bounds[1], design.bounds[1]) + 2
    xs = np.arange(bmin[0], bmax[0] + pitch, pitch)
    ys = np.arange(bmin[1], bmax[1] + pitch, pitch)
    zs = np.arange(bmin[2], bmax[2] + pitch, pitch)
    print(f"grid {len(xs)}x{len(ys)}x{len(zs)}={len(xs)*len(ys)*len(zs)} voxels @ {pitch}mm", flush=True)

    print("voxelizing stock...", flush=True)
    sv = voxelize(stock, xs, ys, zs)
    print("voxelizing design...", flush=True)
    dv = voxelize(design, xs, ys, zs)
    print(f"stock vox={sv.sum()} design vox={dv.sum()} ratio={sv.sum()/max(dv.sum(),1):.3f}", flush=True)

    moves = parse_nc(Path(a.nc))
    if a.max_moves:
        moves = moves[:a.max_moves]
    print(f"parsed {len(moves)} cutting moves", flush=True)

    # 纠错(v2)：不能用"刀尖在毛坯内"过滤——OP1 外锥粗铣刀心 r=135.6 大于毛坯
    # r=132，但 D16 刀具半径 8mm 的切削刃正好扫到毛坯表面。刀心在毛坯外仍有效。
    # 正确做法：所有 G01 段都做扫掠，由 carve_segment 的体素包围盒自动裁剪，
    # 抬刀/安全位移段与毛坯无交集自然不生效。
    removed = np.zeros_like(sv)
    by_tool = {1: 0, 2: 0}
    for m in moves:
        t = TOOLS[m["tool"]]
        R = t["R"]
        d = tool_axis_deg(m["b"], m["c"])
        p0 = np.array(m["p0"])
        p1 = np.array(m["p1"])
        c0 = p0 + R * d
        c1 = p1 + R * d
        carve_segment(removed, c0, c1, R, xs, ys, zs)
        by_tool[m["tool"]] = by_tool.get(m["tool"], 0) + 1
    used = sum(by_tool.values())
    print(f"carved with all {used} moves (T1={by_tool.get(1,0)}, T2={by_tool.get(2,0)})", flush=True)

    machined = sv & ~removed
    # Auto-Diff（对齐 VERICUT 定义）
    gouge = dv & removed          # 设计实体被切掉 -> 过切（红）
    excess = machined & ~dv       # 设计外仍有材料 -> 残留/余量（蓝）
    ok = machined & dv            # 保留的设计内材料

    vx = pitch ** 3
    report = {
        "method": "offline NC-driven voxel sweep + Auto-Diff (VERICUT-independent)",
        "grid_pitch_mm": pitch,
        "grid_shape": [len(xs), len(ys), len(zs)],
        "tools": TOOLS,
        "nc_moves_total": len(moves),
        "nc_moves_in_stock": used,
        "nc_moves_by_tool": {str(k): v for k, v in by_tool.items()},
        "volumes_mm3": {
            "stock": round(float(sv.sum() * vx)),
            "design": round(float(dv.sum() * vx)),
            "machined": round(float(machined.sum() * vx)),
            "removed_total": round(float((sv & removed).sum() * vx)),
            "gouge": round(float(gouge.sum() * vx)),
            "excess": round(float(excess.sum() * vx)),
            "ok_design_retained": round(float(ok.sum() * vx)),
        },
        "gouge_pct_of_design": round(100.0 * gouge.sum() / max(dv.sum(), 1), 3),
        "excess_pct_of_design": round(100.0 * excess.sum() / max(dv.sum(), 1), 3),
        "stock_removal_ratio": round(float(removed.sum() / max(sv.sum(), 1)), 4),
        "verdict": "PASS" if gouge.sum() / max(dv.sum(), 1) < 0.01 else "REVIEW",
    }
    rp = OUTDIR / "autodiff_report.json"
    rp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["volumes_mm3"], ensure_ascii=False, indent=2), flush=True)
    print(f"gouge={report['gouge_pct_of_design']}%  excess={report['excess_pct_of_design']}%  verdict={report['verdict']}", flush=True)

    # 截面红蓝绿图（几个 z 层）
    render_sections(gouge, excess, ok, xs, ys, zs, pitch)
    print("wrote", rp, flush=True)


def render_sections(gouge, excess, ok, xs, ys, zs, pitch):
    from PIL import Image, ImageDraw
    zs_abs = zs
    levels = [5, 25, 45, 65]
    panels = []
    for zl in levels:
        k = int(np.argmin(np.abs(zs_abs - zl)))
        H, W = gouge[:, :, k].shape
        img = np.zeros((H, W, 3), dtype=np.uint8) + 255
        img[ok[:, :, k]] = (90, 200, 130)        # 绿：合格
        img[excess[:, :, k]] = (70, 130, 220)    # 蓝：残留余量
        img[gouge[:, :, k]] = (230, 70, 70)      # 红：过切
        panels.append((zl, Image.fromarray(img)))
    n = len(panels)
    cw = panels[0][1].width
    canvas = Image.new("RGB", (cw * n, cw + 40), "white")
    d = ImageDraw.Draw(canvas)
    for i, (zl, im) in enumerate(panels):
        canvas.paste(im, (i * cw, 30))
        d.text((i * cw + 5, 6), f"z={zl}mm", fill="black")
    out = OUTDIR / "autodiff_sections.png"
    canvas.save(out)
    print("wrote", out, flush=True)


if __name__ == "__main__":
    main()
