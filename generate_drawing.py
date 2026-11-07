# -*- coding: utf-8 -*-
import ezdxf
from ezdxf.enums import TextEntityAlignment
import math
import os
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

def create_refined_drawing(output_dxf_path, output_png_path=None):
    doc = ezdxf.new('R2018', setup=True)
    msp = doc.modelspace()

    # Configure Text Styles for Chinese
    doc.styles.new('CHINESE', dxfattribs={'font': 'msyh.ttc'})
    doc.styles.new('DIM_STYLE', dxfattribs={'font': 'msyh.ttc'})

    # 1. Setup Layers
    doc.layers.new('0_VISIBLE', dxfattribs={'color': 7, 'lineweight': 35})
    doc.layers.new('CENTER', dxfattribs={'color': 1, 'linetype': 'CENTER', 'lineweight': 18})
    doc.layers.new('HIDDEN', dxfattribs={'color': 2, 'linetype': 'DASHED', 'lineweight': 18})
    doc.layers.new('DIM', dxfattribs={'color': 3, 'lineweight': 18})
    doc.layers.new('BORDER', dxfattribs={'color': 7, 'lineweight': 50})
    doc.layers.new('TITLE', dxfattribs={'color': 4, 'lineweight': 25})

    def line(p1, p2, layer='0_VISIBLE'):
        return msp.add_line(p1, p2, dxfattribs={'layer': layer})

    def circle(center, radius, layer='0_VISIBLE'):
        return msp.add_circle(center, radius, dxfattribs={'layer': layer})

    def arc(center, radius, start_angle, end_angle, layer='0_VISIBLE'):
        return msp.add_arc(center, radius, start_angle, end_angle, dxfattribs={'layer': layer})

    def add_arrow(p_tip, p_base, size=0.75, layer='DIM'):
        dx = p_tip[0] - p_base[0]
        dy = p_tip[1] - p_base[1]
        length = math.hypot(dx, dy)
        if length < 1e-6:
            return
        ux = dx / length
        uy = dy / length
        vx = -uy
        vy = ux
        w = size * 0.22
        p1 = (p_tip[0] - ux * size + vx * w, p_tip[1] - uy * size + vy * w)
        p2 = (p_tip[0] - ux * size - vx * w, p_tip[1] - uy * size - vy * w)
        msp.add_solid([p_tip, p1, p2], dxfattribs={'layer': layer, 'color': 3})

    def dim_linear_h(x1, x2, y, text, ext_y1, text_offset=0.75, layer='DIM', ext_offset=0.5):
        y_dir = 1.0 if y >= ext_y1 else -1.0
        line((x1, ext_y1), (x1, y + y_dir * ext_offset), layer=layer)
        line((x2, ext_y1), (x2, y + y_dir * ext_offset), layer=layer)
        line((x1, y), (x2, y), layer=layer)
        add_arrow((x1, y), (x1 + 1.0, y), layer=layer)
        add_arrow((x2, y), (x2 - 1.0, y), layer=layer)
        tx = (x1 + x2) / 2.0
        ty = y + text_offset
        msp.add_text(text, dxfattribs={
            'layer': layer, 'height': 1.0, 'color': 7, 'style': 'DIM_STYLE'
        }).set_placement((tx, ty), align=TextEntityAlignment.MIDDLE_CENTER)

    def dim_linear_v(y1, y2, x, text, ext_x1, text_offset=0.75, layer='DIM', ext_offset=0.5):
        x_dir = 1.0 if x >= ext_x1 else -1.0
        line((ext_x1, y1), (x + x_dir * ext_offset, y1), layer=layer)
        line((ext_x1, y2), (x + x_dir * ext_offset, y2), layer=layer)
        line((x, y1), (x, y2), layer=layer)
        add_arrow((x, y1), (x, y1 + 1.0), layer=layer)
        add_arrow((x, y2), (x, y2 - 1.0), layer=layer)
        tx = x - text_offset
        ty = (y1 + y2) / 2.0
        t = msp.add_text(text, dxfattribs={
            'layer': layer, 'height': 1.0, 'color': 7, 'style': 'DIM_STYLE'
        })
        t.set_placement((tx, ty), align=TextEntityAlignment.MIDDLE_CENTER)
        t.dxf.rotation = 90

    # -------------------------------------------------------------
    # 2. DRAWING BORDER & TITLE BLOCK
    # -------------------------------------------------------------
    border_x0, border_y0 = 4.0, 4.0
    border_x1, border_y1 = 92.0, 72.0
    line((border_x0, border_y0), (border_x1, border_y0), layer='BORDER')
    line((border_x1, border_y0), (border_x1, border_y1), layer='BORDER')
    line((border_x1, border_y1), (border_x0, border_y1), layer='BORDER')
    line((border_x0, border_y1), (border_x0, border_y0), layer='BORDER')

    # Title block: bottom right
    line((48.0, 4.0), (48.0, 8.5), layer='BORDER')
    line((48.0, 8.5), (92.0, 8.5), layer='BORDER')
    line((68.0, 4.0), (68.0, 8.5), layer='BORDER')

    msp.add_text('致用电脑学校', dxfattribs={
        'layer': 'TITLE', 'height': 2.2, 'color': 7, 'style': 'CHINESE'
    }).set_placement((58.0, 6.25), align=TextEntityAlignment.MIDDLE_CENTER)

    msp.add_text('刘国锋 教案', dxfattribs={
        'layer': 'TITLE', 'height': 2.2, 'color': 7, 'style': 'CHINESE'
    }).set_placement((80.0, 6.25), align=TextEntityAlignment.MIDDLE_CENTER)

    # -------------------------------------------------------------
    # 3. VIEW 1: 主视图 (FRONT VIEW) - Top-Left
    # -------------------------------------------------------------
    X_F = 26.0
    Y_base_F = 40.0

    # Base profile with bottom groove
    line((15.9, 40.0), (21.8, 40.0), layer='0_VISIBLE')
    line((21.8, 40.0), (21.8, 41.3), layer='0_VISIBLE')
    line((21.8, 41.3), (30.2, 41.3), layer='0_VISIBLE')
    line((30.2, 41.3), (30.2, 40.0), layer='0_VISIBLE')
    line((30.2, 40.0), (36.1, 40.0), layer='0_VISIBLE')

    line((15.9, 40.0), (15.9, 43.4), layer='0_VISIBLE')
    line((36.1, 40.0), (36.1, 43.4), layer='0_VISIBLE')

    line((15.9, 43.4), (17.95, 43.4), layer='0_VISIBLE')
    line((34.05, 43.4), (36.1, 43.4), layer='0_VISIBLE')

    # Mounting holes dashed lines & centerlines
    line((17.6, 40.0), (17.6, 43.4), layer='HIDDEN')
    line((21.0, 40.0), (21.0, 43.4), layer='HIDDEN')
    line((19.3, 39.0), (19.3, 44.4), layer='CENTER')

    line((31.0, 40.0), (31.0, 43.4), layer='HIDDEN')
    line((34.4, 40.0), (34.4, 43.4), layer='HIDDEN')
    line((32.7, 39.0), (32.7, 44.4), layer='CENTER')

    # Cylinder & side ribs
    circle((26.0, 53.4), 2.85, layer='0_VISIBLE')
    arc((26.0, 53.4), 5.55, 13.22, 166.78, layer='0_VISIBLE')
    line((17.95, 43.4), (20.597, 54.669), layer='0_VISIBLE')
    line((34.05, 43.4), (31.403, 54.669), layer='0_VISIBLE')

    # Central rib: width 1.0
    line((25.5, 43.4), (25.5, 47.85), layer='0_VISIBLE')
    line((26.5, 43.4), (26.5, 47.85), layer='0_VISIBLE')
    line((25.5, 43.4), (26.5, 43.4), layer='0_VISIBLE')

    # Centerlines
    line((19.0, 53.4), (33.0, 53.4), layer='CENTER')
    line((26.0, 38.5), (26.0, 60.0), layer='CENTER')

    # Dimensions
    dim_linear_v(40.0, 53.4, 11.5, '13,4', ext_x1=15.9, text_offset=0.8)
    line((15.9, 53.4), (26.0, 53.4), layer='CENTER')

    dim_linear_v(40.0, 43.4, 13.8, '3,4', ext_x1=15.9, text_offset=0.8)

    dim_linear_h(21.8, 30.2, 37.0, '8,4', ext_y1=40.0, text_offset=0.8)

    # Groove height 1,3
    line((30.2, 41.3), (33.5, 41.3), layer='DIM')
    line((30.2, 40.0), (33.5, 40.0), layer='DIM')
    line((32.5, 38.5), (32.5, 42.5), layer='DIM')
    add_arrow((32.5, 41.3), (32.5, 42.0), layer='DIM')
    add_arrow((32.5, 40.0), (32.5, 39.0), layer='DIM')
    t13 = msp.add_text('1,3', dxfattribs={'layer': 'DIM', 'height': 1.0, 'color': 7, 'style': 'DIM_STYLE'})
    t13.set_placement((32.5, 37.5), align=TextEntityAlignment.MIDDLE_CENTER)
    t13.dxf.rotation = 90

    # Rib width 1
    line((23.0, 45.5), (28.0, 45.5), layer='DIM')
    add_arrow((25.5, 45.5), (24.0, 45.5), layer='DIM')
    add_arrow((26.5, 45.5), (28.0, 45.5), layer='DIM')
    msp.add_text('1', dxfattribs={'layer': 'DIM', 'height': 1.0, 'color': 7, 'style': 'DIM_STYLE'}).set_placement((22.5, 45.5), align=TextEntityAlignment.MIDDLE_RIGHT)

    # Diameters
    ang57 = math.radians(40)
    p_bore1 = (26.0 - 2.85 * math.cos(ang57), 53.4 - 2.85 * math.sin(ang57))
    p_bore2 = (26.0 + 2.85 * math.cos(ang57), 53.4 + 2.85 * math.sin(ang57))
    line(p_bore1, p_bore2, layer='DIM')
    add_arrow(p_bore1, (26.0, 53.4), layer='DIM')
    add_arrow(p_bore2, (26.0, 53.4), layer='DIM')
    p_text57 = (26.0 + 5.0 * math.cos(ang57), 53.4 + 5.0 * math.sin(ang57))
    line(p_bore2, p_text57, layer='DIM')
    t_dia57 = msp.add_text('%%c5,7', dxfattribs={'layer': 'DIM', 'height': 1.0, 'color': 7, 'style': 'DIM_STYLE'})
    t_dia57.set_placement((p_text57[0] + 0.3, p_text57[1] + 0.3), align=TextEntityAlignment.BOTTOM_LEFT)
    t_dia57.dxf.rotation = 40

    ang111 = math.radians(-35)
    p_out1 = (26.0 - 5.55 * math.cos(ang111), 53.4 - 5.55 * math.sin(ang111))
    p_out2 = (26.0 + 5.55 * math.cos(ang111), 53.4 + 5.55 * math.sin(ang111))
    line(p_out1, p_out2, layer='DIM')
    add_arrow(p_out1, (26.0, 53.4), layer='DIM')
    add_arrow(p_out2, (26.0, 53.4), layer='DIM')
    p_text111 = (p_out2[0] + 2.5 * math.cos(ang111), p_out2[1] + 2.5 * math.sin(ang111))
    line(p_out2, p_text111, layer='DIM')
    t_dia111 = msp.add_text('%%c11,1', dxfattribs={'layer': 'DIM', 'height': 1.0, 'color': 7, 'style': 'DIM_STYLE'})
    t_dia111.set_placement((p_text111[0] + 0.3, p_text111[1] + 0.3), align=TextEntityAlignment.BOTTOM_LEFT)
    t_dia111.dxf.rotation = -35

    # -------------------------------------------------------------
    # 4. VIEW 2: 左视图 (LEFT / SIDE VIEW) - Top-Right
    # -------------------------------------------------------------
    X_back_L = 52.0
    line((52.0, 40.0), (65.4, 40.0), layer='0_VISIBLE')
    line((65.4, 40.0), (65.4, 43.4), layer='0_VISIBLE')
    line((65.4, 43.4), (58.7, 43.4), layer='0_VISIBLE')
    line((52.0, 40.0), (52.0, 58.95), layer='0_VISIBLE')

    line((52.0, 41.3), (65.4, 41.3), layer='HIDDEN')

    line((60.3, 40.0), (60.3, 43.4), layer='HIDDEN')
    line((63.7, 40.0), (63.7, 43.4), layer='HIDDEN')
    line((62.0, 39.0), (62.0, 44.4), layer='CENTER')

    line((52.0, 58.95), (60.4, 58.95), layer='0_VISIBLE')
    line((60.4, 58.95), (60.4, 47.85), layer='0_VISIBLE')
    line((60.4, 47.85), (55.4, 47.85), layer='0_VISIBLE')

    line((52.0, 56.25), (60.4, 56.25), layer='HIDDEN')
    line((52.0, 50.55), (60.4, 50.55), layer='HIDDEN')
    line((51.0, 53.4), (61.5, 53.4), layer='CENTER')

    line((55.4, 43.4), (55.4, 47.85), layer='0_VISIBLE')
    line((55.4, 47.85), (55.4, 54.669), layer='0_VISIBLE')
    line((52.0, 54.669), (55.4, 54.669), layer='0_VISIBLE')

    line((55.4, 47.85), (57.1, 47.85), layer='0_VISIBLE')
    line((57.1, 47.85), (57.1, 46.15), layer='0_VISIBLE')
    line((57.1, 46.15), (58.7, 43.4), layer='0_VISIBLE')

    # Side View Dimensions
    dim_linear_h(52.0, 60.4, 61.5, '8,4', ext_y1=58.95, text_offset=0.8)

    # 1,7 vertical
    line((57.1, 46.15), (64.5, 46.15), layer='DIM')
    line((60.4, 47.85), (64.5, 47.85), layer='DIM')
    line((63.5, 45.0), (63.5, 49.0), layer='DIM')
    add_arrow((63.5, 47.85), (63.5, 48.85), layer='DIM')
    add_arrow((63.5, 46.15), (63.5, 45.15), layer='DIM')
    t_v17 = msp.add_text('1,7', dxfattribs={'layer': 'DIM', 'height': 1.0, 'color': 7, 'style': 'DIM_STYLE'})
    t_v17.set_placement((64.5, 47.0), align=TextEntityAlignment.MIDDLE_LEFT)

    # 1,7 horizontal
    line((55.4, 46.0), (55.4, 48.0), layer='DIM')
    line((57.1, 45.0), (57.1, 47.0), layer='DIM')
    line((53.5, 46.5), (59.0, 46.5), layer='DIM')
    add_arrow((55.4, 46.5), (54.0, 46.5), layer='DIM')
    add_arrow((57.1, 46.5), (58.5, 46.5), layer='DIM')
    msp.add_text('1,7', dxfattribs={'layer': 'DIM', 'height': 1.0, 'color': 7, 'style': 'DIM_STYLE'}).set_placement((59.5, 46.5), align=TextEntityAlignment.MIDDLE_LEFT)

    # 3,3 horizontal
    line((58.7, 42.0), (58.7, 44.5), layer='DIM')
    line((54.0, 44.2), (61.0, 44.2), layer='DIM')
    add_arrow((55.4, 44.2), (54.0, 44.2), layer='DIM')
    add_arrow((58.7, 44.2), (60.0, 44.2), layer='DIM')
    msp.add_text('3,3', dxfattribs={'layer': 'DIM', 'height': 1.0, 'color': 7, 'style': 'DIM_STYLE'}).set_placement((61.5, 44.2), align=TextEntityAlignment.MIDDLE_LEFT)

    # -------------------------------------------------------------
    # 5. VIEW 3: 俯视图 (TOP VIEW) - Bottom-Left
    # -------------------------------------------------------------
    line((15.9, 27.0), (36.1, 27.0), layer='0_VISIBLE')
    line((15.9, 27.0), (15.9, 17.0), layer='0_VISIBLE')
    line((36.1, 27.0), (36.1, 17.0), layer='0_VISIBLE')
    line((19.3, 13.6), (32.7, 13.6), layer='0_VISIBLE')

    arc((19.3, 17.0), 3.4, 180, 270, layer='0_VISIBLE')
    arc((32.7, 17.0), 3.4, 270, 360, layer='0_VISIBLE')

    circle((19.3, 17.0), 1.7, layer='0_VISIBLE')
    circle((32.7, 17.0), 1.7, layer='0_VISIBLE')

    line((16.5, 17.0), (22.1, 17.0), layer='CENTER')
    line((19.3, 14.2), (19.3, 19.8), layer='CENTER')
    line((29.9, 17.0), (35.5, 17.0), layer='CENTER')
    line((32.7, 14.2), (32.7, 19.8), layer='CENTER')

    line((20.45, 27.0), (20.45, 18.6), layer='0_VISIBLE')
    line((20.45, 18.6), (31.55, 18.6), layer='0_VISIBLE')
    line((31.55, 27.0), (31.55, 18.6), layer='0_VISIBLE')

    line((23.15, 27.0), (23.15, 18.6), layer='HIDDEN')
    line((28.85, 27.0), (28.85, 18.6), layer='HIDDEN')
    line((26.0, 28.0), (26.0, 12.5), layer='CENTER')

    line((17.95, 27.0), (17.95, 23.6), layer='0_VISIBLE')
    line((17.95, 23.6), (20.45, 23.6), layer='0_VISIBLE')
    line((34.05, 27.0), (34.05, 23.6), layer='0_VISIBLE')
    line((31.55, 23.6), (34.05, 23.6), layer='0_VISIBLE')

    line((25.5, 23.6), (25.5, 18.6), layer='HIDDEN')
    line((26.5, 23.6), (26.5, 18.6), layer='HIDDEN')
    line((25.5, 21.9), (26.5, 21.9), layer='HIDDEN')

    line((21.8, 27.0), (21.8, 13.6), layer='HIDDEN')
    line((30.2, 27.0), (30.2, 13.6), layer='HIDDEN')

    # Top View Dimensions
    dim_linear_h(15.9, 36.1, 30.5, '20,2', ext_y1=27.0, text_offset=0.8)
    dim_linear_h(17.95, 34.05, 28.5, '16,1', ext_y1=27.0, text_offset=0.8)
    dim_linear_v(13.6, 27.0, 12.0, '13,4', ext_x1=15.9, text_offset=0.8)
    dim_linear_v(23.6, 27.0, 14.0, '3,4', ext_x1=15.9, text_offset=0.8)

    # Φ3,4 Leader
    line((32.7 + 1.2, 17.0 - 1.2), (38.5, 14.8), layer='DIM')
    add_arrow((32.7 + 1.2, 17.0 - 1.2), (38.5, 14.8), layer='DIM')
    line((38.5, 14.8), (42.0, 14.8), layer='DIM')
    msp.add_text('%%c3,4', dxfattribs={'layer': 'DIM', 'height': 1.0, 'color': 7, 'style': 'DIM_STYLE'}).set_placement((42.5, 14.8), align=TextEntityAlignment.MIDDLE_LEFT)

    # R3,4 Leader
    ang_r = math.radians(-55)
    p_fillet = (32.7 + 3.4 * math.cos(ang_r), 17.0 + 3.4 * math.sin(ang_r))
    line((32.7, 17.0), p_fillet, layer='DIM')
    add_arrow(p_fillet, (32.7, 17.0), layer='DIM')
    p_f_elbow = (p_fillet[0] + 2.5, p_fillet[1] - 2.5)
    line(p_fillet, p_f_elbow, layer='DIM')
    line(p_f_elbow, (p_f_elbow[0] + 3.5, p_f_elbow[1]), layer='DIM')
    msp.add_text('R3,4', dxfattribs={'layer': 'DIM', 'height': 1.0, 'color': 7, 'style': 'DIM_STYLE'}).set_placement((p_f_elbow[0] + 4.0, p_f_elbow[1]), align=TextEntityAlignment.MIDDLE_LEFT)

    # -------------------------------------------------------------
    # 6. VIEW 4: 轴测图 (ISOMETRIC 3D VIEW) - Bottom-Right
    # -------------------------------------------------------------
    # Render crisp 3D isometric representation matching iso_view.png
    cx_iso = 69.0
    cy_iso = 22.0
    s = 0.82

    def to_iso(x, y, z):
        # Isometric projection where:
        # Front face normal along -Y (points towards viewer)
        # X axis along +30 deg (down-right / up-right)
        # Y axis along +150 deg (up-left)
        # Z axis along +90 deg (up)
        # In iso_view.png, the part is viewed from front-left-top:
        u = cx_iso + s * (x * math.cos(math.radians(-30)) - y * math.cos(math.radians(30)))
        v = cy_iso + s * (x * math.sin(math.radians(-30)) - y * math.sin(math.radians(30)) + z)
        return (u, v)

    def iline(p1, p2, layer='0_VISIBLE'):
        line(to_iso(*p1), to_iso(*p2), layer=layer)

    # We model the visible edges in 3D:
    # Base is X in [0, 20.2], Y in [0, 13.4], Z in [0, 3.4]
    # Y = 13.4 is back, Y = 0 is front
    # Let's verify: In front view, groove is at X in [5.9, 14.3], Z in [0, 1.3]
    # Front-left corner has fillet at (3.4, 3.4), Front-right at (16.8, 3.4)

    # Base top edges (Z = 3.4):
    iline((3.4, 0, 3.4), (16.8, 0, 3.4)) # Front straight top
    iline((0, 3.4, 3.4), (0, 13.4, 3.4)) # Left straight top
    iline((20.2, 3.4, 3.4), (20.2, 13.4, 3.4)) # Right straight top
    iline((0, 13.4, 3.4), (20.2, 13.4, 3.4)) # Back top edge

    # Fillet arcs top (Z = 3.4):
    for deg in range(180, 270, 10):
        r1, r2 = math.radians(deg), math.radians(deg + 10)
        # Front-left:
        iline((3.4 + 3.4*math.cos(r1), 3.4 + 3.4*math.sin(r1), 3.4),
              (3.4 + 3.4*math.cos(r2), 3.4 + 3.4*math.sin(r2), 3.4))
    for deg in range(270, 360, 10):
        r1, r2 = math.radians(deg), math.radians(deg + 10)
        # Front-right:
        iline((16.8 + 3.4*math.cos(r1), 3.4 + 3.4*math.sin(r1), 3.4),
              (16.8 + 3.4*math.cos(r2), 3.4 + 3.4*math.sin(r2), 3.4))

    # Base vertical corners:
    iline((0, 3.4, 0), (0, 3.4, 3.4))
    iline((0, 13.4, 0), (0, 13.4, 3.4))
    iline((20.2, 3.4, 0), (20.2, 3.4, 3.4))
    iline((20.2, 13.4, 0), (20.2, 13.4, 3.4))
    iline((3.4 - 3.4*math.sin(math.radians(45)), 3.4 - 3.4*math.cos(math.radians(45)), 0),
          (3.4 - 3.4*math.sin(math.radians(45)), 3.4 - 3.4*math.cos(math.radians(45)), 3.4))
    iline((16.8 + 3.4*math.cos(math.radians(45)), 3.4 - 3.4*math.sin(math.radians(45)), 0),
          (16.8 + 3.4*math.cos(math.radians(45)), 3.4 - 3.4*math.sin(math.radians(45)), 3.4))

    # Base bottom visible edges (Z = 0):
    iline((0, 3.4, 0), (0, 13.4, 0)) # Left bottom edge
    # Front bottom with groove:
    iline((3.4, 0, 0), (5.9, 0, 0))
    iline((5.9, 0, 0), (5.9, 0, 1.3))
    iline((5.9, 0, 1.3), (14.3, 0, 1.3))
    iline((14.3, 0, 1.3), (14.3, 0, 0))
    iline((14.3, 0, 0), (16.8, 0, 0))
    # Groove ceiling going along Y:
    iline((5.9, 0, 1.3), (5.9, 13.4, 1.3))
    iline((14.3, 0, 1.3), (14.3, 13.4, 1.3))

    # Bottom fillet arcs:
    for deg in range(180, 270, 10):
        r1, r2 = math.radians(deg), math.radians(deg + 10)
        iline((3.4 + 3.4*math.cos(r1), 3.4 + 3.4*math.sin(r1), 0),
              (3.4 + 3.4*math.cos(r2), 3.4 + 3.4*math.sin(r2), 0))
    for deg in range(270, 360, 10):
        r1, r2 = math.radians(deg), math.radians(deg + 10)
        iline((16.8 + 3.4*math.cos(r1), 3.4 + 3.4*math.sin(r1), 0),
              (16.8 + 3.4*math.cos(r2), 3.4 + 3.4*math.sin(r2), 0))

    # Mounting holes (Z = 3.4):
    for deg in range(0, 360, 15):
        r1, r2 = math.radians(deg), math.radians(deg + 15)
        # Left hole:
        iline((3.4 + 1.7*math.cos(r1), 3.4 + 1.7*math.sin(r1), 3.4),
              (3.4 + 1.7*math.cos(r2), 3.4 + 1.7*math.sin(r2), 3.4))
        # Right hole:
        iline((16.8 + 1.7*math.cos(r1), 3.4 + 1.7*math.sin(r1), 3.4),
              (16.8 + 1.7*math.cos(r2), 3.4 + 1.7*math.sin(r2), 3.4))

    # Cylinder: center (10.1, Y, 13.4)
    # Extends from Y = 13.4 (back) forward to Y = 5.0 (depth 8.4 -> 13.4 - 8.4 = 5.0)
    # Front circular face at Y = 5.0:
    for deg in range(0, 360, 15):
        r1, r2 = math.radians(deg), math.radians(deg + 15)
        # Outer:
        iline((10.1 + 5.55*math.cos(r1), 5.0, 13.4 + 5.55*math.sin(r1)),
              (10.1 + 5.55*math.cos(r2), 5.0, 13.4 + 5.55*math.sin(r2)))
        # Bore:
        iline((10.1 + 2.85*math.cos(r1), 5.0, 13.4 + 2.85*math.sin(r1)),
              (10.1 + 2.85*math.cos(r2), 5.0, 13.4 + 2.85*math.sin(r2)))

    # Cylinder silhouette lines (from Y = 5.0 to Y = 13.4):
    # Top silhouette:
    iline((10.1 + 5.55*math.cos(math.radians(120)), 5.0, 13.4 + 5.55*math.sin(math.radians(120))),
          (10.1 + 5.55*math.cos(math.radians(120)), 13.4, 13.4 + 5.55*math.sin(math.radians(120))))
    # Bottom silhouette:
    iline((10.1 + 5.55*math.cos(math.radians(300)), 5.0, 13.4 + 5.55*math.sin(math.radians(300))),
          (10.1 + 5.55*math.cos(math.radians(300)), 13.4, 13.4 + 5.55*math.sin(math.radians(300))))
    # Back arc of cylinder:
    for deg in range(60, 180, 15):
        r1, r2 = math.radians(deg), math.radians(deg + 15)
        iline((10.1 + 5.55*math.cos(r1), 13.4, 13.4 + 5.55*math.sin(r1)),
              (10.1 + 5.55*math.cos(r2), 13.4, 13.4 + 5.55*math.sin(r2)))

    # Side ribs:
    # Left rib: at X = 2.05, Y from 13.4 to 10.0 (thickness 3.4)
    iline((2.05, 10.0, 3.4), (2.05, 13.4, 3.4))
    iline((2.05, 10.0, 3.4), (4.7, 10.0, 14.67))
    iline((2.05, 13.4, 3.4), (4.7, 13.4, 14.67))
    iline((4.7, 10.0, 14.67), (4.7, 13.4, 14.67))

    # Right rib: at X = 18.15
    iline((18.15, 10.0, 3.4), (18.15, 13.4, 3.4))
    iline((18.15, 10.0, 3.4), (15.5, 10.0, 14.67))
    iline((18.15, 13.4, 3.4), (15.5, 13.4, 14.67))
    iline((15.5, 10.0, 14.67), (15.5, 13.4, 14.67))

    # Central rib: width 1.0 -> X from 9.6 to 10.6
    # Under cylinder: Y = 10.0 - 1.7 = 8.3
    # Drop of 1.7: Z from 7.85 to 6.15
    # Toe: Y = 10.0 - 3.3 = 6.7, Z = 3.4
    iline((9.6, 8.3, 7.85), (9.6, 8.3, 6.15))
    iline((9.6, 8.3, 6.15), (9.6, 6.7, 3.4))
    iline((10.6, 8.3, 7.85), (10.6, 8.3, 6.15))
    iline((10.6, 8.3, 6.15), (10.6, 6.7, 3.4))
    iline((9.6, 6.7, 3.4), (10.6, 6.7, 3.4))
    iline((9.6, 8.3, 6.15), (10.6, 8.3, 6.15))

    doc.saveas(output_dxf_path)
    print('Saved DXF to:', output_dxf_path)

    if output_png_path:
        plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimSun']
        plt.rcParams['axes.unicode_minus'] = False
        fig = plt.figure(figsize=(12, 9), dpi=300)
        ax = fig.add_axes([0, 0, 1, 1])
        ctx = RenderContext(doc)
        out = MatplotlibBackend(ax)
        Frontend(ctx, out).draw_layout(msp, finalize=True)
        fig.savefig(output_png_path)
        plt.close(fig)
        print('Rendered PNG to:', output_png_path)

if __name__ == '__main__':
    create_refined_drawing(r'D:\Virtu模型\bearing_bracket_1to1_drawing.dxf', 'bearing_bracket_refined.png')
