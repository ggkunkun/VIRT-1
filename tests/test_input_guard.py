# -*- coding: utf-8 -*-
"""input_guard 契约测试 —— 每一条都对应一个真实的"抢鼠标"故障模式。

这些测试刻意 monkeypatch 掉底层 Win32 调用：验证的是"闸门是否按契约工作"，
而不是"桌面是否真的被点了一下"。任何用例都不允许向真实输入总线写事件。
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
import sys

import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from virtu_omni.computer_use import input_guard


# ---------------------------------------------------------------------------
# 工具：把闸门切到"已授权"并让底层调用变成记录器
# ---------------------------------------------------------------------------
class _FakeUser32:
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

    def GetSystemMetrics(self, idx):
        return {76: 0, 77: 0, 78: 1920, 79: 1080}.get(idx, 0)

    def GetCursorPos(self, ptr):
        return 1


@pytest.fixture
def live_gate(monkeypatch):
    """授权 + 非 dry-run + 底层全部打桩：可验证执行路径而零副作用。"""
    monkeypatch.setenv("VIRTU_DESKTOP_INPUT", "1")
    monkeypatch.delenv("VIRTU_DESKTOP_INPUT_DRYRUN", raising=False)
    monkeypatch.setattr(input_guard, "authorized", lambda: (True, "test"),
                        raising=True)
    monkeypatch.setattr(input_guard, "is_dry_run", lambda: (False, ""),
                        raising=True)
    monkeypatch.setattr(input_guard, "kill_switch_active", lambda: (False, ""),
                        raising=True)
    monkeypatch.setattr(input_guard, "foreign_motion", lambda *a, **k: False,
                        raising=True)
    monkeypatch.setattr(input_guard, "cursor_pos", lambda: (500, 500),
                        raising=True)
    monkeypatch.setattr(input_guard, "release_all_buttons",
                        lambda: {"released": [], "supported": True}, raising=True)
    return _FakeUser32()


# ---------------------------------------------------------------------------
# 1. fail-closed：默认拒绝
# ---------------------------------------------------------------------------
def test_default_is_fail_closed(monkeypatch):
    monkeypatch.delenv("VIRTU_DESKTOP_INPUT", raising=False)
    monkeypatch.delenv("VIRTU_DESKTOP_INPUT_DRYRUN", raising=False)
    monkeypatch.setattr(input_guard, "kill_switch_active", lambda: (False, ""))
    monkeypatch.setattr(input_guard, "is_dry_run", lambda: (False, ""))
    monkeypatch.setattr(input_guard, "cursor_pos", lambda: (500, 500))

    with input_guard.input_session("click", x=400, y=300) as ctx:
        assert ctx["dry_run"] is True
        assert ctx["verdict_code"] == "DESKTOP_INPUT_NOT_APPROVED"


def test_opt_in_allows_execution(live_gate):
    with input_guard.input_session("click", x=400, y=300) as ctx:
        assert ctx["allowed"] is True
        assert ctx["dry_run"] is False


# ---------------------------------------------------------------------------
# 2. 急停：环境变量 / STOP 文件
# ---------------------------------------------------------------------------
def test_kill_env_blocks(monkeypatch):
    monkeypatch.setenv("VIRTU_DESKTOP_KILL", "1")
    with pytest.raises(input_guard.InputDenied) as exc:
        with input_guard.input_session("click", x=10, y=10):
            pytest.fail("kill switch 生效时不允许进入执行体")
    assert exc.value.code == "DESKTOP_KILLED"


def test_stop_file_blocks(monkeypatch):
    monkeypatch.delenv("VIRTU_DESKTOP_KILL", raising=False)
    stop = input_guard.stop_file()
    stop.parent.mkdir(parents=True, exist_ok=True)
    stop.write_text('{"reason": "test"}', encoding="utf-8")
    try:
        with pytest.raises(input_guard.InputDenied) as exc:
            with input_guard.input_session("click", x=10, y=10):
                pytest.fail("STOP 文件存在时不允许进入执行体")
        assert exc.value.code == "DESKTOP_KILLED"
    finally:
        stop.unlink(missing_ok=True)


def test_panic_writes_stop_and_releases(monkeypatch):
    # 刻意不用 live_gate：这里要验证真实的 kill_switch_active() 能读回 STOP 文件
    monkeypatch.delenv("VIRTU_DESKTOP_KILL", raising=False)
    called = {"n": 0}

    def _fake_release():
        called["n"] += 1
        return {"released": ["mouse:left"], "supported": True}

    monkeypatch.setattr(input_guard, "release_all_buttons", _fake_release)
    res = input_guard.panic("unit-test")
    try:
        assert res["panic"] is True
        assert input_guard.stop_file().is_file()
        assert called["n"] == 1
        assert input_guard.kill_switch_active()[0] is True
    finally:
        input_guard.clear_panic()


# ---------------------------------------------------------------------------
# 3. failsafe：光标甩到角落 = 操作者急停
# ---------------------------------------------------------------------------
def test_failsafe_corner_triggers_panic(monkeypatch):
    monkeypatch.delenv("VIRTU_DESKTOP_KILL", raising=False)
    monkeypatch.setattr(input_guard, "cursor_pos", lambda: (0, 0))
    monkeypatch.setattr(input_guard, "screen_virtual_bounds",
                        lambda: (0, 0, 1920, 1080))
    monkeypatch.setattr(input_guard, "release_all_buttons",
                        lambda: {"released": [], "supported": True})
    try:
        with pytest.raises(input_guard.InputDenied) as exc:
            with input_guard.input_session("click", x=10, y=10):
                pytest.fail("failsafe 命中时不允许进入执行体")
        assert exc.value.code == "DESKTOP_FAILSAFE"
    finally:
        input_guard.clear_panic()


# ---------------------------------------------------------------------------
# 4. 越界坐标必须拒绝（旧实现会静默夹到屏幕角落 = 光标跳走）
# ---------------------------------------------------------------------------
def test_out_of_bounds_rejected(monkeypatch):
    monkeypatch.setenv("VIRTU_DESKTOP_INPUT", "1")
    monkeypatch.delenv("VIRTU_DESKTOP_INPUT_DRYRUN", raising=False)
    monkeypatch.setattr(input_guard, "authorized", lambda: (True, "test"))
    monkeypatch.setattr(input_guard, "is_dry_run", lambda: (False, ""))
    monkeypatch.setattr(input_guard, "kill_switch_active", lambda: (False, ""))
    monkeypatch.setattr(input_guard, "cursor_pos", lambda: (500, 500))
    monkeypatch.setattr(input_guard, "screen_virtual_bounds",
                        lambda: (0, 0, 1920, 1080))
    monkeypatch.setattr(input_guard, "release_all_buttons",
                        lambda: {"released": [], "supported": True})

    with pytest.raises(input_guard.InputDenied) as exc:
        with input_guard.input_session("click", x=-99999, y=10, require_bounds=True):
            pytest.fail("越界坐标不允许进入执行体")
    assert exc.value.code == "DESKTOP_POINT_OUT_OF_BOUNDS"


# ---------------------------------------------------------------------------
# 5. 并发：租约必须串行化，不能让两个 agent 同时写光标
# ---------------------------------------------------------------------------
def test_lease_serializes_concurrent_writers(monkeypatch):
    monkeypatch.setenv("VIRTU_DESKTOP_INPUT", "1")
    monkeypatch.delenv("VIRTU_DESKTOP_INPUT_DRYRUN", raising=False)
    monkeypatch.setattr(input_guard, "authorized", lambda: (True, "test"))
    monkeypatch.setattr(input_guard, "is_dry_run", lambda: (False, ""))
    monkeypatch.setattr(input_guard, "kill_switch_active", lambda: (False, ""))
    monkeypatch.setattr(input_guard, "cursor_pos", lambda: (500, 500))
    monkeypatch.setattr(input_guard, "foreign_motion", lambda *a, **k: False)
    monkeypatch.setattr(input_guard, "release_all_buttons",
                        lambda: {"released": [], "supported": True})

    overlaps = []
    active = {"n": 0}
    seq_lock = threading.Lock()

    def worker(tag):
        with input_guard.input_session("click", x=10, y=10, agent=tag):
            with seq_lock:
                active["n"] += 1
                if active["n"] > 1:
                    overlaps.append(tag)
            time.sleep(0.08)
            with seq_lock:
                active["n"] -= 1

    threads = [threading.Thread(target=worker, args=("agent%d" % i,)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)

    assert overlaps == [], "两个执行体同时持有鼠标：%s" % overlaps


def test_lease_timeout_raises_instead_of_stealing(monkeypatch):
    outer = input_guard.InputLease(timeout_s=2.0, label="outer")
    outer.acquire()
    try:
        inner = input_guard.InputLease(timeout_s=0.2, label="inner")
        with pytest.raises(input_guard.InputDenied) as exc:
            inner.acquire()
        assert exc.value.code == "DESKTOP_INPUT_BUSY"
    finally:
        outer.release()


# ---------------------------------------------------------------------------
# 6. 异常中断必须松手：drag 不能把左键留在按下态
# ---------------------------------------------------------------------------
def test_drag_releases_button_when_trajectory_raises(monkeypatch, live_gate):
    from virtu_omni.computer_use import action as action_mod

    monkeypatch.setattr(action_mod, "user32", live_gate)

    engine = action_mod.ActionEngine()
    monkeypatch.setattr(engine, "adapt_coordinates", lambda x, y, **k: (int(x), int(y)))

    calls = {"n": 0}

    def _boom(px, py):
        calls["n"] += 1
        if calls["n"] >= 2:
            raise RuntimeError("simulated mid-drag crash")
        live_gate.events.append(("move", px, py))

    monkeypatch.setattr(engine, "_move_raw", _boom)

    with pytest.raises(RuntimeError):
        engine.drag(100, 100, 300, 300, steps=5)

    downs = [e for e in live_gate.events if e == ("mouse", 0x0002)]
    ups = [e for e in live_gate.events if e == ("mouse", 0x0004)]
    assert downs, "按下事件应当已发出（否则本用例没有覆盖真实路径）"
    assert len(ups) >= len(downs), "中途崩溃后左键没有被释放：downs=%d ups=%d" % (
        len(downs), len(ups))


def test_drag_clamps_zero_steps(monkeypatch, live_gate):
    from virtu_omni.computer_use import action as action_mod

    monkeypatch.setattr(action_mod, "user32", live_gate)
    engine = action_mod.ActionEngine()
    monkeypatch.setattr(engine, "adapt_coordinates", lambda x, y, **k: (int(x), int(y)))

    res = engine.drag(10, 10, 20, 20, steps=0)   # 旧实现会 ZeroDivisionError
    assert res["ok"] is True
    assert res["steps"] == 1


# ---------------------------------------------------------------------------
# 7. 外力检测：别人动了光标就必须让位
# ---------------------------------------------------------------------------
def test_foreign_motion_detects_other_writer(monkeypatch):
    monkeypatch.setattr(input_guard, "cursor_pos", lambda: (900, 900))
    assert input_guard.foreign_motion((100, 100)) is True
    assert input_guard.foreign_motion((902, 903)) is False


def test_humanoid_move_aborts_on_foreign_writer(monkeypatch):
    from virtu_omni.engine import humanoid_controller as hc

    monkeypatch.setenv("VIRTU_DESKTOP_INPUT", "1")
    monkeypatch.setattr(input_guard, "cursor_pos", lambda: (500, 500))
    monkeypatch.setattr(input_guard, "authorized", lambda: (True, "test"))
    monkeypatch.setattr(input_guard, "is_dry_run", lambda: (False, ""))
    monkeypatch.setattr(input_guard, "kill_switch_active", lambda: (False, ""))
    monkeypatch.setattr(input_guard, "release_all_buttons",
                        lambda: {"released": [], "supported": True})
    monkeypatch.setattr(input_guard, "foreign_motion", lambda *a, **k: True)

    sent = []
    monkeypatch.setattr(hc, "get_cursor_pos", lambda: (100, 100))
    monkeypatch.setattr(hc, "send_inputs", lambda inputs: sent.append(len(inputs)))

    mouse = hc.HumanoidMouse(mode="human")
    res = mouse.move_to(600, 400)

    assert res["aborted"] == "foreign_cursor_writer"
    assert len(sent) == 1, "检测到外力后应立刻停止，而不是继续走完整条轨迹"


# ---------------------------------------------------------------------------
# 8. 未授权时三套执行器都不许碰总线
# ---------------------------------------------------------------------------
def test_action_engine_simulates_when_unauthorized(monkeypatch):
    from virtu_omni.computer_use import action as action_mod

    monkeypatch.delenv("VIRTU_DESKTOP_INPUT", raising=False)
    monkeypatch.setattr(input_guard, "kill_switch_active", lambda: (False, ""))
    monkeypatch.setattr(input_guard, "is_dry_run", lambda: (False, ""))
    monkeypatch.setattr(input_guard, "cursor_pos", lambda: (500, 500))

    fake = _FakeUser32()
    monkeypatch.setattr(action_mod, "user32", fake)

    engine = action_mod.ActionEngine()
    res = engine.click(400, 300)
    assert res["ok"] is True
    assert res["status"] == "simulated"
    assert res["input_sent"] is False
    assert fake.events == [], "未授权时不应发出任何 Win32 输入事件"


def test_humanoid_simulates_when_unauthorized(monkeypatch):
    from virtu_omni.engine import humanoid_controller as hc

    monkeypatch.delenv("VIRTU_DESKTOP_INPUT", raising=False)
    monkeypatch.setattr(input_guard, "kill_switch_active", lambda: (False, ""))
    monkeypatch.setattr(input_guard, "is_dry_run", lambda: (False, ""))
    monkeypatch.setattr(input_guard, "cursor_pos", lambda: (500, 500))

    sent = []
    monkeypatch.setattr(hc, "send_inputs", lambda inputs: sent.append(len(inputs)))

    res = hc.HumanoidMouse(mode="human").click(300, 200)
    assert res["status"] == "simulated"
    assert res["input_sent"] is False
    assert sent == []


# ---------------------------------------------------------------------------
# 9. SendInput 归一化：右下角必须映射到 65535，而不是差几个单位
# ---------------------------------------------------------------------------
def test_absolute_normalization_reaches_edge(monkeypatch):
    from virtu_omni.engine import humanoid_controller as hc

    monkeypatch.setattr(hc, "get_virtual_bounds", lambda: (0, 0, 1920, 1080))
    mouse = hc.HumanoidMouse(mode="warp")

    nx, ny = mouse._to_normalized_absolute(0, 0)
    assert (nx, ny) == (0, 0)

    nx, ny = mouse._to_normalized_absolute(1919, 1079)
    assert nx == 65535, "右下角应精确映射到 65535，旧实现是 %d" % nx
    assert ny == 65535

    # 中间像素按比例线性映射（截图取整允许 1 个单位误差）。
    # 旧实现 int(x*65536/1920) 在这里会低 17 个单位的系统性偏差。
    for x in (1, 480, 960, 1440, 1918):
        nx, _ = mouse._to_normalized_absolute(x, 0)
        assert abs(nx - x * 65535 / 1919) <= 1, "x=%d 映射偏差过大: %d" % (x, nx)


def test_negative_virtual_origin_supported(monkeypatch):
    """副屏在主屏左侧时坐标为负，不能把光标甩到 (0,0)。"""
    from virtu_omni.engine import humanoid_controller as hc

    monkeypatch.setattr(hc, "get_virtual_bounds", lambda: (-1920, 0, 1920, 1080))
    mouse = hc.HumanoidMouse(mode="warp")

    nx, ny = mouse._to_normalized_absolute(-1920, 0)
    assert nx == 0
    nx, _ = mouse._to_normalized_absolute(-10, 0)
    assert 0 < nx < 65535


# ---------------------------------------------------------------------------
# 10. 审计：拒绝与放行都要留痕，且能读出拒绝原因
# ---------------------------------------------------------------------------
def test_audit_records_denial(monkeypatch):
    monkeypatch.delenv("VIRTU_DESKTOP_INPUT", raising=False)
    monkeypatch.delenv("VIRTU_DESKTOP_KILL", raising=False)
    monkeypatch.setattr(input_guard, "kill_switch_active", lambda: (False, ""))
    monkeypatch.setattr(input_guard, "is_dry_run", lambda: (False, ""))
    monkeypatch.setattr(input_guard, "cursor_pos", lambda: (500, 500))

    before = len(input_guard.audit_tail(500))
    with input_guard.input_session("click", x=1, y=1, agent="test-agent"):
        pass
    records = input_guard.audit_tail(500)[before:]
    assert any(r.get("verdict_code") == "DESKTOP_INPUT_NOT_APPROVED"
               and r.get("agent") == "test-agent" for r in records)
