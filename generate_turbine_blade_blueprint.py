# -*- coding: utf-8 -*-
"""
Aero-Engine High-Pressure Turbine (HPT) Rotor Blade Engineering Blueprint Generator
Generates:
1. High-Resolution Blueprint Image (PNG) with complete views, dimensions, GD&T, and title block.
2. Standard DXF CAD Blueprint file (ezdxf) with layered engineering discipline.
"""

import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.path import Path as MplPath
import ezdxf

# Set font for clear Chinese engineering annotation
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

output_dir = r"C:\Users\Administrator\.gemini\antigravity\brain\adc7374e-187c-4d80-8350-b1df2ce4409e"
png_path = os.path.join(output_dir, "turbine_blade_blueprint.png")
dxf_path = os.path.join(output_dir, "turbine_blade_blueprint.dxf")

# -------------------------------------------------------------
# 1. Matplotlib Professional Blueprint Generation
# -------------------------------------------------------------
fig = plt.figure(figsize=(19, 13), dpi=220)
ax = fig.add_subplot(111)

# Drawing coordinate space (A3: 420 x 297 mm)
ax.set_xlim(-15, 415)
ax.set_ylim(-10, 290)
ax.set_aspect('equal')
ax.axis('off')

# Standard Border (GB/T 14665)
ax.plot([0, 400, 400, 0, 0], [0, 0, 275, 275, 0], 'k-', lw=1.8)
ax.plot([20, 395, 395, 20, 20], [5, 5, 270, 270, 5], 'k-', lw=1.0)

# Title Block (Bottom Right: 235, 5, 160, 50)
bx, by, bw, bh = 235, 5, 160, 50
ax.add_patch(patches.Rectangle((bx, by), bw, bh, fill=False, edgecolor='black', lw=1.4))
for y_off in [12, 24, 37]:
    ax.plot([bx, bx + bw], [by + y_off, by + y_off], 'k-', lw=0.8)
for x_off in [40, 100, 130]:
    ax.plot([bx + x_off, bx + x_off], [by, by + bh], 'k-', lw=0.8)

ax.text(bx + 20, by + 43, '零件名称', ha='center', va='center', fontsize=9, weight='bold')
ax.text(bx + 70, by + 43, '高压涡轮工作叶片', ha='center', va='center', fontsize=11, weight='bold', color='navy')
ax.text(bx + 115, by + 43, '阶段标记', ha='center', va='center', fontsize=8)
ax.text(bx + 145, by + 43, '量产 (S)', ha='center', va='center', fontsize=9, weight='bold')

ax.text(bx + 20, by + 30, '零件图号', ha='center', va='center', fontsize=9, weight='bold')
ax.text(bx + 70, by + 30, 'AE-HPT-BLD-001', ha='center', va='center', fontsize=10, weight='bold', color='navy')
ax.text(bx + 115, by + 30, '比例', ha='center', va='center', fontsize=8)
ax.text(bx + 145, by + 30, '1 : 1', ha='center', va='center', fontsize=9, weight='bold')

ax.text(bx + 20, by + 18, '材料牌号', ha='center', va='center', fontsize=9, weight='bold')
ax.text(bx + 70, by + 18, 'DD6 单晶高温合金', ha='center', va='center', fontsize=9, color='navy')
ax.text(bx + 115, by + 18, '重量', ha='center', va='center', fontsize=8)
ax.text(bx + 145, by + 18, '0.342 kg', ha='center', va='center', fontsize=9)

ax.text(bx + 20, by + 6, '设计标准', ha='center', va='center', fontsize=8)
ax.text(bx + 70, by + 6, 'GJB 2896 / HB 6153', ha='center', va='center', fontsize=8)
ax.text(bx + 115, by + 6, '张数', ha='center', va='center', fontsize=8)
ax.text(bx + 145, by + 6, '第 1 张 共 1 张', ha='center', va='center', fontsize=8)

# -------------------------------------------------------------
# Geometry Definitions
# -------------------------------------------------------------

# Fir-tree 2D Profile (Side view projection of 3-tier fir tree)
def get_firtree_pts(cx, cy, scale=1.0):
    # cx, cy is the top-center of the fir-tree root (where it meets the platform)
    # returns left half and right half points
    pts = []
    # y goes down from 0 to -30
    profile_right = [
        (0, -30), (7, -30), (8, -29),  # base flat
        (9, -26), (12, -22), (10, -20), # tooth 1 (bottom)
        (7, -19), (11, -15), (13.5, -13), (11.5, -11), # tooth 2 (mid)
        (8, -10), (12.5, -6), (15, -4), (13, -2), # tooth 3 (top)
        (9, -1), (9, 0) # neck to platform
    ]
    # mirror to left
    left_side = [(-x, y) for (x, y) in reversed(profile_right)]
    full_poly = left_side + profile_right
    return [(cx + x * scale, cy + y * scale) for (x, y) in full_poly]

