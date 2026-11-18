# -*- coding: utf-8 -*-
"""整改建议第 7 条回归：`verify_bundle_integrity()` 补真实 SHA-256 比对。

修复前该函数只比对 `size_bytes`，文件大小一致但内容被替换时会放行。
本测试用"同样大小、内容不同"的文件证明该漏洞已被堵住，并固定兼容升级语义：
有摘要 -> 比对；无摘要 -> 告警放行；字节码缓存 -> 跳过；`check_sha256=False` -> 退化旧行为。
"""

from __future__ import annotations

import hashlib
import json
import warnings

import pytest

from virtu_omni.models.smelt_loader import StandardizedSmeltBundle


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _make_bundle(tmp_path, records):
    """按给定记录构造最小 bundle（只需要 package_manifest.json）。"""
    bundle_dir = tmp_path / "bundle"
    (bundle_dir / "weights").mkdir(parents=True)
    manifest = {"package_title": "test-bundle", "files": []}

    for rec in records:
        target = bundle_dir / rec["filename"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(rec["content"])
        manifest["files"].append({
            "target_path": str(target),
            "filename": rec["filename"],
            "size_bytes": len(rec["content"]),
            "sha256": rec.get("sha256"),
        })

    (bundle_dir / "package_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    return StandardizedSmeltBundle(bundle_dir), bundle_dir


def test_matching_sha256_passes(tmp_path):
    payload = b"weights-payload-v1" * 64
    bundle, _ = _make_bundle(tmp_path, [
        {"filename": "weights/a.bin", "content": payload, "sha256": _sha256(payload)},
    ])
    ok, errors = bundle.verify_bundle_integrity()
    assert ok is True, errors
    assert errors == []


def test_same_size_different_content_now_fails(tmp_path):
    """核心可证伪点：尺寸完全一致、内容被替换，旧实现会放行。"""
    original = b"A" * 4096
    tampered = b"B" * 4096
    assert len(original) == len(tampered)

    bundle, bundle_dir = _make_bundle(tmp_path, [
        {"filename": "weights/a.bin", "content": original, "sha256": _sha256(original)},
    ])
    # 尺寸不变地替换内容
    (bundle_dir / "weights" / "a.bin").write_bytes(tampered)

    ok, errors = bundle.verify_bundle_integrity()
    assert ok is False
    assert any("SHA-256 mismatch" in e for e in errors), errors
    assert not any("Size mismatch" in e for e in errors), "尺寸未变，不应报尺寸错误"


def test_size_mismatch_still_reported(tmp_path):
    payload = b"x" * 128
    bundle, bundle_dir = _make_bundle(tmp_path, [
        {"filename": "weights/a.bin", "content": payload, "sha256": _sha256(payload)},
    ])
    (bundle_dir / "weights" / "a.bin").write_bytes(payload + b"extra")

    ok, errors = bundle.verify_bundle_integrity()
    assert ok is False
    assert any("Size mismatch" in e for e in errors), errors


def test_missing_sha256_warns_but_does_not_fail(tmp_path):
    """兼容升级：旧 manifest 无摘要时不得一刀切判红。"""
    payload = b"legacy-bundle" * 8
    bundle, _ = _make_bundle(tmp_path, [
        {"filename": "weights/a.bin", "content": payload, "sha256": None},
    ])
    with pytest.warns(RuntimeWarning):
        ok, errors = bundle.verify_bundle_integrity()
    assert ok is True, errors
    assert errors == []


def test_compiled_cache_is_skipped(tmp_path):
    """字节码缓存摘要随解释器漂移，默认跳过且不判红。"""
    payload = b"bytecode"
    bundle, _ = _make_bundle(tmp_path, [
        {"filename": "__pycache__/mod.cpython-312.pyc", "content": payload,
         "sha256": "deadbeef" * 8},
    ])
    with pytest.warns(RuntimeWarning):
        ok, errors = bundle.verify_bundle_integrity()
    assert ok is True, errors
    assert errors == []


def test_check_sha256_false_degrades_to_legacy_behaviour(tmp_path):
    """check_sha256=False 时必须退化为旧行为（只比尺寸），保证向后兼容。"""
    original = b"C" * 1024
    bundle, bundle_dir = _make_bundle(tmp_path, [
        {"filename": "weights/a.bin", "content": original, "sha256": _sha256(original)},
    ])
    (bundle_dir / "weights" / "a.bin").write_bytes(b"D" * 1024)

    ok, errors = bundle.verify_bundle_integrity(check_sha256=False)
    assert ok is True, errors


def test_missing_file_still_fails(tmp_path):
    payload = b"gone"
    bundle, bundle_dir = _make_bundle(tmp_path, [
        {"filename": "weights/a.bin", "content": payload, "sha256": _sha256(payload)},
    ])
    (bundle_dir / "weights" / "a.bin").unlink()

    ok, errors = bundle.verify_bundle_integrity()
    assert ok is False
    assert any("Missing bundle file" in e for e in errors), errors
