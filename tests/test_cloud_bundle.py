"""Gates on the cloud training bundles (route A = L40S bf16, route C = V100 fp16 QLoRA).

These catch the ways a turnkey run dies on paid GPU time with no local signal:
a shipped corpus whose bytes no longer match the sha the trainer re-checks, a CRLF
bootstrap bash refuses to run, a bootstrap that calls a script the bundle omits, a
ledger naming a different tarball, and the two trainers drifting apart on the data
semantics that make their scores comparable.
"""
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import tarfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "make_cloud_bundle", ROOT / "scripts" / "make_cloud_bundle.py")
BUILDER = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(BUILDER)

ROUTES = {
    "a": {"trainer": "train_virtu_l40s.py", "bootstrap": "bootstrap_l40s_train.sh",
          "requirements": "requirements-l40s.txt"},
    "c": {"trainer": "train_virtu_v100.py", "bootstrap": "bootstrap_v100_train.sh",
          "requirements": "requirements-v100.txt"},
}


def _ledger(route):
    return json.loads(BUILDER.manifest_path(route).read_text(encoding="utf-8"))


def _boot_text(route):
    return (ROOT / "scripts" / ROUTES[route]["bootstrap"]).read_text(encoding="utf-8")


def _trainer_text(route):
    return (ROOT / "scripts" / ROUTES[route]["trainer"]).read_text(encoding="utf-8")


def _tar_members(route):
    with tarfile.open(BUILDER.bundle_path(route), "r:gz") as tar:
        return {m.name: tar.extractfile(m).read() for m in tar.getmembers() if m.isfile()}


class BundlePerRouteMixin:
    route = "a"

    def test_required_files_exist_and_are_ledgered(self):
        for rel in BUILDER.route_paths(self.route):
            self.assertTrue((ROOT / rel).exists(), f"missing in repo: {rel}")
            self.assertIn(rel, _ledger(self.route)["files"], f"not in ledger: {rel}")

    def test_ledger_hashes_match_current_bytes(self):
        _, problems = BUILDER.build_entries(_ledger(self.route),
                                            BUILDER.route_paths(self.route), strict=True)
        self.assertEqual(problems, [])

    def test_tarball_bytes_match_the_ledger_not_just_the_repo(self):
        members = _tar_members(self.route)
        self.assertEqual(len(members), len(BUILDER.route_paths(self.route)))
        for rel, meta in _ledger(self.route)["files"].items():
            blob = members["virtu/" + rel]
            self.assertEqual(len(blob), meta["bytes"], rel)
            self.assertEqual(hashlib.sha256(blob).hexdigest(), meta["sha256"], rel)

    def test_corpus_gate_survives_the_tarball(self):
        entries = BUILDER.build_entries(_ledger(self.route),
                                        BUILDER.route_paths(self.route), strict=True)[0]
        self.assertEqual(BUILDER.check_corpus_gate(entries), [])

    def test_bootstrap_and_trainer_ship_together(self):
        entries = BUILDER.build_entries(_ledger(self.route),
                                        BUILDER.route_paths(self.route), strict=True)[0]
        self.assertEqual(BUILDER.check_trainer_matches_ledger(entries, self.route), [])

    def test_provenance_names_the_tarball_on_disk(self):
        prov = json.loads((ROOT / "checkpoints" / "PROVENANCE.json").read_text(encoding="utf-8"))
        block = prov.get("cloud_handoff", {}).get(f"route_{self.route.upper()}")
        self.assertIsNotNone(block, "PROVENANCE has no cloud_handoff block for this route")
        actual = hashlib.sha256(BUILDER.bundle_path(self.route).read_bytes()).hexdigest()
        self.assertEqual(block["bundle_sha256"], actual,
                         "rebuild then resync: python scripts/make_cloud_bundle.py --route "
                         + self.route)
        self.assertEqual(_ledger(self.route)["bundle"]["sha256"], actual)

    def test_budget_cap_is_stated(self):
        self.assertEqual(_ledger(self.route)["budget_cap_cny"], 50)

    def test_check_mode_exits_zero(self):
        proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_cloud_bundle.py"),
                               "--route", self.route, "--check"],
                              capture_output=True, text=True, cwd=str(ROOT))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("all sha256 verified", proc.stdout)

    def test_bootstrap_is_strict_mode_lf_only_and_shebang(self):
        rel = Path("scripts") / ROUTES[self.route]["bootstrap"]
        raw = (ROOT / rel).read_bytes()
        self.assertIn(b"set -Eeuo pipefail", raw)
        self.assertEqual(raw.count(b"\r"), 0, "CRLF makes bash refuse the script")
        self.assertTrue(raw.startswith(b"#!/usr/bin/env bash"))
        # No `bash -n` here: on this Windows box spawning bash from python either
        # trips the GBK reader thread or hangs at startup. The parse check runs on
        # the host as the first documented command (plan section 7.0).

    def test_prerequisites_are_asserted_before_anything_is_installed(self):
        text = _boot_text(self.route)
        prereq_at = text.index("repo prerequisites")
        # Section header in both bootstraps: "3. python env + deps ...".
        install_at = text.index("python env + deps")
        self.assertLess(prereq_at, install_at,
                        "a missing file must fail before pip/torch time is spent")
        shipped = set(BUILDER.route_paths(self.route))
        checked = set()
        for match in re.finditer(r'\[\s*-f\s*"\$REPO_ROOT/([^"]+)"\s*\]', text):
            rel = match.group(1)
            checked.add(rel)
            self.assertIn(rel, shipped, f"bootstrap requires {rel} but the bundle omits it")
            self.assertLess(text.index(f'"$REPO_ROOT/{rel}"'), install_at,
                            f"{rel} must be asserted in the prereq stage")
        self.assertTrue(checked)

    def test_only_a_completed_receipt_counts_as_success(self):
        self.assertIn('d.get("status") == "COMPLETED"', _boot_text(self.route))


