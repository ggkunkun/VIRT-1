# -*- coding: utf-8 -*-
"""agent_chain_executor 的取证门控测试。

重点锁两类曾经真实发生过的假象：
  1) 把自己写的日志当成仿真产物 → 判成 executed；
  2) 宏/软件返回 0 但没有任何产物 → 判成 executed。
"""

import json
import os
import sys
import time
import types
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agent_chain_executor as ace  # noqa: E402

VERICUT_STDOUT = (
    "错误:在 17 行:G28 U0.0 W0.0,\"Spindle\"和\"Turret\"碰撞.\n"
    "错误:在 44 行:G28 U0.0 W0.0,刀\"2\" 与 \"Stock\" 碰撞，碰撞体积 103453.3141\n"
    "错误:字符 \"G90  - Absolute dimensioning mode\" 未定义.  此行其余内容被忽略.\n"
)


def test_gcode_envelope_counts_real_motion_blocks():
    nc = ("O2026\n"
          "#101 = 45.00\n"
          "G21 G40 G97 G99\n"
          "G00 X[#101] Z2.0\n"
          "G71 U2.0 R0.8\n"
          "G01 Z-40.0 F0.15\n"
          "G70 P100 Q110\n"
          "M30\n")
    env = ace._gcode_envelope(nc)
    assert env["motion_blocks"] == 4
    assert env["macro_variables"] == 1
    assert env["has_rough_cycle"] and env["has_finish_cycle"] and env["has_end"]
    assert env["z_range"] == [-40.0, 2.0]
    assert env["x_range"] == [45.0, 45.0]      # X 写的是直径变量 #101


def _stub_run(payload_stdout, rc=0):
    def fake(cmd, *a, **kw):
        return types.SimpleNamespace(returncode=rc, stdout=payload_stdout.encode("gbk"),
                                     stderr=b"")
    return fake


def test_vericut_not_fooled_by_own_log(tmp_path, monkeypatch):
    out = str(tmp_path)
    proj = os.path.join(out, "p.vcproject")
    open(proj, "w").write("dummy")
    monkeypatch.setattr(ace, "_vericut_batch_run",
                        lambda bat, p, o, timeout=420, **kw: (0, VERICUT_STDOUT, os.path.join(o, "log")))
    # The 180 s background-log watch is unrelated to this verdict; stub it so the
    # suite does not sleep through the whole budget on every run.
    monkeypatch.setattr(ace, "_watch_vericut_simlog", lambda *a, **k: ("", {}))
    rep = ace.stage_vericut(proj, out, gui=False)
    assert rep["status"] == "executed"
    assert rep["metrics"]["collision_events"] == 2
    assert rep["metrics"]["max_collision_volume_mm3"] == 103453.3141
    assert rep["metrics"]["collision_nc_lines"] == [17, 44]
    assert rep["metrics"]["nc_parse_errors"] == 1


def test_vericut_silent_run_is_blocked_not_executed(tmp_path, monkeypatch):
    """只初始化引擎、没有任何仿真事件 → 必须判 blocked（曾经这里被自家日志骗成 executed）。"""
    out = str(tmp_path)
    proj = os.path.join(out, "p.vcproject")
    open(proj, "w").write("dummy")
    monkeypatch.setattr(ace, "_vericut_batch_run",
                        lambda bat, p, o, timeout=420, **kw: (
                            0, "NUMBER OF HARDWARE THREADS AVAILABLE: 12\nOpenGL Loaded\n",
                            os.path.join(o, "log")))
    # The production fallback watches up to 180 s for a background summary log.
    # This case is about the silent-batch verdict, not that wait: stub the watcher
    # so the assertion runs immediately instead of sleeping through the budget.
    monkeypatch.setattr(ace, "_watch_vericut_simlog", lambda *a, **k: ("", {}))
    rep = ace.stage_vericut(proj, out, gui=False)
    # 装载即待命：不能判 executed；由自研解析器承担静态校验 → substituted，且必须写清根因
    assert rep["status"] == "substituted"
    assert rep["metrics"]["collision_events"] == 0
    assert rep["error"] and "training_sessions" in " ".join(rep["notes"])


def _install_fake_nx_exe(tmp_path, monkeypatch):
    """让存在性门放行：这些测试验证的是「回读判定逻辑」，不是 NX 是否安装。

    本机 run_journal.exe 不在硬编码 E: 路径上；若不绕过存在性门，stage_nx 会
    提前返回 run_journal.exe not found，subprocess.run 桩根本不被调用，
    测试就退化成「检测 NX 装没装」而非「检测取证门」。
    """
    exe = tmp_path / "run_journal.exe"
    exe.write_bytes(b"")
    monkeypatch.setattr(ace, "NX_RUN_JOURNAL", str(exe))


