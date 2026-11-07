# -*- coding: utf-8 -*-
"""Falsification gates for the 13.63B MoE asset tools (测量宪法 §4).

Every judge added on 2026-11-06 for the virtu-moe-14b (13,626,848,256 sparse params) work
gets a planted-bad-sample test here: a mutated weight file, a duplicated arm, a template that
drifted, a declared dtype table that contradicts the file layout, a lock held by another chain.
An empty match set, a parse failure, or a missing file must come out RED, never "skipped".

The orientation tests are the important ones: GGUF stores dims column-major, so reading
`ffn_gate_inp.weight` as (2, 4096) instead of its (4096, 2) header shape silently turns every
cosine/norm statistic into noise — which is exactly what the 2026-11-06 router_audit produced.
"""
import importlib.util
import io
import json
import os
import struct
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


forensics = _load("moe14b_gate_forensics")
matched = _load("moe14b_matched_tags")
grid = _load("moe14b_service_point_grid")

TMP = ROOT / "runs" / "eval" / "_test_moe14b_gates"


def _s(v):
    b = v.encode("utf-8")
    return struct.pack("<Q", len(b)) + b


def _kv(key, value):
    """Only the types these files need: str, int (UINT32), list of int (ARRAY of UINT32)."""
    out = _s(key)
    if isinstance(value, str):
        return out + struct.pack("<I", 8) + _s(value)
    if isinstance(value, (list, tuple)):
        return (out + struct.pack("<I", 9) + struct.pack("<I", 4) + struct.pack("<Q", len(value))
                + b"".join(struct.pack("<I", int(x)) for x in value))
    return out + struct.pack("<I", 4) + struct.pack("<I", int(value))


def write_gguf(path, kv, tensors, align=32):
    """tensors: list of (name, dims, dtype_int, np.ndarray in header (C-order) shape)."""
    infos = b""
    payload, offset = b"", 0
    for name, dims, dtype, arr in tensors:
        nbytes = int(np.prod(dims)) * (4 if dtype == 0 else 2)
        infos += _s(name) + struct.pack("<I", len(dims)) + b"".join(
            struct.pack("<Q", d) for d in dims) + struct.pack("<I", dtype) + struct.pack("<Q", offset)
        payload += arr.astype(np.float32 if dtype == 0 else np.float16).tobytes()
        pad = (-nbytes) % align
        payload += b"\x00" * pad
        offset += nbytes + pad
    body = b"".join(_kv(k, v) for k, v in kv.items())
    header = (b"GGUF" + struct.pack("<I", 3) + struct.pack("<Q", len(tensors))
              + struct.pack("<Q", len(kv)) + body + infos)
    header += b"\x00" * ((-len(header)) % align)
    with open(path, "wb") as f:
        f.write(header + payload)


BASE_KV = {"general.architecture": "qwen3moe", "general.name": "synthetic-moe",
           "qwen3moe.block_count": 1, "qwen3moe.expert_count": 2, "qwen3moe.expert_used_count": 1,
           "qwen3moe.embedding_length": 8, "qwen3moe.expert_feed_forward_length": 4,
           "tokenizer.chat_template": "{{ .Prompt }}"}


def gate_matrix(col0, col1):
    """Header dims (hidden=8, experts=2) column-major: expert e is column e."""
    m = np.zeros((8, 2), dtype=np.float32)
    m[:, 0] = col0
    m[:, 1] = col1
    return m


def synth_file(path, gate=None, attn_value=1.0, kv=None):
    g = gate if gate is not None else gate_matrix(np.ones(8, np.float32), -np.ones(8, np.float32))
    attn = np.full((8, 8), attn_value, dtype=np.float32)
    exps = np.ones((4, 8, 2), dtype=np.float32)
    emb = np.ones((8, 6), dtype=np.float32)
    write_gguf(path, kv if kv is not None else BASE_KV,
               [("token_embd.weight", [8, 6], 0, emb),
                ("blk.0.ffn_gate_inp.weight", [8, 2], 0, g),
                ("blk.0.ffn_down_exps.weight", [4, 8, 2], 0, exps),
                ("blk.0.attn_q.weight", [8, 8], 0, attn)])


