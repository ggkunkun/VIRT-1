"""CLI Runner: Virtu Foundation Model Security Audit Suite.

Executes automated defensive security auditing on the Virtu Model,
Harness² scaffolding, multi-agent teams, and API bridge.
Grounded in Cloudflare's security-audit-skill specifications:
- AI-AND-LLM.md
- ATTACK-CLASSES.md
- report-schema.json
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Fix console encoding on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from virtu_omni.security.auditor import ModelSecurityAuditor


def main() -> int:
    print("=" * 76)
    print("  Virtu-Omni-10B x Cloudflare Security Audit (Security-Audit-Skill)")
    print("=" * 76)
    print(f"[*] Workspace Root: {WORKSPACE_DIR}")
    print("[*] Audit Rules: skills/security-audit/AI-AND-LLM.md & ATTACK-CLASSES.md")
    print("[*] Report Schema: skills/security-audit/report-schema.json")
    print("")

    auditor = ModelSecurityAuditor(workspace_root=WORKSPACE_DIR)

    # 1. Run full audit
    t0 = time.time()
    print("[>>>] Executing full security audit sweep across model components...")
    res = auditor.run_full_audit()
    elapsed = time.time() - t0
    summary = res["summary"]

    print(f"[+] Audit completed in {elapsed:.2f}s")
    print(f"    - Total Findings: {summary['total_findings']}")
    print(f"    - Confirmed: {summary['confirmed']}")
    print(f"    - Needs Validation: {summary['needs_validation']}")
    print(f"    - Severity Breakdown: {summary['findings_by_severity']}")
    print("")

    # 2. Export Artifacts
    findings_json_path = WORKSPACE_DIR / "benchmarks" / "security_findings.json"
    report_md_path = WORKSPACE_DIR / "benchmarks" / "model_security_audit_report.md"

    auditor.export_findings(findings_json_path)
    auditor.export_markdown_report(report_md_path)

    print(f"[+] Exported findings JSON: {findings_json_path}")
    print(f"[+] Exported Markdown report: {report_md_path}")
    print("")

    # 3. Validate against report-schema.json using validate-findings.cjs
    print("[>>>] Validating findings JSON against Cloudflare report-schema.json...")
    valid, message = auditor.validate_findings_schema(findings_json_path)

    if valid:
        print("[SUCCESS] Schema validation: PASSED (0 schema errors, 100% compliant)")
    else:
        print(f"[FAILED] Schema validation failed:\n{message}")
        return 1

    print("")
    print("=" * 76)
    print("  Security Audit Summary")
    print("=" * 76)
    for i, finding in enumerate(res["findings"], 1):
        sev = finding.get("severity", {}).get("overall_severity", "").upper()
        print(f"  [{i}] [{sev}] {finding.get('title')} ({finding.get('fingerprint')})")
        print(f"      Root Cause: {finding.get('root_cause', '')[:80]}...")
        print(f"      Strategy: {finding.get('remediation', {}).get('strategy', '')[:80]}...")
    print("=" * 76)
    return 0


if __name__ == "__main__":
    sys.exit(main())
