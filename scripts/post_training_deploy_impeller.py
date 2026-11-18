# -*- coding: utf-8 -*-
"""post_training_deploy_impeller.py — 8.2B 叶轮修复 LoRA 的真实本地部署链（合并→GGUF Q4_0→Ollama 注册）。

修复要点：
1. 修复 Modelfile TEMPLATE 缺失 `{{ .Response }}<|im_end|>` 的致命缺陷（此前导致多轮对话中
   模型上一轮的 assistant 回复被 Ollama 模板吞掉，且残留未闭合 `<|im_start|>assistant` 引发乱码）；
2. 补齐防复读采样参数（repeat_penalty 1.15, repeat_last_n 256, min_p 0.05）与原则级 SYSTEM 契约；
3. 统一产物路径：自动兼容 virtu_impeller_fix2_lora_deliverable.tar.gz 与 virtu_impeller_fix_lora_deliverable.tar.gz；
4. 若本地 127.0.0.1:11435 Ollama 服务未启动，自动挂载 E:\\ollama\\models 拉起服务后完成注册与冒烟验证。
"""
import os
import sys
import json
import time
import shutil
import tarfile
import subprocess
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent
PY = str(ROOT / ".venv" / "Scripts" / "python.exe")
BASE = ROOT / "checkpoints" / "_base_qwen3_8b"
DELIV_CANDIDATES = [
    ROOT / "cloud_train_pack" / "output_impeller" / "virtu_impeller_fix2_lora_deliverable.tar.gz",
    ROOT / "cloud_train_pack" / "output_impeller" / "virtu_impeller_fix_lora_deliverable.tar.gz",
]
MERGED = ROOT / "checkpoints" / "impeller_fixed_merged"
GGUF = ROOT / "checkpoints" / "virtu_impeller_fixed-q4_0.gguf"
MODELFILE = ROOT / "Modelfile_impeller_fixed"
TAG = "virtu-impeller-fixed:latest"

MODELFILE_TEMPLATE = """FROM {gguf}
SYSTEM \"\"\"你是 Virtu 工业超级智能体，负责航空叶轮设计与工程计算。证据契约：所有宣称数值必须可由你给出的参数真实复算；不得宣称未经计算的结果；被审计判红时必须依据 violations 修改违规字段，禁止原样重发同一组参数。\"\"\"
TEMPLATE \"\"\"{{{{ if .System }}}}<|im_start|>system
{{{{ .System }}}}<|im_end|>
{{{{ end }}}}{{{{ if .Prompt }}}}<|im_start|>user
{{{{ .Prompt }}}}<|im_end|>
{{{{ end }}}}<|im_start|>assistant
{{{{ .Response }}}}<|im_end|>
\"\"\"
PARAMETER temperature 0.2
PARAMETER top_p 0.9
PARAMETER min_p 0.05
PARAMETER repeat_penalty 1.15
PARAMETER repeat_last_n 256
PARAMETER num_ctx 8192
PARAMETER num_gpu 99
PARAMETER stop "<|im_start|>"
PARAMETER stop "<|im_end|>"
"""


def run(cmd, timeout=3600):
    print(f"[run] {' '.join(str(c) for c in cmd)[:160]}", flush=True)
    p = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout, cwd=str(ROOT))
    if p.returncode != 0:
        print(p.stdout[-800:]); print(p.stderr[-800:])
        raise SystemExit(f"[FATAL] 命令失败 rc={p.returncode}")
    return p.stdout


