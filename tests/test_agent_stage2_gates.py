# -*- coding: utf-8 -*-
"""tests/test_agent_stage2_gates.py — 阶段二（A–F 组）可证伪验收测试。

设计原则（AGENTS.md §8.4 反证范式）：每条用例都对应审计报告的一个具体缺口，
且必须在"修复前会红、修复后会绿"的样本上跑，不允许只测成功路径。

分组：
  A 工具层三道闸      bridges/tool_calling_specs.py
  B VBA/LISP deny    bridges/code_sandbox_policy.py + 两个 bridge 入口
  C/D deep_agent     bridges/deep_agent.py（闸门 + StepDigest + 配置驱动）
  E 可观测底座        virtu_omni/agent/run_context.py
  F 记忆写入安全      virtu_omni/agent/skill_writer_and_memory.py
  G REACT 接真循环    virtu_omni/agent/super_agent.py（deep_agent 为引擎）
"""

import json
import os
import sys
import tempfile
import threading
import time

import pytest

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)


# ===========================================================================
# A 组：工具层三道闸（jsonschema / 路径白名单 / 有界等待 / arg_remap 回显）
# ===========================================================================
from bridges import tool_calling_specs as T  # noqa: E402


@pytest.fixture()
def clean_gate_env(monkeypatch):
    """隔离审批与 schema 模式，避免本机审批文件/环境变量影响判定。"""
    monkeypatch.delenv("VIRTU_TOOL_SCHEMA_MODE", raising=False)
    monkeypatch.delenv(T.TOOL_APPROVAL_ENV, raising=False)
    monkeypatch.delenv(T.TOOL_APPROVAL_TOKEN_ENV, raising=False)
    monkeypatch.setattr(T, "_approval_file_path",
                        lambda: os.path.join(tempfile.gettempdir(), "virtu_no_approval_stage2.json"))
    yield


def test_a1_schema_required_missing_is_rejected(clean_gate_env):
    """缺失 required（query）必须报错，而不是静默落默认值继续执行。"""
    res = T.execute_tool_call("cadcam_web_search", {})
    assert res.get("status") == "invalid_arguments"
    assert res.get("verdict_code") == "TOOL_SCHEMA_VIOLATION"
    assert "query" in json.dumps(res, ensure_ascii=False)


def test_a2_schema_enum_violation_is_rejected(clean_gate_env):
    """action 枚举外的值必须被拒（原实现会透传到 bridge）。"""
    res = T.execute_tool_call("cadcam_solidworks_model", {"action": "rm_rf"})
    assert res.get("status") == "invalid_arguments"
    assert "action" in json.dumps(res, ensure_ascii=False)


def test_a3_schema_type_mismatch_is_rejected(clean_gate_env):
    res = T.execute_tool_call("cadcam_web_search", {"query": "virtu", "num_results": "many"})
    assert res.get("status") == "invalid_arguments"
    assert "num_results" in json.dumps(res, ensure_ascii=False)


def test_a4_legacy_alias_remap_is_echoed(clean_gate_env):
    """legacy 别名不再静默重组：返回体必须回显 arg_remap（from/to/参数键）。"""
    res = T.execute_tool_call("solidworks.create_parametric_part",
                              {"part_name": "bushing", "spec": {"d": 60}})
    remap = res.get("arg_remap") or {}
    assert remap.get("from") == "solidworks.create_parametric_part"
    assert remap.get("to") == "cadcam_solidworks_model"
    assert "vba_code" in (remap.get("arg_keys_out") or [])
    # 写盘类工具默认无审批 => 必须拦在 bridge 构造之前
    assert res.get("status") == "blocked"
    assert res.get("verdict_code") == "TOOL_APPROVAL_REQUIRED"


def test_a5_tool_call_is_bounded_by_timeout(monkeypatch, clean_gate_env):
    """统一超时闸门：慢实现必须被有界等待掐断，返回 TOOL_TIMEOUT 而非无界等待。"""
    monkeypatch.setenv("VIRTU_TOOL_TIMEOUT_S", "0.2")
    monkeypatch.setenv("VIRTU_TOOL_RETRIES", "0")

    def _slow(tool_name, args, diag=None):
        time.sleep(2.0)
        return {"status": "ok"}

    monkeypatch.setattr(T, "_execute_tool_call_impl", _slow)
    t0 = time.time()
    res = T.execute_tool_call("cadcam_web_search", {"query": "virtu"})
    elapsed = time.time() - t0
    assert res.get("verdict_code") == "TOOL_TIMEOUT"
    assert elapsed < 1.5, f"超时闸门未生效，耗时 {elapsed:.2f}s"


