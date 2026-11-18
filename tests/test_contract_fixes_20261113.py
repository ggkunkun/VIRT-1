# -*- coding: utf-8 -*-
"""tests/test_contract_fixes_20261113.py — 审计 §4 七项落差的回归测试。

对应 reports/SIX_SOFTWARE_DL_DEPTH_AUDIT_2026-11-13.md §4：
  1. VERICUT 工具描述不得再宣称无头批处理
  2. 标准件库查询不得恒返回空
  3. super_agent 的 analyze_inspection 必须存在
  4. Auto-Diff triage 必须能吃下视觉桥的嵌套 metrics
  5. AGENTS.md 契约与实现对齐（已实现项必须给可解析证据，且不得自相矛盾）
  6. 语料工具名必须 100% 有运行时映射
  7. ΔV 判词必须是真实计算值

这些测试不启动任何工业软件，只校验契约与纯函数行为。
"""

import ast
import glob
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

TRIAGE_DIR = os.path.join(ROOT, "skills", "vericut-autodiff-triage", "scripts")
if TRIAGE_DIR not in sys.path:
    sys.path.insert(0, TRIAGE_DIR)


@pytest.fixture()
def approved(monkeypatch):
    """只读/写工具都放行，避免审批闸门干扰契约校验。"""
    monkeypatch.setenv("VIRTU_TOOL_APPROVAL", "1")
    return None


# ---------------------------------------------------------------------------
# 1. VERICUT 工具描述
# ---------------------------------------------------------------------------
def test_vericut_tool_description_does_not_claim_headless():
    from bridges.tool_calling_specs import get_cadcam_tool_definitions

    spec = {
        d["function"]["name"]: d["function"] for d in get_cadcam_tool_definitions()
    }["cadcam_vericut_simulate"]
    desc = spec["description"]
    assert "unsupported_headless" in desc, "描述必须写明 9.6 无头不可用"
    assert "vericut.bat -b 启动无头批处理仿真" not in desc


def test_vericut_headless_returns_structured_unsupported(tmp_path):
    from bridges.vericut_bridge import VericutBridge

    bridge = VericutBridge()
    project = tmp_path / "x.vcproject"
    project.write_text("stub", encoding="utf-8")
    res = bridge.run_batch_simulation(str(project))
    assert res["status"] == "unsupported_headless"
    assert "vericut_link.py" in res["message"]


# ---------------------------------------------------------------------------
# 2. 标准件库查询
# ---------------------------------------------------------------------------
def test_standard_parts_library_returns_items(approved):
    from bridges.tool_calling_specs import execute_tool_call

    res = execute_tool_call("cad.query_standard_parts_library", {"software": "SolidWorks_2021"})
    assert res["status"] == "ok"
    assert res["count"] > 0
    assert res["software"] == "SOLIDWORKS 2021", "旧错误键名 SolidWorks_2021 必须被解析"
    assert res["data_source"] == "software_ontology"
    assert isinstance(res["libraries"], list) and res["libraries"]


def test_standard_parts_library_unknown_software_is_not_found(approved):
    from bridges.tool_calling_specs import execute_tool_call

    res = execute_tool_call(
        "cad.query_standard_parts_library", {"software": "NoSuchCAD 1900", "keyword": "zzz"}
    )
    assert res["status"] == "not_found"
    assert res["count"] == 0


def test_resolve_software_aliases():
    from virtu_omni.knowledge.software_plugin_ontology import resolve_software

    assert resolve_software("Siemens NX 12.0") == "中文版NX12.0"
    assert resolve_software("solidworks") == "SOLIDWORKS 2021"
    assert resolve_software("VERICUT 9.6") == "Vericut 9.6"
    assert resolve_software("斯沃") == "斯沃数控仿真软件 (SSCNC)"
    assert resolve_software("不存在") is None


# ---------------------------------------------------------------------------
# 3. 视觉桥统一入口
# ---------------------------------------------------------------------------
def test_vision_bridge_has_analyze_inspection():
    from bridges.cadcam_vision_bridge import CADCAMVisionBridge

    vb = CADCAMVisionBridge()
    assert hasattr(vb, "analyze_inspection")
    unknown = vb.analyze_inspection("bogus_task", "x.png")
    assert unknown["status"] == "error"
    assert unknown["verdict_code"] == "UNKNOWN_VISION_TASK"
    missing = vb.analyze_inspection("autodiff_inspection", "")
    assert missing["verdict_code"] == "MISSING_IMAGE_PATH"


