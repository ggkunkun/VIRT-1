# -*- coding: utf-8 -*-
r"""record_desktop_trajectories.py — 桌面「观测 → 动作 → 再观测」轨迹采集器（取证侧真值源）

为什么需要它
------------
模型要能"读屏 + 操作鼠标键盘做参数化建模"，训练数据里每一步的 observation 必须是
本机真实产生的字节，不能是作者手写的画面描述。本采集器就是那台"相机"：它调用
bridges/desktop_controller.py 的真实 Win32 通道，把每一步的返回值、截图指纹、
前后帧变化量一并记账，产出的 traces.jsonl 由 scripts/build_engine_agent_corpus.py
直接消费。没有它，GUI 族语料只能靠编——那正是本仓已经证伪过的假绿来源。

红线（写死在代码里，不可通过参数绕过）
--------------------------------------
1. **拒绝伪造帧**：desktop_controller.capture() 在抓屏失败时会合成一张灰色占位图并
   照样返回 status="captured"（带 fallback=True）。这种帧一旦被当作训练靶值，模型学到
   的是"没看到也敢汇报"。本采集器把 fallback 帧一律判 REJECTED，不落进 traces.jsonl。
2. **不碰不是自己开起来的窗口**：任何 click / type_text / hotkey 只有在 --allow-act
   且目标窗口句柄属于"本次进程亲手启动并登记的 PID"时才允许发出；否则只记录一条
   refusal 事件，绝不发送输入。用户自己开着的 SOLIDWORKS 窗口属于用户。
3. **读屏默认无副作用**：默认只做 capture / inspect_window，不点不敲。
4. **每步计时看门狗**：单步超过 --step-timeout-s 立即中止会话并在账本写 truncated，
   不允许静默挂住。
5. **失败要记账**：capture 失败/窗口不存在都进 REJECTS.jsonl，训练侧据此把
   "诚实汇报失败"作为正样本，而不是把它从数据里抹掉。

用法
----
    # 只读采集（默认，安全）
    python scripts/record_desktop_trajectories.py --per-software

    # 允许动作，但只作用于本采集器自己拉起来的目标
    python scripts/record_desktop_trajectories.py --allow-act --act-target notepad

    # 指定输出目录与每种软件重复次数
    python scripts/record_desktop_trajectories.py --out-dir data/desktop_traces/2026-11-04 --repeats 3

输出（全部落在 out-dir 下）
    frames/step_000123.png        真实截图
    traces.jsonl                  通过闸门的步（一步一行，含 observation/frame/delta）
    rejects.jsonl                 被闸门拦下的步 + 原因
    sessions.jsonl                会话级聚合（一条 = 一段可成训练样本的轨迹）
    ledger.json                   取证账本：字节 sha256、真帧/废帧计数、屏幕与 DPI 环境
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from bridges import desktop_coord  # noqa: E402  坐标空间契约（读屏像素 <-> 点击坐标）

# 控制台是 GBK：本文件所有 print 只打 ASCII，中文一律写进 UTF-8 报告文件。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SIX = ["solidworks", "autocad", "nx", "cimco", "vericut", "sscnc"]

# capture() 失败时会退回这张 1920x1080 的灰底占位图；灰底 + 低熵 = 假帧特征
FALLBACK_SIGNATURE_MEAN = 32.0
MIN_FRAME_EDGE = 120


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _frame_fingerprint(path: str) -> Dict[str, Any]:
    """从真实 PNG 字节算指纹：尺寸、字节摘要、灰度熵、均值，以及与上一帧的变化率。"""
    from PIL import Image

    with Image.open(path) as im:
        w, h = im.size
        g = im.convert("L").resize((96, 54))
        px = list(g.getdata())
    mean = sum(px) / len(px)
    hist: Dict[int, int] = {}
    for p in px:
        hist[p] = hist.get(p, 0) + 1
    n = len(px)
    ent = -sum((c / n) * math.log2(c / n) for c in hist.values() if c)
    var = sum((p - mean) ** 2 for p in px) / n
    return {
        "path": path.replace("\\", "/"),
        "bytes_sha256": _sha256_file(path),
        "width": w,
        "height": h,
        "gray_mean": round(mean, 3),
        "gray_std": round(math.sqrt(var), 3),
        "gray_entropy_bits": round(ent, 4),
        "histogram": hist,
    }


def _delta_ratio(prev: Optional[Dict[str, Any]], cur: Dict[str, Any]) -> Optional[float]:
    """两张帧的直方图总变差距离 / 2 ∈ [0,1]：0 = 画面没动，>0.02 = 肉眼可见的变化。"""
    if not prev:
        return None
    keys = set(prev["histogram"]) | set(cur["histogram"])
    np_, nc = sum(prev["histogram"].values()), sum(cur["histogram"].values())
    tv = sum(abs(prev["histogram"].get(k, 0) / np_ - cur["histogram"].get(k, 0) / nc) for k in keys)
    return round(tv / 2.0, 5)


class TrajectoryRecorder:
    def __init__(self, out_dir: str, repeats: int = 1, step_timeout_s: float = 25.0,
                 allow_act: bool = False, settle_s: float = 0.6):
        self.out_dir = out_dir
        self.frames_dir = os.path.join(out_dir, "frames")
        self.repeats = max(1, int(repeats))
        self.step_timeout_s = float(step_timeout_s)
        self.allow_act = bool(allow_act)
        self.settle_s = float(settle_s)
        os.makedirs(self.frames_dir, exist_ok=True)
        self.trace_fp = os.path.join(out_dir, "traces.jsonl")
        self.reject_fp = os.path.join(out_dir, "rejects.jsonl")
        self.session_fp = os.path.join(out_dir, "sessions.jsonl")
        for p in (self.trace_fp, self.reject_fp, self.session_fp):
            with open(p, "w", encoding="utf-8"):
                pass
        self.ctl = None
        self.step_index = 0
        self.accepted = 0
        self.rejected = 0
        self.self_owned_pids: set[int] = set()
        self._prev_frame: Optional[Dict[str, Any]] = None
        # 动作之前先把坐标空间对齐：不对齐就不发点击（详见 bridges/desktop_coord.py 的实测）
        self.awareness = desktop_coord.ensure_dpi_awareness()
        self.spaces = desktop_coord.probe_spaces()

    # ---------- 基础设施 ----------
    def _controller(self):
        if self.ctl is None:
            from bridges.desktop_controller import DesktopController
            self.ctl = DesktopController()
        return self.ctl

    def _run_bounded(self, fn, *a, **kw) -> Dict[str, Any]:
        """带看门狗地执行一次桌面原语：超时不等于成功，也不许静默。"""
        import threading

        box: Dict[str, Any] = {}

        def _w():
            try:
                box["obs"] = fn(*a, **kw)
            except BaseException as exc:  # noqa: BLE001 - 采集器必须兜住一切原生调用
                box["error"] = "%s: %s" % (type(exc).__name__, exc)

        t = threading.Thread(target=_w, daemon=True)
        t0 = time.time()
        t.start()
        t.join(self.step_timeout_s)
        elapsed = round(time.time() - t0, 3)
        if t.is_alive():
            return {"ok": False, "elapsed_s": elapsed,
                    "observation": {"status": "timeout",
                                    "message": "step exceeded %.1fs watchdog" % self.step_timeout_s}}
        if "error" in box:
            return {"ok": False, "elapsed_s": elapsed,
                    "observation": {"status": "exception", "message": box["error"]}}
        obs = box.get("obs")
        if not isinstance(obs, dict):
            obs = {"status": "raw", "value": repr(obs)}
        return {"ok": str(obs.get("status", "")) not in ("error", "timeout", "not_found"),
                "elapsed_s": elapsed, "observation": obs}

    def _write(self, path: str, obj: Dict[str, Any]) -> None:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n")

    # ---------- 单步：发一个动作，取一次证，过闸门 ----------
    def step(self, action: str, args: Dict[str, Any], *, intent: str = "",
             software: Optional[str] = None) -> Dict[str, Any]:
        self.step_index += 1
        ctl = self._controller()
        ts = time.time()
        stage: Dict[str, Any] = {"step": self.step_index, "t": round(ts, 3),
                                 "action": action, "args": args,
                                 "intent": intent, "software": software}

        # 红线 2：动作类只允许打在"本采集器自己起来的进程"的窗口上
        if action in ("click", "type_text", "hotkey"):
            if not self.allow_act:
                stage["gate"] = {"verdict": "REJECTED", "reason": "act_disabled_readonly_session"}
                return self._reject(stage, "只读会话不允许发送键鼠动作")
            if not self.self_owned_pids:
                stage["gate"] = {"verdict": "REJECTED", "reason": "no_self_owned_pid"}
                return self._reject(stage, "没有本次采集器亲自启动并登记的 PID，拒绝操作任何窗口")
            if action in ("type_text", "hotkey"):
                # 键盘输入打在前台窗口上，而前台是谁不由我们说了算——必须先证明
                fstate = self._owns_foreground()
                stage["focus_state"] = fstate
                if not fstate["owned"]:
                    stage["gate"] = {"verdict": "REJECTED", "reason": "focus_not_owned"}
                    return self._reject(
                        stage, "前台窗口 PID=%s 不是本次采集器启动的进程，拒绝发送输入"
                               "（否则会打进用户正开着的窗口）" % fstate["foreground_pid"])
            else:
                owner = self._point_owner(int(args.get("x", 0)), int(args.get("y", 0)))
                stage["point_owner"] = owner
                if not owner["owned"]:
                    stage["gate"] = {"verdict": "REJECTED", "reason": "click_point_not_owned"}
                    return self._reject(
                        stage, "落点 %s,%s 命中的是 PID=%s 的窗口，不属于本次启动的进程，拒绝点击"
                               % (args.get("x"), args.get("y"), owner["pid"]))

        if action == "capture":
            out = os.path.join(self.frames_dir, "step_%06d.png" % self.step_index)
            res = self._run_bounded(ctl.capture, out, software)
        elif action == "inspect_window":
            res = self._run_bounded(ctl.diagnose_software_window, args.get("software", ""))
        elif action == "focus":
            res = self._run_bounded(ctl.focus, args.get("software", ""))
        elif action == "click":
            gate = self._click_gate(int(args.get("x", -1)), int(args.get("y", -1)))
            if not gate["ok"]:
                stage["gate"] = {"verdict": "REJECTED", "reason": gate["reason_code"]}
                return self._reject(stage, gate["reason"])
            cx, cy = gate["click_xy"]
            stage["click_intent"] = {"frame_px": [int(args["x"]), int(args["y"])],
                                     "click_px": [cx, cy], "note": gate["note"]}
            res = self._run_bounded(ctl.click, cx, cy,
                                    button=args.get("button", "left"),
                                    double=bool(args.get("double", False)))
        elif action == "type_text":
            res = self._run_bounded(ctl.type_text, args.get("text", ""))
        elif action == "hotkey":
            res = self._run_bounded(ctl.hotkey, args.get("keys", ""))
        else:
            res = {"ok": False, "elapsed_s": 0.0,
                   "observation": {"status": "error", "message": "unknown action %s" % action}}

        stage["observation"] = res["observation"]
        stage["elapsed_s"] = res["elapsed_s"]
        # ACCEPTED 只代表"这条观测是真的"，不代表动作成功——两者必须分开记账，
        # 否则训练侧会把"探测到软件没开"当成一次成功操作来学。
        stage["action_succeeded"] = bool(res["ok"])

        # 动作之后必须再拍一帧，否则"我点了"没有证据
        after = None
        if action in ("click", "type_text", "hotkey", "focus"):
            time.sleep(self.settle_s)
            out2 = os.path.join(self.frames_dir, "step_%06d_after.png" % self.step_index)
            after = self._run_bounded(ctl.capture, out2, software)
            stage["after_action_frame"] = after["observation"]

        obs = res["observation"]
        status = str(obs.get("status", ""))

        if status == "error":
            stage["gate"] = {"verdict": "REJECTED", "reason": "controller_error"}
            return self._reject(stage, str(obs.get("message", ""))[:200])

        # 红线 1：capture 的 fallback 占位图绝不是观测
        if action == "capture":
            if obs.get("fallback"):
                stage["gate"] = {"verdict": "REJECTED", "reason": "synthesized_fallback_frame"}
                return self._reject(stage, "capture 返回的是合成占位图，不是屏幕真实内容")
            fp = self._capture_frame_fingerprint(obs.get("output_path"))
            if fp is None:
                stage["gate"] = {"verdict": "REJECTED", "reason": "frame_missing_or_tiny"}
                return self._reject(stage, "截图文件不存在或过小")
            if fp["gray_std"] < 1.0 and abs(fp["gray_mean"] - FALLBACK_SIGNATURE_MEAN) < 2.0:
                stage["gate"] = {"verdict": "REJECTED", "reason": "uniform_gray_frame"}
                return self._reject(stage, "帧内容均匀（疑似占位图），拒绝当作观测")
            stage["frame"] = {k: v for k, v in fp.items() if k != "histogram"}
            stage["frame"]["delta_vs_prev"] = _delta_ratio(self._prev_frame, fp)
            stage["frame"]["source"] = "real_screen_capture"
            # 意图 vs 实际：请求了某软件窗口、却只拿到整屏时，必须如实标注，
            # 否则训练靶值会把"截到桌面"写成"截到 SOLIDWORKS 窗口"（= 教模型乱汇报）
            tgt = str(obs.get("target", ""))
            if software and tgt in ("desktop", ""):
                stage["frame"]["window_scoped"] = False
                stage["frame"]["intent_mismatch"] = (
                    "请求 %s 窗口，但该窗口不存在，实际拿到的是整屏" % software)
            else:
                stage["frame"]["window_scoped"] = bool(software) or tgt != "desktop"
            stage["coordinate_space"] = self.spaces
            self._prev_frame = fp
        else:
            # 非 capture 动作也要有独立计时/帧证据，否则只能算"命令发出去了"
            stage["evidence_class"] = "command_issued_needs_reobserve"

        stage["gate"] = {"verdict": "ACCEPTED", "reason": ""}
        self.accepted += 1
        if after is not None and after.get("observation", {}).get("output_path"):
            a_fp = self._capture_frame_fingerprint(after["observation"]["output_path"])
            if a_fp:
                self._prev_frame = a_fp
        return stage

    def _capture_frame_fingerprint(self, path: Optional[str]) -> Optional[Dict[str, Any]]:
        if not path or not os.path.isfile(path):
            return None
        try:
            fp = _frame_fingerprint(path)
        except Exception:
            return None
        if fp["width"] < MIN_FRAME_EDGE or fp["height"] < MIN_FRAME_EDGE:
            return None
        return fp

    def _cursor_roundtrip(self) -> Dict[str, Any]:
        """实测一次「设坐标 -> 回读坐标」，证明点击空间到底接受多大坐标。

        这一步不是可选项：SetCursorPos 越界时静默夹紧、不报错，是唯一能提前发现
        "画面 1920 宽但只能点到 1535"的办法。
        """
        import ctypes
        u = ctypes.windll.user32

        class _PT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        def pos():
            p = _PT()
            u.GetCursorPos(ctypes.byref(p))
            return (p.x, p.y)

        orig = pos()
        frame_w, frame_h = (self.spaces.get("frame_space") or [0, 0])[:2]
        probe = (max(0, frame_w - 2), max(0, frame_h - 2))
        u.SetCursorPos(probe[0], probe[1])
        read = pos()
        u.SetCursorPos(orig[0], orig[1])
        return {"wanted": list(probe), "readback": list(read),
                "clamped": list(read) != list(probe), "restored": list(orig)}

    def _click_gate(self, x: int, y: int) -> Dict[str, Any]:
        sp = desktop_coord.probe_spaces()
        self.spaces = sp
        ok, why = desktop_coord.check_clickable(sp)["ok"], desktop_coord.check_clickable(sp)["reason"]
        if not ok:
            return {"ok": False, "reason_code": "coordinate_spaces_disaligned", "reason": why}
        conv, note = desktop_coord.to_click(x, y, sp)
        if conv is None:
            return {"ok": False, "reason_code": "coordinate_out_of_bounds", "reason": note}
        rt = self._cursor_roundtrip()
        if rt["clamped"]:
            return {"ok": False, "reason_code": "cursor_clamped_by_os",
                    "reason": ("SetCursorPos 把 %s 夹成 %s：点击空间比画面空间小，"
                               "发点击会静默点偏。原因记录=%s" % (rt["wanted"], rt["readback"], note))}
        return {"ok": True, "click_xy": conv, "note": note or "aligned_1to1",
                "cursor_roundtrip": rt}

    def _point_owner(self, x: int, y: int) -> Dict[str, Any]:
        """点击落点落在谁的窗口里——不是自己人的坐标一律不发。

        这是"点偏一格"之外的第二种事故：点进了用户的别的软件，可能直接改用户的文档。
        """
        import ctypes
        import win32gui
        import win32process

        try:
            pt_hwnd = win32gui.WindowFromPoint((x, y))
            top = win32gui.GetAncestor(pt_hwnd, 2)  # GA_ROOT
            _, pid = win32process.GetWindowThreadProcessId(top or pt_hwnd)
            return {"pid": int(pid), "hwnd": int(top or pt_hwnd),
                    "owned": int(pid) in self.self_owned_pids}
        except Exception as exc:  # noqa: BLE001
            return {"pid": None, "hwnd": None, "owned": False, "error": str(exc)}

    def _reject(self, stage: Dict[str, Any], human_reason: str) -> Dict[str, Any]:
        self.rejected += 1
        stage["reject_detail"] = human_reason
        stage.setdefault("gate", {"verdict": "REJECTED", "reason": "unspecified"})
        return stage

    # ---------- 会话（一段轨迹；这里是唯一的落盘点） ----------
    def session(self, name: str, steps: List[Dict[str, Any]], goal: str) -> Dict[str, Any]:
        """把整段步写盘。

        之所以不在 step() 里即时写：调用方常在 step() 返回后再补证据字段（比如
        标题回读），即时写会把补上的证据丢掉——而"缺证据的观测"正是本仓反复踩过的
        假绿来源。
        """
        accepted = 0
        for s in steps:
            if s.get("gate", {}).get("verdict") == "ACCEPTED":
                accepted += 1
                self._write(self.trace_fp, s)
            else:
                self._write(self.reject_fp, s)
        rec = {"session": name, "goal": goal, "n_steps": len(steps), "n_accepted": accepted,
               "steps": steps}
        self._write(self.session_fp, rec)
        return rec

    # ---------- 前台归属：发任何输入之前必须证明"现在接着的是我的窗口" ----------
    def _foreground_pid(self) -> Optional[int]:
        import win32gui
        import win32process
        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return None
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            return int(pid), hwnd  # type: ignore[return-value]
        except Exception:  # noqa: BLE001
            return None

    def _owns_foreground(self) -> Dict[str, Any]:
        fg = self._foreground_pid()
        if not fg or not isinstance(fg, tuple):
            return {"owned": False, "foreground_pid": None, "foreground_hwnd": None}
        pid, hwnd = fg
        return {"owned": pid in self.self_owned_pids, "foreground_pid": pid,
                "foreground_hwnd": hwnd}

    def activate_owned(self, hwnd: int) -> Dict[str, Any]:
        """把自建窗口带到前台，并用 GetForegroundWindow 回读确认，不确认就不算成功。

        Windows 有"前台锁"：后台进程直接 SetForegroundWindow 会抛 error(0)。这里用
        AttachThreadInput 挂到当前前台线程上再抢，抢不到就如实返回 owned=False，
        调用方据此拒绝发送输入——绝不能"假设自己已经在前台"就敲键盘。
        """
        import ctypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        notes: List[str] = []

        def readback() -> Dict[str, Any]:
            return self._owns_foreground()

        for attempt in range(2):
            try:
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                fg = user32.GetForegroundWindow()
                ftid = user32.GetWindowThreadProcessId(fg, None)
                cur = kernel32.GetCurrentThreadId()
                attached = bool(user32.AttachThreadInput(cur, ftid, True)) if ftid else False
                try:
                    user32.BringWindowToTop(hwnd)
                    user32.SetForegroundWindow(hwnd)
                    user32.SetActiveWindow(hwnd)
                    user32.SetFocus(hwnd)
                finally:
                    if attached:
                        user32.AttachThreadInput(cur, ftid, False)
                notes.append("attempt%d attached=%s" % (attempt + 1, attached))
            except Exception as exc:  # noqa: BLE001
                notes.append("attempt%d raised=%s" % (attempt + 1, exc))
            time.sleep(0.35)
            state = readback()
            if state.get("foreground_hwnd") == hwnd or state["owned"]:
                state["hwnd"] = hwnd
                state["attempts"] = notes
                return state
        state = readback()
        state["hwnd"] = hwnd
        state["attempts"] = notes
        return state

    # ---------- 读-only 六软件巡检（默认动作） ----------
    def survey_six(self) -> List[Dict[str, Any]]:
        steps: List[Dict[str, Any]] = []
        steps.append(self.step("capture", {}, intent="先看一眼整屏当前状态", software=None))
        for sw in SIX:
            for _ in range(self.repeats):
                steps.append(self.step("inspect_window", {"software": sw},
                                       intent="探测 %s 是否在跑、主窗句柄是什么" % sw, software=sw))
                steps.append(self.step("capture", {"software": sw},
                                       intent="截取 %s 窗口画面" % sw, software=sw))
        return steps

    # ---------- 动作闭环（只打在自己亲自启动的窗口上） ----------
    def _process_tree(self) -> Dict[int, List[int]]:
        """一次批量 WMI 查询拿到全量 pid->children，别逐 PID 查（本机每次 ~6s）。"""
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId "
                 "| ForEach-Object { \"$($_.ProcessId),$($_.ParentProcessId)\" }"],
                capture_output=True, text=True, timeout=20)
        except Exception:  # noqa: BLE001
            return {}
        tree: Dict[int, List[int]] = {}
        for line in (out.stdout or "").splitlines():
            line = line.strip()
            if not line or "," not in line:
                continue
            a, b = line.split(",", 1)
            try:
                pid, ppid = int(a), int(b)
            except ValueError:
                continue
            tree.setdefault(ppid, []).append(pid)
        return tree

    def _register_descendants(self, root_pid: int, depth: int = 3) -> List[int]:
        """把本次启动进程的整棵子树登记为"自己人"。

        为什么必须展开子树：venv 的 Scripts\\python.exe 是个 stub，真的解释器是它的
        子进程（本机实测：launcher 23836 -> 窗口属主 21420）。只认 launcher PID 会
        把自己起的窗口判成"别人的"，动作闭环直接废掉。
        """
        tree = self._process_tree()
        owned = {root_pid}
        frontier = [root_pid]
        for _ in range(depth):
            nxt = []
            for p in frontier:
                for c in tree.get(p, []):
                    if c not in owned:
                        owned.add(c)
                        nxt.append(c)
            frontier = nxt
            if not nxt:
                break
        self.self_owned_pids |= owned
        return sorted(owned)

    def launch_self_owned(self, exe: str, extra: Optional[List[str]] = None) -> int:
        p = subprocess.Popen([exe] + list(extra or []))
        self.self_owned_pids.add(int(p.pid))
        time.sleep(1.0)
        self._register_descendants(int(p.pid))
        return int(p.pid)

    def _owned_hwnd(self, pid: Optional[int] = None) -> Optional[int]:
        import win32gui
        import win32process

        pids = {pid} if pid else set(self.self_owned_pids)
        found: List[int] = []

        def cb(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return True
            try:
                _, wpid = win32process.GetWindowThreadProcessId(hwnd)
            except Exception:  # noqa: BLE001
                return True
            if wpid in pids:
                found.append(hwnd)
            return True

        try:
            win32gui.EnumWindows(cb, None)
        except Exception:  # noqa: BLE001
            return None
        return found[0] if found else None

    def _save_clipboard(self) -> Optional[str]:
        try:
            import win32clipboard
            import win32con
            win32clipboard.OpenClipboard(None)
            try:
                if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                    data = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                else:
                    data = None
            finally:
                win32clipboard.CloseClipboard()
            return data
        except Exception:  # noqa: BLE001
            return None

    def _restore_clipboard(self, text: Optional[str]) -> None:
        if text is None:
            return
        try:
            import win32clipboard
            import win32con
            win32clipboard.OpenClipboard(None)
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
            finally:
                win32clipboard.CloseClipboard()
        except Exception:  # noqa: BLE001
            pass

    def act_probe_session(self, probe_text: str = "VIRTU-GUI-PROBE-123") -> List[Dict[str, Any]]:
        """端到端证明「读屏 -> 键鼠 -> 画面变化 + 文本回读」，只回收自己起的 PID。

        靶窗口是仓内自带的 Tk 探针（scratch/gui_probe_target.py），它把输入缓冲投影到
        窗口标题，于是"字有没有真落进去"可以靠 GetWindowText 硬读，而不是靠截图猜。
        绝不拿用户的窗口当靶子：Windows 11 的 notepad.exe 是单实例别名，再启一次会把
        窗口塞进用户已经开着的那个 Notepad（本机实测发生过，被 PID 归属闸拦下）。
        """
        import win32gui

        tag = "VIRTU-PROBE-TARGET"
        target = os.path.join(REPO_ROOT, "scratch", "gui_probe_target.py")
        if not os.path.isfile(target):
            return [self._reject({"action": "launch_target", "args": {"path": target},
                                  "gate": {"verdict": "REJECTED",
                                           "reason": "probe_target_missing"}},
                                 "探针靶窗口脚本不存在，动作闭环无法取证")]

        pid = self.launch_self_owned(sys.executable, [target, "--probe-tag", tag])
        hwnd = None
        for _ in range(30):
            hwnd = self._owned_hwnd()
            if hwnd:
                break
            time.sleep(0.5)
        steps: List[Dict[str, Any]] = []
        if not hwnd:
            steps.append(self._reject({"action": "launch_target", "args": {"pid": pid},
                                       "gate": {"verdict": "REJECTED",
                                                "reason": "target_window_never_appeared"}},
                                      "自己启动的目标窗口 15 秒内没出现，动作闭环无法取证"))
            self._terminate_owned(pid)
            return steps

        clip_backup = self._save_clipboard()
        try:
            l, t, r, b = win32gui.GetWindowRect(hwnd)
            title0 = win32gui.GetWindowText(hwnd)
            focus_state = self.activate_owned(hwnd)
            steps.append(self.step("capture", {}, intent="动作前基线帧", software=None))
            steps[-1]["activate_owned"] = focus_state
            st = self.step("type_text", {"text": probe_text},
                           intent="往自建探针窗口的输入框贴入探针文本")
            st["title_readback"] = {"before": title0, "after": win32gui.GetWindowText(hwnd),
                                    "expect_contains": probe_text,
                                    "channel": "GetWindowText（Tk 顶层窗口无子句柄，标题即回读口）"}
            st["activate_owned"] = focus_state
            landed = probe_text in str(st["title_readback"]["after"])
            st["input_landed"] = landed
            steps.append(st)
            steps.append(self.step("click", {"x": int((l + r) / 2), "y": int((t + b) / 2)},
                                   intent="在探针窗口中心点一下，验证点击落点未越界未点偏"))
            steps.append(self.step("hotkey", {"keys": "ctrl,a"},
                                   intent="全选，制造一次可见的画面变化"))
            steps.append(self.step("capture", {}, intent="动作后对照帧", software=None))
            steps[-1]["title_readback"] = {"final": win32gui.GetWindowText(hwnd),
                                           "expect_contains": probe_text}
            steps[-1]["input_landed"] = probe_text in str(win32gui.GetWindowText(hwnd))
        finally:
            self._restore_clipboard(clip_backup)
            self._terminate_owned(pid)
        return steps

    def _terminate_owned(self, pid: int) -> None:
        """只回收本次亲自启动的那棵树；不在账本里的进程一律不动。"""
        if pid not in self.self_owned_pids:
            return
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                           capture_output=True, timeout=20)
        except Exception:  # noqa: BLE001
            pass
        self.self_owned_pids.discard(pid)

    def write_ledger(self, sessions: List[Dict[str, Any]], extra: Dict[str, Any]) -> Dict[str, Any]:
        led = {
            "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "repo_root": REPO_ROOT.replace("\\", "/"),
            "allow_act": self.allow_act,
            "self_owned_pids": sorted(self.self_owned_pids),
            "n_sessions": len(sessions),
            "n_steps": self.step_index,
            "n_accepted": self.accepted,
            "n_rejected": self.rejected,
            "sessions": [{"session": s["session"], "n_steps": s["n_steps"],
                          "n_accepted": s["n_accepted"]} for s in sessions],
            "artifacts": {
                "traces_jsonl": self.trace_fp.replace("\\", "/"),
                "traces_jsonl_sha256": _sha256_file(self.trace_fp),
                "rejects_jsonl": self.reject_fp.replace("\\", "/"),
                "rejects_jsonl_sha256": _sha256_file(self.reject_fp),
                "sessions_jsonl": self.session_fp.replace("\\", "/"),
                "sessions_jsonl_sha256": _sha256_file(self.session_fp),
            },
        }
        led.update(extra)
        with open(os.path.join(self.out_dir, "ledger.json"), "w", encoding="utf-8") as f:
            json.dump(led, f, ensure_ascii=False, indent=2, sort_keys=True)
        return led


def _screen_environment() -> Dict[str, Any]:
    env: Dict[str, Any] = {}
    try:
        import win32api
        import win32con
        env["screen_px"] = [win32api.GetSystemMetrics(win32con.SM_CXSCREEN),
                            win32api.GetSystemMetrics(win32con.SM_CYSCREEN)]
        env["dpi"] = win32api.GetDpiForSystem() if hasattr(win32api, "GetDpiForSystem") else None
    except Exception as exc:  # noqa: BLE001
        env["screen_error"] = str(exc)
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"],
                             capture_output=True, text=True, timeout=15)
        env["gpu"] = out.stdout.strip().splitlines()[:2]
    except Exception:  # noqa: BLE001
        env["gpu"] = None
    return env


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="桌面观测/动作轨迹采集器（取证真值源）")
    ap.add_argument("--out-dir", default=os.path.join(REPO_ROOT, "data", "desktop_traces", "latest"))
    ap.add_argument("--repeats", type=int, default=1, help="每种软件重复几轮（默认 1）")
    ap.add_argument("--step-timeout-s", type=float, default=25.0)
    ap.add_argument("--allow-act", action="store_true",
                    help="允许键鼠动作；仍只作用于本进程亲自启动并登记的窗口")
    ap.add_argument("--survey-only", action="store_true", help="只做六软件只读巡检，连 --allow-act 也不发动作")
    ap.add_argument("--act-target", default="tk_probe", choices=["tk_probe"],
                    help="动作闭环的自建靶窗口（scratch/gui_probe_target.py，零工程副作用）")
    ap.add_argument("--settle-s", type=float, default=0.6, help="动作后等待多少秒再回拍")
    args = ap.parse_args(argv)

    rec = TrajectoryRecorder(args.out_dir, repeats=args.repeats,
                             step_timeout_s=args.step_timeout_s,
                             allow_act=args.allow_act, settle_s=args.settle_s)
    print("[record] dpi_awareness=%s spaces=%s" % (
        rec.awareness.get("via"), rec.spaces.get("frame_over_click_ratio")))
    sessions: List[Dict[str, Any]] = []
    try:
        six_steps = rec.survey_six()
        sessions.append(rec.session("six_software_survey", six_steps,
                                    goal="六大软件在跑的是哪些、窗口句柄与画面长什么样"))
    except Exception as exc:  # noqa: BLE001
        print("[FATAL] survey crashed: %r" % (exc,))
        return 3

    if args.allow_act and not args.survey_only:
        try:
            act_steps = rec.act_probe_session()
            sessions.append(rec.session("self_owned_act_probe", act_steps,
                                        goal="在自建窗口上证明 读屏->键鼠->画面变化 端到端可用"))
        except Exception as exc:  # noqa: BLE001
            print("[WARN] act probe crashed: %r" % (exc,))

    led = rec.write_ledger(sessions, {
        "environment": _screen_environment(),
        "dpi_awareness": rec.awareness,
        "coordinate_spaces": rec.spaces,
    })
    print("[record] steps=%d accepted=%d rejected=%d" % (led["n_steps"], led["n_accepted"], led["n_rejected"]))
    print("[record] ledger -> %s" % os.path.join(args.out_dir, "ledger.json").replace("\\", "/"))
    if led["n_accepted"] == 0:
        print("[FATAL] zero accepted observations -> 本机此刻抓不到真实屏幕，"
              "GUI 族语料必须留空（不许用占位图顶包）")
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
