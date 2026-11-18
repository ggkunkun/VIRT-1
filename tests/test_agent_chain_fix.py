# -*- coding: utf-8 -*-
"""agent_chain_executor 致命缺陷修复反证测试（坏样本 ⇒ 必须红）。

覆盖四处真实缺陷：

A. open_vericut_gui 的 bat 路径曾被写成垂直制表符（\\x0b）损坏：
   `E:\\windows64\\commands<VT>ericut_console.bat`，指向不存在的文件 → GUI 通道起不来。
   反证：Popen 收到的 bat 必须是正确的 vericut_console.bat，且不含任何 VT 字节。
B. _find_play_button 把 PIL 的 size=(width,height) 解构成 `H, W`（对调），
   扫描几何全错：1920x1080 屏上 x 范围被截到 0..1080、y_lo 用 1920 算 → 右下角播放键必然 miss。
   反证：在合成 1920x1080 截图右下角放模板，必须命中真实物理坐标；对调时返回 None。
C. _vericut_click_play(real=True) 曾用 pyautogui.click 直写键鼠总线，绕过 input_guard
   （违反 AGENTS.md §4.5「input_guard 是键鼠总线唯一入口」）。修复后走 win_input.click。
   反证：win_input.click 必须被调用，pyautogui.click 必须 0 次调用。
D. taskkill /PID /T /F 曾用 capture_output=True 且无 timeout（§8.1⑦ 管道死锁源）。
   反证：close_launched 派发的 taskkill 必须 stdout=DEVNULL + timeout，绝不能 capture_output。

运行： .venv/Scripts/python.exe -m pytest tests/test_agent_chain_fix.py -q
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

import agent_chain_executor as ace  # noqa: E402

VT = chr(11)
CORRECT_BAT = r"E:\windows64\commands\vericut_console.bat"


# ---------------------------------------------------------------------------
# A：VERICUT GUI bat 路径不得损坏
# ---------------------------------------------------------------------------
def test_open_vericut_gui_bat_path_is_not_corrupted(tmp_path, monkeypatch):
    captured = {}

    class _FakePopen:
        def __init__(self, cmd, **kw):
            captured["cmd"] = cmd
            self.pid = 4242

    monkeypatch.setattr(ace, "_vericut_training_stub", lambda p: ("stub_dir", p))
    monkeypatch.setattr(ace.subprocess, "Popen", _FakePopen)
    proj = str(tmp_path / "p.vcproject")
    Path(proj).write_text("dummy", encoding="utf-8")
    ace.open_vericut_gui(proj, out_dir=str(tmp_path))
    bat = captured["cmd"][0]
    assert VT not in bat, "bat 路径仍含垂直制表符损坏字节"
    assert bat == CORRECT_BAT, f"bat 路径错误: {bat!r}"


# ---------------------------------------------------------------------------
# B：_find_play_button 宽高不得对调
# ---------------------------------------------------------------------------
def test_find_play_button_uses_width_height_not_swapped(tmp_path, monkeypatch):
    np = pytest.importorskip("numpy")
    from PIL import Image
    import pyautogui

    W, H = 1920, 1080
    tw, th = 200, 100
    # 模板：纯色亮块，与黑底反差极大，匹配无歧义
    tpl_arr = np.zeros((th, tw, 3), dtype=np.uint8)
    tpl_arr[:, :] = (255, 0, 255)
    tpl_dir = tmp_path / "work" / "vericut-toolchain"
    tpl_dir.mkdir(parents=True)
    Image.fromarray(tpl_arr).save(tpl_dir / "vc_playbtn.png")

    # 合成截图：黑底，右下角 (1600,900) 贴上模板（落在 y>=0.78H 的扫描带内）
    shot_arr = np.zeros((H, W, 3), dtype=np.uint8)
    px, py = 1600, 900
    shot_arr[py:py + th, px:px + tw] = (255, 0, 255)
    shot_img = Image.fromarray(shot_arr)

    monkeypatch.setattr(ace, "ROOT", str(tmp_path))
    monkeypatch.setattr(pyautogui, "screenshot", lambda *a, **k: shot_img)

    res = ace._find_play_button(hwnd=None, scan_all=True, scale=4, threshold=0.80)
    assert res is not None, "宽高对调致右下角播放键 miss（旧 H,W 解构 bug）"
    score, (cx, cy) = res
    assert score >= 0.90
    # 命中点必须落在真实物理坐标附近（模板中心 = 1600+100, 900+50）
    assert abs(cx - (px + tw // 2)) <= 8, f"cx={cx} 偏离真实中心 {px + tw // 2}"
    assert abs(cy - (py + th // 2)) <= 8, f"cy={cy} 偏离真实中心 {py + th // 2}"


# ---------------------------------------------------------------------------
# C：真实点击必须经 input_guard（win_input.click），不得用 pyautogui 直写总线
# ---------------------------------------------------------------------------
def test_real_click_routes_through_input_guard_not_pyautogui(monkeypatch):
    import win_input
    import pyautogui

    wi_calls = []
    pg_calls = []
    monkeypatch.setattr(win_input, "click", lambda x, y, **k: wi_calls.append((x, y)) or True)
    monkeypatch.setattr(pyautogui, "click", lambda *a, **k: pg_calls.append(a))

    note = ace._vericut_click_play(123, (100, 200), real=True)
    assert wi_calls == [(100, 200)], "真实点击未经 win_input/input_guard"
    assert pg_calls == [], "pyautogui.click 仍被调用，绕过键鼠闸门（§4.5）"
    assert "input_guard" in note


def test_real_click_denied_is_reported_honestly(monkeypatch):
    import win_input
    monkeypatch.setattr(win_input, "click", lambda x, y, **k: False)  # 闸门拒绝/演练
    note = ace._vericut_click_play(123, (100, 200), real=True)
    assert "未发出" in note or "拒绝" in note, "被拒点击不得谎称已发出"


# ---------------------------------------------------------------------------
# D：taskkill 必须 DEVNULL + timeout，不得 capture_output（§8.1⑦）
# ---------------------------------------------------------------------------
def test_close_launched_taskkill_uses_devnull_not_capture_output(monkeypatch):
    monkeypatch.setattr(ace, "_launch_ledger_read",
                        lambda: [{"pid": 111, "exe": "acad.exe", "path": "D:/x/acad.exe"}])
    monkeypatch.setattr(ace, "_proc_table",
                        lambda: [{"name": "acad.exe", "pid": "111", "path": "D:/x/acad.exe"}])
    monkeypatch.setattr(ace, "_launch_ledger_append", lambda rec: True)
    seen = {}

    def spy(cmd, **kw):
        seen["cmd"] = cmd
        seen["kw"] = kw
        return type("R", (), {"returncode": 0})()

    monkeypatch.setattr(ace.subprocess, "run", spy)
    closed = ace.close_launched()
    assert closed == [111]
    assert seen["cmd"][0] == "taskkill"
    kw = seen["kw"]
    assert kw.get("capture_output") is not True, "taskkill 仍用 capture_output（管道死锁源）"
    assert kw.get("stdout") == subprocess.DEVNULL
    assert kw.get("stderr") == subprocess.DEVNULL
    assert kw.get("timeout"), "taskkill 必须带 timeout"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))