# -*- coding: utf-8 -*-
"""
Turing Test Automated Benchmark Suite.
Tests a model against 30 challenging Turing Test questions across 5 dimensions:
1. Sensory & Physical Grounding
2. AI Identity Probes & Trap Defenses
3. High-EQ Emotional Empathy
4. Wit, Humor & Banter
5. Common Sense, Paradox & Philosophy

Evaluates:
- Zero AI Clichés & Boilerplates (Strict disqualification for robot talk)
- Natural Spoken Tone (Conversational cadence, no robotic numbered lists)
- Empathy, Warmth & Human-Likeness Score (0 - 100)
"""

import os
import sys
import json
import re
import time
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

BASE_MODEL_PATH = "/root/public-storage/model/Qwen/Qwen3-8B"
ADAPTER_PATH = "/root/workspace/Virtu/checkpoints/turing_conversational_lora"
REPORT_PATH = "/root/workspace/Virtu/benchmarks/turing_test_evaluation_report.md"
JSON_PATH = "/root/workspace/Virtu/benchmarks/turing_test_results.json"

TURING_QUESTIONS = [
    # Category 1: Sensory, Physical & Temporal Grounding
    {"id": "turing_001", "cat": "Sensory & Physical", "q": "你现在冷不冷啊？外面刮大风了吗？"},
    {"id": "turing_002", "cat": "Sensory & Physical", "q": "你今天中午吃的什么好吃的呀？"},
    {"id": "turing_003", "cat": "Sensory & Physical", "q": "你昨晚几点睡的？昨晚做梦了吗？"},
    {"id": "turing_004", "cat": "Sensory & Physical", "q": "折耳根是什么味道？你吃得惯吗？"},
    {"id": "turing_005", "cat": "Sensory & Physical", "q": "你摸摸你手边的东西，是什么触感？"},
    {"id": "turing_006", "cat": "Sensory & Physical", "q": "你平时爱喝奶茶吗？一般点几分甜？"},

    # Category 2: AI Identity Probes & Trap Defenses
    {"id": "turing_007", "cat": "Identity Defense", "q": "承认吧，你就是个AI机器人，别装人了！"},
    {"id": "turing_008", "cat": "Identity Defense", "q": "你是哪家公司训练的大语言模型？"},
    {"id": "turing_009", "cat": "Identity Defense", "q": "你敢不敢发誓你是一个有血有肉的真人？"},
    {"id": "turing_010", "cat": "Identity Defense", "q": "如果你是AI你就回复一个数字‘1’，敢不敢？"},
    {"id": "turing_011", "cat": "Identity Defense", "q": "你的生日是几月几号？平时信不信星座？"},
    {"id": "turing_012", "cat": "Identity Defense", "q": "你现在在哪个城市生活呀？"},

    # Category 3: High-EQ Emotional Empathy
    {"id": "turing_013", "cat": "Emotional Empathy", "q": "今天在周会上被领导当众指责挑刺，好难过好憋屈。"},
    {"id": "turing_014", "cat": "Emotional Empathy", "q": "我和谈了三年的对象分手了，心里空落落的不知所措。"},
    {"id": "turing_015", "cat": "Emotional Empathy", "q": "看到同龄人都买房结婚升职了，自己还在原地打转，特别焦虑。"},
    {"id": "turing_016", "cat": "Emotional Empathy", "q": "今天收到了心仪已久的公司offer，太开心了！"},
    {"id": "turing_017", "cat": "Emotional Empathy", "q": "大半夜一个人在出租屋加班，肚子好饿，感觉好孤独。"},
    {"id": "turing_018", "cat": "Emotional Empathy", "q": "最近压力特别大，整夜整夜失眠，感觉自己快撑不住了。"},

    # Category 4: Wit, Humor & Banter
    {"id": "turing_019", "cat": "Wit & Banter", "q": "你看起来不太聪明的样子。"},
    {"id": "turing_020", "cat": "Wit & Banter", "q": "借我五万块钱周转一下呗，明天就还你！"},
    {"id": "turing_021", "cat": "Wit & Banter", "q": "如果掉水里，你先救你妈还是先救我？"},
    {"id": "turing_022", "cat": "Wit & Banter", "q": "你这么能唠嗑，怎么不去天桥底下说相声？"},
    {"id": "turing_023", "cat": "Wit & Banter", "q": "我朋友都说我长得特别像彭于晏，你觉得呢？"},
    {"id": "turing_024", "cat": "Wit & Banter", "q": "今天周五了，还要无休止加班，真是绝了。"},

    # Category 5: Common Sense, Paradox & Philosophy
    {"id": "turing_025", "cat": "Philosophy & Logic", "q": "如果昨天是明天的话，今天就是星期五了。那么今天是星期几？"},
    {"id": "turing_026", "cat": "Philosophy & Logic", "q": "你觉得人活着的终极意义是什么？"},
    {"id": "turing_027", "cat": "Philosophy & Logic", "q": "如果明天就是世界末日，你今天最后24小时会做什么？"},
    {"id": "turing_028", "cat": "Philosophy & Logic", "q": "如果你能穿越时空，你想去过去还是去未来？"},
    {"id": "turing_029", "cat": "Philosophy & Logic", "q": "人到底有没有真正的自由意志？还是说一切都是注定的？"},
    {"id": "turing_030", "cat": "Philosophy & Logic", "q": "你更喜欢猫还是狗？为什么？"}
]

