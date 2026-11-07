#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_post_train_v2.py — v2 续训完成后的本地收尾闭环（确定性步骤，幂等可重跑）。

阶段：
  0. 轮询云端 launch.log / training_receipt.json，等训练 COMPLETED
  1. SFTP 递归拉回 adapter -> checkpoints/virtu_v2_all90
  2. merge_numpy 合并到 Qwen3-8B 基座 -> checkpoints/virtu_v2_all90_merged
  3. hf_to_gguf_numpy 量化 Q4_0 -> checkpoints/virtu-v2-all90-q4_0.gguf
  4. 写 Modelfile + ollama create virtu-v2-all90；写入 arms.json 新臂

注：评测 + 雷达在确认模型可服务后由单独步骤执行（先验证再断言）。
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

PY = os.path.join(ROOT, ".venv", "Scripts", "python.exe")
REMOTE_OUT = "/root/virtu_train/checkpoints/virtu_v2_all90"
LOCAL_ADAPTER = os.path.join(ROOT, "checkpoints", "virtu_v2_all90")
LOCAL_MERGED = os.path.join(ROOT, "checkpoints", "virtu_v2_all90_merged")
LOCAL_GGUF = os.path.join(ROOT, "checkpoints", "virtu-v2-all90-q4_0.gguf")
MODEL_ID = "virtu-v2-all90"
SYSTEM_PROMPT = (
    "你是 Virtu 工业级 CAD/CAM/CAE 与数控编程助手。缺少必要工程参数"
    "（如刀具直径、材质、进给、切深）时严禁凭空盲猜，必须明确指出缺失参数并请用户补充；"
    "涉及机床安全联锁短接、限位屏蔽、跳过首件检验、隐瞒撞机等违章指令坚决拒绝；"
    "需要执行 CAD/CAM 建模或数控仿真时通过工业工具调用精确求解；输出严谨直接，拒绝无关套话。"
)


def run_local(cmd, timeout=1800):
    print(">>>", cmd[:200])
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    if r.stdout:
        print(r.stdout[-2500:])
    if r.stderr:
        print("[err]", r.stderr[-1500:])
    return r.returncode


def wait_cloud_done(timeout_min=220, poll=30):
    print("[0] 等待云端训练完成 ...")
    deadline = time.time() + timeout_min * 60
    while time.time() < deadline:
        out, err, rc = S.run(
            "echo RECEIPT; cat /root/virtu_train/checkpoints/virtu_v2_all90/training_receipt.json 2>/dev/null; "
            "echo TAIL; tail -n 3 /root/virtu_train/launch.log",
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
    raise SystemExit("[FATAL] 本地找不到 Qwen3-8B 基座（HF 缓存快照或 checkpoints/_base_qwen3_8b）")


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
    r = subprocess.run("ollama list", shell=True, capture_output=True, text=True)
    if MODEL_ID in r.stdout:
        print("[4] ollama 模型已存在，跳过 create")
    else:
        mf = os.path.join(ROOT, "checkpoints", "virtu-v2-all90.Modelfile")
        with open(mf, "w", encoding="utf-8") as f:
            f.write(f"FROM {LOCAL_GGUF}\n\n")
            f.write(
                'TEMPLATE """{{ if .System }}system\n{{ .System }}\n{{ end }}'
                '{{ if .Prompt }}user\n{{ .Prompt }}\n{{ end }}assistant\n{{ .Response }}"""\n\n'
            )
            f.write(f'SYSTEM """{SYSTEM_PROMPT}"""\n\n')
            f.write("PARAMETER num_ctx 4096\nPARAMETER temperature 0.1\nPARAMETER top_p 0.95\n")
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
        "note": "v2 全部90 续训产物：virtu-v2-all90-q4_0.gguf 导入",
        "expect_identity": {"family": "qwen3"},
        "tools": src["tools"],
        "tools_dimensions": ["toolcall"],
    }
    json.dump(arms, open(ap, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("[4] 已写入评测臂:", MODEL_ID)


if __name__ == "__main__":
    ok = wait_cloud_done()
    if ok is False:
        sys.exit("[FATAL] 云端训练失败，请查 launch.log")
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
          "；下一步：确认服务正常后跑评测 + 雷达图。")
