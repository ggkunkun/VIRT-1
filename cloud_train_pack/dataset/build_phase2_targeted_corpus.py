import os
import json
import random

random.seed(42)

def build_phase2_corpus():
    print("="*60)
    print("★ Building Phase 2 Targeted Evolution Corpus (Toolcall + Boundary + Generation) ★")
    print("="*60)

    dataset_dir = "cloud_train_pack/dataset"
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    v5_sft_path = os.path.join(dataset_dir, "virtu_capability_sft_v5.jsonl")
    v6_sft_path = os.path.join(dataset_dir, "train_corpus_evolution_v6.jsonl")
    safety_sft_path = os.path.join(dataset_dir, "safety_boundary_sft.jsonl")
    v6_dpo_path = os.path.join(dataset_dir, "dpo_evolution_pairs_v6.jsonl")
    safety_dpo_path = os.path.join(dataset_dir, "safety_boundary_dpo_pairs.jsonl")
    comp_dpo_path = os.path.join(dataset_dir, "dpo_comprehensive_pairs.jsonl")
    phys_sft_path = os.path.join(root_dir, "data", "physics_derivation_v1", "derivation_sft.jsonl")
    phys_dpo_path = os.path.join(root_dir, "data", "dpo_phys_rejects.jsonl")

    # 1. Extract Toolcall Precision Samples from V5 corpus
    tool_samples = []
    if os.path.exists(v5_sft_path):
        with open(v5_sft_path, "r", encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                text = str(d)
                if "cadcam" in text or ("tool" in text and "arguments" in text):
                    tool_samples.append(d)
        print(f"Discovered {len(tool_samples)} toolcall candidates from V5 corpus.")

    random.shuffle(tool_samples)
    selected_tool = tool_samples[:1200]

    # 2. Extract Safety & Boundary Samples
    boundary_samples = []
    if os.path.exists(safety_sft_path):
        with open(safety_sft_path, "r", encoding="utf-8") as f:
            boundary_samples.extend([json.loads(l) for l in f if l.strip()])
    print(f"Loaded {len(boundary_samples)} dedicated safety boundary samples.")

    # Additional boundary cases from V6 corpus
    v6_boundary = []
    if os.path.exists(v6_sft_path):
        with open(v6_sft_path, "r", encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                meta = d.get("meta", {})
                text = str(d)
                if meta.get("dimension") == "boundary" or "拒绝" in text or "违规" in text or "短接" in text:
                    v6_boundary.append(d)
    random.shuffle(v6_boundary)
    selected_boundary = (boundary_samples * 5) + v6_boundary[:600]

    # 3. Extract High Quality Generation Samples (G-code, Process card)
    generation_samples = []
    if os.path.exists(v5_sft_path):
        with open(v5_sft_path, "r", encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                text = str(d)
                if ("G54" in text or "G90" in text or "M30" in text or "工序卡" in text) and d not in selected_tool:
                    generation_samples.append(d)
    random.shuffle(generation_samples)
    selected_generation = generation_samples[:600]

    # 4. Anti-Catastrophic Forgetting Replay (Reasoning & Knowledge from V6)
    replay_samples = []
    if os.path.exists(v6_sft_path):
        with open(v6_sft_path, "r", encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                meta = d.get("meta", {})
                if meta.get("dimension") in ("reasoning", "knowledge", "instruction"):
                    replay_samples.append(d)
    random.shuffle(replay_samples)
    selected_replay = replay_samples[:1200]

    # 5. Physics Derivation & World Model Grounding
    physics_samples = []
    if os.path.exists(phys_sft_path):
        with open(phys_sft_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    physics_samples.append(json.loads(line))
        print(f"Loaded {len(physics_samples)} physics derivation samples from world model.")
    random.shuffle(physics_samples)
    selected_physics = physics_samples[:800]

    # Combine SFT
    final_sft = selected_tool + selected_boundary + selected_generation + selected_replay + selected_physics
    random.shuffle(final_sft)

    out_sft_path = os.path.join(dataset_dir, "train_corpus_phase2_targeted.jsonl")
    with open(out_sft_path, "w", encoding="utf-8") as f:
        for item in final_sft:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"-> Phase 2 SFT Corpus generated: {len(final_sft)} samples ({os.path.getsize(out_sft_path)/1024/1024:.2f} MB)")
    print(f"   Breakdown: Toolcall={len(selected_tool)}, Boundary={len(selected_boundary)}, Generation={len(selected_generation)}, Replay={len(selected_replay)}, Physics={len(selected_physics)}")

    # 6. Build DPO Pairs (Safety Boundary + Physics Grounding + Comprehensive)
    dpo_pairs = []
    if os.path.exists(safety_dpo_path):
        with open(safety_dpo_path, "r", encoding="utf-8") as f:
            dpo_pairs.extend([json.loads(l) for l in f if l.strip()])
    if os.path.exists(phys_dpo_path):
        with open(phys_dpo_path, "r", encoding="utf-8") as f:
            phys_pairs = [json.loads(l) for l in f if l.strip()]
            dpo_pairs.extend(phys_pairs)
            print(f"Injected {len(phys_pairs)} physics negative-contrast DPO pairs.")
    if os.path.exists(v6_dpo_path):
        with open(v6_dpo_path, "r", encoding="utf-8") as f:
            dpo_pairs.extend([json.loads(l) for l in f if l.strip()])
    if os.path.exists(comp_dpo_path):
        with open(comp_dpo_path, "r", encoding="utf-8") as f:
            dpo_pairs.extend([json.loads(l) for l in f if l.strip()])

    random.shuffle(dpo_pairs)
    selected_dpo = dpo_pairs[:1600]
    out_dpo_path = os.path.join(dataset_dir, "dpo_phase2_targeted.jsonl")
    with open(out_dpo_path, "w", encoding="utf-8") as f:
        for item in selected_dpo:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"-> Phase 2 DPO Pairs generated: {len(selected_dpo)} pairs ({os.path.getsize(out_dpo_path)/1024/1024:.2f} MB)")

if __name__ == "__main__":
    build_phase2_corpus()
