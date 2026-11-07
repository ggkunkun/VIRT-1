"""Finalise virtu_eval/arms.json: absolute paths that exist, and a self-check."""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "virtu_eval", "arms.json")


def abspath(rel):
    return os.path.join(ROOT, rel).replace("\\", "/")


def main():
    with open(P, encoding="utf-8") as f:
        arms = json.load(f)

    arms["virtu_lora_cadcam"]["model_path"] = abspath("checkpoints/_base_qwen3_8b")
    arms["virtu_lora_cadcam"]["adapter_path"] = abspath("checkpoints/cad_cam_six_software_lora")
    arms["qwen3_8b_base"]["model_path"] = abspath("checkpoints/_base_qwen3_8b")
    arms["virtu_merged_v3"]["model_path"] = abspath("checkpoints/virtu_cad_cam_merged_v3")
    arms["vision_local_qwen3vl2b"]["model_path"] = abspath("models/Qwen3-VL-2B-Instruct")

    # the transformers path on this box measured ~1.8 tok/s (Windows bnb NF4),
    # so a full 240-case sweep there is not affordable; cap the budget instead.
    for key in ("virtu_lora_cadcam", "qwen3_8b_base", "virtu_merged_v3"):
        arms[key]["max_tokens_cap"] = 256
        arms[key]["note"] = (arms[key].get("note", "") +
                             " | transformers+NF4 路径实测 ~1.8 tok/s（Windows bnb 反量化慢），"
                             "token 预算已收紧").strip(" |")

    with open(P, "w", encoding="utf-8") as f:
        json.dump(arms, f, ensure_ascii=False, indent=2)

    ok = True
    print("arm                     kind              path / url                            exists")
    for key, spec in arms.items():
        if spec["kind"] in ("hf_local", "hf_vision"):
            p = spec["model_path"]
            e = os.path.exists(p)
            a = spec.get("adapter_path")
            if a:
                e = e and os.path.exists(a)
                extra = f" adapter={os.path.exists(a)}"
            else:
                extra = ""
            ok = ok and e
            print(f"{key:24s} {spec['kind']:17s} {p:<34s} {e}{extra}")
        else:
            print(f"{key:24s} {spec['kind']:17s} {spec.get('base_url',''):<34s} n/a")
    print("\nALL PATHS OK" if ok else "\nSOME PATHS MISSING")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
