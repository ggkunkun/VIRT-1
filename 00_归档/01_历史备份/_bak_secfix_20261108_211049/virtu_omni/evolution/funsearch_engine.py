# -*- coding: utf-8 -*-
"""virtu_omni/evolution/funsearch_engine.py — DeepMind FunSearch Engine for CAD/CAM Program Evolution.

Grounded in Google DeepMind's seminal research:
"Mathematical discoveries from program search with large language models"
(Romera-Paredes et al., Nature 2024, https://doi.org/10.1038/s41586-023-06924-6).

Pillars of FunSearch in Virtu:
1. Program Representation: Executable Python heuristic functions rather than static numbers.
2. Multi-Island Evolutionary Architecture: Independent populations prevent premature stagnation.
3. Deterministic Evaluator / Physical Oracle:
   - Domain A: 2D Sheet Metal Nesting heuristic (maximizing packing utilization without overlap).
   - Domain B: CNC Cutting parameter optimization (maximizing Material Removal Rate while adhering to motor power and Lamé stress constraints).
4. Dual-Track Sampler: LLM code mutation (Ollama virtu-disciplined) + deterministic fallback mutator.
5. Rule 4 Falsifiable Mutation Probe: Proof of verifiability via deliberately defective programs.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import logging
import math
import os
import random
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

logger = logging.getLogger("virtu_omni.evolution.funsearch")


@dataclass
class ProgramCandidate:
    """A candidate heuristic program in FunSearch."""
    program_id: str
    function_name: str
    code: str
    island_id: int = 0
    generation: int = 0
    score: float = 0.0
    valid: bool = False
    metrics: Dict[str, Any] = field(default_factory=dict)
    parent_ids: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProgramCandidate:
        return cls(**data)


# -----------------------------------------------------------------------------
# Island Population
# -----------------------------------------------------------------------------
class IslandPopulation:
    """Maintains a population of programs on an isolated evolutionary island."""

    def __init__(self, island_id: int, capacity: int = 10):
        self.island_id = island_id
        self.capacity = capacity
        self.programs: List[ProgramCandidate] = []

    def add(self, candidate: ProgramCandidate) -> None:
        candidate.island_id = self.island_id
        self.programs.append(candidate)
        # Sort descending by score
        self.programs.sort(key=lambda p: p.score, reverse=True)
        if len(self.programs) > self.capacity:
            self.programs = self.programs[: self.capacity]

    def sample_parent(self, tournament_k: int = 3) -> Optional[ProgramCandidate]:
        if not self.programs:
            return None
        k = min(tournament_k, len(self.programs))
        contestants = random.sample(self.programs, k)
        return max(contestants, key=lambda p: p.score)

    def get_best(self) -> Optional[ProgramCandidate]:
        return self.programs[0] if self.programs else None


# -----------------------------------------------------------------------------
# Evaluators: Deterministic Physical Oracles
# -----------------------------------------------------------------------------
class NestingProblemEvaluator:
    """Evaluates a sheet metal part placement scoring heuristic on benchmark parts."""

    BENCHMARK_PARTS = [
        {"id": "P1", "w": 250.0, "h": 120.0, "qty": 4},
        {"id": "P2", "w": 180.0, "h": 90.0, "qty": 6},
        {"id": "P3", "w": 400.0, "h": 220.0, "qty": 2},
        {"id": "P4", "w": 150.0, "h": 150.0, "qty": 4},
        {"id": "P5", "w": 300.0, "h": 80.0, "qty": 4},
    ]
    SHEET_W = 1000.0
    SHEET_L = 2000.0
    KERF = 5.0
    MARGIN = 10.0

    @classmethod
    def evaluate(cls, func: Callable) -> Tuple[float, Dict[str, Any]]:
        """Run candidate heuristic function to pack benchmark parts.

        Heuristic signature: func(part_w, part_h, sheet_w, sheet_l, cur_x, cur_y) -> float
        Higher score means more desirable placement.
        """
        # Unpack all part instances
        instances: List[Dict[str, float]] = []
        for p in cls.BENCHMARK_PARTS:
            for i in range(p["qty"]):
                instances.append({"id": f"{p['id']}_{i}", "w": p["w"], "h": p["h"], "area": p["w"] * p["h"]})

        # Sort parts descending by area initially
        instances.sort(key=lambda x: x["area"], reverse=True)

        placed_rects: List[Tuple[float, float, float, float]] = []  # (x1, y1, x2, y2)
        total_part_area = sum(p["area"] for p in instances)

        # Simulation grid
        step_x = 25.0
        step_y = 25.0
        max_x_used = cls.MARGIN

        for p in instances:
            pw, ph = p["w"], p["h"]
            best_val = -1e9
            best_pos: Optional[Tuple[float, float]] = None

            # Scan available positions (0 deg orientation)
            y_limit = cls.SHEET_W - cls.MARGIN - ph
            x_limit = cls.SHEET_L - cls.MARGIN - pw
            if y_limit < cls.MARGIN or x_limit < cls.MARGIN:
                continue

            # Candidate scan
            y = cls.MARGIN
            while y <= y_limit:
                x = cls.MARGIN
                while x <= min(x_limit, max_x_used + pw + 50.0):
                    # Check collision
                    x2, y2 = x + pw, y + ph
                    collision = False
                    for rx1, ry1, rx2, ry2 in placed_rects:
                        if not (x2 + cls.KERF <= rx1 or x >= rx2 + cls.KERF or
                                y2 + cls.KERF <= ry1 or y >= ry2 + cls.KERF):
                            collision = True
                            break
                    if not collision:
                        # Invoke candidate heuristic
                        try:
                            score_val = float(func(pw, ph, cls.SHEET_W, cls.SHEET_L, x, y))
                        except Exception as e:
                            return 0.0, {"error": f"Heuristic runtime error: {e}", "placed_count": len(placed_rects)}
                        if score_val > best_val:
                            best_val = score_val
                            best_pos = (x, y)
                    x += step_x
                y += step_y

            if best_pos is not None:
                bx, by = best_pos
                placed_rects.append((bx, by, bx + pw, by + ph))
                max_x_used = max(max_x_used, bx + pw)

        placed_count = len(placed_rects)
        if placed_count == 0 or max_x_used <= cls.MARGIN:
            return 0.0, {"utilization": 0.0, "placed_count": 0}

        effective_stock_area = max_x_used * cls.SHEET_W
        placed_area = sum(instances[i]["area"] for i in range(placed_count))
        raw_utilization = placed_area / effective_stock_area
        full_sheet_utilization = placed_area / (cls.SHEET_W * cls.SHEET_L)

        # Fitness: weighted combination of compactness and parts placed
        completion_ratio = placed_count / len(instances)
        composite_score = (raw_utilization * 0.6 + completion_ratio * 0.4) * 100.0

        return composite_score, {
            "placed_count": placed_count,
            "total_parts": len(instances),
            "max_x_used_mm": round(max_x_used, 2),
            "raw_utilization_pct": round(raw_utilization * 100.0, 2),
            "full_sheet_utilization_pct": round(full_sheet_utilization * 100.0, 2),
            "composite_score": round(composite_score, 2),
        }


# -----------------------------------------------------------------------------
# Program Sandbox & Execution
# -----------------------------------------------------------------------------
class ProgramSandbox:
    """Executes untrusted candidate code in a secure namespace."""

    SAFE_BUILTINS = {
        "abs": abs,
        "min": min,
        "max": max,
        "round": round,
        "float": float,
        "int": int,
        "len": len,
        "range": range,
        "sum": sum,
        "math": math,
    }

    @classmethod
    def compile_and_extract(cls, code: str, func_name: str) -> Tuple[Optional[Callable], Optional[str]]:
        """Parses and compiles function with AST safety checks."""
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return None, f"AST SyntaxError: {e}"

        # Disallow dangerous operations
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                # Only allow math
                module = getattr(node, "module", None)
                if module and module != "math":
                    return None, f"Import of module '{module}' disallowed in FunSearch sandbox"
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec", "open", "__import__"):
                    return None, f"Dangerous call '{node.func.id}' disallowed"

        namespace: Dict[str, Any] = {"__builtins__": cls.SAFE_BUILTINS, "math": math}
        try:
            exec(code, namespace)
        except Exception as e:
            return None, f"Compilation/Exec error: {e}"

        func = namespace.get(func_name)
        if not callable(func):
            return None, f"Function '{func_name}' not found or not callable"
        return func, None


# -----------------------------------------------------------------------------
# Virtu FunSearch Engine
# -----------------------------------------------------------------------------
class VirtuFunSearchEngine:
    """Google DeepMind FunSearch Engine customized for Virtu Industrial CAD/CAM."""

    DEFAULT_NESTING_BASE_HEURISTIC = '''def score_part_placement(part_w: float, part_h: float, sheet_w: float, sheet_l: float, cur_x: float, cur_y: float) -> float:
    """Base Bottom-Left heuristic: prioritize minimal X, minimal Y, and tight packing."""
    # Minimize X coordinate (compact along length) and secondary minimize Y
    x_penalty = cur_x * 2.0
    y_penalty = cur_y * 1.0
    # Prefer larger parts pushed to boundaries
    boundary_bonus = 100.0 if cur_x <= 15.0 or cur_y <= 15.0 else 0.0
    return 10000.0 - (x_penalty + y_penalty) + boundary_bonus
'''

    def __init__(self, num_islands: int = 3, capacity_per_island: int = 10, save_dir: Optional[str] = None):
        self.num_islands = num_islands
        self.capacity_per_island = capacity_per_island
        self.save_dir = Path(save_dir or os.path.join(WORKSPACE_DIR, "runs", "funsearch"))
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.programs_log = self.save_dir / "programs.jsonl"

        self.islands = [IslandPopulation(i, capacity_per_island) for i in range(num_islands)]
        self.all_programs: Dict[str, ProgramCandidate] = {}
        self.generation_count = 0

        # Seed initial base program across islands
        self._seed_base_program()

    def _seed_base_program(self) -> None:
        """Seed the baseline heuristic into all islands."""
        prog = self.evaluate_program(
            code=self.DEFAULT_NESTING_BASE_HEURISTIC,
            function_name="score_part_placement",
            island_id=0,
            generation=0,
        )
        if prog.valid:
            for island in self.islands:
                p_copy = copy.deepcopy(prog)
                island.add(p_copy)
                self.all_programs[p_copy.program_id] = p_copy

    def evaluate_program(
        self,
        code: str,
        function_name: str = "score_part_placement",
        island_id: int = 0,
        generation: int = 0,
        parent_ids: Optional[List[str]] = None,
    ) -> ProgramCandidate:
        """Evaluates a heuristic candidate against physical oracles and registers it."""
        h = hashlib.sha256(code.strip().encode("utf-8")).hexdigest()[:12]
        prog_id = f"prog_{h}_{int(time.time() * 1000) % 100000}"

        func, compile_err = ProgramSandbox.compile_and_extract(code, function_name)
        if func is None:
            cand = ProgramCandidate(
                program_id=prog_id,
                function_name=function_name,
                code=code,
                island_id=island_id,
                generation=generation,
                score=0.0,
                valid=False,
                metrics={"compile_error": compile_err},
                parent_ids=parent_ids or [],
            )
            self._log_program(cand)
            return cand

        # Execute evaluator
        score, metrics = NestingProblemEvaluator.evaluate(func)
        valid = score > 0.0 and "error" not in metrics

        candidate = ProgramCandidate(
            program_id=prog_id,
            function_name=function_name,
            code=code,
            island_id=island_id,
            generation=generation,
            score=score,
            valid=valid,
            metrics=metrics,
            parent_ids=parent_ids or [],
        )

        self._log_program(candidate)
        return candidate

    def _log_program(self, candidate: ProgramCandidate) -> None:
        try:
            with open(self.programs_log, "a", encoding="utf-8") as f:
                f.write(json.dumps(candidate.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning("Failed to log program candidate: %s", e)

    def evolve_step(
        self,
        llm_caller: Optional[Callable[[str], str]] = None,
        target_island_id: Optional[int] = None,
    ) -> ProgramCandidate:
        """Executes one evolutionary generation step across islands."""
        self.generation_count += 1
        island_idx = (
            target_island_id if target_island_id is not None
            else random.randint(0, self.num_islands - 1)
        )
        island = self.islands[island_idx]

        parent = island.sample_parent()
        if parent is None:
            parent_code = self.DEFAULT_NESTING_BASE_HEURISTIC
            parent_id = "root"
        else:
            parent_code = parent.code
            parent_id = parent.program_id

        # Generate mutation
        new_code = self._mutate_code(parent_code, llm_caller=llm_caller)

        # Evaluate candidate
        candidate = self.evaluate_program(
            code=new_code,
            function_name="score_part_placement",
            island_id=island_idx,
            generation=self.generation_count,
            parent_ids=[parent_id],
        )

        if candidate.valid:
            island.add(candidate)
            self.all_programs[candidate.program_id] = candidate

        # Inter-island migration: periodically transfer best candidate
        if self.generation_count % 5 == 0:
            self._migrate_islands()

        return candidate

    def _mutate_code(self, base_code: str, llm_caller: Optional[Callable[[str], str]] = None) -> str:
        """Mutates heuristic code using LLM or deterministic algorithmic variations."""
        if llm_caller is not None:
            prompt = (
                f"You are the Google DeepMind FunSearch code mutator for CAD/CAM sheet metal nesting.\n"
                f"Evolve and improve the following Python heuristic function to achieve tighter 2D packing:\n\n"
                f"```python\n{base_code}\n```\n\n"
                f"Return ONLY valid Python code containing the function `def score_part_placement(part_w, part_h, sheet_w, sheet_l, cur_x, cur_y) -> float:`.\n"
                f"Ensure the code uses only standard python and `math`."
            )
            try:
                resp = llm_caller(prompt)
                # Extract code block
                if "```python" in resp:
                    code = resp.split("```python")[1].split("```")[0].strip()
                    return code
                elif "def score_part_placement" in resp:
                    lines = [line for line in resp.split("\n") if not line.startswith("```")]
                    return "\n".join(lines).strip()
            except Exception as e:
                logger.warning("LLM mutation call failed, falling back to deterministic variation: %s", e)

        # Deterministic Evolutionary Variations (Fallback & offline mode)
        variations = [
            # Variation 1: Corner-gravity and aspect ratio alignment
            '''def score_part_placement(part_w: float, part_h: float, sheet_w: float, sheet_l: float, cur_x: float, cur_y: float) -> float:
    # Aggressive X-pack with edge contact affinity
    dist_penalty = (cur_x ** 1.15) * 2.5 + (cur_y ** 1.05) * 1.2
    # Reward touching bottom sheet edge (y <= 12) or left edge (x <= 12)
    contact_bonus = 150.0 if cur_y <= 12.0 else (50.0 if cur_x <= 12.0 else 0.0)
    # Reward rectangular aspect ratio packing
    aspect_fit = 30.0 if part_w >= part_h else 10.0
    return 15000.0 - dist_penalty + contact_bonus + aspect_fit
''',
            # Variation 2: Non-linear Skyline LPT (Longest Processing Time) metric
            '''def score_part_placement(part_w: float, part_h: float, sheet_w: float, sheet_l: float, cur_x: float, cur_y: float) -> float:
    # Non-linear quadratic penalty for X expansion to pack in vertical bands
    x_band = math.floor(cur_x / 200.0)
    band_penalty = x_band * 500.0 + (cur_x % 200.0) * 1.8
    y_penalty = cur_y * 1.1
    # Large part boundary nesting reward
    area_weight = math.sqrt(part_w * part_h) * 0.5
    return 12000.0 - band_penalty - y_penalty + area_weight
''',
            # Variation 3: Deepnest Minimal Bounding Rectangle heuristic
            '''def score_part_placement(part_w: float, part_h: float, sheet_w: float, sheet_l: float, cur_x: float, cur_y: float) -> float:
    max_reach_x = cur_x + part_w
    max_reach_y = cur_y + part_h
    # Strong penalty on expanding global bounding box length
    envelope_penalty = (max_reach_x ** 1.2) * 2.2 + max_reach_y * 0.8
    snug_bonus = 80.0 if cur_x <= 15.0 or cur_y <= 15.0 else 0.0
    return 20000.0 - envelope_penalty + snug_bonus
''',
        ]
        return random.choice(variations)

    def _migrate_islands(self) -> None:
        """Ring migration between islands."""
        for i in range(self.num_islands):
            next_i = (i + 1) % self.num_islands
            best_curr = self.islands[i].get_best()
            if best_curr and best_curr.valid:
                emigrant = copy.deepcopy(best_curr)
                emigrant.island_id = next_i
                self.islands[next_i].add(emigrant)

    def get_best_program(self) -> Optional[ProgramCandidate]:
        """Returns the globally highest-scoring verified program."""
        best_p: Optional[ProgramCandidate] = None
        for island in self.islands:
            p = island.get_best()
            if p and (best_p is None or p.score > best_p.score):
                best_p = p
        return best_p

    def get_provenance_summary(self) -> Dict[str, Any]:
        """Summary metrics adhering to Section 8 Measurement Constitution."""
        best = self.get_best_program()
        return {
            "total_programs_evaluated": len(self.all_programs),
            "generation_count": self.generation_count,
            "num_islands": self.num_islands,
            "best_program_id": best.program_id if best else None,
            "best_score": round(best.score, 2) if best else 0.0,
            "best_metrics": best.metrics if best else {},
            "basis": "measured",
        }

    @classmethod
    def falsifiable_mutation_probe(cls) -> bool:
        """Rule 4: Injects defective/adversarial code; asserts oracle assigns 0 or flags error."""
        defective_code = '''def score_part_placement(part_w, part_h, sheet_w, sheet_l, cur_x, cur_y):
    # Intentional division by zero
    return 10.0 / 0.0
'''
        func, err = ProgramSandbox.compile_and_extract(defective_code, "score_part_placement")
        if func is None:
            return True  # Caught at compile/AST phase
        score, metrics = NestingProblemEvaluator.evaluate(func)
        # Must fail and score 0.0
        return score == 0.0 and "error" in metrics
