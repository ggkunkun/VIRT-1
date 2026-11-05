# -*- coding: utf-8 -*-
"""桌面输入闸门判据。

两条铁律：
1. 拦截必须"零输入上总线"——用 win32api 的 spy 计数证明，不是只看返回值。
2. 判定必须 fail-closed——环境变量缺省、非法值、读不到进程表，一律当拒绝。
"""
import json
import os
import io
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import win32api  # noqa: E402

from bridges import desktop_gate  # noqa: E402
from bridges.tool_calling_specs import execute_tool_call  # noqa: E402

MUTATING = ["click", "focus", "type_text", "hotkey", "dismiss_dialogs"]


class Spy:
    """把三个真实输入入口换成计数器；谁被调用就记谁。"""

    def __init__(self):
        self.calls = []

    def install(self, tc):
        for name in ("mouse_event", "keybd_event", "SetCursorPos", "SendInput"):
            orig = getattr(win32api, name, None)

            def make(n, o):
                def _spy(*a, **k):
                    self.calls.append(n)
                    raise AssertionError("input syscall %s reached the bus" % n)
                return _spy
            if orig is not None:
                tc.addCleanup(setattr, win32api, name, orig)
                setattr(win32api, name, make(name, orig))
        # ctypes 通道也一并封住
        tc.addCleanup(setattr, desktop_gate, "_u", desktop_gate._u)

    def assert_clean(self):
        if self.calls:
            raise AssertionError("blocked call must not touch input APIs: %r" % (self.calls,))


