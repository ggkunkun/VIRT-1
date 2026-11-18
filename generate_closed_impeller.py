# -*- coding: utf-8 -*-
"""
Aero-Engine Closed Impeller (Shrouded Impeller / 闭式叶轮) Generator
1. Generates High-Resolution Engineering Blueprint Image (PNG) with Full Axial Section View & Plan View.
2. Generates Standard Layered CAD DXF (ezdxf).
3. Generates 3D Parametric CAD Solid Model (STEP & STL) via build123d.
"""

import os
import math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import ezdxf
from build123d import *

# Set font for clear Chinese engineering annotation
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

output_dir = r"C:\Users\Administrator\.gemini\antigravity\brain\adc7374e-187c-4d80-8350-b1df2ce4409e"
png_path = os.path.join(output_dir, "closed_impeller_blueprint.png")
dxf_path = os.path.join(output_dir, "closed_impeller_blueprint.dxf")
step_path = os.path.join(output_dir, "closed_impeller.step")
design_stl = r"D:\Virtu模型\closed_impeller_design.stl"
stock_stl = r"D:\Virtu模型\closed_impeller_stock.stl"

# ==============================================================
# 1. 闭式叶轮三维参数化 CAD 建模 (build123d)
# ==============================================================
print(">>> Generating 3D Closed Impeller CAD Model...")

# Dimensions:
# Outlet Diameter D2 = 160 mm (Radius R2 = 80 mm)
# Inlet Shroud Eye D1s = 70 mm (Radius R1s = 35 mm)
# Shaft Hole Dh = 28 mm (Radius Rh = 14 mm)
# Hub Height H = 45 mm
# Shroud Thickness = 3.5 mm, Hub Base Thickness = 6.0 mm
# Number of Blades Z = 10

try:
    with BuildPart() as impeller:
        # 1.1 轮盘体 (Hub Solid - Revolve)
        with BuildSketch(Plane.XZ):
            hub_pts = [
                (14, 0),    # shaft hole bottom
                (80, 0),    # outlet bottom
                (80, 6),    # outlet edge
                (35, 30),   # hub curve mid
                (14, 45),   # hub top
                (14, 0)     # close
            ]
            Polygon([Vector(p[0], p[1]) for p in hub_pts])
        revolve(axis=Axis.Z)
        
        # 1.2 前轮盖 (Shroud Cover - Revolve)
        with BuildSketch(Plane.XZ):
            shroud_pts = [
                (35, 45),   # inlet inner lip
                (38.5, 45), # inlet outer lip
                (80, 16),   # outlet top
                (80, 12.5), # outlet bottom lip
                (35, 41.5), # inner shroud curve
                (35, 45)    # close
            ]
            Polygon([Vector(p[0], p[1]) for p in shroud_pts])
        revolve(axis=Axis.Z)
        
        # 1.3 内部封闭扭曲叶片 (10 Blades inside Hub and Shroud)
        # Blade spans between hub profile and shroud inner profile
        # Sweeping along backward logarithmic spiral
        num_blades = 10
        blade_thick = 2.5
        
        for i in range(num_blades):
            angle_deg = i * (360.0 / num_blades)
            # Create a twisted curved blade rib
            with BuildSketch(Plane.XY.offset(6)):
                with Locations(Rotation(0, 0, angle_deg)):
                    # 2D arc from inlet (r=35) to outlet (r=80)
                    pts_blade = []
                    for t in np.linspace(0, 1, 15):
                        r = 35.0 + (80.0 - 35.0) * t
                        phi = -math.radians(35.0 * (t**1.4)) # backward curved
                        pts_blade.append((r * math.cos(phi), r * math.sin(phi)))
                    # thicken to polygon
                    poly_forward = [(p[0] + blade_thick*0.5, p[1]) for p in pts_blade]
                    poly_back = [(p[0] - blade_thick*0.5, p[1]) for p in reversed(pts_blade)]
                    Polygon([Vector(p[0], p[1]) for p in (poly_forward + poly_back)])
            extrude(amount=30)
            
    impeller_part = impeller.part
    print(f"Closed Impeller modeled successfully!")
    print(f"Volume: {impeller_part.volume:.2f} mm^3")
    print(f"Bounding Box: {impeller_part.bounding_box()}")
    
    # Export STEP
    export_step(impeller_part, step_path)
    print(f"Exported STEP to: {step_path}")
    
    # Export STL
    export_stl(impeller_part, design_stl)
    print(f"Exported Design STL to: {design_stl}")
    
    # Create matching cylindrical blank stock (D=165mm, H=50mm)
    with BuildPart() as stock_p:
        Cylinder(radius=82.5, height=52)
    export_stl(stock_p.part, stock_stl)
    print(f"Exported Stock STL to: {stock_stl}")

