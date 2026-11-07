"""Generate real-solver distillation records from the LIVE AutoCAD drawing.

Reads real dimension measurements via SOLIDWORKS/AutoCAD COM and emits
sim_out.jsonl ({inputs, outputs, family}) consumable by
build_worldmodel_sft.py --distill.

This is the concrete proof that the installed industrial software produces
ground-truth world_state data (not numpy approximations).
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import sim_adaptors as S


def main():
    out_path = os.path.join(ROOT, "data", "sft", "wm_sim_out_autocad.jsonl")

    # 1) real blueprint dims from the live AutoCAD drawing
    bp = S.acad_blueprint_dims()
    recs = []
    if bp:
        recs.append({
            "inputs": {
                "drawing": bp.get("drawing"),
                "task": "将蓝图中的真实标注尺寸结构化，输出世界状态 blueprint_dims_mm",
            },
            "outputs": {
                "blueprint_dims_mm": bp["blueprint_dims_mm"],
                "n_dims": bp["n_dims"],
            },
            "family": "blueprint_dims",
        })
        print(f"[autocad] real dims extracted: n={bp['n_dims']}, drawing={bp.get('drawing')}")
    else:
        print("[autocad] no live AutoCAD dims (app not running?) -> skip")

    # 2) (future) SW mass properties / FEA / VERICUT autodiff slots are code-ready
    #    in sim_adaptors; they activate when those apps are open. For now we only
    #    have AutoCAD live, so we emit what we can prove.

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[ok] wrote {len(recs)} real-distill records -> {out_path}")


if __name__ == "__main__":
    main()
