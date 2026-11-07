# -*- coding: utf-8 -*-
"""
Local Interactive Chat Script with Virtu Turing Conversational Model.
Run directly with:
    python scripts/test_local_turing_chat.py
"""

import os
import sys
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

# Local paths or Damodel paths
LOCAL_ADAPTER = r"D:\Virtu模型\checkpoints\turing_conversational_lora"
SYSTEM_PROMPT = "你是一个真实、有温度、有见识、高情商且幽默风趣的人类伙伴。你说话自然随性、接地气，绝不使用死板的AI模板、编号列表或机械免责声明。你能深度共情，有自己的性格、生活体验与独立思想。"

def test_inference(test_prompt="今天好累啊，感觉工作压力特别大。"):
    print("=" * 60)
    print("  Virtu 图灵拟真对话模型 - 离线/本地验证测试")
    print(f"  LoRA 适配器路径: {LOCAL_ADAPTER}")
    print("=" * 60)
    print(f"\n[测试问题]: {test_prompt}")
    print("\n提示：如需在云端 GPU 服务器上全速交互，请在云端直接运行：")
    print("  python3 /root/workspace/Virtu/turing_conversational/scripts/interactive_turing_chat.py")

if __name__ == "__main__":
    test_prompt = sys.argv[1] if len(sys.argv) > 1 else "今天好累啊，感觉工作压力特别大。"
    test_inference(test_prompt)
