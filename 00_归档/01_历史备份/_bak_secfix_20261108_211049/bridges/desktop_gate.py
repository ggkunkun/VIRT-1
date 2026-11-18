# -*- coding: utf-8 -*-
"""桌面输入闸门：模型侧唯一漏斗 execute_tool_call 上的 fail-closed 判定。

为什么要有这个模块：cadcam_desktop_gui 的 click/focus/type_text/hotkey/
dismiss_dialogs 会真的往这台机器的鼠标键盘总线上写，而模型是会产生幻觉调用的
那一侧。第三方 MCP 服务器的 approve_automation / 限速 / kill_switch 只保护它
自己那条通道，仓内通道（REST 桥、MCP 桥、CLI、router 的 FUNCTION_CALLING
分支、workbuddy 的 "Auto-executing" 循环）全部绕过它们，直连 SendInput。
"""

import ctypes
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

MUTATING_ACTIONS = frozenset({"click", "focus", "type_text", "hotkey", "dismiss_dialogs", "drag", "scroll"})
READ_ONLY_ACTIONS = frozenset({"capture", "inspect_window", "move"})

# 通用宿主进程不能用来"证明焦点属于目标软件"：vericut 的 process_names 里就有
# javaw.exe，放行等于对任意 Java 窗口注键。
GENERIC_HOST_PROCESSES = frozenset({
    "javaw.exe", "java.exe", "python.exe", "pythonw.exe", "node.exe",
    "cmd.exe", "powershell.exe", "pwsh.exe", "conhost.exe", "explorer.exe",
    "windowsterminal.exe", "wt.exe", "taskhostw.exe",
})

OPT_IN_ENV = "VIRTU_DESKTOP_INPUT"
KILL_ENV = "VIRTU_DESKTOP_KILL"
RATE_ENV = "VIRTU_DESKTOP_MAX_PER_MIN"
APPROVAL_ENV = "VIRTU_DESKTOP_APPROVAL_FILE"
APPROVAL_TTL_ENV = "VIRTU_DESKTOP_APPROVAL_TTL_S"
AUDIT_ENV = "VIRTU_DESKTOP_AUDIT_LOG"
ALLOWED_PIDS_ENV = "VIRTU_DESKTOP_ALLOWED_PIDS"

DEFAULT_MAX_PER_MIN = 20
DEFAULT_APPROVAL_TTL_S = 600.0

_stamp_cache = []  # type: List[float]


def _u():
    return ctypes.windll.user32


def screen_bounds() -> Tuple[int, int, int, int]:
    """虚拟桌面矩形 (x0, y0, x1, y1)；多屏时含负坐标。"""
    u = _u()
    x0 = u.GetSystemMetrics(76)
    y0 = u.GetSystemMetrics(77)
    w = u.GetSystemMetrics(78)
    h = u.GetSystemMetrics(79)
    return (x0, y0, x0 + w, y0 + h)


def foreground_hwnd() -> int:
    """当前前台窗口句柄；测试/取证用它来"用完即还原焦点"，不长期占用操作者输入。"""
    return int(_u().GetForegroundWindow() or 0)


def foreground_pid() -> int:
    u = _u()
    hwnd = u.GetForegroundWindow()
    if not hwnd:
        return 0
    pid = ctypes.c_ulong(0)
    u.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid))
    return int(pid.value)


def running_pids() -> Dict[str, List[int]]:
    from bridges.software_registry import get_running_processes
    return get_running_processes()


def authorized_targets(software: str) -> Tuple[Dict[str, List[int]], List[str]]:
    """目标软件当前可注键的 exe→pids，以及被剔除的通用宿主名。"""
    from bridges.software_registry import SOFTWARE_SPECS
    key = (software or "").strip().lower()
    aliased = {"solidworks": "solidworks", "sw": "solidworks", "acad": "autocad",
               "cimcoedit": "cimco", "siemens nx": "nx"}
    key = aliased.get(key, key)
    spec = SOFTWARE_SPECS.get(key)
    if not spec:
        return {}, []
    names = [str(n).lower() for n in (spec.get("process_names") or [])]
    dropped = [n for n in names if n in GENERIC_HOST_PROCESSES]
    names = [n for n in names if n not in GENERIC_HOST_PROCESSES]
    try:
        table = running_pids()
    except Exception:
        return {}, dropped
    by_exe = {}
    for k, v in table.items():
        kk = str(k).lower()
        if kk in names:
            by_exe[kk] = list(v or [])
    return by_exe, dropped


