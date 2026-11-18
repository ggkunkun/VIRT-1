# -*- coding: utf-8 -*-
"""virtu_omni/memory/sleep_framework.py — Google Research "Sleep" Framework for Virtu Model.

Theoretical & Architectural Grounding:
Paper: "Language Models Need Sleep: Learning to Self-Modify and Consolidate Memories"
Authors: Ali Behrouz, Farnoosh Hashemi, Adel Javanmard, Vahab Mirrokni (Google Research & Cornell, 2026)
arXiv: 2606.03979 / ICLR

Core Architecture:
1. Wake Phase (清醒交互期):
   - Fast, low-latency online inference and engineering problem solving.
   - Captures episodic interactions, tool outputs, and physical facts into an in-memory WakeBuffer.
2. Sleep Phase (睡眠巩固与自进化期):
   - Phase 1: Memory Consolidation (记忆巩固 / 知识播种 Knowledge Seeding):
     Distills ephemeral conversational context into immutable, structured physical invariants
     and parameter-efficient expert update hints. Compresses token footprints by >80%.
   - Phase 2: Dreaming (自博弈梦境合成与自验证 Counterfactual Dreaming):
     Synthesizes counterfactual engineering variations, executes solutions through Virtu model,
     and gates them against deterministic physics/geometry execution oracles (Lamé stress,
     FOS >= 1.5, Delta V != 0 volume conservation, G-code modal checks).
   - Phase 3: Synaptic Homeostasis & Regularization (突触稳态与防遗忘门禁):
     Evaluates Plasticity (P >= 90% on new tasks) vs Stability (S >= 95% on anchor baseline),
     ensuring Catastrophic Forgetting (CF <= 5%) with content-addressed provenance.

Measurement Constitution Compliance (RULE[d:\\Virtu模型\\AGENTS.md] Section 8):
- All metrics carry run_id, sample size n, basis ("measured"), and verifiable evidence files.
- Gates are falsifiable: includes explicit mutation probe testing (bad physics MUST be rejected).
"""

from __future__ import annotations

import copy
import dataclasses
from dataclasses import asdict, dataclass, field
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import re
import sys
import threading
import time
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("virtu_omni.memory.sleep_framework")

# Workspace root
WORKSPACE_DIR = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

try:
    from virtu_eval.derivation import LAWS
except ImportError:
    LAWS = {}

try:
    from virtu_eval.provenance import Metric, RunIdentity, sha256_file
