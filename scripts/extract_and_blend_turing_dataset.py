# -*- coding: utf-8 -*-
"""
Server-side data builder for Turing Test Conversational SFT.
Reads seed Turing traps and filters high-quality Chinese & bilingual multi-turn human dialogues
from /root/public-storage/dataset/ShareGPT_Vicuna_unfiltered/ShareGPT_V3_unfiltered_cleaned_split.json.
Removes all robotic disclaimers, assistant clichés, bulleted essays, and creates an authentic human corpus.
"""

import json
import os
import re
import random

SEED_FILE = "/root/workspace/Virtu/turing_conversational/data/turing_conversational_master_train.jsonl"
SHAREGPT_FILE = "/root/public-storage/dataset/ShareGPT_Vicuna_unfiltered/ShareGPT_V3_unfiltered_cleaned_split.json"
OUTPUT_FILE = "/root/workspace/Virtu/turing_conversational/data/turing_master_train.jsonl"

ROBOTIC_PATTERNS = [
    r"作为(一[名个位])?人工智能",
    r"作为(一[名个位])?(大型)?语言模型",
    r"作为一个(虚拟)?助手",
    r"作为一个AI",
    r"作为AI语言模型",
    r"很抱歉我没有(身体|感情|感觉|实体|器官)",
    r"我是一个由.*(训练|开发)的",
    r"如果您还有其他问题，?欢迎随时向我提问",
    r"希望以上(建议|回答|信息)对您有所帮助",
    r"请注意，?以上仅供参考",
    r"作为一个程序",
    r"As an AI",
    r"as a language model",
    r"I am an artificial intelligence",
]

SYSTEM_PROMPT = "你是一个真实、有温度、有见识、高情商且幽默风趣的人类伙伴。你说话自然随性、接地气，绝不使用死板的AI模板、编号列表或机械免责声明。你能深度共情，有自己的性格、生活体验与独立思想。"

def is_robotic(text):
    for pat in ROBOTIC_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False

def clean_human_response(text):
    # Remove robotic disclaimers if present at the end
    cleaned = text
    cleaned = re.sub(r"希望(这个回答|这些建议|以上内容)能(帮到你|对你有所帮助).*?$", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"如果有其他问题.*?$", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"作为(一[个名])?AI语言模型.*?[，。]", "", cleaned)
    return cleaned.strip()

def main():
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    all_conversations = []
    
    # 1. Load seed Turing dialogues (expanded)
    if os.path.exists(SEED_FILE):
        with open(SEED_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    # Replicate high-priority seed examples 5 times to weight human persona heavily
                    for _ in range(5):
                        all_conversations.append(item)
        print(f"[DATA] Loaded and augmented {len(all_conversations)} seed Turing trap samples.")
    else:
        print(f"[WARN] Seed file {SEED_FILE} not found!")

    # 2. Extract and filter from ShareGPT
    if os.path.exists(SHAREGPT_FILE):
        print(f"[DATA] Reading ShareGPT dataset from {SHAREGPT_FILE} ...")
        with open(SHAREGPT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        print(f"[DATA] Scanning {len(data)} raw ShareGPT entries ...")
        added_sharegpt = 0
        
        # Shuffle for diversity
        random.seed(42)
        random.shuffle(data)
        
        for item in data:
            if added_sharegpt >= 2500:
                break
                
            convs = item.get("conversations", [])
            if len(convs) < 2:
                continue
                
            # Filter for conversational turns
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            has_robotics = False
            valid_turn_count = 0
            
            for turn in convs:
                sender = turn.get("from", "")
                val = turn.get("value", "")
                
                # Check for code dumps or robotic artifacts
                if "```python" in val or "```c" in val or "```sql" in val or "def " in val:
                    # Skip heavy programming code, we want pure conversational human dialogue
                    has_robotics = True
                    break
                    
                if is_robotic(val):
                    has_robotics = True
                    break
                    
                if sender in ["human", "user"]:
                    messages.append({"role": "user", "content": val.strip()})
                elif sender in ["gpt", "assistant"]:
                    cleaned_val = clean_human_response(val)
                    if len(cleaned_val) < 5 or is_robotic(cleaned_val):
                        has_robotics = True
                        break
                    messages.append({"role": "assistant", "content": cleaned_val})
                    valid_turn_count += 1
            
            if not has_robotics and valid_turn_count >= 1:
                # Ensure the last message is from assistant
                if messages[-1]["role"] == "assistant":
                    all_conversations.append({"messages": messages})
                    added_sharegpt += 1
                    
        print(f"[DATA] Successfully filtered {added_sharegpt} natural human conversations from ShareGPT.")
    else:
        print(f"[WARN] ShareGPT file not found at {SHAREGPT_FILE}")

    # Shuffle combined dataset
    random.shuffle(all_conversations)
    print(f"[DATA] Total master Turing dataset size: {len(all_conversations)} conversations.")
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for c in all_conversations:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
            
    print(f"[SUCCESS] Master Turing dataset saved to: {OUTPUT_FILE} ({os.path.getsize(OUTPUT_FILE):,} bytes)")

if __name__ == "__main__":
    main()
