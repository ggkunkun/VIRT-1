"""三条「干净检出还能不能复现分数」的基线约束。

为什么需要这个文件
------------------
2026-11-13 实测：`data/benchmark/` 下 74 个题板 .jsonl 里有 73 个从未入 git
（只有 COVERAGE.json 和图片被跟踪），而 `CASES.lock` 本身也在库外。于是：

  * 全新克隆里 `virtu_eval_phys_v1/physics.jsonl` 不存在 →
    `test_physics_case_set` / `test_eval_in_situ_gate` 走 `pytest.skip`，
    整套测试照样「绿」，但物理维度一分没测。
  * 本机 `core.autocrlf=true`（实测）。就算把题板提交进去，克隆时
    LF→CRLF，`CASES.lock` 里 74 条 sha256 会集体对不上——
    一个「防静默改题」的锁，被自己的检出手续打翻。

所以这里钉三件事：题板必须入库、题板必须按字节存证、锁必须覆盖全部题板。
三者缺一，分数就不是可复现的东西，只是一次本机观测。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "data" / "benchmark"
LOCK = BENCH / "CASES.lock"


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8", check=True).stdout


@pytest.fixture(scope="module")
def have_git():
    try:
        _git("rev-parse", "--is-inside-work-tree")
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git 不可用，无法验证入库状态（这是环境缺失，不是通过）")
    return True


def test_every_benchmark_board_is_tracked(have_git):
    """题板必须在 git 里。否则干净检出的测试会因为文件缺失而静默 skip。"""
    on_disk = {p.relative_to(ROOT).as_posix()
               for p in BENCH.rglob("*.jsonl") if p.is_file()}
    tracked = set(_git("ls-files", "-z", "data/benchmark").split("\0")) - {""}
    missing = sorted(on_disk - tracked)
    assert not missing, (
        "这些题板没入库，干净检出会丢用例并静默 skip：\n  " + "\n  ".join(missing))


def test_benchmark_is_byte_exact_across_checkout(have_git):
    """题板必须标记 -text。否则 autocrlf=true 的机器克隆后哈希全变。"""
    targets = ["data/benchmark/virtu_eval_v1/toolcall.jsonl",
               "data/benchmark/virtu_eval_cl_v1/toolrouting.jsonl",
               "data/benchmark/CASES.lock"]
    out = _git("check-attr", "text", "--", *targets)
    for line in out.strip().splitlines():
        path, _, value = line.rpartition(":")
        assert value.strip() == "unset", (
            f"{path.strip()} 未标记 -text（得到 {value.strip()!r}）；"
            "core.autocrlf=true 下克隆会把 LF 换成 CRLF，CASES.lock 的 sha256 会整体失效")


def test_lock_covers_every_board_and_matches():
    """锁必须覆盖全部题板且逐字节一致。只锁一条等于没锁。"""
    assert LOCK.exists(), "没有 CASES.lock；跑 scripts/check_case_lock.py --write"
    locked = json.loads(LOCK.read_text(encoding="utf-8"))["files"]
    boards = {p.relative_to(ROOT).as_posix() for p in BENCH.rglob("*.jsonl") if p.is_file()}
    unlocked = sorted(boards - set(locked))
    assert not unlocked, f"这些题板不在锁里，改了也没人知道：{unlocked[:10]}"

    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_case_lock.py")],
                          cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0, f"用例锁校验失败：\n{proc.stdout}\n{proc.stderr}"