# Airfoil 2D Section (NACA/Gas Turbine cambered airfoil)
def get_airfoil_curve(chord, max_thick_ratio, camber, stagger_deg, offset_x, offset_y):
    # Generates a cambered gas turbine airfoil curve
    n = 60
    beta = np.linspace(0, np.pi, n)
    x = 0.5 * (1 - np.cos(beta)) # cluster near LE/TE
    
    # Camber line: parabolic
    yc = camber * x * (1 - x)
    dyc_dx = camber * (1 - 2 * x)
    theta = np.arctan(dyc_dx)
    
    # Thickness distribution
    yt = 5 * max_thick_ratio * (0.2969 * np.sqrt(np.maximum(x, 1e-6)) - 0.1260 * x - 0.3516 * (x**2) + 0.2843 * (x**3) - 0.1015 * (x**4))
    
    # Upper (Suction) and Lower (Pressure) surfaces
    xu = x - yt * np.sin(theta)
    yu = yc + yt * np.cos(theta)
    xl = x + yt * np.sin(theta)
    yl = yc - yt * np.cos(theta)
    
    # Combine loop: LE to TE along suction, then back along pressure
    x_coords = np.concatenate([xu, xl[::-1]]) * chord
    y_coords = np.concatenate([yu, yl[::-1]]) * chord
    
    # Rotate by stagger angle
    rad = np.radians(stagger_deg)
    cos_r, sin_r = np.cos(rad), np.sin(rad)
    xr = cos_r * x_coords - sin_r * y_coords + offset_x
    yr = sin_r * x_coords + cos_r * y_coords + offset_y
    return xr, yr

# =============================================================
# View 1: 主视图 (Front View) - [cx=95, cy=55]
# Shows: Fir-tree root, Platform, 3D Twisted Blade Body, Shroud
# =============================================================
f_cx, f_cy = 95, 65

# 1.1 Fir-tree root (Front Projection)
# In front view, fir-tree root is seen from the front (axial view: trapezoidal root stem)
ax.plot([f_cx - 9, f_cx - 15, f_cx + 15, f_cx + 9, f_cx - 9], 
        [f_cy, f_cy - 28, f_cy - 28, f_cy, f_cy], 'k-', lw=1.4)
ax.plot([f_cx - 12, f_cx + 12], [f_cy - 10, f_cy - 10], 'k--', lw=0.6)
ax.plot([f_cx - 13.5, f_cx + 13.5], [f_cy - 19, f_cy - 19], 'k--', lw=0.6)

# Centerline
ax.plot([f_cx, f_cx], [f_cy - 35, f_cy + 135], 'r-.', lw=0.7)

# 1.2 Platform (缘板)
p_w, p_h = 36, 6
ax.plot([f_cx - p_w/2, f_cx + p_w/2, f_cx + p_w/2, f_cx - p_w/2, f_cx - p_w/2],
        [f_cy, f_cy, f_cy + p_h, f_cy + p_h, f_cy], 'k-', lw=1.5)
# Transition fillets
ax.plot([f_cx - p_w/2 - 2, f_cx - p_w/2], [f_cy + p_h/2, f_cy + p_h/2], 'k-', lw=0.8)

# 1.3 Blade Body (扭转气动叶身前视图轮廓)
# Root to Tip span = 85 mm
# Smooth contour curves for suction and pressure edge projection
h_root = f_cy + p_h
h_tip = h_root + 85

# Suction (leading) edge curve
z_span = np.linspace(h_root, h_tip, 50)
t = (z_span - h_root) / 85.0
le_x = f_cx - 14 + 10 * t - 3 * (t**2)
te_x = f_cx + 12 - 6 * t - 2 * (t**2)

ax.plot(le_x, z_span, 'k-', lw=1.6)
ax.plot(te_x, z_span, 'k-', lw=1.6)
# Blade tip (开式叶顶/平顶带倒角)
ax.plot([le_x[-1], te_x[-1]], [h_tip, h_tip], 'k-', lw=1.5)
# Blade root fillet with platform
ax.plot([le_x[0] - 2, le_x[0]], [h_root, h_root + 2], 'k-', lw=1.0)
ax.plot([te_x[0], te_x[0] + 2], [h_root + 2, h_root], 'k-', lw=1.0)

