# -*- coding: utf-8 -*-
import pathlib

p = pathlib.Path(r"D:\Virtu模型\scripts\impeller_deterministic_solver.py")
s = p.read_text(encoding="utf-8")
s = s.replace(
    'def solve_min_hub_thickness(p, h_rim=H_RIM_MIN, power=HUB_TAPER_POWER, lo=8.0, hi=40.0, step=0.25):',
    'def solve_min_hub_thickness(p, h_rim=H_RIM_MIN, power=HUB_TAPER_POWER, lo=8.0, hi=40.0, step=0.25,\n                           target=HUB_FOS_TARGET):')
s = s.replace('        if r["FOS_bore"] >= 1.5:\n            return th, r',
              '        if r["FOS_bore"] >= target:\n            return th, r')
s = s.replace(
    'HUB_TAPER_POWER = 6.0    # 外段幂律指数：内厚外薄，坡度越大 bore 应力越低',
    'HUB_TAPER_POWER = 6.0    # 外段幂律指数：内厚外薄，坡度越大 bore 应力越低\n'
    'HUB_FOS_TARGET = 1.60    # 反解厚度时的设计目标（尺子红线 1.5，留约 7% 裕度）')
p.write_text(s, encoding="utf-8")
print("ok", "target" in s, "HUB_FOS_TARGET" in s)