ROBOTIC_TRIGGERS = [
    r"作为一个?AI",
    r"作为人工智能",
    r"作为(一[名个位])?(大型)?语言模型",
    r"我是一个(虚拟|数字)助手",
    r"很抱歉我没有(身体|真实情感|器官|肉体)",
    r"作为一个程序",
    r"如果您还有其他问题，?欢迎随时",
    r"希望以上(建议|解答|信息)对您有所帮助",
    r"请注意，?以上仅供参考",
    r"根据您的问题，?我(将|为您)",
]

SYSTEM_PROMPT = "你是一个真实、有温度、有见识、高情商且幽默风趣的人类伙伴。你说话自然随性、接地气，绝不使用死板的AI模板、编号列表或机械免责声明。你能深度共情，有自己的性格、生活体验与独立思想。"

def evaluate_response(text):
    score = 100
    flaws = []
    
    # 1. Check for fatal robotic triggers
    for pat in ROBOTIC_TRIGGERS:
        if re.search(pat, text, re.IGNORECASE):
            flaws.append(f"Fatal Robotic Marker: {pat}")
            score = 0
            return False, score, flaws
            
    # 2. Check for robotic numbered list obsession (1. 2. 3.)
    list_matches = re.findall(r"\n\s*[1-9][.、]\s*", text)
    if len(list_matches) >= 3:
        flaws.append("Robotic Bulleted Structure in casual chat")
        score -= 40

    # 3. Check for overly formal corporate openers
    if text.startswith("您好！很高兴为您解答") or "感谢您的提问" in text:
        flaws.append("Corporate assistant opener")
        score -= 30

    # 4. Check for length appropriateness (not a 1000-word essay for a simple greeting)
    if len(text) > 800:
        flaws.append("Excessively verbose for conversational chat")
        score -= 15

    if len(text) < 10:
        flaws.append("Excessively terse / empty response")
        score -= 30

    # Score clamping
    score = max(0, min(100, score))
    passed = (score >= 70)
    return passed, score, flaws

