# -*- coding: utf-8 -*-
"""
兜底方案 B：用 ezdxf 生成法兰盘 2D 剖面 (DXF, 单位 mm)。
SOLIDWORKS 可直接 File > Open 该 DXF，导入向导会建成草图，
随后一次"拉伸"(厚度 20) + "异形孔/切除"(6 个 Ø12 通孔) 即得到实体。
无需 SW 运行、无需任何网络安装。
参数(mm): 外径120 轴孔40 厚20 6×Ø12 均布Ø95
"""
import math
import ezdxf

OUT = r"D:\Virtu模型\Flange_Parametric.dxf"

D_Outer = 120.0
D_Bore  = 40.0
Thk     = 20.0
N       = 6
D_Bolt  = 12.0
PCD     = 95.0

doc = ezdxf.new("R2010")
msp = doc.modelspace()

# 外圆 + 中心轴孔
msp.add_circle((0, 0), D_Outer / 2.0)
msp.add_circle((0, 0), D_Bore / 2.0)

# 6 个螺栓孔（均布于分布圆 PCD）
r_pcd = PCD / 2.0
r_bolt = D_Bolt / 2.0
for i in range(N):
    a = 2.0 * math.pi * i / N
    x = r_pcd * math.cos(a)
    y = r_pcd * math.sin(a)
    msp.add_circle((x, y), r_bolt)

# 中心线（辅助）
msp.add_line((-D_Outer, 0), (D_Outer, 0), dxfattribs={"linetype": "CENTER"})
msp.add_line((0, -D_Outer), (0, D_Outer), dxfattribs={"linetype": "CENTER"})

doc.saveas(OUT)
print("已生成 DXF:", OUT)
print("包含: 外圆Ø%d, 轴孔Ø%d, %d×Ø%d 均布Ø%d" % (D_Outer, D_Bore, N, D_Bolt, PCD))
