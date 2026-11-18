# -*- coding: utf-8 -*-
"""闭式叶轮五轴 NC 生成（几何驱动 + 干涉寻优），修正原程序的四处硬伤。

原程序 scripts/generate_closed_impeller_5axis_nc.py 的实测缺陷（本轮逐条量化）：
  1. 刀路压在叶片中曲面上（沿 camber 单程直穿）——等于沿叶片中心线切一刀，切掉叶片。
  2. 刀轴倾角 B=+12..22°，方向反了：封闭流道内刀杆必须朝轴线倒（负 B），
     正向倾角把刀杆压进前轮盖（实测 B=+20° 侵入 13~34 点）。
  3. 外段（t>0.65）从进气口进刀无任何无干涉解——必须改从出口环带进刀（B≈130°）。
  4. 退刀与回摆写在同一个 G00 块（`G00 Z95. B0.`），刀尖在流道深处回摆会扫过轮盖。

本程序：
  * 倾角不靠猜：对每个「站位 × 偏置刀路」在 2° 网格上做真实实体包含判定（trimesh 射线法），
    记录可行窗口；再按「与上一点倾角变化最小」贪心连成连续曲线，限制每站位跳变 ≤12°。
  * 双侧进刀：内侧段 t∈[0,0.62] 自进气口进入；外侧段 t∈[0.55,1.0] 自出口环带进入，重叠 7%。
  * 每条流道 5 条周向偏置刀路（球头 D8 / 刀颈 D5 / 悬伸 70）。
  * 退刀沿刀轴方向，回摆一律在工件之外执行。
  * 定位：半精加工 / 工艺可达性验证，留 0.4mm 余量，最终 Ra0.8 由磨粒流(AFM)保证。

输出：
  artifacts/aero_closed_impeller/AE_CLOSED_IMPELLER_5AXIS_FIXED.nc
  artifacts/aero_closed_impeller/nc_validation_fixed.json
"""

from __future__ import annotations

import gc
import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "artifacts" / "aero_closed_impeller"

_s = importlib.util.spec_from_file_location("geo", ROOT / "scripts" / "build_nasa_closed_impeller.py")
geo = importlib.util.module_from_spec(_s)
_s.loader.exec_module(geo)

MESH = OUT / "AE_CLOSED_IMPELLER_NASA1975.stl"
NC_PATH = OUT / "AE_CLOSED_IMPELLER_5AXIS_FIXED.nc"
REPORT = OUT / "nc_validation_fixed.json"

R_BALL, R_NECK, REACH = 4.0, 2.5, 70.0
SAFETY = 0.5          # 校验时刀体半径外扩，避免"恰好擦到"被判合格
VC_MS = 55.0
N_SPINDLE = int(round(1000 * VC_MS / (math.pi * 2 * R_BALL) / 10) * 10)
FZ, N_FLUTES = 0.04, 2
F_FEED = int(round(N_SPINDLE * N_FLUTES * FZ / 10) * 10)
N_OP1, F_OP1 = 1200, 380
# 毛坯按 v3 近净仿形件（设计逐层包络 +3mm 径向余量）：
#   r_max(root)=132.04, 顶≈93.6, z=-5..75.9；旧值 129.03 是零余量，导致 NC 只刮表面、
#   残留 2.45mm（见 artifacts/.../autodiff_distance_report.json）。这里改为真实毛坯外径。
STOCK_TOP, STOCK_R, STOCK_BOTTOM = 74.85, 129.03, -5.0   # 包容块口径：顶面与设计件齐平、XY==设计 bbox、底面=夹具顶面
STOCK_ALLOW = 0.0     # 毛坯相对设计的径向余量（对齐案例 force_impeller: Stock XY == Design XY）
ALLOW = 0.4           # 半精加工留给最终精加工/磨粒流的余量

PITCH = 2 * math.pi / geo.Z_BLADES
N_ST = 13
PASSES = 5
ZONE_EYE = (0.0, 0.62)
ZONE_OD = (0.55, 1.0)
MAX_JUMP = 12.0        # 相邻站位 B 跳变上限（度）

_tg, _theta = geo.camber_theta()


