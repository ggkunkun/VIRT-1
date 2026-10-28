"""Unit tests for License Provenance Ledger and Compliance Scanner."""

import os
import tempfile
import json
from virtu_code.config import ComplianceConfig
from virtu_code.compliance.ledger import LicenseProvenanceLedger
from virtu_code.compliance.scanner import ComplianceScanner


def test_provenance_ledger_and_hash_chain() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        ledger_path = os.path.join(tmp_dir, "manifest.json")
        chain_path = os.path.join(tmp_dir, "chain.jsonl")
        cfg = ComplianceConfig(ledger_path=ledger_path, audit_chain_path=chain_path)
        ledger = LicenseProvenanceLedger(cfg)

        entry1 = ledger.record_provenance_entry(
            repo_name="psf/requests",
            author_or_org="psf",
            license_spdx="Apache-2.0",
            repo_url="https://github.com/psf/requests",
            commit_sha="abc1234",
            total_files_ingested=200,
        )

        entry2 = ledger.record_provenance_entry(
            repo_name="tokio-rs/tokio",
            author_or_org="tokio-rs",
            license_spdx="MIT",
            repo_url="https://github.com/tokio-rs/tokio",
            commit_sha="def5678",
            total_files_ingested=350,
        )

        assert entry2["previous_hash"] == entry1["current_hash"]

        # Verify integrity
        valid, blocks, msg = ledger.verify_ledger_integrity()
        assert valid is True
        assert blocks == 2
        assert msg == "HASH_CHAIN_INTEGRITY_VERIFIED"

        # Export 3rd-party audit bundle
        export_dir = os.path.join(tmp_dir, "bundle")
        cert_path = ledger.export_third_party_audit_bundle(export_dir)
        assert os.path.exists(cert_path)


def test_tamper_detection_in_hash_chain() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        chain_path = os.path.join(tmp_dir, "chain.jsonl")
        cfg = ComplianceConfig(audit_chain_path=chain_path)
        ledger = LicenseProvenanceLedger(cfg)

        ledger.record_provenance_entry("repo/a", "authorA", "MIT", "url", "sha1", 10)
        ledger.record_provenance_entry("repo/b", "authorB", "MIT", "url", "sha2", 20)

        # Tamper line 1
        with open(chain_path, "r", encoding="utf-8") as f:
            lines = [json.loads(line) for line in f]
        lines[0]["author_or_org"] = "MALICIOUS_IMPOSTER"
        with open(chain_path, "w", encoding="utf-8") as f:
            for l_entry in lines:
                f.write(json.dumps(l_entry) + "\n")

        # Verify tamper is caught
        valid, line_idx, msg = ledger.verify_ledger_integrity()
        assert valid is False
        assert "TAMPER_DETECTED" in msg


def test_compliance_scanner_clean_and_violations() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        corpus_clean = os.path.join(tmp_dir, "corpus_clean.jsonl")
        corpus_dirty = os.path.join(tmp_dir, "corpus_dirty.jsonl")
        manifest = os.path.join(tmp_dir, "manifest.json")

        with open(corpus_clean, "w", encoding="utf-8") as f:
            f.write(json.dumps({"clean_code": "def hello(): pass\n", "extracted_comments": []}) + "\n")

        with open(corpus_dirty, "w", encoding="utf-8") as f:
            f.write(json.dumps({
                "clean_code": "// Licensed under GNU General Public License v3.0\n",
                "extracted_comments": ["GPLv3 clause"],
            }) + "\n")

        with open(manifest, "w", encoding="utf-8") as f:
            json.dump({"repositories": [{"full_name": "clean/repo", "license_spdx": "MIT"}]}, f)

        scanner = ComplianceScanner(ComplianceConfig(scan_report_path=os.path.join(tmp_dir, "rep.md")))

        # Scan clean
        res_clean = scanner.scan_corpus(corpus_clean, manifest)
        assert res_clean["violations_found"] == 0
        assert res_clean["compliance_verdict"] == "COMPLIANT_ZERO_COPYLEFT_POLLUTION"

        # Scan dirty
        res_dirty = scanner.scan_corpus(corpus_dirty, manifest)
        assert res_dirty["violations_found"] >= 1
        assert res_dirty["compliance_verdict"] == "NON_COMPLIANT_VIOLATIONS_FOUND"