except Exception as e:
    import traceback
    traceback.print_exc()

# ==============================================================
# 2. 闭式叶轮标准工程图纸生成 (Matplotlib + ezdxf)
# ==============================================================
print(">>> Generating Engineering Blueprint Image & DXF...")

fig = plt.figure(figsize=(19, 13), dpi=220)
ax = fig.add_subplot(111)

ax.set_xlim(-15, 415)
ax.set_ylim(-10, 290)
ax.set_aspect('equal')
ax.axis('off')

# Standard Border (GB/T 14665)
ax.plot([0, 400, 400, 0, 0], [0, 0, 275, 275, 0], 'k-', lw=1.8)
ax.plot([20, 395, 395, 20, 20], [5, 5, 270, 270, 5], 'k-', lw=1.0)

# Title Block (Bottom Right)
bx, by, bw, bh = 235, 5, 160, 50
ax.add_patch(patches.Rectangle((bx, by), bw, bh, fill=False, edgecolor='black', lw=1.4))
for y_off in [12, 24, 37]:
    ax.plot([bx, bx + bw], [by + y_off, by + y_off], 'k-', lw=0.8)
for x_off in [40, 100, 130]:
    ax.plot([bx + x_off, bx + x_off], [by, by + bh], 'k-', lw=0.8)

ax.text(bx + 20, by + 43, '零件名称', ha='center', va='center', fontsize=9, weight='bold')
ax.text(bx + 70, by + 43, '航空闭式叶轮 (封闭叶轮)', ha='center', va='center', fontsize=11, weight='bold', color='navy')
ax.text(bx + 115, by + 43, '阶段标记', ha='center', va='center', fontsize=8)
ax.text(bx + 145, by + 43, '科研生产 (S)', ha='center', va='center', fontsize=9, weight='bold')

ax.text(bx + 20, by + 30, '零件图号', ha='center', va='center', fontsize=9, weight='bold')
ax.text(bx + 70, by + 30, 'AE-SHR-IMP-002', ha='center', va='center', fontsize=10, weight='bold', color='navy')
ax.text(bx + 115, by + 30, '比例', ha='center', va='center', fontsize=8)
ax.text(bx + 145, by + 30, '1 : 1.5', ha='center', va='center', fontsize=9, weight='bold')

ax.text(bx + 20, by + 18, '材料牌号', ha='center', va='center', fontsize=9, weight='bold')
ax.text(bx + 70, by + 18, 'TC11 钛合金 / Inconel 718', ha='center', va='center', fontsize=9, color='navy')
ax.text(bx + 115, by + 18, '重量', ha='center', va='center', fontsize=8)
ax.text(bx + 145, by + 18, '1.68 kg', ha='center', va='center', fontsize=9)

ax.text(bx + 20, by + 6, '工艺规范', ha='center', va='center', fontsize=8)
ax.text(bx + 70, by + 6, '五轴插铣 + 摇动放电 / 扩散焊', ha='center', va='center', fontsize=8)
ax.text(bx + 115, by + 6, '张数', ha='center', va='center', fontsize=8)
ax.text(bx + 145, by + 6, '第 1 张 共 1 张', ha='center', va='center', fontsize=8)

# -------------------------------------------------------------
# View 1: 主视图 (过旋转轴线的全剖视图 - Full Axial Section View)
# Demonstrates Hub, Shroud, Internal Enclosed Channel, Shaft Bore
# Center: cx=125, cy=85 (Scaled 0.8: R80 -> 64mm, H45 -> 36mm)
# -------------------------------------------------------------
mcx, mcy = 125, 80
sc = 0.8  # scale factor for drafting

# Centerline (Axis of Rotation)
ax.plot([mcx, mcx], [mcy - 15, mcy + 65], 'r-.', lw=0.9)

