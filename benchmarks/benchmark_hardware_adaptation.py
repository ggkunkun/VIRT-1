import time
import requests
import json
import subprocess

def test_model(model_name, prompt, num_predict=128):
    print(f"\n==========================================")
    print(f"Testing Model: {model_name}")
    print(f"==========================================")
    
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": num_predict
        }
    }
    
    t0 = time.time()
    try:
        r = requests.post(url, json=payload, timeout=120)
        t_total = time.time() - t0
        data = r.json()
        
        response = data.get("response", "").strip()
        eval_count = data.get("eval_count", 0)
        eval_duration_s = data.get("eval_duration", 1) / 1e9
        eval_rate = eval_count / eval_duration_s if eval_duration_s > 0 else 0
        prompt_eval_count = data.get("prompt_eval_count", 0)
        prompt_eval_s = data.get("prompt_eval_duration", 1) / 1e9
        prompt_rate = prompt_eval_count / prompt_eval_s if prompt_eval_s > 0 else 0
        
        print(f"Status: Success")
        print(f"Response preview: {response[:120]}...")
        print(f"Prompt Tokens: {prompt_eval_count} ({prompt_rate:.1f} tok/s)")
        print(f"Generated Tokens: {eval_count} in {eval_duration_s:.2f}s")
        print(f"Speed: {eval_rate:.2f} tokens/s")
        print(f"Wall Clock Time: {t_total:.2f}s")
        
        # Check ollama ps
        ps_out = subprocess.run(["ollama", "ps"], capture_output=True, text=True).stdout
        print("\n[Ollama Active Engine Allocation]:")
        for line in ps_out.strip().split("\n"):
            if model_name.split(":")[0] in line or "NAME" in line:
                print("  " + line)
                
        return {
            "model": model_name,
            "speed": eval_rate,
            "prompt_speed": prompt_rate,
            "eval_count": eval_count,
            "total_time": t_total
        }
    except Exception as e:
        print(f"Error testing {model_name}: {e}")
        return None

if __name__ == "__main__":
    print("Benchmark Hardware Adaptation Suite Ready.")