def test_nx_requires_journal_result_file(tmp_path, monkeypatch):
    out = str(tmp_path)
    _install_fake_nx_exe(tmp_path, monkeypatch)
    monkeypatch.setattr(ace.subprocess, "run", _stub_run("Execution was successful."))
    rep = ace.stage_nx({"d_outer": 53.0, "d_inner": 14.0, "overall_len": 45.0}, out)
    assert rep["status"] == "blocked"          # RC=0 但没有回读文件
    assert "结果文件" in rep["error"]


def test_nx_reads_back_measured_geometry(tmp_path, monkeypatch):
    out = str(tmp_path)
    _install_fake_nx_exe(tmp_path, monkeypatch)

    def fake(cmd, *a, **kw):
        json.dump({"status": "OK", "feature_count": 2, "part_exists": True,
                   "part_bytes": 121821, "body_tag": 33303,
                   "bbox_raw": "[-26.5, -26.5, -45.0, 26.5, 26.5, 0.0]"},
                  open(os.path.join(out, "stage02_nx.json"), "w"))
        return types.SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(ace.subprocess, "run", fake)
    rep = ace.stage_nx({"d_outer": 53.0, "d_inner": 14.0, "overall_len": 45.0}, out)
    assert rep["status"] == "executed"
    assert rep["metrics"]["part_bytes"] == 121821
    assert "-45.0" in rep["metrics"]["bbox_raw"]


def test_nx_missing_executable_fails_closed(tmp_path, monkeypatch):
    """反证：run_journal.exe 不存在 ⇒ 必须 blocked 且绝不调用 subprocess（fail-closed）。

    若有人删掉存在性门，本用例会因 calls 非空 / status 变 executed 而翻红。
    """
    out = str(tmp_path)
    monkeypatch.setattr(ace, "NX_RUN_JOURNAL", str(tmp_path / "absent.exe"))
    calls = []

    def spy(cmd, *a, **kw):
        calls.append(cmd)
        return types.SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(ace.subprocess, "run", spy)
    rep = ace.stage_nx({"d_outer": 53.0, "d_inner": 14.0, "overall_len": 45.0}, out)
    assert rep["status"] == "blocked"
    assert "not found" in rep["error"]
    assert calls == []          # 门禁必须在派发 subprocess 之前拦截


def test_sw_verdict_needs_volume_within_analytic_band(tmp_path, monkeypatch):
    out = str(tmp_path)

    class FakeApp:
        Visible = True
        RevisionNumber = "29.5.0.0070"   # 版本门：夹具必须声明真实版本，否则 stage_sw 直接 blocked

        def RunMacro2(self, *a):
            m = os.path.join(out, "stage01_sw_metrics.txt")
            # 用 VBA 报告文件的口径喂：体积对得上 → executed
            open(m, "w", encoding="gbk").write(
                "DOC=零件1\r\nPLANE=前视基准面\r\nSKETCH=草图1\r\nSEL_SKETCH=True\r\n"
                "BOSS=凸台-拉伸1\r\nVOLUME_M3=9.9278254E-05\r\nAREA_M2=1.19050653E-02\r\n"
                "STEP_EXISTS=True\r\nSTEP_BYTES=11844\r\n")
            return (True, 0)

    monkeypatch.setattr(ace, "ensure_process", lambda *a, **kw: {"attached": True, "pid": 1})
    import win32com.client as w32c
    monkeypatch.setattr(w32c, "GetActiveObject", lambda progid: FakeApp())
    rep = ace.stage_sw({"d_outer": 53.0, "d_inner": 14.0, "overall_len": 45.0}, out)
    assert rep["status"] == "executed"
    assert rep["metrics"]["volume_deviation_pct"] < 1.0

    # 空零件（体积 0）必须判 blocked
    class EmptyApp(FakeApp):
        def RunMacro2(self, *a):
            open(os.path.join(out, "stage01_sw_metrics.txt"), "w", encoding="gbk").write(
                "DOC=零件2\r\nVOLUME_M3=0\r\nAREA_M2=0\r\nSTEP_BYTES=4503\r\n")
            return (True, 0)

    monkeypatch.setattr(w32c, "GetActiveObject", lambda progid: EmptyApp())
    rep2 = ace.stage_sw({"d_outer": 53.0, "d_inner": 14.0, "overall_len": 45.0}, out)
    assert rep2["status"] == "blocked"


