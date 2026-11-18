"""Virtu Industrial Omni-Agent Autonomous Engine & Multi-Agent Team.

Modules:
- blueprint_inverse_engine: Inverse feature tree deduction and assembly from blueprints.
- self_reflection_optimizer: Code execution, self-reflection, and iterative optimization.
- headless_sandbox_verifier: In-the-loop virtual execution and kinematic collision verification.
- skill_writer_and_memory: Autonomous skill synthesis, dense-vector long-term memory, and web retrieval.
- agent_team: Collaborative Industrial Multi-Agent Team (Chief Architect, Modeler, Standards, CAM, Auditor, Memory).

NOTE: the public names below are resolved lazily (PEP 562). Importing this
package used to pull torch, the hindsight OpenAPI client and the RAG vector
store unconditionally, which cost 410 s of wall clock in a cold child process
(profiled with ``python -X importtime``). Callers that only need a leaf module
(e.g. ``agent_chain_executor`` importing ``process_memory_reclaimer``) paid the
whole bill and blew their 60 s hard timeout. ``from virtu_omni.agent import X``
still works unchanged; it now imports only the submodule that defines ``X``.
"""

_LAZY_EXPORTS = {
    "BlueprintInverseEngine": ".blueprint_inverse_engine",
    "SelfReflectionOptimizer": ".self_reflection_optimizer",
    "HeadlessSandboxVerifier": ".headless_sandbox_verifier",
    "SkillWriterAndMemory": ".skill_writer_and_memory",
    "BaseIndustrialAgent": ".agent_team",
    "ChiefArchitectAgent": ".agent_team",
    "ParametricModelingAgent": ".agent_team",
    "StandardsAndGDAgent": ".agent_team",
    "MachiningAndToolpathAgent": ".agent_team",
    "AuditorAndSandboxAgent": ".agent_team",
    "EvolutionAndMemoryAgent": ".agent_team",
    "IndustrialAgentTeam": ".agent_team",
    "REAL_ENGINEERING_RUNTIME": ".agent_team",
    "LEGACY_RUNTIME_TAG": ".agent_team",
    # 真实工程运行时（AGENTS.md §4 四项契约的落地实现）
    "SwarmCommander": ".swarm_orchestrator",
    "Blackboard": ".swarm_orchestrator",
    "AdversarialCritic": ".swarm_orchestrator",
    "META_SOP_STAGES": ".swarm_orchestrator",
    "AccessModality": ".adaptive_router",
    "AgentDispatcher": ".adaptive_router",
    "DispatchPlan": ".adaptive_router",
    "TargetDetector": ".adaptive_router",
    "DIFFICULTY_ROUTING_DISABLED": ".adaptive_router",
    "CADCAMAutonomousAgent": ".cadcam_autonomous_agent",
    "AgentExecutionReport": ".cadcam_autonomous_agent",
    "VirtuSuperAgent": ".super_agent",
    "SuperAgent": ".super_agent",
    "IndustrialSuperAgent": ".super_agent",
    "SuperAgentMode": ".super_agent",
    "SuperAgentExecutionResult": ".super_agent",
    "CircuitBreakerException": ".super_agent",
}

__all__ = list(_LAZY_EXPORTS)


def __getattr__(name: str):
    """Import the owning submodule on first attribute access (PEP 562)."""
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    value = getattr(import_module(module_name, __name__), name)
    globals()[name] = value  # cache so later lookups skip __getattr__
    return value


def __dir__():
    return sorted(__all__)
