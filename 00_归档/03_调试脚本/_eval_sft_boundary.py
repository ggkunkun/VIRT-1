"""SFT 复评：独立 run 目录，评测 virtu_boundary_sft 臂（Ollama 实测部署产物）。

为什么必须用独立目录：
  virtu_eval.runner 按 case_id 续跑（raw.jsonl append-only），并且对 manifest 做
  指纹校验（git_sha / harness sha / arm / sampling / case_dir / case 文件哈希）。
  旧目录 _eval_full4 里已有 240 条有效记录（基座 qwen3:8b 的成绩），若沿用该目录，
  runner 会把全部用例判为 done 并直接复用旧模型的答案 —— 分数看似刷新，实则没测新模型。
  所以这里写全新的 _eval_sft_boundary 目录，让 240 例全部真正打到 SFT 模型。

用法：
  D:/Virtu模型/.venv/Scripts/python.exe _eval_sft_boundary.py
"""
import json
import os
import sys
import traceback

sys.path.insert(0, os.getcwd())
import virtu_eval.runner as R  # noqa: E402

ARM = "virtu_boundary_sft"
OUT = os.path.join(os.getcwd(), "_eval_sft_boundary")


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