def test_a6_path_traversal_blocked_at_tool_layer(clean_gate_env):
    """路径参数必须 abspath + 白名单：越界必须在 execute_tool_call 就被拦。"""
    res = T.execute_tool_call("cadcam_cimco_validate",
                              {"action": "launch", "nc_file_path": "C:/Windows/x.nc"})
    assert res.get("status") == "blocked"
    assert res.get("verdict_code") == "PATH_TRAVERSAL_BLOCKED"


# ===========================================================================
# B 组：VBA / AutoLISP deny-by-default
# ===========================================================================
from bridges import code_sandbox_policy as P  # noqa: E402

WINEXEC_SAMPLE = 'Private Declare PtrSafe Function WinExec Lib "kernel32" (ByVal lpCmdLine As String, ByVal nCmdShow As Long) As Long'


def test_b1_vba_freeform_is_denied_by_default():
    """自由文本 VBA 默认拒绝（原黑名单实现会放行任何不含黑名单词的代码）。"""
    res = P.validate_code("vba", 'Dim x As Integer\nx = 1\nDebug.Print x\n')
    assert res is not None
    assert res["status"] == "blocked"
    assert res["verdict_code"] == "VBA_FREEFORM_DISABLED"
    assert res["policy"] == "deny_by_default"


def test_b2_winexec_declare_sample_is_blocked():
    """审计报告点名的反证样本：Declare PtrSafe Function WinExec 必须 blocked。"""
    res = P.validate_code("vba", WINEXEC_SAMPLE)
    assert res is not None and res["status"] == "blocked"
    assert res["verdict_code"] == "VBA_DENY_LIST_VIOLATION"
    assert res["rule"]
    # 硬禁与自由文本开关无关：即使显式开出自由执行也必须被拦
    res2 = P.validate_code("vba", WINEXEC_SAMPLE, allow_freeform=True)
    assert res2 is not None and res2["status"] == "blocked"


def test_b3_autolisp_startapp_is_blocked():
    res = P.validate_code("lisp", '(startapp "cmd.exe")')
    assert res is not None and res["status"] == "blocked"
    assert res["verdict_code"] == "LISP_DENY_LIST_VIOLATION"


def test_b4_bridge_entrypoints_return_blocked():
    """两个对外入口必须把 deny 结果原样返回，不能继续落盘/执行。"""
    from bridges.solidworks_bridge import SolidWorksBridge
    from bridges.autocad_bridge import AutoCADBridge

    class _Dummy:  # 只走到策略判定就返回，不触碰任何 COM 对象
        sw = None

    sw_res = SolidWorksBridge.execute_vba_code(_Dummy(), WINEXEC_SAMPLE)
    assert sw_res.get("status") == "blocked"

    cad_res = AutoCADBridge.send_lisp_command(_Dummy(), '(startapp "cmd.exe")')
    assert cad_res.get("status") == "blocked"


def test_b5_orchestrator_does_not_bypass_lisp_deny(monkeypatch):
    """编排层不得绕过 deny-by-default。

    回归点：six_software_orchestrator 的 autocad/send_lisp 分支曾写死
    ``allow_freeform=params.get("allow_freeform", True)``，使工具层的
    deny-by-default 在编排入口被整体旁路。此处要求默认参数下必须返回 blocked。
    """
    from bridges.autocad_bridge import AutoCADBridge
    from bridges.six_software_orchestrator import SixSoftwareOrchestrator

    calls = {}

    def _spy(self, code, allow_freeform=None):
        calls["allow_freeform"] = allow_freeform
        return {"status": "spy"}

    monkeypatch.setattr(AutoCADBridge, "send_lisp_command", _spy)
    orch = SixSoftwareOrchestrator.__new__(SixSoftwareOrchestrator)
    orch.cad = AutoCADBridge.__new__(AutoCADBridge)
    orch.dispatch("autocad", "send_lisp", {"code": '(command "_.CIRCLE" "0,0" "10")'})

    # 关键断言：不显式传参时不得替调用方打开 freeform，必须交给策略默认（拒绝）
    assert calls.get("allow_freeform") is None


# ===========================================================================
# C/D 组：deep_agent 闸门 + 结构化上下文压缩
# ===========================================================================
from bridges import deep_agent as D  # noqa: E402