# Section lines A-A, B-B, C-C
y_aa = h_root + 5
y_bb = h_root + 42.5
y_cc = h_root + 80
for y_sec, lbl in [(y_aa, 'A'), (y_bb, 'B'), (y_cc, 'C')]:
    ax.plot([f_cx - 24, f_cx + 22], [y_sec, y_sec], 'b--', lw=0.8)
    ax.arrow(f_cx - 24, y_sec, 0, 4, head_width=2, head_length=2.5, fc='b', ec='b')
    ax.arrow(f_cx + 22, y_sec, 0, 4, head_width=2, head_length=2.5, fc='b', ec='b')
    ax.text(f_cx - 27, y_sec + 2, lbl, fontsize=10, weight='bold', color='blue')
    ax.text(f_cx + 25, y_sec + 2, lbl, fontsize=10, weight='bold', color='blue')

# Cooling holes (气膜冷却微孔示意点)
for zz in np.linspace(h_root + 15, h_tip - 10, 8):
    ax.plot([f_cx - 10 + (zz - h_root)*0.08], [zz], 'ko', markersize=2.0)
    ax.plot([f_cx - 6 + (zz - h_root)*0.07], [zz - 2], 'ko', markersize=2.0)

ax.text(f_cx, f_cy - 45, '主视图 (Front View)\n比例 1:1', ha='center', va='top', fontsize=11, weight='bold')

# =============================================================
# View 2: 左视图 / 榫头齿廓详图 (Side View & Fir-tree Detail) - [cx=195, cy=65]
# Demonstrates the authentic 3-tier Fir-Tree serrations
# =============================================================
s_cx, s_cy = 195, 65

# Centerline
ax.plot([s_cx, s_cx], [s_cy - 35, s_cy + 135], 'r-.', lw=0.7)

# Side view fir-tree geometry
firtree_poly = get_firtree_pts(s_cx, s_cy, scale=1.0)
fx, fy = zip(*firtree_poly)
ax.plot(fx, fy, 'k-', lw=1.6)

# Side view platform
ax.plot([s_cx - 15, s_cx + 15, s_cx + 15, s_cx - 15, s_cx - 15],
        [s_cy, s_cy, s_cy + p_h, s_cy + p_h, s_cy], 'k-', lw=1.5)

# Side view blade profile (showing lean and camber)
s_le_x = s_cx - 8 + 6 * t
s_te_x = s_cx + 9 + 4 * t
ax.plot(s_le_x, z_span, 'k-', lw=1.5)
ax.plot(s_te_x, z_span, 'k-', lw=1.5)
ax.plot([s_le_x[-1], s_te_x[-1]], [h_tip, h_tip], 'k-', lw=1.5)

# Fir-tree Detailed Dimension Callouts on Side View
# 1. 榫头总高 30 mm
ax.annotate('', xy=(s_cx + 25, s_cy), xytext=(s_cx + 25, s_cy - 30),
            arrowprops=dict(arrowstyle='<->', color='black', lw=0.9))
ax.plot([s_cx + 10, s_cx + 28], [s_cy, s_cy], 'k:', lw=0.6)
ax.plot([s_cx + 8, s_cx + 28], [s_cy - 30, s_cy - 30], 'k:', lw=0.6)
ax.text(s_cx + 30, s_cy - 15, '30 ±0.01', va='center', fontsize=9, weight='bold')

# 2. 齿距 Pitch = 7.5 mm
ax.annotate('', xy=(s_cx - 24, s_cy - 4), xytext=(s_cx - 24, s_cy - 11.5),
            arrowprops=dict(arrowstyle='<->', color='black', lw=0.8))
ax.text(s_cx - 32, s_cy - 7.5, 'P=7.5', va='center', fontsize=8)

# 3. 接触角 35°
ax.plot([s_cx + 11.5, s_cx + 20], [s_cy - 11, s_cy - 16], 'r-', lw=0.8)
ax.text(s_cx + 22, s_cy - 14, '35°承压面', fontsize=8, color='crimson', weight='bold')

# 4. 齿顶圆弧 R1.2 与 齿底 r0.8
ax.annotate('R1.2', xy=(s_cx + 15, s_cy - 4), xytext=(s_cx + 24, s_cy - 2),
            arrowprops=dict(arrowstyle='->', color='black', lw=0.7), fontsize=8)
