# -*- coding: utf-8 -*-
"""统一桌面输入闸门（Input Guard / 输入仲裁器）。

为什么必须有它
--------------
``bridges/desktop_gate.py`` 只守着 ``cadcam_desktop_gui`` 这一条漏斗，而仓内至少
还有四条直连 ``SendInput`` / ``SetCursorPos`` 的通道照样能往真机鼠标总线上写：

  * ``virtu_omni.computer_use.action.ActionEngine``
    （被 ``VirtuComputerUse``、``SkillWriterAndMemory`` 与测试直接调用）
  * ``virtu_omni.engine.humanoid_controller.HumanoidMouse``（轨迹动画最多 120Hz）
  * ``bridges.desktop_controller.DesktopController``
  * ``skills/computer-use/scripts/input_action.py`` / ``win_input.py``（CLI）

于是就有了"智能体突然失控抢鼠标"：一次幻觉调用、后台 pytest、或两个并发
agent，都能把操作者的光标拽走、把左键按住不放、或让光标在两个目标之间来回抽动。

本模块是这四条通道的唯一仲裁点，六条契约（每条都可证伪）：

1. **fail-closed**：``VIRTU_DESKTOP_INPUT`` 不为 ``"1"`` 就拒绝，不做"静默真发"。
2. **可中止**：``VIRTU_DESKTOP_KILL=1`` 或 ``runs/desktop_input/STOP`` 存在即拒绝；
   光标落到屏幕四角 failsafe 区同样立即中止（给操作者一个"甩到角落就停"的刹车）。
3. **单人操作**：跨进程文件锁租约，同一时刻只有一个执行体持有鼠标；并发者排队，
   而不是两个 agent 各自 ``SetCursorPos`` 互相打断——那正是"乱跳"的观感来源。
4. **不留残留**：任何异常/中断路径都释放按键；提供 :func:`release_all_buttons` 兜底，
   避免"左键一直按着、用户一动就变成拖选"。
5. **用户优先**：执行中检测到光标偏离我方轨迹或出现非我方按键 → 立即中止让位。
6. **可追溯**：每次放行/拒绝都写 ``runs/desktop_input/input_audit.jsonl``（含 agent 标识）。

设计上刻意不复用 ``desktop_gate`` 的策略：那套是"模型调用合法性"检查（软件焦点绑定、
热键白名单），本模块是"物理输入总线仲裁"（互斥、让位、残留、急停）。两者串联使用。
"""

from __future__ import annotations

import contextlib
import ctypes
import json
import math
import os
import time
from ctypes import wintypes
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Tuple

__all__ = [
    "InputDenied",
    "InputLease",
    "authorized",
    "clear_panic",
    "cursor_pos",
    "failsafe_triggered",
    "foreign_motion",
    "input_session",
    "is_dry_run",
    "kill_switch_active",
    "panic",
    "point_in_virtual_desktop",
    "release_all_buttons",
    "screen_virtual_bounds",
    "audit_tail",
]

# --------------------------------------------------------------------------
# 环境开关
# --------------------------------------------------------------------------
OPT_IN_ENV = "VIRTU_DESKTOP_INPUT"          # "1" 才允许真发输入
KILL_ENV = "VIRTU_DESKTOP_KILL"             # "1" 立即止血，优先于任何授权
DRYRUN_ENV = "VIRTU_DESKTOP_INPUT_DRYRUN"   # "1" 只演练：返回 ok 但不碰总线
AGENT_ENV = "VIRTU_DESKTOP_AGENT"           # 审计里的执行体标识
LOCK_TIMEOUT_ENV = "VIRTU_DESKTOP_LOCK_TIMEOUT_S"
LOCK_TTL_ENV = "VIRTU_DESKTOP_LOCK_TTL_S"

DEFAULT_LOCK_TIMEOUT_S = 8.0
DEFAULT_LOCK_TTL_S = 120.0

#: failsafe：光标落在屏幕四角这么多像素内就当作操作者的急停动作
FAILSAFE_MARGIN_PX = 2