def run_forensics(a, b, out, skip_hash=False):
    argv = [sys.argv[0], "--a", str(a), "--b", str(b), "--out", str(out)]
    if skip_hash:
        argv.append("--skip-hash")
    buf = io.StringIO()
    old = sys.argv
    try:
        sys.argv = argv
        with redirect_stdout(buf):
            rc = forensics.main()
    finally:
        sys.argv = old
    return rc, json.loads(Path(out).read_text(encoding="utf-8"))


def tensor_map_of(path):
    kv, infos, _, _, _, info_end = forensics.read_header(str(path))
    align = int(kv.get("general.alignment", 32))
    data_start = (info_end + align - 1) // align * align
    geometry = forensics.infer_geometry(infos, os.path.getsize(path), data_start, align)
    return kv, forensics.build_tensor_map(infos, geometry, data_start)


class TestGateOrientation(unittest.TestCase):
    """The bug that produced the old router_audit: reading the gate in the wrong orientation."""

    def setUp(self):
        TMP.mkdir(parents=True, exist_ok=True)

    def test_orthogonal_columns_measure_as_cos_zero(self):
        p = TMP / "orth.gguf"
        e0 = np.zeros(8, np.float32); e0[0] = 1.0
        e1 = np.zeros(8, np.float32); e1[1] = 1.0
        synth_file(p, gate=gate_matrix(e0, e1))
        _, tensors = tensor_map_of(p)
        stats = forensics.gate_stats(str(p), tensors, 2, 8)
        self.assertAlmostEqual(stats["cos_rows"]["mean"], 0.0, places=6)
        self.assertEqual(stats["expert_row_norm_mean"], 1.0)
        self.assertAlmostEqual(stats["cond_number"]["mean"], 1.0, places=3)
        self.assertEqual(stats["rank_deficient_layers"], 0)

    def test_antiparallel_columns_measure_as_cos_minus_one(self):
        p = TMP / "anti.gguf"
        synth_file(p)  # e1 = -e0
        _, tensors = tensor_map_of(p)
        stats = forensics.gate_stats(str(p), tensors, 2, 8)
        self.assertAlmostEqual(stats["cos_rows"]["mean"], -1.0, places=6)
        # rank-1 gate: must be reported as rank-deficient, never averaged into a silent nan
        self.assertEqual(stats["rank_deficient_layers"], 1)
        self.assertIsNone(stats["cond_number"]["mean"])