def test_cimco_title_match_accepts_relative_but_not_stale_doc():
    nc = r"D:\Virtu模型\runs\full_chain\RUN_A\04_CIMCO_Edit_2026.nc"
    # 全路径 / 相对路径都要认
    assert ace._cimco_title_matches(
        "CIMCO Edit 2026.01.02 - [D:\\Virtu模型\\runs\\full_chain\\RUN_A\\04_CIMCO_Edit_2026.nc]", nc)
    assert ace._cimco_title_matches(
        "CIMCO Edit 2026.01.02 - [runs/full_chain/RUN_A/04_CIMCO_Edit_2026.nc]", nc)
    # 另一个运行包里的同名旧文档不能算通过
    assert not ace._cimco_title_matches(
        "CIMCO Edit 2026 - [D:\\other\\RUN_B\\04_CIMCO_Edit_2026.nc]", nc)
    assert not ace._cimco_title_matches("CIMCO Edit 2026", nc)


def test_wtext_does_not_hang_on_unresponsive_window():
    # 0 是非法句柄：必须立刻返回而不是阻塞
    t0 = time.time()
    out = ace._wtext(0)
    assert time.time() - t0 < 2.0
    assert isinstance(out, str)


def test_report_matrix_marks_each_tier():
    bundle = {"run_id": "t", "wish": "w", "spec": {"d_outer": 53.0, "d_inner": 14.0,
                "overall_len": 45.0, "material": "Cr12MoV"}, "executed_count": 1,
        "out_dir": ".", "report": "",
        "stages": {
            "solidworks": ace._evidence("solidworks", "executed", "COM", metrics={"volume_mm3": 1.0}),
            "nx": ace._evidence("nx", "blocked", "journal", error="模板不存在"),
            "autocad": ace._evidence("autocad", "executed", "COM", metrics={"entity_count": 6}),
            "cimco": ace._evidence("cimco", "substituted", "解析器"),
            "vericut": ace._evidence("vericut", "executed", "batch", metrics={"collision_events": 14}),
            "sscnc": ace._evidence("sscnc", "blocked", "WM_COMMAND", error="模式前置未满足"),
        }}
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        bundle["out_dir"] = d
        path = ace.write_report(bundle)
        txt = open(path, encoding="utf-8").read()
    assert "✅ 已实测执行" in txt and "⛔ 被具体根因挡住" in txt and "自研确定性替代" in txt
    assert "根因" in txt          # blocked 必须带根因行
    assert "判决口径" in txt


def test_run_child_surfaces_broken_worker_without_raising():
    """子进程 harness 自己坏掉时也必须交回结构化结果，而不是把整条链带崩。"""
    d = os.path.join(os.path.dirname(os.path.abspath(ace.__file__)), "scratch", "acp", "t_child1")
    os.makedirs(d, exist_ok=True)
    r = ace._run_child("_no_such_worker_xyz", {"a": 1}, 60, d, name="plumbing")
    assert r["data"] is None
    assert r["timed_out"] is False
    assert r["rc"] not in (0, None)


def test_run_child_parent_returns_within_budget():
    """真·看门狗语义：worker 里跑的是会挂的 AutoCAD COM，主进程必须在预算内返回。
    环境相关（有无 acad），所以只断言「有界 + 有结构」，不断言具体判决。"""
    d = os.path.join(os.path.dirname(os.path.abspath(ace.__file__)), "scratch", "acp", "t_child2")
    os.makedirs(d, exist_ok=True)
    t0 = time.time()
    r = ace._run_child("_acad_com_worker",
                       {"lsp": os.path.join(d, "none.lsp"),
                        "marker": os.path.join(d, "none.txt"),
                        "dwg": None, "deadline_s": 60},
                       6, d, name="watchdog")
    # 看门狗的判决口径：主进程必须在预算内拿回控制权，不管对端挂不挂
    assert time.time() - t0 < 40
    assert set(["data", "rc", "timed_out", "elapsed_s"]) <= set(r)


