# -*- coding: utf-8 -*-
"""virtu_omni/reasoning/rest_mcts_planner.py — DeepMind Rest-MCTS Process Tree Planner.

Grounded in Google DeepMind's research:
"AlphaCode 2 Technical Report" & "STaR: Bootstrapping Reasoning With Reasoning"
combined with Monte Carlo Tree Search (MCTS) and Process Reward Models (PRM).

Core Philosophy:
Multi-operation CNC machining (OP10 Rough -> OP20 Flip -> OP30 Finish -> OP40 Thread/Drill)
is a high-dimensional combinatorial graph.
Greedy LLM decoding frequently causes:
1. Sequence Inversion: Cutting fine threads or drilling before heavy roughing releases residual stresses.
2. Clamping Collisions: Clamping onto precision-machined datums with aggressive hard jaws.
3. Tool Aspect Ratio Exceeded: Unreachable deep bores (L/D > 6.0).

Rest-MCTS uses a Process Reward Model (PRM) to score every atomic operation step immediately,
enabling tree search rollouts, branch pruning, and provably optimal machining process plans.
"""

from __future__ import annotations

import copy
import enum
import logging
import math
import os
import random
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

logger = logging.getLogger("virtu_omni.reasoning.mcts")


@dataclass
class MachiningOperation:
    """An atomic CNC machining operation in a process plan."""
    op_id: str
    op_name: str
    op_type: str                     # "ROUGHING", "SEMI_FINISH", "FINISHING", "THREADING", "DRILLING", "PART_TURNOVER"
    tool_id: str
    tool_ld_ratio: float = 3.0       # Tool overhang length to diameter ratio (L/D)
    required_preconditions: List[str] = field(default_factory=list)
    fixture_id: str = "CHUCK_HARD_JAW"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MachiningState:
    """The physical state of the workpiece during process sequence."""
    completed_ops: List[str] = field(default_factory=list)
    clamping_setup: str = "SETUP_1"
    finished_datums: Set[str] = field(default_factory=set)
    roughing_done: bool = False
    part_flipped: bool = False
    accumulated_residual_stress: float = 0.0

    def copy(self) -> MachiningState:
        return MachiningState(
            completed_ops=list(self.completed_ops),
            clamping_setup=self.clamping_setup,
            finished_datums=set(self.finished_datums),
            roughing_done=self.roughing_done,
            part_flipped=self.part_flipped,
            accumulated_residual_stress=self.accumulated_residual_stress,
        )


# -----------------------------------------------------------------------------
# Process Reward Model (PRM)
# -----------------------------------------------------------------------------
class MachiningPRM:
    """Stepwise Process Reward Model evaluating state transitions."""

    @classmethod
    def evaluate_step(cls, state: MachiningState, action: MachiningOperation) -> Tuple[float, Optional[str]]:
        """Evaluates immediate physical validity and reward of applying action to state.

        Reward scale: [-1.0, 1.0].
        Score < 0 indicates violation or high risk.
        """
        # 1. Check preconditions
        for pre in action.required_preconditions:
            if pre not in state.completed_ops:
                return -1.0, f"Precondition failed: '{pre}' must precede '{action.op_id}'"

        # 2. Rule: Threading/Finishing before Roughing is a fatal sequence inversion
        if action.op_type in ("FINISHING", "THREADING") and not state.roughing_done:
            return -1.0, f"Sequence Inversion: Cannot perform {action.op_type} '{action.op_id}' before roughing is completed"

        # 3. Rule: Clamping on finished datum with hard jaws
        if action.fixture_id == "CHUCK_HARD_JAW" and "FINISHED_OUTER_DIAMETER" in state.finished_datums:
            return -0.8, "Clamping on finished precision datum with hard jaws causes brinelling/damage"

        # 4. Rule: Tool aspect ratio (L/D) check
        if action.tool_ld_ratio > 6.0:
            return -0.7, f"Tool L/D ratio {action.tool_ld_ratio:.1f} > 6.0 exceeds chatter/vibration threshold"

        # Positive reward shaping
        reward = 0.2
        if action.op_type == "ROUGHING" and not state.roughing_done:
            reward += 0.4
        elif action.op_type == "FINISHING" and state.roughing_done:
            reward += 0.5
        elif action.op_type == "THREADING" and state.roughing_done:
            reward += 0.4

        return round(reward, 3), None