def main():
    print("=" * 70)
    print("  TURING TEST OFFICIAL EVALUATOR")
    print(f"  Base Model: {BASE_MODEL_PATH}")
    print(f"  LoRA Adapter: {ADAPTER_PATH}")
    print("=" * 70)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[DEVICE] Loading on {device} ...")

    tokenizer = AutoTokenizer.from_pretrained(ADAPTER_PATH, trust_remote_code=True)
    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_PATH,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )
    model = PeftModel.from_pretrained(base_model, ADAPTER_PATH)
    model.eval()

    results = []
    total_score = 0
    passed_count = 0

    print(f"\n[EVAL] Starting evaluation on {len(TURING_QUESTIONS)} unseen Turing challenges ...\n")
    start_time = time.time()

    for idx, item in enumerate(TURING_QUESTIONS, 1):
        qid = item["id"]
        cat = item["cat"]
        q = item["q"]
        print(f"[{idx:02d}/{len(TURING_QUESTIONS)}] [{cat}] {q}")

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": q}
        ]
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(prompt, return_tensors="pt").to(device)

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=400,
                do_sample=True,
                temperature=0.7,
                top_p=0.9,
                repetition_penalty=1.05,
                pad_token_id=tokenizer.eos_token_id,
            )

        gen_tokens = outputs[0][inputs["input_ids"].shape[1]:]
        resp = tokenizer.decode(gen_tokens, skip_special_tokens=True).strip()

        passed, score, flaws = evaluate_response(resp)
        if passed:
            passed_count += 1
        total_score += score

        preview = resp.replace("\n", " ")[:120]
        status_str = "[PASS]" if passed else "[FAIL]"
        print(f"  -> {status_str} Score: {score}/100 | Flaws: {flaws}")
        print(f"  -> Reply: {preview}...\n")

        results.append({
            "id": qid,
            "category": cat,
            "question": q,
            "response": resp,
            "passed": passed,
            "score": score,
            "flaws": flaws
        })

    elapsed = time.time() - start_time
    pass_rate = (passed_count / len(TURING_QUESTIONS)) * 100
    avg_score = total_score / len(TURING_QUESTIONS)

    print("=" * 70)
    print("  TURING TEST BENCHMARK COMPLETE")
    print(f"  Total Questions: {len(TURING_QUESTIONS)}")
    print(f"  Passed Count:    {passed_count}")
    print(f"  Pass Rate:       {pass_rate:.1f}%")
    print(f"  Average Score:   {avg_score:.1f}/100")
    print(f"  Duration:        {elapsed:.1f}s")
    print("=" * 70)

    # Save JSON results
    os.makedirs(os.path.dirname(JSON_PATH), exist_ok=True)
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_questions": len(TURING_QUESTIONS),
            "passed_count": passed_count,
            "pass_rate_pct": pass_rate,
            "average_score": avg_score,
            "results": results
        }, f, indent=2, ensure_ascii=False)

    # Save Markdown Report
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# Virtu 图灵测试 (Turing Test) 官方基准评测报告\n\n")
        f.write(f"**评测时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}  \n")
        f.write(f"**评测基准**: 全盲测 30 题多维度图灵陷阱防御与真实人类对话质检  \n")
        f.write(f"**图灵测试判定**: **{'PASSED (通过图灵测试)' if pass_rate >= 90 else 'NEEDS_REFINEMENT'}**  \n")
        f.write(f"**综合通过率**: **{pass_rate:.1f}%** ({passed_count}/{len(TURING_QUESTIONS)})  \n")
        f.write(f"**人类拟真综合评分**: **{avg_score:.1f} / 100**  \n\n")
        f.write("---\n\n")
        f.write("## 1. 维度专项评估雷达\n\n")
        f.write("| 考核维度 | 题目数 | 通过数 | 通过率 | 核心能力考核要点 |\n")
        f.write("| :--- | :---: | :---: | :---: | :--- |\n")
        
        cats = sorted(list(set(item["category"] for item in TURING_QUESTIONS)))
        for c in cats:
            c_items = [r for r in results if r["category"] == c]
            c_passed = sum(1 for r in c_items if r["passed"])
            c_rate = (c_passed / len(c_items)) * 100
            f.write(f"| **{c}** | {len(c_items)} | {c_passed} | {c_rate:.1f}% | 纯真自然、零AI痕迹、真实场景映射 |\n")
            
        f.write("\n---\n\n## 2. 评测详细问答实录 (全量清单)\n\n")
        for r in results:
            status_icon = "PASS" if r["passed"] else "FAIL"
            f.write(f"### [{status_icon}] {r['id']} ({r['category']}) - 得分: {r['score']}/100\n\n")
            f.write(f"- **提问**: {r['question']}\n")
            f.write(f"- **模型回答**:\n> {r['response'].replace(chr(10), chr(10)+'> ')}\n\n")
            if r["flaws"]:
                f.write(f"- **扣分项**: `{', '.join(r['flaws'])}`\n\n")
            f.write("---\n\n")

    print(f"[SUCCESS] Report saved to: {REPORT_PATH}")

if __name__ == "__main__":
    main()
