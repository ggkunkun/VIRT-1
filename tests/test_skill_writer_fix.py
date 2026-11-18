# -*- coding: utf-8 -*-
"""skill_writer_and_memory 两处缺陷的反证测试（植入坏样本 ⇒ 必须红）。

  1) search_web_knowledge 离线伪造 "Technical Reference" 并谎报 SUCCESS（§5）；
     修复后：无真实检索 ⇒ NO_EVIDENCE + findings=[]，绝不伪造证据。
  2) synthesize_skill 的 skill_name / scripts 键来自工具调用（外部输入），
     旧实现 os.path.join 直接拼接 ⇒ ../ 或绝对路径可逃出 skills_root 写文件。
     修复后：路径穿越必须 ValueError，且不得在根外落盘。

运行： .venv/Scripts/python.exe -m pytest tests/test_skill_writer_fix.py -q
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from virtu_omni.agent.skill_writer_and_memory import SkillWriterAndMemory  # noqa: E402


def _writer(tmp_path) -> SkillWriterAndMemory:
    return SkillWriterAndMemory(
        memory_path=str(tmp_path / "mem.json"),
        skills_root=str(tmp_path / "skills"),
    )


# ---------------------------------------------------------------------------
# 1. 离线检索不得伪造证据
# ---------------------------------------------------------------------------
def test_offline_search_returns_no_evidence_not_fabricated(tmp_path):
    w = _writer(tmp_path)
    w.reach = None                       # 强制走离线降级
    res = w.search_web_knowledge("solidworks macro", channel="github", limit=3)
    assert res["status"] == "NO_EVIDENCE", "离线仍谎报 SUCCESS"
    assert res["findings"] == [], "离线伪造了 findings 条目"
    assert res["backend"] == "offline-fallback"
    # 不得出现伪造的 "Technical Reference" 标题 / github search URL
    assert "Technical Reference" not in str(res)


def test_search_with_no_items_is_no_evidence(tmp_path):
    w = _writer(tmp_path)

    class _Reach:
        def search(self, **kw):
            return {"ok": True, "items": []}      # 真实检索但零结果

    w.reach = _Reach()
    res = w.search_web_knowledge("nonexistent-topic-xyz", channel="github")
    assert res["status"] == "NO_EVIDENCE"
    assert res["findings"] == []


def test_search_with_real_items_is_success(tmp_path):
    """正对照：真实 ok+items ⇒ SUCCESS（证明不是无条件全红）。"""
    w = _writer(tmp_path)

    class _Reach:
        def search(self, **kw):
            return {"ok": True, "backend": "github-api",
                    "items": [{"title": "real/repo", "url": "https://github.com/real/repo"}]}

    w.reach = _Reach()
    res = w.search_web_knowledge("cad", channel="github")
    assert res["status"] == "SUCCESS"
    assert len(res["findings"]) == 1
    assert res["backend"] == "github-api"


# ---------------------------------------------------------------------------
# 2. synthesize_skill 路径穿越必须被拒
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bad_name", ["../escape", "..", "a/b", "a\\b", "..\\..\\x"])
def test_synthesize_rejects_traversal_skill_name(tmp_path, bad_name):
    w = _writer(tmp_path)
    root = tmp_path / "skills"
    with pytest.raises(ValueError):
        w.synthesize_skill(bad_name, "desc", "# body")
    # 根外不得落盘任何 SKILL.md
    assert not (tmp_path / "escape").exists()
    assert not (tmp_path.parent / "escape").exists()


def test_synthesize_rejects_absolute_skill_name(tmp_path):
    w = _writer(tmp_path)
    outside = str(tmp_path / "outside_abs")
    with pytest.raises(ValueError):
        w.synthesize_skill(outside, "desc", "# body")
    assert not Path(outside).exists()


def test_synthesize_rejects_traversal_script_name(tmp_path):
    w = _writer(tmp_path)
    with pytest.raises(ValueError):
        w.synthesize_skill("safe-skill", "desc", "# body",
                           scripts={"../evil.py": "print('pwned')"})
    # evil.py 不得写到 skills_root 之外
    assert not (tmp_path / "evil.py").exists()
    assert not (tmp_path / "skills" / "evil.py").exists()


def test_synthesize_safe_name_and_scripts_still_work(tmp_path):
    """正对照：合法单层名 + 合法脚本名 ⇒ 正常落盘（防止过度拒绝）。"""
    w = _writer(tmp_path)
    p = w.synthesize_skill("depth-check", "检查孔深", "# 步骤\n测深",
                           scripts={"probe.py": "print('ok')"})
    assert Path(p).exists()
    assert (tmp_path / "skills" / "depth-check" / "scripts" / "probe.py").exists()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-o", "addopts=", "-p", "no:cacheprovider"]))