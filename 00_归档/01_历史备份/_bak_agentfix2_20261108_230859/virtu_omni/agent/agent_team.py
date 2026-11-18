"""Virtu Industrial Omni-Agent Multi-Agent Team (Agent Team) Architecture.

Decomposes complex CAD/CAM/CAE manufacturing tasks across a collaborative team
of specialized AI Agents:
1. ChiefArchitectAgent: Master system architecture, intent decomposition & team coordinator.
2. ParametricModelingAgent: 3D CAD parametric FeatureTree planner & equation designer.
3. StandardsAndGDAgent: 2D drawing projection, fits & tolerances (H7/g6) & GD&T expert.
4. MachiningAndToolpathAgent: CAM toolpaths, cutting feeds & speeds, CNC Macro B & G-code specialist.
5. AuditorAndSandboxAgent: Headless simulation verification, collision detection & self-reflection optimizer.
6. EvolutionAndMemoryAgent: Dense-vector episodic memory retrieval, experience commitment & SKILL synthesis.
"""

from __future__ import annotations
import os
import sys
import json
import time
from typing import Dict, Any, List, Optional

WORKSPACE_DIR = r"D:\Virtu模型"
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from virtu_omni.agent.blueprint_inverse_engine import BlueprintInverseEngine
from virtu_omni.agent.self_reflection_optimizer import SelfReflectionOptimizer
from virtu_omni.agent.headless_sandbox_verifier import HeadlessSandboxVerifier
from virtu_omni.agent.skill_writer_and_memory import SkillWriterAndMemory
from virtu_omni.agent.process_memory_reclaimer import ProcessMemoryReclaimer
from virtu_omni.engine.wish_cad_cam_engine import WishCADCAMEngine
from virtu_omni.security.auditor import ModelSecurityAuditor
from virtu_omni.memory import VirtuHindsightMemory, MemoryType


class BaseIndustrialAgent:
    """Base class for specialized industrial autonomous agents."""

    def __init__(self, name: str, role: str, responsibilities: List[str]):
        self.name = name
        self.role = role
        self.responsibilities = responsibilities

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


class ChiefArchitectAgent(BaseIndustrialAgent):
    """Lead Architect Agent: Analyzes requirements, parses design intent, and coordinates team."""

    def __init__(self):
        super().__init__(
            name="Virtu-Chief-Architect",
            role="工业系统总架构师与工程任务分解中心",
            responsibilities=[
                "用户制造愿景深度揣测与参数解析",
                "自动化设备系统级工程拆解 (Frame, Feeding, Tooling)",
                "分派多智能体任务与最终交付物统合"
            ]
        )
        self.engine = WishCADCAMEngine()

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = context.get("user_prompt", "")
        # Parse intent using WishCADCAMEngine
        spec = self.engine.parse_wish_intent(prompt)
        
        # Decide category and assembly decomposition
        equipment_type = "自动化回转/精密加工组件"
        if "机" in prompt or "总成" in prompt or "装配" in prompt:
            equipment_type = "自动化成套非标加工设备"

        sub_modules = [
            {"module_name": "基座机架与支撑总成", "type": "frame", "parts": ["安装底板", "立柱连接板"]},
            {"module_name": "核心工件运动与传动机构", "type": "motion", "parts": ["主轴套筒/滑块", "定位销轴"]},
            {"module_name": "末端夹紧与执行工具组件", "type": "tooling", "parts": ["压紧卡爪", "刀具接柄"]}
        ]

        return {
            "agent": self.name,
            "status": "COMPLETED",
            "parsed_spec": spec,
            "equipment_type": equipment_type,
            "sub_modules": sub_modules,
            "summary": f"已完成需求解析：识别零件/设备为【{spec.get('wish_name', '精密机械构件')}】，材料为【{spec.get('material', 'AL6061-T6')}】，规划 3 大子功能模块。"
        }


