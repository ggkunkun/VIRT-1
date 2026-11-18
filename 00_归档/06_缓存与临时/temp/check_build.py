# -*- coding: utf-8 -*-
import json
import sys

sys.path.insert(0, r"D:\Virtu模型\scripts")
import impeller_deterministic_solver as S          # noqa: E402
import closed_impeller_proctor as CP               # noqa: E402

p, m = S.build(220.0, 40300.5)
print(json.dumps(p, ensure_ascii=False, indent=1))
print("META", json.dumps(m, ensure_ascii=False))
v, d, a = CP.ruler(p)
print("VIOL", len(v))
for x in v:
    print("  -", x)
for x in a:
    if "bore" in x.lower() or "taper" in x.lower():
        print("  adv:", x)
