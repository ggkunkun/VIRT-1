"""可视化校验报告生成器（独立单文件 HTML + SVG 刀轨与风险点标注）。"""
from __future__ import annotations

import html
from typing import Any, Dict, List, Optional, Tuple

from cam_autogen.contracts import MachineSetup, NCProgram, ProcessPlan, ProcessType, RiskItem, StockSetup, VerificationReport


def _svg_milling(program: NCProgram, stock_setup: Optional[StockSetup], risk_points: List[Dict[str, Any]]) -> str:
    pts: List[Tuple[float, float, float, str]] = []
    cx = cy = cz = 0.0
    for m in program.ir:
        if m.kind in ("rapid", "linear", "arc_cw", "arc_ccw"):
            nx = float(m.x) if m.x is not None else cx
            ny = float(m.y) if m.y is not None else cy
            nz = float(m.z) if m.z is not None else cz
            pts.append((nx, ny, nz, m.kind))
            cx, cy, cz = nx, ny, nz

    xs = [p[0] for p in pts] or [0.0, 100.0]
    ys = [p[1] for p in pts] or [0.0, 80.0]
    zs = [p[2] for p in pts] or [-30.0, 30.0]
    if stock_setup:
        for fz in stock_setup.fixture_zones:
            xs.extend([fz.box[0], fz.box[1]])
            ys.extend([fz.box[2], fz.box[3]])
            zs.extend([fz.box[4], fz.box[5]])

    xmin, xmax = min(xs) - 10, max(xs) + 10
    ymin, ymax = min(ys) - 10, max(ys) + 10
    zmin, zmax = min(zs) - 10, max(zs) + 10
    w, h = 480, 320

    def map_xy(x: float, y: float) -> Tuple[float, float]:
        sx = 20 + (x - xmin) / max(xmax - xmin, 1.0) * (w - 40)
        sy = h - 20 - (y - ymin) / max(ymax - ymin, 1.0) * (h - 40)
        return round(sx, 1), round(sy, 1)

    def map_xz(x: float, z: float) -> Tuple[float, float]:
        sx = 20 + (x - xmin) / max(xmax - xmin, 1.0) * (w - 40)
        sy = h - 20 - (z - zmin) / max(zmax - zmin, 1.0) * (h - 40)
        return round(sx, 1), round(sy, 1)

    xy_segs, xz_segs = [], []
    px, py, pz = 0.0, 0.0, 26.0
    for nx, ny, nz, kind in pts:
        color = "#d97706" if kind == "rapid" else "#2563eb"
        dash = ' stroke-dasharray="4 3"' if kind == "rapid" else ""
        x1, y1 = map_xy(px, py)
        x2, y2 = map_xy(nx, ny)
        xy_segs.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1.2"{dash}/>')
        x1z, z1p = map_xz(px, pz)
        x2z, z2p = map_xz(nx, nz)
        xz_segs.append(f'<line x1="{x1z}" y1="{z1p}" x2="{x2z}" y2="{z2p}" stroke="{color}" stroke-width="1.2"{dash}/>')
        px, py, pz = nx, ny, nz

    fix_xy, fix_xz = [], []
    if stock_setup:
        for fz in stock_setup.fixture_zones:
            bx0, bx1, by0, by1, bz0, bz1 = fz.box
            p1, p2 = map_xy(bx0, by1), map_xy(bx1, by0)
            fix_xy.append(f'<rect x="{p1[0]}" y="{p1[1]}" width="{max(1, p2[0]-p1[0]):.1f}" '
                          f'height="{max(1, p2[1]-p1[1]):.1f}" fill="rgba(220,38,38,0.12)" stroke="#dc2626" stroke-dasharray="3 2"/>')
            q1, q2 = map_xz(bx0, bz1), map_xz(bx1, bz0)
            fix_xz.append(f'<rect x="{q1[0]}" y="{q1[1]}" width="{max(1, q2[0]-q1[0]):.1f}" '
                          f'height="{max(1, q2[1]-q1[1]):.1f}" fill="rgba(220,38,38,0.12)" stroke="#dc2626" stroke-dasharray="3 2"/>')

    r_xy, r_xz = [], []
    for rp in risk_points[:20]:
        rx, ry = map_xy(rp["x"], rp["y"])
        rx2, rz2 = map_xz(rp["x"], rp["z"])
        r_xy.append(f'<circle cx="{rx}" cy="{ry}" r="6" fill="rgba(220,38,38,0.3)" stroke="#b91c1c" stroke-width="2"/>')
        r_xz.append(f'<circle cx="{rx2}" cy="{rz2}" r="6" fill="rgba(220,38,38,0.3)" stroke="#b91c1c" stroke-width="2"/>')

    return (
        f'<div class="svg-grid">'
        f'<svg viewBox="0 0 {w} {h}" class="plot"><text x="10" y="16" font-size="12" fill="#334155">XY 俯视刀轨 (蓝=切削 橙虚=快进 红框=虎钳/垫铁)</text>'
        f'{"".join(fix_xy)}{"".join(xy_segs)}{"".join(r_xy)}</svg>'
        f'<svg viewBox="0 0 {w} {h}" class="plot"><text x="10" y="16" font-size="12" fill="#334155">XZ 侧视刀轨 (含 Z 向分层与安全高度)</text>'
        f'{"".join(fix_xz)}{"".join(xz_segs)}{"".join(r_xz)}</svg>'
        f'</div>'
    )


