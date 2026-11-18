"""SFT 复评（bridge arm）：与基线 _eval_full4 完全同口径的 before/after 对比。

为什么必须用 bridge arm 而不是 ollama_native：
  基线 _eval_full4 用的是 arms.json 的 `bridge_deployed`（http_openai，指向
  http://127.0.0.1:8000/v1，model_id=virtu-cad-cam-10b）。bridge 对外只暴露一个
  别名，真正的文本后端由 VIRTU_VLLM_MODEL 决定，视觉由独立 VL 通道处理。
  灰度切到 virtu-boundary-sft 之后，唯一变化就是文本后端权重 —— 因此用同一
  arm 重跑 240 例，得到的就是严格可比的 before/after。
  （先前用 ollama_native 跑的那轮：multimodal 30 例全 transport_error，因为
  Ollama 原生 /api/chat 端点不接收图片输入；该轮仅作调试，不作结论。）

为什么必须用独立 run 目录：
  virtu_eval.runner 按 case_id 续跑（raw.jsonl append-only），并对 manifest 做
  指纹校验（git_sha / harness sha / arm / sampling / case_dir / case 文件哈希）。
  旧目录 _eval_full4 已有 240 条基座有效记录，若沿用，runner 会把所有用例判为
  done 并直接复用旧模型的答案 —— 分数看似刷新，实则根本没测新模型。
"""
import json
import os
import sys
import traceback

sys.path.insert(0, os.getcwd())
import virtu_eval.runner as R  # noqa: E402

ARM = "bridge_deployed"
OUT = os.path.join(os.getcwd(), "_eval_sft_bridge")


def main():
    arms = json.load(open("virtu_eval/arms.json", encoding="utf-8"))
    spec = arms[ARM]
    print(f"=== SFT 复评 arm={ARM} model_id={spec['model_id']} -> {OUT} ===", flush=True)
    try:
        R.run(os.path.join(os.getcwd(), "data/benchmark/virtu_eval_v1"),
              spec, OUT, temperature=0.0, seed=1234)
    except Exception:
        traceback.print_exc()
        sys.exit(2)
    print("=== run completed cleanly ===", flush=True)


if __name__ == "__main__":
    main()
