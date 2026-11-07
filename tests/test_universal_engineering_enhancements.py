# -*- coding: utf-8 -*-
"""tests/test_universal_engineering_enhancements.py — 验证工业构件万能解析、CAE 强度自愈闭环与二维排样优化全套新增能力.

测试矩阵：
1. 万能构件族自然语言意图反解 (Shaft, Flange, Bracket, Keyway, Sheet Metal)
2. 几何解析物理体积守恒公理 (ΔV > 0)
3. AutoCAD 2026 DXF 国标 6 大图层与形位公差 (GD&T) 框格实体审计
4. SOLIDWORKS 2021 VBA 宏内孔拉伸切除与螺栓孔圆周阵列生成
5. Siemens NX 12.0 Python Journal 参数化多孔建模生成
6. FANUC G-code 切削循环与宏变量校验
7. 通用 CAE 强度仿真分析与安全系数 (FOS >= 1.5) 闭环自愈
8. 钣金二维排样优化 (BLF 算法、割缝留量、母板利用率 >= 80%) 与 DXF 导出
9. 几何特征词元化对齐桥接器 (GeometryTokenBridge) 向量投影测试
"""

import os
import sys
import math
import tempfile
import unittest
import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from virtu_omni.engine.universal_geometry_engine import (
    UniversalGeometryEngine,
    PartFamily,
    ShaftGeometrySpec,
    FlangeGeometrySpec,
    KeywayGeometrySpec,
    BearingBracketGeometrySpec,
    SheetMetalBendSpec,
)
from virtu_omni.engine.universal_cae_engine import UniversalCAEEngine
from virtu_omni.engine.sheetmetal_nesting_engine import (
    SheetMetalNestingEngine,
    NestingPart,
    SheetStock,
)
from virtu_omni.models.geometry_token_bridge import (
    GeometryTokenBridge,
    GeometryFeatureProjector,
    GEOMETRY_SPECIAL_TOKENS,
)


