#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
看守脚本：等待全量真实测评（eval_all_models_live.py）结束，
随后自动运行 generate_verified_radar.py --self-test 产出可溯源雷达图。
轮询 run.log 末尾是否出现 EXIT 标记（外层 shell 的 echo "EXIT=$?"）。
"""
import os, time, subprocess, sys, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_LOG = os.path.join(ROOT, "runs", "eval", "all_models_live_v2_20261107", "run.log")
RADAR_SCRIPT = os.path.join(ROOT, "scripts", "generate_verified_radar.py")
DONE_FLAG = os.path.join(ROOT, "runs", "eval", "all_models_live_v2_20261107", "radar_done.flag")

POLL = 30          # 秒
MAX_WAIT = 4 * 3600  # 最多等 4 小时


def log(msg):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def eval_finished():
    if not os.path.exists(RUN_LOG):
        return False
    try:
        with open(RUN_LOG, "r", encoding="utf-8", errors="replace") as f:
            tail = f.read()[-4000:]
    except Exception:
        return False
    return "EXIT=" in tail


def main():
    if os.path.exists(DONE_FLAG):
        log("radar_done.flag 已存在，跳过。")
        return
    log("看守启动：等待全量测评结束（检测 run.log 的 EXIT 标记）...")
    waited = 0
    while not eval_finished():
        time.sleep(POLL)
        waited += POLL
        if waited % 300 == 0:
            log(f"已等待 {waited//60} 分钟，测评仍在进行...")
        if waited > MAX_WAIT:
            log("超过最大等待时间，放弃。")
            return

    log("检测到测评结束，开始生成可溯源雷达图（含反证闸门自测）...")
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    cmd = [sys.executable, RADAR_SCRIPT, "--self-test"]
    try:
        proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True,
                              timeout=600)
        out = (proc.stdout or "") + (proc.stderr or "")
        log(f"radar exit={proc.returncode}")
        for line in out.splitlines()[-40:]:
            log("  " + line)
        if proc.returncode == 0:
            with open(DONE_FLAG, "w", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%dT%H:%M:%S%z") + "\n")
            log("雷达图生成完成，已写 radar_done.flag。")
        else:
            log("雷达图生成失败，请手动检查。")
    except Exception as e:
        log(f"生成异常：{type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