def test_vision_bridge_routes_each_task(monkeypatch):
    from bridges.cadcam_vision_bridge import CADCAMVisionBridge

    vb = CADCAMVisionBridge()
    seen = {}

    def fake(method):
        def _inner(path):
            seen[method] = path
            return {"status": "success", "via": method}
        return _inner

    for task, method in (
        ("autodiff_inspection", "inspect_vericut_autodiff"),
        ("blueprint_analysis", "analyze_drawing_blueprint"),
        ("cnc_screen_perception", "inspect_cnc_screen"),
    ):
        monkeypatch.setattr(vb, method, fake(method))
        out = vb.analyze_inspection(task, "img.png")
        assert out["via"] == method

    assert set(seen) == {
        "inspect_vericut_autodiff",
        "analyze_drawing_blueprint",
        "inspect_cnc_screen",
    }


def test_super_agent_visual_inspect_call_is_not_dangling():
    import inspect

    from bridges.cadcam_vision_bridge import CADCAMVisionBridge

    src = inspect.getsource(CADCAMVisionBridge)
    assert "def analyze_inspection" in src


# ---------------------------------------------------------------------------
# 4. Auto-Diff triage 字段兼容
# ---------------------------------------------------------------------------
def _nested_payload(gouge=0, excess=200, green=199800, machined=200000, total=99.9,
                    verdict="PASSED_IN_TOLERANCE"):
    return {
        "status": "success",
        "metrics": {
            "gouge_pixels": gouge,
            "gouge_percentage": round(100.0 * gouge / machined, 2),
            "excess_pixels": excess,
            "excess_percentage": round(100.0 * excess / machined, 2),
            "green_pixels": green,
            "machined_pixels": machined,
            "in_tolerance_percentage": total,
        },
        "safety_verdict": verdict,
    }


def test_triage_accepts_nested_metrics():
    from triage_autodiff import audit

    res = audit(_nested_payload())
    assert res["verdict"] == "AUTODIFF_ACCEPTED", res
    assert res["totals"]["machined"] == 200000
    assert res["totals"]["green"] > 0


def test_triage_flags_gouge_from_nested_metrics():
    from triage_autodiff import audit

    payload = _nested_payload(gouge=5000, excess=3000, green=192000, total=96.0,
                              verdict="CRITICAL_GOUGE_DETECTED")
    res = audit(payload)
    assert res["verdict"] == "REVIEW_GOUGE"
    assert res["totals"]["red"] == 5000