#: 判断"光标被别人挪了"的容差（px）。太小会被 DPI 取整误判，太大会漏掉真实抢占。
FOREIGN_MOTION_TOL_PX = 6

_ON_WINDOWS = os.name == "nt"


def _u():
    return ctypes.windll.user32


def _env_is(name: str, value: str = "1") -> bool:
    return str(os.environ.get(name) or "").strip().lower() == value


# --------------------------------------------------------------------------
# 路径（工作区内的运行态目录，跟 desktop_gate 平级）
# --------------------------------------------------------------------------
def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _state_dir() -> Path:
    d = Path(os.environ.get("VIRTU_DESKTOP_STATE_DIR") or (_repo_root() / "runs" / "desktop_input"))
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return d


def stop_file() -> Path:
    return _state_dir() / "STOP"


def lock_file() -> Path:
    return _state_dir() / "input.lock"


def audit_log() -> Path:
    return _state_dir() / "input_audit.jsonl"


# --------------------------------------------------------------------------
# 拒绝异常
# --------------------------------------------------------------------------
class InputDenied(RuntimeError):
    """输入被闸门拒绝。``code`` 稳定可断言，``detail`` 给人看。"""

    def __init__(self, code: str, detail: str, **evidence: Any) -> None:
        super().__init__("%s: %s" % (code, detail))
        self.code = code
        self.detail = detail
        self.evidence = evidence

    def as_result(self, action: str = "") -> Dict[str, Any]:
        out = {
            "ok": False,
            "status": "blocked",
            "action": action,
            "verdict_code": self.code,
            "detail": self.detail,
            "input_sent": False,
        }
        out.update({k: v for k, v in self.evidence.items() if v is not None})
        return out


# --------------------------------------------------------------------------
# 授权 / 急停 / 演练判定
# --------------------------------------------------------------------------
def kill_switch_active() -> Tuple[bool, str]:
    """急停是否生效。环境变量与 STOP 文件任一命中即视为急停。"""
    if _env_is(KILL_ENV):
        return True, "%s=1" % KILL_ENV
    sf = stop_file()
    try:
        if sf.is_file():
            return True, "STOP file present: %s" % sf
    except OSError:
        pass
    return False, ""


def _pytest_active() -> bool:
    """pytest 会话内一律演练。

    事故现场：``tests/test_computer_use_integration.py`` 直接对真机发
    ``click(400,300)`` + ``ctrl+s`` + ``drag(10,10->50,50)``，跑一次就把操作者的
    光标拽走一次。测试要验的是"指令构造正确"，不该验"桌面真的被点了"。
    """
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    if os.environ.get("VIRTU_PYTEST_ACTIVE") == "1":
        return True
    import sys
    return "pytest" in sys.modules


def authorized() -> Tuple[bool, str]:
    """是否允许真发输入。默认 False（fail-closed）。"""
    if _env_is(OPT_IN_ENV):
        return True, "%s=1" % OPT_IN_ENV
    return False, "%s != 1（默认拒绝真实键鼠输入）" % OPT_IN_ENV


def is_dry_run() -> Tuple[bool, str]:
    """是否处于演练模式：调用方拿到 ``ok=True``，但总线上不会出现任何事件。"""
    if _env_is(DRYRUN_ENV):
        return True, "%s=1" % DRYRUN_ENV
    if _pytest_active():
        return True, "pytest session -> forced dry-run"
    return False, ""


# --------------------------------------------------------------------------
# 光标 / 屏幕 / 外力检测
# --------------------------------------------------------------------------
def cursor_pos() -> Tuple[int, int]:
    if not _ON_WINDOWS:
        return (0, 0)
    pt = wintypes.POINT()
    _u().GetCursorPos(ctypes.byref(pt))
    return int(pt.x), int(pt.y)