# Right half Hub Profile
rh_pts = [(0, 0), (14, 0), (80, 0), (80, 6), (35, 30), (14, 45), (0, 45)]
rh_scaled = [(mcx + p[0]*sc, mcy + p[1]*sc) for p in rh_pts]

# Right half Shroud Profile (Closed cover)
rs_pts = [(35, 45), (38.5, 45), (80, 16), (80, 12.5), (35, 41.5), (35, 45)]
rs_scaled = [(mcx + p[0]*sc, mcy + p[1]*sc) for p in rs_pts]

# Left half (mirrored)
lh_scaled = [(mcx - p[0]*sc, mcy + p[1]*sc) for p in rh_pts]
ls_scaled = [(mcx - p[0]*sc, mcy + p[1]*sc) for p in rs_pts]

# Draw Solid Outlines
for poly, color in [(rh_scaled, 'k-'), (lh_scaled, 'k-')]:
    px, py = zip(*poly)
    ax.plot(px, py, color, lw=1.6)

for poly, color in [(rs_scaled, 'k-'), (ls_scaled, 'k-')]:
    px, py = zip(*poly)
    ax.plot(px, py, color, lw=1.6)

# Internal Blade Section (Connecting Hub and Shroud in Section)
# Shown as hatched blade cross-section in flow channel
ax.plot([mcx + 35*sc, mcx + 35*sc], [mcy + 30*sc, mcy + 41.5*sc], 'k-', lw=1.2)
ax.plot([mcx + 60*sc, mcx + 60*sc], [mcy + 15*sc, mcy + 22.5*sc], 'k-', lw=1.2)
ax.plot([mcx - 35*sc, mcx - 35*sc], [mcy + 30*sc, mcy + 41.5*sc], 'k-', lw=1.2)
ax.plot([mcx - 60*sc, mcx - 60*sc], [mcy + 15*sc, mcy + 22.5*sc], 'k-', lw=1.2)

# Hatching Hub & Shroud
ax.fill([p[0] for p in rh_scaled], [p[1] for p in rh_scaled], hatch='//', fill=False, edgecolor='gray', lw=0.5)
ax.fill([p[0] for p in lh_scaled], [p[1] for p in lh_scaled], hatch=r'\\', fill=False, edgecolor='gray', lw=0.5)
ax.fill([p[0] for p in rs_scaled], [p[1] for p in rs_scaled], hatch='//', fill=False, edgecolor='gray', lw=0.5)
ax.fill([p[0] for p in ls_scaled], [p[1] for p in ls_scaled], hatch=r'\\', fill=False, edgecolor='gray', lw=0.5)

# Annotation for Enclosed Flow Channel
ax.annotate('内部封闭流道\n(叶片完全包覆在轮盘与前轮盖之间)', 
            xy=(mcx + 55*sc, mcy + 20*sc), xytext=(mcx + 75*sc, mcy + 35*sc),
            arrowprops=dict(arrowstyle='->', color='crimson', lw=1.2),
            fontsize=9, color='crimson', weight='bold')

ax.annotate('前轮盖 (Shroud / 封闭盖板)', 
            xy=(mcx + 65*sc, mcy + 15*sc), xytext=(mcx + 75*sc, mcy + 5*sc),
            arrowprops=dict(arrowstyle='->', color='navy', lw=1.0),
            fontsize=8.5, color='navy', weight='bold')

ax.annotate('后轮盘 (Hub / 轮盘体)', 
            xy=(mcx + 70*sc, mcy + 3*sc), xytext=(mcx + 75*sc, mcy - 12*sc),
            arrowprops=dict(arrowstyle='->', color='navy', lw=1.0),
            fontsize=8.5, color='navy', weight='bold')

# Dimension Callouts
# 1. Outlet Diameter D2 = 160 mm
ax.annotate('', xy=(mcx + 80*sc, mcy - 8), xytext=(mcx - 80*sc, mcy - 8),
            arrowprops=dict(arrowstyle='<->', color='black', lw=1.0))
