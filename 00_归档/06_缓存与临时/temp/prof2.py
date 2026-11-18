# -*- coding: utf-8 -*-
import cProfile
import pstats
import sys

sys.path.insert(0, r"D:\Virtu模型\scripts")
import impeller_deterministic_solver as S  # noqa: E402

pr = cProfile.Profile()
pr.enable()
S.build(220.0, 40300.5)
pr.disable()
st = pstats.Stats(pr)
st.sort_stats("cumulative").print_stats(12)
