"""Remote evaluation script to run on DAMODEL L40S.
Loads Qwen3-8B + trained CAD/CAM LoRA adapter and evaluates across 6 CAD/CAM/CNC software tools.
"""

import json
import os
import time
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

BASE_MODEL_PATH = "/root/public-storage/model/Qwen/Qwen3-8B"
ADAPTER_PATH = "/root/cad_cam_finetune/output_checkpoints/cad_cam_six_software_lora_final"
OUTPUT_FILE = "/root/cad_cam_finetune/eval_results.json"

TEST_PROMPTS = [
    {
        "software": "SOLIDWORKS 2021",
        "instruction": "请为SOLIDWORKS 2021编写参数化建模VBA宏，实现微型机轮模总成的参数化驱动（变量包括外径D_Outer=53, 内孔D_Bore=14, 三道变径弧槽半径R1=15, R2=12, R3=10, 槽底圆角R_GrooveArc=3）。"
    },
    {
        "software": "中文版NX12.0",
        "instruction": "请为Siemens NX 12.0编写Python Open API脚本，通过表达式驱动创建微型机轮模的旋转截面与三道环形减径槽布尔切除特征。"
    },
    {
        "software": "AutoCAD 2026",
        "instruction": "请使用AutoLISP编写AutoCAD 2026轮模工程图参数化绘制程序(c:DRAWWHEELMOLD)，包含中心线图层、轮廓剖面图层、ANSI31剖面线填充以及关键尺寸标注。"
    },
    {
        "software": "Vericut 9.6",
        "instruction": "请生成Vericut 9.6数控仿真工程配置(.opt)，设置Cr12MoV毛坯(D55x60)、三爪卡盘夹持、外圆粗车刀/圆弧成型刀/内孔镗刀刀具库，以及0.005mm过切干涉碰撞检测。"
    },
    {
        "software": "CIMCO Edit 2026",
        "instruction": "请编写适用于FANUC系统的CIMCO Edit参数化Macro B数控宏程序，定义#101-#108宏变量，使用G71外圆粗车循环与G70精车，精确加工轮模的三道R15/R12/R10圆弧槽。"
    },
    {
        "software": "斯沃数控仿真软件 (SSCNC)",
        "instruction": "请为斯沃数控仿真软件(SSCNC FANUC 0i-TF系统)编写轮模加工车间级实操与对刀手册，包括工件毛坯装夹、G54工件坐标系对刀步骤及刀尖方位号(刀沿方向T1~T4)设定。"
    }
]


def run_evaluation():
    print(f"Loading Base Model from: {BASE_MODEL_PATH}")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_PATH, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_PATH,
        torch_dtype=torch.bfloat16,
        device_map="cuda:0",
        trust_remote_code=True
    )
    print(f"Loading Fine-Tuned LoRA Adapter from: {ADAPTER_PATH}")
    model = PeftModel.from_pretrained(base_model, ADAPTER_PATH)
    model.eval()

    results = []
    print("\n====== RUNNING EVALUATION ACROSS 6 CAD/CAM/CNC SOFTWARE TOOLS ======\n")

    for i, test in enumerate(TEST_PROMPTS, 1):
        software = test["software"]
        prompt = test["instruction"]
        print(f"[{i}/6] Testing: {software} ...")

        messages = [
            {"role": "system", "content": "你是由Virtu模型深度强化的工业级CAD/CAM/CNC与数控宏程序高级工程专家，精通SOLIDWORKS、NX12、AutoCAD、Vericut、CIMCO与斯沃数控仿真软件的参数化建模与代码生成。"},
            {"role": "user", "content": prompt}
        ]

        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer([text], return_tensors="pt").to("cuda:0")

        start_t = time.time()
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=800,
                do_sample=False,
                temperature=0.0,
                pad_token_id=tokenizer.pad_token_id
            )
        elapsed = time.time() - start_t

        generated_ids = outputs[0][inputs.input_ids.shape[1]:]
        response = tokenizer.decode(generated_ids, skip_special_tokens=True).strip()

        print(f"  -> Generated {len(generated_ids)} tokens in {elapsed:.2f}s ({len(generated_ids)/elapsed:.1f} tok/s)")
        results.append({
            "software": software,
            "prompt": prompt,
            "response": response,
            "tokens": len(generated_ids),
            "latency_sec": elapsed
        })

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n[SUCCESS] Evaluation complete! Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    run_evaluation()