def _svg_turning(program: NCProgram, stock_setup: Optional[StockSetup], risk_points: List[Dict[str, Any]]) -> str:
    pts: List[Tuple[float, float, str]] = []
    cx, cz = 120.0, 60.0
    for m in program.ir:
        if m.kind in ("rapid", "linear", "arc_cw", "arc_ccw", "thread"):
            nx = float(m.x) if m.x is not None else cx
            nz = float(m.z) if m.z is not None else cz
            pts.append((nz, nx / 2.0, m.kind))
            cx, cz = nx, nz

    zs = [p[0] for p in pts] or [-100.0, 60.0]
    rs = [p[1] for p in pts] or [-30.0, 70.0]
    if stock_setup:
        for fz in stock_setup.fixture_zones:
            zs.extend([fz.box[0], fz.box[1]])
            rs.extend([fz.box[2], fz.box[3]])
    zmin, zmax = min(zs) - 10, max(zs) + 10
    rmin, rmax = min(min(rs), -15.0) - 10, max(rs) + 10
    w, h = 920, 320

    def mzx(z: float, r: float) -> Tuple[float, float]:
        sx = 20 + (z - zmin) / max(zmax - zmin, 1.0) * (w - 40)
        sy = h - 20 - (r - rmin) / max(rmax - rmin, 1.0) * (h - 40)
        return round(sx, 1), round(sy, 1)

    segs = []
    pz, pr = 60.0, 60.0
    for nz, nr, kind in pts:
        color = "#d97706" if kind == "rapid" else ("#7c3aed" if kind == "thread" else "#2563eb")
        dash = ' stroke-dasharray="4 3"' if kind == "rapid" else ""
        x1, y1 = mzx(pz, pr)
        x2, y2 = mzx(nz, nr)
        segs.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1.4"{dash}/>')
        pz, pr = nz, nr

    # 主轴中心线
    c1, c2 = mzx(zmin, 0.0), mzx(zmax, 0.0)
    centerline = f'<line x1="{c1[0]}" y1="{c1[1]}" x2="{c2[0]}" y2="{c2[1]}" stroke="#64748b" stroke-dasharray="8 4 2 4"/>'

    fix_rects = []
    if stock_setup:
        for fz in stock_setup.fixture_zones:
            bz0, bz1, br0, br1 = fz.box
            p1, p2 = mzx(bz0, br1), mzx(bz1, br0)
            fix_rects.append(f'<rect x="{p1[0]}" y="{p1[1]}" width="{max(1, p2[0]-p1[0]):.1f}" '
                             f'height="{max(1, p2[1]-p1[1]):.1f}" fill="rgba(220,38,38,0.12)" stroke="#dc2626" stroke-dasharray="3 2"/>')

    r_marks = []
    for rp in risk_points[:20]:
        rx, ry = mzx(rp["z"], rp["x"] / 2.0)
        r_marks.append(f'<circle cx="{rx}" cy="{ry}" r="6" fill="rgba(220,38,38,0.3)" stroke="#b91c1c" stroke-width="2"/>')

    return (
        f'<svg viewBox="0 0 {w} {h}" class="plot">'
        f'<text x="10" y="16" font-size="12" fill="#334155">ZX 车削半剖刀轨 (横轴Z 纵轴半径R | 蓝=切削 紫=螺纹 橙虚=快进 红框=卡爪/尾座)</text>'
        f'{centerline}{"".join(fix_rects)}{"".join(segs)}{"".join(r_marks)}</svg>'
    )