def _schemas(*names):
    return [{"name": n, "description": n,
             "inputSchema": {"type": "object",
                             "properties": {"mode": {"type": "string"}},
                             "required": []}}
            for n in names]


class _PlanStub:
    """替换 plan_stage：不联网，直接返回构造好的计划。"""

    def __init__(self, steps, criteria=None):
        self.steps = steps
        self.criteria = criteria or ["观察输出中出现期望的实测关键字"]

    def __call__(self, *a, **kw):
        plan = {"analysis": "stub", "goal": "验证 deep_agent 闸门",
                "success_criteria": self.criteria, "steps": self.steps}
        return {"stage": "plan", "used": "model", "plan": plan,
                "violations": D.validate_plan(plan, _schemas(*sorted({s["tool"] for s in self.steps}))),
                "valid": True, "elapsed_s": 0.0}


class _Adapter:
    """最小 tool_adapter：schema 固定，call 返回可控观察。"""

    def __init__(self, text="observed value 42", is_error=False):
        self._text = text
        self._is_error = is_error
        self.calls = []

    def schemas(self):
        return _schemas("Probe")

    def call(self, name, args):
        self.calls.append({"tool": name, "args": args})
        return {"is_error": self._is_error, "text": self._text, "impl": "stub"}

    def restore(self):
        return True


def _run_stub(monkeypatch, steps, adapter, criteria=None):
    monkeypatch.setattr(D, "plan_stage", _PlanStub(steps, criteria))
    monkeypatch.setattr(D, "verify_stage", lambda *a, **kw: {"items": []})
    return D.run(task="stage2-gate-test", model="stub-model",
                 tool_adapter=adapter, run_ctx=None)


def _step(i, tool="Probe", args=None):
    return {"id": i, "intent": f"第{i}步取证", "tool": tool,
            "args": args or {"probe": f"p{i}"},
            "expect": "observed value 42"}


def test_c1_duplicate_action_is_blocked(monkeypatch):
    """同一工具+同一参数重复调用必须被 duplicate_action 拦截。"""
    steps = [_step(1, args={"probe": "same"}), _step(2, args={"probe": "same"})]
    trace = _run_stub(monkeypatch, steps, _Adapter())
    guards = [g["guard"] for g in trace["guards"]]
    assert "duplicate_action" in guards
    assert trace["metrics"]["blocked_duplicates"] == 1
    assert trace["metrics"]["executed_calls"] == 1


def test_c2_consecutive_failures_trip_circuit_breaker(monkeypatch):
    """连续失败必须熔断并给出 aborted 原因（原实现只累加计数不熔断）。"""
    steps = [_step(i, args={"probe": f"x{i}"}) for i in (1, 2, 3, 4)]

    class _Failing(_Adapter):
        def call(self, name, args):
            self.calls.append({"tool": name, "args": args})
            return {"is_error": True, "text": "boom", "impl": "stub"}

    trace = _run_stub(monkeypatch, steps, _Failing())
    assert trace.get("aborted") == "circuit_breaker_3_consecutive_failures"
    assert trace["success"] is False
    assert trace["metrics"]["executed_calls"] < len(steps)


def test_c3_plan_over_max_steps_is_invalid():
    """计划超步数必须判非法（而不是默默截断后继续跑）。"""
    steps = [_step(i, args={"probe": f"n{i}"}) for i in range(1, D.cfg("max_steps") + 2)]
    violations = D.validate_plan({"goal": "g", "success_criteria": ["c1 足够长的具体标准"],
                                  "steps": steps},
                                 _schemas("Probe"))
    assert any("超过上限" in v for v in violations)


def test_c4_skip_if_resumes_from_cached_plan(monkeypatch):
    """断点续跑：skip_if 命中上一步观察时跳过该步并留痕。"""
    steps = [
        {"id": 1, "intent": "第一步取证", "tool": "Probe", "args": {"probe": "a"},
         "expect": "observed value 42"},
        {"id": 2, "intent": "第二步取证", "tool": "Probe", "args": {"probe": "b"},
         "expect": "observed value 42", "skip_if": {"step": 1, "contains": "observed"}},
    ]
    trace = _run_stub(monkeypatch, steps, _Adapter())
    skipped = [s for s in trace["steps"] if s.get("skipped")]
    assert skipped and "skip_if" in skipped[0]["why"]
    assert trace["metrics"]["executed_calls"] == 1


def _write_schemas():
    return [{"name": "Process", "description": "p",
             "inputSchema": {"type": "object",
                             "properties": {"mode": {"type": "string", "enum": ["list", "kill"]}},
                             "required": ["mode"]}}]