_DANGEROUS_COMBOS = (
    ({"win"}, "Windows 键组合可锁屏/唤出系统面板/注销"),
    ({"alt", "f4"}, "Alt+F4 会关闭当前焦点窗口"),
    ({"ctrl", "alt", "del"}, "Ctrl+Alt+Del 是系统安全序列"),
    ({"ctrl", "shift", "esc"}, "Ctrl+Shift+Esc 打开任务管理器"),
)


def _blocked(code: str, detail: str, **ev) -> Dict[str, Any]:
    out = {"status": "blocked", "verdict_code": code, "detail": detail,
            "channel": "repo_execute_tool_call", "input_sent": False}
    out.update({k: v for k, v in ev.items() if v is not None})
    return out


def _hotkey_tokens(keys: str) -> List[str]:
    return [t.strip().lower() for t in str(keys or "").replace("+", ",").split(",") if t.strip()]


def _dangerous(keys: str) -> Optional[str]:
    toks = set(_hotkey_tokens(keys))
    for combo, why in _DANGEROUS_COMBOS:
        if combo <= toks:
            return "%s -> %s" % ("+".join(sorted(combo)), why)
    return None


def _rate_ok() -> Tuple[bool, int, int]:
    try:
        cap = int(os.environ.get(RATE_ENV) or DEFAULT_MAX_PER_MIN)
    except ValueError:
        cap = DEFAULT_MAX_PER_MIN
    now = time.monotonic()
    _stamp_cache[:] = [s for s in _stamp_cache if now - s < 60.0]
    if cap <= 0 or len(_stamp_cache) >= cap:
        return False, len(_stamp_cache), cap
    _stamp_cache.append(now)
    return True, len(_stamp_cache), cap


def _approval_fresh() -> Tuple[bool, Optional[float], str]:
    path = os.environ.get(APPROVAL_ENV) or ""
    if not path:
        return True, None, ""
    try:
        age = time.time() - os.path.getmtime(path)
    except OSError:
        return False, None, path
    try:
        ttl = float(os.environ.get(APPROVAL_TTL_ENV) or DEFAULT_APPROVAL_TTL_S)
    except ValueError:
        ttl = DEFAULT_APPROVAL_TTL_S
    return age <= ttl, age, path


def operator_approved_pids() -> List[int]:
    """操作者点名的例外（测试窗口、非六大软件的自研工具）。只放宽目标绑定。"""
    raw = os.environ.get(ALLOWED_PIDS_ENV) or ""
    out = []
    for tok in raw.replace(";", ",").split(","):
        tok = tok.strip()
        if tok.isdigit():
            out.append(int(tok))
    return sorted(set(out))


def _focus_binding(software: str) -> Dict[str, Any]:
    """把"当前焦点属于目标软件（或操作者点名的 PID）"作为注键/注鼠的前置条件。"""
    by_exe, dropped = authorized_targets(software)
    pid = foreground_pid()
    approved = operator_approved_pids()
    allowed_pids = sorted({p for v in by_exe.values() for p in v} | set(approved))
    return {"software": software, "foreground_pid": pid, "allowed_pids": allowed_pids,
            "matched_exes": sorted(by_exe), "operator_approved_pids": approved,
            "dropped_generic_hosts": dropped}