ax.plot([mcx + 80*sc, mcx + 80*sc], [mcy, mcy - 12], 'k:', lw=0.6)
ax.plot([mcx - 80*sc, mcx - 80*sc], [mcy, mcy - 12], 'k:', lw=0.6)
ax.text(mcx, mcy - 11, '出口外径 Φ160 ±0.02', ha='center', va='top', fontsize=9, weight='bold')

# 2. Inlet Eye Diameter D1s = 70 mm
ax.annotate('', xy=(mcx + 35*sc, mcy + 52*sc), xytext=(mcx - 35*sc, mcy + 52*sc),
            arrowprops=dict(arrowstyle='<->', color='black', lw=0.9))
ax.plot([mcx + 35*sc, mcx + 35*sc], [mcy + 45*sc, mcy + 55*sc], 'k:', lw=0.6)
ax.plot([mcx - 35*sc, mcx - 35*sc], [mcy + 45*sc, mcy + 55*sc], 'k:', lw=0.6)
ax.text(mcx, mcy + 54*sc, '进气口径 Φ70 ±0.03', ha='center', va='bottom', fontsize=9, weight='bold')

# 3. Shaft Bore Diameter = 28 mm
ax.annotate('', xy=(mcx + 14*sc, mcy + 25*sc), xytext=(mcx - 14*sc, mcy + 25*sc),
            arrowprops=dict(arrowstyle='<->', color='black', lw=0.8))
ax.text(mcx, mcy + 27*sc, 'Φ28 H7', ha='center', va='bottom', fontsize=8, weight='bold')

# 4. Total Height H = 45 mm
ax.annotate('', xy=(mcx - 90*sc, mcy + 45*sc), xytext=(mcx - 90*sc, mcy),
            arrowprops=dict(arrowstyle='<->', color='black', lw=0.9))
ax.plot([mcx - 95*sc, mcx - 14*sc], [mcy + 45*sc, mcy + 45*sc], 'k:', lw=0.6)
ax.plot([mcx - 95*sc, mcx - 80*sc], [mcy, mcy], 'k:', lw=0.6)
ax.text(mcx - 93*sc, mcy + 22.5*sc, '总高 45', ha='right', va='center', rotation=90, fontsize=9, weight='bold')

ax.text(mcx, mcy - 30, '主视图 (A-A 全剖视图)\n封闭式内部流道构造', ha='center', va='top', fontsize=11, weight='bold')

# -------------------------------------------------------------
# View 2: 俯视投影与内部叶片三元流型线 (Top Plan View)
# Center: cx=290, cy=180 (Radius 80*0.75 = 60mm)
# -------------------------------------------------------------
tcx, tcy = 295, 185
tsc = 0.72

# Circles: Outer Diameter, Inlet Shroud Ring, Shaft Bore
circle_out = patches.Circle((tcx, tcy), 80*tsc, fill=False, edgecolor='black', lw=1.6)
circle_inlet = patches.Circle((tcx, tcy), 35*tsc, fill=False, edgecolor='navy', lw=1.2, ls='--')
circle_bore = patches.Circle((tcx, tcy), 14*tsc, fill=False, edgecolor='black', lw=1.2)
ax.add_patch(circle_out)
ax.add_patch(circle_inlet)
ax.add_patch(circle_bore)

# Centerlines
ax.plot([tcx - 90*tsc, tcx + 90*tsc], [tcy, tcy], 'r-.', lw=0.7)
ax.plot([tcx, tcx], [tcy - 90*tsc, tcy + 90*tsc], 'r-.', lw=0.7)

# Draw 10 Backward Curved Blades (Hidden under shroud: dashed lines)
for i in range(10):
    ang = i * (2 * math.pi / 10)
    # blade spiral curve from r=35 to r=80
    r_arr = np.linspace(35*tsc, 80*tsc, 25)
    t_arr = np.linspace(0, 1, 25)
    phi_arr = ang - np.radians(38.0 * (t_arr**1.35))
    xb = tcx + r_arr * np.cos(phi_arr)
    yb = tcy + r_arr * np.sin(phi_arr)
    ax.plot(xb, yb, 'b--', lw=1.2) # dashed because inside closed shroud

ax.annotate('10 片三元后弯封闭叶片\n(前轮盖下方隐蔽流道)', xy=(tcx + 45*tsc, tcy + 35*tsc), xytext=(tcx + 55*tsc, tcy + 65*tsc),
            arrowprops=dict(arrowstyle='->', color='blue', lw=0.9), fontsize=8.5, color='blue', weight='bold')