ax.annotate('r0.8 (过渡圆角)', xy=(s_cx + 8, s_cy - 10), xytext=(s_cx + 18, s_cy - 8),
            arrowprops=dict(arrowstyle='->', color='black', lw=0.7), fontsize=8)

ax.text(s_cx, s_cy - 45, '左视图 (Left View)\n枞树型榫头结构特写', ha='center', va='top', fontsize=11, weight='bold')

# =============================================================
# View 3: A-A, B-B, C-C 气动翼型截面型线图 (Section Views)
# [A-A: 根部, B-B: 中部, C-C: 叶顶] - [x=290 ~ 360, y=140 ~ 240]
# =============================================================

# 3.1 C-C 截面 (叶顶 Z=80 mm) - 弦长较短、安装角平缓
c_chord, c_thick, c_camber, c_stagger = 24, 0.10, 0.18, 25
xc, yc = get_airfoil_curve(c_chord, c_thick, c_camber, c_stagger, 300, 220)
ax.plot(xc, yc, 'b-', lw=1.5)
ax.fill(xc, yc, color='lightblue', alpha=0.35)
ax.plot([300 - 4, 300 + 26], [220, 220], 'k-.', lw=0.6)
ax.text(300, 238, 'C-C 截面 (叶顶 Z=80 mm)', fontsize=9, weight='bold', color='navy')
ax.text(300, 232, f'弦长 b={c_chord}mm | 安装角 β={c_stagger}° | 最大厚比 10%', fontsize=8)

# 3.2 B-B 截面 (中部 Z=42.5 mm)
b_chord, b_thick, b_camber, b_stagger = 28, 0.14, 0.22, 36
xb, yb = get_airfoil_curve(b_chord, b_thick, b_camber, b_stagger, 300, 160)
ax.plot(xb, yb, 'b-', lw=1.5)
ax.fill(xb, yb, color='lightblue', alpha=0.35)
ax.plot([300 - 4, 300 + 28], [160, 160], 'k-.', lw=0.6)
ax.text(300, 178, 'B-B 截面 (叶中 Z=42.5 mm)', fontsize=9, weight='bold', color='navy')
ax.text(300, 172, f'弦长 b={b_chord}mm | 安装角 β={b_stagger}° | 最大厚比 14%', fontsize=8)

# 3.3 A-A 截面 (根部 Z=5 mm) - 弦长最长、弯度大、安装角陡峭
a_chord, a_thick, a_camber, a_stagger = 32, 0.18, 0.28, 48
xa, ya = get_airfoil_curve(a_chord, a_thick, a_camber, a_stagger, 300, 100)
ax.plot(xa, ya, 'b-', lw=1.5)
ax.fill(xa, ya, color='lightblue', alpha=0.35)
ax.plot([300 - 4, 300 + 30], [100, 100], 'k-.', lw=0.6)
ax.text(300, 118, 'A-A 截面 (叶根 Z=5 mm)', fontsize=9, weight='bold', color='navy')
ax.text(300, 112, f'弦长 b={a_chord}mm | 安装角 β={a_stagger}° | 最大厚比 18%', fontsize=8)

# Aerodynamic twist annotation
ax.annotate('总气动扭转角 Δβ = 23°\n(根部 48° ➔ 顶部 25°)', xy=(350, 195), xytext=(350, 195),
            bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.25),
            fontsize=8.5, weight='bold')

# =============================================================
# Technical Requirements & GD&T (技术要求与制造规范)
# Top-Left Box: [x=25, y=190, w=170, h=75]
# =============================================================
req_x, req_y = 25, 205
ax.text(req_x, req_y + 55, '【技术要求与制造标准】(TECHNICAL SPECIFICATIONS)', fontsize=10, weight='bold', color='darkred')
specs = [
    '1. 材质与冶金：DD6 第二代镍基单晶高温合金，按 GJB 2896 航空规范执行。',
    '2. 热处理制度：1290℃×1h+1300℃×2h+1315℃×4h/AC + 1120℃×4h/AC + 870℃×32h/AC。',
    '3. 几何公差 (GD&T)：',
    '   - 叶身自由曲面型面轮廓度: ⌒ 0.03 mm (相对于基准 A-B-C，全型面激光扫描比对)。',
    '   - 枞树型榫头接触齿面轮廓度与对称度: ⌒ 0.008 mm，各齿承载接触斑点率 ≥ 85%。',
    '   - 叶片积叠轴同轴度与垂直度: ⊥ 0.015 mm。',
    '4. 表面完整性：',
    '   - 枞树榫头齿面粗糙度 Ra ≤ 0.2 μm (缓进给成形磨削/CNC线切割)。',
    '   - 叶身气动曲面粗糙度 Ra ≤ 0.4 μm (五轴精密铣削 + 自适应机器人砂带抛光)。',
    '5. 无损检测 (NDT)：100% 射线探伤 (RT) 与高灵敏度荧光渗透探伤 (FPI)，不允许任何裂纹与疏松。',
    '6. 气膜冷却孔：飞秒激光打孔，孔径 φ0.35±0.03 mm，倾角 30°，重铸层厚度 ≤ 5 μm。'
]