def test_cimco_match_ignores_stale_first_frame():
    """上一次运行留下的编辑器窗口排在 frames[0]，本次的文档在第二个窗口——必须仍能认出已载入。"""
    nc = r"D:\Virtu模型\runs\full_chain\20261030_199901\04_CIMCO_Edit_2026.nc"
    state = {"frame_title": r"CIMCO Edit 2026.01.02 - [runs\full_chain\20261030_184009\04_CIMCO_Edit_2026.nc]",
             "frame_titles": [r"CIMCO Edit 2026.01.02 - [runs\full_chain\20261030_184009\04_CIMCO_Edit_2026.nc]",
                              r"CIMCO Edit 2026.01.02 - [runs\full_chain\20261030_199901\04_CIMCO_Edit_2026.nc]"]}
    assert ace._cimco_any_match(state, nc) is True
    stale_only = dict(state, frame_titles=[state["frame_titles"][0]])
    assert ace._cimco_any_match(stale_only, nc) is False


def test_acad_sentinel_lisp_selfreports_counts():
    """AutoCAD 自写计数是 COM 挂起时的备用证据通道：字面量必须真的写出 marker 路径和计数键。"""
    lsp = ace._acad_sentinel_lsp(r"D:\tmp\m.txt")
    assert "c:VIRTU_VERIFY" in lsp.replace("VIRTU_VERIFY", "VIRTU_VERIFY")
    assert "(c:DRAWWHEELMOLD)" in lsp
    assert 'entity_count=' in lsp and 'entity_layers=' in lsp
    assert "D:/tmp/m.txt" in lsp
    assert lsp.count("(") == lsp.count(")")


def test_stage_acad_hands_cad_only_absolute_paths(tmp_path, monkeypatch):
    """外部软件按自己的 CWD 解析相对路径，症状是「实体 0」而不是报错——路径必须绝对化。"""
    captured = {}

    def fake_child(worker, payload, timeout, out_dir, name=None):
        captured.update(payload)
        return {"data": {"entity_count": 6, "sentinel": {"entity_count": "6"},
                         "layers": ["0"], "entity_layers": ["02_PROFILE"]},
                "rc": 0, "timed_out": False, "elapsed_s": 1.0,
                "child_log": os.path.join(out_dir, "x.log"),
                "result_path": os.path.join(out_dir, "x.json")}

    monkeypatch.setattr(ace, "_run_child", fake_child)
    monkeypatch.setattr(ace, "ensure_process",
                        lambda *a, **k: {"attached": True, "pid": 1, "started_by_us": False})
    monkeypatch.setattr(ace, "dismiss_app_dialogs", lambda exe, prefer=None: [])
    rel = str(tmp_path)
    rep = ace.stage_acad({"d_outer": 53.0, "d_inner": 14.0, "overall_len": 45.0},
                         rel, lambda s: "(defun c:DRAWWHEELMOLD () 1)")
    for key in ("lsp", "marker", "dwg"):
        assert os.path.isabs(captured[key]), key
        assert captured[key].startswith(os.path.abspath(rel)), key
    assert rep["status"] == "executed"


def test_stage_cimco_abspath_before_handing_to_editor(tmp_path, monkeypatch):
    """CIMCO 拿到相对路径会「打开失败但不报错」，载入必须用绝对路径喂它。"""
    seen = {}
    monkeypatch.setattr(ace, "_spawn_detached",
                        lambda exe, arg=None, join_s=8: seen.update(arg=arg) or {"pid": 1})
    monkeypatch.setattr(ace, "_cimco_doc_state",
                        lambda: {"frame_title": "CIMCO Edit 2026.01.02 - [x]",
                                 "frame_titles": [], "doc_tabs": [], "ribbon_tabs": [],
                                 "doc_count": 0, "hwnd": 1})
    monkeypatch.setattr(ace.time, "sleep", lambda *a: None)
    # 本测试只验证「绝对路径交接」，不依赖真实进程枚举：mock tasklist 调用，
    # 避免在无 CIMCO/被沙箱拦截 tasklist 的环境里挂起。
    monkeypatch.setattr(ace.subprocess, "check_output", lambda *a, **k: "")
    nc = tmp_path / "04_CIMCO_Edit_2026.nc"
    nc.write_text("O2026\nG00 X53.0 Z2.0\nM30\n", encoding="gbk")
    monkeypatch.chdir(tmp_path.parent)
    rel_nc = os.path.relpath(str(nc), os.getcwd())
    ace.stage_cimco(rel_nc, str(tmp_path))
    assert seen.get("arg") == os.path.abspath(str(nc))


