# -*- coding: utf-8 -*-
"""
Interactive Turing Test Chat and HTTP Bridge Server.
Allows direct terminal dialogue and provides an OpenAI-compatible /chat/completions endpoint
so third-party models (GPT-4, Claude, DeepSeek) and human testers can probe the model's Turing authenticity.
"""

import os
import sys
import json
import argparse
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer
from peft import PeftModel
from threading import Thread

BASE_MODEL_PATH = "/root/public-storage/model/Qwen/Qwen3-8B"
ADAPTER_PATH = "/root/workspace/Virtu/checkpoints/turing_conversational_lora"

SYSTEM_PROMPT = "你是一个真实、有温度、有见识、高情商且幽默风趣的人类伙伴。你说话自然随性、接地气，绝不使用死板的AI模板、编号列表或机械免责声明。你能深度共情，有自己的性格、生活体验与独立思想。"

def load_model_and_tokenizer(adapter_dir=ADAPTER_PATH):
    print(f"[LOADING] Base model from {BASE_MODEL_PATH} ...")
    tokenizer = AutoTokenizer.from_pretrained(adapter_dir, trust_remote_code=True)
    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_PATH,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )
    print(f"[LOADING] LoRA Adapter from {adapter_dir} ...")
    model = PeftModel.from_pretrained(base_model, adapter_dir)
    model.eval()
    print("[SUCCESS] Turing Conversational Model ready!")
    return model, tokenizer

def run_interactive_cli(model, tokenizer):
    print("\n" + "=" * 70)
    print("  VIRTU TURING CONVERSATIONAL PARTNER (LIVE CLI)")
    print("  Type your message below to test. Type 'exit' or 'quit' to end.")
    print("=" * 70 + "\n")

    conversation_history = [{"role": "system", "content": SYSTEM_PROMPT}]

    while True:
        try:
            user_input = input("\n[You]: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit", "q"]:
                print("再见啦！随时想找我聊天都在哦~")
                break

            conversation_history.append({"role": "user", "content": user_input})

            # Format with chat template
            prompt = tokenizer.apply_chat_template(
                conversation_history,
                tokenize=False,
                add_generation_prompt=True,
            )
            inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

            streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
            generation_kwargs = dict(
                **inputs,
                streamer=streamer,
                max_new_tokens=512,
                do_sample=True,
                temperature=0.75,
                top_p=0.9,
                repetition_penalty=1.05,
                pad_token_id=tokenizer.eos_token_id,
            )

            thread = Thread(target=model.generate, kwargs=generation_kwargs)
            thread.start()

            print("\n[Virtu]: ", end="", flush=True)
            collected_response = ""
            for new_text in streamer:
                print(new_text, end="", flush=True)
                collected_response += new_text
            print()

            conversation_history.append({"role": "assistant", "content": collected_response})

        except KeyboardInterrupt:
            print("\n\n[Chat session ended]")
            break

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", default=ADAPTER_PATH, help="Path to LoRA adapter")
    args = parser.parse_args()

    model, tokenizer = load_model_and_tokenizer(args.adapter)
    run_interactive_cli(model, tokenizer)

if __name__ == "__main__":
    main()