def screen_virtual_bounds() -> Tuple[int, int, int, int]:
    """虚拟桌面矩形 (x0, y0, x1, y1)，多屏时含负坐标。

    旧代码把坐标 clamp 到 ``[0, primary_w-1]``，在副屏（负坐标或超出主屏宽度）
    上操作时会把光标直接甩到主屏左上角——看起来就是"失控"。
    """
    if not _ON_WINDOWS:
        return (0, 0, 1920, 1080)
    u = _u()
    x0 = u.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN
    y0 = u.GetSystemMetrics(77)   # SM_YVIRTUALSCREEN
    w = u.GetSystemMetrics(78)    # SM_CXVIRTUALSCREEN
    h = u.GetSystemMetrics(79)    # SM_CYVIRTUALSCREEN
    if w <= 0 or h <= 0:
        return (0, 0, u.GetSystemMetrics(0), u.GetSystemMetrics(1))
    return (int(x0), int(y0), int(x0 + w), int(y0 + h))


def point_in_virtual_desktop(x: int, y: int) -> bool:
    x0, y0, x1, y1 = screen_virtual_bounds()
    return x0 <= int(x) <= x1 and y0 <= int(y) <= y1


def failsafe_triggered(margin: int = FAILSAFE_MARGIN_PX) -> Tuple[bool, Tuple[int, int]]:
    """光标贴到屏幕四角 = 操作者的急停手势（沿用 pyautogui 的约定）。"""
    x, y = cursor_pos()
    x0, y0, x1, y1 = screen_virtual_bounds()
    hit = ((abs(x - x0) <= margin or abs(x - x1) <= margin) and
           (abs(y - y0) <= margin or abs(y - y1) <= margin))
    return hit, (x, y)


def foreign_motion(expected: Optional[Tuple[int, int]], tol: int = FOREIGN_MOTION_TOL_PX) -> bool:
    """光标是否偏离了"我方轨迹下一步该在的位置"。

    轨迹动画期间每步都会回读光标。若实际位置与预期差得离谱，说明有别的执行体
    （另一个 agent / 操作者的真鼠标）在同时写光标，继续走完只会让两边互相拉扯。
    """
    if expected is None:
        return False
    ax, ay = cursor_pos()
    return math.hypot(ax - expected[0], ay - expected[1]) > tol


def _button_states() -> Dict[str, bool]:
    if not _ON_WINDOWS:
        return {}
    u = _u()
    # VK_LBUTTON=0x01 VK_RBUTTON=0x02 VK_MBUTTON=0x04
    return {
        "left": bool(u.GetAsyncKeyState(0x01) & 0x8000),
        "right": bool(u.GetAsyncKeyState(0x02) & 0x8000),
        "middle": bool(u.GetAsyncKeyState(0x04) & 0x8000),
    }


def release_all_buttons() -> Dict[str, Any]:
    """兜底释放鼠标键与常用修饰键。异常退出/中止后调用，避免"键一直按着"。"""
    if not _ON_WINDOWS:
        return {"released": [], "supported": False}
    u = _u()
    released = []
    before = _button_states()
    # MOUSEEVENTF_LEFTUP=0x0004 RIGHTUP=0x0010 MIDDLEUP=0x0040
    for name, flag in (("left", 0x0004), ("right", 0x0010), ("middle", 0x0040)):
        if before.get(name):
            u.mouse_event(flag, 0, 0, 0, 0)
            released.append("mouse:" + name)
    # 修饰键 KEYUP：shift 0x10 ctrl 0x11 alt 0x12 win 0x5B
    for name, vk in (("shift", 0x10), ("ctrl", 0x11), ("alt", 0x12), ("win", 0x5B)):
        if u.GetAsyncKeyState(vk) & 0x8000:
            u.keybd_event(vk, 0, 0x0002, 0)
            released.append("key:" + name)
    if released:
        _write_audit({"event": "release_all_buttons", "released": released,
                      "agent": os.environ.get(AGENT_ENV) or "unknown"})
    return {"released": released, "supported": True, "before": before}