def test_vericut_sidecar_must_be_fresh_and_name_our_nc(tmp_path):
    """假通过的真实来源：CWD 里上一次运行留下的同名 sidecar 被当成本次证据。
    现在双条件把关：本次新建 + 内容指名我们那份 NC。"""
    import os as _os
    out = str(tmp_path)
    proj = os.path.join(out, "p.vcproject")
    open(proj, "w", encoding="utf-8").write(
        '<NCPrograms><NCProgram File="D:/x/our_program.nc"/></NCPrograms>')
    stale = os.path.join(out, "p.log")
    open(stale, "w", encoding="gbk").write("our_program.nc 在 17 行:碰撞体积 999.0")
    _os.utime(stale, (1700000000, 1700000000))
    rc, blob, log = ace._vericut_batch_run(
        sys.executable, proj, out, timeout=30, argv_extra=["-c", "pass"])
    assert "SIDECAR_REJECTED_STALE" in blob
    assert "999.0" not in blob

    fresh = os.path.join(out, "q.vcproject")
    open(fresh, "w", encoding="utf-8").write('<NCProgram File="D:/x/our_program.nc"/>')
    side = os.path.join(out, "q.log")
    open(side, "w", encoding="gbk").write("our_program.nc 在 17 行:碰撞体积 12.0")
    rc, blob2, log2 = ace._vericut_batch_run(
        sys.executable, fresh, out, timeout=30, argv_extra=["-c", "pass"])
    assert "12.0" in blob2


def test_vericut_sidecar_of_somebody_els_nc_is_rejected(tmp_path):
    """新落盘但不是我们的 NC（例如样本工程自己的日志）→ 同样必须拒收。"""
    out = str(tmp_path)
    proj = os.path.join(out, "p.vcproject")
    open(proj, "w", encoding="utf-8").write('<NCProgram File="D:/x/our_program.nc"/>')
    side = os.path.join(out, "p.log")
    open(side, "w", encoding="gbk").write("force_turning_fanuc_sample.nc 碰撞体积 644700.6")
    rc, blob, log = ace._vericut_batch_run(
        sys.executable, proj, out, timeout=30, argv_extra=["-c", "pass"])
    assert "SIDECAR_REJECTED_NOT_OUR_NC" in blob
    assert "644700" not in blob


def test_vericut_project_nc_reads_reference_from_project(tmp_path):
    proj = tmp_path / "p.vcproject"
    proj.write_text('<X><NCProgram File="E:/a/b/WM2026.nc"/></X>', encoding="utf-8")
    assert ace._vericut_project_nc(str(proj)) == "WM2026.nc"


def test_ensure_process_matches_by_install_tail_not_just_exe_name(monkeypatch):
    """同名 exe 但装的不是同一份 → 不能当「我们的实例」接管，要单独列 foreign。"""
    rows = [
        {"name": "acad.exe", "pid": "111", "path": "C:/Other/AutoCAD 2026/acad.exe"},
        {"name": "acad.exe", "pid": "222", "path": "D:/cad2026/AutoCAD 2026/acad.exe"},
    ]
    monkeypatch.setattr(ace, "_proc_table", lambda: rows)
    monkeypatch.setattr(ace, "_launch_ledger_read", lambda: [])
    r = ace.ensure_process("acad.exe", r"D:\cad2026\AutoCAD 2026\acad.exe", wait_s=1)
    assert r["attached"] is True and r["pid"] == 222
    assert r["identity"] == "same_install"
    assert any("Other" in x for x in r["foreign"])
    assert r["started_by_us"] is False


def test_ensure_process_reports_foreign_and_missing_launcher(monkeypatch):
    rows = [{"name": "acad.exe", "pid": "111", "path": "C:/Other/AutoCAD 2026/acad.exe"}]
    monkeypatch.setattr(ace, "_proc_table", lambda: rows)
    monkeypatch.setattr(ace, "_launch_ledger_read", lambda: [])
    r = ace.ensure_process("acad.exe", r"Z:\nope\AutoCAD 2026\acad.exe", wait_s=1)
    assert r["attached"] is False and r["pid"] is None
    assert "不存在" in r["error"] and r["foreign"]


def test_launch_ledger_refuses_to_overwrite_unreadable_file(tmp_path, monkeypatch):
    """读失败时绝不写回空表（那会把历史账目抹掉）。"""
    bad = tmp_path / "ledger.json"
    bad.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(ace, "_launch_ledger_path", lambda: str(bad))
    before = bad.read_bytes()
    assert ace._launch_ledger_append({"pid": 1}) is False
    assert bad.read_bytes() == before
    assert list(tmp_path.glob("ledger.json.bad_*"))


