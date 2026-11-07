import requests
import time
import json

def benchmark(model, prompt):
    url = 'http://localhost:11434/api/generate'
    payload = {'model': model, 'prompt': prompt, 'stream': False}
    t0 = time.time()
    try:
        r = requests.post(url, json=payload, timeout=60).json()
        t_total = time.time() - t0
        
        eval_c = r.get('eval_count', 0)
        eval_d = r.get('eval_duration', 1) / 1e9
        peval_c = r.get('prompt_eval_count', 0)
        peval_d = r.get('prompt_eval_duration', 1) / 1e9
        
        gen_speed = eval_c / eval_d if eval_d > 0 else 0
        prompt_speed = peval_c / peval_d if peval_d > 0 else 0
        
        print(f"=== Model: {model} ===")
        print(f"  Prompt Evaluation : {peval_c} tokens at {prompt_speed:.1f} tokens/s")
        print(f"  Token Generation  : {eval_c} tokens at {gen_speed:.1f} tokens/s (Total {t_total:.2f}s)")
        print(f"  Response Preview  : {r.get('response', '').strip()[:100]}...\n")
        return {"model": model, "gen_speed": gen_speed, "prompt_speed": prompt_speed, "tokens": eval_c}
    except Exception as e:
        print(f"Error testing {model}: {e}")
        return None

if __name__ == '__main__':
    print("---------------------------------------------------------")
    print("  DUAL-MODEL PERFORMANCE VERIFICATION (RTX 4050 6GB LAPTOP)")
    print("---------------------------------------------------------")
    
    # 1. Test long context model
    res1 = benchmark('virtu-longctx:latest', '请给出机械加工工艺卡片的核心编制步骤，包括基准选择、工序划分与切削用量设定原则。')
    
    # 2. Test world model
    res2 = benchmark('virtu-wm-v3:latest', '【场景】铣削去除材料：毛坯 120x80x30 mm，加工后工件 120x80x25 mm，钢密度 7.85 g/cm3。')