class _WriteAdapter(_Adapter):
    """带写操作 schema 的适配器：Process.mode=kill 属写操作。"""

    def schemas(self):
        return _write_schemas()

    def call(self, name, args):
        self.calls.append({"tool": name, "args": args})
        return {"is_error": False, "text": "observed value 42 / kill done", "impl": "stub"}


def test_c5_first_step_write_is_blocked(monkeypatch):
    """反证：计划首步直接写（无任何先验观察）必须被 unplanned_write 拦截。

    原判据 planned_write 把当前 step 自身也算进"计划内写操作"，恒为真，
    导致该闸门在运行期不可达 —— 首步 Process.kill 会被直接执行。
    """
    steps = [{"id": 1, "intent": "直接杀进程", "tool": "Process",
              "args": {"mode": "kill"}, "expect": "observed value 42"}]
    trace = _run_stub(monkeypatch, steps, _WriteAdapter())
    assert trace["metrics"]["blocked_unplanned_writes"] == 1
    assert trace["metrics"]["executed_calls"] == 0
    assert trace["steps"][0]["outcome"] == "blocked_write_not_in_plan"


def test_c6_observe_then_write_is_allowed(monkeypatch):
    """正向对照：先观察再写（Process.list -> Process.kill）不得被误拦。"""
    steps = [
        {"id": 1, "intent": "先看进程现状", "tool": "Process",
         "args": {"mode": "list"}, "expect": "observed value 42"},
        {"id": 2, "intent": "再结束目标进程", "tool": "Process",
         "args": {"mode": "kill"}, "expect": "observed value 42"},
    ]
    trace = _run_stub(monkeypatch, steps, _WriteAdapter())
    assert trace["metrics"]["blocked_unplanned_writes"] == 0
    assert trace["metrics"]["executed_calls"] == 2


def test_d1_mechanical_check_rejects_generic_words():
    """反证：expect 只含 fail/error/process 这类通用词时必须 not_met（原实现命中即 met）。"""
    history = [{"step": 1, "observation": "process window error: failed to open process\nall good"}]
    step = {"id": 2, "expect": "确认 process 与 error 都已 fail 处理完毕"}
    chk = D.mechanical_check(step, history)
    assert chk["verdict"] == "not_met"
    assert "不可证伪" in chk.get("reason", "") or "未同句共现" in chk.get("reason", "")


def test_d2_step_digest_keeps_tail_and_key_lines():
    """上下文结构化压缩：长输出必须保留 obs_tail 与命中 expect 的关键行，而非硬截断。"""
    long_obs = "\n".join([f"line {i}: filler text without keywords" for i in range(60)])
    long_obs += "\nHWND 0x00120A3C title=DeepSeek window app_id=chrome.exe pid=8842\n"
    digest = D.make_step_digest({"id": 1, "intent": "枚举窗口", "tool": "Probe",
                                 "args": {"probe": "w"},
                                 "expect": "HWND DeepSeek chrome.exe pid"},
                                long_obs, {"judge": {"verdict": "met"}})
    for key in ("step", "goal", "tool", "args_digest", "obs_head", "obs_tail",
                "key_lines", "verdict"):
        assert key in digest
    assert "pid=8842" in digest["obs_tail"]
    assert any("HWND" in ln for ln in digest["key_lines"])
    assert digest["obs_chars"] == len(long_obs)


def test_d3_num_ctx_and_predict_are_config_driven(monkeypatch):
    """num_ctx / num_predict 必须由配置驱动，而不是硬编码在 chat() 里。"""
    monkeypatch.setenv("VIRTU_DEEP_NUM_CTX", "8192")
    monkeypatch.setenv("VIRTU_DEEP_NUM_PREDICT_VERIFY", "777")
    cfg = D.configure({"num_ctx": 8192})
    assert int(cfg["num_ctx"]) == 8192
    assert int(D.cfg("num_predict_verify")) == 777
    D.configure({"num_ctx": D.AGENT_CONFIG.get("num_ctx", 4096)})


# ===========================================================================
# E 组：可观测底座 RunContext
# ===========================================================================
from virtu_omni.agent.run_context import RunContext, content_fingerprint, ensure_ctx  # noqa: E402


def test_e1_run_id_is_content_fingerprint_not_time_based():
    a = content_fingerprint("same-task", "model-x")
    b = content_fingerprint("same-task", "model-x")
    c = content_fingerprint("other-task", "model-x")
    assert a == b and a != c


