---
name: hindsight
description: Semantic memory architecture for agents that retains, recalls, and reflects across sessions. Use for cross-task engineering memory, learning from outcomes, and preventing recurring errors.
---

# Hindsight Memory System

You have persistent multi-tiered memory powered by **Vectorize Hindsight** (arXiv:2512.12818).
Memory is organized into 4 types across dedicated banks (`virtu_cad_cam`, `virtu_cnc_machining`, `virtu_quality_audit`, `default`):

1. **World Facts**: Material physical parameters, machine tool constraints, engineering tolerances.
2. **Agent Experiences**: Detailed execution logs of CAD generation, CNC toolpaths, and simulation verifications.
3. **Entity Summaries**: Software profiles (SolidWorks, NX, CIMCO, AutoCAD), materials (SS304, AL7075, Ti-6Al-4V).
4. **Mental Models**: Evolving beliefs, learned failure modes, and self-reflection directives.

## Core Operations

### 1. Retain (Store Learning)
Always retain after discovering an important lesson, finding a bug workaround, or validating a machining parameter:
```python
memory.retain(
    bank_id="virtu_cad_cam",
    content="AL7075-T6 cutting speed 250-500 m/min with carbide endmill",
    context="learnings",
    tags=["materials", "speed"]
)
```

### 2. Recall (Retrieve Context)
Always recall relevant past experiences before generating models or toolpaths:
```python
memories = memory.recall(
    bank_id="virtu_cad_cam",
    query="SolidWorks equation manager double quote syntax",
    max_results=5
)
```

### 3. Reflect (Synthesize Cross-Session Strategy)
Synthesize historical learnings into high-level actionable directives:
```python
reflection = memory.reflect(
    bank_id="virtu_cnc_machining",
    query="Thin wall titanium alloy roughing strategy"
)
```
