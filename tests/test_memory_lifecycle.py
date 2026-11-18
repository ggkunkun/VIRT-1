"""P2 记忆生命周期与工程化回归测试（不依赖网络 / Ollama / GPU / 服务）。

覆盖：
- retain 内容指纹去重（重复内容不新增 unit、返回已有 id）
- recall 跳过过期 unit，且命中写回 access_count / last_recalled_at
- prune / compact 按 utility+recency 淘汰并返回淘汰数量
- 旧格式 JSON 向后兼容（缺字段给默认值，历史数据可读回）
- tool_calling_specs.py 的坏调用不再抛 AttributeError（静态 AST 检查，避免重依赖）
- synthesize_skill 产物写入 skills_catalog（去重 / skill_id / sha256）

所有持久化均落在 ``tmp_path``，绝不读写仓库的 ``data/**`` 数据文件。
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from virtu_omni.memory.hindsight_adapter import VirtuHindsightMemory

ROOT = Path(__file__).resolve().parent.parent


def _mem(tmp_path: Path, name: str = "banks.json") -> VirtuHindsightMemory:
    """构造独立实例；关闭 embedder 以走纯 lexical 命中，避免依赖 numpy/向量库。"""
    m = VirtuHindsightMemory(storage_path=tmp_path / name)
    m.embedder = None
    return m


# ---------------------------------------------------------------------------
# 1. 内容指纹去重
# ---------------------------------------------------------------------------
def test_retain_dedup_does_not_grow_units(tmp_path):
    m = _mem(tmp_path)
    r1 = m.retain("bank", "identical content block")
    r2 = m.retain("bank", "identical content block")
    r3 = m.retain("bank", "  identical content block  ")  # strip 归一化后仍为重复

    units = m.banks["bank"]["units"]
    assert len(units) == 1, "重复 retain 不应让 units 增长"
    assert r2["status"] == "duplicate"
    assert r2["id"] == r1["id"], "重复内容应返回已有 id"
    assert r3["id"] == r1["id"]
    assert len(units[r1["id"]]["content_sha256"]) == 64


# ---------------------------------------------------------------------------
# 2. 过期 unit 不被 recall 返回
# ---------------------------------------------------------------------------
def test_expired_unit_not_recalled(tmp_path):
    m = _mem(tmp_path)
    m.retain("bank", "alpha_only_expired", ttl_seconds=-10)
    assert m.recall("bank", "alpha_only_expired") == [], "已过期 unit 必须被跳过"

    # 确保 recall 不是整体失灵：未过期的 unit 仍能被命中
    m.retain("bank", "beta_only_fresh")
    res = m.recall("bank", "beta_only_fresh")
    assert [r["content"] for r in res] == ["beta_only_fresh"]


# ---------------------------------------------------------------------------
# 3. recall 命中写回计数（并落盘可重读）
# ---------------------------------------------------------------------------
def test_recall_writes_back_access_count(tmp_path):
    m = _mem(tmp_path)
    m.retain("bank", "recall_hit_target_gamma")
    res = m.recall("bank", "recall_hit_target_gamma")
    assert len(res) == 1

    uid = res[0]["id"]
    unit = m.banks["bank"]["units"][uid]
    assert unit["access_count"] == 1
    assert unit["last_recalled_at"] is not None
    assert unit["utility_score"] > 1.0

    # 写回已持久化：重新加载同一存储仍可见
    reloaded = VirtuHindsightMemory(storage_path=m.storage_path)
    reloaded.embedder = None
    assert reloaded.banks["bank"]["units"][uid]["access_count"] == 1

    # 再次命中继续累加
    m.recall("bank", "recall_hit_target_gamma")
    assert m.banks["bank"]["units"][uid]["access_count"] == 2


# ---------------------------------------------------------------------------
# 4. 超过容量触发 prune，且返回淘汰数量
# ---------------------------------------------------------------------------
def test_prune_over_capacity_returns_removed_count(tmp_path):
    m = _mem(tmp_path, "prune.json")
    n = 8
    for i in range(n):
        m.retain("bank", f"distinct row {i} gamma")

    before = sum(len(b["units"]) for b in m.banks.values())
    assert before == n  # 四个默认 bank 为空，只有自定义 bank 的 n 条

    max_units = 3
    removed = m.prune(max_units=max_units)
    after = sum(len(b["units"]) for b in m.banks.values())

    assert removed == n - max_units, "prune 必须返回实际淘汰数量"
    assert removed > 0
    assert after == max_units


def test_prune_bank_scoped(tmp_path):
    m = _mem(tmp_path, "prune_scoped.json")
    for i in range(5):
        m.retain("bank", f"row {i} scoped")
    removed = m.prune(max_units=2, bank_id="bank")
    assert removed == 3
    assert len(m.banks["bank"]["units"]) == 2


# ---------------------------------------------------------------------------
# 5. compact 清理过期与重复内容
# ---------------------------------------------------------------------------
def test_compact_removes_expired_and_duplicates(tmp_path):
    m = _mem(tmp_path, "compact.json")
    m.retain("bank", "dup_alpha")
    m.retain("bank", "dup_alpha")  # 入库存重
    m.retain("bank", "to_expire", ttl_seconds=-10)
    assert len(m.banks["bank"]["units"]) == 2

    removed = m.compact(bank_id="bank")
    assert removed >= 1
    assert all(u["content"] != "to_expire" for u in m.banks["bank"]["units"].values())


# ---------------------------------------------------------------------------
# 6. 旧格式 JSON 能读回（缺字段给默认值，不被误判为过期）
# ---------------------------------------------------------------------------
def test_legacy_json_backward_compatible(tmp_path):
    legacy = {
        "version": "2.0-Hindsight",
        "updated_at": 1,
        "banks": {
            "legacy": {
                "bank_id": "legacy",
                "description": "old format bank",
                "created_at": 1,
                "units": {
                    "MEM_LEGA_0001_0001": {
                        "id": "MEM_LEGA_0001_0001",
                        "bank_id": "legacy",
                        "memory_type": "world_facts",
                        "content": "legacy alpha content",
                        "context": "general",
                        "tags": ["world_facts"],
                        "entities": [],
                        "created_at": 1,
                        "updated_at": 1,
                        "metadata": {},
                        "confidence": 1.0,
                        # 故意不带任何新字段
                    }
                },
                "vectors": {},
            }
        },
    }
    p = tmp_path / "legacy.json"
    p.write_text(json.dumps(legacy, ensure_ascii=False), encoding="utf-8")

    m = VirtuHindsightMemory(storage_path=p)
    m.embedder = None
    u = m.banks["legacy"]["units"]["MEM_LEGA_0001_0001"]

    assert u["access_count"] == 0
    assert u["last_recalled_at"] is None
    assert u["expires_at"] is None, "历史 unit 不得被误判为过期"
    assert u["utility_score"] == 1.0
    assert len(u["content_sha256"]) == 64

    # 旧数据仍可召回
    assert [r["content"] for r in m.recall("legacy", "legacy alpha content")] == [
        "legacy alpha content"
    ]
    assert m.get_status()["total_units"] >= 1


def test_real_hindsight_json_reads_historical_units(tmp_path):
    """只读方式加载真实历史数据，验证 559 条旧格式 unit 可整体读回。"""
    real = ROOT / "data" / "memory" / "hindsight_banks.json"
    if not real.exists():
        pytest.skip("历史记忆数据文件不存在（干净检出）")

    raw = json.loads(real.read_text(encoding="utf-8"))  # 仅读，绝不回写原文件
    n_units = sum(len(b.get("units", {})) for b in raw["banks"].values())
    assert n_units > 0

    # 写到临时副本再加载，任何 _save_storage 都只作用于副本
    copy = tmp_path / "hindsight_copy.json"
    copy.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    m = VirtuHindsightMemory(storage_path=copy)
    m.embedder = None

    total = sum(len(b.get("units", {})) for b in m.banks.values())
    assert total == n_units, "历史数据条数必须完整读回"
    for bank in m.banks.values():
        for u in bank.get("units", {}).values():
            for key in ("content_sha256", "expires_at", "access_count",
                        "last_recalled_at", "utility_score"):
                assert key in u
            assert u["expires_at"] is None
            assert isinstance(u["access_count"], int)
            assert len(u["content_sha256"]) == 64


# ---------------------------------------------------------------------------
# 7. tool_calling_specs.py 坏调用不再抛 AttributeError（静态 AST）
# ---------------------------------------------------------------------------
def test_tool_calling_specs_no_bad_commit_experience_call():
    src_path = ROOT / "bridges" / "tool_calling_specs.py"
    tree = ast.parse(src_path.read_text(encoding="utf-8"))

    bad = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr in ("commit_experience", "EPISODIC")
    ]
    assert not bad, "commit_experience / MemoryType.EPISODIC 坏引用仍存在"

    branch_calls = set()
    found = False
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "tool_name"
            and any(
                isinstance(c, ast.Constant) and c.value == "memory.commit_long_term_experience"
                for c in node.test.comparators
            )
        ):
            found = True
            # 只收集该分支 body（不含后续 elif 链）里的属性调用
            for stmt in node.body:
                for sub in ast.walk(stmt):
                    if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
                        branch_calls.add(sub.func.attr)

    assert found, "memory.commit_long_term_experience 分支不应被删除"
    assert "commit_experience" not in branch_calls
    assert "retain" in branch_calls, "应改调 hindsight_adapter 真实存在的 retain"


# ---------------------------------------------------------------------------
# 8. synthesize_skill 产物写入 skills_catalog（去重 / skill_id / sha256）
# ---------------------------------------------------------------------------
def test_synthesize_skill_writes_catalog_dedup(tmp_path):
    from virtu_omni.agent.skill_writer_and_memory import SkillWriterAndMemory

    writer = SkillWriterAndMemory(
        memory_path=str(tmp_path / "industrial_knowledge_memory.json"),
        skills_root=str(tmp_path / "skills"),
    )
    p1 = writer.synthesize_skill("depth-check", "检查孔深", "# 步骤\n测深")
    writer.synthesize_skill("depth-check", "检查孔深", "# 步骤\n测深")  # 重复触发

    catalog = writer.memory["skills_catalog"]
    assert Path(p1).exists(), "不得破坏现有 SKILL.md 写入"
    assert len(catalog) == 1, "重复触发不产生重复条目"

    entry = catalog[0]
    assert entry["skill_id"]
    assert len(entry["sha256"]) == 64
    assert entry["files"][0]["sha256"] == entry["sha256"]
    assert entry["name"] == "depth-check"
    # 与 skills/SKILLS_PROVENANCE.json 条目格式对齐的关键字段
    for key in ("name", "tier", "role", "install_path", "files"):
        assert key in entry
