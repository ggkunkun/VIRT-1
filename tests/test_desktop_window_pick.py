# -*- coding: utf-8 -*-
"""窗口选择器判据：主窗必须压过辅助窗与启动画面。

候选集取自 2026-11-05 本机 SOLIDWORKS 2021 实启后的 EnumWindows 结果：
第一个 PID 命中窗是 0×0 的 Internet Explorer_Hidden，旧逻辑会选它。
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bridges.desktop_controller import _pick_main_window, _window_candidate_score  # noqa: E402

SW_TITLES = ["SOLIDWORKS", "SLDWORKS"]
MAIN = (264640, "SOLIDWORKS Premium 2021 SP5.0 - [零件1]",
        "Afx:0000000140000000:8:0000000000010003", 849239, 3820)


class WindowPickTests(unittest.TestCase):
    def test_real_solidworks_candidate_set(self):
        candidates = [
            (200222, "", "Internet Explorer_Hidden", 0, 3820),
            (332272, "零件1", "swThumbnailWnd", 0, 3820),
            (1835904, "splash", "Afx:0000000140000000:0", 154560, 3820),
            MAIN,
        ]
        self.assertEqual(_pick_main_window(candidates, SW_TITLES), MAIN[0])
        # 反证：旧策略「第一个 PID 命中」会选中 0×0 辅助窗
        self.assertEqual(candidates[0][0], 200222)
        self.assertNotEqual(_pick_main_window(candidates, SW_TITLES), candidates[0][0])

    def test_minimized_main_window_still_wins(self):
        minimized = (264640, "SOLIDWORKS Premium 2021 SP5.0",
                     "Afx:0000000140000000:8", 23373, 3820)
        big_helper = (111, "splash", "Afx:0000000140000000:0", 900000, 3820)
        big_unrelated = (222, "Some Other App", "Chrome_WidgetWin_1", 900000, 3820)
        self.assertEqual(
            _pick_main_window([big_helper, big_unrelated, minimized], SW_TITLES),
            minimized[0])

    def test_helpers_only_returns_none(self):
        candidates = [
            (1, "", "IME", 0, 9),
            (2, "splash", "Afx:0000000140000000:0", 154560, 9),
            (3, "", "Internet Explorer_Hidden", 0, 9),
        ]
        self.assertIsNone(_pick_main_window(candidates, SW_TITLES))

    def test_title_match_beats_larger_unrelated(self):
        main = (10, "SOLIDWORKS", "Afx:0000000140000000:8", 50000, 9)
        bigger = (11, "Explorer", "CabinetWClass", 800000, 9)
        self.assertEqual(_pick_main_window([bigger, main], SW_TITLES), 10)

    def test_zero_area_titled_window_allowed(self):
        # 最小化后 rect 可能归零，但标题仍能证明它是主窗
        titled = (12, "SOLIDWORKS", "Afx:0000000140000000:8", 0, 9)
        helper = (13, "", "Internet Explorer_Hidden", 0, 9)
        self.assertEqual(_pick_main_window([helper, titled], SW_TITLES), 12)
        self.assertEqual(_window_candidate_score("splash", "Afx:0", 154560, SW_TITLES), None)


if __name__ == "__main__":
    unittest.main()
