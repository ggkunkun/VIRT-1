# -*- coding: utf-8 -*-
"""
deploy_and_verify.py - 注册 virtu-production:v3 到本地 Ollama，测试推理并执行 CAD/CAM 智能体链路
"""
import os
import sys
import json
import time
import subprocess
import urllib.request
import urllib.error

# 设置控制台输出 UTF-8
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

MODEL_NAME = "virtu-production:v3"
MODELFILE_PATH = r"d:\Virtu模型\scripts\Modelfile.virtu-production-v3"
OLLAMA_API = "http://127.0.0.1:11434"

# 隔离代理环境变量
CLEAN_ENV = os.environ.copy()
CLEAN_ENV["NO_PROXY"] = "127.0.0.1,localhost,0.0.0.0"
CLEAN_ENV["no_proxy"] = "127.0.0.1,localhost,0.0.0.0"
CLEAN_ENV.pop("HTTP_PROXY", None)
CLEAN_ENV.pop("HTTPS_PROXY", None)
CLEAN_ENV.pop("http_proxy", None)
CLEAN_ENV.pop("https_proxy", None)

def test_ollama_alive():
    print(f"[1/4] 检查 Ollama 服务连通性: {OLLAMA_API} ...")
    proxy_handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(proxy_handler)
    try:
        req = urllib.request.Request(f"{OLLAMA_API}/api/version")
        with opener.open(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            print(f"      Ollama 版本: {data.get('version', 'unknown')} (正常在线)")
            return True
    except Exception as e:
        print(f"      Ollama 连接异常: {e}")
        return False

def create_model():
    print(f"\n[2/4] 注册模型 {MODEL_NAME} 从 {MODELFILE_PATH} ...")
    cmd = ["ollama", "create", MODEL_NAME, "-f", MODELFILE_PATH]
    p = subprocess.Popen(
        cmd,
        env=CLEAN_ENV,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace"
    )
    for line in iter(p.stdout.readline, ''):
        line_clean = line.strip()
        if line_clean:
            print(f"      [Ollama] {line_clean}")
    p.wait()
    if p.returncode == 0:
        print(f"      >>> 模型 {MODEL_NAME} 注册成功！")
        return True
    else:
        print(f"      >>> 模型注册失败，退出码: {p.returncode}")
        return False

def test_inference():
    print(f"\n[3/4] 验证模型 {MODEL_NAME} 推理能力 ...")
    prompt = "作为 Virtu 工业模型，请简述双工位自动锁螺丝机的核心组成与伺服电批选型要点。"
    print(f"      测试 Prompt: {prompt}\n")
    
    proxy_handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(proxy_handler)
    
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 300
        }
    }
    
    req = urllib.request.Request(
        f"{OLLAMA_API}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    
    t0 = time.time()
    try:
        with opener.open(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            elapsed = time.time() - t0
            response_text = result.get("response", "")
            eval_count = result.get("eval_count", 0)
            eval_duration = result.get("eval_duration", 1) / 1e9
            speed = eval_count / eval_duration if eval_duration > 0 else 0
            print(f"      推理耗时: {elapsed:.2f}s | 生成 Token 数: {eval_count} | 速度: {speed:.1f} tok/s")
            print(f"\n--- 模型生成回复 ---\n{response_text}\n-------------------")
            return True
    except Exception as e:
        print(f"      推理请求失败: {e}")
        return False

def run_agent_chain():
    print(f"\n[4/4] 运行 CAD/CAM 智能体端到端协同链路 (cad_cam_agent_chain.py) ...")
    wish = "我想制造一套双工位伺服打螺丝机 铝合金机架 包含上下料滑台与电批模组"
    cmd = [sys.executable, r"d:\Virtu模型\cad_cam_agent_chain.py", "--wish", wish]
    
    p = subprocess.Popen(
        cmd,
        cwd=r"d:\Virtu模型",
        env=CLEAN_ENV,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace"
    )
    for line in iter(p.stdout.readline, ''):
        line_clean = line.strip()
        if line_clean:
            print(f"      [Chain] {line_clean}")
    p.wait()
    if p.returncode == 0:
        print(f"\n      >>> CAD/CAM 智能体链路执行完成！")
        return True
    else:
        print(f"\n      >>> 链路执行异常，退出码: {p.returncode}")
        return False

if __name__ == "__main__":
    alive = test_ollama_alive()
    if not alive:
        print("错误: Ollama 未运行或无法访问！")
        sys.exit(1)
        
    created = create_model()
    if not created:
        print("警告: 尝试验证模型是否已存在...")
    
    inferred = test_inference()
    
    chained = run_agent_chain()
    
    print("\n================ 全部执行完毕 ================")
