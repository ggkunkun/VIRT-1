# -*- coding: utf-8 -*-
"""可证伪测试：VERICUT 官方培训资产 -> 实测知识 -> Agent 召回。

反证目标（坏样本必须红）：
* 模板套话 / basis=asserted / 假 sha256 / 空内容不得入库；
* 空查询不得靠零向量「召回」出条目冒充命中；
* 本地培训知识不得冒充互联网实时资料；
* 注入必须幂等，且不得改动用户消息。
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

from virtu_omni.internet import augmentation
from virtu_omni.internet import deep_learning_pipeline as dlp
from virtu_omni.knowledge import vericut_training as vt

WORKSPACE = Path(__file__).resolve().parents[1]


def _binary_stl(path: Path) -> None:
    tri = struct.pack(
        "<12fH",
        0, 0, 1,
        0, 0, 0, 5, 0, 0, 0, 8, 0,
        0,
    )
    path.write_bytes(b"\0" * 80 + struct.pack("<I", 1) + tri)


def _ascii_stl(path: Path) -> None:
    path.write_text(
        "solid mini\nfacet normal 0 0 1\nouter loop\n"
        "vertex 0 0 0\nvertex 1 0 0\nvertex 0 2 0\n"
        "endloop\nendfacet\nendsolid mini\n",
        encoding="utf-8",
    )


def _mini_corpus(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "mini.vcproject").write_text(
        '<?xml version="1.0"?>\n<VcProject Version="9.6" Unit="inch">'
        '<File>mini.mcd</File>'
        '<AutoDiff Method="solid" Type="both" Report="on">'
        '<Solid><Gouge Tol="0.004" Hue="0"/><Excess Tol="0.004" Hue="14"/></Solid>'
        '</AutoDiff><Cut Feed="10.0"/></VcProject>',
        encoding="utf-8",
    )
    (root / "mini.tls").write_text(
        '<?xml version="1.0"?><CGTechToolLibrary Version="9.6"><Tools>'
        '<Tool ID="1" Units="Inch"><Description>0.5 MILL</Description><Type>Milling</Type>'
        '<GagePoint><X>0</X><Y>0</Y><Z>7.1</Z></GagePoint></Tool></Tools></CGTechToolLibrary>',
        encoding="utf-8",
    )
    (root / "mini.mcd").write_text(
        "%\n(VERICUT SAMPLE)\n"
        "N010 G90G0X5.Y4.\n"
        "N020 G43Z3.2H1S1400M3\n"
        "N030 G81X3.2Y1.2R1.3Z.9F2.M8\n"
        "N040 G80\n",
        encoding="utf-8",
    )


def _fake_record(content: str, **overrides) -> dict:
    rec = {
        "topic": "VERICUT 测试记录",
        "content": content,
        "category": "verification",
        "source_path": "E:/training/mini.vcproject",
        "source_sha256": "a" * 64,
        "source_type": "vericut_project",
        "evidence": {"unit": "inch", "autodiff": {"solid_gouge_tol": {"Tol": "0.004"}}},
        "basis": "measured",
        "record_id": "r" * 20,
    }
    rec.update(overrides)
    return rec


# --------------------------------------------------------------------------- parser
def test_stl_bbox_binary_and_ascii(tmp_path):
    b, a = tmp_path / "b.stl", tmp_path / "a.stl"
    _binary_stl(b)
    _ascii_stl(a)
    rb, ra = vt.stl_bbox(b), vt.stl_bbox(a)
    assert rb["triangles"] == 1 and rb["bbox_max"] == [5.0, 8.0, 0.0]
    assert ra["triangles"] == 1 and ra["extent"] == [1.0, 2.0, 0.0]
    # 单位不可从 STL 推断，不得臆断 mm
    assert rb["unit"] == ra["unit"] == "unknown_from_stl"


def test_nc_parser_handles_concatenated_codes_and_ignores_comments(tmp_path):
    root = tmp_path / "training"
    _mini_corpus(root)
    recs, stats = vt.scan(root)
    nc = [r for r in recs if r.source_type == "nc_program"]
    assert len(nc) == 1
    codes = set(nc[0].evidence["unique_g"])
    # G90G0 / G43 / G81 这类连写代码必须被抽到
    assert {"90", "0", "43", "81", "80"} <= codes
    assert nc[0].evidence["code_counts"].get("S") == 1
    assert nc[0].evidence["spindle_speeds"] == ["1400"]
    assert not stats.errors


def test_scan_extracts_real_project_fields(tmp_path):
    root = tmp_path / "training"
    _mini_corpus(root)
    recs, _ = vt.scan(root)
    proj = [r for r in recs if r.source_type == "vericut_project"][0]
    assert proj.evidence["unit"] == "inch"
    assert proj.evidence["autodiff"]["solid_gouge_tol"]["Tol"] == "0.004"
    assert "mini.mcd" in proj.evidence["referenced_files"]
    assert proj.basis == "measured" and len(proj.source_sha256) == 64
    assert all(r.record_id() for r in recs)


def test_pdf_chunking_when_extractor_available(tmp_path):
    pymupdf = pytest.importorskip("pymupdf")
    root = tmp_path / "training" / "training_sessions" / "verification"
    root.mkdir(parents=True)
    pdf = root / "Session 999L-Test Handout.pdf"
    doc = pymupdf.open()
    for i in range(2):
        page = doc.new_page()
        page.insert_text((72, 72), f"Session 999L page {i + 1}: AutoDiff Gouge check.")
    doc.save(str(pdf))
    doc.close()
    recs, stats = vt.scan(tmp_path / "training")
    pdf_recs = [r for r in recs if r.source_type == "official_session_pdf"]
    assert pdf_recs and stats.pdf_pages == 2
    assert pdf_recs[0].evidence["session"] == "999L"
    assert pdf_recs[0].category == "verification"


# --------------------------------------------------------------------------- ingest gate
@pytest.fixture
def isolated_pipeline(tmp_path, monkeypatch):
    store = tmp_path / "store.json"
    monkeypatch.setattr(dlp, "KNOWLEDGE_STORE_FILE", store)
    return dlp.ContinualLearningPipeline(), tmp_path / "sft.jsonl"


def test_ingest_rejects_fabricated_evidence(isolated_pipeline):
    pipeline, sft = isolated_pipeline
    bad = [
        _fake_record("系统遵循 GB/ISO 国标及力学安全守则（FOS >= 1.5，体积守恒 Delta V != 0）。", record_id="b1"),
        _fake_record("这是一段足够长的技术说明文字，用于验证 basis 校验真的生效。", basis="asserted", record_id="b2"),
        _fake_record("这是一段足够长的技术说明文字，用于验证 sha 校验真的生效。", source_sha256="xyz", record_id="b3"),
        _fake_record("too short", record_id="b4"),
    ]
    out = pipeline.ingest_structured_records(bad, sft_file=sft, dry_run=True)
    assert out["accepted"] == 0 and out["rejected_count"] == 4
    assert {r["reason"] for r in out["rejected"]} == {
        "template_boilerplate", "basis_not_measured", "invalid_source_sha256",
        "empty_or_too_short_content",
    }


def test_ingest_is_idempotent_and_sft_is_rebuilt(isolated_pipeline):
    pipeline, sft = isolated_pipeline
    good = [
        _fake_record("VERICUT 工程 mini.vcproject 实测：Auto-Diff Solid Gouge Tol=0.004，Excess Tol=0.004，单位 inch。",
                     topic="AutoDiff 过切与残料容差", record_id="g1"),
        _fake_record("VERICUT 刀具库 mini.tls 实测：Tool ID=1，0.5 MILL，GagePoint Z=7.1，Units=Inch。",
                     topic="刀具库 GagePoint 规格", record_id="g2"),
    ]
    first = pipeline.ingest_structured_records(good, sft_file=sft)
    assert first["accepted"] == 2 and first["sft_pairs"] == 4
    assert sft.exists() and len(sft.read_text(encoding="utf-8").splitlines()) == 4

    again = pipeline.ingest_structured_records(good, sft_file=sft)
    assert again["accepted"] == 0 and again["duplicates"] == 2
    # 重新加载后仍幂等（按 record_id，而不是只在内存里）
    reloaded = dlp.ContinualLearningPipeline()
    third = reloaded.ingest_structured_records(good, sft_file=sft)
    assert third["accepted"] == 0 and third["duplicates"] == 2
    assert third["sft_pairs"] == 4

    rows = [json.loads(x) for x in sft.read_text(encoding="utf-8").splitlines()]
    assert all(r["provenance"]["basis"] == "measured" for r in rows)
    assert all(len(r["provenance"]["source_sha256"]) == 64 for r in rows)


def test_retrieve_returns_measured_provenance_and_empty_query_is_empty(isolated_pipeline):
    pipeline, sft = isolated_pipeline
    pipeline.ingest_structured_records([
        _fake_record("VERICUT 工程 mini.vcproject 实测：Auto-Diff Solid Gouge Tol=0.004，Excess Tol=0.004，单位 inch。",
                     topic="AutoDiff 过切与残料容差", record_id="g1"),
    ], sft_file=sft)
    hits = pipeline.retrieve_training_knowledge("Auto-Diff 过切 Gouge 残料 Excess 容差")
    assert hits and hits[0]["basis"] == "measured"
    assert hits[0]["source_path"].endswith("mini.vcproject")
    assert len(hits[0]["source_sha256"]) == 64
    assert "keyword_overlap" in hits[0] and "score" in hits[0]
    assert pipeline.retrieve_training_knowledge("") == []
    assert pipeline.retrieve_training_knowledge(" ") == []


# --------------------------------------------------------------------------- Agent wiring
def test_augmentation_injects_local_kb_without_pretending_internet(monkeypatch, isolated_pipeline):
    pipeline, sft = isolated_pipeline
    pipeline.ingest_structured_records([
        _fake_record("VERICUT 工程 mini.vcproject 实测：Auto-Diff Solid Gouge Tol=0.004，Excess Tol=0.004，单位 inch。",
                     topic="AutoDiff 过切与残料容差", record_id="g1"),
    ], sft_file=sft)
    monkeypatch.setattr(dlp, "get_learning_pipeline", lambda: pipeline)
    monkeypatch.setenv("VIRTU_INTERNET", "off")
    monkeypatch.setenv("VIRTU_TRAINING_KB", "on")

    q = "Auto-Diff 过切 Gouge 容差是多少？"
    prompt, cites = augmentation.augment_prompt(q)
    assert augmentation.TRAINING_MARKER in prompt
    assert augmentation.MARKER not in prompt  # 绝不冒充联网资料
    assert "本地实测来源" in prompt and "不得当作实时联网资料" in prompt
    assert cites and cites[0]["engine"] == "vericut_training_kb"
    assert cites[0]["basis"] == "measured"
    assert augmentation.augment_prompt(prompt) == (prompt, [])  # 幂等

    msgs = [{"role": "user", "content": q}]
    out, mcites = augmentation.augment_messages(msgs)
    assert any(augmentation.TRAINING_MARKER in str(m.get("content")) for m in out)
    assert [m for m in out if m["role"] == "user"][-1]["content"] == q
    assert mcites and mcites[0]["engine"] == "vericut_training_kb"


def test_training_kb_off_keeps_prompt_untouched(monkeypatch, isolated_pipeline):
    pipeline, sft = isolated_pipeline
    pipeline.ingest_structured_records([
        _fake_record("VERICUT 工程 mini.vcproject 实测：Auto-Diff Solid Gouge Tol=0.004，单位 inch。",
                     topic="AutoDiff 容差", record_id="g1"),
    ], sft_file=sft)
    monkeypatch.setattr(dlp, "get_learning_pipeline", lambda: pipeline)
    monkeypatch.setenv("VIRTU_INTERNET", "off")
    monkeypatch.setenv("VIRTU_TRAINING_KB", "off")
    q = "Auto-Diff Gouge 容差"
    assert augmentation.augment_prompt(q) == (q, [])


def test_super_agent_exposes_recall_tool(monkeypatch, isolated_pipeline):
    from virtu_omni.agent.super_agent import VirtuSuperAgent

    pipeline, sft = isolated_pipeline
    pipeline.ingest_structured_records([
        _fake_record("VERICUT Session 253L 实测：Learn From NC Program 优化流程与 Force 分析步骤。",
                     topic="Session 253L Learn From NC Program", record_id="g1"),
    ], sft_file=sft)
    monkeypatch.setattr(dlp, "get_learning_pipeline", lambda: pipeline)
    agent = VirtuSuperAgent()
    assert "recall_vericut_training" in agent._tool_registry
    res = agent.facet_recall_vericut_training({"query": "Learn From NC Program Force optimization"})
    assert res["success"] and res["basis"] == "measured"
    assert res["hit_count"] >= 1
    assert res["hits"][0]["source_sha256"]
    assert agent.facet_recall_vericut_training("")["basis"] == "no_evidence"


# --------------------------------------------------------------------------- shipped corpus gates
def test_shipped_sft_has_no_boilerplate_and_no_eval_leak():
    corpus = WORKSPACE / "data" / "sft" / "vericut_official_training.jsonl"
    if not corpus.exists():
        pytest.skip("official training corpus not ingested in this checkout")
    rows = [json.loads(x) for x in corpus.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert len(rows) >= 2
    assert all(r["provenance"]["basis"] == "measured" for r in rows)
    assert all(len(r["provenance"]["source_sha256"]) == 64 for r in rows)
    assert all(p not in r["output"] for r in rows for p in dlp.TEMPLATE_BOILERPLATE)

    from virtu_eval.contamination_check import scan_corpus
    assert scan_corpus(str(corpus))["hard_leaks"] == 0