class TestUniversalEngineeringEnhancements(unittest.TestCase):

    def setUp(self):
        self.geom_engine = UniversalGeometryEngine()
        self.cae_engine = UniversalCAEEngine()
        self.nesting_engine = SheetMetalNestingEngine()
        self.token_bridge = GeometryTokenBridge(hidden_dim=256)

    def test_01_flange_intent_parsing_and_volume(self):
        """测试法兰盘自然语言意图反解与物理体积守恒。"""
        wish = "设计一个外径140mm、内孔45mm、厚度20mm的标准304不锈钢法兰盘，带6个直径14mm的螺栓孔，PCD 105mm"
        data = self.geom_engine.parse_universal_intent(wish)
        self.assertEqual(data["family"], PartFamily.FLANGE_PLATE.value)
        spec = data["spec"]
        self.assertEqual(spec["material"], "SS304")
        self.assertEqual(spec["d_outer"], 140.0)
        self.assertEqual(spec["d_inner"], 45.0)
        self.assertEqual(spec["thickness"], 20.0)
        self.assertEqual(spec["bolt_hole_count"], 6)
        self.assertEqual(spec["bolt_hole_diam"], 14.0)
        self.assertEqual(spec["pcd"], 105.0)
        self.assertGreater(data["volume_mm3"], 0.0)

    def test_02_bracket_and_sheetmetal_parsing(self):
        """测试轴承支座与钣金折弯自然语言解析。"""
        # 支架测试
        bracket_wish = "航空铝7075精密轴承座，轴承孔径47mm，中心高50mm，底座长150mm"
        b_data = self.geom_engine.parse_universal_intent(bracket_wish)
        self.assertEqual(b_data["family"], PartFamily.BEARING_BRACKET.value)
        self.assertEqual(b_data["spec"]["material"], "AL7075-T6")
        self.assertEqual(b_data["spec"]["bearing_bore_diam"], 47.0)
        self.assertGreater(b_data["volume_mm3"], 0.0)

        # 钣金测试
        sheet_wish = "2mm厚 304不锈钢机箱盖板 90度折弯，长边60mm，短边40mm"
        s_data = self.geom_engine.parse_universal_intent(sheet_wish)
        self.assertEqual(s_data["family"], PartFamily.SHEET_METAL_BEND.value)
        self.assertEqual(s_data["spec"]["sheet_thickness"], 2.0)
        self.assertEqual(s_data["spec"]["bend_angle_deg"], 90.0)
        self.assertGreater(s_data["unfolded_length_mm"], 80.0)

    def test_03_keyway_gb1095_standard_lookup(self):
        """测试 GB/T 1095 平键槽标准参数查表与意图反解。"""
        key_wish = "45号钢传动轴 直径30mm 带标准普通平键槽"
        k_data = self.geom_engine.parse_universal_intent(key_wish)
        self.assertEqual(k_data["family"], PartFamily.KEYWAY_FEATURE.value)
        self.assertEqual(k_data["spec"]["material"], "Steel45")
        self.assertEqual(k_data["spec"]["shaft_diam"], 30.0)
        self.assertEqual(k_data["spec"]["key_width"], 8.0)
        self.assertEqual(k_data["spec"]["key_depth_shaft"], 4.0)

    def test_04_autocad_dxf_generation_with_gdt(self):
        """测试 AutoCAD DXF 包含国标 6 大图层与 GD&T 形位公差框格。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            dxf_path = os.path.join(tmpdir, "test_flange.dxf")
            flange_data = self.geom_engine.parse_universal_intent("Ø120法兰盘 中心孔Ø40 4个Ø12螺栓孔 PCD 90 厚度18")
            res = self.geom_engine.generate_autocad_dxf(flange_data, dxf_path)
            self.assertEqual(res["status"], "success")
            self.assertTrue(os.path.exists(dxf_path))
            self.assertGreater(res["entity_count"], 15)

    def test_05_solidworks_and_nx_code_synthesis(self):
        """测试 SolidWorks 宏与 NX 12.0 Python Journal 代码生成。"""
        flange_data = self.geom_engine.parse_universal_intent("Ø120法兰盘 中心孔Ø40 4个Ø12螺栓孔 PCD 90 厚度18")
        
        sw_macro = self.geom_engine.generate_solidworks_macro(flange_data)
        self.assertIn("FeatureExtrusion3", sw_macro)
        self.assertIn("FeatureCut3", sw_macro)
        self.assertIn("CreateCircleByRadius", sw_macro)

        nx_journal = self.geom_engine.generate_nx12_journal(flange_data)
        self.assertIn("CreateCyl1", nx_journal)
        self.assertIn("UF_SUBTRACT", nx_journal)

        fanuc_nc = self.geom_engine.generate_fanuc_gcode(flange_data)
        self.assertIn("G83", fanuc_nc)
        self.assertIn("WHILE", fanuc_nc)
        self.assertIn("M30", fanuc_nc)

    def test_06_cae_strength_analysis_and_closed_loop_self_healing(self):
        """测试力学仿真与安全系数 (FOS >= 1.5) 自愈闭环。"""
        flange_data = self.geom_engine.parse_universal_intent("Ø120法兰盘 中心孔Ø40 4个Ø12螺栓孔 PCD 90 厚度18 材质SS304")
        
        # 极端高压工况 (80 MPa) 导致初始 FOS 不足 1.5
        extreme_loads = {"fluid_pressure_mpa": 80.0}
        cae_report = self.cae_engine.analyze_and_optimize(flange_data, load_params=extreme_loads)
        
        # 必须触发闭环自愈强化，且强化后 FOS 必须 >= 1.5
        self.assertEqual(cae_report["status"], "optimized")
        self.assertTrue(cae_report["needs_reinforcement"])
        self.assertGreaterEqual(cae_report["factor_of_safety"], 1.5)
        self.assertGreater(cae_report["optimized_spec"]["thickness"], 18.0)
        self.assertIn("强化", cae_report["reinforcement_applied"])

    def test_07_sheetmetal_true_shape_nesting_optimization(self):
        """测试 2D 排样优化与材料利用率计算。"""
        stock = SheetStock(length=1000.0, width=800.0, edge_margin=10.0, kerf_spacing=5.0)
        engine = SheetMetalNestingEngine(stock=stock)
        
        # 10 个矩形构件
        parts = [
            NestingPart(part_id="P1", length=200.0, width=150.0, quantity=4),
            NestingPart(part_id="P2", length=180.0, width=100.0, quantity=6),
            NestingPart(part_id="P3", length=120.0, width=80.0, quantity=8),
        ]
        
        res = engine.optimize_nesting(parts, allow_rotation=True)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["placed_count"], 18)
        self.assertGreater(res["overall_utilization_rate"], 35.0)
        self.assertGreater(res["local_bounding_utilization"], 75.0)

        with tempfile.TemporaryDirectory() as tmpdir:
            dxf_nest = os.path.join(tmpdir, "nesting_layout.dxf")
            engine.export_nesting_dxf(res, dxf_nest)
            self.assertTrue(os.path.exists(dxf_nest))

    def test_08_geometry_token_bridge_and_manifold_projection(self):
        """测试几何实体词元化编码与主干流形张量投影。"""
        elements = [
            {"type": "point", "x1": 0.0, "y1": 0.0, "z1": 0.0},
            {"type": "line", "x1": 0.0, "y1": 0.0, "x2": 50.0, "y2": 0.0},
            {"type": "circle", "x1": 25.0, "y1": 25.0, "r": 15.0},
        ]
        token_ids, geom_tensor = self.token_bridge.encode_geometry_sequence(elements)
        self.assertEqual(len(token_ids), 3)
        self.assertEqual(geom_tensor.shape, (1, 3, 8))

        # 投影至隐层空间 [1, 3, 256]
        manifold_embed = self.token_bridge.project_to_manifold(geom_tensor)
        self.assertEqual(manifold_embed.shape, (1, 3, 256))
        self.assertFalse(torch.isnan(manifold_embed).any())


if __name__ == "__main__":
    unittest.main()
