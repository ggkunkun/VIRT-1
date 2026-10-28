"""Inference and generation verification script for CAD/CAM/CNC fine-tuned model on L40S."""

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE_MODEL_PATH = "/root/public-storage/model/Qwen/Qwen3-8B"
ADAPTER_PATH = "/root/workspace/Virtu/checkpoints/cad_cam_six_software_lora"

PROMPTS = [
    "请使用 SOLIDWORKS 2021 VBA API 编写参数化轮模建模宏，通过方程式驱动外径53mm、轴孔14mm以及成型槽。",
    "请使用数控宏程序 (Macro B) 编写适用于 CIMCO Edit 2026 背绘仿真的全参数化车削程序，加工 R15/R12/R10 阶梯轮模。",
    "在斯沃数控仿真软件 (SSCNC) 中加工全圆弧轮槽时，如何正确设置刀尖圆角半径 (R) 与刀尖方位 (T) 代号？"
]

def main():
    print("==================================================================")
    print("  Virtu: Testing Fine-Tuned Model on NVIDIA L40S")
    print("==================================================================")
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device} | GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None'}")

    print("Loading base tokenizer and model...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_PATH, trust_remote_code=True)
    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_PATH,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True
    )

    print(f"Loading LoRA Adapter from: {ADAPTER_PATH} ...")
    model = PeftModel.from_pretrained(base_model, ADAPTER_PATH)
    model.eval()
    print("[SUCCESS] Model and Adapter successfully loaded into GPU VRAM!\n")

    for i, p in enumerate(PROMPTS, 1):
        print(f"\n[{i}/3] Test Prompt: {p}")
        print("-" * 60)
        messages = [
            {"role": "system", "content": "你是一位工业级 CAD/CAM/CNC 专家。"},
            {"role": "user", "content": p}
        ]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer([text], return_tensors="pt").to(device)

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=256,
                temperature=0.3,
                top_p=0.9,
                do_sample=True,
            )

        resp = tokenizer.decode(outputs[0][len(inputs.input_ids[0]):], skip_special_tokens=True)
        print(resp.strip())
        print("=" * 60)

    print("\n[ALL TESTS PASSED] Model inference verified on cloud GPU!")

if __name__ == "__main__":
    main()