class TestForensicsRefusals(unittest.TestCase):
    def setUp(self):
        TMP.mkdir(parents=True, exist_ok=True)
        self.a = TMP / "a.gguf"
        self.b = TMP / "b.gguf"
        self.out = TMP / "r.json"
        synth_file(self.a)

    def test_non_moe_file_without_gates_is_red_not_empty_green(self):
        p = TMP / "dense.gguf"
        write_gguf(p, {"general.architecture": "qwen3", "qwen3.block_count": 1},
                   [("blk.0.attn_q.weight", [8, 8], 0, np.ones((8, 8), np.float32))])
        kv, infos, _, _, _, info_end = forensics.read_header(str(p))
        ds = (info_end + 31) // 32 * 32
        tensors = forensics.build_tensor_map(infos, forensics.infer_geometry(
            infos, os.path.getsize(p), ds, 32), ds)
        with self.assertRaises(ValueError):
            forensics.gate_stats(str(p), tensors, 2, 8)

    def test_declared_dtype_table_contradicting_layout_fails_loud(self):
        kv, infos, _, _, _, info_end = forensics.read_header(str(self.a))
        ds = (info_end + 31) // 32 * 32
        saved = forensics.ENUM_GEOMETRY[0]
        forensics.ENUM_GEOMETRY[0] = (256, 144, "Q4_K")  # wrong: this file holds F32
        try:
            with self.assertRaises(ValueError) as ctx:
                forensics.infer_geometry(infos, os.path.getsize(self.a), ds, 32)
            self.assertIn("contradicts", str(ctx.exception))
        finally:
            forensics.ENUM_GEOMETRY[0] = saved

    def test_same_file_on_both_sides_yields_red_gate_diff_claim(self):
        rc, rep = run_forensics(self.a, self.a, self.out)
        self.assertEqual(rc, 0)
        self.assertEqual(rep["hash_pass"]["differing_tensor_count"], 0)
        # empty difference set must NOT read as "all differences were gates"
        self.assertFalse(rep["hash_pass"]["all_differences_are_ffn_gate_inp"])

    def test_non_gate_tensor_mutation_is_caught(self):
        synth_file(self.b, attn_value=2.0)  # attn_q changed, gate identical
        _, rep = run_forensics(self.a, self.b, self.out)
        self.assertFalse(rep["hash_pass"]["all_differences_are_ffn_gate_inp"])
        self.assertIn("blk.0.attn_q.weight", rep["hash_pass"]["differing_tensors"])

    def test_gate_only_mutation_is_the_one_true_pairing(self):
        g = gate_matrix(np.ones(8, np.float32), np.array([0, 1, 0, 0, 0, 0, 0, 0], np.float32))
        synth_file(self.b, gate=g)
        _, rep = run_forensics(self.a, self.b, self.out)
        self.assertEqual(rep["hash_pass"]["differing_tensor_count"], 1)
        self.assertTrue(rep["hash_pass"]["all_differences_are_ffn_gate_inp"])

    def test_truncated_file_is_refused_not_zero_params(self):
        p = TMP / "trunc.gguf"
        data = Path(self.a).read_bytes()
        p.write_bytes(data[: len(data) // 2])
        with self.assertRaises(Exception):
            run_forensics(self.a, p, self.out)

    def test_incomplete_geometry_metadata_refuses_active_params(self):
        kv = dict(BASE_KV)
        kv["qwen3moe.expert_feed_forward_length"] = 0
        p = TMP / "nokv.gguf"
        synth_file(p, kv=kv)
        rc, _ = run_forensics(p, self.a, self.out)  # the defective file must be the one read
        self.assertEqual(rc, 3)  # refuses to derive active params from missing geometry


class TestMatchedTagGates(unittest.TestCase):
    def _arm(self, **kw):
        base = {"template": "T", "system": "S", "parameters": {"num_ctx": 4096, "num_gpu": 30},
                "parameter_count": matched.EXPECT_PARAMS, "gguf_sha256": "aaa",
                "kv_section_sha256": "kv1"}
        base.update(kw)
        return base

    def test_happy_path_is_matched(self):
        arms = {"t:a": self._arm(), "t:b": self._arm(gguf_sha256="bbb", kv_section_sha256="kv1")}
        gates, failures = matched.evaluate_gates(arms)
        self.assertEqual(failures, [])
        self.assertEqual(gates["G0_kv_sections_identical"], True)

    def test_identical_weights_are_rejected(self):
        arms = {"t:a": self._arm(), "t:b": self._arm()}  # same gguf sha
        gates, failures = matched.evaluate_gates(arms)
        self.assertFalse(gates["G5_gguf_bytes_differ"])
        self.assertTrue(any("G-5" in f for f in failures))

    def test_template_drift_is_rejected(self):
        arms = {"t:a": self._arm(), "t:b": self._arm(gguf_sha256="bbb", template="OTHER")}
        gates, failures = matched.evaluate_gates(arms)
        self.assertFalse(gates["G1_template_equal"])
        self.assertTrue(any("G-1" in f for f in failures))

    def test_system_drift_is_rejected(self):
        arms = {"t:a": self._arm(), "t:b": self._arm(gguf_sha256="bbb", system="OTHER SYSTEM")}
        self.assertFalse(matched.evaluate_gates(arms)[0]["G2_system_equal"])

    def test_parameter_drift_is_rejected(self):
        arms = {"t:a": self._arm(),
                "t:b": self._arm(gguf_sha256="bbb", parameters={"num_ctx": 8192, "num_gpu": 22})}
        self.assertFalse(matched.evaluate_gates(arms)[0]["G3_parameters_equal"])

    def test_wrong_parameter_count_is_rejected(self):
        arms = {"t:a": self._arm(), "t:b": self._arm(gguf_sha256="bbb", parameter_count=8190735360)}
        self.assertFalse(matched.evaluate_gates(arms)[0]["G4_parameter_count_equal_expected"])

    def test_missing_kv_evidence_is_red_not_vacuously_green(self):
        arms = {"t:a": self._arm(kv_section_sha256=None),
                "t:b": self._arm(gguf_sha256="bbb", kv_section_sha256=None)}
        self.assertFalse(matched.evaluate_gates(arms)[0]["G0_kv_sections_identical"])

    def test_single_arm_cannot_produce_a_verdict(self):
        gates, failures = matched.evaluate_gates({"only": self._arm()})
        self.assertEqual(gates, {"G0_two_arms": False})
        self.assertTrue(failures)


class TestServicePointGridGates(unittest.TestCase):
    def test_unknown_tag_refuses_to_measure(self):
        with self.assertRaises(SystemExit):
            grid.assert_model_present("virtu-moe-14b:nope", {"models": [{"name": "other:latest"}]})

    def test_empty_tag_list_is_red_not_free_pass(self):
        with self.assertRaises(SystemExit):
            grid.assert_model_present("anything", {"models": []})

    def test_fresh_lock_blocks_a_second_chain(self):
        lock_dir = Path(grid.ROOT) / "runs"
        lock_dir.mkdir(parents=True, exist_ok=True)
        other = lock_dir / "_other_chain.chain.lock"
        other.write_text(json.dumps({"chain": "other", "pid": 999999}), encoding="utf-8")
        try:
            os.utime(other, None)  # now -> fresh
            with self.assertRaises(SystemExit):
                grid.acquire_lock("_test_chain")
        finally:
            other.unlink(missing_ok=True)

    def test_stale_lock_does_not_wedge_the_box(self):
        lock_dir = Path(grid.ROOT) / "runs"
        lock_dir.mkdir(parents=True, exist_ok=True)
        other = lock_dir / "_other_chain.chain.lock"
        other.write_text(json.dumps({"chain": "other", "pid": 999999}), encoding="utf-8")
        old = time.time() - (grid.LOCK_STALE_S + 600)
        try:
            os.utime(other, (old, old))
            path = grid.acquire_lock("_test_chain_stale")
            self.assertTrue(os.path.exists(path))
        finally:
            other.unlink(missing_ok=True)
            (lock_dir / "_test_chain_stale.chain.lock").unlink(missing_ok=True)

    def test_cell_transport_error_is_recorded_not_swallowed(self):
        """A 500 from a crashed runner must show up as a transport error, never as a speed."""
        orig = grid.ask
        grid.ask = lambda *a, **k: (_ for _ in ()).throw(
            SystemExit("[FATAL] 请求失败（HTTP Error 500: Internal Server Error）"))
        try:
            rec = grid.measure_cell("m", "p", {"num_ctx": 4096, "num_gpu": 22}, 8,
                                    "gpu-sweep ctx4096", 4096, 22, {})
        finally:
            grid.ask = orig
        self.assertIsNone(rec["tok_s"])
        self.assertIn("500", rec["transport_error"])

    def test_cell_success_path_still_reports_speed(self):
        orig = grid.ask
        grid.ask = lambda *a, **k: {"tok_s": 9.8, "load_s": 2.0, "wall_s": 12.0, "eval_tokens": 96,
                                    "prompt_tokens": 40, "prompt_tok_s": 300.0,
                                    "truncated": False, "repeat_runs": 0, "response_head": "x",
                                    "served_model": "virtu-moe-14b:fast"}
        try:
            rec = grid.measure_cell("m", "p", {}, 8, "c", 4096, 30, {})
        finally:
            grid.ask = orig
        self.assertEqual(rec["tok_s"], 9.8)
        self.assertNotIn("transport_error", rec)


if __name__ == "__main__":
    unittest.main(verbosity=2)