def test_e2_run_context_carries_parent_span_and_step():
    root = RunContext.root("task", "REACT")
    plan_span = root.child("plan")
    step_span = plan_span.with_step(3)
    assert step_span.run_id == root.run_id
    assert plan_span.parent_span == root.span
    assert step_span.span == plan_span.span          # 同 span 换步号，不新开一层
    assert step_span.parent_span == plan_span.parent_span
    assert step_span.step == 3
    fields = step_span.fields()
    for key in ("run_id", "span", "parent_span", "step", "pid"):
        assert key in fields
    assert ensure_ctx(step_span, "x").run_id == root.run_id


def test_e3_structured_log_line_has_required_fields(caplog):
    ctx = RunContext.root("task-log", "REACT")
    with caplog.at_level("INFO"):
        ctx.child("act").log("step_executed", step=1, duration_ms=12.5)
    text = caplog.text
    assert "span=root/act" in text
    for token in ("run_id=", "stage=step_executed", "step=1", "duration_ms=12.5", "pid="):
        assert token in text, f"结构化日志缺少字段 {token}"


# ===========================================================================
# F 组：记忆写入安全（去硬编码 + 追加 WAL + 原子替换 + 文件锁）
# ===========================================================================
from virtu_omni.agent import skill_writer_and_memory as M  # noqa: E402


def test_f1_memory_path_is_env_overridable(tmp_path, monkeypatch):
    target = tmp_path / "mem" / "kb.json"
    monkeypatch.setenv("VIRTU_MEMORY_PATH", str(target))
    assert os.path.abspath(M.resolve_memory_path(None)) == os.path.abspath(str(target))
    # 显式入参优先
    assert os.path.abspath(M.resolve_memory_path(str(tmp_path / "x.json"))) == \
        os.path.abspath(str(tmp_path / "x.json"))


def test_f2_atomic_write_leaves_no_temp_file(tmp_path, monkeypatch):
    mem = tmp_path / "kb.json"
    writer = M.SkillWriterAndMemory(memory_path=str(mem),
                                    skills_root=str(tmp_path / "skills"), embedding_dim=16)
    writer.commit_experience("sig-atomic", "问题", "方案", ["规则"])
    data = json.loads(mem.read_text(encoding="utf-8"))
    assert data["patterns"]
    leftovers = [p.name for p in tmp_path.iterdir() if p.name.startswith(".memory_")]
    assert not leftovers, f"原子写入残留临时文件: {leftovers}"


def test_f3_concurrent_commits_do_not_lose_writes(tmp_path):
    """反证：两个实例并发 commit，两条记录都必须存在（原实现后写者覆盖前者）。"""
    mem = tmp_path / "kb.json"
    a = M.SkillWriterAndMemory(memory_path=str(mem), skills_root=str(tmp_path / "s"), embedding_dim=16)
    b = M.SkillWriterAndMemory(memory_path=str(mem), skills_root=str(tmp_path / "s"), embedding_dim=16)

    errors = []

    def _commit(writer, sig):
        try:
            writer.commit_experience(sig, "并发问题", "并发方案", ["并发规则"])
        except Exception as err:  # noqa: BLE001
            errors.append(err)

    t1 = threading.Thread(target=_commit, args=(a, "sig-concurrent-A"))
    t2 = threading.Thread(target=_commit, args=(b, "sig-concurrent-B"))
    t1.start()
    t2.start()
    t1.join(60)
    t2.join(60)

    assert not errors, f"并发 commit 抛错: {errors}"
    data = json.loads(mem.read_text(encoding="utf-8"))
    sigs = {p.get("task_signature") for p in data["patterns"]}
    assert {"sig-concurrent-A", "sig-concurrent-B"} <= sigs, f"并发丢写: {sigs}"