def render_html_report(
    report: VerificationReport,
    program: NCProgram,
    setup: MachineSetup,
    stock_setup: Optional[StockSetup] = None,
    plan: Optional[ProcessPlan] = None,
) -> str:
    status_cls = "pass" if report.passed else "fail"
    status_txt = "PASSED（零修改可上机）" if report.passed else "BLOCKED（检出阻断风险）"
    rpts = report.path_check.get("risk_points", [])
    svg = (_svg_milling(program, stock_setup, rpts) if program.process_type == ProcessType.MILLING
           else _svg_turning(program, stock_setup, rpts))

    badges = "".join(
        f'<div class="badge {lvl}"><span>{lvl}</span><b>{report.summary.get(lvl, 0)}</b></div>'
        for lvl in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")
    )
    risk_rows = "".join(
        f'<tr><td><span class="pill {r.level}">{r.level}</span></td><td>{html.escape(r.check)}</td>'
        f'<td><code>{html.escape(r.code)}</code></td><td>{html.escape(r.message)}</td>'
        f'<td><code>{html.escape(str(r.location))}</code></td></tr>'
        for r in report.risks
    ) or '<tr><td colspan="5" style="text-align:center;color:#16a34a">未发现任何风险或告警项</td></tr>'

    op_rows = "".join(
        f'<tr><td>{op.op_id}</td><td>{op.category}</td><td>{op.tool.tool_id}</td>'
        f'<td>{op.params.vc_m_min}</td><td>{op.params.rpm:.0f}</td><td>{op.params.feed_mm_min}</td>'
        f'<td>{op.params.ap_mm}</td><td>{op.metrics.ra_pred_um}</td><td>{op.metrics.power_kw}</td>'
        f'<td>{op.metrics.cut_time_min}</td></tr>'
        for op in (plan.operations if plan else [])
    )

    m = setup.machine
    prog_escaped = html.escape("\n".join(program.program_text.splitlines()[:120]))
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/>
<title>CAM 双重校验报告 - {html.escape(report.part_id)}</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;margin:0;padding:24px;background:#f8fafc;color:#0f172a}}
.card{{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:18px;margin-bottom:16px;box-shadow:0 1px 2px rgba(0,0,0,.04)}}
.hdr{{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}}
.status{{padding:8px 16px;border-radius:8px;font-weight:700;color:#fff}}
.status.pass{{background:#16a34a}}.status.fail{{background:#dc2626}}
.badges{{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}}
.badge{{padding:8px 14px;border-radius:8px;background:#f1f5f9;display:flex;gap:8px;align-items:center}}
.badge.CRITICAL{{border-left:4px solid #dc2626}}.badge.HIGH{{border-left:4px solid #ea580c}}
.badge.MEDIUM{{border-left:4px solid #d97706}}.badge.LOW{{border-left:4px solid #2563eb}}.badge.INFO{{border-left:4px solid #64748b}}
.svg-grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.plot{{width:100%;height:auto;border:1px solid #e2e8f0;border-radius:8px;background:#fff}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th,td{{border-bottom:1px solid #e2e8f0;padding:7px 9px;text-align:left}}th{{background:#f8fafc}}
.pill{{padding:2px 8px;border-radius:99px;font-size:11px;font-weight:700;color:#fff}}
.pill.CRITICAL{{background:#dc2626}}.pill.HIGH{{background:#ea580c}}.pill.MEDIUM{{background:#d97706}}.pill.LOW{{background:#2563eb}}.pill.INFO{{background:#64748b}}
pre{{background:#0f172a;color:#e2e8f0;padding:14px;border-radius:8px;overflow:auto;max-height:360px;font-size:12px}}
</style></head><body>
<div class="card hdr">
  <div><h1 style="margin:0 0 6px">CAM 程序双重校验报告 · {html.escape(report.part_id)}</h1>
    <div>工艺：<b>{program.process_type.value}</b> | 匹配机床：<b>{html.escape(m.model)}</b> ({html.escape(m.controller)}, {m.dialect}) | SHA256: <code>{program.sha256[:12]}</code></div></div>
  <div class="status {status_cls}">{status_txt}</div>
</div>
<div class="card"><h3 style="margin-top:0">分级告警统计</h3><div class="badges">{badges}</div></div>
<div class="card"><h3 style="margin-top:0">加工路径与夹具避让可视化</h3>{svg}</div>
<div class="card"><h3 style="margin-top:0">机床配置与行程校验</h3>
  <div>工作偏置 <b>{html.escape(setup.work_offset)}</b> = <code>{html.escape(str(setup.work_offset_values))}</code> |
       行程校验 = <b>{setup.travel_check.get("within_limits")}</b> | 刀位数 = <b>{len(setup.tool_pockets)}/{m.tool_capacity}</b></div>
  <div style="margin-top:6px"><code>{html.escape(str(setup.travel_check))}</code></div>
</div>
<div class="card"><h3 style="margin-top:0">风险与校验明细 ({len(report.risks)})</h3>
  <table><thead><tr><th>等级</th><th>校验项</th><th>代码</th><th>说明</th><th>位置</th></tr></thead>
  <tbody>{risk_rows}</tbody></table>
</div>
<div class="card"><h3 style="margin-top:0">工序优化参数</h3>
  <table><thead><tr><th>工步</th><th>类别</th><th>刀具</th><th>Vc</th><th>RPM</th><th>F</th><th>ap</th><th>Ra预测</th><th>功率kW</th><th>时间min</th></tr></thead>
  <tbody>{op_rows}</tbody></table>
</div>
<div class="card"><h3 style="margin-top:0">NC 程序预览（前 120 行）</h3><pre>{prog_escaped}</pre></div>
</body></html>
"""