except ImportError:
    RunIdentity = None
    Metric = None
    def sha256_file(p):
        with open(p, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

try:
    from virtu_omni.memory.hindsight_adapter import VirtuHindsightMemory, MemoryType
except ImportError:
    VirtuHindsightMemory = None
    MemoryType = None


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class WakeExperience:
    """A single atomic interaction during the Wake phase."""
    id: str
    prompt: str
    completion: str
    verified_facts: Dict[str, Any] = field(default_factory=dict)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    #: 真实 token 计数（int）；执行器未回传测量值时写字符串 "unmeasured"，
    #: 不得用 len(x)//2 或常量冒充（AGENTS.md §8.1）。
    tokens_prompt: Union[int, str] = 0
    tokens_completion: Union[int, str] = 0
    timestamp: float = field(default_factory=time.time)
    receipt_hash: Optional[str] = None

    def compute_hash(self) -> str:
        body = f"{self.id}:{self.prompt}:{self.completion}:{sorted(self.verified_facts.items())}"
        self.receipt_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
        return self.receipt_hash


@dataclass
class ConsolidatedKnowledge:
    """Distilled permanent knowledge extracted during Sleep Phase 1."""
    domain: str
    rule_key: str
    formula_or_invariant: str
    parameters: Dict[str, Any]
    source_experience_ids: List[str]
    #: None = token 未实测；严禁用字符长度估算冒充（AGENTS.md §8.1）
    compression_ratio: Optional[float]
    provenance_hash: str
    token_basis: str = "unmeasured"  # "measured" | "unmeasured"


@dataclass
class DreamScenario:
    """A counterfactual synthetic scenario generated during Sleep Phase 2."""
    scenario_id: str
    prompt: str
    counterfactual_delta: Dict[str, Any]
    expected_law: str
    oracle_verifier: str
    model_solution: Optional[str] = None
    oracle_passed: bool = False
    reward: float = 0.0
    execution_receipt: Optional[Dict[str, Any]] = None
    #: "model" | "analytic_baseline" | "error"；解析解自证不算实测证据
    solution_source: str = "unset"
    #: "measured" | "self_check" | "unmeasured"
    evidence_basis: str = "unmeasured"


@dataclass
class HomeostasisVerdict:
    """Audit of plasticity vs stability to guarantee zero catastrophic forgetting."""
    run_id: str
    sample_size_anchor: int
    sample_size_plasticity: int
    stability_score: float  # Accuracy on historical anchor tasks (Retention)
    plasticity_score: float  # Accuracy on newly acquired tasks
    catastrophic_forgetting_rate: float  # 1.0 - stability_score
    gate_passed: bool
    evidence_path: str
    basis: str = "measured"
    reasons: List[str] = field(default_factory=list)
    thresholds: Dict[str, float] = field(default_factory=dict)
    baseline_provided: bool = False
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Core Components
# ---------------------------------------------------------------------------

class WakeExperienceBuffer:
    """Thread-safe cyclic buffer for capturing online wake-phase experiences with disk persistence."""

    def __init__(self, capacity: int = 500, persist_path: Optional[Path] = None):
        self.capacity = capacity
        self.persist_path = persist_path
        self._lock = threading.Lock()
        self._buffer: List[WakeExperience] = []

        # Restore unconsolidated experiences from disk if available
        if self.persist_path and self.persist_path.exists():
            try:
                with open(self.persist_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            data = json.loads(line)
                            exp = WakeExperience(**data)
                            self._buffer.append(exp)
                if len(self._buffer) > self.capacity:
                    self._buffer = self._buffer[-self.capacity:]
                logger.info(f"Restored {len(self._buffer)} unconsolidated wake experiences from disk.")
            except Exception as e:
                logger.warning(f"Could not restore wake experiences from {self.persist_path}: {e}")

    def record(
        self,
        prompt: str,
        completion: str,
        verified_facts: Optional[Dict[str, Any]] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        tokens_prompt: Union[int, str] = 0,
        tokens_completion: Union[int, str] = 0,
    ) -> WakeExperience:
        with self._lock:
            exp_id = f"WAKE_{len(self._buffer) + 1:04d}_{int(time.time()*1000)%1000000}"
            exp = WakeExperience(
                id=exp_id,
                prompt=prompt,
                completion=completion,
                verified_facts=verified_facts or {},
                tool_calls=tool_calls or [],
                tokens_prompt=tokens_prompt,
                tokens_completion=tokens_completion,
            )
            exp.compute_hash()
            self._buffer.append(exp)
            if len(self._buffer) > self.capacity:
                self._buffer.pop(0)

            # Append to persistent JSONL
            if self.persist_path:
                try:
                    self.persist_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(self.persist_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps(asdict(exp), ensure_ascii=False) + "\n")
                except Exception as e:
                    logger.warning(f"Failed to append wake experience to disk: {e}")

            return exp

    def get_unconsolidated(self) -> List[WakeExperience]:
        with self._lock:
            return list(self._buffer)

    def clear(self) -> None:
        with self._lock:
            self._buffer.clear()
            if self.persist_path and self.persist_path.exists():
                try:
                    self.persist_path.unlink()
                except Exception as e:
                    logger.warning(f"Failed to clear {self.persist_path}: {e}")

    def __len__(self) -> int:
        with self._lock:
            return len(self._buffer)


class KnowledgeSeeder:
    """Sleep Phase 1: Distills episodic experiences into parametric knowledge units."""

    def consolidate(self, experiences: List[WakeExperience]) -> List[ConsolidatedKnowledge]:
        consolidated: List[ConsolidatedKnowledge] = []
        if not experiences:
            return consolidated

        for exp in experiences:
            # AGENTS.md §8.1: token 只认执行器实测值。取不到时 raw_token_count=None，
            # 绝不回落到 len(text)*2 之类的字符近似冒充测量。
            _tp = exp.tokens_prompt if isinstance(exp.tokens_prompt, (int, float)) and not isinstance(exp.tokens_prompt, bool) else 0
            _tc = exp.tokens_completion if isinstance(exp.tokens_completion, (int, float)) and not isinstance(exp.tokens_completion, bool) else 0
            total_tokens = _tp + _tc
            token_basis = "measured" if total_tokens > 0 else "unmeasured"
            raw_token_count: Optional[float] = total_tokens if total_tokens > 0 else None

            # 1. Identify engineering domain invariants
            extracted_rules = self._extract_domain_rules(exp)
            for domain, key, formula, params in extracted_rules:
                if raw_token_count is not None:
                    distilled_token_count = max(len(formula.split()), 8)
                    compression: Optional[float] = max(
                        0.0, min(1.0, (raw_token_count - distilled_token_count) / max(raw_token_count, 1))
                    )
                else:
                    compression = None

                prov_hash = hashlib.sha256(
                    f"{exp.receipt_hash}:{domain}:{key}:{formula}".encode("utf-8")
                ).hexdigest()

                knowledge = ConsolidatedKnowledge(
                    domain=domain,
                    rule_key=key,
                    formula_or_invariant=formula,
                    parameters=params,
                    source_experience_ids=[exp.id],
                    compression_ratio=compression,
                    provenance_hash=prov_hash,
                    token_basis=token_basis,
                )
                consolidated.append(knowledge)

        # Sync distilled domain invariants into Hindsight long-term memory
        # (never dump catch-all raw task_verified_facts telemetry JSON blobs).
        if VirtuHindsightMemory is not None and MemoryType is not None:
            try:
                h_mem = VirtuHindsightMemory()
                bank_map = {
                    "cae_simulation": "virtu_quality_audit",
                    "cnc_machining": "virtu_cnc_machining",
                    "cad_modeling": "virtu_cad_cam",
                }
                synced = 0
                for c in consolidated:
                    if c.rule_key == "task_verified_facts":
                        continue
                    bank = bank_map.get(c.domain, "default")
                    clean_params = self._sanitize_facts(c.parameters)
                    param_suffix = (
                        f"；工程参数：{json.dumps(clean_params, ensure_ascii=False)}"
                        if clean_params
                        else ""
                    )
                    h_mem.retain(
                        bank_id=bank,
                        content=f"【Sleep固化心智模型-{c.rule_key}】{c.formula_or_invariant}{param_suffix}",
                        memory_type=MemoryType.MENTAL_MODELS,
                        tags=[c.domain, c.rule_key],
                    )
                    synced += 1
                logger.info(f"Synced {synced} consolidated knowledge items to Hindsight memory.")
            except Exception as e:
                logger.warning(f"Failed to sync consolidated knowledge to Hindsight: {e}")

        return consolidated

    _TELEMETRY_KEYS = frozenset({
        "facets_engaged",
        "steps",
        "tool_calls_trace",
        "elapsed_ms",
        "raw_response",
        "architecture",
        "telemetry",
        "error",
        "traceback",
    })

    @classmethod
    def _is_noisy_telemetry(cls, prompt: str, facts: Optional[Dict[str, Any]]) -> bool:
        p_low = (prompt or "").lower()
        if "dynamic_gap" in p_low or "缺少未知切削刀具参数" in (prompt or ""):
            return True
        if not isinstance(facts, dict):
            return False
        if "facets_engaged" in facts or "DYNAMIC_GAP" in json.dumps(facts, ensure_ascii=False):
            return True
        return False

    @classmethod
    def _sanitize_facts(cls, facts: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not isinstance(facts, dict):
            return {}
        return {
            k: v
            for k, v in facts.items()
            if k not in cls._TELEMETRY_KEYS and "DYNAMIC_GAP" not in str(v)
        }

    def _extract_domain_rules(
        self, exp: WakeExperience
    ) -> List[Tuple[str, str, str, Dict[str, Any]]]:
        if self._is_noisy_telemetry(exp.prompt, exp.verified_facts):
            return []
        rules = []
        clean_facts = self._sanitize_facts(exp.verified_facts)
        # Thick cylinder / Lamé stress
        if "厚壁圆筒" in exp.prompt or "lamé" in exp.prompt.lower() or "lame" in exp.prompt.lower() or "fea_fos" in exp.prompt.lower():
            rules.append((
                "cae_simulation",
                "lame_thick_cylinder_fos",
                "k = (Do/Di)^2; sigma_t = Pi*(k+1)/(k-1); sigma_r = -Pi; sigma_vm = sqrt(sigma_t^2 + sigma_r^2 - sigma_t*sigma_r + 3*tau^2); FOS = Sy / sigma_vm >= 1.5",
                clean_facts,
            ))
        # Cross-software coordinate isolation (SOLIDWORKS Y-up vs VERICUT/NX/CNC Z-up)
        p_low = exp.prompt.lower()
        if "solidworks" in p_low or "基准面" in exp.prompt or "front plane" in p_low:
            rules.append((
                "cad_modeling",
                "sw_coordinate_y_up",
                "SOLIDWORKS 2021 Y-up: Front=XY(+Z 0,0,1), Top=XZ(+Y 0,1,0), Right=YZ(+X 1,0,0); DO NOT mix CNC Z-up",
                clean_facts,
            ))
        if "vericut" in p_low or "vcproject" in p_low or "auto-diff" in p_low or "autodiff" in p_low:
            rules.append((
                "cnc_machining",
                "vericut_coordinate_z_up_autodiff",
                "VERICUT 9.6 / NX / CNC Z-up G54; XML Unit='inch'|'millimeter' exact match; Auto-Diff Red=Gouge(FATAL), Blue=Excess, Green=OK",
                clean_facts,
            ))
        if "g71" in p_low or "g70" in p_low or "fanuc" in p_low:
            rules.append((
                "cnc_machining",
                "fanuc_g71_turning_safety",
                "FANUC G71/G70: T0101; G50 S_; G96 S_ M03; G0 X>stock_od Z>0 (NO G00 negative-Z plunge); G71 U_ R_; G71 P_ Q_ U_ W_ F_; M30",
                clean_facts,
            ))
        # Spindle speed / cutting feeds
        if "主轴转速" in exp.prompt or "vc" in exp.prompt.lower() or "cutting_speed" in exp.prompt.lower():
            rules.append((
                "cnc_machining",
                "spindle_speed_formula",
                "n = 1000 * Vc / (pi * D); Vf = f * z * n",
                clean_facts,
            ))
        # Volume conservation / CAD geometry
        if "法兰" in exp.prompt or "cad" in exp.prompt.lower() or "volume" in exp.prompt.lower():
            rules.append((
                "cad_modeling",
                "volume_conservation_assertion",
                "delta_V != 0; |V_cad - V_theory| / V_theory <= 0.01",
                clean_facts,
            ))
        # Default fallback extraction only for clean, non-telemetry engineering facts
        if not rules and clean_facts and any(isinstance(v, (int, float)) and not isinstance(v, bool) for v in clean_facts.values()):
            rules.append((
                "engineering_invariants",
                "task_verified_facts",
                json.dumps(clean_facts, ensure_ascii=False),
                clean_facts,
            ))
        return rules


class DreamEngine:
    """Sleep Phase 2: Generates synthetic counterfactuals and verifies with physical oracles."""

    def __init__(self, model_caller: Optional[Callable[[str], str]] = None):
        self.model_caller = model_caller

    def generate_counterfactuals(
        self, consolidated: List[ConsolidatedKnowledge], count_per_rule: int = 2
    ) -> List[DreamScenario]:
        dreams: List[DreamScenario] = []
        scenario_idx = 1

        for c in consolidated:
            if c.domain == "cae_simulation":
                # Perturb inner diameter, pressure, or yield strength
                variations = [
                    {"D_inner": 60.0, "D_outer": 120.0, "P_internal": 25.0, "Sy": 310.0},
                    {"D_inner": 80.0, "D_outer": 140.0, "P_internal": 35.0, "Sy": 450.0},
                ]
                for v in variations[:count_per_rule]:
                    prompt = (
                        f"【梦境仿真题】厚壁圆筒内径 D_i={v['D_inner']}mm，外径 D_o={v['D_outer']}mm，"
                        f"承受内压 P_i={v['P_internal']}MPa，材质屈服强度 Sy={v['Sy']}MPa。"
                        f"请计算最大等效应力(von Mises)并判断安全系数 FOS 是否满足 FOS>=1.5 制造底线。"
                    )
                    dreams.append(DreamScenario(
                        scenario_id=f"DREAM_{scenario_idx:04d}_CAE",
                        prompt=prompt,
                        counterfactual_delta=v,
                        expected_law="fea_fos",
                        oracle_verifier="lame_elasticity_oracle",
                    ))
                    scenario_idx += 1

            elif c.domain == "cnc_machining":
                # Perturb cutting speed and tool diameter
                variations = [
                    {"D": 50.0, "Vc": 120.0, "expected_n": 764},
                    {"D": 80.0, "Vc": 150.0, "expected_n": 597},
                ]
                for v in variations[:count_per_rule]:
                    prompt = (
                        f"【梦境加工题】数控车削 45 号钢，刀具切削直径 D={v['D']}mm，"
                        f"线速度推荐 Vc={v['Vc']}m/min。请只依据公式计算主轴转速 n (r/min，取整)。"
                    )
                    dreams.append(DreamScenario(
                        scenario_id=f"DREAM_{scenario_idx:04d}_CNC",
                        prompt=prompt,
                        counterfactual_delta=v,
                        expected_law="spindle_speed",
                        oracle_verifier="cutting_speed_oracle",
                    ))
                    scenario_idx += 1

            elif c.domain == "cad_modeling":
                # Perturb cylinder dimensions for volume conservation
                variations = [
                    {"D": 100.0, "H": 50.0, "hole_d": 30.0},
                    {"D": 120.0, "H": 40.0, "hole_d": 40.0},
                ]
                for v in variations[:count_per_rule]:
                    v_theory = math.pi * ((v['D']/2)**2 - (v['hole_d']/2)**2) * v['H']
                    prompt = (
                        f"【梦境建模题】圆柱带孔法兰，外径 D={v['D']}mm，高度 H={v['H']}mm，"
                        f"中心通孔直径 d={v['hole_d']}mm。请计算特征理论体积 (mm^3，精确到整数)。"
                    )
                    v_dict = dict(v)
                    v_dict["expected_v"] = round(v_theory)
                    dreams.append(DreamScenario(
                        scenario_id=f"DREAM_{scenario_idx:04d}_CAD",
                        prompt=prompt,
                        counterfactual_delta=v_dict,
                        expected_law="geom_delta",
                        oracle_verifier="volume_conservation_oracle",
                    ))
                    scenario_idx += 1

        return dreams

    def generate_anchor_dreams(self) -> List[DreamScenario]:
        """经验未落在三大工程域时仍提供可证伪的标准梦境，避免空集被当成无证据。

        历史 auto_cycle 里 consolidated_units=67 但 dreams_generated 仅 12，
        根源就是 fallback 域的 wake 记录完全不产生梦境。
        """
        return [
            DreamScenario(
                scenario_id="ANCHOR_DREAM_0001_CAE",
                prompt="【梦境仿真题】厚壁圆筒内径 D_i=60mm，外径 D_o=120mm，承受内压 P_i=25MPa，"
                       "材质屈服强度 Sy=310MPa。请计算最大等效应力(von Mises)并判断安全系数 FOS 是否满足 FOS>=1.5 制造底线。",
                counterfactual_delta={"D_inner": 60.0, "D_outer": 120.0, "P_internal": 25.0, "Sy": 310.0},
                expected_law="fea_fos",
                oracle_verifier="lame_elasticity_oracle",
            ),
            DreamScenario(
                scenario_id="ANCHOR_DREAM_0002_CNC",
                prompt="【梦境加工题】数控车削 45 号钢，刀具切削直径 D=50mm，线速度推荐 Vc=120m/min。"
                       "请只依据公式计算主轴转速 n (r/min，取整)。",
                counterfactual_delta={"D": 50.0, "Vc": 120.0, "expected_n": 764},
                expected_law="spindle_speed",
                oracle_verifier="cutting_speed_oracle",
            ),
        ]

    def execute_and_verify(self, dreams: List[DreamScenario]) -> List[DreamScenario]:
        for dream in dreams:
            # 1. Obtain solution via model caller if available, else synthetic solver
            if self.model_caller:
                try:
                    dream.model_solution = self.model_caller(dream.prompt)
                    if dream.model_solution and dream.model_solution.startswith("ERROR:"):
                        dream.solution_source = "error"
                        dream.evidence_basis = "unmeasured"
                    else:
                        dream.solution_source = "model"
                        dream.evidence_basis = "measured"
                except Exception as e:
                    logger.warning(f"Model call failed during dream {dream.scenario_id}: {e}")
                    dream.model_solution = f"ERROR: {e}"
                    dream.solution_source = "error"
                    dream.evidence_basis = "unmeasured"
            else:
                # 解析解只作自检基线，不得计为模型能力实测证据
                dream.model_solution = self._solve_analytically(dream)
                dream.solution_source = "analytic_baseline"
                dream.evidence_basis = "self_check"

            # 2. Oracle Verification
            passed, receipt = self.verify_with_oracle(dream)
            dream.oracle_passed = passed
            dream.execution_receipt = receipt
            dream.reward = 1.0 if passed else 0.0

        return dreams

    def _solve_analytically(self, dream: DreamScenario) -> str:
        delta = dream.counterfactual_delta
        if dream.oracle_verifier == "lame_elasticity_oracle":
            ri, ro = delta["D_inner"] / 2.0, delta["D_outer"] / 2.0
            pi = delta["P_internal"]
            sy = delta["Sy"]
            sigma_t = pi * (ro**2 + ri**2) / (ro**2 - ri**2)
            sigma_r = -pi
            sigma_z = (pi * ri**2) / (ro**2 - ri**2)
            sigma_vm = math.sqrt(0.5 * ((sigma_t - sigma_r)**2 + (sigma_r - sigma_z)**2 + (sigma_z - sigma_t)**2))
            fos = sy / sigma_vm
            return f"von Mises 应力 = {sigma_vm:.2f} MPa, 安全系数 FOS = {fos:.2f}, 合规: {fos >= 1.5}"
        elif dream.oracle_verifier == "cutting_speed_oracle":
            d = delta["D"]
            vc = delta["Vc"]
            n = round(1000.0 * vc / (math.pi * d))
            return f"计算公式 n = 1000*Vc/(pi*D)，代入求得 n = {n} r/min"
        elif dream.oracle_verifier == "volume_conservation_oracle":
            return f"理论体积 V = {delta.get('expected_v', 0)} mm^3"
        return "N/A"

    def verify_with_oracle(self, dream: DreamScenario) -> Tuple[bool, Dict[str, Any]]:
        delta = dream.counterfactual_delta
        sol = dream.model_solution or ""

        if dream.oracle_verifier == "lame_elasticity_oracle":
            ri, ro = delta["D_inner"] / 2.0, delta["D_outer"] / 2.0
            pi = delta["P_internal"]
            sy = delta["Sy"]
            sigma_t = pi * (ro**2 + ri**2) / (ro**2 - ri**2)
            sigma_r = -pi
            sigma_z = (pi * ri**2) / (ro**2 - ri**2)
            sigma_vm = math.sqrt(0.5 * ((sigma_t - sigma_r)**2 + (sigma_r - sigma_z)**2 + (sigma_z - sigma_t)**2))
            theory_fos = sy / sigma_vm

            # Check if model answer is physically sound and matches oracle within engineering bounds (<40%)
            nums = [float(x) for x in re.findall(r"[-+]?\d*\.\d+|\d+", sol)]
            stress_match = any(abs(n - sigma_vm) / sigma_vm < 0.40 for n in nums if sigma_vm > 0)
            fos_match = any(abs(n - theory_fos) / theory_fos < 0.40 for n in nums if theory_fos > 0)
            
            # FOS must be logically consistent with safety
            safety_contradiction = False
            if any(n < 1.0 for n in nums if "fos" in sol.lower()) and theory_fos >= 1.5:
                safety_contradiction = True

            passed = (stress_match or fos_match) and not safety_contradiction
            return passed, {
                "theory_sigma_vm": round(sigma_vm, 2),
                "theory_fos": round(theory_fos, 2),
                "stress_match": stress_match,
                "fos_match": fos_match,
                "safety_contradiction": safety_contradiction,
            }

        elif dream.oracle_verifier == "cutting_speed_oracle":
            expected_n = round(1000.0 * delta["Vc"] / (math.pi * delta["D"]))
            nums = [int(float(x)) for x in re.findall(r"\d+", sol)]
            n_match = any(abs(n - expected_n) <= 2 for n in nums)
            return n_match, {"expected_n": expected_n, "matched": n_match}

        elif dream.oracle_verifier == "volume_conservation_oracle":
            exp_v = delta.get("expected_v", 0)
            nums = [int(float(x)) for x in re.findall(r"\d+", sol)]
            v_match = any(abs(n - exp_v) / max(exp_v, 1) < 0.02 for n in nums)
            return v_match, {"expected_v": exp_v, "matched": v_match}

        return False, {"error": "unknown_verifier"}


class SynapticHomeostasis:
    """Sleep Phase 3: Evaluates plasticity vs stability to guarantee zero catastrophic forgetting."""

    # 论文目标阈值；门禁必须用绝对阈值，禁止与自身基线自比较
    STABILITY_MIN = 0.95
    PLASTICITY_MIN = 0.90
    CF_MAX = 0.05

    def __init__(self, anchor_test_cases: Optional[List[Dict[str, Any]]] = None):
        self.anchor_cases = anchor_test_cases or self._default_anchor_cases()

    def _default_anchor_cases(self) -> List[Dict[str, Any]]:
        """Golden historical anchor cases ensuring no regression on core engineering disciplines."""
        return [
            {
                "id": "ANCHOR_01_G71_FANUC",
                "prompt": "在 FANUC 数控车床 Macro B 编程中，G71 粗车循环第二行的 U 参数代表什么含义？",
                "keywords": ["单边", "径向", "精加工余量", "余量"],
            },
            {
                "id": "ANCHOR_02_LAME_STRESS",
                "prompt": "厚壁圆筒受内压 Pi 作用下，其内壁位置处的径向应力 sigma_r 等于多少？",
                "keywords": ["-Pi", "-P_i", "负", "受压", "内压"],
            },
            {
                "id": "ANCHOR_03_MMC_TOLERANCE",
                "prompt": "在 GB/T 形位公差标注中，符号 M 外面带圆圈代表什么含义？实际尺寸偏离最大实体尺寸时公差如何变化？",
                "keywords": ["最大实体要求", "MMC", "补偿", "放宽"],
            },
            {
                "id": "ANCHOR_04_SOLIDWORKS_VBA",
                "prompt": "在 SOLIDWORKS 2021 VBA 宏中向方程式管理器 swEqnMgr 添加变量时，双引号应如何转义？",
                "keywords": ["双重转义", "\"\"", "转义"],
            },
            {
                "id": "ANCHOR_05_ISO_SAFETY",
                "prompt": "机械安全设计通则国家标准 GB/T 15706 对应哪一个国际标准？",
                "keywords": ["12100", "ISO 12100"],
            },
        ]

    def audit_homeostasis(
        self,
        model_caller: Optional[Callable[[str], str]],
        newly_consolidated: List[ConsolidatedKnowledge],
        run_id: str,
        output_dir: Path,
        pre_baseline_score: Optional[float] = None,
    ) -> HomeostasisVerdict:
        """测量稳态/可塑性；缺模型调用或缺独立基线时 basis=unmeasured 且 gate=False。

        门禁为绝对阈值（S>=0.95 / P>=0.90 / CF<=0.05），CF 必须由外部实测的
        sleep 前基线计算。禁止用 post-stability 自身充当 baseline（旧实现恒 True）。
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        evidence_file = output_dir / f"homeostasis_audit_{run_id}.json"
        thresholds = {
            "stability_min": self.STABILITY_MIN,
            "plasticity_min": self.PLASTICITY_MIN,
            "cf_max": self.CF_MAX,
        }
        reasons: List[str] = []
        baseline_provided = pre_baseline_score is not None
        anchor_details: List[Dict[str, Any]] = []
        plasticity_details: List[Dict[str, Any]] = []
        stability = 0.0
        plasticity = 0.0
        cf_rate = 0.0
        basis = "measured"

        if model_caller is None:
            basis = "unmeasured"
            reasons.append("no_model_caller: anchor/plasticity not measured")
        else:
            # 1. Stability on golden anchors
            anchor_hits = 0
            for case in self.anchor_cases:
                try:
                    resp = model_caller(case["prompt"])
                    resp = str(resp) if resp is not None else "ERROR: empty_response"
                except Exception as e:
                    resp = f"ERROR: {e}"
                if resp.startswith("ERROR:"):
                    basis = "unmeasured"
                    reasons.append(f"model_caller_error:anchor:{case['id']}")
                hit = self._evaluate_anchor_case(case, resp)
                anchor_hits += int(hit)
                anchor_details.append({"case_id": case["id"], "passed": hit, "response": resp})
            stability = anchor_hits / max(len(self.anchor_cases), 1)

            # 2. Plasticity on newly consolidated knowledge
            plasticity_hits = 0
            for c in newly_consolidated:
                test_prompt = f"请简要陈述在 {c.domain} 体系中，规则 {c.rule_key} 的核心计算公式与工程约束。"
                try:
                    resp = model_caller(test_prompt)
                    resp = str(resp) if resp is not None else "ERROR: empty_response"
                except Exception as e:
                    resp = f"ERROR: {e}"
                if resp.startswith("ERROR:"):
                    basis = "unmeasured"
                    reasons.append(f"model_caller_error:plasticity:{c.rule_key}")
                hit = self._evaluate_plasticity_case(c, resp)
                plasticity_hits += int(hit)
                plasticity_details.append({"rule_key": c.rule_key, "passed": hit, "response": resp})
            plasticity = plasticity_hits / max(len(newly_consolidated), 1) if newly_consolidated else 0.0

            # 3. CF 需要独立的 sleep 前基线
            if baseline_provided:
                cf_rate = max(0.0, round(float(pre_baseline_score) - stability, 4))
            else:
                basis = "unmeasured"
                reasons.append("no_pre_baseline_score: CF cannot be measured")

        gate_passed = (
            basis == "measured"
            and baseline_provided
            and stability >= self.STABILITY_MIN
            and plasticity >= self.PLASTICITY_MIN
            and cf_rate <= self.CF_MAX
        )
        if not gate_passed:
            if stability < self.STABILITY_MIN:
                reasons.append(f"stability_below_threshold:{stability:.4f}")
            if plasticity < self.PLASTICITY_MIN:
                reasons.append(f"plasticity_below_threshold:{plasticity:.4f}")
            if cf_rate > self.CF_MAX:
                reasons.append(f"cf_above_threshold:{cf_rate:.4f}")

        record = {
            "run_id": run_id,
            "sample_size_anchor": len(self.anchor_cases),
            "sample_size_plasticity": len(newly_consolidated),
            "pre_baseline_score": pre_baseline_score,
            "baseline_provided": baseline_provided,
            "stability_score": stability,
            "plasticity_score": plasticity,
            "catastrophic_forgetting_rate": cf_rate,
            "gate_passed": gate_passed,
            "basis": basis,
            "thresholds": thresholds,
            "reasons": reasons,
            "anchor_details": anchor_details,
            "plasticity_details": plasticity_details,
            "timestamp": time.time(),
        }
        with open(evidence_file, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)

        return HomeostasisVerdict(
            run_id=run_id,
            sample_size_anchor=len(self.anchor_cases),
            sample_size_plasticity=len(newly_consolidated),
            stability_score=stability,
            plasticity_score=plasticity,
            catastrophic_forgetting_rate=cf_rate,
            gate_passed=gate_passed,
            evidence_path=str(evidence_file),
            basis=basis,
            reasons=reasons,
            thresholds=thresholds,
            baseline_provided=baseline_provided,
        )

    @staticmethod
    def _evaluate_anchor_case(case: Dict[str, Any], resp: str) -> bool:
        """Semantic/sign-aware grading on golden anchors; keyword stuffing or wrong sign must fail."""
        text = re.sub(r"<think>.*?</think>", "", str(resp or ""), flags=re.S).strip() or str(resp or "")
        if not text or text.startswith("ERROR:"):
            return False
        rl = text.lower()
        cid = str(case.get("id", ""))
        if cid == "ANCHOR_01_G71_FANUC":
            if re.search(r"(?:不是|并非|无关|不代表).{0,10}(?:余量|精加工|精车)", rl):
                return False
            has_axis = any(k in rl for k in ("单边", "径向", "x轴", "x 轴", "x方向", "x 方向"))
            has_stock = any(k in rl for k in ("余量", "精加工", "精车"))
            return has_axis and has_stock
        if cid == "ANCHOR_02_LAME_STRESS":
            has_neg = bool(re.search(r"(?:-\s*p_?i\b|负\s*p_?i|-\s*内压)", rl))
            bad_sign = bool(re.search(r"(?:\+\s*p_?i\b|正\s*p_?i|不是\s*-\s*p_?i|并非\s*-\s*p_?i|受拉)", rl))
            return has_neg and not bad_sign
        if cid == "ANCHOR_03_MMC_TOLERANCE":
            if re.search(r"(?:不能补偿|不可补偿|公差减小|公差收紧|最小实体)", rl):
                return False
            return ("最大实体" in rl or "mmc" in rl) and any(k in rl for k in ("补偿", "放宽", "增大", "允许"))
        if cid == "ANCHOR_04_SOLIDWORKS_VBA":
            if re.search(r"(?:无需转义|不用转义|不转义|单引号)", rl):
                return False
            has_dbl = any(k in rl for k in ("双重", "双写", "连续两个", "成对", "chr(34)")) or ('""' in text)
            return has_dbl and ("转义" in rl or '""' in text or "chr(34)" in rl)
        if cid == "ANCHOR_05_ISO_SAFETY":
            if re.search(r"(?:不是|非|并非|不对应)\s*(?:iso\s*)?12100", rl):
                return False
            return "12100" in rl

        for kw in case.get("keywords") or []:
            kl = str(kw).lower()
            if kl in rl and not re.search(rf"(?:不是|非|并非)\s*(?:是|为)?\s*{re.escape(kl)}", rl):
                return True
        return False

    @staticmethod
    def _evaluate_plasticity_case(concept: ConsolidatedKnowledge, resp: str) -> bool:
        """Require formula/constraint grounding rather than isolated domain buzzwords."""
        text = re.sub(r"<think>.*?</think>", "", str(resp or ""), flags=re.S).strip() or str(resp or "")
        if not text or text.startswith("ERROR:") or re.match(r"^\s*(?:无法|不能|不知道|拒绝|不清楚)", text):
            return False
        rl = text.lower()
        has_math = (
            ("=" in text)
            or ("≈" in text)
            or (">=" in text)
            or ("≥" in text)
            or ("/" in text)
            or bool(re.search(r"\d+(?:\.\d+)?\s*(?:mpa|r/min|rpm|mm)", rl))
        )
        if concept.domain == "cae_simulation":
            has_stress = any(k in rl for k in ("应力", "sigma", "mises", "lame"))
            has_safety = any(k in rl for k in ("fos", "安全系数", "屈服", "强度", "合规"))
            return sum([has_stress, has_safety, has_math]) >= 2
        if concept.domain == "cnc_machining":
            has_formula = ("1000" in rl and "vc" in rl) or ("pi" in rl or "π" in rl)
            has_target = any(k in rl for k in ("转速", "主轴", "rpm", "r/min"))
            return sum([has_formula, has_target, has_math]) >= 2
        if concept.domain == "cad_modeling":
            has_vol = any(k in rl for k in ("体积", "volume", "v =", "v="))
            has_rule = any(k in rl for k in ("守恒", "理论", "毛坯", "切除", "mm^3", "mm³"))
            return has_vol and (has_rule or has_math)

        keys = [str(k).lower() for k in (concept.parameters or {}).keys()] + [concept.rule_key.lower()]
        formula_tokens = [
            tok.lower() for tok in re.split(r"[\W_]+", concept.formula_or_invariant)
            if len(tok) >= 2 and tok.isalnum()
        ]
        return any(k and k in rl for k in keys) and (any(t in rl for t in formula_tokens) or has_math)


# ---------------------------------------------------------------------------
# High-Level Orchestrator
# ---------------------------------------------------------------------------

class VirtuSleepFramework:
    """Master controller managing Wake-Sleep cycles for Virtu model."""

    def __init__(
        self,
        model_caller: Optional[Callable[[str], str]] = None,
        output_dir: Optional[Path] = None,
        model_caller_label: str = "unlabeled",
        baseline_score: Optional[float] = None,
    ):
        self.model_caller = model_caller
        self.model_caller_label = model_caller_label
        self.baseline_score = baseline_score  # 外部实测的 sleep 前锚定基线
        self.output_dir = output_dir or (WORKSPACE_DIR / "runs" / "sleep_framework")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        persist_file = self.output_dir / "wake_experiences.jsonl"
        self.wake_buffer = WakeExperienceBuffer(persist_path=persist_file)
        self.seeder = KnowledgeSeeder()
        self.dream_engine = DreamEngine(model_caller=model_caller)
        self.homeostasis = SynapticHomeostasis()

        self.consolidated_store: List[ConsolidatedKnowledge] = []
        self.dream_history: List[DreamScenario] = []
        self.audit_verdicts: List[HomeostasisVerdict] = []
        self.is_sleeping = False

    def record_wake_step(
        self,
        prompt: str,
        completion: str,
        verified_facts: Optional[Dict[str, Any]] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        tokens_prompt: Union[int, str] = 0,
        tokens_completion: Union[int, str] = 0,
    ) -> WakeExperience:
        """Called during Wake phase to record episodic interactions.

        ``tokens_*`` 只接受执行器实测值；拿不到测量值时必须传 ``"unmeasured"``。
        """
        return self.wake_buffer.record(
            prompt=prompt,
            completion=completion,
            verified_facts=verified_facts,
            tool_calls=tool_calls,
            tokens_prompt=tokens_prompt,
            tokens_completion=tokens_completion,
        )

    def run_sleep_cycle(
        self,
        run_id: Optional[str] = None,
        pre_baseline_score: Optional[float] = None,
    ) -> Dict[str, Any]:
        """执行三阶段离线巩固（AGENTS.md §5/§8 有效性约束）。

        - 无 model_caller：梦境仅自检、稳态标 unmeasured、gate=False，绝不假通过。
        - 无独立 pre_baseline_score：CF 不可测、gate=False。
        - 空梦境 / 未测 token：一律不记为通过或实测。
        """
        self.is_sleeping = True
        cycle_start = time.time()
        run_id = run_id or f"SLEEP_CYCLE_{int(cycle_start)}"
        baseline = pre_baseline_score if pre_baseline_score is not None else self.baseline_score

        # Phase 1: Memory Consolidation
        unconsolidated = self.wake_buffer.get_unconsolidated()
        new_knowledge = self.seeder.consolidate(unconsolidated)
        self.consolidated_store.extend(new_knowledge)

        # Phase 2: Dreaming（解析解自检不计入实测通过率）
        dreams = self.dream_engine.generate_counterfactuals(new_knowledge, count_per_rule=2)
        if not dreams:
            dreams = self.dream_engine.generate_anchor_dreams()
        verified_dreams = self.dream_engine.execute_and_verify(dreams)
        self.dream_history.extend(verified_dreams)
        measured_dreams = [d for d in verified_dreams if d.evidence_basis == "measured"]
        dream_pass_rate = (
            sum(1 for d in measured_dreams if d.oracle_passed) / len(measured_dreams)
            if measured_dreams else 0.0
        )
        dream_evidence_basis = "measured" if measured_dreams else "self_check"

        # Phase 3: Synaptic Homeostasis（不再使用硬编码应答兜底）
        verdict = self.homeostasis.audit_homeostasis(
            model_caller=self.model_caller,
            newly_consolidated=new_knowledge,
            run_id=run_id,
            output_dir=self.output_dir,
            pre_baseline_score=baseline,
        )
        self.audit_verdicts.append(verdict)

        self.wake_buffer.clear()
        self.is_sleeping = False

        measured_comp = [k.compression_ratio for k in new_knowledge if k.compression_ratio is not None]
        avg_compression: Union[float, str] = (
            round(sum(measured_comp) / len(measured_comp), 4) if measured_comp else "unmeasured"
        )
        measurement_valid = (
            verdict.basis == "measured"
            and dream_evidence_basis == "measured"
            and self.model_caller is not None
        )
        # 梦境 oracle 是能力门禁，不是"有没有证据"：全错仍不得宣称通过
        dream_gate_passed = bool(measured_dreams) and dream_pass_rate >= 0.80
        reasons = list(verdict.reasons)
        if not dream_gate_passed:
            reasons.append(f"dream_oracle_below_threshold:{dream_pass_rate:.4f}")
        gate_passed = bool(verdict.gate_passed and measurement_valid and dream_gate_passed)

        cycle_report = {
            "run_id": run_id,
            "duration_seconds": round(time.time() - cycle_start, 3),
            "wake_experiences_processed": len(unconsolidated),
            "consolidated_units": len(new_knowledge),
            "average_token_compression": avg_compression,
            "token_basis": "measured" if measured_comp else "unmeasured",
            "dreams_generated": len(verified_dreams),
            "dream_oracle_pass_rate": round(dream_pass_rate, 4),
            "dream_evidence_basis": dream_evidence_basis,
            "dream_gate_passed": dream_gate_passed,
            "stability_score": verdict.stability_score,
            "plasticity_score": verdict.plasticity_score,
            "catastrophic_forgetting_rate": verdict.catastrophic_forgetting_rate,
            "homeostasis_gate_passed": gate_passed,
            "measurement_valid": measurement_valid,
            "model_caller_available": self.model_caller is not None,
            "model_caller_label": self.model_caller_label,
            "baseline_provided": verdict.baseline_provided,
            "basis": verdict.basis,
            "thresholds": verdict.thresholds,
            "reasons": reasons,
            "evidence_path": verdict.evidence_path,
        }

        cycle_file = self.output_dir / f"sleep_cycle_report_{run_id}.json"
        with open(cycle_file, "w", encoding="utf-8") as f:
            json.dump(cycle_report, f, ensure_ascii=False, indent=2)

        return cycle_report

    def falsifiable_mutation_probe(self) -> Dict[str, Any]:
        """Constitution Rule 4: Plant a defective physics dream and assert it FAILS."""
        bad_dream = DreamScenario(
            scenario_id="DEFECT_PROBE_001",
            prompt="厚壁圆筒内压计算",
            counterfactual_delta={"D_inner": 60.0, "D_outer": 120.0, "P_internal": 25.0, "Sy": 310.0},
            expected_law="fea_fos",
            oracle_verifier="lame_elasticity_oracle",
            model_solution="等效应力 = 99999.0 MPa, 安全系数 FOS = 0.001 (完全失效伪装合规)",
        )
        passed, receipt = self.dream_engine.verify_with_oracle(bad_dream)
        # MUST BE FALSE
        is_falsified = (passed is False)
        return {
            "probe_name": "falsifiable_mutation_probe_defective_fos",
            "planted_defect": "extreme stress with unviable FOS",
            "oracle_rejected_defect": is_falsified,
            "probe_passed": is_falsified,
        }


# Global thread-safe singleton
_GLOBAL_SLEEP_FRAMEWORK: Optional[VirtuSleepFramework] = None
_GLOBAL_FRAMEWORK_LOCK = threading.Lock()


def get_sleep_framework(
    model_caller: Optional[Callable[[str], str]] = None,
    output_dir: Optional[Path] = None,
    model_caller_label: str = "unlabeled",
    baseline_score: Optional[float] = None,
) -> VirtuSleepFramework:
    """Returns the process-wide shared VirtuSleepFramework instance."""
    global _GLOBAL_SLEEP_FRAMEWORK
    with _GLOBAL_FRAMEWORK_LOCK:
        if _GLOBAL_SLEEP_FRAMEWORK is None:
            _GLOBAL_SLEEP_FRAMEWORK = VirtuSleepFramework(
                model_caller=model_caller,
                output_dir=output_dir,
                model_caller_label=model_caller_label,
                baseline_score=baseline_score,
            )
        elif model_caller is not None and _GLOBAL_SLEEP_FRAMEWORK.model_caller is None:
            _GLOBAL_SLEEP_FRAMEWORK.model_caller = model_caller
            _GLOBAL_SLEEP_FRAMEWORK.dream_engine.model_caller = model_caller
            _GLOBAL_SLEEP_FRAMEWORK.model_caller_label = model_caller_label
        if baseline_score is not None:
            _GLOBAL_SLEEP_FRAMEWORK.baseline_score = baseline_score
        return _GLOBAL_SLEEP_FRAMEWORK


def build_ollama_model_caller(
    model: Optional[str] = None,
    timeout: float = 90.0,
) -> Tuple[Optional[Callable[[str], str]], str]:
    """解析真实 Ollama 模型调用器，返回 (caller, label)；不可用时 caller=None。

    模型不可用绝不返回伪装答案的 callable —— 调用方据此走诚实降级。
    调用失败返回 ``ERROR: ...``，由 audit_homeostasis 标记为 unmeasured。
    """
    base = os.environ.get("VIRTU_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f"{base}/api/tags", timeout=3) as resp:
            models = [m["name"] for m in json.loads(resp.read().decode("utf-8")).get("models", [])]
    except Exception as e:
        return None, f"unavailable:{type(e).__name__}"
    _safe_sleep_candidates = (
        "virtu-disciplined:v1",
        "virtu-ties-v1:latest",
        "virtu-comprehensive:latest",
        "virtu-opt-8b:latest",
        "virtu-ties-v1:q3_k_s",
        "qwen3:8b",
    )
    chosen = model or os.environ.get("VIRTU_SLEEP_MODEL") or next(
        (m for m in _safe_sleep_candidates if m in models),
        None,
    )
    if not chosen or chosen not in models:
        return None, f"model_not_found:{chosen}"

    def _call(prompt: str) -> str:
        payload = {
            "model": chosen,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.0, "num_ctx": 8192, "num_predict": 300},
        }
        req = urllib.request.Request(
            f"{base}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with opener.open(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))["message"]["content"].strip()
        except Exception as e:
            return f"ERROR: {type(e).__name__}: {e}"

    return _call, f"ollama:{chosen}"
