"""Hash-check the indexed E:/training machine-selection cases without editing them."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from virtu_omni.manufacturing.nc_audit import audit_nc_capability

INDEX = ROOT / "knowledge_base" / "training_case_index.json"
OUTPUT = ROOT / "knowledge_base" / "machining" / "training_case_manifest.jsonl"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_artifact(base: Path, relative: str, expected: str) -> Dict[str, Any]:
    path = base / relative
    if not path.is_file():
        return {"path": relative, "expected_sha256": expected, "verified": False,
                "issue": "source_file_missing"}
    actual = sha256_file(path)
    return {"path": relative, "expected_sha256": expected, "actual_sha256": actual,
            "verified": actual.lower() == str(expected or "").lower(),
            "issue": None if actual.lower() == str(expected or "").lower() else "sha256_mismatch"}


def build_manifest() -> Dict[str, Any]:
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    source_root = Path(str(index.get("root") or ""))
    if not source_root.is_dir():
        raise RuntimeError(f"training source root unavailable: {source_root}")
    machines = {str(item.get("file")): item for item in index.get("machines", [])}
    rows, issues = [], []
    static_capability_counts: Dict[str, int] = {}
    for case in index.get("cases", []):
        case_id = str(case.get("case_id") or "")
        project = verify_artifact(source_root, str(case.get("path") or ""),
                                  str(case.get("sha256") or ""))
        artifacts = [project]
        if not project["verified"]:
            issues.append(f"{case_id}:project:{project.get('issue')}")
        machine_ref = case.get("machine") or {}
        machine = machines.get(str(machine_ref.get("file") or ""))
        machine_ev = None
        if machine:
            machine_ev = verify_artifact(source_root, str(machine.get("path") or machine.get("file")),
                                         str(machine.get("sha256") or ""))
            artifacts.append(machine_ev)
            if not machine_ev["verified"]:
                issues.append(f"{case_id}:machine:{machine_ev.get('issue')}")
        program_rows = []
        for program in case.get("programs", []):
            row = verify_artifact(source_root, str(program.get("path") or program.get("file") or ""),
                                  str(program.get("sha256") or ""))
            if row["verified"]:
                try:
                    program_text = (source_root / row["path"]).read_bytes().decode("utf-8", errors="replace")
                    row["static_audit"] = audit_nc_capability(program_text)
                    for candidate in row["static_audit"].get("feature_candidates", []):
                        static_capability_counts[candidate] = static_capability_counts.get(candidate, 0) + 1
                except OSError as exc:
                    row["static_audit"] = {"status": "unavailable", "issues": [str(exc)],
                                            "program_release_allowed": False}
            else:
                row["static_audit"] = {"status": "unavailable", "issues": [row.get("issue")],
                                        "program_release_allowed": False}
            program_rows.append(row)
            if not row["verified"]:
                issues.append(f"{case_id}:program:{row.get('path')}:{row.get('issue')}")
        rows.append({
            "case_id": case_id,
            "case_status": case.get("status"),
            "case_status_basis": case.get("status_basis"),
            "required_capability": case.get("required_capability"),
            "capability_label": case.get("capability_label"),
            "capability_basis": case.get("capability_basis"),
            "axis_consistency": case.get("axis_consistency"),
            "machine": machine_ref,
            "programs": [{**{k: program.get(k) for k in
                              ("file", "sha256", "rotary_axes", "feed_rotary_axes",
                               "index_rotary_axes", "max_rotary_axes_in_feed_block")},
                           "static_audit": artifact.get("static_audit")}
                          for program, artifact in zip(case.get("programs", []), program_rows)],
            "artifacts": artifacts + program_rows,
            "expected_use": "reference_or_error_case_for_machine_and_axis_selection; labels preserve source index and are not independent proof of production safety",
            "source_case_path": str(case.get("path") or ""),
        })
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                                         for row in rows), encoding="utf-8")
    return {"case_count": len(rows), "machine_count": len(machines),
            "verified_artifacts": sum(bool(a["verified"]) for row in rows for a in row["artifacts"]),
            "artifact_count": sum(len(row["artifacts"]) for row in rows),
            "static_capability_counts": static_capability_counts,
            "issues": issues, "output": str(OUTPUT), "source_root": str(source_root)}


if __name__ == "__main__":
    try:
        result = build_manifest()
    except Exception as exc:
        print(json.dumps({"status": "error", "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        sys.exit(2)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(1 if result["issues"] else 0)