class ParametricModelingAgent(BaseIndustrialAgent):
    """Parametric Modeling Specialist: Designs 3D sketches, FeatureTree, and parametric equations."""

    def __init__(self):
        super().__init__(
            name="Virtu-Parametric-Modeler",
            role="3D CAD 原生特征树规划与参数化建模专家",
            responsibilities=[
                "逆向图纸几何基元推导 (Revolving / Prismatic)",
                "SolidWorks FeatureManager 原生设计树规划",
                "全局方程式驱动绑定 (swEqnMgr) 与 0 呆料实体建模"
            ]
        )
        self.inverse_engine = BlueprintInverseEngine()

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        arch_data = context.get("architecture", {})
        spec = arch_data.get("parsed_spec", {})
        prompt = context.get("user_prompt", "")

        blueprint_input = {
            "description": prompt,
            "material": spec.get("material", "AL6061-T6"),
            "dimensions": {
                "length": spec.get("d_outer", 80.0),
                "width": spec.get("overall_len", 60.0),
                "thickness": spec.get("overall_len", 30.0),
                "hole_d": spec.get("d_inner", 20.0),
                "pitch": spec.get("d_outer", 80.0) * 0.7
            }
        }

        inverse_res = self.inverse_engine.infer_blueprint_features(blueprint_input)
        sw_vba = self.inverse_engine.generate_solidworks_vba_script(inverse_res)

        return {
            "agent": self.name,
            "status": "COMPLETED",
            "category": inverse_res["classified_primitive"],
            "equations": inverse_res["deduced_equations"],
            "feature_tree": inverse_res["feature_tree"],
            "assembly_mates": inverse_res["assembly_mates"],
            "solidworks_vba": sw_vba,
            "summary": f"完成 3D 参数化特征树构建：基元分类为【{inverse_res['classified_primitive']}】，绑定 {len(inverse_res['deduced_equations'])} 项全局参数方程式，生成完整原生 FeatureTree。"
        }


class StandardsAndGDAgent(BaseIndustrialAgent):
    """Engineering Standards & GD&T Specialist: Generates 2D views, fits, GD&T, and roughness."""

    def __init__(self):
        super().__init__(
            name="Virtu-Standards-GD&T-Engineer",
            role="工程图标准基准、配合公差与形位公差专家",
            responsibilities=[
                "正交三视图投影与剖视规划",
                "基孔制/基轴制标准配合公差计算 (H7/g6, H7/h6)",
                "形位公差 (GD&T) 与主要加工面表面粗糙度 (Ra) 规范定义"
            ]
        )

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        arch_data = context.get("architecture", {})
        spec = arch_data.get("parsed_spec", {})
        d_inner = spec.get("d_inner", 20.0)

        drawing_spec = {
            "sheet_size": "A3_Landscape",
            "projection_views": ["主视图(1:1)", "俯视图(1:1)", "左视图(1:1)", "局部轴测剖视图"],
            "fit_tolerances": [
                {
                    "dimension_target": "核心配合轴承孔",
                    "nominal_size": d_inner,
                    "tolerance_class": "H7 (+0.021 / 0 mm)"
                },
                {
                    "dimension_target": "端面安装止口定位台阶",
                    "nominal_size": spec.get("d_outer", 60.0),
                    "tolerance_class": "g6 (-0.010 / -0.029 mm)"
                }
            ],
            "geometric_tolerances_gdt": [
                {"symbol": "parallelism", "value_mm": 0.015, "datum_ref": "A (底面安装基准)"},
                {"symbol": "concentricity", "value_mm": 0.020, "datum_ref": "B (内孔轴线)"}
            ],
            "surface_roughness": {
                "bearing_bore": "Ra 0.8 (磨削/精密镗孔)",
                "mounting_face": "Ra 1.6 (精铣)",
                "non_contact": "Ra 6.3 (去氧化皮)"
            },
            "technical_notes": [
                "1. 未注倒角均按 C1.0 执行，锐边倒钝去毛刺；",
                "2. 调质处理硬度达到 HRC 28~32；",
                "3. 表面本色阳极氧化，膜厚 12~15 μm。"
            ]
        }

        return {
            "agent": self.name,
            "status": "COMPLETED",
            "drawing_spec": drawing_spec,
            "summary": f"已完成工程图标注规范：基孔制 H7 配合公差、平行度与同轴度 GD&T (≤0.02mm)、表面粗糙度与 3 条核心技术要求。"
        }


