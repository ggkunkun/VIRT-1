#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
merge_lora.py — 把对话 / CAD / 其它 Virtu LoRA 合并进 Qwen3-8B 基座，产出单一权重目录。

为什么需要它:
  - 你的多个 LoRA(turing_conversational / cad_cam_six_software / tool_agent / omni / ug / damodel)
    基底都是 Qwen3-8B（peft 0.21.2, r=32, alpha=64），彼此兼容、可线性叠加。
  - 合并后只需一个目录作为 VIRTU_MODEL_PATH，启动快、离线可跑、无需运行时切换适配器。
  - 这就是"做出真·Virtu 模型"的最后一步：基座 + 你的真实 LoRA = 一个真正属于你的模型。

用法:
  # 默认：合对话 + CAD 两个核心 LoRA
  python merge_lora.py --base /path/to/Qwen3-8B

  # 把全部 6 个 Virtu LoRA 按默认权重叠加成一个"全能 Virtu"
  python merge_lora.py --base /path/to/Qwen3-8B --all

  # 自定义：指定若干 LoRA 与其权重
  python merge_lora.py --base /path/to/Qwen3-8B \
      --lora checkpoints/turing_conversational_lora --weight 1.0 \
      --lora checkpoints/cad_cam_six_software_lora --weight 1.0

  # 自定义输出目录
  python merge_lora.py --base /path/to/Qwen3-8B --out checkpoints/virtu_merged

说明:
  - 需要: torch transformers peft accelerate（在 GPU / 足够内存的机器上执行）。
  - 合并方式: 用 peft.add_weighted_adapter 把多个 LoRA 线性叠加后 merge_and_unload。
  - 注意: 合并会混合多种能力。若想运行时按意图独立切换，请不要合并，
    改用 virtu_real_backend 的 VIRTU_CONV_LORA / VIRTU_CAD_LORA 等环境变量。
