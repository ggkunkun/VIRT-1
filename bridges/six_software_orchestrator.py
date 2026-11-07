# -*- coding: utf-8 -*-
"""bridges/six_software_orchestrator.py — Unified Six-Software Industrial Orchestrator.

Integrates the 6 core industrial applications into a single unified API:
1. SOLIDWORKS 2021 (Parametric FeatureTree & EquationMgr)
2. Siemens NX 12.0 (NXOpen Python & ExpressionCollection)
3. AutoCAD 2026 (ActiveX COM, AutoLISP & ezdxf)
4. VERICUT 9.6 (Batch G-code simulation & Collision Detection)
5. CIMCO Edit 2026 (FANUC Macro B Validation & G-code transmission)
6. 斯沃数控仿真软件 SSCNC 7.2 (WCS G54 & Tool Offset quadrant calculation)
"""

import os
import sys
import json
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from bridges.software_registry import (
    SOFTWARE_SPECS,
    normalize_software_key,
    get_software_health,
    diagnose_all,
)
from bridges.solidworks_bridge import SolidWorksBridge
from bridges.nx_bridge import SiemensNXBridge
from bridges.autocad_bridge import AutoCADBridge
from bridges.vericut_bridge import VericutBridge
from bridges.cimco_bridge import CIMCOBridge
from bridges.sscnc_bridge import SSCNCBridge


