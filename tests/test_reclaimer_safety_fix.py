# -*- coding: utf-8 -*-
"""ProcessMemoryReclaimer 安全修复反证测试（坏样本 ⇒ 必须红）。

覆盖两处真实缺陷的修复，每条都植入坏样本证明旧行为会被拦下：

D2  close_software 此前无条件返回 status="RECLAIMED"，即使强杀后进程仍存活。
    这违反 AGENTS.md §5「证据先于断言」：没确认死亡就宣称已回收。
    修复后：仍存活的进程计入 residual_pids，status="FAILED"。
    反证：StubbornProc（kill 不生效）必须判 FAILED，绝不能是 RECLAIMED。
    同时保住既有契约：kill 真正生效时仍报 RECLAIMED（test_reclaimer_baseline C 组）。

D3  _append_log 此前 read-modify-write 非原子，且既有 JSON 损坏时静默 cur=[]，
    把全部历史取证记录丢弃（§8 证据不可毁灭）。
    修复后：原子写（temp+os.replace），损坏文件另存 .corrupt-<ts>.bak 留证。
    反证：写入损坏日志后，原始字节必须仍在某个 .bak 中，新记录必须落盘。

边界（不在本测试改动范围）：unload_ollama_model(None) 的「卸载全部驻留模型 /
枚举失败回退 virtu-ties-v1:latest」是被 test_agent_8b_serving_defaults 冻结的
预期行为（stop 是可逆卸载，非删除；删除保护在 cleanup_obsolete_models 的
chain_is_measuring + evaluation_referenced_tags），本修复不动它。

运行： .venv/Scripts/python.exe -m pytest tests/test_reclaimer_safety_fix.py -q
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from virtu_omni.agent.process_memory_reclaimer import ProcessMemoryReclaimer  # noqa: E402
import virtu_omni.agent.process_memory_reclaimer as reclaimer_module  # noqa: E402


class DyingProc:
    """kill 真正生效的进程替身（与 test_reclaimer_baseline.FakeProc 同语义）。"""

    def __init__(self, pid: int):
        self.pid = pid
        self._alive = True
        self.killed = False

    def is_running(self) -> bool:
        return self._alive

    def kill(self) -> None:
        self.killed = True
        self._alive = False

    def memory_info(self):
        return type("MI", (), {"rss": 64 * 1024 * 1024})()


class StubbornProc:
    """坏样本：受保护/拒绝退出的进程，kill 不生效，始终存活。"""

    def __init__(self, pid: int):
        self.pid = pid
        self.killed = False

    def is_running(self) -> bool:
        return True

    def kill(self) -> None:
        self.killed = True  # 发出了终止请求，但进程拒绝退出

    def wait(self, timeout=None):
        return None  # 等待后仍存活

    def memory_info(self):
        return type("MI", (), {"rss": 64 * 1024 * 1024})()


class Harness(ProcessMemoryReclaimer):
    def __init__(self, procs):
        super().__init__()
        self._procs = procs

    def find_target_processes(self, software_key):
        return list(self._procs.get(software_key.lower(), []))

    def get_system_memory(self):
        return {"total_mb": 16000.0, "available_mb": 8000.0, "percent": 50.0}

    def trim_system_working_set(self):
        return None

    def unload_ollama_model(self, *a, **k):
        return True


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    # 不触碰真实 Win32 窗口枚举 / 工作集净化，保证 hermetic。
    monkeypatch.setattr(reclaimer_module, "user32", None)
    monkeypatch.setattr(reclaimer_module, "k32", None)
    monkeypatch.setattr(reclaimer_module, "psapi", None)


def _harness_with(proc, key="solidworks"):
    h = Harness({key: [proc]})
    h._baseline_pids = set()
    h.register_session_pid(proc.pid)
    return h


def test_stubborn_process_must_not_be_reclaimed():
    """D2 反证：强杀后仍存活 ⇒ status=FAILED + residual_pids，绝不能 RECLAIMED。"""
    stubborn = StubbornProc(987654)
    h = _harness_with(stubborn)
    rec = h.close_software("solidworks", grace_period_s=0.01)
    assert rec["status"] == "FAILED", f"存活进程被谎报回收: {rec['status']}"
    assert stubborn.pid in rec["residual_pids"]
    assert rec["status"] != "RECLAIMED"


def test_dying_process_still_reclaimed():
    """保住既有契约：kill 真正生效 ⇒ RECLAIMED，residual_pids 为空。"""
    dying = DyingProc(987655)
    h = _harness_with(dying)
    rec = h.close_software("solidworks", grace_period_s=0.01)
    assert rec["status"] == "RECLAIMED"
    assert rec["residual_pids"] == []
    assert dying.killed is True


def test_mixed_residual_only_flags_survivor():
    """一死一活：只把存活者计入 residual，整体判 FAILED（不掩盖残留）。"""
    dying = DyingProc(111)
    stubborn = StubbornProc(222)
    h = Harness({"nx": [dying, stubborn]})
    h._baseline_pids = set()
    h.register_session_pids([111, 222])
    rec = h.close_software("nx", grace_period_s=0.01)
    assert rec["status"] == "FAILED"
    assert rec["residual_pids"] == [222]
    assert dying.killed and stubborn.killed


def test_append_log_atomic_and_valid(tmp_path):
    """D3：写入后日志必须是合法 JSON 数组且含新记录（原子写，无半截）。"""
    log = tmp_path / "forensic.json"
    r = ProcessMemoryReclaimer(log_path=str(log))
    r._append_log({"event": "A", "n": 1})
    r._append_log({"event": "B", "n": 2})
    data = json.loads(log.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert [d["event"] for d in data] == ["A", "B"]
    assert not list(tmp_path.glob("*.tmp")), "临时文件未清理"


def test_append_log_corrupt_preserved_not_discarded(tmp_path):
    """D3 反证：既有日志损坏 ⇒ 原始字节留证于 .bak，绝不静默清空丢弃。"""
    log = tmp_path / "forensic.json"
    corrupt_bytes = b'{"event": "OLD", "broken": '  # 半截 JSON（崩溃残留）
    log.write_bytes(corrupt_bytes)
    r = ProcessMemoryReclaimer(log_path=str(log))
    r._append_log({"event": "NEW"})
    # 新记录落盘
    data = json.loads(log.read_text(encoding="utf-8"))
    assert isinstance(data, list) and data[-1]["event"] == "NEW"
    # 原始损坏字节被保留为证据（旧实现会直接 cur=[] 丢弃）
    baks = list(tmp_path.glob("forensic.json.corrupt-*.bak"))
    assert baks, "损坏的取证日志被静默丢弃，未留证"
    assert baks[0].read_bytes() == corrupt_bytes


def test_append_log_non_array_root_backed_up(tmp_path):
    """D3：根不是数组（如对象）也视为损坏，留证后起新数组。"""
    log = tmp_path / "forensic.json"
    log.write_text('{"not": "an array"}', encoding="utf-8")
    r = ProcessMemoryReclaimer(log_path=str(log))
    r._append_log({"event": "NEW"})
    data = json.loads(log.read_text(encoding="utf-8"))
    assert isinstance(data, list) and data[-1]["event"] == "NEW"
    assert list(tmp_path.glob("forensic.json.corrupt-*.bak"))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))