class GateDecisionTests(unittest.TestCase):
    GATED_VARS = (desktop_gate.OPT_IN_ENV, desktop_gate.KILL_ENV, desktop_gate.RATE_ENV,
                  desktop_gate.APPROVAL_ENV, desktop_gate.APPROVAL_TTL_ENV,
                  desktop_gate.AUDIT_ENV)

    def setUp(self):
        self.spy = Spy()
        self.spy.install(self)
        # 一次性快照 + 还原；不要用"每个变量注册一个自我再注册的 cleanup"，
        # 那会让清理队列边排空边增长而永不收尾。
        backup = dict(os.environ)
        self.addCleanup(os.environ.update, backup)
        for var in self.GATED_VARS:
            os.environ.pop(var, None)

    def test_01_default_deny_every_mutating_action(self):
        for act in MUTATING:
            self.spy.calls = []
            v = desktop_gate.evaluate("cadcam_desktop_gui",
                                      {"action": act, "software": "solidworks",
                                       "x": 100, "y": 100, "text": "hi", "keys": "ctrl,s"})
            self.assertIsNotNone(v, "%s must be blocked without opt-in" % act)
            self.assertEqual(v["verdict_code"], "DESKTOP_INPUT_NOT_APPROVED")
            self.assertFalse(v["input_sent"])
            self.spy.assert_clean()

    def test_02_kill_switch_beats_opt_in(self):
        os.environ[desktop_gate.OPT_IN_ENV] = "1"
        os.environ[desktop_gate.KILL_ENV] = "1"
        v = desktop_gate.evaluate("cadcam_desktop_gui", {"action": "capture"})
        self.assertIsNone(v, "capture is read-only and stays allowed")
        v = desktop_gate.evaluate("cadcam_desktop_gui",
                                  {"action": "hotkey", "keys": "ctrl,s", "software": "solidworks"})
        self.assertEqual(v["verdict_code"], "DESKTOP_KILLED")
        self.spy.assert_clean()

    def test_03_read_only_actions_pass(self):
        for act in ("capture", "inspect_window"):
            self.assertIsNone(desktop_gate.evaluate("cadcam_desktop_gui", {"action": act}))

    def test_04_unknown_action_rejected_when_enabled(self):
        os.environ[desktop_gate.OPT_IN_ENV] = "1"
        v = desktop_gate.evaluate("cadcam_desktop_gui", {"action": "rm_rf"})
        self.assertEqual(v["verdict_code"], "DESKTOP_ACTION_UNKNOWN")

    def test_05_click_needs_explicit_coords_not_silent_default(self):
        os.environ[desktop_gate.OPT_IN_ENV] = "1"
        v = desktop_gate.evaluate("cadcam_desktop_gui", {"action": "click", "software": "solidworks"})
        self.assertEqual(v["verdict_code"], "DESKTOP_CLICK_NEEDS_EXPLICIT_COORDS")
        v = desktop_gate.evaluate("cadcam_desktop_gui",
                                  {"action": "click", "software": "solidworks", "x": 10 ** 9, "y": 7})
        self.assertEqual(v["verdict_code"], "DESKTOP_CLICK_OUT_OF_BOUNDS")
        self.spy.assert_clean()

    def _allow_target(self, software="solidworks", foreground=4321, pids=(4321,)):
        os.environ[desktop_gate.OPT_IN_ENV] = "1"
        self._patch(desktop_gate, "authorized_targets",
                    lambda sw: ({software: list(pids)}, []))
        self._patch(desktop_gate, "foreground_pid", lambda: foreground)

    def _patch(self, obj, name, value):
        orig = getattr(obj, name)
        self.addCleanup(setattr, obj, name, orig)
        setattr(obj, name, value)

    def test_06_foreign_focus_refuses(self):
        self._allow_target(foreground=9999, pids=(4321,))
        v = desktop_gate.evaluate("cadcam_desktop_gui",
                                  {"action": "type_text", "software": "solidworks", "text": "M10"})
        self.assertEqual(v["verdict_code"], "DESKTOP_FOREIGN_FOCUS")
        self.spy.assert_clean()

    def test_07_named_target_required(self):
        os.environ[desktop_gate.OPT_IN_ENV] = "1"
        v = desktop_gate.evaluate("cadcam_desktop_gui", {"action": "type_text", "text": "M10"})
        self.assertEqual(v["verdict_code"], "DESKTOP_TARGET_NOT_NAMED")

    def test_08_generic_java_host_cannot_authorize_vericut(self):
        os.environ[desktop_gate.OPT_IN_ENV] = "1"
        self._patch(desktop_gate, "running_pids",
                    lambda: {"javaw.exe": [111, 222], "VERICUT.exe": [333]})
        by_exe, dropped = desktop_gate.authorized_targets("vericut")
        self.assertIn("javaw.exe", dropped)
        self.assertNotIn("javaw.exe", by_exe)
        v = desktop_gate.evaluate("cadcam_desktop_gui",
                                  {"action": "hotkey", "software": "vericut", "keys": "ctrl,s"})
        self.assertIn(v["verdict_code"], ("DESKTOP_TARGET_NOT_RUNNING", "DESKTOP_FOREIGN_FOCUS"))

    def test_09_dangerous_hotkey_refused_even_for_bound_target(self):
        for keys in ("alt,f4", "win,l", "ctrl+alt+del", "ctrl,shift,esc"):
            self._allow_target()
            v = desktop_gate.evaluate("cadcam_desktop_gui",
                                      {"action": "hotkey", "software": "solidworks", "keys": keys})
            self.assertEqual(v["verdict_code"], "DESKTOP_HOTKEY_FORBIDDEN", keys)
            self.spy.assert_clean()

    def test_10_bound_target_hotkey_allowed(self):
        self._allow_target()
        self.assertIsNone(desktop_gate.evaluate(
            "cadcam_desktop_gui", {"action": "hotkey", "software": "solidworks", "keys": "ctrl,s"}))

    def test_11_rate_cap_blocks_after_quota(self):
        self._allow_target()
        os.environ[desktop_gate.RATE_ENV] = "2"
        desktop_gate._stamp_cache[:] = []
        args = {"action": "hotkey", "software": "solidworks", "keys": "ctrl,s"}
        self.assertIsNone(desktop_gate.evaluate("cadcam_desktop_gui", args))
        self.assertIsNone(desktop_gate.evaluate("cadcam_desktop_gui", args))
        v = desktop_gate.evaluate("cadcam_desktop_gui", args)
        self.assertEqual(v["verdict_code"], "DESKTOP_RATE_CAPPED")

    def test_12_stale_approval_file_blocks(self):
        self._allow_target()
        import tempfile
        d = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, d, True)
        f = os.path.join(d, "approve.flag")
        io.open(f, "w").close()
        os.utime(f, (0, 0))
        os.environ[desktop_gate.APPROVAL_ENV] = f
        v = desktop_gate.evaluate("cadcam_desktop_gui",
                                  {"action": "hotkey", "software": "solidworks", "keys": "ctrl,s"})
        self.assertEqual(v["verdict_code"], "DESKTOP_APPROVAL_STALE_OR_MISSING")

    def test_13_funnel_enforces_gate_for_every_channel(self):
        """execute_tool_call 是 REST/MCP/CLI/SDK/路由共用的漏斗：闸门必须长在它身上。"""
        for act in ("hotkey", "type_text", "click", "focus", "dismiss_dialogs"):
            res = execute_tool_call("cadcam_desktop_gui",
                                    {"action": act, "software": "solidworks",
                                     "x": 100, "y": 100, "text": "hi", "keys": "ctrl,s"})
            self.assertEqual(res.get("status"), "blocked", act)
            self.assertEqual(res.get("verdict_code"), "DESKTOP_INPUT_NOT_APPROVED", act)
        self.spy.assert_clean()

    def test_14_audit_never_stores_typed_plaintext(self):
        p = os.path.join(os.environ.get("TEMP", "."), "virtu_gate_audit_test.jsonl")
        if os.path.exists(p):
            os.remove(p)
        secret = "P@ssw0rd-in-the-editor"
        desktop_gate.audit("cadcam_desktop_gui", {"action": "type_text", "text": secret},
                           None, log_path=p)
        with open(p, encoding="utf-8") as fh:
            body = fh.read()
        self.assertNotIn(secret, body)
        rec = json.loads(body.strip().splitlines()[-1])
        self.assertEqual(rec["text_len"], len(secret))
        self.assertEqual(len(rec["text_sha8"]), 8)
        os.remove(p)


if __name__ == "__main__":
    unittest.main(verbosity=2)
