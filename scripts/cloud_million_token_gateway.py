import os
import sys
import argparse
import json
import requests

def query_gemini_2m(prompt, file_contents="", api_key=None):
    api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "错误: 未检测到 GEMINI_API_KEY 环境变量。请先设置 setx GEMINI_API_KEY 'your_key'"
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={api_key}"
    full_text = f"{file_contents}\n\n{prompt}" if file_contents else prompt
    
    payload = {
        "contents": [{
            "parts": [{"text": full_text}]
        }]
    }
    
    try:
        r = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=180)
        r.raise_for_status()
        data = r.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"Gemini 2M API 请求异常: {e}"

def query_qwen_1m(prompt, file_contents="", api_key=None):
    api_key = api_key or os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        return "错误: 未检测到 DASHSCOPE_API_KEY 环境变量。请先设置 setx DASHSCOPE_API_KEY 'your_key'"
        
    url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    full_text = f"{file_contents}\n\n{prompt}" if file_contents else prompt
    
    payload = {
        "model": "qwen-plus",  # supports up to 1M context
        "messages": [
            {"role": "user", "content": full_text}
        ]
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=180)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Qwen 1M API 请求异常: {e}"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="百万 Token 云端原生超长上下文调用网关")
    parser.add_argument("--provider", choices=["gemini", "qwen"], default="gemini", help="云端超长上下文提供方")
    parser.add_argument("--file", type=str, help="待读取分析的超长文件路径（支持几万至上百万字）")
    parser.add_argument("--prompt", type=str, required=True, help="分析指令或问题")
    args = parser.parse_args()

    content = ""
    if args.file and os.path.exists(args.file):
        with open(args.file, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        print(f"[Gateway] 已读取目标文件: {args.file} (字符数: {len(content):,})")

    if args.provider == "gemini":
        print("[Gateway] 正在调用 Gemini 1.5 Pro (2,000,000 Tokens 原生网关)...")
        ans = query_gemini_2m(args.prompt, file_contents=content)
    else:
        print("[Gateway] 正在调用 Qwen-Plus (1,000,000 Tokens 原生网关)...")
        ans = query_qwen_1m(args.prompt, file_contents=content)

    print("\n================ 云端超长模型分析结果 ================\n")
    print(ans)
