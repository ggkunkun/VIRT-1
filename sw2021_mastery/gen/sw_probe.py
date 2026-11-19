# -*- coding: utf-8 -*-
"""连接探针：只做一件事——用版本化 ProgID 拉起 SW2021 并断言版本。"""
import json
import sys
import time

SK = r"C:\Users\Administrator\.workbuddy\skills\solidworks-automation\scripts"
sys.path.insert(0, SK)

from sw_connect import connect_solidworks, get_sw_version  # noqa: E402

t0 = time.time()
sw, model, meta = connect_solidworks(version=2021, wait_seconds=180, visible=True, return_metadata=True)
print("META", json.dumps(meta, ensure_ascii=False, default=str))
print("ELAPSED", round(time.time() - t0, 1))
print("REVISION", sw.RevisionNumber)
print("YEAR", get_sw_version(sw)["year"])
try:
    print("TEMPLATE_PART", sw.GetUserPreferenceStringValue(8))
except Exception as exc:
    print("TEMPLATE_PART_ERR", exc)
print("VISIBLE", sw.Visible)
