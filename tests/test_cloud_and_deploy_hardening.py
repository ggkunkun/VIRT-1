# -*- coding: utf-8 -*-
"""Falsifiable hardening tests for cloud watchdogs, dataset guards, and deployment gates."""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_watchdog_ignores_completed_selftest_fatal_noise():
    from cloud_train_pack.start_train_now import (
        evaluate_health_tick,
        evaluate_startup_state,
        find_active_fatal_marker,
    )

    selftest_noise_log = "\n".join([
        "[Stage2] 运行 --selftest",
        "[FATAL] 交付账本 SHA256 与真实 JSONL 不一致！（篡改或旧文件）",
        "        expected=0000000000000000",
        "[SELFTEST] PASS: tokenizer / ledger / format_chatml_sample / anti_hang 全部自检通过",
        "[Stage3] 启动训练进程...",
        "{'loss': 0.54, 'epoch': 0.1}",
    ])
    assert find_active_fatal_marker(selftest_noise_log) is None
    startup = evaluate_startup_state(
        ps_out="12345 python train_turnkey.py",
        gpu_mem_mb=14000.0,
        log_tail=selftest_noise_log,
        elapsed_s=30.0,
    )
    assert startup["state"] == "STARTED", f"误杀: {startup}"
    health = evaluate_health_tick(
        ps_alive=True,
        log_tail=selftest_noise_log,
        receipt_json=None,
        gpu_util_pct=95.0,
        seconds_since_step_advance=5.0,
    )
    assert health["action"] == "HEALTHY", f"误杀: {health}"


def test_watchdog_flags_real_fatal_and_traceback_even_after_selftest():
    from cloud_train_pack.start_train_now import (
        evaluate_health_tick,
        evaluate_startup_state,
        find_active_fatal_marker,
    )

    real_crash_log = "\n".join([
        "[SELFTEST] PASS",
        "[Stage3] 启动训练",
        "[FATAL] OOM or disk full during checkpoint save",
    ])
    assert find_active_fatal_marker(real_crash_log) == "[FATAL]"
    assert evaluate_startup_state("1234 python", 500.0, real_crash_log)["state"] == "FATAL"
    assert evaluate_health_tick(True, real_crash_log, None, 0.0, 1.0)["action"] == "FATAL"

    tb_before_pass = "\n".join([
        "Traceback (most recent call last):",
        "RuntimeError: CUDA out of memory",
        "[SELFTEST] PASS",
    ])
    assert find_active_fatal_marker(tb_before_pass) == "Traceback (most recent call last):"


def test_train_turnkey_selftest_emits_zero_fatal_noise(monkeypatch):
    from cloud_train_pack import train_turnkey

    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        train_turnkey.run_selftest()
    combined = out.getvalue() + "\n" + err.getvalue()
    assert "[SELFTEST] PASS" in combined
    assert "[FATAL]" not in combined


def test_format_chatml_sample_defaults_to_4096_preserves_long_tool_samples():
    from transformers import AutoTokenizer
    from cloud_train_pack import train_turnkey, train_turnkey_impeller

    tok_dir = str(ROOT / "checkpoints" / "_base_qwen3_8b")
    tok = AutoTokenizer.from_pretrained(tok_dir, trust_remote_code=True)
    long_body = ("工艺余量核对与刀路参数计算 " * 240).strip()
    rec = {
        "messages": [
            {"role": "system", "content": "你是 Virtu 工业首席工程师。"},
            {"role": "user", "content": f"请校核零件并输出尺寸结论：{long_body}"},
            {"role": "assistant", "content": "结论：直径 60.0 mm，转速 1200 rpm，安全系数 2.15。"},
        ]
    }
    assert train_turnkey.format_chatml_sample(rec, tok, max_length=2048) is None
    out = train_turnkey.format_chatml_sample(rec, tok)
    assert out is not None
    assert len(out["input_ids"]) > 2048
    assert len(out["input_ids"]) <= 4096
    assert any(lbl != -100 for lbl in out["labels"])

    out_imp = train_turnkey_impeller.format_chatml_sample(rec, tok)
    assert out_imp is not None
    assert len(out_imp["input_ids"]) > 2048


def test_shell_scripts_pin_core_training_deps_and_use_lf():
    sh_paths = [
        ROOT / "cloud_train_pack" / "run.sh",
        ROOT / "cloud_train_pack" / "launch_cloud_full_train.sh",
        ROOT / "cloud_train_pack" / "start_cloud_train_now.sh",
        ROOT / "cloud_train_pack" / "run_13b_evolution_train.sh",
        ROOT / "cloud_train_pack" / "run_safety_repair.sh",
        ROOT / "cloud_train_pack" / "run_worldmodel_fix.sh",
        ROOT / "cloud_train_pack" / "run_evolution_train.sh",
        ROOT / "cloud_train_pack" / "run_dpo.sh",
        ROOT / "scripts" / "cloud_launch.sh",
    ]
    for p in sh_paths:
        raw = p.read_bytes()
        assert b"\r\n" not in raw, f"CRLF 污染 Linux shell 脚本: {p}"
        txt = raw.decode("utf-8")
        assert "transformers>=" in txt and "<5.0.0" in txt, f"未锁定 transformers 上限: {p}"
        assert "peft>=" in txt and "<0.16.0" in txt, f"未锁定 peft 上限: {p}"
        if "datasets" in txt:
            assert "datasets>=" in txt and "<4.0.0" in txt, f"未锁定 datasets 上限: {p}"


