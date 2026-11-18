# -*- coding: utf-8 -*-
"""反证：v5 编排训练前的 Ollama 内存释放门（scripts/run_full_repair_v5.py::free_ollama_ram）。

根因事故（2026-11-16）：基线 verify 加载的模型 keep_alive 常驻主机内存，叠加 8B QLoRA
pinned CPU 权重把 commit 耗尽，训练进程被系统终止（rc=0x40010004，dwm 0xc00001ad）。
本门必须：卸载常驻模型并确认 ps 空才放行；卸载无效/查询失败一律 False（fail-closed），
绝不把训练送进必然耗尽的内存窗口。下列用例植入坏样本验证「必须红」。
"""
import importlib.util
import json
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("rfv5", ROOT / "scripts" / "run_full_repair_v5.py")
rfv5 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rfv5)


@pytest.fixture(autouse=True)
def _isolate_log(tmp_path, monkeypatch):
    """log() 写模块全局 LOG；隔离到 tmp，避免测试把假卸载/FATAL 行污染真实编排日志。"""
    monkeypatch.setattr(rfv5, "LOG", tmp_path)


class _Resp:
    def __init__(self, payload):
        self._b = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._b


class _Opener:
    """ps_sequence 按调用次序返回；generate 记录卸载请求。

    clear_on_unload=True 模拟有效卸载（generate 后 ps 变空）；
    False 模拟坏样本：卸载无效，ps 永远非空。
    """
    def __init__(self, ps_sequence, clear_on_unload=True, ps_raises=False):
        self.ps_sequence = list(ps_sequence)
        self.clear_on_unload = clear_on_unload
        self.ps_raises = ps_raises
        self.generate_calls = []
        self.ps_idx = 0

    def open(self, req, timeout=None):
        url = getattr(req, "full_url", req)
        if url.endswith("/api/ps"):
            if self.ps_raises:
                raise OSError("connection refused")
            doc = self.ps_sequence[min(self.ps_idx, len(self.ps_sequence) - 1)]
            self.ps_idx += 1
            return _Resp(doc)
        if url.endswith("/api/generate"):
            self.generate_calls.append(json.loads(req.data.decode("utf-8")))
            if self.clear_on_unload:
                self.ps_sequence.append({"models": []})
            return _Resp({"done": True})
        raise AssertionError("unexpected url: " + url)


def test_unload_sends_keep_alive_zero_and_confirms_empty():
    op = _Opener([{"models": [{"name": "virtu-six-software:v4-local-repair"}]}])
    assert rfv5.free_ollama_ram(opener=op) is True
    assert op.generate_calls == [
        {"model": "virtu-six-software:v4-local-repair", "keep_alive": 0}
    ]


def test_empty_ps_passes_without_unload():
    op = _Opener([{"models": []}])
    assert rfv5.free_ollama_ram(opener=op) is True
    assert op.generate_calls == []


def test_ineffective_unload_must_fail_closed(monkeypatch):
    """坏样本：卸载请求发了但 ps 仍非空 ⇒ 必须 False，不得谎报内存已释放。"""
    monkeypatch.setattr(time, "sleep", lambda *a, **k: None)  # 跳过 12×5s 等待
    op = _Opener([{"models": [{"name": "virtu-six-software:v3"}]}], clear_on_unload=False)
    assert rfv5.free_ollama_ram(opener=op) is False
    assert op.generate_calls  # 确实尝试了卸载
    assert op.generate_calls[0]["keep_alive"] == 0


def test_ps_query_failure_must_fail_closed():
    """坏样本：ps 查询失败 ⇒ False（fail-closed），不得抛异常或假装成功。"""
    op = _Opener([{"models": []}], ps_raises=True)
    assert rfv5.free_ollama_ram(opener=op) is False


def test_multiple_loaded_models_all_unloaded():
    op = _Opener([{"models": [{"name": "virtu-six-software:v3"},
                              {"name": "virtu-six-software:v4-local-repair"}]}])
    assert rfv5.free_ollama_ram(opener=op) is True
    assert {c["model"] for c in op.generate_calls} == {
        "virtu-six-software:v3", "virtu-six-software:v4-local-repair"}
    assert all(c["keep_alive"] == 0 for c in op.generate_calls)


# --- verify_capture 取证门反证（§8.4：空集/解析失败/基础设施崩溃必须红）---

def _plant(tmp_path, monkeypatch, rec, run_ok=True):
    monkeypatch.setattr(rfv5, "LOG", tmp_path)
    tag, rnd = "virtu-six-software:v3", 1
    if rec is not None:
        p = tmp_path / f"verify_{tag.replace(':', '_')}_r{rnd}.json"
        p.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(rfv5, "run", lambda *a, **k: run_ok)
    return tag, rnd


def test_verify_good_receipt_passes(tmp_path, monkeypatch):
    rec = {"error": None, "detail": {"lame_stress_probe": {"passed": True}}, "passed": 1, "total": 1}
    tag, rnd = _plant(tmp_path, monkeypatch, rec)
    assert rfv5.verify_capture(tag, rnd) is True


def test_verify_genuine_probe_failure_is_baseline_not_fatal(tmp_path, monkeypatch):
    """真实模型缺陷（detail 非空、部分 passed=False）必须放行作基线，不得 fail-closed。"""
    rec = {"error": None, "detail": {"lame_stress_probe": {"passed": False, "reason": "missing_sigma_theta_33.33"}},
           "passed": 0, "total": 1}
    tag, rnd = _plant(tmp_path, monkeypatch, rec)
    assert rfv5.verify_capture(tag, rnd) is True


def test_verify_error_receipt_must_fail_closed(tmp_path, monkeypatch):
    """坏样本：标签 404 / 测量崩溃 ⇒ error 非空、detail 空 ⇒ 必须 False。"""
    rec = {"error": "HTTPError:404", "detail": {}, "passed": 0, "total": 0}
    tag, rnd = _plant(tmp_path, monkeypatch, rec)
    assert rfv5.verify_capture(tag, rnd) is False


def test_verify_empty_probes_must_fail_closed(tmp_path, monkeypatch):
    """坏样本：无 error 但探针空集 ⇒ 必须 False（空匹配集判红）。"""
    rec = {"error": None, "detail": {}, "passed": 0, "total": 0}
    tag, rnd = _plant(tmp_path, monkeypatch, rec)
    assert rfv5.verify_capture(tag, rnd) is False


def test_verify_missing_receipt_must_fail_closed(tmp_path, monkeypatch):
    """坏样本：子进程报成功但凭证缺失/不可解析 ⇒ 必须 False。"""
    tag, rnd = _plant(tmp_path, monkeypatch, None)
    assert rfv5.verify_capture(tag, rnd) is False


def test_verify_subprocess_crash_must_fail_closed(tmp_path, monkeypatch):
    """坏样本：子进程非零退出（导入崩溃等）⇒ 必须 False。"""
    rec = {"error": None, "detail": {"x": {"passed": True}}}
    tag, rnd = _plant(tmp_path, monkeypatch, rec, run_ok=False)
    assert rfv5.verify_capture(tag, rnd) is False