# -*- coding: utf-8 -*-
"""Computer Use 判决失真修复反证测试（坏样本 ⇒ 必须红）。

覆盖四处真实的「无证据却宣称完成/已发送」缺陷（AGENTS.md §5/§8）：

A. adapter.run_see_think_act_loop 空动作列表：all([])==True 陷阱，旧实现报
   ok=True / status=COMPLETED，等于「什么都没做却说完成了」。修复后 NO_ACTIONS / ok=False。
B. adapter 任一步骤 ok=False：旧实现 status 仍 COMPLETED。修复后 FAILED / ok=False。
C. action.drag 中途被外力打断（foreign_motion）：旧实现仍报 ok=True / executed。
   修复后 ok=False / status=aborted / aborted=foreign_cursor_writer（input_sent 仍 True，
   因为按下+部分移动+抬起确实发出去了）。
D. action.hotkey 空组合/全部未知键：vk_codes 为空却报 input_sent=True / executed。
   修复后 ok=False / input_sent=False / status=no_keys。

保住的既有契约（不在本测试改动范围，且必须仍绿）：
- 全部步骤被闸门抑制但 ok=True ⇒ COMPLETED_SIMULATED / simulated=True / input_sent_steps=0
  （test_computer_use_integration.test_structured_see_think_act_loop）。
- failsafe 角落时 ActionEngine.mouse_move 必须 RAISE InputDenied（紧急停车硬传播，
  test_computer_use_integration.test_action_blocks_when_cursor_in_failsafe_corner）——
  本修复不把 InputDenied 转成结构化返回，正是为了保住该安全契约。
- drag 轨迹中途抛通用 RuntimeError 必须传播且松手（test_input_guard）。本修复只改
  「外力让位」的判决，不吞通用异常。

运行： .venv/Scripts/python.exe -m pytest tests/test_computer_use_verdict_fix.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from virtu_omni.computer_use import input_guard  # noqa: E402
from virtu_omni.computer_use import action as action_mod  # noqa: E402
from virtu_omni.computer_use.adapter import VirtuComputerUse  # noqa: E402


# ---------------------------------------------------------------------------
# A / B：adapter 判决
# ---------------------------------------------------------------------------
def test_empty_actions_must_not_report_completed():
    cu = VirtuComputerUse()
    res = cu.run_see_think_act_loop(goal="nothing", actions=[], capture_screenshots=False)
    assert res["ok"] is False, "空动作列表被谎报 ok=True"
    assert res["status"] == "NO_ACTIONS"
    assert res["status"] != "COMPLETED"
    assert res["total_steps"] == 0
    assert res["simulated"] is False


def test_failed_step_must_not_report_completed():
    cu = VirtuComputerUse()
    res = cu.run_see_think_act_loop(
        goal="bad", actions=[{"action": "totally_unsupported_action"}],
        capture_screenshots=False,
    )
    assert res["ok"] is False
    assert res["status"] == "FAILED"
    assert res["status"] != "COMPLETED"


def test_all_suppressed_ok_steps_still_completed_simulated():
    """保住既有契约：演练会话如实标 COMPLETED_SIMULATED，而不是 COMPLETED。"""
    cu = VirtuComputerUse()
    res = cu.run_see_think_act_loop(
        goal="dry", actions=[{"action": "move", "x": 200, "y": 200},
                             {"action": "click", "x": 200, "y": 200}],
        capture_screenshots=False,
    )
    assert res["ok"] is True
    assert res["status"] == "COMPLETED_SIMULATED"
    assert res["simulated"] is True
    assert res["input_sent_steps"] == 0


# ---------------------------------------------------------------------------
# D：hotkey 空组合
# ---------------------------------------------------------------------------
def test_empty_hotkey_must_not_claim_input_sent():
    engine = action_mod.ActionEngine()
    res = engine.hotkey([])
    assert res["ok"] is False
    assert res["input_sent"] is False, "空 hotkey 谎称已发送输入"
    assert res["status"] == "no_keys"


def test_all_unknown_hotkey_must_not_claim_input_sent():
    engine = action_mod.ActionEngine()
    res = engine.hotkey(["not_a_real_key"])
    assert res["ok"] is False
    assert res["input_sent"] is False
    assert res["status"] == "no_keys"


# ---------------------------------------------------------------------------
# C：drag 外力让位（真实执行路径，底层 Win32 全部打桩，零副作用）
# ---------------------------------------------------------------------------
class _Recorder:
    def __init__(self):
        self.events = []

    def mouse_event(self, flag, dx=0, dy=0, data=0, extra=0):
        self.events.append(("mouse", flag))

    def keybd_event(self, vk, scan=0, flags=0, extra=0):
        self.events.append(("key", vk, flags))

    def SetCursorPos(self, x, y):
        self.events.append(("move", x, y))
        return True

    def GetAsyncKeyState(self, vk):
        return 0


@pytest.fixture
def foreign_drag_gate(monkeypatch):
    """授权 + 非 dry-run + 外力恒在：drag 第一步就必须让位。底层全打桩。"""
    monkeypatch.setenv("VIRTU_DESKTOP_INPUT", "1")
    monkeypatch.delenv("VIRTU_DESKTOP_INPUT_DRYRUN", raising=False)
    monkeypatch.setattr(input_guard, "authorized", lambda: (True, "test"))
    monkeypatch.setattr(input_guard, "is_dry_run", lambda: (False, ""))
    monkeypatch.setattr(input_guard, "kill_switch_active", lambda: (False, ""))
    monkeypatch.setattr(input_guard, "cursor_pos", lambda: (500, 500))
    monkeypatch.setattr(input_guard, "point_in_virtual_desktop", lambda *a, **k: True)
    monkeypatch.setattr(input_guard, "foreign_motion", lambda *a, **k: True)
    monkeypatch.setattr(input_guard, "release_all_buttons",
                        lambda: {"released": [], "supported": True})
    rec = _Recorder()
    monkeypatch.setattr(action_mod, "user32", rec)
    return rec


def test_drag_aborted_by_foreign_writer_must_not_report_executed(foreign_drag_gate):
    engine = action_mod.ActionEngine()
    engine.adapt_coordinates = lambda x, y, **k: (int(x), int(y))
    res = engine.drag(100, 100, 300, 300, steps=5)
    assert res["ok"] is False, "外力打断的 drag 被谎报 ok=True"
    assert res["status"] == "aborted"
    assert res["status"] != "executed"
    assert res["aborted"] == "foreign_cursor_writer"
    # 真实输入确实部分发出（按下+抬起），input_sent 仍须如实为 True
    assert res["input_sent"] is True
    downs = [e for e in foreign_drag_gate.events if e == ("mouse", 0x0002)]
    ups = [e for e in foreign_drag_gate.events if e == ("mouse", 0x0004)]
    assert downs and len(ups) >= len(downs), "让位后必须松手，不能把左键留在按下态"


def test_drag_completes_when_no_foreign_writer(monkeypatch, foreign_drag_gate):
    """对照：无外力时 drag 走完整条轨迹 ⇒ ok=True / executed（保住正常契约）。"""
    monkeypatch.setattr(input_guard, "foreign_motion", lambda *a, **k: False)
    engine = action_mod.ActionEngine()
    engine.adapt_coordinates = lambda x, y, **k: (int(x), int(y))
    res = engine.drag(100, 100, 300, 300, steps=5)
    assert res["ok"] is True
    assert res["status"] == "executed"
    assert res["aborted"] is None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))