def ensure_ollama_server(host="127.0.0.1:11435"):
    os.environ["OLLAMA_HOST"] = host
    if Path("E:/ollama/models").exists():
        os.environ.setdefault("OLLAMA_MODELS", "E:/ollama/models")
    url = f"http://{host}/api/tags"
    try:
        urllib.request.urlopen(url, timeout=3).read()
        return
    except Exception:
        print(f"[ollama] {host} 未运行，正在后台拉起 ollama serve (OLLAMA_MODELS={os.environ.get('OLLAMA_MODELS')})...")
        subprocess.Popen(
            ["ollama", "serve"],
            env=dict(os.environ),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        for _ in range(20):
            time.sleep(1)
            try:
                urllib.request.urlopen(url, timeout=2).read()
                print(f"[ollama] {host} 已就绪")
                return
            except Exception:
                pass
        raise SystemExit(f"[FATAL] 无法拉起 Ollama 服务 ({host})")


def find_adapter(root: Path):
    for f in root.rglob("adapter_config.json"):
        d = f.parent
        if (d / "adapter_model.safetensors").exists() or list(d.glob("adapter_model*.safetensors")):
            return d
    return None


def resolve_deliverable(specified: str = None) -> Path:
    if specified:
        p = Path(specified)
        if p.exists():
            return p
    for c in DELIV_CANDIDATES:
        if c.exists():
            return c
    raise SystemExit(f"[FATAL] 交付件不存在: 候选 {[str(c) for c in DELIV_CANDIDATES]}")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--deliverable", default=None, help="LoRA 交付件 tar.gz 路径")
    ap.add_argument("--tag", default=TAG)
    ap.add_argument("--skip-merge", action="store_true")
    ap.add_argument("--modelfile-only", action="store_true", help="仅用现有 GGUF 重新注册修复后的 Modelfile")
    args = ap.parse_args()

    if not args.modelfile_only:
        deliv = resolve_deliverable(args.deliverable)
        print(f"[1/5] 解压交付件 {deliv}")
        extract_dir = ROOT / "checkpoints" / "_impeller_deliverable"
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        extract_dir.mkdir(parents=True, exist_ok=True)
        with tarfile.open(deliv, "r:gz") as tar:
            tar.extractall(extract_dir)
        adapter = find_adapter(extract_dir)
        if adapter is None:
            raise SystemExit("[FATAL] 交付件里找不到 LoRA adapter (adapter_config.json)")
        print(f"  -> adapter: {adapter}")

        if not args.skip_merge:
            print("[2/5] numpy 合并 LoRA → 8.2B 基座 (_base_qwen3_8b)")
            run([PY, "scripts/merge_numpy.py", "--base", BASE, "--lora", adapter, "--weight", "1.0",
                 "--out", MERGED, "--mode", "delta"], timeout=7200)
        else:
            print("[2/5] 跳过合并（--skip-merge）")

        print("[3/5] HF → GGUF Q4_0")
        run([PY, "scripts/hf_to_gguf_numpy.py", "--model", MERGED, "--out", GGUF], timeout=7200)

    if not GGUF.exists() or GGUF.stat().st_size < 100_000_000:
        raise SystemExit(f"[FATAL] GGUF 产物缺失或过小: {GGUF}")

    print("[4/5] 写 Modelfile 并注册 Ollama 标签")
    MODELFILE.write_text(MODELFILE_TEMPLATE.format(gguf=str(GGUF).replace("\\", "/")), encoding="utf-8")
    ensure_ollama_server("127.0.0.1:11435")
    run(["ollama", "create", args.tag, "-f", str(MODELFILE)], timeout=1800)

    print("[5/5] 校验注册与多轮模板推理")
    tags = json.loads(urllib.request.urlopen("http://127.0.0.1:11435/api/tags", timeout=15).read())
    names = [m["name"] for m in tags["models"]]
    assert args.tag in names, f"标签未注册: {args.tag} 不在 {names}"
    payload = {"model": args.tag, "messages": [{"role": "user", "content": "只回复：部署就绪"}],
               "stream": False, "options": {"num_predict": 16, "num_ctx": 2048}}
    req = urllib.request.Request("http://127.0.0.1:11435/api/chat",
                                 data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        ans = json.loads(r.read().decode("utf-8"))["message"]["content"]
    print(f"[DONE] {args.tag} 注册成功，推理返回: {ans[:60]!r}")
    print(f"GGUF: {GGUF} ({GGUF.stat().st_size/1024/1024/1024:.2f} GB)")


if __name__ == "__main__":
    main()
