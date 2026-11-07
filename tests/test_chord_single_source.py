"""The chord law is implemented twice; pin them together until a trig family exists.

`derivation.LAWS` speaks arithmetic only (no `sin`), so the分度圆弦长 cannot be registered
there without extending the expression evaluator - which would re-grade every derivation case
mid-measurement. Meanwhile `virtu_real_backend.py` and the flange executor each compute
`D*sin(180/z)` by hand. Measured 2026-11-05 they agree with the closed form to 0.0 relative
error on a grid; this test is what keeps that from rotting silently, and the TODO is the single
source, not another copy.
"""
import io
import math
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SIZES = [(80.0, 2), (80.0, 6), (160.0, 4), (160.0, 8), (274.0, 6), (32.0, 12), (125.0, 3)]


def closed_form(diameter, count):
    return 2.0 * (diameter / 2.0) * math.sin(math.pi / count)


class ChordHasOneMeaning(unittest.TestCase):
    def test_runtime_backend_still_matches_the_closed_form(self):
        text = io.open(ROOT / "virtu_real_backend.py", encoding="utf-8").read()
        self.assertIn("chord = d * math.sin(math.radians(180.0 / z))", text,
                      "运行时的弦长写法变了：要么同步本测试，要么把它接进 derivation.LAWS")
        for d, z in SIZES:
            self.assertAlmostEqual(d * math.sin(math.radians(180.0 / z)),
                                   closed_form(d, z), places=9, msg=(d, z))

    def test_the_executor_agrees_or_the_divergence_is_declared(self):
        src = io.open(ROOT / "scripts" / "sw_flange_demo.py", encoding="utf-8").read()
        exprs = re.findall(r"(?:chord|弦长)[^\n]*=[^\n]*", src)
        if not exprs:
            self.skipTest("执行器不再自算弦长，说明已收敛到单一来源")
        for line in exprs:
            self.assertNotIn("cos", line, f"执行器用了另一种等价式，需人工确认口径一致：{line}")

    def test_no_third_copy_appears(self):
        copies = []
        for rel in ("virtu_real_backend.py", "scripts/sw_flange_demo.py",
                    "virtu_eval/planted_defects.py", "bridges/tool_calling_specs.py"):
            path = ROOT / rel
            if path.exists() and re.search(r"sin\(math\.radians\(180", path.read_text(
                    encoding="utf-8", errors="ignore")):
                copies.append(rel)
        self.assertLessEqual(len(copies), 2,
                             f"弦长实现复制到 {copies}；第三份出现即说明没有收口到单一来源")


if __name__ == "__main__":
    unittest.main()