# --------------------------------------------------------------------------
# 跨进程互斥租约
# --------------------------------------------------------------------------
class InputLease:
    """跨进程鼠标租约（``msvcrt.locking`` 非阻塞锁 + 超时排队）。

    没有它，两个并发 agent 会各自 ``SetCursorPos``：A 移到 (400,300) 点击的瞬间
    B 把光标拉去 (100,100)，A 的 click 就落在 B 的目标上——这就是"抢鼠标"。
    """

    def __init__(self, timeout_s: Optional[float] = None, label: str = "") -> None:
        self.label = label
        self._fh = None
        if timeout_s is None:
            try:
                timeout_s = float(os.environ.get(LOCK_TIMEOUT_ENV) or DEFAULT_LOCK_TIMEOUT_S)
            except ValueError:
                timeout_s = DEFAULT_LOCK_TIMEOUT_S
        self.timeout_s = timeout_s
        self.waited_s = 0.0

    def acquire(self) -> "InputLease":
        if not _ON_WINDOWS:
            return self
        import msvcrt

        path = str(lock_file())
        deadline = time.monotonic() + self.timeout_s
        fh = open(path, "a+b")
        # 锁文件至少要 1 字节才能锁定区域
        fh.seek(0, os.SEEK_END)
        if fh.tell() == 0:
            fh.write(b"\0")
            fh.flush()
        waited_start = time.monotonic()
        while True:
            try:
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                self._fh = fh
                self.waited_s = round(time.monotonic() - waited_start, 3)
                if self.waited_s > 0.05:
                    _write_audit({"event": "lease_waited", "label": self.label,
                                  "waited_s": self.waited_s})
                return self
            except OSError:
                if time.monotonic() >= deadline:
                    fh.close()
                    raise InputDenied(
                        "DESKTOP_INPUT_BUSY",
                        "另一个执行体已持有鼠标租约超过 %.1fs；拒绝并发抢占" % self.timeout_s,
                        lock_file=path,
                    )
                time.sleep(0.02)

    def release(self) -> None:
        if self._fh is None:
            return
        try:
            import msvcrt
            self._fh.seek(0)
            msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        finally:
            try:
                self._fh.close()
            except OSError:
                pass
            self._fh = None

    def __enter__(self) -> "InputLease":
        return self.acquire()

    def __exit__(self, *exc) -> None:
        self.release()