def evaluate(tool_name: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """返回 None 表示放行；返回 dict 表示拦下，调用方应把它原样作为工具结果。"""
    if tool_name != "cadcam_desktop_gui":
        return None
    args = args or {}
    act = str(args.get("action") or "capture").strip().lower()
    if act in READ_ONLY_ACTIONS:
        return None
    if act not in MUTATING_ACTIONS:
        return _blocked("DESKTOP_ACTION_UNKNOWN",
                        "未知动作 %r，不在只读/可变更任一集合内" % act)

    if str(os.environ.get(KILL_ENV) or "") == "1":
        return _blocked("DESKTOP_KILLED", "%s=1，kill switch 优先于任何授权" % KILL_ENV,
                        attempted_action=act)
    if str(os.environ.get(OPT_IN_ENV) or "") != "1":
        return _blocked("DESKTOP_INPUT_NOT_APPROVED",
                        "模型侧要发真实键鼠输入必须先设 %s=1；默认不设即拒绝" % OPT_IN_ENV,
                        attempted_action=act)
    fresh, age, apath = _approval_fresh()
    if not fresh:
        return _blocked("DESKTOP_APPROVAL_STALE_OR_MISSING",
                        "批准凭据 %s 不存在或已超过 TTL（age=%s）" % (apath, age),
                        attempted_action=act, approval_age_s=age)
    ok, used, cap = _rate_ok()
    if not ok:
        return _blocked("DESKTOP_RATE_CAPPED",
                        "60 秒内已用 %d/%d 次输入配额，拒绝继续注入" % (used, cap),
                        attempted_action=act, actions_last_60s=used, cap=cap)

    if act == "click":
        x, y = args.get("x"), args.get("y")
        if x is None or y is None:
            return _blocked("DESKTOP_CLICK_NEEDS_EXPLICIT_COORDS",
                            "click 必须显式给 x/y；旧代码在这里静默用 (0,0) 或 (500,500) "
                            "当默认值，等于在用户桌面盲点一下",
                            attempted_action=act)
        try:
            xi, yi = int(x), int(y)
        except (TypeError, ValueError):
            return _blocked("DESKTOP_CLICK_COORDS_NOT_INT",
                            "x/y 必须是整数像素坐标，收到 %r/%r" % (x, y), attempted_action=act)
        x0, y0, x1, y1 = screen_bounds()
        if not (x0 <= xi <= x1 and y0 <= yi <= y1):
            return _blocked("DESKTOP_CLICK_OUT_OF_BOUNDS",
                            "坐标 (%d,%d) 落在虚拟桌面 (%d,%d,%d,%d) 之外" % (xi, yi, x0, y0, x1, y1),
                            attempted_action=act)

    if act in ("type_text", "hotkey", "click", "dismiss_dialogs"):
        sw = str(args.get("software") or "").strip()
        if not sw:
            return _blocked("DESKTOP_TARGET_NOT_NAMED",
                            "%s 必须显式指定 software，否则输入会落进用户此刻正看着的任何窗口" % act,
                            attempted_action=act)
        binding = _focus_binding(sw)
        if act in ("type_text", "hotkey", "click"):
            if not binding["allowed_pids"]:
                return _blocked("DESKTOP_TARGET_NOT_RUNNING",
                                "%s 没有可注键的进程实例（通用宿主已被剔除：%s）"
                                % (sw, binding["dropped_generic_hosts"]),
                                attempted_action=act, **binding)
            if binding["foreground_pid"] not in binding["allowed_pids"]:
                return _blocked("DESKTOP_FOREIGN_FOCUS",
                                "当前焦点 PID %s 不属于 %s，拒绝对别人的窗口注键"
                                % (binding["foreground_pid"], sw),
                                attempted_action=act, **binding)
        if act == "hotkey":
            why = _dangerous(args.get("keys", ""))
            if why:
                return _blocked("DESKTOP_HOTKEY_FORBIDDEN",
                                "即使命名目标属于该窗口仍拒绝：%s" % why,
                                attempted_action=act, keys=args.get("keys"))
            if not _hotkey_tokens(args.get("keys", "")):
                return _blocked("DESKTOP_HOTKEY_EMPTY", "keys 为空", attempted_action=act)
        if act == "type_text" and not str(args.get("text") or ""):
            return _blocked("DESKTOP_TEXT_EMPTY", "text 为空", attempted_action=act)

    return None


def default_audit_log() -> str:
    return os.environ.get(AUDIT_ENV) or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "runs", "desktop_gate", "decisions.jsonl")


def audit(tool_name: str, args: Dict[str, Any], verdict: Optional[Dict[str, Any]],
          log_path: str = "") -> Dict[str, Any]:
    """留痕。绝不写入被敲入的原文——只记长度与指纹，避免把用户口令打进日志。"""
    args = args or {}
    rec = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "epoch": time.time(),
        "host_pid": os.getpid(),
        "tool": tool_name,
        "action": args.get("action"),
        "software": args.get("software"),
        "decision": "allowed" if verdict is None else "blocked",
        "verdict_code": None if verdict is None else verdict.get("verdict_code"),
        "input_sent": True if verdict is None else bool(verdict.get("input_sent", False)),
    }
    if args.get("keys"):
        rec["keys"] = args.get("keys")
    if args.get("text") is not None:
        text = str(args.get("text"))
        import hashlib
        rec["text_len"] = len(text)
        rec["text_sha8"] = hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:8]
    path = log_path or default_audit_log()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return rec


def gate(tool_name: str, args: Dict[str, Any], log_path: str = "") -> Optional[Dict[str, Any]]:
    """判定 + 留痕一步到位；返回 None 放行，返回 dict 即为工具应返回的结果。"""
    verdict = evaluate(tool_name, args)
    audit(tool_name, args, verdict, log_path=log_path)
    return verdict
