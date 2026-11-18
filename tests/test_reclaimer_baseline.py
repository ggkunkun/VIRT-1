# -*- coding: utf-8 -*-
"""ProcessMemoryReclaimer 基线/接管语义验证（可证伪）。

修复的真实 bug：流水线运行期间**新拉起**的 CAD 软件从未登记进 ``_session_pids``，
``close_software`` 于是认为"该软件没在跑"，返回 NOT_RUNNING 并把孤儿留在机器上。

修复后语义（本测试逐条证伪）：

A. ``snapshot_baseline()`` 记录的开工前进程 = 基线，永不接管。
B. ``adopt_new_processes()`` 只接管基线之外的新进程，基线 PID 不进 ``_session_pids``。
C. ``close_software()`` 对"新出现"的进程会真正 kill 并报 RECLAIMED。
D. ``close_software()`` 对"基线内"的用户进程返回 NOT_RUNNING 且**绝不 kill**。
E. ``orphan_processes()`` 只报新进程，不把用户实例算成孤儿。
F. 端到端：``IndustrialAgentTeam.solve()`` 取基线并输出 ``orphan_total == 0``。

运行： python tests/test_reclaimer_baseline.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from virtu_omni.agent.process_memory_reclaimer import ProcessMemoryReclaimer  # noqa: E402


class FakeProc:
    """最小 psutil.Process 替身：只实现回收器用到的成员。"""

    def __init__(self, pid: int, alive: bool = True):
        self.pid = pid
        self._alive = alive
        self.killed = False

    def is_running(self) -> bool:
        return self._alive

    def kill(self) -> None:
        self.killed = True
        self._alive = False

    def memory_info(self):
        return type("MI", (), {"rss": 64 * 1024 * 1024})()


class Harness(ProcessMemoryReclaimer):
    """用可控的假进程表替代真实 psutil 枚举。"""

    def __init__(self, procs):
        super().__init__()
        self._procs = procs  # software_key -> list[FakeProc]
        self._baseline_calls = 0

    def find_target_processes(self, software_key):
        return list(self._procs.get(software_key.lower(), []))

    def get_system_memory(self):
        return {"total_mb": 16000.0, "available_mb": 8000.0, "percent": 50.0}

    def trim_system_working_set(self):
        return None

    def unload_ollama_model(self):
        return None


def main() -> int:
    checks = []

    # 开工前：用户自己开着一个 SolidWorks（pid 1000）
    user_sld = FakeProc(1000)
    harness = Harness({"solidworks": [user_sld]})
    harness.snapshot_baseline(["solidworks"])
    checks.append(("A 基线包含用户实例", harness._baseline_pids == {1000}))

    # 运行期间新拉起一个 SolidWorks（pid 2000）
    new_sld = FakeProc(2000)
    harness._procs["solidworks"].append(new_sld)

    adopted = harness.adopt_new_processes("solidworks")
    print("adopt:", adopted, "| session:", sorted(harness._session_pids),
          "| baseline:", sorted(harness._baseline_pids))
    checks.append(("B 只接管新进程", adopted == [2000]))
    checks.append(("B 基线 PID 未被登记", 1000 not in harness._session_pids))

    orphans = harness.orphan_processes("solidworks")
    print("orphans:", [p.pid for p in orphans])
    checks.append(("E 孤儿只含新进程", [p.pid for p in orphans] == [2000]))

    # 关闭：新进程应被 kill，用户实例保持存活
    rec = harness.close_software("solidworks", grace_period_s=0.01)
    print("close status:", rec.get("status"), "| killed:", rec.get("killed_pids"),
          "| adopted:", rec.get("adopted_pids"))
    checks.append(("C 新进程被回收", rec.get("status") == "RECLAIMED" and new_sld.killed))
    checks.append(("D 用户实例未被杀", user_sld.killed is False and user_sld.is_running()))
    checks.append(("D 基线 PID 不出现在 pids_found", 1000 not in (rec.get("pids_found") or [])))

    # 只有用户实例、没有新进程时：必须 NOT_RUNNING，且绝不 kill
    user_only = FakeProc(3000)
    h2 = Harness({"autocad": [user_only]})
    h2.snapshot_baseline(["autocad"])
    rec2 = h2.close_software("autocad", grace_period_s=0.01)
    checks.append(("D 纯用户实例 -> NOT_RUNNING",
                   rec2.get("status") == "NOT_RUNNING" and user_only.killed is False))

    # 未取基线时保守：只认显式登记，绝不认为孤儿
    h3 = Harness({"nx": [FakeProc(4000)]})
    print("no-baseline orphans:", h3.orphan_processes("nx"))
    checks.append(("E 无基线 -> 不臆造孤儿", h3.orphan_processes("nx") == []))

    # ---- F. 端到端：真实 solve() 必须取基线并报 orphan_total=0 ----
    from virtu_omni.agent.agent_team import IndustrialAgentTeam
    team = IndustrialAgentTeam()
    res = team.solve("设计一个精密成型轮模 材质Cr12MoV",
                     output_dir=str(ROOT / "runs" / "reclaimer_test"), memory_safe=True)
    residual = res.get("residual_processes") or {}
    print("F residual:", {k: residual.get(k) for k in ("basis", "residual_total", "orphan_total")})
    checks.append(("F 取到基线", team.reclaimer._baseline_pids is not None))
    checks.append(("F 孤儿数为 0", residual.get("orphan_total") == 0))

    print("\n=== 回收器基线/接管测试 ===")
    all_pass = True
    for name, ok in checks:
        print(("  PASS  " if ok else "  FAIL  ") + name)
        all_pass = all_pass and bool(ok)
    print("\n" + ("ALL PASS (%d/%d)" % (sum(1 for _, o in checks if o), len(checks))
                  if all_pass else "HAS FAILURES"))
    return 0 if all_pass else 1


import pytest


@pytest.fixture
def isolated_reclaimer(tmp_path, monkeypatch):
    import virtu_omni.agent.agent_team as team_module
    import virtu_omni.agent.process_memory_reclaimer as reclaimer_module
    from virtu_omni.memory import VirtuHindsightMemory

    monkeypatch.setattr(reclaimer_module, "user32", None)
    monkeypatch.setattr(reclaimer_module, "k32", None)
    monkeypatch.setattr(reclaimer_module, "psapi", None)
    monkeypatch.setattr(ProcessMemoryReclaimer, "find_target_processes", lambda self, key: [])
    monkeypatch.setattr(ProcessMemoryReclaimer, "unload_ollama_model", lambda *a, **k: False)
    monkeypatch.setenv("VIRTU_MEMORY_PATH", str(tmp_path / "memory.json"))
    monkeypatch.delenv("HINDSIGHT_API_URL", raising=False)
    monkeypatch.delenv("HINDSIGHT_BASE_URL", raising=False)
    memory = VirtuHindsightMemory(storage_path=str(tmp_path / "hindsight.json"))
    monkeypatch.setattr(team_module, "VirtuHindsightMemory", lambda: memory)


def test_reclaimer_baseline_contracts(tmp_path, monkeypatch, isolated_reclaimer):
    monkeypatch.setattr(sys.modules[__name__], "ROOT", tmp_path)
    assert main() == 0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