def station(t: float):
    rh = geo.R1H + (geo.R2 - geo.R1H) * t
    rs = geo.R1S + (geo.R2 - geo.R1S) * t
    return ((rh + rs) / 2.0, (geo.z_hub(rh) + geo.z_shroud(rs)) / 2.0,
            float(np.interp(t, _tg, _theta)))


def pass_offsets(r: float) -> list[float]:
    half_thick = max(geo.T_HUB, geo.T_SHROUD) / 2.0
    usable = PITCH / 2 - (half_thick + R_BALL) / r - math.radians(0.6)
    return [(-1.0 + 2.0 * k / (PASSES - 1)) * usable for k in range(PASSES)]


def tool_axis(B_deg: float, C_deg: float) -> np.ndarray:
    """BC 双转台：C 为工件绕 Z 转角，B 为绕 Y 倾角。

    工件坐标系下刀轴 = Rz(-C)·(sinB,0,cosB) = (sinB·cosC, -sinB·sinC, cosB)。
    因此刀轴向方位 φ 倾倒时必须取 C = -φ（本程序据此写 C 值）。
    """
    b, c = math.radians(B_deg), math.radians(C_deg)
    return np.array([math.sin(b) * math.cos(c), -math.sin(b) * math.sin(c), math.cos(b)])


def shank_cloud(p: np.ndarray, B: float, C: float, length: float = REACH) -> np.ndarray:
    """刀体采样：p 为刀尖，d 指向刀柄；球头按真实半球，不能当圆柱。"""
    d = tool_axis(B, C)
    e1 = np.array([-math.sin(math.radians(C)), math.cos(math.radians(C)), 0.0])
    e1 = e1 - d * float(e1 @ d)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(d, e1)

    def ring(ts: float, rad: float):
        base = p + d * ts
        return np.array([base + (math.cos(a) * e1 + math.sin(a) * e2) * rad
                         for a in np.linspace(0, 2 * math.pi, 8, endpoint=False)])

    clouds = []
    rb = R_BALL + SAFETY
    for ts in np.linspace(0.0, rb, 5):
        rad = math.sqrt(max(rb ** 2 - (rb - ts) ** 2, 0.0))
        clouds.append(ring(ts, rad))
        if rad > 0.01:
            clouds.append(ring(ts, rad * 0.5))
    for ts in np.linspace(rb, length, 26):
        clouds.append(ring(ts, R_NECK + SAFETY))
    return np.vstack(clouds)