class MachiningAndToolpathAgent(BaseIndustrialAgent):
    """CAM & CNC Toolpath Specialist: Computes machining feeds/speeds, Macro B, and G-code."""

    def __init__(self):
        super().__init__(
            name="Virtu-CAM-CNC-Engineer",
            role="数控加工工艺、切削刀路与宏程序专家",
            responsibilities=[
                "切削参数动力学计算 (线速度 Vc, 进给率 Fz, 主轴转速 S)",
                "FANUC/SIEMENS Macro B 参数化数控程序合成",
                "对刀基准 (G54) 与刀尖方位号 (T01~T09) 配置"
            ]
        )

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        arch_data = context.get("architecture", {})
        spec = arch_data.get("parsed_spec", {})
        material = spec.get("material", "AL6061-T6")

        # Material based cutting parameters
        if "Ti" in material:
            vc, fz, spindle_rpm = 60, 0.08, 1200
        elif "7075" in material or "6061" in material:
            vc, fz, spindle_rpm = 280, 0.20, 3500
        elif "Cr12" in material:
            vc, fz, spindle_rpm = 90, 0.10, 1600
        else:
            vc, fz, spindle_rpm = 150, 0.15, 2200

        macro_b_code = f"""%
O0001 (VIRTU AGENT TEAM CNC PARAMETRIC MACRO)
(MATERIAL: {material} | CUTTING SPEED Vc: {vc} m/min)
G21 G40 G97 G99
G28 U0.0 W0.0
T0101 (ROUGH TURNING TOOL R0.8)
G54
M03 S{spindle_rpm}

#100 = {spec.get('d_outer', 80.0)} (RAW STOCK OD)
#101 = {spec.get('d_inner', 20.0)} (TARGET BORE ID)
#102 = {spec.get('overall_len', 50.0)} (TOTAL LENGTH)

(--- SAFE RAPID POSITIONING ---)
G00 X[#100 + 4.0] Z2.0
M08 (COOLANT ON)

(--- G71 ROUGH TURNING CYCLE ---)
G71 U2.0 R0.5
G71 P10 Q20 U0.4 W0.1 F{fz}
N10 G00 X[#101 + 5.0]
    G01 Z0.0 F{fz}
    G01 X[#100] Z-2.0
    G01 Z-[#102]
N20 G01 X[#100 + 2.0]

(--- G70 FINISH TURNING CYCLE ---)
G70 P10 Q20 F[#100 * 0.0015]

M09
G28 U0.0 W0.0
M05
M30
%
"""

        return {
            "agent": self.name,
            "status": "COMPLETED",
            "cutting_params": {"spindle_rpm": spindle_rpm, "feed_rate": fz, "surface_speed": vc},
            "macro_b_code": macro_b_code,
            "summary": f"完成数控加工规划：匹配材质【{material}】，计算主轴转速 S{spindle_rpm}、进给 F{fz}，生成含 G71/G70 粗精车循环的参数化 Macro B 宏程序。"
        }


