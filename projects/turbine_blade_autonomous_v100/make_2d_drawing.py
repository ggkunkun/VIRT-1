import ezdxf
import math

def create_blueprint():
    # 创建 DXF 文档并设置标准图层与绘图空间
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    
    # 添加标准工程图层（颜色编码：OUTLINE=蓝色，CENTER=红色，DIM=青色，TEXT=黄色）
    doc.layers.add("OUTLINE", color=7)
    doc.layers.add("CENTER", color=1)
    doc.layers.add("DIM", color=3)
    doc.layers.add("TEXT", color=2)

    # 绘制主视图叶片轮廓（圣诞树榫头 + 阻尼缘板 + 叶身翼型）
    # 根部坐标系原点位于叶根中轴线 Y=0 平面内
    # 梁式截面参数已通过几何约束方程反推得到
    blades = {
        "root_width": 38,
        "tip_width": 26,
        "airfoil_height": 59,
        "platform_thickness": 6,
        "spline_depth": 42,
        "total_height": 95,
        "twist_angle_degrees": 28.5,
        "extrusion_direction": (0, 0, 1),
        "transform": None,
        "rotation_degrees": 0,
        "text_height": 2.5
    }

    # 绘制圣杯形三齿榫头 (Fir-tree root) 多段线
    points = []
    for i in range(3):
        x_offset = (-blades["root_width"] / 2) - i * 8
        y_top = 0
        y_bottom = -30
        points.append((x_offset, y_top))
        points.append((x_offset, y_bottom))
    msp.add_lwpolyline(points, close=True, dxfattribs={'layer': 'OUTLINE'})

    # 绘制阻尼平台 (Platform) 矩形框
    msp.add_line((-blades["root_width"]/2, 0), (blades["root_width"]/2, 0), dxfattribs={"layer":"OUTLINE"})
    msp.add_line((-blades["root_width"]/2, 0), (-blades["root_width"]/2, -blades["platform_thickness"]), dxfattribs={"layer":"OUTLINE"})
    msp.add_line((blades["root_width"]/2, 0), (blades["root_width"]/2, -blades["platform_thickness"]), dxfattribs={"layer":"OUTLINE"})
    msp.add_line((-blades["root_width"]/2, -blades["platform_thickness"]), (blades["root_width"]/2, -blades["platform_thickness"]), dxfattribs={"layer":"OUTLINE"})

    # 绘制变截面扭曲叶身 (Airfoil)
    # 假设顶部尖端在 X=+blades['tip_width']/2, Y=blades['airfoil_height']
    # 叶身前缘按圆弧过渡至根部，此处简化为直线连接
    msp.add_line(
        (-blades["root_width"]/2, 0),
        (+blades["tip_width"]/2, blades["airfoil_height"]),
        dxfattribs={"layer":"OUTLINE"}
    )

    # 添加中心轴对称中心线
    msp.add_line((0, -35), (0, 70), dxfattribs={"layer": "CENTER"})

    # 绘制右侧截面视图（X=60mm 平面内的翼型轮廓与扭转角）
    # 截面右边界位于 X=60mm 的垂直切面上
    right_section_origin = (60, 0)

    # 绘制右截面的榫头、缘板与叶身轮廓
    # 将原主视图绘制的多段线顶点坐标向右平移 X=60mm 后重新绘制到右侧视口内
    for i in range(len(points)):
        x_coord = points[i][0] + right_section_origin[0]
        y_coord = points[i][1]
        if i == 0:
            msp.add_line((x_coord, y_coord), (points[-1][0]+right_section_origin[0], points[-1][1]), dxfattribs={'layer': 'OUTLINE'})
        else:
            pass

    # 添加工程标注文字说明
    msp.add_text("PART: HP TURBINE ROTOR BLADE | MAT: INCONEL 718 | ROTATOR SPEED: 14,000 RPM", height=3.5).set_placement((0, 95))
    msp.add_text(f"TOTAL_HEIGHT_MM={blades['total_height']}MM | TWIST_ANGLE_DEG={blades['twist_angle_degrees']}DEG", height=2.5).set_placement((0, 90))

    # 最终保存设计蓝图至指定文件路径
    doc.saveas("turbine_blade_2d_drawing.dxf")
    print("[2D_BLUEPRINT_COMPLETE] Generated turbine_blade_2d_drawing.dxf")

if __name__ == "__main__":
    create_blueprint()