# ===========================================================================
# G 组：REACT 接真循环（deep_agent 为执行引擎，旧流水线仅 fallback）
# ===========================================================================
def test_g1_react_uses_deep_agent_engine(monkeypatch):
    from virtu_omni.agent.super_agent import VirtuSuperAgent

    captured = {}

    def _fake_run(**kwargs):
        captured.update(kwargs)
        return {"task": kwargs.get("task"), "success": False, "plan_valid": True,
                "guards": [], "steps": [], "criteria_met": 0, "criteria_total": 1,
                "history": [{"step": 1, "tool": "facet_parse_intent",
                             "args": {"prompt": "x"},
                             "observation": "parsed intent: bushing, d=60"}],
                "digests": {1: {"step": 1, "goal": "解析意图",
                                "tool": "facet_parse_intent",
                                "args_digest": "{}", "obs_head": "parsed intent: bushing, d=60",
                                "obs_tail": "", "obs_chars": 30,
                                "key_lines": ["parsed intent: bushing, d=60"],
                                "verdict": "met"}},
                "verify": {"items": [{"met": "no"}]},
                "metrics": {"executed_calls": 1},
                "run_context": {"run_id": "deadbeef", "span": "s", "parent_span": None,
                                "step": 0, "pid": os.getpid()},
                "tool_source": "injected-adapter"}

    monkeypatch.setattr(D, "run", _fake_run)
    agent = VirtuSuperAgent()
    res = agent._solve_react("造一根连杆衬套", max_steps=4)

    assert res.mode == "REACT"
    assert res.metrics["engine"] == "deep_agent"
    assert captured.get("tool_adapter") is not None, "REACT 必须把 facet 以 tool_adapter 注入 deep_agent"
    assert captured.get("config", {}).get("max_steps") == 4
    assert res.trace_log and res.trace_log[0]["thought"] == "解析意图"
    assert res.trace_log[0]["observation"]
    assert res.metrics["react_steps"] == 1
    assert res.metrics["verification_basis"] == "deep_agent_verify_stage_criteria"


def test_g2_react_falls_back_only_with_visible_reason(monkeypatch):
    """引擎异常时必须降级且把原因写进 metrics（不静默假装成功）。"""
    from virtu_omni.agent.super_agent import VirtuSuperAgent

    def _boom(**kwargs):
        raise RuntimeError("engine down")

    monkeypatch.setattr(D, "run", _boom)
    agent = VirtuSuperAgent()
    res = agent._solve_react("造一根连杆衬套", max_steps=2)
    assert res.metrics.get("engine") == "pipeline_fallback"
    assert "engine down" in str(res.metrics.get("engine_fallback_reason"))


# ===========================================================================
# A 组补齐：路径白名单闸门 + VIRTU_ALLOWED_ROOTS 扩展位
# ===========================================================================
class _OrchStub:
    def dispatch(self, *a, **kw):
        return {"status": "ok", "stub": True}


def _path_gate_call(monkeypatch, script_path):
    from bridges import tool_calling_specs as T

    monkeypatch.setattr(T, "get_orchestrator", lambda: _OrchStub())
    return T.execute_tool_call(
        "cadcam_autocad_draw",
        {"action": "send_lisp", "code": '(command "_.CIRCLE" "0,0" "10")',
         "script_path": str(script_path)},
    )


def test_a8_allowed_roots_field_is_echoed(monkeypatch):
    """工作区外路径必须被判 PATH_TRAVERSAL_BLOCKED，并回显允许根便于诊断。"""
    monkeypatch.setenv("VIRTU_TOOL_APPROVAL", "1")
    monkeypatch.delenv("VIRTU_ALLOWED_ROOTS", raising=False)
    res = _path_gate_call(monkeypatch, r"C:\Windows\System32\drivers\etc\hosts")
    assert res.get("verdict_code") == "PATH_TRAVERSAL_BLOCKED"
    assert res.get("allowed_roots")


def test_a7_env_allowed_roots_extends_whitelist(monkeypatch):
    """VIRTU_ALLOWED_ROOTS 指定的根必须被放行（该扩展位此前只在文档里存在）。

    注意：pyproject.toml 里 --basetemp=.pytest_tmp_fix 会让 tmp_path 落在工作区内，
    用它做对照组会失效；这里显式用系统 temp 下的目录，确保路径确实在工作区外。
    """
    import tempfile

    monkeypatch.setenv("VIRTU_TOOL_APPROVAL", "1")
    ext_root = tempfile.mkdtemp(prefix="virtu_stage2_ext_")
    target = os.path.join(ext_root, "ext.lsp")
    with open(target, "w", encoding="utf-8") as fh:
        fh.write("(princ)")

    monkeypatch.delenv("VIRTU_ALLOWED_ROOTS", raising=False)
    assert _path_gate_call(monkeypatch, target).get("verdict_code") == "PATH_TRAVERSAL_BLOCKED"

    monkeypatch.setenv("VIRTU_ALLOWED_ROOTS", ext_root)
    assert _path_gate_call(monkeypatch, target).get("verdict_code") != "PATH_TRAVERSAL_BLOCKED"