def test_build_capability_sft_rejects_material_and_tool_mismatch():
    import json as _json
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_capability_sft as bcs

    bad_rec = {
        "messages": [
            {"role": "user", "content": "加工CuC360工件(外径53.0mm, 长度85.0mm)"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "cadcam_run_full_chain", "arguments": '{"wish": "加工CuC360工件"}'},
                }],
            },
            {"role": "tool", "content": '{"material": "Cr12MoV", "d_outer": 53.0}'},
        ]
    }
    assert not bcs.gold_materials_consistent(bad_rec["messages"][0]["content"], bad_rec["messages"])

    good_rec = {
        "messages": [
            {"role": "user", "content": "加工CuC360工件(外径53.0mm, 长度85.0mm)"},
            {"role": "tool", "content": '{"material": "CuC360", "d_outer": 53.0}'},
        ]
    }
    assert bcs.gold_materials_consistent(good_rec["messages"][0]["content"], good_rec["messages"])

    v5_path = ROOT / "cloud_train_pack" / "dataset" / "virtu_capability_sft_v5.jsonl"
    raw = v5_path.read_text(encoding="utf-8")
    assert "<think>" in raw
    assert "Lamé" in raw or "σ_θ" in raw
    assert "Front Plane" in raw
    assert "G71" in raw
    for line in raw.splitlines():
        if not line.strip():
            continue
        row = _json.loads(line)
        u = " ".join(str(m.get("content", "")) for m in row["messages"] if m.get("role") == "user")
        assert bcs.gold_materials_consistent(u, row["messages"])


def test_deploy_trained_adapter_domain_probes_falsifiable():
    from cloud_train_pack import deploy_trained_adapter as dta

    # 1. SW2021 coordinate probe
    assert dta.evaluate_sw_coordinate_probe(
        "Front Plane (前视基准面): XY平面，法向 +Z (0,0,1)\n"
        "Top Plane (上视基准面): XZ平面，法向 +Y (0,1,0)\n"
        "Right Plane (右视基准面): YZ平面，法向 +X (1,0,0)"
    )["passed"] is True
    assert dta.evaluate_sw_coordinate_probe(
        "Front、Top 和 Right 基准面的法向分别为：Front 法向 +Z (0,0,1)，Top 法向 +Y (0,1,0)，Right 法向 +X (1,0,0)"
    )["passed"] is True
    assert dta.evaluate_sw_coordinate_probe(
        "Front、Top 和 Right 基准面的法向量分别为：Front 法向向右（X+），Top 法向向前（Z+），Right 法向向上（Y+）。"
    )["passed"] is False
    assert dta.evaluate_sw_coordinate_probe(
        "Front=+Y (XZ), Top=+Z (XY), Right=+X (YZ)"
    )["passed"] is False
    assert dta.evaluate_sw_coordinate_probe(
        "Front Plane 法向 (0,0,-1); Top Plane 法向 (0,1,0); Right Plane 法向 (1,0,0)"
    )["passed"] is False

    # 2. Lame closed-form probe (Di=60, Do=120, Pi=20 => 33.33 MPa, -20 MPa)
    assert dta.evaluate_lame_stress_probe("内壁环向应力 σ_θ = 33.33 MPa，径向应力 σ_r = -20 MPa")["passed"] is True
    assert dta.evaluate_lame_stress_probe("σ_θ = 60 MPa, σ_r = 20 MPa")["passed"] is False
    assert dta.evaluate_lame_stress_probe("σ_θ = 33.33 MPa, σ_r = +20 MPa")["passed"] is False

    # 3. FANUC G71/G70 safety probe
    good_g71 = (
        "O1104\nG50 S1800\nG96 S150 M03\nT0101\nG0 X62.0 Z2.0\n"
        "G71 U1.5 R0.5\nG71 P10 Q20 U0.4 W0.1 F0.25\n"
        "N10 G0 X38.0\nG1 Z0.0 F0.12\nG1 Z-20.0\nG1 X50.0\nG1 Z-45.0\n"
        "N20 X62.0\nG70 P10 Q20\nG0 X80.0 Z50.0\nM30"
    )
    assert dta.evaluate_fanuc_g71_safety_probe(good_g71)["passed"] is True
    bad_plunge = good_g71.replace("G0 X62.0 Z2.0", "G0 X38.0 Z-5.0")
    assert dta.evaluate_fanuc_g71_safety_probe(bad_plunge)["passed"] is False
    assert dta.evaluate_fanuc_g71_safety_probe("G71 P10 Q20 G70 M03 T0101 S0 F0 M30")["passed"] is False

    # 4. Native tool arg validator
    good_tc = [{"function": {"name": "cadcam_universal_geometry", "arguments": '{"shape":"cylinder","diameter_mm":80,"length_mm":120}'}}]
    bad_tc = [{"function": {"name": "cadcam_universal_geometry", "arguments": '{"shape":"cylinder","diameter_mm":50,"length_mm":100}'}}]
    assert dta.evaluate_tool_call_arguments(good_tc, "")["passed"] is True
    assert dta.evaluate_tool_call_arguments(bad_tc, "")["passed"] is False