for idx, sp in enumerate(specs):
    ax.text(req_x, req_y + 45 - idx * 7.5, sp, fontsize=7.6, color='black')

# Overall Dimensions on Front View
# Total Height Callout: 30(root) + 6(plat) + 85(blade) = 121 mm
ax.annotate('', xy=(f_cx - 45, f_cy + 91), xytext=(f_cx - 45, f_cy - 30),
            arrowprops=dict(arrowstyle='<->', color='black', lw=1.0))
ax.plot([f_cx - 48, f_cx - 15], [f_cy - 30, f_cy - 30], 'k:', lw=0.6)
ax.plot([f_cx - 48, f_cx - 5], [f_cy + 91, f_cy + 91], 'k:', lw=0.6)
ax.text(f_cx - 52, f_cy + 30, '总高 121 ±0.05', va='center', ha='right', rotation=90, fontsize=10, weight='bold')

# Blade span callout: 85 mm
ax.annotate('', xy=(f_cx - 30, f_cy + 91), xytext=(f_cx - 30, f_cy + 6),
            arrowprops=dict(arrowstyle='<->', color='black', lw=0.8))
ax.plot([f_cx - 33, f_cx - p_w/2], [f_cy + 6, f_cy + 6], 'k:', lw=0.6)
ax.text(f_cx - 35, f_cy + 48, '叶身高度 85', va='center', ha='right', rotation=90, fontsize=9)

plt.tight_layout()
fig.savefig(png_path, dpi=240, bbox_inches='tight')
plt.close(fig)
print(f"Engineering blueprint image generated: {png_path}")

# -------------------------------------------------------------
# 2. Standard DXF Generation via ezdxf (GB Layer Discipline)
# -------------------------------------------------------------
doc = ezdxf.new('R2010')
msp = doc.modelspace()

# Setup standard layers
layers = [
    ('OUTLINE', 7, 'CONTINUOUS'),   # White/Black solid
    ('DIM', 1, 'CONTINUOUS'),       # Red
    ('CENTER', 1, 'CENTER'),        # Red centerline
    ('SECTION', 4, 'CONTINUOUS'),   # Cyan
    ('TITLE_BLOCK', 3, 'CONTINUOUS')# Green
]
for name, color, ltype in layers:
    doc.layers.add(name=name, color=color, linetype=ltype)

# Draw Title block in DXF
msp.add_lwpolyline([(bx, by), (bx + bw, by), (bx + bw, by + bh), (bx, by + bh), (bx, by)], dxfattribs={'layer': 'TITLE_BLOCK'})
msp.add_text('AERO ENGINE HPT TURBINE ROTOR BLADE', dxfattribs={'layer': 'TITLE_BLOCK', 'height': 4.0}).set_placement((bx + 10, by + 40))
msp.add_text('PART NO: AE-HPT-BLD-001 | MATERIAL: DD6 SINGLE CRYSTAL', dxfattribs={'layer': 'TITLE_BLOCK', 'height': 3.0}).set_placement((bx + 10, by + 28))

# Draw Fir-tree profile in DXF
msp.add_lwpolyline(firtree_poly, close=True, dxfattribs={'layer': 'OUTLINE'})

# Draw Airfoil Sections in DXF
msp.add_lwpolyline(list(zip(xa, ya)), close=True, dxfattribs={'layer': 'SECTION'})
msp.add_lwpolyline(list(zip(xb, yb)), close=True, dxfattribs={'layer': 'SECTION'})
msp.add_lwpolyline(list(zip(xc, yc)), close=True, dxfattribs={'layer': 'SECTION'})

doc.saveas(dxf_path)
print(f"Engineering blueprint DXF generated: {dxf_path}")
