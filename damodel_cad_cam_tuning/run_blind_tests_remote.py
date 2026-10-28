"""Run 3 Tough Industrial Blind Tests on L40S using the fine-tuned Wish-Style LoRA Model.

Blind Test 1: 航天高压压气机 12 叶片闭式整体叶轮 (Ti-6Al-4V)
Blind Test 2: 双色精密车灯面罩注塑模具滑块侧抽芯与斜顶机构 (P20 / Cr12MoV)
Blind Test 3: 重载工业齿轮箱行星减速机太阳轮参数化宏编程 (20CrMnTi)
"""

import json
import time
import os
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

BASE_MODEL_PATH = "/root/public-storage/model/Qwen/Qwen3-8B"
ADAPTER_PATH = "/root/cad_cam_finetune/output_checkpoints/cad_cam_six_software_lora_final"
OUTPUT_FILE = "/root/cad_cam_finetune/blind_test_results.json"

BLIND_TEST_PROMPTS = [
    {
        "id": "BLIND_TEST_01_AEROSPACE_IMPELLER",
        "title": "航天钛合金Ti-6Al-4V闭式12叶片高压压气机整体叶轮5轴全流程",
        "prompt": "【许愿式工业制造求解】我想制造一款航空高压压气机级12叶片闭式整体叶轮（材质Ti-6Al-4V），要求叶轮外轮廓最大外径D180mm，轮毂根部外径D60mm，轴向总高55mm，叶片均布且具有38度空间扭曲流道，叶根倒圆角R3mm。请全面输出：\n1) SOLIDWORKS 2021或NX 12.0的参数化建模驱动核心脚本（流道曲面造型与圆周阵列）；\n2) AutoCAD 2026二维工程图出图核心指令（规范图层管理与关键尺寸标注）；\n3) Vericut 9.6五轴机床仿真工程配置（开启OptiPath/Force物理力学切削优化与五轴防过切0.003mm校验）；\n4) CIMCO Edit 2026适用的参数化五轴宏程序框架（Macro B坐标系与刀轴矢量计算）；\n5) 斯沃数控仿真软件（SSCNC 7.2）车铣复合/五轴中心的工件装夹与对刀规范。"
    },
    {
        "id": "BLIND_TEST_02_INJECTION_MOLD_TOOLING",
        "title": "双色精密车灯面罩注塑模具滑块侧抽芯与斜顶机构",
        "prompt": "【许愿式工业制造求解】许愿设计一套双色精密车灯面罩注塑模具的滑块侧抽芯与斜顶机构（动定模仁材质P20，耐磨块材质Cr12MoV，外形基准D140x85mm，侧向抽芯行程25mm，斜顶倾角8度，过渡圆角R2.5mm）。请全面给出：\n1) NX 12.0 Mold Wizard或SOLIDWORKS Plastics模流与机构参数化建模代码；\n2) AutoCAD 2026模具总装装配图的参数化几何约束与图层图符标注；\n3) Vericut 9.6模仁高光微细铣削的AUTO-DIFF偏差比对与干涉容差配置；\n4) CIMCO Edit 2026模仁深腔微孔摆线铣削与断屑啄钻参数化宏程序；\n5) 斯沃数控仿真立式加工中心（FANUC 0i-MF系统）对刀仪寻边器校准G54坐标系步骤。"
    },
    {
        "id": "BLIND_TEST_03_PLANETARY_SUN_GEAR",
        "title": "重载工业齿轮箱行星减速机太阳轮齿轮轴参数化全闭环",
        "prompt": "【许愿式工业制造求解】针对重载工业齿轮箱行星减速机构中的太阳轮与齿轮轴（材质20CrMnTi渗碳淬火，外径D110mm，内轴孔D35mm，齿宽60mm，齿根倒圆R2.0mm，8处传动齿形减重孔）。请提供：\n1) SOLIDWORKS 2021 EquationMgr全局变量联动与齿形特征参数化宏；\n2) AutoCAD 2026 AutoLISP自动标注齿圈齿顶圆、分度圆、齿根圆公差；\n3) Vericut 9.6齿形仿真的机床运动学树配置与Force切削载荷抑制；\n4) CIMCO Edit 2026 FANUC G71/G70轮廓宏循环与动态进给调节；\n5) 斯沃数控车削中心的软爪镗削配车与G54试切对刀手册。"
    }
]


def run_blind_tests():
    print(f"Loading Base Model: {BASE_MODEL_PATH}")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_PATH, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_PATH,
        torch_dtype=torch.bfloat16,
        device_map="cuda:0",
        trust_remote_code=True
    )

    print(f"Loading Reinforced LoRA Adapter: {ADAPTER_PATH}")
    model = PeftModel.from_pretrained(base_model, ADAPTER_PATH)
    model.eval()

    results = []
    print("\n====== EXECUTING 3 HARD INDUSTRIAL BLIND TESTS ======\n")

    for i, test in enumerate(BLIND_TEST_PROMPTS, 1):
        test_id = test["id"]
        title = test["title"]
        prompt = test["prompt"]
        print(f"[{i}/3] Running Blind Test: {title} ...")

        messages = [
            {
                "role": "system",
                "content": "你是由Virtu模型深度强化的工业级CAD/CAM/CAE与数控编程专家，精通SOLIDWORKS、NX12、AutoCAD、Vericut、CIMCO与斯沃数控仿真软件的参数化建模与全生命周期工程求解。"
            },
            {"role": "user", "content": prompt}
        ]

        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer([text], return_tensors="pt").to("cuda:0")

        t0 = time.time()
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=1500,
                do_sample=False,
                temperature=0.0,
                pad_token_id=tokenizer.pad_token_id
            )
        elapsed = time.time() - t0

        gen_tokens = outputs[0][inputs.input_ids.shape[1]:]
        response = tokenizer.decode(gen_tokens, skip_special_tokens=True).strip()

        print(f"  -> Generated {len(gen_tokens)} tokens in {elapsed:.2f}s ({len(gen_tokens)/elapsed:.1f} tok/s)")
        results.append({
            "test_id": test_id,
            "title": title,
            "prompt": prompt,
            "response": response,
            "tokens": len(gen_tokens),
            "latency_sec": elapsed
        })

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n[SUCCESS] Blind tests complete! Results saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    run_blind_tests()
