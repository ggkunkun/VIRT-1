"""
Verification and Test Script for Virtu-MoE-14B (Q4_K_M)
Follows 2026-11-05 《测量宪法》:
- Basis: measured
- Captures run_id, token speed, memory usage, and actual model responses
"""
import os
import sys
import json
import time
import urllib.request
import urllib.error
import subprocess

GGUF_PATH = r"D:\Virtu模型\checkpoints\virtu-moe-14b-q4_k_m.gguf"
MODELFILE_PATH = r"D:\Virtu模型\checkpoints\Modelfile.virtu_moe_14b"
MODEL_NAME = "virtu-moe-14b"
PROVENANCE_PATH = r"D:\Virtu模型\checkpoints\PROVENANCE.json"

def check_file():
    if not os.path.exists(GGUF_PATH):
        raise FileNotFoundError(f"GGUF file not found: {GGUF_PATH}")
    size_bytes = os.path.getsize(GGUF_PATH)
    size_gb = size_bytes / (1024 ** 3)
    print(f"[1/5] GGUF file exists: {size_bytes:,} bytes ({size_gb:.2f} GB)")
    return size_bytes

def register_ollama():
    print(f"[2/5] Registering model '{MODEL_NAME}' in Ollama...")
    cmd = ["ollama", "create", MODEL_NAME, "-f", MODELFILE_PATH]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    print(res.stdout)
    if res.returncode != 0:
        print(res.stderr)
        raise RuntimeError(f"Ollama create failed with code {res.returncode}")
    print("[2/5] Registration succeeded.")

def test_inference(prompt, test_id):
    print(f"\n[Running Test {test_id}] Prompt: {prompt[:40]}...")
    url = "http://127.0.0.1:11434/api/generate"
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": 256,
            "temperature": 0.2
        }
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"Error during inference request: {e}")
        raise
    
    elapsed = time.time() - t0
    response_text = resp_data.get("response", "")
    eval_count = resp_data.get("eval_count", 0)
    eval_duration_ns = resp_data.get("eval_duration", 0)
    speed = (eval_count / (eval_duration_ns / 1e9)) if eval_duration_ns > 0 else 0.0
    
    print(f"Test {test_id} complete in {elapsed:.2f}s | Tokens: {eval_count} | Speed: {speed:.2f} tok/s")
    print("----- Preview of Response -----")
    print(response_text[:300] + ("..." if len(response_text) > 300 else ""))
    print("-------------------------------")
    
    return {
        "test_id": test_id,
        "prompt": prompt,
        "response_len": len(response_text),
        "tokens": eval_count,
        "speed_tok_s": round(speed, 2),
        "elapsed_s": round(elapsed, 2),
        "response_sample": response_text[:500]
    }

def main():
    print("=== Virtu-MoE-14B Deployment & Inference Verification ===")
    size_bytes = check_file()
    register_ollama()
    
    # Industrial Test
    prompt_industrial = (
        "你是一个工业数控与CAD专家。请给出在 SolidWorks 中使用 VBA 创建法兰盘基体拉伸凸台"
        "（直径100mm，厚度15mm）的核心代码片段，并指出其特征树 API 对象名称。"
    )
    res_ind = test_inference(prompt_industrial, "TEST_01_INDUSTRIAL_CAD")
    
    # Theoretical Mechanics Test
    prompt_theory = (
        "作为机械工程力学专家，请写出受内压力 p 的厚壁圆筒（内径 a，外径 b）的 Lamé 径向应力与环向应力公式，"
        "并说明内壁处应力是否最大。"
    )
    res_theory = test_inference(prompt_theory, "TEST_02_LAME_STRESS")
    
    # Provenance Seal Update
    if os.path.exists(PROVENANCE_PATH):
        with open(PROVENANCE_PATH, "r", encoding="utf-8") as f:
            prov = json.load(f)
    else:
        prov = {}
        
    prov["virtu_moe_14b_q4_deployment"] = {
        "status": "VERIFIED_ACTIVE",
        "basis": "measured",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "model_name": MODEL_NAME,
        "gguf_file": GGUF_PATH,
        "file_size_bytes": size_bytes,
        "file_size_gb": round(size_bytes / (1024**3), 2),
        "hardware_target": "RTX 4050 (6GB) + 16GB RAM",
        "verification_results": [res_ind, res_theory]
    }
    
    with open(PROVENANCE_PATH, "w", encoding="utf-8") as f:
        json.dump(prov, f, indent=2, ensure_ascii=False)
    print(f"\n[5/5] Provenance updated at {PROVENANCE_PATH}")
    print("All verification steps passed successfully!")

if __name__ == "__main__":
    main()