class SixSoftwareOrchestrator:
    def __init__(self):
        self.sw = SolidWorksBridge()
        self.nx = SiemensNXBridge()
        self.cad = AutoCADBridge()
        self.vericut = VericutBridge()
        self.cimco = CIMCOBridge()
        self.sscnc = SSCNCBridge()

    def preflight(self) -> dict:
        """Perform system preflight health diagnostic on all 6 industrial tools."""
        return diagnose_all()

    def dispatch(self, software_name: str, action: str, params: dict = None) -> dict:
        """Route request to appropriate software bridge or orchestration pipeline."""
        params = params or {}
        s_norm = normalize_software_key(software_name)
        act = (action or "").strip().lower()

        # Global system queries
        if s_norm in ("all", "preflight", "system") or act == "preflight":
            return self.preflight()

        # Extreme Speed & Quality Pipeline with Circuit Breaker
        if s_norm in ("extreme", "extreme_chain", "fast_chain") or "extreme" in act:
            return self.run_extreme_chain(
                wish=params.get("wish") or params.get("prompt") or "精密轴承套圈外圆加工",
                out_root=params.get("out_root"),
                max_attempts=int(params.get("max_attempts", 3)),
                tier2_native=bool(params.get("tier2_native", False))
            )

        # Full manufacturing chain
        if s_norm in ("chain", "full_chain", "pipeline") or "chain" in act:
            return self.run_full_chain(
                wish=params.get("wish") or params.get("prompt") or "精密轴承套圈外圆加工",
                out_root=params.get("out_root"),
                skip=params.get("skip", ()),
            )

        # 1. SolidWorks 2021
        if s_norm == "solidworks":
            if act in ("execute_vba", "vba"):
                return self.sw.execute_vba_code(params.get("code", ""))
            elif act in ("model_flange", "flange") or "flange" in params.get("part_name", "").lower():
                return self.sw.model_flange(
                    dimensions=params.get("dimensions", {}),
                    out_path=params.get("out_path")
                )
            elif act in ("create_parametric_part", "create_part", "model"):
                return self.sw.create_parametric_part(
                    params.get("part_name", "part"),
                    params.get("dimensions", {}),
                    params.get("features", [])
                )
            elif act in ("connect", "ping"):
                return self.sw.connect()
            elif act in ("health", "status"):
                return get_software_health("solidworks")

        # 2. Siemens NX 12.0
        elif s_norm == "nx":
            if act in ("run_journal", "journal"):
                return self.nx.run_python_journal(
                    params.get("script_path", ""),
                    params.get("args")
                )
            elif act in ("create_parametric_model", "generate_script", "model"):
                return self.nx.generate_parametric_nx_model(
                    params.get("part_name", "nx_part"),
                    params.get("expressions", {})
                )
            elif act in ("health", "status"):
                return get_software_health("nx")

        # 3. AutoCAD 2026
        elif s_norm == "autocad":
            if act in ("send_lisp", "lisp"):
                return self.cad.send_lisp_command(params.get("code", ""))
            elif act in ("run_headless_script", "run_script", "accoreconsole"):
                return self.cad.run_headless_script(
                    params.get("script_path", ""),
                    params.get("dwg_path")
                )
            elif act in ("create_dxf", "dxf"):
                return self.cad.create_headless_dxf(
                    params.get("drawing_name", "drawing"),
                    params.get("entities", []),
                    params.get("output_path")
                )
            elif act in ("connect", "ping"):
                return self.cad.connect()
            elif act in ("health", "status"):
                return get_software_health("autocad")

        # 4. VERICUT 9.6
        elif s_norm == "vericut":
            if act in ("run_simulation", "simulate"):
                return self.vericut.run_batch_simulation(
                    params.get("project_path", ""),
                    params.get("log_output_path")
                )
            elif act in ("check_collision", "parse_log"):
                return self.vericut.parse_collision_log(params.get("log_path", ""))
            elif act in ("health", "status"):
                return get_software_health("vericut")

        # 5. CIMCO Edit 2026
        elif s_norm == "cimco":
            if act in ("validate_macro", "validate"):
                return self.cimco.validate_fanuc_macro_b(params.get("code", ""))
            elif act in ("launch", "open"):
                return self.cimco.launch_in_cimco(params.get("nc_file_path", ""))
            elif act in ("health", "status"):
                return get_software_health("cimco")

        # 6. SSCNC (斯沃数控仿真 7.2)
        elif s_norm == "sscnc":
            if act in ("launch", "boot"):
                return self.sscnc.launch()
            elif act in ("find_window", "window"):
                return self.sscnc.find_window()
            elif act in ("calculate_offsets", "offsets"):
                return self.sscnc.calculate_tool_offsets(params.get("tools", []))
            elif act in ("health", "status"):
                return get_software_health("sscnc")

        # 7. Universal Geometry Engine
        elif s_norm in ("geometry", "universal_geometry", "universal_cad"):
            return self.universal_geometry(
                wish=params.get("wish", ""),
                part_type=params.get("part_type", "auto"),
                output_dir=params.get("output_dir"),
            )

        # 8. Universal CAE Stress Engine
        elif s_norm in ("cae", "stress", "cae_stress"):
            return self.cae_stress_analysis(
                spec=params.get("spec", {}),
                material=params.get("material", "45号钢"),
                pressure_mpa=float(params.get("pressure_mpa", 0.0)),
                force_n=float(params.get("force_n", 0.0)),
                torque_nm=float(params.get("torque_nm", 0.0)),
                target_fos=float(params.get("target_fos", 1.5)),
            )

        # 9. 2D True-Shape Nesting Engine
        elif s_norm in ("nest", "nesting", "sheetmetal_nest"):
            return self.sheetmetal_nest(
                parts=params.get("parts", []),
                sheet_width=float(params.get("sheet_width", 1000.0)),
                sheet_height=float(params.get("sheet_height", 1000.0)),
                margin=float(params.get("margin", 5.0)),
                output_dxf=params.get("output_dxf"),
            )

        # 10. STEP Reverse Engineering & Parametric Rebuild Engine
        elif s_norm in ("step_reverse", "reverse", "reverse_engineering", "cadcam_step_reverse"):
            return self.step_reverse(
                step_path=params.get("step_path") or params.get("file_path") or params.get("path", ""),
                action=params.get("action", act or "analyze"),
                out_sldprt_path=params.get("out_sldprt_path") or params.get("output_path"),
            )

        return {
            "status": "error",
            "message": f"Unknown software [{software_name}] (normalized: {s_norm}) or action [{action}].",
            "supported_software": list(SOFTWARE_SPECS.keys()) + ["full_chain", "universal_geometry", "cae_stress", "sheetmetal_nest", "step_reverse"],
        }

    def run_extreme_chain(self, wish: str, out_root: str = None, max_attempts: int = 3, tier2_native: bool = False) -> dict:
        """Run extreme-speed closed-loop CAD/CAE/CAM lifecycle with circuit breaker.
        
        Axiom: “又快又准到极限，未到极限则继续，到了极限则放弃”
        """
        try:
            from virtu_omni.engine.extreme_cadcam_pipeline import ExtremeCADCAMPipeline
            pipeline = ExtremeCADCAMPipeline()
            res = pipeline.run_full_lifecycle(wish, out_root=out_root, max_attempts=max_attempts)
            if res.get("status") == "success" and tier2_native:
                # Optionally run Tier 2 desktop execution
                chain_res = self.run_full_chain(wish, out_root=out_root)
                res["tier2_native_execution"] = chain_res
            return res
        except Exception as e:
            import traceback
            return {
                "status": "error",
                "message": f"Failed to execute extreme chain: {e}",
                "trace": traceback.format_exc(),
            }

    def run_full_chain(self, wish: str, out_root: str = None, skip: tuple = ()) -> dict:
        """Run complete 6-software manufacturing pipeline via agent_chain_executor."""
        try:
            import agent_chain_executor as chain_exec
            bundle = chain_exec.run_chain(wish, out_root=out_root, skip=skip)
            return {
                "status": "success",
                "run_id": bundle.get("run_id"),
                "out_dir": bundle.get("out_dir"),
                "verdicts": bundle.get("verdicts"),
                "executed_count": bundle.get("executed_count"),
                "report_md": bundle.get("report"),
                "stages": {
                    k: {
                        "status": v.get("status"),
                        "method": v.get("method"),
                        "metrics": v.get("metrics"),
                        "files": v.get("files"),
                        "error": v.get("error"),
                    }
                    for k, v in bundle.get("stages", {}).items()
                },
            }
        except Exception as e:
            import traceback
            return {
                "status": "error",
                "message": f"Failed to execute chain: {e}",
                "trace": traceback.format_exc(),
            }

    def universal_geometry(self, wish: str, part_type: str = "auto", output_dir: str = None) -> dict:
        """Parse natural language CAD requirement and generate multi-platform artifacts."""
        try:
            from virtu_omni.engine.universal_geometry_engine import UniversalGeometryEngine
            engine = UniversalGeometryEngine()
            intent_data = engine.parse_universal_intent(wish)

            output_dir = output_dir or os.path.join(_ROOT, "runs", "universal_cad")
            os.makedirs(output_dir, exist_ok=True)

            spec = intent_data.get("spec", {})
            part_name = spec.get("part_name", "Component")
            dxf_path = os.path.join(output_dir, f"{part_name}.dxf")
            dxf_res = engine.generate_autocad_dxf(intent_data, dxf_path)

            sw_macro = engine.generate_solidworks_macro(intent_data)
            sw_path = os.path.join(output_dir, f"{part_name}_sw.vba")
            with open(sw_path, "w", encoding="utf-8") as f:
                f.write(sw_macro)

            nx_journal = engine.generate_nx12_journal(intent_data)
            nx_path = os.path.join(output_dir, f"{part_name}_nx.py")
            with open(nx_path, "w", encoding="utf-8") as f:
                f.write(nx_journal)

            gcode = engine.generate_fanuc_gcode(intent_data)
            nc_path = os.path.join(output_dir, f"{part_name}.nc")
            with open(nc_path, "w", encoding="utf-8") as f:
                f.write(gcode)

            return {
                "status": "success",
                "part_family": intent_data.get("family"),
                "part_name": part_name,
                "material": spec.get("material", "Cr12MoV"),
                "spec": spec,
                "volume_mm3": intent_data.get("volume_mm3", 0.0),
                "artifacts": {
                    "dxf_path": dxf_path,
                    "sw_vba_path": sw_path,
                    "nx_journal_path": nx_path,
                    "gcode_path": nc_path,
                    "dxf_info": dxf_res,
                }
            }
        except Exception as e:
            import traceback
            return {
                "status": "error",
                "message": f"Universal geometry generation failed: {e}",
                "trace": traceback.format_exc(),
            }

    def cae_stress_analysis(self, spec: dict, material: str = "45号钢", pressure_mpa: float = 0.0,
                            force_n: float = 0.0, torque_nm: float = 0.0, target_fos: float = 1.5) -> dict:
        """Perform analytical stress verification and closed-loop geometry self-healing."""
        try:
            from virtu_omni.engine.universal_cae_engine import UniversalCAEEngine
            from virtu_omni.engine.universal_geometry_engine import PartFamily
            cae = UniversalCAEEngine()
            loads = {}
            if pressure_mpa > 0:
                loads["internal_pressure_mpa"] = pressure_mpa
                loads["fluid_pressure_mpa"] = pressure_mpa
            if force_n > 0:
                loads["load_n"] = force_n
                loads["moment_arm_mm"] = 100.0
            if torque_nm > 0:
                loads["torque_nm"] = torque_nm

            family = spec.get("family", spec.get("part_family", PartFamily.ROTATIONAL_SHAFT.value))
            intent_data = {
                "family": family,
                "spec": dict(spec),
            }
            if material:
                intent_data["spec"]["material"] = material

            res = cae.analyze_and_optimize(intent_data=intent_data, load_params=loads)
            return {
                "status": "success",
                "cae_result": res,
            }
        except Exception as e:
            import traceback
            return {
                "status": "error",
                "message": f"CAE stress analysis failed: {e}",
                "trace": traceback.format_exc(),
            }

    def sheetmetal_nest(self, parts: list, sheet_width: float = 1000.0, sheet_height: float = 1000.0,
                        margin: float = 5.0, output_dxf: str = None) -> dict:
        """Perform 2D True-Shape Nesting optimization and generate DXF layout."""
        try:
            from virtu_omni.engine.sheetmetal_nesting_engine import SheetMetalNestingEngine, SheetStock, NestingPart
            stock = SheetStock(
                length=sheet_width,
                width=sheet_height,
                edge_margin=margin,
                kerf_spacing=margin,
            )
            nest_parts = []
            for p in parts:
                nest_parts.append(NestingPart(
                    part_id=str(p.get("name", p.get("part_id", "part"))),
                    length=float(p.get("width", p.get("length", 50.0))),
                    width=float(p.get("height", p.get("width", 50.0))),
                    quantity=int(p.get("quantity", 1)),
                ))
            engine = SheetMetalNestingEngine(stock=stock)
            layout = engine.optimize_nesting(nest_parts, allow_rotation=True)
            dxf_path = output_dxf
            if dxf_path and layout.get("status") in ("success", "partial"):
                engine.export_nesting_dxf(layout, dxf_path)
            return {
                "status": "success",
                "layout": layout,
                "dxf_path": dxf_path,
            }
        except Exception as e:
            import traceback
            return {
                "status": "error",
                "message": f"Sheet metal nesting failed: {e}",
                "trace": traceback.format_exc(),
            }

    def step_reverse(self, step_path: str, action: str = "analyze", out_sldprt_path: str = None) -> dict:
        """Execute STEP Reverse Engineering, feature extraction, and SolidWorks rebuild."""
        try:
            from virtu_omni.engine.step_reverse_engine import StepReverseEngine
            engine = StepReverseEngine()
            if not step_path or not os.path.exists(step_path):
                return {
                    "status": "error",
                    "error": f"STEP file does not exist or invalid path: {step_path}"
                }

            act = (action or "analyze").lower()

            # P0 解法：STEP→结构化 BOM（理解装配体首选）。
            # 独立于几何逆向引擎，避免大文件或异常几何拖垮结构解析；
            # 返回 prompt_context 可直接注入 13.63B 领域模型。
            if act in ("bom", "assembly_tree", "structure"):
                from bridges.step_bom import StepBOM
                bom = StepBOM(step_path)
                return {
                    "status": "success",
                    "tool": "cadcam_step_reverse",
                    "action": "bom",
                    "step_file": step_path,
                    "ap_version": bom.ap_version,
                    "encoding": bom.encoding,
                    "is_assembly": len(bom.nauo) > 0,
                    "bom": bom.to_dict(),
                    "dsl": bom.to_dsl(),
                    "prompt_context": bom.to_prompt_context(),
                }

            analysis = engine.analyze_step(step_path)

            if act in ("analyze", "inspect", "extract"):
                return {
                    "status": "success",
                    "step_file": step_path,
                    "part_family": analysis.part_family,
                    "bounding_box": analysis.bounding_box,
                    "cylindrical_diameters": analysis.cylindrical_diameters,
                    "toroidal_grooves": analysis.toroidal_grooves,
                    "conical_half_angles": analysis.conical_half_angles,
                    "hole_patterns": analysis.hole_patterns,
                    "revolved_profile": analysis.revolved_profile,
                    "key_dimensions": analysis.key_dimensions,
                    "theoretical_volume_mm3": analysis.theoretical_volume_mm3,
                    "vba_code_preview": analysis.reconstruction_vba[:500] + "...",
                }

            elif act in ("reconstruct_vba", "vba", "generate_vba"):
                return {
                    "status": "success",
                    "step_file": step_path,
                    "part_family": analysis.part_family,
                    "vba_code": analysis.reconstruction_vba,
                    "key_dimensions": analysis.key_dimensions,
                    "theoretical_volume_mm3": analysis.theoretical_volume_mm3,
                }

            elif act in ("build_solidworks", "build", "solidworks", "full_reverse"):
                if not out_sldprt_path:
                    base_name = os.path.splitext(os.path.basename(step_path))[0]
                    out_sldprt_path = os.path.join(self.sw.workspace_root, f"{base_name}_reversed.SLDPRT")

                res = engine.execute_solidworks_rebuild(analysis, out_sldprt_path)
                res["step_file"] = step_path
                res["part_family"] = analysis.part_family
                res["vba_code"] = analysis.reconstruction_vba
                return res

            return {
                "status": "error",
                "error": f"Unknown step_reverse action: {action}"
            }
        except Exception as e:
            import traceback
            return {
                "status": "error",
                "error": f"STEP reverse execution error: {type(e).__name__}: {str(e)}",
                "trace": traceback.format_exc()
            }


if __name__ == "__main__":
    orch = SixSoftwareOrchestrator()
    print("Testing Preflight...")
    pf = orch.preflight()
    print(f"Preflight: {pf['ready_count']}/{pf['total_software']} Ready")
    print("Dispatch CIMCO validation:", orch.dispatch("cimco", "validate_macro", {"code": "#100=10\nM30"}))
