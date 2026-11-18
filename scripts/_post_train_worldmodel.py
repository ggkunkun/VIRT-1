#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_post_train_worldmodel.py — 世界模型训练完成后本地收尾闭环（幂等可重跑）。

阶段：
  0. 轮询云端 training_receipt.json，等 virtu_wm_all90 训练 COMPLETED
  1. SFTP 递归拉回 adapter -> checkpoints/virtu_wm_all90
  2. merge_numpy 合并到 Qwen3-8B 基座 -> checkpoints/virtu_wm_all90_merged
  3. hf_to_gguf_numpy 量化 Q4_0 -> checkpoints/virtu-wm-all90-q4_0.gguf
  4. 写 Modelfile + ollama create virtu-wm-all90；写入 arms.json 新臂

SSH 密码只从 DAMODEL_PW 环境变量读取，不打印。
"""
import os
import sys
import time
import json
import glob
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import _ssh_damodel as S
from build_wm_modelfile import render_modelfile
import wm_contract as _wm_contract

PY = os.path.join(ROOT, ".venv", "Scripts", "python.exe")
# 产物族参数化：默认 v1（virtu_wm_all90），v2 用环境变量覆盖即可复用同一收尾链路
TAG = os.environ.get("WM_TAG", "virtu_wm_all90")               # 云端/本地 adapter 目录名
MODEL_ID = os.environ.get("WM_MODEL_ID", "virtu-wm-all90")     # ollama 模型名
LOG_NAME = os.environ.get("WM_LOG", "launch_wm.log")           # 云端日志名
REMOTE_OUT = f"/root/virtu_train/checkpoints/{TAG}"
LOCAL_ADAPTER = os.path.join(ROOT, "checkpoints", TAG)
LOCAL_MERGED = os.path.join(ROOT, "checkpoints", TAG + "_merged")
LOCAL_GGUF = os.path.join(ROOT, "checkpoints", f"{MODEL_ID}-q4_0.gguf")
SYSTEM_PROMPT = _wm_contract.SYSTEM


def run_local(cmd, timeout=1800):
    print(">>>", cmd[:200])
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    if r.stdout:
        print(r.stdout[-2500:])
    if r.stderr:
        print("[err]", r.stderr[-1500:])
    return r.returncode


def wait_cloud_done(timeout_min=220, poll=30):
    print("[0] 等待云端世界模型训练完成 ...")
    deadline = time.time() + timeout_min * 60
    while time.time() < deadline:
        out, err, rc = S.run(
            f"echo RECEIPT; cat {REMOTE_OUT}/training_receipt.json 2>/dev/null; "
            f"echo TAIL; tail -n 3 /root/virtu_train/{LOG_NAME}",
            timeout=30,
        )
        if '"status": "COMPLETED"' in out:
            print("[0] 云端训练 COMPLETED")
            return True
        if '"status": "FAILED"' in out:
            print("[0] 云端训练 FAILED:\n", out)
            return False
        time.sleep(poll)
    print("[0] 等待超时；稍后重跑本脚本即可续跑")
    return None


def pull_adapter():
    if os.path.exists(os.path.join(LOCAL_ADAPTER, "adapter_config.json")):
        print("[1] adapter 已存在，跳过拉取")
        return True
    os.makedirs(LOCAL_ADAPTER, exist_ok=True)
    print("[1] 从云端 SFTP 拉回 adapter ...")
    c = S._client()
    try:
        sftp = c.open_sftp()

        def get_tree(remote, local):
            os.makedirs(local, exist_ok=True)
            for e in sftp.listdir_attr(remote):
                rp = remote + "/" + e.filename
                lp = os.path.join(local, e.filename)
                if e.st_mode & 0x4000:  # 目录
                    get_tree(rp, lp)
                else:
                    sftp.get(rp, lp)
                    print("  got", os.path.relpath(lp, ROOT))

        get_tree(REMOTE_OUT, LOCAL_ADAPTER)
    finally:
        c.close()
    return os.path.exists(os.path.join(LOCAL_ADAPTER, "adapter_config.json"))


def find_base():
    pat = os.path.expandvars(
        r"C:\Users\Administrator\.cache\huggingface\hub\models--Qwen--Qwen3-8B\snapshots\*"
    )
    for d in glob.glob(pat):
        if os.path.exists(os.path.join(d, "config.json")) and glob.glob(
            os.path.join(d, "model-*.safetensors")
        ):
            return d
    alt = os.path.join(ROOT, "checkpoints", "_base_qwen3_8b")
    if os.path.exists(os.path.join(alt, "config.json")):
        return alt
    raise SystemExit("[FATAL] 本地找不到 Qwen3-8B 基座")


def merge(base):
    if os.path.exists(os.path.join(LOCAL_MERGED, "merge_receipt.json")):
        print("[2] 合并产物已存在，跳过")
        return
    print("[2] 合并 LoRA 进基座 ...")
    run_local(
        f'"{PY}" scripts/merge_numpy.py --base "{base}" --lora "{LOCAL_ADAPTER}" '
        f'--weight 1.0 --mode delta --out "{LOCAL_MERGED}" --verify-samples 3'
    )


def quantize():
    if os.path.exists(LOCAL_GGUF):
        print("[3] GGUF 已存在，跳过")
        return
    print("[3] 量化 Q4_0 GGUF ...")
    run_local(
        f'"{PY}" scripts/hf_to_gguf_numpy.py --model "{LOCAL_MERGED}" --out "{LOCAL_GGUF}"'
    )


def register():
    r = subprocess.run(["ollama", "list"], shell=False, capture_output=True, text=True)
    if MODEL_ID in r.stdout:
        print("[4] ollama 模型已存在，跳过 create")
    else:
        mf = os.path.join(ROOT, "checkpoints", f"{MODEL_ID}.Modelfile")
        with open(mf, "w", encoding="utf-8", newline="\n") as f:
            f.write(render_modelfile(LOCAL_GGUF))
        run_local(f'ollama create {MODEL_ID} -f "{mf}"')
    add_arm()


def add_arm():
    ap = os.path.join(ROOT, "virtu_eval", "arms.json")
    arms = json.load(open(ap, encoding="utf-8"))
    if MODEL_ID in arms:
        print("[4] 评测臂已存在，跳过")
        return
    src = arms["ollama_qwen3_8b_base"]
    arms[MODEL_ID] = {
        "kind": "ollama_native",
        "base_url": "http://127.0.0.1:11434",
        "model_id": MODEL_ID,
        "num_ctx": 4096,
        "timeout": 600,
        "retries": 1,
        "note": f"世界模型产物：{MODEL_ID}-q4_0.gguf（在 v3 之上续训世界状态预测 + 自纠错/设计/工艺/适配）",
        "expect_identity": {"family": "qwen3"},
        "tools": src["tools"],
        "tools_dimensions": ["toolcall"],
    }
    json.dump(arms, open(ap, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("[4] 已写入评测臂:", MODEL_ID)


if __name__ == "__main__":
    ok = wait_cloud_done()
    if ok is False:
        sys.exit("[FATAL] 云端训练失败，请查 launch_wm.log")
    if ok is None:
        sys.exit("[INFO] 云端尚未完成；稍后重跑本脚本续跑")
    if not pull_adapter():
        sys.exit("[FATAL] adapter 拉取失败")
    base = find_base()
    print("[base]", base)
    merge(base)
    quantize()
    register()
    print("\n[阶段 0-4 全部完成] 模型已注册为", MODEL_ID,
          "；下一步：确认服务正常后跑世界状态预测评测。")