def test_acad_gate_counts_only_entities_added_this_run(tmp_path, monkeypatch):
    """沿用旧文档时必须扣掉历史实体：102 总数 / 90 历史 → 本次只新增 12。"""
    def fake_child(worker, payload, timeout, out_dir, name=None):
        return {"data": {"entity_count": 102, "entity_count_before": 90,
                         "reused_document": True, "sentinel": {"entity_count": "102"},
                         "layers": ["0"], "entity_layers": ["02_PROFILE"]},
                "rc": 0, "timed_out": False, "elapsed_s": 1.0,
                "child_log": os.path.join(out_dir, "x.log"),
                "result_path": os.path.join(out_dir, "x.json")}

    monkeypatch.setattr(ace, "_run_child", fake_child)
    monkeypatch.setattr(ace, "ensure_process",
                        lambda *a, **k: {"attached": True, "pid": 1, "started_by_us": False})
    monkeypatch.setattr(ace, "dismiss_app_dialogs", lambda exe, prefer=None: [])
    rep = ace.stage_acad({"d_outer": 53.0, "d_inner": 14.0, "overall_len": 45.0},
                         str(tmp_path), lambda s: "(defun c:DRAWWHEELMOLD () 1)")
    assert rep["status"] == "executed"
    assert rep["metrics"]["entities_added"] == 12

    def fake_zero(worker, payload, timeout, out_dir, name=None):
        d = dict(fake_child(worker, payload, timeout, out_dir, name))
        d["data"] = dict(d["data"], entity_count_before=102)
        return d
    monkeypatch.setattr(ace, "_run_child", fake_zero)
    rep2 = ace.stage_acad({"d_outer": 53.0, "d_inner": 14.0, "overall_len": 45.0},
                          str(tmp_path), lambda s: "(defun c:DRAWWHEELMOLD () 1)")
    assert rep2["status"] == "blocked"
    assert rep2["metrics"]["entities_added"] == 0


