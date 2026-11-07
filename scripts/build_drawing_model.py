# -*- coding: utf-8 -*-
"""
按图纸 (3D建模练习图1500例 / 3D模型(1)(1).jpg) 在 SOLIDWORKS 2021 中建模。

图纸内容（视觉辨识）：
  - 俯视图：外轮廓约 48×48 正方形（含内部投影线框）
  - 主视图：梯形轮廓，左高 57、右高 36，顶部为斜线
  - 轴测/剖视：斜顶多面体

本脚本采用"斜顶方棱柱（wedge）"解释来建模，直接使用图纸标注尺寸：
  - 底面：48 (X) × 48 (Y)
  - 高度沿 X 方向倾斜：左端 57，右端 36
建模方式：在上视基准面用"主视图梯形" (0,0)-(48,0)-(48,36)-(0,57) 作草图，
沿其法向（Y，即深度方向）拉伸 48mm，得到斜顶棱柱。

如需改为"缩颈四棱锥台（顶 36×36 倾斜）"解释，把 build_wedge 换成
build_frustum 即可（见文件末尾备选实现）。

运行解释器需装有 pywin32（且与运行本脚本的 python 同一解释器）。
用法：
  python scripts/build_drawing_model.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bridges.solidworks_bridge import SolidWorksBridge


def build_wedge(part):
    """斜顶方棱柱：主视图梯形轮廓拉伸 48mm 深。"""
    b = SolidWorksBridge._instance = None
    # 直接用传入 part 的 bridge 句柄
    bridge = build_wedge._bridge
    bridge.select_plane(part, "top")
    part.SketchManager.InsertSketch(True)
    part.ClearSelection2(True)
    L = part.SketchManager.CreateLine
    # 主视图梯形 (mm) -> 上视基准面(XZ)局部坐标 (x, z)
    L(0.0, 0.0, 0.0, 0.048, 0.0, 0.0)
    L(0.048, 0.0, 0.0, 0.048, 0.036, 0.0)
    L(0.048, 0.036, 0.0, 0.0, 0.057, 0.0)
    L(0.0, 0.057, 0.0, 0.0, 0.0, 0.0)
    part.SketchManager.InsertSketch(True)
    part.ClearSelection2(True)
    bridge.extrude_boss(part, 0.048)


def best_effort_mass_props(part):
    """尽力读取体积/表面积/质心；受 pywin32 类型库绑定限制可能失败。"""
    try:
        bodies = part.GetBodies2(0)
        if bodies:
            body = bodies[0]
            vol = body.GetVolume() * 1e9          # mm^3
            sur = body.GetSurfaceArea() * 1e6    # mm^2
            arr = body.GetMassProperties(0)
            cg = [float(arr[3 + i]) * 1000.0 for i in range(3)]  # mm
            return {"volume_mm3": vol, "surface_area_mm2": sur, "centroid_mm": cg}
    except Exception as e:
        return {"note": f"质量属性接口在本 pywin32/类型库组合下不可用: {e}；"
                        f"可在 SOLIDWORKS 中 评估->质量属性 直接读取。"}
    return {"note": "未取到实体质量属性"}


def main():
    bridge = SolidWorksBridge()
    build_wedge._bridge = bridge
    print("connect:", bridge.connect())
    part = bridge.new_part()
    build_wedge(part)
    print("model built (wedge)")

    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "runs", "drawing_model.sldprt")
    print("save:", bridge.save_part(part, out), "exists:", os.path.exists(out))

    mp = best_effort_mass_props(part)
    print("mass props:", mp)
    print("DONE ->", out)


if __name__ == "__main__":
    main()
