# -*- coding: utf-8 -*-
"""ruler 层反例：显式给定不合规 tapered 轮毂，硬判据必须判红。"""
import sys

sys.path.insert(0, r"D:\Virtu模型\scripts")
import impeller_deterministic_solver as S          # noqa: E402
import closed_impeller_proctor as CP               # noqa: E402

p, m = S.build(220.0, 40300.5)
print("基线 VIOL:", CP.ruler(p)[1])

bad = dict(p)
bad["hub_disk_thickness_mm"] = 8.0
bad["hub_rim_thickness_mm"] = 4.0
bad["hub_taper_exponent"] = 1.0
rec, vio, adv = CP.ruler(bad)
print(f"反例(8mm, p=1.0) VIOL={len(vio)}")
for x in vio:
    print("  红:", x)
print("是否命中 bore 判据:", any("bore" in x or "轮毂" in x for x in vio))

same = dict(p)
same["hub_disk_thickness_mm"] = 12.25
same.pop("hub_rim_thickness_mm")
print("退化(无 h_rim 字段) VIOL:", len(CP.ruler(same)[1]))