def test_bridge_app_lock_is_single_flight():
    """同一批工业软件只能被一条链驱动：第二条必须被拒（返回 False），释放后才能再进。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "wvb", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "scripts", "workbuddy_virtu_bridge.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    from bridges.bridge_security import SingleFlight
    # The production lock is a cross-process named mutex; isolate this test
    # from any running bridge or parallel test holding the production name.
    mod._app_lock = SingleFlight(name="VirtuBridgeTest-" + uuid.uuid4().hex)
    assert mod._try_lock_app("t1") is True
    ok, payload = mod.run_exclusive(lambda: 1, "t2")
    assert ok is False and "并发" in payload["error"]
    mod._unlock_app()
    ok2, val = mod.run_exclusive(lambda: 42, "t3")
    assert ok2 is True and val == 42


def test_intent_parses_all_groove_radii_and_ignores_material_code():
    """R15 R12 R10 必须全都解析出来；Cr12MoV 里的 r12 不能被当成半径。"""
    from virtu_omni.engine.wish_cad_cam_engine import WishCADCAMEngine
    e = WishCADCAMEngine()
    sp = e.parse_wish_intent('轮模 材质Cr12MoV 外径53 轴孔14 宽度45 三道圆弧槽R15 R12 R10')
    assert sp["groove_radii"] == [15.0, 12.0, 10.0]
    assert sp["num_grooves"] == 3 and sp["num_features"] == 3
    assert sp["parse_warnings"]
    sp2 = e.parse_wish_intent('轴 材质Cr12MoV 外径40 内孔10 长100 圆角R5')
    assert sp2["groove_radii"] == [5.0]


def test_cimco_cuts_every_groove_radius():
    """三道槽就要有三条不同 R 的 G02，不能只切第一个 R。"""
    from virtu_omni.engine.wish_cad_cam_engine import WishCADCAMEngine
    e = WishCADCAMEngine()
    sp = e.parse_wish_intent('轮模 外径53 轴孔14 宽度45 三道圆弧槽R15 R12 R10')
    nc = e.generate_cimco_macro(sp)
    g02 = [l for l in nc.splitlines() if l.strip().startswith("G02")]
    radii = [l.split("R")[-1].split()[0] for l in g02]
    assert radii == ["15.00", "12.00", "10.00"], g02
    assert "#105" in nc and "#106" in nc and "#107" in nc


def test_nx_journal_uses_literal_radii_not_spec():
    """生成的 journal 里不能出现 spec 变量（那是生成期的对象）。"""
    from virtu_omni.engine.wish_cad_cam_engine import WishCADCAMEngine
    e = WishCADCAMEngine()
    sp = e.parse_wish_intent('轮模 外径53 轴孔14 宽度45 三道圆弧槽R15 R12 R10')
    nx = e.generate_nx12_script(sp)
    assert "enumerate([15.0, 12.0, 10.0], 1)" in nx
    assert "spec.get" not in nx and "spec[" not in nx
    compile(nx, "nx_journal", "exec")


def test_bridge_validates_tool_call_arguments():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "wvb2", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "scripts", "workbuddy_virtu_bridge.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    v = mod._validate_dispatch_args
    assert v("", "run", {})[0] is False
    assert v("photoshop", "run", {})[0] is False
    assert v("Siemens_NX", "", {})[0] is False
    assert v("Siemens_NX", "run_journal", "not-a-dict")[0] is False
    assert v("Siemens_NX", "run_journal", {})[0] is True
    assert v("VERICUT", "run_simulation", {"a": 1})[0] is True


def test_prune_runs_keeps_newest_and_ignores_other_dirs(tmp_path):
    root = str(tmp_path)
    names = ["20260101_00000%d" % i for i in range(5)]
    for n in names:
        os.makedirs(os.path.join(root, n))
    os.makedirs(os.path.join(root, "manual_stages"))
    removed = ace._prune_runs(root, keep=2)
    left = sorted(d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d)))
    assert len(removed) == 3
    assert left == sorted(names[-2:] + ["manual_stages"])


def test_proc_table_parses_wmic_csv_by_header(monkeypatch):
    """wmic CSV 列序是 Node,ExecutablePath,Name,ProcessId —— 按位置硬解析曾把 name/pid 对调，
    导致 ensure_process 永远匹配不到同源进程（SW/NX 那轮就是这么被误判成 blocked 的）。"""
    csv = ("Node,ExecutablePath,Name,ProcessId\r\n"
           "PC,D:/x/AutoCAD 2026/acad.exe,acad.exe,123\r\n"
           "PC,,Protected.exe,456\r\n")
    monkeypatch.setattr(ace.subprocess, "check_output", lambda *a, **k: csv)
    rows = ace._proc_table()
    assert rows[0]["name"] == "acad.exe"
    assert rows[0]["pid"] == "123"
    assert rows[0]["path"].endswith("acad.exe")
    assert rows[1]["name"] == "Protected.exe" and rows[1]["path"] == ""


def test_autocad_draws_only_feasible_grooves():
    """放不下的槽不能画到件外：R15 在 Ø53×45 上不可行 → 只画 2 段弧 + 一条告警。"""
    from virtu_omni.engine.wish_cad_cam_engine import WishCADCAMEngine
    e = WishCADCAMEngine()
    sp = e.parse_wish_intent('轮模 外径53 轴孔14 宽度45 三道圆弧槽R15 R12 R10')
    assert len(sp["geometry_warnings"]) == 1 and "R15" in sp["geometry_warnings"][0]
    assert e.generate_autocad_lisp(sp).count('(command "ARC"') == 2
    sp2 = e.parse_wish_intent('轮模 外径60 轴孔14 宽度80 三道圆弧槽R8 R6 R5')
    assert sp2["geometry_warnings"] == []
    assert e.generate_autocad_lisp(sp2).count('(command "ARC"') == 3


def test_bridge_rejects_paths_outside_allowed_roots():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "wvb3", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "scripts", "workbuddy_virtu_bridge.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    inside = os.path.join(root, "runs", "x", "a.nc")
    assert mod._path_allowed(inside) is True
    assert mod._path_allowed("C:/Windows/system32/calc.exe") is False
    ok, why = mod._validate_dispatch_args("CIMCO_Edit", "load", {"nc_file_path": "C:/Windows/x.nc"})
    assert ok is False and "允许根" in why


def test_close_launched_only_kills_ledger_pids(monkeypatch):
    killed = []
    monkeypatch.setattr(ace, "_launch_ledger_read",
                        lambda: [{"pid": 111, "exe": "acad.exe", "path": "D:/cad2026/AutoCAD 2026/acad.exe"},
                                 {"pid": 222, "exe": "acad.exe", "path": "D:/cad2024/AutoCAD 2024/acad.exe"}])
    monkeypatch.setattr(ace, "_proc_table",
                        lambda: [{"name": "acad.exe", "pid": "111", "path": "D:/cad2026/AutoCAD 2026/acad.exe"},
                                 {"name": "acad.exe", "pid": "222", "path": "C:/Other/AutoCAD 2026/acad.exe"}])
    monkeypatch.setattr(ace, "_launch_ledger_append", lambda rec: True)
    monkeypatch.setattr(ace.subprocess, "run",
                        lambda cmd, **kw: killed.append(cmd) or type("R", (), {"returncode": 0})())
    closed = ace.close_launched()
    assert closed == [111]
    assert len(killed) == 1 and "111" in killed[0]


def test_code_fingerprint_has_real_hashes():
    fp = ace._code_fingerprint()
    assert fp["files"].get("agent_chain_executor.py")
    for v in fp["files"].values():
        assert len(v) == 16


def test_autocad_lisp_is_valid_and_hatches_the_contour():
    """生成物必须是 LISP：不能把 Python 列表 repr 写进去；HATCH 边界要绑轮廓线而不是 entlast。"""
    from virtu_omni.engine.wish_cad_cam_engine import WishCADCAMEngine
    e = WishCADCAMEngine()
    sp = e.parse_wish_intent('轮模 外径53 轴孔14 宽度45 三道圆弧槽R15 R12 R10')
    lsp = e.generate_autocad_lisp(sp)
    assert '["' not in lsp and "']" not in lsp
    assert lsp.count('(command "ARC"') == 2
    assert '(setq pl_tail (entlast))' in lsp
    assert '"S" pl_tail' in lsp
    assert lsp.count("(") == lsp.count(")")


_HDR = """VERICUT-log
Version-9.6
*** 处理数控程序文件D:/Virtu模型/runs/x/04_CIMCO_Edit_2026.nc
Sat Oct 31 01:15:21 2026
"""

_TABLE = """刀路文件 : D:/Virtu模型/runs/x/04_CIMCO_Edit_2026.nc
Seq.  记录                         刀具描述                         刀具高度  刀具夹长  时间          空刀时间        空刀时间 %  切削距离  距离
-------
   1    20: N10 T0101 M03 S1200  1: OD ROUGH RIGHT - 80 DEG.  N/A   N/A   0:00:57     0:00:24     43%     278.513708  1254.681001
