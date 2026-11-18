# -*- coding: utf-8 -*-
"""Falsification gates for the tool-call plumbing fixed on 2026-11-06.

Two incidents these tests pin down, both measured the same day:
  * 16 `cadcam_*` schemas make a toolcall prompt 4779 tokens, while the old backend
    ladder capped any tool turn at num_ctx=4096 ⇒ every real tool request died with
    HTTP 400 "exceeds the available context size" — the model never got asked.
  * arms carrying `tools_dimensions` but no `tools` scored 24/30 zeros and the same
    dimension mean across three arms (16.67) — vacuous grading that still produced
    a publishable number.

2026-11-13：工具面从 16 增到 17（补 `cadcam_feature_ops`），同一条请求在两个面上
各做了一次真实服务端回读（`scripts/measure_prompt_tokens.py` →
`reports/PROMPT_TOKENS_BY_TOOL_SURFACE_2026-11-13.json`）：

    16 工具 → prompt_eval_count 4759
    17 工具 → prompt_eval_count 5132（+373）

于是「估算 vs 实测」的 20% 校准对两个面都成立，不必再靠「不低于旧实测」兜底。
"""
import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import virtu_real_backend as backend                      # noqa: E402
from virtu_eval.runner import tools_gate                  # noqa: E402

ARMS = json.load(open(ROOT / "virtu_eval" / "arms.json", encoding="utf-8"))
ARM_TOOLS = ARMS["virtu_moe_14b"]["tools"]
CASE = json.loads(open(ROOT / "data" / "benchmark" / "virtu_eval_v1" / "toolcall.jsonl",
                       encoding="utf-8").readline())
#: 实测面与数字是绑定的。2026-11-13 用同一条题（toolcall-e01）、同一模型
#: （virtu-moe-14b:latest）、num_ctx=8192，对 16 / 17 两个工具面各做一次真实
#: /api/chat 回读：16 面 4759，17 面 5132（见 reports/PROMPT_TOKENS_BY_TOOL_SURFACE_2026-11-13.json）。
#: 11-06 记的 4779 与今天 4759 差 20，是工具描述文本在这期间被改过的结果——
#: 两个数都保留，但卡校准只认当下这一次回读。
MEASURED_TOOLS = [t for t in ARM_TOOLS if t["function"]["name"] != "cadcam_feature_ops"]
MEASURED_PROMPT_TOKENS_16 = 4759
MEASURED_PROMPT_TOKENS_17 = 5132
HISTORICAL_4779 = 4779


class TestCtxLadderMatchesMeasurement(unittest.TestCase):
    def test_estimator_is_calibrated_to_the_observed_400(self):
        self.assertEqual(len(MEASURED_TOOLS), 16, "实测面必须仍是当年那 16 个工具")
        est = backend._estimate_prompt_tokens([{"role": "user", "content": CASE["prompt"]}],
                                              MEASURED_TOOLS)
        drift = abs(est - MEASURED_PROMPT_TOKENS_16) / MEASURED_PROMPT_TOKENS_16
        self.assertLessEqual(drift, 0.20,
                             f"估算 {est} 偏离实测 {MEASURED_PROMPT_TOKENS_16} 达 {drift:.0%}；"
                             f"字符/token 常数 {_CHARS_NOTE()} 需要重新标定")
        self.assertGreaterEqual(est, MEASURED_PROMPT_TOKENS_16, "估算应偏保守（宁可多给一档 KV）")
        # 历史值只用于解释偏差来源，不参与卡线
        self.assertLess(abs(MEASURED_PROMPT_TOKENS_16 - HISTORICAL_4779), 60,
                        "重测值离 11-06 的 4779 太远，说明工具描述被大改过，需重新确认基线")

    def test_grown_surface_matches_its_own_measurement(self):
        """17 工具面有独立实测，就不再拿 16 面的数字外推。"""
        self.assertEqual(len(ARM_TOOLS), 17, "工具面变了，先跑 scripts/measure_prompt_tokens.py")
        est = backend._estimate_prompt_tokens([{"role": "user", "content": CASE["prompt"]}],
                                              ARM_TOOLS)
        drift = abs(est - MEASURED_PROMPT_TOKENS_17) / MEASURED_PROMPT_TOKENS_17
        self.assertLessEqual(drift, 0.20,
                             f"17 工具面估算 {est} 偏离实测 {MEASURED_PROMPT_TOKENS_17} 达 {drift:.0%}")
        self.assertGreaterEqual(est, MEASURED_PROMPT_TOKENS_17, "估算应偏保守")
        self.assertGreater(MEASURED_PROMPT_TOKENS_17, MEASURED_PROMPT_TOKENS_16,
                           "多一个工具面反而更短，说明回读写错了面")

    def test_tool_turn_no_longer_caps_at_4096(self):
        ctx = backend._plan_ctx([{"role": "user", "content": CASE["prompt"]}], ARM_TOOLS, 256)
        self.assertGreaterEqual(ctx, 8192, "带工具面的腿必须越过 4096，否则恒 400")

    def test_plain_short_turn_stays_cheap(self):
        ctx = backend._plan_ctx([{"role": "user", "content": "法兰外径多少"}], None, 256)
        self.assertEqual(ctx, 2048, "无工具短问不该被推高，白白吃 KV")

    def test_env_override_still_wins(self):
        old = os.environ.get("VIRTU_NUM_CTX")
        os.environ["VIRTU_NUM_CTX"] = "12288"
        try:
            self.assertEqual(backend._resolve_ctx([{"content": "x"}], None, 128), 12288)
        finally:
            os.environ.pop("VIRTU_NUM_CTX", None)
            if old is not None:
                os.environ["VIRTU_NUM_CTX"] = old

    def test_ladder_top_is_finite_and_next_step_works(self):
        self.assertEqual(backend._next_ctx_up(4096), 8192)
        self.assertIsNone(backend._next_ctx_up(backend._CTX_LADDER[-1]),
                          "已经在最高档时必须没有下一档 —— 让调用方报错而不是无限重试")


