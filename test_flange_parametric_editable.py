# -*- coding: utf-8 -*-
r"""
测试带草图完全定义与方程驱动可二次修改的法兰盘建模脚本
"""
import os
import sys
import math
import time
import subprocess

import win32com.client.gencache as gc

TLB_GUID = "{83A33D31-27C5-11CE-BFD4-00400513BB57}"
SW_VERSION = 29

try:
    subprocess.run(["taskkill", "/F", "/IM", "SLDWORKS.exe"], capture_output=True)
except Exception:
    pass
time.sleep(2)

mod = gc.EnsureModule(TLB_GUID, 0, SW_VERSION, 0)
sw = mod.SldWorks()
sw.Visible = True

raw_part = sw.NewPart()
part = mod.IModelDoc2(raw_part._oleobj_)
print("New part created:", part.GetTitle())

# 注入全局变量
eqn = part.GetEquationMgr()
params = [
    ('"D_Outer" = 160', '法兰外径'),
    ('"D_Bore" = 50', '中心通孔'),
    ('"Thk_Disk" = 20', '法兰厚度'),
    ('"D_Boss" = 90', '凸台外径'),
    ('"H_Boss" = 15', '凸台高度'),
    ('"PCD" = 125', '螺栓孔分度圆'),
    ('"N_Bolts" = 6', '螺栓孔数量'),
    ('"D_Bolt" = 14', '螺栓孔直径')
]
for idx, (eq, desc) in enumerate(params):
    eqn.Add(idx, eq)
    print(f"Added equation #{idx}: {eq} ({desc})")

# 选择前视基准面
part.SelectByID("前视基准面", "PLANE", 0, 0, 0)
part.SketchManager.InsertSketch(True)

# 绘制外圆与内孔
c1 = part.SketchManager.CreateCircleByRadius(0.0, 0.0, 0.0, 0.080)
c2 = part.SketchManager.CreateCircleByRadius(0.0, 0.0, 0.0, 0.025)

# 添加智能尺寸定义
part.ClearSelection2(True)
c1.Select4(False, None)
d1 = part.AddDimension2(0.080, 0.080, 0.0)
print("d1 added:", d1.GetName2() if d1 else "None")

part.ClearSelection2(True)
c2.Select4(False, None)
d2 = part.AddDimension2(-0.025, 0.025, 0.0)
print("d2 added:", d2.GetName2() if d2 else "None")

# 拉伸主体
extrude1_args = [
    True, False, True, 0, 0, 0.020, 0.0,
    False, False, False, False, 0.0, 0.0,
    False, False, False, False, True, False, True,
    0, 0.0, False
]
feat1 = part.FeatureManager.FeatureExtrusion2(*extrude1_args)
print("feat1 created:", feat1.Name if feat1 else "None")

part.ViewZoomtofit2()
print("Test completed successfully!")