"""

_TOTALS = """   2    37: N20 T0202 M03 S800   2: OD Right 55 deg           N/A   N/A   0:00:26     0:00:18     72%     179.51995  848.34992
==============================================================================================================================
      总时间:                                                          0:01:23     0:00:43     52%     458.033658  2103.030921

错误数: 107
警告数: 0
"""


def test_vericut_simlog_refuses_totals_before_summary_separator():
    """仿真只跑到中途（有刀具明细、没 `=====` 汇总线）时不能把某个刀具行冒充总量。"""
    sim = ace._parse_vericut_simlog(_HDR + _TABLE)
    assert sim.get("summary_complete") is None
    assert "total_distance_mm" not in sim
    assert len(sim.get("tool_rows") or []) == 1


def test_vericut_simlog_reads_real_summary_block():
    """对齐 2026-10-31 实测 27,583 字节日志：汇总行在 `=====` 之后，错误/警告按标签取。"""
    sim = ace._parse_vericut_simlog(_HDR + _TABLE + _TOTALS)
    assert sim["summary_complete"] is True
    assert sim["total_time"] == "0:01:23"
    assert sim["air_pct"] == 52
    assert sim["total_cut_distance_mm"] == 458.033658
    assert sim["total_distance_mm"] == 2103.030921
    assert sim["errors"] == 107 and sim["warnings"] == 0


def test_stage_sw_blocks_when_revision_is_not_29(tmp_path, monkeypatch):
    """连到 Rev 34（2026 卸载残留的 ProgID 空壳）必须 blocked。

    背景：本机 HKCR\\SldWorks.Application.34 仍指向已删除的安装目录。
    任何「探测最高版本」或沿用无版本 ProgID 的旧代码都可能落到它上面。
    版本门必须在建模之前拦住，而不是让 2026 的 API 差异静默污染结果。
    """
    out = str(tmp_path)

    class WrongRevApp:
        Visible = True
        RevisionNumber = "34.0.0.0001"

        def RunMacro2(self, *a):
            raise AssertionError("版本不符时不得执行建模宏")

    monkeypatch.setattr(ace, "ensure_process", lambda *a, **kw: {"attached": True, "pid": 1})
    import win32com.client as w32c
    monkeypatch.setattr(w32c, "GetActiveObject", lambda progid: WrongRevApp())

    rep = ace.stage_sw({"d_outer": 53.0, "d_inner": 14.0, "overall_len": 45.0}, out)

    assert rep["status"] == "blocked"
    assert "34.0.0.0001" in rep["error"]