# --------------------------------------------------------------------------
# 审计
# --------------------------------------------------------------------------
def _write_audit(rec: Dict[str, Any]) -> None:
    rec = dict(rec)
    rec.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%S"))
    rec.setdefault("epoch", round(time.time(), 3))
    rec.setdefault("pid", os.getpid())
    try:
        with open(audit_log(), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass


def audit_tail(n: int = 20) -> list:
    """给排障用：最近 n 条输入审计。"""
    try:
        with open(audit_log(), "r", encoding="utf-8") as fh:
            lines = [ln for ln in fh.read().splitlines() if ln.strip()]
        return [json.loads(ln) for ln in lines[-max(0, n):]]
    except (OSError, ValueError):
        return []


# --------------------------------------------------------------------------
# 会话入口
# --------------------------------------------------------------------------
@contextlib.contextmanager
def input_session(
    action: str,
    *,
    agent: str = "",
    target: str = "",
    x: Optional[int] = None,
    y: Optional[int] = None,
    require_bounds: bool = False,
    lease: bool = True,
) -> Iterator[Dict[str, Any]]:
    """一次真实输入动作的完整生命周期：判定 → 加锁 → 执行 → 释放残留 → 审计。

    用法::

        with input_session("click", agent="swarm.worker3", x=400, y=300) as ctx:
            if ctx["dry_run"]:
                return {"ok": True, "dry_run": True}   # 演练：不碰总线
            ...真实发送...

    拒绝时抛 :class:`InputDenied`，调用方用 ``exc.as_result()`` 转成结构化返回。
    """
    agent = agent or os.environ.get(AGENT_ENV) or "unknown"

    killed, why = kill_switch_active()
    if killed:
        _write_audit({"event": "deny", "action": action, "agent": agent,
                      "verdict_code": "DESKTOP_KILLED", "reason": why})
        raise InputDenied("DESKTOP_KILLED", "%s 生效，拒绝任何键鼠注入" % why,
                          attempted_action=action, agent=agent)

    hit, pos = failsafe_triggered()
    if hit:
        panic("failsafe corner hit at %s" % (pos,))
        _write_audit({"event": "deny", "action": action, "agent": agent,
                      "verdict_code": "DESKTOP_FAILSAFE", "cursor": list(pos)})
        raise InputDenied(
            "DESKTOP_FAILSAFE",
            "光标位于屏幕角落 %s，视为操作者急停；已写入 STOP 文件" % (pos,),
            attempted_action=action, agent=agent, cursor=list(pos),
        )

    if require_bounds and x is not None and y is not None:
        if not point_in_virtual_desktop(x, y):
            x0, y0, x1, y1 = screen_virtual_bounds()
            _write_audit({"event": "deny", "action": action, "agent": agent,
                          "verdict_code": "DESKTOP_POINT_OUT_OF_BOUNDS"})
            raise InputDenied(
                "DESKTOP_POINT_OUT_OF_BOUNDS",
                "目标 (%d,%d) 落在虚拟桌面 (%d,%d,%d,%d) 之外" % (int(x), int(y), x0, y0, x1, y1),
                attempted_action=action, agent=agent,
            )

    allowed, allow_reason = authorized()
    dry, dry_reason = is_dry_run()

    ctx: Dict[str, Any] = {
        "action": action,
        "agent": agent,
        "target": target,
        "allowed": allowed,
        "dry_run": (not allowed) or dry,
        "verdict_code": None if allowed else "DESKTOP_INPUT_NOT_APPROVED",
        "reason": allow_reason if not allowed else (dry_reason or ""),
        "lease_waited_s": 0.0,
    }

    if not allowed:
        _write_audit({"event": "deny", "action": action, "agent": agent, "target": target,
                      "verdict_code": "DESKTOP_INPUT_NOT_APPROVED", "reason": allow_reason})
        # 不抛异常：保持"调用方拿到 ok=False"的旧语义，避免把现有链路打断。
        # 真正的拒绝理由是 verdict_code，调用方必须检查 input_sent。
        yield ctx
        return

    _lease = InputLease(label="%s/%s" % (agent, action)) if (lease and not ctx["dry_run"]) else None
    if _lease is not None:
        try:
            _lease.acquire()
        except InputDenied as exc:
            _write_audit({"event": "deny", "action": action, "agent": agent,
                          "verdict_code": exc.code})
            raise
        ctx["lease_waited_s"] = _lease.waited_s

    try:
        _write_audit({"event": "allow", "action": action, "agent": agent, "target": target,
                      "dry_run": ctx["dry_run"], "reason": ctx["reason"],
                      "cursor": list(cursor_pos())})
        yield ctx
    finally:
        if _lease is not None:
            _lease.release()
        if not ctx["dry_run"]:
            # 无论正常结束还是异常中断，都不许留按下状态。
            release_all_buttons()


# --------------------------------------------------------------------------
# 急停
# --------------------------------------------------------------------------
def panic(reason: str, *, agent: str = "") -> Dict[str, Any]:
    """立即止血：写 STOP 文件 + 释放所有按键。之后任何输入请求都会被拒绝。"""
    released = release_all_buttons()
    sf = stop_file()
    try:
        sf.write_text(
            json.dumps({"reason": reason, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "pid": os.getpid(), "agent": agent or os.environ.get(AGENT_ENV) or "unknown"},
                       ensure_ascii=False),
            encoding="utf-8")
    except OSError:
        pass
    _write_audit({"event": "panic", "reason": reason, "agent": agent or "unknown",
                  "released": released.get("released")})
    return {"ok": True, "panic": True, "reason": reason,
            "stop_file": str(sf), "released": released.get("released")}


def clear_panic() -> Dict[str, Any]:
    """解除急停（操作者确认可以恢复自动化时调用）。"""
    sf = stop_file()
    removed = False
    try:
        if sf.is_file():
            sf.unlink()
            removed = True
    except OSError:
        pass
    os.environ.pop(KILL_ENV, None)
    _write_audit({"event": "clear_panic", "removed": removed})
    return {"ok": True, "removed": removed, "stop_file": str(sf)}
