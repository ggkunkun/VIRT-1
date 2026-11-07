# -*- coding: utf-8 -*-
"""tests/test_agent_adaptive_routing.py — Test Suite for Explicit Modality Dispatch.

Verifies:
1. Direct execution via explicit modality (PYTHON_SDK, FUNCTION_CALLING, DESKTOP_GUI, etc.)
2. Removal of automatic difficulty assessment and routing
3. AgentExecutionReport serialization and summary generation
4. Resilient parameter handling and modality fallbacks
"""

import os
import sys
import json
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from virtu_omni.agent.adaptive_router import (
    AgentDispatcher,
    AccessModality,
    MODALITY_FALLBACKS,
    DIFFICULTY_ROUTING_DISABLED,
)
from virtu_omni.agent.cadcam_autonomous_agent import CADCAMAutonomousAgent


class TestAgentDirectRouting(unittest.TestCase):

    def setUp(self):
        self.agent = CADCAMAutonomousAgent()
        self.dispatcher = AgentDispatcher()

    def test_01_modalities_enum(self):
        """Test supported access modalities are present."""
        self.assertEqual(AccessModality.PYTHON_SDK.value, "PYTHON_SDK")
        self.assertEqual(AccessModality.FUNCTION_CALLING.value, "FUNCTION_CALLING")
        self.assertEqual(AccessModality.MCP.value, "MCP")
        self.assertEqual(AccessModality.CLI.value, "CLI")
        self.assertEqual(AccessModality.REST_API.value, "REST_API")
        self.assertEqual(AccessModality.DESKTOP_GUI.value, "DESKTOP_GUI")
        self.assertEqual(AccessModality.AGENT_CHAIN.value, "AGENT_CHAIN")

    def test_02_agent_solve_python_sdk(self):
        """Test Agent execution via explicit PYTHON_SDK modality."""
        prompt = "校验宏程序 #100=50.0\n#101=10.0\nWHILE [#101 LE #100] DO 1\n#101=#101+5\nEND 1\nM30"
        rep = self.agent.solve(
            prompt,
            modality="PYTHON_SDK",
            target_software="cimco",
            action="validate_macro",
            params={"code": prompt}
        )
        self.assertTrue(rep.success)
        self.assertEqual(rep.modality, "PYTHON_SDK")
        self.assertTrue(rep.result_data.get("is_valid"))
        self.assertIn("#100", rep.result_data.get("variables", []))

    def test_03_agent_solve_function_calling(self):
        """Test Agent execution via explicit FUNCTION_CALLING modality.

        DXF 无头生成依赖 ezdxf；该库未安装时底层 bridge 同样返回
        'ezdxf library not available'，属环境依赖缺失而非路由问题。
        因此此处断言：走的是 FUNCTION_CALLING 通道，且失败时沿固定容灾链降级。
        """
        prompt = "在AutoCAD中生成测试轮廓"
        params = {
            "action": "create_dxf",
            "drawing_name": "agent_test_dxf",
            "entities": [{"type": "circle", "center": [0, 0], "radius": 15.0}]
        }
        rep = self.agent.solve(
            prompt,
            modality="FUNCTION_CALLING",
            target_software="autocad",
            action="create_dxf",
            params=params
        )
        self.assertEqual(rep.modality, "FUNCTION_CALLING")
        self.assertEqual(rep.action, "create_dxf")
        self.assertEqual(rep.target_software, "autocad")
        self.assertTrue(rep.execution_attempts)
        self.assertEqual(rep.execution_attempts[0]["modality"], "FUNCTION_CALLING")
        if not rep.success:
            # 失败时必须如实记录降级过程
            self.assertGreaterEqual(len(rep.execution_attempts), 1)
            self.assertEqual(rep.result_data["status"], "error")
        else:
            self.assertEqual(rep.executed_modality, "FUNCTION_CALLING")
            self.assertEqual(rep.result_data.get("status"), "success")

    def test_04_agent_solve_desktop_gui(self):
        """Test Agent execution via explicit DESKTOP_GUI modality."""
        prompt = "截屏当前桌面"
        os.makedirs(os.path.join(ROOT, "scratch"), exist_ok=True)
        out_cap = os.path.join(ROOT, "scratch", "agent_gui_solve.png")
        rep = self.agent.solve(
            prompt,
            modality="DESKTOP_GUI",
            target_software="desktop",
            action="capture",
            params={"output_path": out_cap}
        )
        self.assertTrue(rep.success)
        self.assertEqual(rep.modality, "DESKTOP_GUI")
        self.assertTrue(os.path.exists(out_cap))

    def test_05_invalid_modality_defaults_to_function_calling(self):
        """Test that unknown/invalid modality gracefully defaults to FUNCTION_CALLING."""
        rep = self.agent.solve(
            "测试非法模态",
            modality="NON_EXISTENT_MODALITY",
            target_software="cimco",
            action="validate_macro",
            params={"code": "#100=1\nM30"}
        )
        self.assertEqual(rep.modality, "FUNCTION_CALLING")

    def test_06_execution_report_structure(self):
        """Test AgentExecutionReport formatting and serialization."""
        rep = self.agent.solve(
            "#100=1\n#101=2\nM30",
            modality="PYTHON_SDK",
            target_software="cimco",
            action="validate_macro",
            params={"code": "#100=1\n#101=2\nM30"}
        )
        report_dict = rep.to_dict()
        self.assertIn("task_prompt", report_dict)
        self.assertIn("modality", report_dict)
        self.assertIn("success", report_dict)
        self.assertIn("total_latency_sec", report_dict)
        self.assertIn("result_data", report_dict)
        summary = rep.summary_markdown()
        self.assertIn("Agent 执行报告", summary)
        self.assertIn("PYTHON_SDK", summary)

    # ---- 新增：难度自动选路规则已删除的回归断言 ----

    def test_07_no_difficulty_classification_api(self):
        """难度分级相关的 API 与枚举必须已彻底移除。"""
        import virtu_omni.agent.adaptive_router as router

        for removed in ("TaskDifficultyAnalyzer", "TaskDifficultyLevel",
                        "DifficultyAssessment", "AdaptiveAgentDispatcher"):
            self.assertFalse(hasattr(router, removed),
                             f"{removed} 不应再存在——难度自动选路规则已删除")
        for removed in ("GUI_KEYWORDS", "CHAIN_KEYWORDS", "HEAVY_KEYWORDS", "TRIVIAL_KEYWORDS"):
            self.assertFalse(hasattr(router, removed),
                             f"{removed} 难度关键词表不应再存在")

    def test_08_difficulty_fields_marked_disabled(self):
        """报告中的难度字段保留但恒为停用标记。"""
        # 用不触碰真实工业软件的纯内存动作（宏程序静态校验）验证报告字段。
        rep = self.agent.solve(
            "#100=1\n#101=2\nM30",
            modality="PYTHON_SDK",
            target_software="cimco",
            action="validate_macro",
            params={"code": "#100=1\n#101=2\nM30"}
        )
        self.assertEqual(rep.difficulty_level, DIFFICULTY_ROUTING_DISABLED)
        self.assertEqual(rep.complexity_score, 0.0)
        self.assertEqual(rep.to_dict()["difficulty_level"], DIFFICULTY_ROUTING_DISABLED)

    def test_09_explicit_modality_is_respected(self):
        """显式指定的接入方式必须被原样采用，不被任何自动逻辑改写。"""
        for mod in ("PYTHON_SDK", "FUNCTION_CALLING", "MCP", "CLI",
                    "REST_API", "DESKTOP_GUI", "AGENT_CHAIN"):
            plan = self.dispatcher.plan(
                AccessModality[mod],
                "我想制造一款精密成型轮模 材质Cr12MoV 外径53mm 轴孔14mm 宽度45mm"
            )
            self.assertEqual(plan.modality.value, mod)
            self.assertEqual(plan.modality, AccessModality[mod])

    def test_10_fallback_chain_is_static_and_present(self):
        """每个接入方式都有固定容灾链，且与难度无关。"""
        for modality, fallbacks in MODALITY_FALLBACKS.items():
            self.assertTrue(fallbacks, f"{modality.value} 缺少容灾链")
            for fb in fallbacks:
                self.assertNotEqual(fb, modality,
                                    f"{modality.value} 的容灾链不应包含自身")
                self.assertIn(fb, AccessModality)

    def test_11_plan_reports_tool_and_action(self):
        """派发计划应给出目标软件、动作与标准工具名。"""
        plan = self.dispatcher.plan(
            AccessModality.FUNCTION_CALLING,
            "校验宏程序 #100=50\nM30",
            target_software="cimco",
        )
        self.assertEqual(plan.target_software, "cimco")
        self.assertEqual(plan.action, "validate_macro")
        self.assertEqual(plan.tool_name, "cadcam_cimco_validate")
        self.assertEqual(plan.to_dict()["difficulty_level"], DIFFICULTY_ROUTING_DISABLED)

    def test_12_explain_decision_mentions_no_difficulty(self):
        """决策说明应说明接入方式派发，且标明难度选路已停用。"""
        text = self.agent.explain_decision(
            "调用VERICUT批处理仿真",
            modality="FUNCTION_CALLING",
        )
        self.assertIn("FUNCTION_CALLING", text)
        self.assertIn("备选容灾链条", text)
        self.assertIn("已停用", text)
        self.assertNotIn("L1", text)
        self.assertNotIn("L2", text)
        self.assertNotIn("L3", text)


if __name__ == "__main__":
    unittest.main()