"""

import os
import argparse
import json
import math
import hashlib


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    p = argparse.ArgumentParser(description="合并 Virtu 的多个 LoRA 到 Qwen3-8B 基座")
    p.add_argument("--base", required=True, help="Qwen3-8B 基座目录（与 LoRA 基底同版本）")
    p.add_argument("--lora", action="append", default=[], help="LoRA 目录（可重复）；不填则用 --all 或默认两项")
    p.add_argument("--weight", action="append", type=float, default=[], help="与 --lora 对应的权重（可重复）")
    p.add_argument("--all", action="store_true", help="合并全部 6 个 Virtu LoRA（默认权重见 DEFAULT_ALL）")
    p.add_argument("--out", default=os.path.join(here, "checkpoints", "virtu_merged"),
                   help="合并后输出目录")
    p.add_argument("--device", default="auto")
    p.add_argument("--mode", choices=["delta", "ties", "peft_linear"], default="delta",
                   help="合并算法：delta(推荐，无交叉项噪声直接求和) | ties(TIES共识符号) | peft_linear(粗近似含交叉项)")
    args = p.parse_args()

    if args.lora and args.weight and len(args.lora) != len(args.weight):
        raise SystemExit("[merge] --weight 数量必须与 --lora 数量相同")
    if any(not math.isfinite(weight) for weight in args.weight):
        raise SystemExit("[merge] --weight 必须是有限数值")
    if args.all and (args.lora or args.weight):
        raise SystemExit("[merge] --all 不能与 --lora/--weight 同时使用")
    out_path = os.path.abspath(args.out)
    if os.path.isdir(out_path) and os.listdir(out_path):
        raise SystemExit(f"[merge] 输出目录非空，拒绝覆盖: {out_path}")
    if os.path.abspath(args.base) == out_path:
        raise SystemExit("[merge] 输出目录不能与基座目录相同")

    # 延迟导入，确保本脚本在无 torch 的机器上也能被 --help 调用而不报错
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    # 默认的"对话 + CAD"两件套
    default_pair = [
        (os.path.join(here, "checkpoints", "turing_conversational_lora"), 1.0),
        (os.path.join(here, "checkpoints", "cad_cam_six_software_lora"), 1.0),
    ]
    # --all 的 4 件套（全部 r=32/alpha=64，linear 合并要求同 rank）
    # 排除项（实测 2026-10-30）：
    #   - tool_agent_lora_final: r=16/alpha=32，与其余 r=32 不兼容，
    #     单独保留为运行时可挂载适配器（或后续与新训的 virtu_toolcall_lora 一起用）。
    #   - damodel_l40s_cad_cam_lora: 与 cad_cam_six_software_lora 的
    #     training_receipt.json / adapter 权重完全一致（重复拷贝），双份叠加会过度放大 CAD 能力。
    # 对话权重略高，保住"像人聊天"的体感。
    DEFAULT_ALL = [
        (os.path.join(here, "checkpoints", "turing_conversational_lora"), 1.2),
        (os.path.join(here, "checkpoints", "cad_cam_six_software_lora"), 1.0),
        (os.path.join(here, "checkpoints", "omni_autonomous_agent_lora"), 0.8),
        (os.path.join(here, "checkpoints", "ug_teacher_guided_agent_lora"), 0.7),
    ]

    if args.all:
        pairs = [(p_, w) for p_, w in DEFAULT_ALL if os.path.isdir(p_)]
    elif args.lora:
        loras = args.lora
        weights = args.weight if args.weight else [1.0] * len(loras)
        pairs = list(zip(loras, weights))
    else:
        pairs = [(p_, w) for p_, w in default_pair if os.path.isdir(p_)]

    if not pairs:
        raise SystemExit("[merge] 没有找到任何可用 LoRA，请检查 --base 与 LoRA 路径")

    # 防御性预检：peft.add_weighted_adapter(combination_type="linear") 要求所有
    # 适配器 rank 一致，否则会抛出晦涩的维度错误。这里提前给出可读诊断。
    ranks = {}
    alpha_values = {}
    fingerprints = {}
    for lora_dir, weight in pairs:
        if not math.isfinite(weight):
            raise SystemExit(f"[merge] LoRA 权重必须是有限数值: {lora_dir}")
        cfg_path = os.path.join(lora_dir, "adapter_config.json")
        if not os.path.isfile(cfg_path):
            raise SystemExit(f"[merge] 缺少 adapter_config.json: {lora_dir}")
        with open(cfg_path, encoding="utf-8") as cf:
            adapter_cfg = json.load(cf)
        name = os.path.basename(os.path.normpath(lora_dir))
        rank, alpha = adapter_cfg.get("r"), adapter_cfg.get("lora_alpha")
        if not isinstance(rank, int) or rank <= 0 or not isinstance(alpha, (int, float)) or not math.isfinite(alpha) or alpha <= 0:
            raise SystemExit(f"[merge] {name} 的 rank/lora_alpha 缺失或无效")
        weight_files = sorted([*__import__("glob").glob(os.path.join(lora_dir, "*.safetensors")),
                               *__import__("glob").glob(os.path.join(lora_dir, "*.bin"))])
        if not weight_files:
            raise SystemExit(f"[merge] {name} 没有适配器权重文件")
        digest = hashlib.sha256()
        for weight_file in weight_files:
            with open(weight_file, "rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
        ranks[name] = rank
        alpha_values[name] = float(alpha)
        fingerprints[name] = digest.hexdigest()
    if len(set(ranks.values())) != 1:
        raise SystemExit(
            f"[merge] LoRA rank 不一致，无法 linear 合并: {ranks}\n"
            f"        请只选择同 rank 的适配器，或改用 --lora 显式指定子集。")
    bases = {json.load(open(os.path.join(lora_dir, "adapter_config.json"), encoding="utf-8")).get("base_model_name_or_path")
             for lora_dir, _ in pairs}
    if len(bases) > 1:
        raise SystemExit(f"[merge] LoRA 基座标识不一致: {sorted(str(x) for x in bases)}")

    # 逐字节相同的适配器是同一份训练权重的拷贝（实测 cad_cam_six_software_lora 与
    # damodel_l40s_cad_cam_lora 的 adapter_model.safetensors 同 md5）。把它们当两个
    # 独立能力叠加 = 该能力被放大两倍，而"两次训练"其实只产出过一个产物。
    dupes = {}
    for name, digest in fingerprints.items():
        dupes.setdefault(digest, []).append(name)
    repeated = [group for group in dupes.values() if len(group) > 1]
    if repeated:
        raise SystemExit(
            "[merge] 检测到内容完全相同的适配器，拒绝重复叠加:\n"
            + "\n".join("        " + " == ".join(group) for group in repeated)
            + "\n        只保留其中一个，或改用真正不同的训练产物。")

    print(f"[merge] 加载基座: {args.base}")
    base = AutoModelForCausalLM.from_pretrained(
        args.base, torch_dtype="auto", device_map=args.device
    )
    tok = AutoTokenizer.from_pretrained(args.base)

    names = []
    for i, (lora_dir, w) in enumerate(pairs):
        name = f"a{i}"
        print(f"[merge] 挂载 LoRA[{i}] {os.path.basename(lora_dir)} (weight={w})")
        if i == 0:
            model = PeftModel.from_pretrained(base, lora_dir, adapter_name=name)
        else:
            model.load_adapter(lora_dir, adapter_name=name)
        names.append(name)

    if args.mode == "delta":
        print(f"[merge] 使用 delta 纯净相加算法（无交叉项噪声）逐项合并 {len(pairs)} 个适配器...")
        # 逐项缩放与合并，杜绝 (B_new @ A_new) 产生的交叉项噪声 (B_i @ A_j, i!=j)
        for name, (_, w) in zip(names, pairs):
            model.set_adapter(name)
            for module in model.modules():
                if hasattr(module, "scaling") and isinstance(module.scaling, dict) and name in module.scaling:
                    module.scaling[name] *= w
            print(f"[merge] 烘焙适配器 {name} (weight={w}) 到基座...")
            model = model.merge_and_unload()
    elif args.mode == "ties":
        print(f"[merge] 使用 TIES-Merging 算法叠加 {len(names)} 个 LoRA -> 'virtu' 适配器")
        model.add_weighted_adapter(
            adapters=names,
            weights=[w for _, w in pairs],
            combination_type="ties",
            adapter_name="virtu",
        )
        model.set_adapter("virtu")
        print("[merge] 烘焙进基座 (merge_and_unload)...")
        model = model.merge_and_unload()
    else:
        print(f"[merge] 线性叠加 {len(names)} 个 LoRA -> 'virtu' 适配器")
        model.add_weighted_adapter(
            adapters=names,
            weights=[w for _, w in pairs],
            combination_type="linear",
            adapter_name="virtu",
        )
        model.set_adapter("virtu")
        print("[merge] 烘焙进基座 (merge_and_unload)...")
        model = model.merge_and_unload()

    os.makedirs(out_path, exist_ok=True)
    model.save_pretrained(out_path)
    tok.save_pretrained(out_path)
    receipt = {
        "status": "COMPLETED",
        "base_model": os.path.basename(os.path.normpath(args.base)),
        "merge_method": f"peft_add_weighted_adapter_{args.mode}",
        "mode": args.mode,
        "rank": next(iter(ranks.values())),
        "adapters": [
            {"name": os.path.basename(os.path.normpath(path)), "weight": weight,
             "rank": ranks[os.path.basename(os.path.normpath(path))],
             "alpha": alpha_values[os.path.basename(os.path.normpath(path))],
             "sha256": fingerprints[os.path.basename(os.path.normpath(path))]}
            for path, weight in pairs
        ],
    }
    with open(os.path.join(out_path, "merge_receipt.json"), "w", encoding="utf-8") as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2)
    print(f"[merge] 完成 -> {args.out}")
    print(f"[merge] 之后设置: VIRTU_BACKEND=transformers  VIRTU_MODEL_PATH={args.out}")
    print(f"[merge] 转 GGUF 离线跑(无 GPU): 用 llama.cpp/convert_hf_to_gguf.py 转换 {args.out}")


if __name__ == "__main__":
    main()