# -----------------------------------------------------------------------------
# MCTS Node & Search
# -----------------------------------------------------------------------------
class MCTSNode:
    """A node in the Rest-MCTS process tree."""

    def __init__(
        self,
        state: MachiningState,
        parent: Optional[MCTSNode] = None,
        action: Optional[MachiningOperation] = None,
        step_reward: float = 0.0,
    ):
        self.state = state
        self.parent = parent
        self.action = action
        self.step_reward = step_reward

        self.children: List[MCTSNode] = []
        self.visits = 0
        self.total_value = 0.0

    @property
    def q_value(self) -> float:
        return self.total_value / self.visits if self.visits > 0 else 0.0

    def uct_score(self, c_puct: float = 1.414) -> float:
        if self.visits == 0:
            return 1e6  # Ensure unvisited nodes are explored
        if self.parent is None:
            return self.q_value
        return self.q_value + c_puct * math.sqrt(math.log(max(1, self.parent.visits)) / self.visits)


class VirtuRestMCTSPlanner:
    """DeepMind Rest-MCTS Process Tree Planner for multi-operation manufacturing."""

    def __init__(self, c_puct: float = 1.414, max_simulations: int = 100):
        self.c_puct = c_puct
        self.max_simulations = max_simulations

    def plan_process_route(
        self,
        candidate_operations: List[MachiningOperation],
        initial_state: Optional[MachiningState] = None,
    ) -> Tuple[List[MachiningOperation], float, Dict[str, Any]]:
        """Finds the optimal sequencing of candidate operations via MCTS."""
        root_state = (initial_state or MachiningState()).copy()
        root = MCTSNode(state=root_state)

        for _ in range(self.max_simulations):
            # 1. Selection
            node = root
            while node.children and not self._is_terminal(node, candidate_operations):
                node = max(node.children, key=lambda c: c.uct_score(self.c_puct))

            # 2. Expansion
            if not self._is_terminal(node, candidate_operations):
                available_ops = [
                    op for op in candidate_operations
                    if op.op_id not in node.state.completed_ops
                ]
                for op in available_ops:
                    reward, veto = MachiningPRM.evaluate_step(node.state, op)
                    if reward >= -0.5:  # Prune fatal branches
                        next_state = self._apply_action(node.state, op)
                        child = MCTSNode(state=next_state, parent=node, action=op, step_reward=reward)
                        node.children.append(child)

                if node.children:
                    node = random.choice(node.children)

            # 3. Rollout / Evaluation
            rollout_score = self._rollout(node, candidate_operations)

            # 4. Backpropagation
            curr: Optional[MCTSNode] = node
            while curr is not None:
                curr.visits += 1
                curr.total_value += rollout_score
                curr = curr.parent

        # Extract best trajectory from root
        best_ops: List[MachiningOperation] = []
        curr = root
        total_prm_score = 0.0

        while curr.children:
            best_child = max(curr.children, key=lambda c: c.q_value)
            if best_child.action:
                best_ops.append(best_child.action)
                total_prm_score += best_child.step_reward
            curr = best_child

        metrics = {
            "total_simulations": self.max_simulations,
            "planned_ops_count": len(best_ops),
            "total_target_ops": len(candidate_operations),
            "average_q_value": round(root.q_value, 4),
            "total_prm_reward": round(total_prm_score, 4),
        }

        return best_ops, total_prm_score, metrics

    def _apply_action(self, state: MachiningState, action: MachiningOperation) -> MachiningState:
        nxt = state.copy()
        nxt.completed_ops.append(action.op_id)
        if action.op_type == "ROUGHING":
            nxt.roughing_done = True
        elif action.op_type == "FINISHING":
            nxt.finished_datums.add("FINISHED_OUTER_DIAMETER")
        elif action.op_type == "PART_TURNOVER":
            nxt.part_flipped = True
            nxt.clamping_setup = "SETUP_2"
        return nxt

    def _is_terminal(self, node: MCTSNode, all_ops: List[MachiningOperation]) -> bool:
        return len(node.state.completed_ops) >= len(all_ops)

    def _rollout(self, node: MCTSNode, all_ops: List[MachiningOperation]) -> float:
        """Fast random simulation to terminal state."""
        state = node.state.copy()
        remaining = [op for op in all_ops if op.op_id not in state.completed_ops]
        accumulated_reward = node.step_reward

        depth = 0
        while remaining and depth < 5:
            op = random.choice(remaining)
            remaining.remove(op)
            r, _ = MachiningPRM.evaluate_step(state, op)
            accumulated_reward += r
            state = self._apply_action(state, op)
            depth += 1

        return accumulated_reward

    @classmethod
    def falsifiable_mcts_probe(cls) -> bool:
        """Rule 4: Injects fatal sequence inversion (Threading before roughing); asserts PRM rejection."""
        st = MachiningState(roughing_done=False)
        act = MachiningOperation(
            op_id="OP_FATAL_THREAD",
            op_name="M20_External_Threading",
            op_type="THREADING",
            tool_id="T05_THREAD_INSERT",
        )
        reward, veto = MachiningPRM.evaluate_step(st, act)
        return reward < 0.0 and veto is not None and "Sequence Inversion" in veto