class TestBundleRouteA(BundlePerRouteMixin, unittest.TestCase):
    route = "a"


class TestBundleRouteC(BundlePerRouteMixin, unittest.TestCase):
    route = "c"


class TestTrainersStayComparable(unittest.TestCase):
    """Routes A and C may differ in precision/length, never in data semantics."""

    @staticmethod
    def _has(text, needle, where):
        # assertTrue rather than assertIn: a failure must not dump a 20KB source file.
        assert needle in text, f"{needle!r} missing from {where}"

    def test_same_lora_target_modules(self):
        for mod in ("q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"):
            for route in ROUTES:
                self._has(_trainer_text(route), f'"{mod}"', ROUTES[route]["trainer"])

    def test_both_use_the_shared_chatml_loader(self):
        for route in ROUTES:
            self._has(_trainer_text(route), "from train_virtu import load_and_tokenize",
                      ROUTES[route]["trainer"])

    def test_both_gate_the_data_dir_and_the_receipt_identically(self):
        for route in ROUTES:
            text = _trainer_text(route)
            for needle in ("expected exactly one *.jsonl", "training_receipt.json",
                           '"SMOKE_ONLY" if args.smoke else "COMPLETED"'):
                self._has(text, needle, ROUTES[route]["trainer"])

    def test_precision_matches_the_hardware(self):
        a, c = _trainer_text("a"), _trainer_text("c")
        self._has(a, "bf16=True", "l40s args")
        assert "fp16=True" not in a, "the bf16 route must not set fp16"
        self._has(c, "fp16=True", "v100 args")
        self._has(c, "bf16=False", "v100 args")
        self._has(c, "no bf16", "v100 docstring")

    def test_l40s_defaults_to_the_length_the_audit_proved_necessary(self):
        la = re.search(r'--max-len.*?default=(\d+)', _trainer_text("a"))
        lc = re.search(r'--max-len.*?default=(\d+)', _trainer_text("c"))
        self.assertIsNotNone(la)
        self.assertIsNotNone(lc)
        # work/corpus_len_distribution.json: 300 of 5,991 rows are ~4.9-5.0k tokens,
        # so 4096 truncates them too; 5120 is the measured zero-truncation cap.
        self.assertEqual(int(la.group(1)), 5120, "route A exists to keep the corpus whole")
        self.assertEqual(int(lc.group(1)), 2048, "route C is VRAM-bound; 5120 would OOM")
        self._has(_trainer_text("a"), "(1024, 1536, 2048, 3072, 4096, 5120)", "audit caps")

    def test_l40s_padding_grouping_and_length_audit(self):
        text = _trainer_text("a")
        self.assertIn("group_by_length=args.group_by_length", text)
        self.assertIn("--audit-lengths", text)
        self.assertIn("--audit-lengths", _boot_text("a"),
                      "the bootstrap must measure truncation before paying for training")

    def test_v100_empty_optional_flags_survive_set_u(self):
        text = _boot_text("c")
        self.assertIn('--output "$OUTPUT" ${SMOKE_FLAGS[@]+"${SMOKE_FLAGS[@]}"}', text)
        self.assertNotIn('--output "$OUTPUT" "${SMOKE_FLAGS[@]}"', text)

    def test_l40s_smoke_ladder_walks_down_then_quantizes(self):
        text = _boot_text("a")
        ladder = text[text.index("LADDER=("):text.index("run_smoke()")]
        rungs = re.findall(r'"([^"]*)"', ladder)
        self.assertEqual(rungs[0], "", "rung 0 must be the untouched defaults")
        cut = next((i for i, r in enumerate(rungs) if "--load-4bit" in r), len(rungs))
        # Quantizing is the last resort, so it must only appear at the tail.
        assert all("--load-4bit" in r for r in rungs[cut:]), f"4bit rung out of order: {rungs}"
        pre = [int(m.group(1)) for r in rungs[:cut]
               for m in [re.search(r"--max-len (\d+)", r)] if m]
        self.assertEqual(pre, sorted(pre, reverse=True), f"pre-4bit ladder must shrink: {rungs[:cut]}")
        assert rungs[-1].startswith("--load-4bit"), f"last rung must quantize: {rungs[-1]}"

    def test_neither_route_pays_for_a_flash_attn_build(self):
        for route in ROUTES:
            req = (ROOT / ROUTES[route]["requirements"]).read_text(encoding="utf-8")
            pins = [ln.strip() for ln in req.splitlines() if ln.strip() and not ln.startswith("#")]
            self.assertNotIn("flash-attn", [p.split("[")[0] for p in pins], route)


if __name__ == "__main__":
    unittest.main()