def test_triage_still_rejects_empty_evidence():
    from triage_autodiff import audit

    res = audit({"status": "success", "metrics": {}})
    assert res["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert [e["code"] for e in res["escalations"]] == ["AD-EMPTY-FIELD"]


def test_triage_reports_bridge_error_as_insufficient():
    from triage_autodiff import audit

    res = audit({"status": "error", "message": "OpenCV (cv2) not installed"})
    assert res["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert [e["code"] for e in res["escalations"]] == ["AD-INSPECT-ERROR"]


def test_triage_accepts_legacy_flat_payload():
    from triage_autodiff import audit

    res = audit({
        "red_pixels": 0, "blue_pixels": 0, "green_pixels": 100000,
        "machined_pixels": 100000, "gouge_ratio": 0.0, "excess_ratio": 0.0,
        "in_tolerance_ratio": 100.0, "verdict": "PASSED",
    })
    assert res["verdict"] == "AUTODIFF_ACCEPTED"


# ---------------------------------------------------------------------------
# 5. 契约文档一致性
# ---------------------------------------------------------------------------
def _resolve_citation(token: str) -> bool:
    """把 AGENTS.md 里引用的路径解析到真实文件（支持 basename 兜底）。"""
    token = token.split("::")[0].strip()
    if not token.endswith((".py", ".json", ".md", ".yaml", ".yml")):
        return True  # 非文件引用（符号名/模式名）不参与存在性校验
    direct = os.path.join(ROOT, token.replace("/", os.sep))
    if os.path.exists(direct):
        return True
    base = os.path.basename(token)
    hits = [h for h in glob.glob(os.path.join(ROOT, "**", base), recursive=True)
            if ".venv" not in h and "00_归档" not in h and "__pycache__" not in h]
    return bool(hits)


def test_agents_md_implemented_rows_cite_existing_evidence():
    """§4 状态表凡标「已实现」者，必须给出可解析证据且文件真实存在。

    旧断言把「规划中（未实现）」写死，SWARM 四项于 2026-11-13 落地后该断言反向失真。
    改为不绑定结论、只绑定证据：结论可以随实现变化，证据链必须随时可核对。
    """
    text = open(os.path.join(ROOT, "AGENTS.md"), encoding="utf-8").read()
    rows = [ln for ln in text.splitlines()
            if ln.strip().lstrip("> ").startswith("|") and "已实现" in ln]
    assert rows, "AGENTS.md §4 状态表不应为空"

    no_evidence, broken = [], []
    for row in rows:
        cited = re.findall(r"`([^`]+)`", row)
        if not cited:
            no_evidence.append(row.strip()[:70])
        for token in cited:
            if not _resolve_citation(token):
                broken.append((row.strip()[:50], token))
    assert no_evidence == [], f"已实现行缺少证据引用: {no_evidence}"
    assert broken == [], f"证据文件不存在: {broken}"


def test_agents_md_has_no_unimplemented_claims_marked_done():
    """反向守卫：标「已实现」的行不得同时自称未实现/规划中（自相矛盾）。"""
    text = open(os.path.join(ROOT, "AGENTS.md"), encoding="utf-8").read()
    for ln in text.splitlines():
        if not ln.strip().lstrip("> ").startswith("|") or "已实现" not in ln:
            continue
        assert "规划中" not in ln and "未实现" not in ln.replace("未实现**", ""), ln.strip()[:90]


def test_declared_tools_are_all_dispatchable():
    """宣告面每个工具都必须有真实分派分支，否则模型能看到却调不通。"""
    path = os.path.join(ROOT, "bridges", "tool_calling_specs.py")
    tree = ast.parse(open(path, encoding="utf-8").read())
    declared = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                getattr(t, "id", "") == "CADCAM_TOOLS_DEFINITION" for t in node.targets):
            declared = [t["function"]["name"] for t in ast.literal_eval(node.value)]
    impl = [n for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name == "_execute_tool_call_impl"][0]
    lits = {x.value for x in ast.walk(impl) if isinstance(x, ast.Constant) and isinstance(x.value, str)}
    missing = [d for d in declared if d not in lits]
    assert missing == [], f"声明但无分派: {missing}"


def test_executable_corpus_mappings_use_real_actions():
    """语料映射若声明 executable，其 action 必须真在该工具的 action 枚举里。"""
    from bridges.tool_calling_specs import get_cadcam_tool_definitions
    from virtu_omni.knowledge.corpus_tool_map import (
        CORPUS_TOOL_NAMES,
        DISPATCH_ONLY_TOOLS,
        describe,
    )

    spec = {s["function"]["name"]: s["function"] for s in get_cadcam_tool_definitions()}
    bad = []
    for name in CORPUS_TOOL_NAMES:
        info = describe(name)
        if info["kind"] != "executable":
            continue
        tool, act = info["canonical_tool"], info.get("canonical_action") or ""
        if tool not in spec:
            if tool not in DISPATCH_ONLY_TOOLS:
                bad.append((name, "tool_missing", tool))
            continue
        enum = (spec[tool]["parameters"]["properties"].get("action") or {}).get("enum")
        if enum and act and act not in enum:
            bad.append((name, "action_not_in_enum", f"{tool}:{act}"))
        if enum and not act:
            bad.append((name, "action_missing", tool))
    assert bad == [], f"语料映射与工具能力不符: {bad}"


def test_feature_ops_all_unknown_ops_is_error_not_partial():
    """0 步成功不得自称 partial：未知 op 全失败必须如实 error。"""
    from bridges.feature_ops import feature_ops

    res = feature_ops(action="execute_plan", plan={"ops": [{"op": "fillet", "radius": 2}]},
                      workspace_root=ROOT)
    assert res["status"] == "error", res
    assert "全部 op 均失败" in (res.get("message") or "")


# ---------------------------------------------------------------------------
# 6. 语料工具名覆盖
# ---------------------------------------------------------------------------
def test_every_corpus_tool_name_is_mapped():
    from virtu_omni.knowledge.corpus_tool_map import CORPUS_TOOL_NAMES, coverage

    report = coverage(list(CORPUS_TOOL_NAMES))
    assert report["unmapped"] == []
    assert report["executable"] + report["knowledge_only"] == report["total"]
    assert report["total"] >= 60


def test_corpus_tool_targets_exist_in_runtime_surface():
    from bridges.tool_calling_specs import get_cadcam_tool_definitions
    from virtu_omni.knowledge.corpus_tool_map import (
        CORPUS_TOOL_NAMES,
        DISPATCH_ONLY_TOOLS,
        describe,
    )

    runtime = {d["function"]["name"] for d in get_cadcam_tool_definitions()}
    runtime |= set(DISPATCH_ONLY_TOOLS)  # 内部可调用入口（不进宣告面）
    bad = [
        (n, describe(n)["canonical_tool"])
        for n in CORPUS_TOOL_NAMES
        if describe(n)["kind"] == "executable"
        and describe(n)["canonical_tool"] not in runtime
    ]
    assert bad == []


def test_knowledge_only_tool_returns_honest_payload(approved):
    from bridges.tool_calling_specs import execute_tool_call

    res = execute_tool_call("solidworks.export_step", {"part_name": "x"})
    assert res["status"] == "knowledge_only"
    assert res["verdict_code"] == "TOOL_NOT_EXECUTABLE"
    assert res["input_sent"] is False


def test_mapped_corpus_tool_reaches_canonical_tool(approved):
    from bridges.tool_calling_specs import execute_tool_call

    res = execute_tool_call("knowledge.lookup_module", {"module": "solidworks"})
    assert res["status"] == "ok"
    assert res["count"] >= 1


# ---------------------------------------------------------------------------
# 7. ΔV 判词
# ---------------------------------------------------------------------------
def test_delta_v_is_computed_not_asserted():
    from virtu_omni.engine.extreme_cadcam_pipeline import ExtremeCADCAMPipeline

    pipeline = ExtremeCADCAMPipeline()
    spec = pipeline.wish_engine.parse_wish_intent(
        "精密轴承套圈外圆加工，材质Cr12MoV，外径53，孔径14，总长45，圆角3"
    )
    out_dir = os.path.join(ROOT, "runs", "pytest_delta_v")
    os.makedirs(out_dir, exist_ok=True)
    stage = pipeline.execute_modeling_stage(spec, out_dir)

    assert stage["delta_v_mm3"] > 0
    assert stage["volume_basis"].startswith("analytic_geometry")
    assert stage["cad_mass_property_verified"] is False
    assert "Verified" not in stage["volume_assertion"]
    assert "PASSED" in stage["volume_assertion"]


def test_sw_mass_properties_action_exposed():
    from bridges.tool_calling_specs import get_cadcam_tool_definitions

    spec = {
        d["function"]["name"]: d["function"] for d in get_cadcam_tool_definitions()
    }["cadcam_solidworks_model"]
    assert "mass_properties" in spec["parameters"]["properties"]["action"]["enum"]


# ---------------------------------------------------------------------------
# 8. 「吞异常后仍报成功」三处（2026-11-13 扫描命中）
# ---------------------------------------------------------------------------
def test_nc_validation_sentinel_unavailable_is_not_green(monkeypatch):
    """哨兵没跑起来时，is_valid 不得为真、status 不得是 success。"""
    import bridges.cimco_bridge as cb
    import virtu_omni.serving.gbnf_grammar as gg

    bridge = cb.CIMCOBridge()
    program = "O1000\n#100=50.0\nG01 X#100 F300\nM05\nM30\n"

    ok = bridge.validate_fanuc_macro_b(program)
    assert ok["syntax_checked"] is True
    assert ok["status"] == "success"

    def _boom(_code):
        raise RuntimeError("tokenizer unavailable")

    monkeypatch.setattr(gg, "validate_gcode_syntax", _boom)
    res = bridge.validate_fanuc_macro_b(program)
    assert res["syntax_checked"] is False
    assert res["is_valid"] is False, "没检查不许当成检查通过"
    assert res["status"] == "partial", "状态必须降级，不能仍报 success"
    assert any(e.startswith("CHECK_UNAVAILABLE:") for e in res["errors"])
    assert "tokenizer unavailable" in (res["syntax_check_error"] or "")


def test_cli_non_json_stdout_is_an_error(monkeypatch):
    """退出码 0 只代表进程没崩；stdout 不是 JSON 时不得报 success。"""
    import subprocess as sp

    from virtu_omni.agent.adaptive_router import AccessModality, AgentDispatcher

    class _Done:
        returncode = 0
        stdout = "CIMCO: program OK\n(not json)"
        stderr = ""

    monkeypatch.setattr(sp, "run", lambda *a, **k: _Done())
    dispatcher = AgentDispatcher()
    res = dispatcher._execute_under_modality(
        AccessModality.CLI, "cimco", "validate_macro", "cadcam_cimco_validate",
        "#100=1\nM30", {"code": "#100=1\nM30"})
    assert res["status"] == "error"
    assert res["verdict_code"] == "CLI_OUTPUT_NOT_JSON"
    assert "not json" in res["raw_output"]


def test_mcp_non_json_result_is_an_error(monkeypatch):
    """MCP 返回纯文本时同样不得报 success。"""
    import bridges.cadcam_mcp_server as mcp

    from virtu_omni.agent.adaptive_router import AccessModality, AgentDispatcher

    monkeypatch.setattr(mcp, "handle_request",
                        lambda call: {"result": {"content": [{"text": "OK (plain text)"}]}})
    dispatcher = AgentDispatcher()
    res = dispatcher._execute_under_modality(
        AccessModality.MCP, "solidworks", "model", "cadcam_solidworks_model",
        "建个法兰", {"wish": "建个法兰"})
    assert res["status"] == "error"
    assert res["verdict_code"] == "MCP_RESULT_NOT_JSON"
    assert "plain text" in res["text"]