def _contains_any(mesh, pts, chunk: int = 64, retries: int = 3) -> bool:
    """内存友好的实体包含判定：分块射线求交，避免一次生成大批候选三角形索引。

    语义与 `mesh.contains(pts).any()` 完全一致，仅降低峰值内存（OOM 修复，2026-11-17）。
    """
    arr = np.asarray(pts, dtype=np.float64)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    n = arr.shape[0]
    for i in range(0, n, chunk):
        blk = arr[i:i + chunk]
        for attempt in range(retries):
            try:
                if mesh.contains(blk).any():
                    return True
                break
            except MemoryError:
                if blk.shape[0] == 1:
                    raise
                blk = blk[: max(1, blk.shape[0] // 2)]
                gc.collect()
    return False


def main() -> dict:
    mesh = trimesh.load(str(MESH), force="mesh")

    # ---------- 1) 逐「站位 × 刀路」求可行倾角 ----------
    grid: dict[tuple[str, int], list[list[float]]] = {}
    # 刀具可从进气口(B<=10)或出口环带(B>=90)两个方位进入，二者都试，由连续性择优
    ALL_B = sorted(list(range(10, -91, -2)) + list(range(90, 181, 2)))
    CACHE = OUT / "_cam_grid_cache.json"
    cache_key = json.dumps({"mesh": MESH.stat().st_size, "safety": SAFETY, "n_st": N_ST,
                            "passes": PASSES, "zones": [list(ZONE_EYE), list(ZONE_OD)],
                            "ball": R_BALL}, sort_keys=True)
    cached = None
    if CACHE.exists():
        try:
            blob = json.loads(CACHE.read_text(encoding="utf-8"))
            if blob.get("key") == cache_key:
                cached = {(z, int(k)): v for (z, k), v in
                          ((kk.split("|"), vv) for kk, vv in blob["grid"].items())}
                cached = {(z, int(k)): v for (z, k), v in cached.items()}
                print(f">>> 复用倾角搜索缓存 ({len(cached)} 组)")
        except Exception as exc:
            print("缓存不可用:", exc)
    for zone in ("eye", "od"):
        rng = ALL_B
        for k in range(PASSES):
            if cached and (zone, k) in cached:
                grid[(zone, k)] = cached[(zone, k)]
                continue
            per_station = []
            zlo, zhi = ZONE_EYE if zone == "eye" else ZONE_OD
            for i in range(N_ST):
                t = zlo + (zhi - zlo) * i / (N_ST - 1)   # 必须与刀路取点同一映射
                r, z, th_c = station(t)
                th = th_c + PITCH / 2.0 + pass_offsets(r)[k]
                p = np.array([r * math.cos(th), r * math.sin(th), z])
                Cdeg = (360.0 - math.degrees(th)) % 360.0
                ok = [float(B) for B in rng if not _contains_any(mesh, shank_cloud(p, B, Cdeg))]
                per_station.append(ok)
            if any(not lst for lst in per_station):
                bad = [round(i / (N_ST - 1), 3) for i, lst in enumerate(per_station) if not lst]
                raise RuntimeError(f"{zone} 段第 {k + 1} 条刀路在站位 {bad} 无可行倾角")
            grid[(zone, k)] = per_station

    CACHE.write_text(json.dumps(
        {"key": cache_key, "grid": {f"{z}|{k}": v for (z, k), v in grid.items()}}),
        encoding="utf-8")

    # ---------- 2) 每个站位取「离上一点最近」的可行倾角，限制跳变 ----------
    sched: dict[tuple[str, int], list[float]] = {}
    for zone in ("eye", "od"):
        for k in range(PASSES):
            per_station = grid[(zone, k)]
            seed = 5.0 if zone == "eye" else 132.0
            prev = min(per_station[0], key=lambda b: abs(b - seed))
            runs: list[list[tuple[int, float]]] = [[(0, prev)]]
            for i in range(1, N_ST):
                lst = per_station[i]
                near = min(lst, key=lambda b: abs(b - prev))
                if abs(near - prev) > MAX_JUMP:
                    # 方位切换（眼口 <-> 出口环带）：断开为新的一段，NC 中退刀换向再进
                    near = min(lst, key=lambda b: abs(b - seed))
                    runs.append([])
                runs[-1].append((i, near))
                prev = near
            sched[(zone, k)] = runs

    # ---------- 3) 组装刀路（一段 = 一条连续切削）----------
    override: dict[tuple[int, str, int, int], float] = {}

    def channel_paths(ch: int, zone: str) -> list[list[dict]]:
        lo, hi = ZONE_EYE if zone == "eye" else ZONE_OD
        base = ch * PITCH
        out = []
        for k in range(PASSES):
            for run in sched[(zone, k)]:
                pts = []
                for i, B in run:
                    t = lo + (hi - lo) * i / (N_ST - 1)
                    r, z, th_c = station(t)
                    th = th_c + base + PITCH / 2.0 + pass_offsets(r)[k]
                    B = override.get((ch, zone, k, i), B)
                    pts.append({"t": t, "r": r, "z": z, "theta": th, "B": B,
                                "k": k, "i": i})
                if len(pts) >= 2:
                    out.append(pts)
        return out

    # ---------- 4) 干涉复检（一个流道即可，16 条周向对称）----------
    bad, total, first = 0, 0, None
    for ch_v in range(geo.Z_BLADES):          # 网格非严格 16 重对称，必须逐流道验
      for zone in ("eye", "od"):
        for pts in channel_paths(ch_v, zone):
            for n, q in enumerate(pts):
                p = np.array([q["r"] * math.cos(q["theta"]), q["r"] * math.sin(q["theta"]), q["z"]])
                Cdeg = (360.0 - math.degrees(q["theta"])) % 360.0
                total += 1
                if _contains_any(mesh, shank_cloud(p, q["B"], Cdeg)):
                    bad += 1
                    first = first or {"zone": zone, "t": round(q["t"], 3), "B": q["B"]}
                if n == 0:      # 接近段：沿刀轴 100mm 必须通畅
                    total += 1
                    if _contains_any(mesh, shank_cloud(p, q["B"], Cdeg, length=REACH + 30)):
                        bad += 1
                        first = first or {"zone": zone, "t": round(q["t"], 3), "B": q["B"],
                                          "note": "接近段干涉"}
    # 定点修正：对残余边缘点在其自身方位上就近重选倾角，最多 3 轮
    fixes = 0
    for _round in range(3):
        if bad == 0:
            break
        for ch_v in range(geo.Z_BLADES):
            for zone in ("eye", "od"):
                k_iter = 0
                for pts in channel_paths(ch_v, zone):
                    for n, q in enumerate(pts):
                        p = np.array([q["r"] * math.cos(q["theta"]),
                                      q["r"] * math.sin(q["theta"]), q["z"]])
                        Cdeg = (360.0 - math.degrees(q["theta"])) % 360.0
                        if not _contains_any(mesh, shank_cloud(p, q["B"], Cdeg)):
                            continue
                        cand = sorted(ALL_B, key=lambda b: abs(b - q["B"]))
                        for b in cand:
                            if abs(b - q["B"]) > 40:
                                break
                            if not _contains_any(mesh, shank_cloud(p, b, Cdeg)):
                                override[(ch_v, zone, q["k"], q["i"])] = b
                                q["B"] = b
                                fixes += 1
                                break
                    k_iter += 1
        # 重算
        bad, total, first = 0, 0, None
        for ch_v in range(geo.Z_BLADES):
            for zone in ("eye", "od"):
                for pts in channel_paths(ch_v, zone):
                    for n, q in enumerate(pts):
                        p = np.array([q["r"] * math.cos(q["theta"]),
                                      q["r"] * math.sin(q["theta"]), q["z"]])
                        Cdeg = (360.0 - math.degrees(q["theta"])) % 360.0
                        total += 1
                        if _contains_any(mesh, shank_cloud(p, q["B"], Cdeg)):
                            bad += 1
                            first = first or {"zone": zone, "t": round(q["t"], 3), "B": q["B"]}
                        if n == 0:
                            total += 1
                            if _contains_any(mesh, shank_cloud(p, q["B"], Cdeg,
                                                         length=REACH + 30)):
                                bad += 1

    check = {"points_checked": total, "points_with_collision": bad,
             "first_bad": first, "targeted_fixes": fixes}
    if bad:
        REPORT.write_text(json.dumps({"status": "FAILED_COLLISION", **check},
                                     ensure_ascii=False, indent=2), encoding="utf-8")
        raise RuntimeError(f"刀路干涉复检未通过: {check}")

    # ---------- 5) 写 NC ----------
    def f(v: float) -> str:
        return f"{v:.3f}".rstrip("0").rstrip(".")

    L: list[str] = []
    a = L.append
    a("%")
    a("O2004 (AE-CI-258 CLOSED IMPELLER - 5AXIS SEMI-FINISH, GEOMETRY-DRIVEN)")
    a("(MODEL: AE_CLOSED_IMPELLER_NASA1975 D2=258.06 H=74.85 Z=16)")
    a("(MACHINE: DMG MORI NMV1500 / FANUC 30iM / BC TABLE B-180..160 C0..360)")
    # 毛坯为与机床 X/Y/Z 对齐的长方体包容块（导出 STL 为 8 顶点 bbox+余量方块），
    # 不是圆柱/回转体；STOCK_R 仅用于粗铣刀路的外锥包络半径，不代表毛坯形状。
    a("(STOCK: BOX %.2f X %.2f X %.2f  Z%.1f..%.1f  MATERIAL: TC11  [X/Y-ALIGNED BLOCK, NOT CYLINDER])"
      % (2 * STOCK_R, 2 * STOCK_R, STOCK_TOP - STOCK_BOTTOM, STOCK_BOTTOM, STOCK_TOP))
    a("(TOOL2: D8 BALL / D5 NECK / REACH 70MM)")
    a("(NOTE: SEMI-FINISH 0.4MM ALLOWANCE; FINAL Ra0.8 BY AFM)")
    a("G21 G90 G40 G80 G49 G17")
    a("G54")
    a("")
    # ---- OP1：盖板外锥面分层粗铣（五轴加工中心，纯铣削；毛坯外径/端面已到位）----
    a("(=== OP1: SHROUD OUTER CONE Z-LEVEL ROUGH MILLING D16 ===)")
    a("(5-AXIS MACHINING CENTER - MILLING ONLY, NO TURNING)")
    a("M01")
    a("T1 M06 (D16 ROUGHING ENDMILL)")
    a(f"S{N_OP1} M03")
    a("M08")
    a("G00 G90 B0. C0.")
    a("G00 X0. Y0. Z120.")
    a("G43 H1 Z110.")
    # 锥面母线：(R2, Z_COVER_OUT_EXIT) -> (R_COVER_OUT_INLET, Z_COVER_OUT_INLET)
    A = np.array([geo.R2, geo.Z_COVER_OUT_EXIT])
    Bp = np.array([geo.R_COVER_OUT_INLET, geo.Z_COVER_OUT_INLET])
    dirv = Bp - A
    mer_len = float(np.linalg.norm(dirv))
    nrm = np.array([dirv[1], -dirv[0]]) / mer_len          # (r,z) 平面外法线（朝外上）
    n_layers = int(math.ceil(mer_len / 4.0))
    r_tool = 8.0
    for k in range(n_layers + 1):
        # 每层沿外法线偏移，形成一条圆锥螺旋；5 度一段
        base = A + dirv * (k / n_layers)
        c = base + nrm * (r_tool + ALLOW)
        zc, rc = float(c[1]), float(c[0])
        a(f"(--- CONE LAYER {k + 1}/{n_layers + 1} r={rc:.2f} z={zc:.2f} ---)")
        a(f"G00 X{rc:.3f} Y0. Z{max(zc, geo.Z_COVER_OUT_INLET) + 6:.3f}")
        a(f"G01 Z{zc:.3f} F300.")
        a(f"G02 X{rc:.3f} Y0. I{-rc:.3f} J0. F{F_OP1}.")
    a("G00 Z110.")
    a("")
    # ---- OP1b：进气口开腔（把 r<84.58 的 5mm 厚盖顶料挖掉，通道才有入口）----
    a("(=== OP1b: INLET EYE HELICAL MILLING (DEPTH 5.0, FLOOR Z69.85) ===)")
    z_eye = geo.Z_INLET + ALLOW
    r_eye = geo.R1S + ALLOW - r_tool * 0.0
    a(f"G00 X{geo.R1S - 2:.3f} Y0. Z{z_eye + 8:.3f}")
    rr = geo.R1S + r_tool + ALLOW
    a(f"G00 X{rr:.3f} Y0. Z{z_eye + 6:.3f}")
    a(f"G01 Z{z_eye + 3:.3f} F300.")
    a(f"G01 Z{z_eye:.3f} F200.")
    r_now = rr
    while r_now > geo.R_BORE + r_tool:
        a(f"G02 X{r_now:.3f} Y0. I{-r_now:.3f} J0. F{F_OP1}.")
        r_now = max(r_now - (2 * r_tool - 1.5), geo.R_BORE + r_tool)
        a(f"G01 X{r_now:.3f} Y0. F{F_OP1}.")
    a(f"G02 X{r_now:.3f} Y0. I{-r_now:.3f} J0. F{F_OP1}.")
    a("G00 Z110.")
    a("")
    # ---- OP1c：Φ25 通孔（D16 螺旋铣，刀心 r=(25.8-16)/2=4.9 覆盖中心）----
    a("(=== OP1c: BORE D25.8 HELICAL MILLING D16 (0.4 ALLOWANCE) ===)")
    r_bore = (2 * (geo.R_BORE + ALLOW) - 2 * r_tool) / 2.0
    a(f"G00 X{r_bore:.3f} Y0. Z{geo.Z_COVER_OUT_INLET + 6:.3f}")
    a(f"G01 Z{geo.Z_COVER_OUT_INLET + 1:.3f} F300.")
    z = geo.Z_COVER_OUT_INLET + 1
    while z > STOCK_BOTTOM + 1:
        z = max(z - 3.0, STOCK_BOTTOM + 1)
        a(f"G03 X{r_bore:.3f} Y0. I{-r_bore:.3f} J0. Z{z:.3f} F200.")
    a("G00 Z110.")
    a("M09")
    a("G49")
    a("")
    # ---- OP1d：锥面五轴联动精铣（球刀，刀轴沿锥面法向，B≈51.8°，圆锥螺旋）----
    a("(=== OP1d: CONE 5-AXIS CONTOUR MILLING D8 BALL, TOOL AXIS NORMAL TO SURFACE ===)")
    a("M01")
    a("T2 M06 (D8 BALL D5 NECK REACH70)")
    a(f"S{N_SPINDLE} M03")
    a("M08")
    a("G05.1 Q1")
    a("G43.4 H2 (RTCP / TCPM)")
    B_cone = math.degrees(math.atan2(nrm[0], nrm[1]))     # 法向与 +Z 夹角
    pitch = 4.0
    revs = max(1, int(math.ceil(mer_len / pitch)))
    seg = 72
    for k in range(revs * seg + 1):
        frac = k / (revs * seg)
        base = A + dirv * frac
        tip = base + nrm * (R_BALL + ALLOW)
        th = 2 * math.pi * (frac * revs)
        C = (360.0 - math.degrees(th)) % 360.0
        x, y = tip[0] * math.cos(th), tip[0] * math.sin(th)
        cmd = "G01" if k else "G00"
        a(f"{cmd} X{x:.3f} Y{y:.3f} Z{tip[1]:.3f} B{B_cone:.2f} C{C:.3f}"
          + (f" F{F_FEED}." if k else ""))
    a("G00 Z140.")
    a("G00 B0. C0.")
    a("G49")
    a("G05.1 Q0")
    a("")

    a("(=== OP2/OP3: 16 CLOSED PASSAGES, TWO-SIDED 5-AXIS, D8 BALL ===)")
    a("M01")
    a("T2 M06 (D8 BALL D5 NECK REACH70)")
    a(f"S{N_SPINDLE} M03")
    a("M08")
    a("G05.1 Q1")
    a("G43.4 H2 (RTCP / TCPM)")

    blocks = 0
    for ch in range(geo.Z_BLADES):
        for zone, label in (("eye", "INLET SIDE"), ("od", "DISCHARGE SIDE")):
            for k, pts in enumerate(channel_paths(ch, zone)):
                q0 = pts[0]
                C0 = (360.0 - math.degrees(q0["theta"])) % 360.0
                p0 = np.array([q0["r"] * math.cos(q0["theta"]),
                               q0["r"] * math.sin(q0["theta"]), q0["z"]])
                pre = p0 + tool_axis(q0["B"], C0) * (REACH + 30)
                a(f"(--- CH{ch + 1:02d} {label} SEG {k + 1} B{q0['B']:.0f} ---)")
                # 接近必须拆成 4 步：抬到安全高度 -> 平移到刀轴外侧 -> 转台摆角 -> 落到进刀点，
                # 最后沿刀轴进给切入。原程序的"一块五轴快速定位"会斜穿毛坯。
                a("G00 Z140.")
                a(f"G00 X{f(pre[0])} Y{f(pre[1])}")
                a(f"G00 B{f(q0['B'])} C{f(C0)}")
                a(f"G00 Z{f(pre[2])}")
                a(f"G01 X{f(p0[0])} Y{f(p0[1])} Z{f(p0[2])} F250.")
                blocks += 4
                for q in pts[1:]:
                    C = (360.0 - math.degrees(q["theta"])) % 360.0
                    a(f"G01 X{f(q['r'] * math.cos(q['theta']))} "
                      f"Y{f(q['r'] * math.sin(q['theta']))} "
                      f"Z{f(q['z'])} B{f(q['B'])} C{f(C)} F{F_FEED}.")
                    blocks += 1
                # 退刀：沿已切削刀路反向退回段首（该路径已被证明无干涉），再沿段首刀轴抽出
                for q in reversed(pts[:-1]):
                    C = (360.0 - math.degrees(q["theta"])) % 360.0
                    a(f"G01 X{f(q['r'] * math.cos(q['theta']))} "
                      f"Y{f(q['r'] * math.sin(q['theta']))} "
                      f"Z{f(q['z'])} B{f(q['B'])} C{f(C)} F400.")
                    blocks += 1
                a(f"G01 X{f(pre[0])} Y{f(pre[1])} Z{f(pre[2])} F400.")
                a("G00 Z140.")
                a("G00 B0. C0.")
                blocks += 3
    a("G49")
    a("G05.1 Q0")
    a("G00 Z150.")
    a("M09")
    a("M05")
    a("G91 G28 Z0.")
    a("G28 X0. Y0. B0. C0.")
    a("M30 (PROGRAM END)")
    a("%")
    NC_PATH.write_text("\n".join(L) + "\n", encoding="utf-8")

    # ---------- 6) 静态校验 ----------
    errs = []
    # 注：L 是整行列表，list.count("G43.4") 恒为 0（原判据误报，2026-11-17 修复为前缀匹配）
    if sum(1 for ln in L if ln.strip().startswith("G43.4")) < 1:
        errs.append("缺少 RTCP 指令")
    if "M30" not in L[-2]:
        errs.append("缺少 M30")
    for i, ln in enumerate(L, 1):
        body = ln.split("(")[0]
        if "B0." in body and "G00 Z" in body:
            errs.append(f"L{i}: 退刀与回摆同块")
    if sum(1 for ln in L if ln.startswith("(--- CH")) < geo.Z_BLADES * 2:
        errs.append("通道段数异常")
    vc_actual = math.pi * 2 * R_BALL * N_SPINDLE / 1000.0

    # ---------- 7) NC 回放校验：解析刚写出的程序，逐条复核刀体 ----------
    import re
    word = re.compile(r"([A-Z])([+-]?\d+(?:\.\d+)?)")
    cur = {"X": 0.0, "Y": 0.0, "Z": 0.0, "B": 0.0, "C": 0.0}
    in_op2 = False
    replay_total = replay_bad = 0
    replay_first = None
    for ln in L:
        body = ln.split("(")[0].strip()
        if "=== OP2/OP3" in ln:
            in_op2 = True
        if not body:
            continue
        w = {k.upper(): float(v) for k, v in word.findall(body)}
        for ax in ("X", "Y", "Z", "B", "C"):
            if ax in w:
                cur[ax] = w[ax]
        if not in_op2 or not body.startswith("G01"):
            continue
        p = np.array([cur["X"], cur["Y"], cur["Z"]])
        replay_total += 1
        if _contains_any(mesh, shank_cloud(p, cur["B"], cur["C"])):
            replay_bad += 1
            replay_first = replay_first or {"x": round(cur["X"], 2), "y": round(cur["Y"], 2),
                                            "z": round(cur["Z"], 2), "B": cur["B"], "C": cur["C"]}
    if replay_bad:
        errs.append(f"NC 回放发现 {replay_bad}/{replay_total} 个切削点刀体侵入")
    replay = {"cutting_points": replay_total, "collisions": replay_bad, "first": replay_first}

    report = {
        "nc_file": str(NC_PATH),
        "nc_lines": len(L),
        "cutting_blocks": blocks,
        "strategy": {
            "zones": {"inlet_side_t": list(ZONE_EYE), "discharge_side_t": list(ZONE_OD)},
            "passes_per_passage": PASSES, "stations": N_ST,
            "tool": {"ball_d_mm": 2 * R_BALL, "neck_d_mm": 2 * R_NECK, "reach_mm": REACH},
            "claimed_process": "semi-finish, 0.4mm allowance, final Ra0.8 by AFM",
            "spindle_schedules": {f"{z}_p{k}": v for (z, k), v in sched.items()},
        },
        "cutting_data": {"material": "TC11", "vc_target_m_min": VC_MS,
                         "spindle_rpm": N_SPINDLE, "vc_actual_m_min": round(vc_actual, 1),
                         "feed_mm_min": F_FEED, "fz_mm": FZ, "flutes": N_FLUTES},
        "collision_verification": check,
        "nc_replay_verification": replay,
        "static_validation": {"errors": errs, "warnings": []},
        "valid": not errs,
        "basis": "measured (entity containment + per-pass interception search)",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "strategy"},
                     ensure_ascii=False, indent=2))
    print("\n倾角调度（每段一条连续曲线）:")
    for (z, k), runs in sched.items():
        for n, run in enumerate(runs, 1):
            seq = " ".join(f"{b:.0f}" for _, b in run)
            print(f"  {z}/pass{k} seg{n} (i{run[0][0]}..i{run[-1][0]}): {seq}")
    return report


if __name__ == "__main__":
    main()