# Callouts on Top View
ax.annotate('出口叶片安放角\nβ2 = 32° (后弯)', xy=(tcx + 78*tsc, tcy + 8*tsc), xytext=(tcx + 65*tsc, tcy - 30*tsc),
            arrowprops=dict(arrowstyle='->', color='darkred', lw=0.8), fontsize=8, color='darkred')

ax.text(tcx, tcy - 72*tsc, '俯视图 (Top Plan View)\n10叶片三元流闭式布局', ha='center', va='top', fontsize=11, weight='bold')

# -------------------------------------------------------------
# Technical Specifications Box (Top Left: x=25, y=185)
# -------------------------------------------------------------
ax.text(25, 260, '【闭式叶轮设计与制造技术规范】(CLOSED IMPELLER SPECIFICATIONS)', fontsize=10.5, weight='bold', color='darkred')
specs = [
    '1. 零件构型与功能定义：',
    '   - 结构特征：由轮盘(Hub)、前轮盖(Shroud)与10片内部三维扭曲后弯叶片(Blades)组成的完全封闭流道。',
    '   - 气动优势：消除叶尖漏气损失，单级绝热效率 η ≥ 84.5%，总压比 π ≥ 4.8。',
    '2. 材质与热处理：',
    '   - TC11 钛合金 (Ti-6.5Al-3.5Mo-1.5Zr-0.3Si) 模锻毛坯。',
    '   - 双重退火制度：960℃×2h/空冷 + 530℃×6h/空冷，抗拉强度 σb ≥ 1050 MPa。',
    '3. 五轴特种加工工艺路线 (Extreme CAM Route)：',
    '   - 工步一：五轴大进给深切插铣粗开进气口与外缘轮廓。',
    '   - 工步二：五轴联动特种加长杆棒糖铣刀 (Lollipop Cutter) / 弯头刀伸入内部封闭流道多轴精铣。',
    '   - 工步三：多轴数控摇动电火花 (Orbital EDM) 或电解精加工 (ECM) 完成叶盆与叶背高精度修光。',
    '4. 精度公差与表面质量 (GD&T)：',
    '   - 轮毂内孔同轴度与端面跳动: ⌖ 0.008 mm，圆柱度: ○ 0.005 mm。',
    '   - 封闭流道叶片型面三维轮廓度: ⌒ 0.035 mm (三坐标蓝光/工业CT三维无损复测)。',
    '   - 内部流道表面粗糙度: Ra ≤ 0.4 μm (特种磨料流抛光 / AFM)。',
    '5. 动平衡检验：超高速动平衡 G 1.0 级，工作转速 65,000 RPM 下残余不平衡量 ≤ 0.15 g·mm。'
]

for idx, sp in enumerate(specs):
    ax.text(25, 246 - idx * 7.8, sp, fontsize=7.8, color='black')

plt.tight_layout()
fig.savefig(png_path, dpi=240, bbox_inches='tight')
plt.close(fig)
print(f"Closed impeller blueprint generated: {png_path}")

# DXF Generation
doc = ezdxf.new('R2010')
msp = doc.modelspace()
doc.layers.add(name='OUTLINE', color=7)
doc.layers.add(name='CENTER', color=1)
doc.layers.add(name='SECTION', color=4)
doc.layers.add(name='TITLE', color=3)

# Add title block & main outlines
msp.add_lwpolyline(rh_pts, close=True, dxfattribs={'layer': 'OUTLINE'})
msp.add_lwpolyline(rs_pts, close=True, dxfattribs={'layer': 'OUTLINE'})
msp.add_circle((0, 0), 80, dxfattribs={'layer': 'OUTLINE'})
msp.add_circle((0, 0), 35, dxfattribs={'layer': 'OUTLINE'})
msp.add_circle((0, 0), 14, dxfattribs={'layer': 'OUTLINE'})
msp.add_text('CLOSED IMPELLER - AE-SHR-IMP-002', dxfattribs={'layer': 'TITLE', 'height': 5.0}).set_placement((0, -25))
doc.saveas(dxf_path)
print(f"Closed impeller DXF generated: {dxf_path}")