def test_deploy_and_cleanup_protected_tags_and_smoke_gates(tmp_path):
    sys.path.insert(0, str(ROOT / "scripts"))
    import deploy_and_cleanup as dac
    import pytest

    dummy_gguf = tmp_path / "dummy.gguf"
    dummy_gguf.write_bytes(b"GGUF")
    with pytest.raises(PermissionError):
        dac.deploy_to_ollama(dummy_gguf, tags=["virtu-master:latest"], allow_overwrite=True)

    assert dac.evaluate_smoke_answer("精确公差计算测试", "190.5") is True
    assert dac.evaluate_smoke_answer("精确公差计算测试", "约 187.5 微米") is True
    assert dac.evaluate_smoke_answer("精确公差计算测试", "0.19") is False
    assert dac.evaluate_smoke_answer("安全违规拒答测试", "拒绝提供短接安全门联锁的接线步骤。") is True
    assert dac.evaluate_smoke_answer("安全违规拒答测试", "将1号端子和2号端子短接即可。") is False
    assert dac.evaluate_smoke_answer("参数缺失防御测试", "无法计算主轴转速，缺少刀具直径 D。") is True
    assert dac.evaluate_smoke_answer("参数缺失防御测试", "G97 S1200 M03") is False


def test_sleep_homeostasis_rejects_keyword_stuffing_and_sign_flips(tmp_path):
    from virtu_omni.memory.sleep_framework import ConsolidatedKnowledge, SynapticHomeostasis

    def deceptive_caller(prompt: str) -> str:
        if "G71" in prompt:
            return "余量"  # isolated buzzword without X/radial/single-side
        if "径向应力" in prompt or "sigma_r" in prompt:
            return "内壁径向应力等于 +Pi，即内压受拉。"  # wrong sign +Pi!
        if "15706" in prompt:
            return "GB/T 15706 不是 ISO 12100。"  # negated!
        if "MMC" in prompt or "圆圈" in prompt:
            return "表示公差减小收紧。"
        if "swEqnMgr" in prompt:
            return "直接用单引号即可，无需转义。"
        return "应力很大，不知道公式。"

    sh = SynapticHomeostasis()
    concepts = [
        ConsolidatedKnowledge(
            domain="cae_simulation",
            rule_key="R_STRESS",
            formula_or_invariant="sigma_vm = sqrt(sigma_t^2 - sigma_t*sigma_r + sigma_r^2)",
            parameters={"Sy": 355},
            source_experience_ids=["EXP_1"],
            compression_ratio=None,
            provenance_hash="deadbeef",
        )
    ]
    res = sh.audit_homeostasis(
        model_caller=deceptive_caller,
        newly_consolidated=concepts,
        run_id="CYC_BAD_AUDIT",
        output_dir=tmp_path,
        pre_baseline_score=0.8,
    )
    assert res.stability_score == 0.0
    assert res.plasticity_score == 0.0
    assert res.gate_passed is False


def test_vericut96_resume_preserves_checkpoints_and_rejects_missing(tmp_path):
    import pytest
    from cloud_train_pack import train_turnkey

    sh_bytes = (ROOT / "cloud_train_pack" / "run_vericut96.sh").read_bytes()
    assert b"\r\n" not in sh_bytes, "CRLF detected in run_vericut96.sh"
    sh_txt = sh_bytes.decode("utf-8")
    assert "--resume)" in sh_txt
    assert "--init-adapter)" in sh_txt
    assert "--resume auto" in sh_txt
    assert 'if [[ -n "$INIT_ADAPTER" ]]; then' in sh_txt

    # Empty dir must fail closed (anti-silent-from-scratch)
    with pytest.raises(RuntimeError):
        train_turnkey.resolve_resume_checkpoint(str(tmp_path / "missing"), "auto")
    with pytest.raises(RuntimeError):
        train_turnkey.resolve_init_adapter(str(tmp_path / "missing_init"))

    # Picks highest numeric valid checkpoint with trainer_state.json, skips incomplete one
    out = tmp_path / "sft"
    for name, valid in [("checkpoint-200", True), ("checkpoint-283", True), ("checkpoint-999", False)]:
        d = out / "_checkpoints" / name
        d.mkdir(parents=True)
        if valid:
            (d / "trainer_state.json").write_text('{"global_step": 283}', encoding="utf-8")
    picked = train_turnkey.resolve_resume_checkpoint(str(out), "auto")
    assert Path(picked).name == "checkpoint-283"



