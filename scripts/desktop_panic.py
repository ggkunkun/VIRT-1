#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""desktop_panic.py — 一键止血：立即停止任何智能体对真实鼠标键盘的占用。

背景
----
"智能体突然失控抢鼠标"有四种典型现场，本脚本覆盖全部：

1. 有 agent 正在跑轨迹动画（光标自己乱跑）；
2. 有 agent 把左键按下后崩溃，键一直按着（用户一动就变成拖选）；
3. 后台 pytest / 重试循环在反复点击；
4. 多个 agent 并发抢夺，光标在两个目标之间抖动。

``panic`` 做三件事：写 STOP 文件（此后所有输入请求一律拒绝）→ 释放所有按下的
鼠标键与修饰键 → 留审计记录。之后任何 ``input_guard.input_session`` 都会立刻
抛 ``DESKTOP_KILLED``，不需要重启进程。

用法
----
    python scripts/desktop_panic.py              # 立即止血
    python scripts/desktop_panic.py --status     # 看当前状态（含租约占用者）
    python scripts/desktop_panic.py --clear      # 确认安全后恢复自动化
    python scripts/desktop_panic.py --audit 30   # 看最近 30 条输入审计
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from virtu_omni.computer_use import input_guard  # noqa: E402


def _lease_state() -> str:
    """租约当前是否被占用。非阻塞试锁一次即可判定。"""
    if os.name != "nt":
        return "n/a"
    path = input_guard.lock_file()
    if not path.is_file():
        return "none（从未被使用）"
    try:
        import msvcrt
        with open(path, "a+b") as fh:
            fh.seek(0, os.SEEK_END)
            if fh.tell() == 0:
                fh.write(b"\0")
                fh.flush()
            fh.seek(0)
            try:
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
                return "free（当前无执行体持有）"
            except OSError:
                return "HELD（另一个进程正持有鼠标，可能就是抢鼠标的那个）"
    except OSError as exc:
        return "unknown（%s）" % exc


def cmd_status() -> int:
    killed, why = input_guard.kill_switch_active()
    allowed, allow_why = input_guard.authorized()
    dry, dry_why = input_guard.is_dry_run()
    print("急停状态      :", "ON  (%s)" % why if killed else "off")
    print("输入授权      :", "ON  (%s)" % allow_why if allowed else "OFF（%s）" % allow_why)
    print("演练模式      :", "ON  (%s)" % dry_why if dry else "off")
    print("STOP 文件     :", input_guard.stop_file(), "存在" if input_guard.stop_file().is_file() else "不存在")
    print("租约状态      :", _lease_state())
    print("审计日志      :", input_guard.audit_log())
    recent = input_guard.audit_tail(5)
    if recent:
        print("\n最近 5 条：")
        for rec in recent:
            print("  " + json.dumps(rec, ensure_ascii=False))
    return 0


def cmd_panic() -> int:
    res = input_guard.panic("operator panic via scripts/desktop_panic.py")
    print("已止血。")
    print("  STOP 文件 :", res["stop_file"])
    print("  已释放    :", res.get("released") or "（本来就没有按下的键）")
    print()
    print("后续所有键鼠注入都会被拒绝，直到执行：")
    print("  python scripts/desktop_panic.py --clear")
    print()
    print("如果光标仍在被拖动，说明肇事进程不经过本闸门（例如第三方 MCP）。")
    print("排查：Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' } "
          "| Select ProcessId, CommandLine")
    return 0


def cmd_clear() -> int:
    res = input_guard.clear_panic()
    print("已解除急停（STOP 文件 %s）。" % ("已删除" if res["removed"] else "本就不存在"))
    print("注意：这只是去掉急停标记；真发输入仍需 VIRTU_DESKTOP_INPUT=1。")
    return 0


def cmd_audit(n: int) -> int:
    records = input_guard.audit_tail(n)
    if not records:
        print("（暂无审计记录）")
        return 0
    for rec in records:
        print(json.dumps(rec, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="停止/查看智能体对真实鼠标键盘的占用")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--status", action="store_true", help="查看急停、授权、租约、最近审计")
    group.add_argument("--clear", action="store_true", help="解除急停，恢复可自动化状态")
    group.add_argument("--audit", type=int, metavar="N", help="打印最近 N 条输入审计")
    args = parser.parse_args()

    if args.status:
        return cmd_status()
    if args.clear:
        return cmd_clear()
    if args.audit is not None:
        return cmd_audit(args.audit)
    return cmd_panic()


if __name__ == "__main__":
    sys.exit(main())
