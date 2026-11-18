---
name: multi-axis-machine-selection
description: Classify machining requirements and choose a feasible three-axis, four-axis, five-axis, lathe, or mill-turn machine; derive a stock blank and block production NC when evidence is incomplete.
metadata:
  version: "1.0.0"
  supported-consequence-levels: "manufacturing_planning execution_adjacent"
  short-description: Select a machine class and derive stock safely
---

# Multi-axis Machine Selection and Stock Planning

Use this before CAM generation whenever a job needs turning, 3/4/5-axis milling,
indexed 3+2 work, simultaneous rotary cutting, mill-turn operations, or subspindle
transfer.

## Required inputs

- Explicit machining features from the reviewed feature enum. Do not map ambiguous
  prose directly to a machine class.
- Finished-part bounding box in mm, material, stock shape, stock axis when cylindrical,
  and non-negative radial/side/end allowances.
- Machine travel in the intended setup orientation. If the oriented envelope is absent,
  use the conservative blank envelope and label that basis.
- For an exact production machine: machine, controller, postprocessor, and simulation
  artifacts with matching SHA-256 hashes; verified axes and travel; collision-free result;
  and a valid VERICUT Auto-Diff verdict.

## Feature-to-machine rules

- Three-axis milling requires X/Y/Z linear travel.
- Indexed four-axis work requires one rotary axis and explicit indexing capability.
- Simultaneous four-axis work requires at least one rotary axis and four simultaneous
  controlled axes.
- Five-axis 3+2 requires two rotary axes and verified indexing support. Rotary axes alone
  do not prove 3+2 capability.
- Simultaneous five-axis work requires two rotary axes and five simultaneous controlled
  axes. A 5-axis machine model or a positioning move is insufficient proof.
- Mill-turn work requires a turning spindle, live tooling, and the requested C/Y axes.
  Subspindle transfer additionally requires a verified subspindle.
- A machine with known insufficient travel or axes is excluded with a reason. Unknown
  capability remains unknown and cannot unlock production NC.

## Stock rules

- Derive stock from the finished-part envelope plus explicit allowance. Do not guess a
  stock size or infer allowance from a machine model.
- Check finite, positive dimensions and the stock-sanity gate.
- Compare machine travel against the oriented stock envelope where no tighter measured
  machining envelope is available.
- Report the derived dimensions, origin, material, units, and basis.

## Output and release gate

Return the requested machine class, feasible candidates, excluded candidates and reasons,
unknown capabilities, stock result, travel-check envelope, artifact evidence, and whether
controller code generation is allowed. Training profiles support class planning only.
Never mark a toolpath production-ready from a class recommendation, a simulator model,
or a passing static CNC parser. Missing, mismatched, blank, or unrendered simulation
evidence blocks release.

Use `audit_nc_capability` for a read-only first pass over an existing NC program. It can
distinguish literal rotary words in feed blocks from indexing moves and identify turning
cycles. Macro-variable axes stay unresolved. A static candidate never validates a post,
live tooling, subspindle transfer, or five-axis kinematics.
