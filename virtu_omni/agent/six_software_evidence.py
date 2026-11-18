# -*- coding: utf-8 -*-
"""Fail-closed adjudication for six-software chain evidence bundles."""

from __future__ import annotations

import hashlib
import os
from typing import Any


REQUIRED_STAGES = ("solidworks", "nx", "autocad", "cimco", "vericut", "sscnc")


def adjudicate_chain_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    """Verify each stage executed and its recorded output files still match their hashes.

    A preflight pass or a stage's own ``status=executed`` claim is insufficient without
    nonempty on-disk artifacts, recorded metrics, and matching integrity digests.
    """
    issues: list[str] = []
    if not isinstance(bundle, dict):
        return {"passed": False, "verified": False, "verdict_code": "INVALID_BUNDLE",
                "issues": ["bundle is not an object"], "stages": {}}
    run_id = str(bundle.get("run_id") or "").strip()
    if not run_id:
        issues.append("run_id_missing")
    raw_stages = bundle.get("stages")
    if not isinstance(raw_stages, dict):
        raw_stages = {}
        issues.append("stages_missing")
    integrity = bundle.get("integrity") if isinstance(bundle.get("integrity"), dict) else {}
    stage_results: dict[str, Any] = {}

    for name in REQUIRED_STAGES:
        stage = raw_stages.get(name)
        stage_issues: list[str] = []
        if not isinstance(stage, dict):
            stage_issues.append("stage_missing")
            stage_results[name] = {"passed": False, "issues": stage_issues, "files": []}
            issues.extend(f"{name}:{item}" for item in stage_issues)
            continue
        if stage.get("status") != "executed":
            stage_issues.append(f"status_{stage.get('status') or 'missing'}")
        if not isinstance(stage.get("metrics"), dict) or not stage.get("metrics"):
            stage_issues.append("metrics_missing")

        files = stage.get("files")
        if not isinstance(files, list) or not files:
            files = []
            stage_issues.append("artifact_list_missing")
        file_results = []
        for raw_path in files:
            if not isinstance(raw_path, str) or not raw_path.strip():
                stage_issues.append("artifact_path_invalid")
                continue
            path = os.path.abspath(raw_path)
            if not os.path.isfile(path):
                stage_issues.append(f"artifact_missing:{os.path.basename(path)}")
                continue
            size = os.path.getsize(path)
            if size <= 0:
                stage_issues.append(f"artifact_empty:{os.path.basename(path)}")
                continue
            expected = integrity.get(raw_path) or integrity.get(path)
            if not isinstance(expected, dict) or not expected.get("sha256"):
                stage_issues.append(f"digest_missing:{os.path.basename(path)}")
                continue
            digest = hashlib.sha256()
            with open(path, "rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            actual_sha = digest.hexdigest()
            if actual_sha != expected.get("sha256") or size != int(expected.get("bytes", -1)):
                stage_issues.append(f"digest_mismatch:{os.path.basename(path)}")
                continue
            file_results.append({"path": path, "bytes": size, "sha256": actual_sha,
                                 "verified": True})
        if not file_results:
            stage_issues.append("no_verified_artifacts")
        stage_passed = not stage_issues
        stage_results[name] = {"passed": stage_passed, "status": stage.get("status"),
                               "issues": stage_issues, "files": file_results}
        issues.extend(f"{name}:{item}" for item in stage_issues)

    passed = not issues and all(stage_results.get(name, {}).get("passed") for name in REQUIRED_STAGES)
    return {
        "passed": passed,
        "verified": passed,
        "verdict_code": "SIX_SOFTWARE_EVIDENCE_PASS" if passed else "SIX_SOFTWARE_EVIDENCE_INCOMPLETE",
        "basis": "measured_artifact_hashes" if passed else "insufficient_or_invalid_evidence",
        "required_stages": list(REQUIRED_STAGES),
        "run_id": run_id or None,
        "issues": issues,
        "stages": stage_results,
    }