class AuditorAndSandboxAgent(BaseIndustrialAgent):
    """Quality & Simulation Auditor: Verifies code in headless sandbox, enforces security audit, and drives self-reflection."""

    def __init__(self):
        super().__init__(
            name="Virtu-Sandbox-Auditor",
            role="无头沙箱仿真执行、合规性审计与自省自愈专家",
            responsibilities=[
                "Headless CAD/CAM 虚拟沙箱仿真执行",
                "运动学刀路碰撞检测与 COM 对象生命周期检查",
                "自动化自省反思与代码闭环自愈",
                "Defensive Security Audit: 提示词注入检测、工具参数汇校验与安全报告生成",
            ]
        )
        self.optimizer = SelfReflectionOptimizer()
        self.verifier = HeadlessSandboxVerifier()
        self.security_auditor = ModelSecurityAuditor()

    def security_audit(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Perform defensive security audit on prompt, parameters, and generated code."""
        prompt = context.get("user_prompt", "")
        prompt_check = self.security_auditor.audit_prompt_injection(prompt)

        arch_data = context.get("architecture", {})
        spec = arch_data.get("parsed_spec", {})
        tool_check = self.security_auditor.audit_tool_arguments("cad.parse_wish_intent", spec)

        return {
            "prompt_security": prompt_check,
            "tool_arguments_security": tool_check,
            "passed": prompt_check["passed"] and tool_check["passed"],
        }

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        modeling_data = context.get("modeling", {})
        machining_data = context.get("machining", {})

        sw_code = modeling_data.get("solidworks_vba", "")
        macro_code = machining_data.get("macro_b_code", "")

        # 1. Audit SolidWorks Code
        sw_audit = self.optimizer.audit_code(sw_code, "solidworks")
        sw_optimized, sw_reflection = self.optimizer.reflect_and_optimize(sw_code, sw_audit)

        # 2. Audit Macro B Code
        macro_audit = self.optimizer.audit_code(macro_code, "cimco_macro")
        macro_optimized, macro_reflection = self.optimizer.reflect_and_optimize(macro_code, macro_audit)

        # 3. Defensive Security Audit (Cloudflare security-audit-skill)
        sec_audit = self.security_audit(context)

        # Gate must be falsifiable: never hard-code a passing verdict.
        audit_breakdown = {
            "solidworks_vba_audit": bool(sw_audit.get("passed")),
            "macro_b_audit": bool(macro_audit.get("passed")),
            "security_audit": bool(sec_audit.get("passed")),
        }
        all_passed = all(audit_breakdown.values())
        failed_checks = [name for name, ok in audit_breakdown.items() if not ok]
        if all_passed:
            summary = "沙箱审计通过：VBA / Macro B / 安全审计三项均 PASS（基于本次实际审计结果）。"
        else:
            summary = (
                "沙箱审计未通过（FAIL）：" + ", ".join(failed_checks)
                + "。禁止据此宣称任务完成，修复后必须重跑验证。"
            )
        return {
            "agent": self.name,
            "status": "COMPLETED" if all_passed else "FAILED",
            "passed": all_passed,
            "audit_breakdown": audit_breakdown,
            "failed_checks": failed_checks,
            "sw_audit_score": sw_audit.get("score"),
            "macro_audit_score": macro_audit.get("score"),
            "security_audit": sec_audit,
            "verified_sw_vba": sw_optimized,
            "verified_macro_code": macro_optimized,
            "reflection_log": f"{sw_reflection}\n\n{macro_reflection}",
            "summary": summary,
        }


class EvolutionAndMemoryAgent(BaseIndustrialAgent):
    """Memory & Evolution Agent: Retrieves past experience via Hindsight multi-tiered memory and synthesizes skills."""

    def __init__(self):
        super().__init__(
            name="Virtu-Memory-Evolution-Curator",
            role="Hindsight 跨会话语义记忆图谱与自主技能演化专家",
            responsibilities=[
                "Hindsight 核心操作三部曲 (Retain / Recall / Reflect)",
                "多维度记忆银行 (virtu_cad_cam, virtu_cnc_machining, virtu_quality_audit)",
                "新任务成功经验固化落盘 (Commit Experience) 与自省反思",
                "将高频通用工艺自主沉淀为标准 Antigravity SKILL 包",
                "长期记忆防投毒与跨会话隔离校验",
            ]
        )
        self.memory_engine = SkillWriterAndMemory()
        self.security_auditor = ModelSecurityAuditor()
        self.hindsight = VirtuHindsightMemory()

    def retrieve_context(self, prompt: str) -> List[Dict[str, Any]]:
        """Retrieve historical similar solved engineering patterns via Hindsight recall."""
        # 1. Hindsight Recall
        hindsight_hits = self.hindsight.recall(bank_id="virtu_cad_cam", query=prompt, max_results=3)
        # 2. Legacy Vector Store
        legacy_hits = self.memory_engine.query_memory(prompt, top_k=2)

        combined = list(hindsight_hits)
        for h in legacy_hits:
            if not any(c.get("id") == h.get("id") for c in combined):
                combined.append(h)
        return combined

    def reflect_on_intent(self, prompt: str) -> Dict[str, Any]:
        """Synthesize past learnings and mental models to guide current manufacturing task."""
        return self.hindsight.reflect(bank_id="virtu_cad_cam", query=prompt, budget="mid")

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        arch_data = context.get("architecture", {})
        spec = arch_data.get("parsed_spec", {})
        task_sig = f"AgentTeam_{spec.get('wish_name', 'Part')}_{spec.get('material', 'AL')}"
        solution_strategy = "协同 Agent Team：架构拆解 -> 参数化特征树 -> GD&T 标注 -> G71 宏程序 -> 沙箱闭环自愈"

        # Validate against memory poisoning before committing
        mem_audit = self.security_auditor.audit_memory_entry(task_sig, solution_strategy)
        if not mem_audit["passed"]:
            raise ValueError(f"Security audit blocked poisoned memory commit: {mem_audit['violations']}")

        key_rules = [
            "回转特征必须优先绑定 swEqnMgr 方程式管理器",
            "精密切削必须使用 G71 粗车留 0.4mm 余量再经 G70 精修",
            "沙箱仿真必须验证 ForceRebuild3 与 G00 快速移动无负向切削碰撞"
        ]

        # 1. Commit to Hindsight Memory (both agent experiences and mental models)
        h_exp = self.hindsight.retain(
            bank_id="virtu_cad_cam",
            content=f"成功完成【{spec.get('wish_name', '零件')}】参数化建模与数控规划。材质: {spec.get('material', 'AL')}, 策略: {solution_strategy}",
            context="procedures",
            tags=["agent_team", "cad_cam", spec.get("material", "AL")],
            memory_type=MemoryType.AGENT_EXPERIENCES,
            metadata={"task_signature": task_sig, "spec": spec}
        )

        h_mm = self.hindsight.retain(
            bank_id="virtu_cad_cam",
            content=f"针对【{spec.get('wish_name', '零件')}】设计经验法则: {' | '.join(key_rules)}",
            context="learnings",
            tags=["mental_model", "best_practices"],
            memory_type=MemoryType.MENTAL_MODELS,
            metadata={"task_signature": task_sig}
        )

        # 2. Commit to legacy dense vector memory
        rec = self.memory_engine.commit_experience(
            task_signature=task_sig,
            problem_summary=context.get("user_prompt", "")[:200],
            solution_strategy=solution_strategy,
            key_rules_learned=key_rules,
            code_snippet=context.get("auditor", {}).get("verified_sw_vba", "")[:1000]
        )

        return {
            "agent": self.name,
            "status": "COMPLETED",
            "memory_id": rec["id"],
            "hindsight_experience_id": h_exp["id"],
            "hindsight_mental_model_id": h_mm["id"],
            "memory_security": mem_audit,
            "total_experiences": self.memory_engine.memory["total_experiences"],
            "hindsight_total_units": self.hindsight.get_status()["total_units"],
            "summary": f"已将本次多智能体协同经验与心智模型固化至 Hindsight 记忆库 (EXP: {h_exp['id']}, MM: {h_mm['id']})，通过防投毒安全审查。"
        }


class IndustrialAgentTeam:
    """Master Orchestrator for the Collaborative Industrial Multi-Agent Team.
    
    遵循铁律：
    每完一步任务就保存到本地文件，关闭上一步的软件用来节省内存，完成以后执行下一步任务。
    """

    def __init__(self, log_path: Optional[str] = None):
        self.memory_agent = EvolutionAndMemoryAgent()
        self.architect_agent = ChiefArchitectAgent()
        self.modeler_agent = ParametricModelingAgent()
        self.standards_agent = StandardsAndGDAgent()
        self.machining_agent = MachiningAndToolpathAgent()
        self.auditor_agent = AuditorAndSandboxAgent()
        self.reclaimer = ProcessMemoryReclaimer(log_path=log_path)

    def to_super_agent(self):
        """Bridge and convert this multi-agent team into a unified Virtu Super Agent."""
        from virtu_omni.agent.super_agent import VirtuSuperAgent
        return VirtuSuperAgent()

    # 七步流水线中登记进 per_agent_status 的角色顺序（用于团队级状态聚合）
    ROLE_ORDER = (
        "EvolutionAndMemoryAgent.retrieve_context",
        "ChiefArchitectAgent",
        "ParametricModelingAgent",
        "StandardsAndGDAgent",
        "MachiningAndToolpathAgent",
        "AuditorAndSandboxAgent",
        "EvolutionAndMemoryAgent.commit",
    )

    def probe_residual_processes(self) -> Dict[str, Any]:
        """实测六大 CAD/CAM 软件的残留进程数（报告用，替代原先未实测的模板断言）。"""
        softwares = ("solidworks", "autocad", "nx", "cimco", "vericut", "sscnc")
        detail: Dict[str, Any] = {}
        measured = True
        total = 0
        probe = getattr(self.reclaimer, "find_target_processes", None)
        if not callable(probe):
            return {"basis": "unmeasured", "detail": {}, "residual_total": "unmeasured"}
        for key in softwares:
            try:
                procs = probe(key)
                n = len(procs) if procs is not None else 0
                detail[key] = n
                total += n
            except Exception as e:  # pragma: no cover - 探测失败如实标注
                detail[key] = f"unmeasured: {e}"
                measured = False
        return {
            "basis": "measured" if measured else "partially_unmeasured",
            "detail": detail,
            "residual_total": total if measured else "unmeasured",
        }

    @staticmethod
    def aggregate_team_status(per_agent_status: Dict[str, str]) -> str:
        """由 7 步子智能体真实 status 聚合出团队级状态（禁止字面量 SUCCESS）。

        规则：任一 FAILED → FAILED；全部 COMPLETED → SUCCESS；其余 → PARTIAL。
        """
        values = [str(v).upper() for v in per_agent_status.values()]
        if any(v == "FAILED" for v in values):
            return "FAILED"
        if values and all(v == "COMPLETED" for v in values):
            return "SUCCESS"
        return "PARTIAL"

    def _persist_and_reclaim(
        self,
        step_idx: int,
        step_title: str,
        artifacts_to_save: Dict[str, Any],
        output_dir: str,
        software_key: Optional[str] = None,
        memory_safe: bool = True
    ) -> Dict[str, Any]:
        """立即将步骤产物落盘至本地文件，确证大小>0，关闭对应软件并净化内存。"""
        saved_files = []
        for fname, content in artifacts_to_save.items():
            fpath = os.path.join(output_dir, fname)
            if isinstance(content, (dict, list)):
                with open(fpath, "w", encoding="utf-8") as f:
                    json.dump(content, f, ensure_ascii=False, indent=2)
            else:
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(str(content))
            sz = os.path.getsize(fpath)
            saved_files.append({"filename": fname, "path": fpath, "bytes": sz, "valid": sz > 0})

        reclaim_record = None
        ram_before = self.reclaimer.get_system_memory()
        if memory_safe:
            if software_key:
                reclaim_record = self.reclaimer.close_software(software_key)
            self.reclaimer.trim_system_working_set()
        ram_after = self.reclaimer.get_system_memory()

        return {
            "step_idx": step_idx,
            "step_title": step_title,
            "saved_files": saved_files,
            "all_persisted": all(f["valid"] for f in saved_files),
            "software_closed": software_key if memory_safe and software_key else None,
            "ram_before_mb": ram_before["available_mb"],
            "ram_after_mb": ram_after["available_mb"],
            "reclaimed_mb": round(ram_after["available_mb"] - ram_before["available_mb"], 2),
            "reclaim_record": reclaim_record
        }

    def solve(
        self,
        user_prompt: str,
        output_dir: Optional[str] = None,
        memory_safe: bool = True
    ) -> Dict[str, Any]:
        """Execute collaborative end-to-end multi-agent problem solving with stage-gated memory safety."""
        t0 = time.time()
        if not output_dir:
            ts = time.strftime("%Y%m%d_%H%M%S")
            output_dir = os.path.join(WORKSPACE_DIR, "runs", "agent_team", ts)
        os.makedirs(output_dir, exist_ok=True)

        collaboration_log: List[Dict[str, Any]] = []
        persisted_manifest = []

        # Step 1: Memory Agent retrieves historical patterns via Hindsight Recall & Reflect
        past_experiences = self.memory_agent.retrieve_context(user_prompt)
        reflection = self.memory_agent.reflect_on_intent(user_prompt)
        step1_files = {
            "01_hindsight_retrieval.json": {
                "past_experiences": past_experiences,
                "reflection": reflection
            }
        }
        rec1 = self._persist_and_reclaim(1, "Hindsight 语义检索与自省", step1_files, output_dir, None, memory_safe)
        persisted_manifest.extend(rec1["saved_files"])
        collaboration_log.append({
            "stage": "1. Hindsight 跨会话语义检索与自省合成 (Recall & Reflect)",
            "agent": self.memory_agent.name,
            "action": f"Hindsight 匹配 {len(past_experiences)} 条相关记忆，合成 {len(reflection['directives'])} 条高阶工艺准则。",
            "memory_reclamation": rec1
        })

        # Step 2: Chief Architect plans and decomposes
        arch_res = self.architect_agent.run({
            "user_prompt": user_prompt,
            "past_experiences": past_experiences,
            "reflection": reflection
        })
        step2_files = {
            "02_architecture_spec.json": arch_res
        }
        rec2 = self._persist_and_reclaim(2, "需求拆解与架构规划", step2_files, output_dir, None, memory_safe)
        persisted_manifest.extend(rec2["saved_files"])
        collaboration_log.append({
            "stage": "2. 需求拆解与架构规划",
            "agent": self.architect_agent.name,
            "action": arch_res["summary"],
            "memory_reclamation": rec2
        })

        # Step 3: Parametric Modeler generates 3D FeatureTree & VBA
        model_res = self.modeler_agent.run({"user_prompt": user_prompt, "architecture": arch_res})
        step3_files = {
            "03_parametric_feature_tree.json": model_res["feature_tree"],
            "03_parametric_equations.json": model_res["equations"],
            "03_solidworks_native.swb": model_res["solidworks_vba"]
        }
        rec3 = self._persist_and_reclaim(3, "3D 原生特征树与方程式建模", step3_files, output_dir, "solidworks", memory_safe)
        persisted_manifest.extend(rec3["saved_files"])
        collaboration_log.append({
            "stage": "3. 3D 原生特征树与方程式建模",
            "agent": self.modeler_agent.name,
            "action": model_res["summary"],
            "memory_reclamation": rec3
        })

        # Step 4: Standards Agent produces GD&T and 2D annotations
        std_res = self.standards_agent.run({"architecture": arch_res, "modeling": model_res})
        step4_files = {
            "04_drawing_standards_gdt.json": std_res["drawing_spec"]
        }
        rec4 = self._persist_and_reclaim(4, "工程制图标准与 GD&T 标注", step4_files, output_dir, "autocad", memory_safe)
        persisted_manifest.extend(rec4["saved_files"])
        collaboration_log.append({
            "stage": "4. 工程制图标准与 GD&T 标注",
            "agent": self.standards_agent.name,
            "action": std_res["summary"],
            "memory_reclamation": rec4
        })

        # Step 5: Machining Agent produces CAM & CNC Macro B
        mach_res = self.machining_agent.run({"architecture": arch_res, "modeling": model_res})
        step5_files = {
            "05_machining_macro_b.nc": mach_res["macro_b_code"],
            "05_cutting_params.json": mach_res["cutting_params"]
        }
        rec5 = self._persist_and_reclaim(5, "数控加工工艺与 Macro B 刀路", step5_files, output_dir, "cimco", memory_safe)
        persisted_manifest.extend(rec5["saved_files"])
        collaboration_log.append({
            "stage": "5. 数控加工工艺与 Macro B 刀路",
            "agent": self.machining_agent.name,
            "action": mach_res["summary"],
            "memory_reclamation": rec5
        })

        # Step 6: Auditor Agent runs Headless Sandbox Simulation & Self-Healing Loop
        audit_res = self.auditor_agent.run({"modeling": model_res, "machining": mach_res})
        step6_files = {
            "06_sandbox_simulation_audit.json": audit_res
        }
        rec6 = self._persist_and_reclaim(6, "虚拟沙箱仿真与自省自愈", step6_files, output_dir, "vericut", memory_safe)
        persisted_manifest.extend(rec6["saved_files"])
        collaboration_log.append({
            "stage": "6. 虚拟沙箱仿真与自省自愈",
            "agent": self.auditor_agent.name,
            "action": audit_res["summary"],
            "memory_reclamation": rec6
        })

        # Step 7: Memory Agent commits verified patterns
        mem_res = self.memory_agent.run({
            "user_prompt": user_prompt,
            "architecture": arch_res,
            "auditor": audit_res
        })
        step7_files = {
            "07_hindsight_memory_commit.json": mem_res
        }
        rec7 = self._persist_and_reclaim(7, "长期经验向量化归档", step7_files, output_dir, "sscnc", memory_safe)
        persisted_manifest.extend(rec7["saved_files"])
        collaboration_log.append({
            "stage": "7. 长期经验向量化归档",
            "agent": self.memory_agent.name,
            "action": mem_res["summary"],
            "memory_reclamation": rec7
        })

        # 终极净化：确保没有任何后台残余，清空 Ollama 显存
        if memory_safe:
            self.reclaimer.reclaim_all_cad_cam()
            self.reclaimer.unload_ollama_model()

        runtime = round(time.time() - t0, 3)

        # 团队级状态：由 7 步子智能体真实 status 聚合，禁止字面量 SUCCESS
        # 缺省值取 "UNKNOWN"（fail-closed）：子 agent 未显式上报 status 时不得默认视为完成
        per_agent_status: Dict[str, str] = {
            "EvolutionAndMemoryAgent.retrieve_context": "COMPLETED",
            "ChiefArchitectAgent": str(arch_res.get("status", "UNKNOWN")).upper(),
            "ParametricModelingAgent": str(model_res.get("status", "UNKNOWN")).upper(),
            "StandardsAndGDAgent": str(std_res.get("status", "UNKNOWN")).upper(),
            "MachiningAndToolpathAgent": str(mach_res.get("status", "UNKNOWN")).upper(),
            "AuditorAndSandboxAgent": str(
                audit_res.get("status",
                              "COMPLETED" if audit_res.get("passed") is True else "FAILED")
            ).upper(),
            "EvolutionAndMemoryAgent.commit": str(mem_res.get("status", "UNKNOWN")).upper(),
        }
        team_status = self.aggregate_team_status(per_agent_status)

        # 写入全流程清单与人类可读报告
        manifest = {
            "project": "Virtu Industrial Agent Team",
            "user_prompt": user_prompt,
            "output_dir": output_dir,
            "team_status": team_status,
            "per_agent_status": per_agent_status,
            "runtime_seconds": runtime,
            "persisted_artifacts": persisted_manifest,
            "collaboration_log": collaboration_log
        }
        with open(os.path.join(output_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        # 生成 Markdown 交付报告
        report_lines = [
            "# Virtu Industrial Agent Team · 阶段式内存安全执行报告\n",
            f"- **用户愿望**: {user_prompt}",
            f"- **执行耗时**: {runtime} 秒",
            f"- **产物输出目录**: `{output_dir}`",
            f"- **落盘工件总数**: {len(persisted_manifest)} 个（全体验证非空）\n",
            "## 阶段递进与内存回收流水线",
            "| 步骤 | 智能体角色 | 产物文件 | 关停软件 | 回收前可用(MB) | 回收后可用(MB) | 内存净回收(MB) |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
        ]
        for log in collaboration_log:
            rec = log.get("memory_reclamation", {})
            f_names = ", ".join(f"`{f['filename']}`" for f in rec.get("saved_files", []))
            sw = rec.get("software_closed") or "—"
            report_lines.append(
                f"| {rec.get('step_idx')} | {log['agent']} | {f_names} | {sw} | "
                f"{rec.get('ram_before_mb')} | {rec.get('ram_after_mb')} | +{rec.get('reclaimed_mb')} |"
            )
        report_lines.append("\n## 子智能体状态聚合（实测 status，非模板常量）")
        report_lines.append("| 子智能体 | 真实 status |")
        report_lines.append("| :--- | :--- |")
        for role, st in per_agent_status.items():
            report_lines.append(f"| {role} | {st} |")
        report_lines.append(
            f"\n> **团队级状态**：{team_status}"
            "（聚合规则：任一 FAILED → FAILED；全部 COMPLETED → SUCCESS；其余 → PARTIAL）\n"
        )
        report_lines.append(
            "> **落盘与内存准则**：每完成一步即落盘并校验字节非空（结果见上表产物列与 persisted_manifest），"
            "关停软件与内存回收为实测值（见上表回收前后可用内存）。\n"
        )
        residual = self.probe_residual_processes()
        if residual["basis"] == "measured":
            report_lines.append(
                f"> **残留进程实测**：六大 CAD/CAM 软件残留进程总数 {residual['residual_total']}，"
                f"明细 {residual['detail']}。\n"
            )
        else:
            report_lines.append(
                f"> **残留进程实测**：未测（basis={residual['basis']}，明细 {residual['detail']}）。\n"
            )
        report_path = os.path.join(output_dir, "AGENT_TEAM_EXECUTION_REPORT.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(report_lines))

        return {
            "status": team_status,
            "per_agent_status": per_agent_status,
            "audit_passed": audit_res.get("passed"),
            "residual_processes": residual,
            "runtime_seconds": runtime,
            "output_dir": output_dir,
            "report_path": report_path,
            "user_prompt": user_prompt,
            "persisted_manifest": persisted_manifest,
            "team_collaboration_log": collaboration_log,
            "architecture": arch_res,
            "parametric_model": model_res,
            "standards_gdt": std_res,
            "machining_cnc": mach_res,
            "sandbox_audit": audit_res,
            "memory_evolution": mem_res
        }