def _CHARS_NOTE():
    return backend._CHARS_PER_TOKEN


class _StubBackend:
    max_tokens = 256
    _chat_with_room = backend.VirtuRealModel._chat_with_room


class TestOverflowRetry(unittest.TestCase):
    def test_400_overflow_escalates_ctx_and_succeeds(self):
        seen = []

        def chat(**kw):
            seen.append(kw["num_ctx"])
            if kw["num_ctx"] < 8192:
                raise RuntimeError(f"Ollama API HTTP 400: request (4779 tokens) exceeds the "
                                   f"available context size ({kw['num_ctx']} tokens), try increasing it")
            return {"content": "ok"}

        out = _StubBackend()._chat_with_room(chat, num_ctx=4096, num_predict=256,
                                             messages=[{"content": "x"}], tools=None)
        self.assertEqual(out["content"], "ok")
        self.assertEqual(seen, [4096, 8192], "第一次失败后必须升一档再试，而不是原样重放")

    def test_unrelated_error_propagates_immediately(self):
        calls = []

        def chat(**kw):
            calls.append(1)
            raise RuntimeError("Ollama API HTTP 500: model not found")

        with self.assertRaises(RuntimeError):
            _StubBackend()._chat_with_room(chat, num_ctx=4096, num_predict=256, messages=[])
        self.assertEqual(len(calls), 1, "非目标错误不得重试（重试会把真故障伪装成慢）")

    def test_truncated_tool_json_still_widens_predict_budget(self):
        seen = []

        def chat(**kw):
            seen.append(kw.get("num_predict"))
            if len(seen) == 1:
                raise RuntimeError("Ollama API HTTP 500: invalid tool call arguments "
                                   "unexpected end of JSON input")
            return {"content": "ok"}

        _StubBackend()._chat_with_room(chat, num_ctx=8192, num_predict=220, messages=[])
        self.assertGreater(seen[1], seen[0])

    def test_no_higher_step_raises_instead_of_looping(self):
        def chat(**kw):
            raise RuntimeError("request (99999 tokens) exceeds the available context size "
                               f"({kw['num_ctx']} tokens)")

        with self.assertRaises(RuntimeError):
            _StubBackend()._chat_with_room(chat, num_ctx=backend._CTX_LADDER[-1],
                                           num_predict=256, messages=[])


class TestToolsVacuityGate(unittest.TestCase):
    TC = [{"dimension": "toolcall", "id": "t1"}, {"dimension": "toolcall", "id": "t2"}]

    def test_toolcall_without_schema_is_refused(self):
        with self.assertRaises(ValueError) as ctx:
            tools_gate({"model_id": "virtu-moe-14b:fast", "tools_dimensions": ["toolcall"]}, self.TC)
        msg = str(ctx.exception)
        self.assertIn("2", msg, "报错必须说清涉及几道题")
        self.assertIn("virtu-moe-14b:fast", msg, "报错必须点名是哪条臂")

    def test_toolcall_with_schema_passes(self):
        self.assertEqual(tools_gate({"tools": [{"function": {}}]}, self.TC)["verdict"], "ok")

    def test_waiver_is_recorded_not_silent(self):
        old = os.environ.get("VIRTU_ALLOW_TOOLSLESS_TOOLCALL")
        os.environ["VIRTU_ALLOW_TOOLSLESS_TOOLCALL"] = "1"
        try:
            g = tools_gate({"model_id": "m"}, self.TC)
            self.assertEqual(g["verdict"], "waived_by_env")
            self.assertFalse(g["schema_exposed"])
        finally:
            os.environ.pop("VIRTU_ALLOW_TOOLSLESS_TOOLCALL", None)
            if old is not None:
                os.environ["VIRTU_ALLOW_TOOLSLESS_TOOLCALL"] = old

    def test_no_toolcall_cases_is_not_applicable_not_green(self):
        g = tools_gate({"model_id": "m"}, [{"dimension": "knowledge", "id": "k1"}])
        self.assertFalse(g["applicable"])
        self.assertEqual(g["verdict"], "not_applicable")

    def test_empty_case_list_cannot_dress_as_ok(self):
        self.assertEqual(tools_gate({"model_id": "m"}, [])["toolcall_cases"], 0)
        self.assertFalse(tools_gate({"model_id": "m"}, [])["applicable"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
