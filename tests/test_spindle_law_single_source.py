"""转速/切削速度公式必须与 virtu_eval.derivation.LAWS 单一参照同源（测量宪法第 5 条）。

virtu_real_backend 自带两份硬编码转速公式（11-08 审计残留项）。数值当前恒等，
但没有闸门钉住，任何一侧漂移都会静默产生两套物理。本测试把 backend 的产物
逐点打到 LAWS 权威表达式上；植入错公式（100*vc 冒充 1000*vc）必须红，
证明比对不是空转。
"""
import math
import unittest

from virtu_eval.audit_case_arithmetic import eval_expr
from virtu_eval.derivation import resolve
from virtu_real_backend import _cutting_speed_problem, _spindle_speed_problem

VC_GRID = [60.0, 120.0, 180.0, 250.0]
D_GRID = [20.0, 50.0, 80.0, 160.0]
N_GRID = [300.0, 900.0, 2400.0, 6000.0]


def laws_spindle_rpm(vc: float, d: float) -> float:
    expr = resolve("process", {"vc": vc, "D": d, "f": 0.2, "ap": 2.0,
                               "r_eps": 0.8, "L": 100.0})["spindle_rpm"]
    val, _ = eval_expr(expr)
    return val


class SpindleLawSingleSourceTests(unittest.TestCase):
    def test_backend_spindle_matches_laws_grid(self):
        for vc in VC_GRID:
            for d in D_GRID:
                msgs = [{"role": "user",
                         "content": f"求主轴转速：切削速度 Vc={vc:g} m/min，直径 D={d:g} mm"}]
                got = _spindle_speed_problem(msgs)
                self.assertIsNotNone(got, f"backend 未识别 Vc={vc} D={d}")
                _, _, n = got
                want = laws_spindle_rpm(vc, d)
                self.assertAlmostEqual(n / want, 1.0, delta=1e-9,
                                       msg=f"Vc={vc} D={d}: backend={n} LAWS={want}")

    def test_backend_cutting_speed_roundtrips_through_laws(self):
        for d in D_GRID:
            for n in N_GRID:
                msgs = [{"role": "user",
                         "content": f"求切削速度：直径 D={d:g} mm，主轴转速 n={n:g} r/min"}]
                got = _cutting_speed_problem(msgs)
                self.assertIsNotNone(got, f"backend 未识别 D={d} n={n}")
                _, _, vc = got
                # 把 backend 算出的 Vc 代回权威定律，必须复现原转速
                back = laws_spindle_rpm(vc, d)
                self.assertAlmostEqual(back / n, 1.0, delta=1e-9,
                                       msg=f"D={d} n={n}: 往返={back}")

    def test_mutant_formula_must_fail(self):
        """反证：100*vc/(pi*D) 冒充权威公式时，比对必须判红（闸非空转）。"""
        vc, d = 120.0, 80.0
        want = laws_spindle_rpm(vc, d)
        mutant = 100.0 * vc / (math.pi * d)
        self.assertGreater(abs(mutant / want - 1.0), 0.5)
        # 另一变异：π 漏掉（量纲级错误）
        mutant2 = 1000.0 * vc / d
        self.assertGreater(abs(mutant2 / want - 1.0), 0.5)


if __name__ == "__main__":
    unittest.main()