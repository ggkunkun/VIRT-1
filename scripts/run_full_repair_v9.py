#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全面修补 v5 守候编排（2026-11-16）。

流程（严格串行，杜绝并发污染 —— 工作区 §8 测量宪法）：
  0. 等 GPU 独占：无其它 train/eval 进程 + ollama ps 空 + free>=5000MB，连续 3 次；
  1. 干净复测基线：对 v3 与 v4 各 2 轮 verify(all)，落独立目录（先取证后修补）；
  2. v5 训练：基座 = v3 的 merged_hf（与 v4 相同起点），数据 = 355 行强化语料，
     epochs=1, grad_accum=4, max_length=640, lr=8e-5, save_every=10；
  3. 合并 + GGUF + 部署为 virtu-six-software:v5-repair（新标签，不覆盖 v3/v4）；
  4. 独占验收：v5 跑 3 轮 verify(all)，与基线对比；
  5. 写报告 reports/FULL_REPAIR_V5_2026-11-16.md。

任一步失败即停，不伪造成功。所有子进程超时控制。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / ".venv" / "Scripts" / "python.exe"
LOG = ROOT / "runs" / "full_repair_v9_20261117"
LOG.mkdir(parents=True, exist_ok=True)

BASE = ROOT / "checkpoints" / "_deploy_six_software_v3" / "merged_hf"
DATA = ROOT / "reports" / "handover_20261115" / "train_data" / "six_software_v9_repair_sft.jsonl"
OUT_LORA = ROOT / "checkpoints" / "six_software_v9_repair_lora"
DEPLOY_DIR = ROOT / "checkpoints" / "_deploy_six_v9_repair"
GGUF = DEPLOY_DIR / "virtu-six-software_v9.q4_0.gguf"
TAG = "virtu-six-software:v9-repair"
PROFILE = ROOT / "cloud_train_pack" / "deploy_trained_adapter.py"


def log(msg: str):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with (LOG / "orchestrator.log").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(cmd: list, logfile: str, timeout: int, cwd=None) -> bool:
    log(f"RUN {logfile}: {' '.join(str(c) for c in cmd)[:220]}")
    t0 = time.time()
    env = dict(os.environ)
    env.setdefault("HF_DEACTIVATE_ASYNC_LOAD", "1")
    with (LOG / logfile).open("w", encoding="utf-8") as lf:
        try:
            p = subprocess.run([str(c) for c in cmd], stdout=lf, stderr=subprocess.STDOUT,
                               timeout=timeout, cwd=str(cwd or ROOT), env=env)
            rc = p.returncode
        except subprocess.TimeoutExpired:
            rc = -99
            lf.write(f"\n[ORCH] TIMEOUT {timeout}s\n")
    log(f"END {logfile}: rc={rc} elapsed={time.time()-t0:.1f}s")
    return rc == 0


def free_commit_mb() -> int:
    try:
        import ctypes
        class _MEM(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]
        m = _MEM(dwLength=ctypes.sizeof(_MEM))
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
            return int(m.ullAvailPageFile // (1024 * 1024))
    except Exception:
        pass
    return 0


def gpu_free_mb() -> int:
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            text=True, timeout=20)
        return int(out.strip().splitlines()[0].strip())
    except Exception:
        return 0


def other_busy() -> list[str]:
    """用 psutil 查命令行，找其它 train/eval 进程（排除本编排及其子进程）。

    只认 *.py 脚本作为可执行主体（cmdline[1] 或 [2]），避免把「命令行里恰好提到
    这些关键词」的 bash -c 包装器（含本检测脚本自身）误判为占用者。
    """
    import psutil
    me = {os.getpid(), os.getppid()}
    busy = []
    targets = (
        "train_vericut_local_qlora.py", "verify_v4_vs_v3.py", "run_v3_law_eval",
        "eval_all_models_live.py", "run_domain_ab.py", "eval_vericut_e_training.py",
        "run_full_repair",
    )
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if p.info["pid"] in me:
                continue
            name = (p.info["name"] or "").lower()
            args = [a for a in (p.info["cmdline"] or [])[1:] if a]
            # 主体必须是 python.exe / pythonw.exe，且脚本参数命中目标
            if "python" not in name:
                continue
            if any(a == "pytest" or a.endswith("pytest.exe") for a in args) or (
                "-m" in args and "pytest" in args
            ):
                busy.append(f"{p.info['pid']}:pytest")
                continue
            for a in args:
                if a.endswith(".py") and any(t in a for t in targets):
                    busy.append(f"{p.info['pid']}:{a}")
                    break
        except Exception:
            pass
    return busy


def ollama_loaded() -> list[str]:
    try:
        import urllib.request
        op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        doc = json.loads(op.open("http://127.0.0.1:11434/api/ps", timeout=15).read())
        return [m.get("name", "") for m in doc.get("models", [])]
    except Exception:
        return ["<query-failed>"]


def free_ollama_ram(opener=None) -> bool:
    """训练前卸载 Ollama 常驻模型并确认 ps 空，释放主机内存（fail-closed）。

    根因（2026-11-16 实测）：基线 verify 把 v3/v4 加载进 Ollama，默认 keep_alive≈5min
    使其在训练启动后仍常驻主机内存；8B QLoRA（embed/lm_head pinned@cpu ~2.5GB）叠加
    常驻 GGUF 把系统 commit 耗尽 —— dwm.exe 报 0xc00001ad FATAL_MEMORY_EXHAUSTION，
    训练进程被终止 rc=0x40010004（无 Python traceback）。起始独占门只查训练「前」ps 空，
    基线之后模型重新常驻，故必须在 STEP 2 之前显式卸载。

    返回 True 仅当确认 ps 已空；卸载无效（ps 仍非空）返回 False，调用方据此 fail-closed，
    绝不把训练送进必然耗尽的内存窗口。opener 可注入以便反证测试。
    """
    import urllib.request
    if opener is None:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _ps():
        doc = json.loads(opener.open("http://127.0.0.1:11434/api/ps", timeout=15).read())
        return [m.get("name", "") for m in doc.get("models", []) if m.get("name")]

    try:
        loaded = _ps()
    except Exception as exc:
        log(f"free_ollama_ram: ps query failed ({exc})")
        return False
    for name in loaded:
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:11434/api/generate",
                data=json.dumps({"model": name, "keep_alive": 0}).encode("utf-8"),
                headers={"Content-Type": "application/json"})
            opener.open(req, timeout=60).read()
            log(f"unloaded ollama model: {name}")
        except Exception as exc:
            log(f"unload {name} failed: {exc}")
    for _ in range(12):
        try:
            if not _ps():
                log("ollama ps empty -> host RAM freed for training")
                return True
        except Exception:
            pass
        time.sleep(5)
    log("[FATAL] ollama ps still non-empty after unload; refusing to train into RAM exhaustion")
    return False


def wait_exclusive():
    log("等待 GPU 与宿主机提交内存独占（连续 3 次：无其它训练/评测/pytest + ollama 空 + free>=5000MB + commit>=13200MB）")
    hits = 0
    while True:
        busy = other_busy()
        loaded = ollama_loaded()
        free = gpu_free_mb()
        commit_mb = free_commit_mb()
        if not busy and not loaded and free >= 5000 and commit_mb >= 13200:
            hits += 1
            log(f"idle candidate {hits}/3: free={free}MB commit={commit_mb}MB")
            if hits >= 3:
                log("GPU 与提交内存独占确认 -> 开始串行流程")
                return True
        else:
            if hits:
                log("独占中断，重新计数")
            hits = 0
            log(f"busy: procs={len(busy)} ollama={loaded[:2]} free={free}MB commit={commit_mb}MB")
        time.sleep(20)


def verify_round(tag: str, round_no: int) -> bool:
    """用判分器原函数串行跑一轮 all 档（不并发），写独立 JSON。"""
    code = f'''
import json, sys, time
sys.path.insert(0, r"{ROOT / 'cloud_train_pack'}")
import deploy_trained_adapter as d
tag = {tag!r}
t0 = time.time()
try:
    probes = d.verify_deployed_model(tag, probe_profile="all", think=False)
    err = None
except Exception as exc:
    probes, err = {{}}, f"{{type(exc).__name__}}:{{exc}}"
passed = [k for k,v in probes.items() if isinstance(v,dict) and v.get("passed")]
failed = {{k:(v.get("reason") or str(v.get("sample"))[:100]) for k,v in probes.items() if isinstance(v,dict) and not v.get("passed")}}
rec = {{"tag":tag,"round":{round_no},"started_at":time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(t0)),
        "runtime_s":round(time.time()-t0,1),"total":len(probes),"passed":len(passed),"failed":failed,
        "error":err,"grader_sha256":getattr(d,"GRADER_SHA256",""),"detail":probes}}
print(json.dumps(rec, ensure_ascii=False))
'''
    out = LOG / f"verify_{tag.replace(':', '_')}_r{round_no}.json"
    rc = run([str(PY), "-c", code], f"verify_{tag.replace(':', '_')}_r{round_no}.log", 1200)
    if rc and out.exists():
        try:
            rec = json.loads(out.read_text(encoding="utf-8"))
            log(f"VERIFY {tag} r{round_no}: {rec['passed']}/{rec['total']} failed={list(rec['failed'])}")
            return True
        except Exception:
            pass
    return False


def verify_capture(tag: str, round_no: int) -> bool:
    """verify_round 的包装：把 -c 的 stdout 落 JSON（run 已重定向到 .log，这里改用直接文件）。"""
    code = f'''
import json, sys, time
sys.path.insert(0, r"{ROOT / 'cloud_train_pack'}")
import deploy_trained_adapter as d
tag = {tag!r}
t0 = time.time()
try:
    probes = d.verify_deployed_model(tag, probe_profile="all", think=False)
    err = None
except Exception as exc:
    probes, err = {{}}, f"{{type(exc).__name__}}:{{exc}}"
passed = [k for k,v in probes.items() if isinstance(v,dict) and v.get("passed")]
failed = {{k:(v.get("reason") or str(v.get("sample"))[:100]) for k,v in probes.items() if isinstance(v,dict) and not v.get("passed")}}
rec = {{"tag":tag,"round":{round_no},"started_at":time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(t0)),
        "runtime_s":round(time.time()-t0,1),"total":len(probes),"passed":len(passed),"failed":failed,
        "error":err,"grader_sha256":getattr(d,"GRADER_SHA256",""),
        "measurement_version":getattr(d,"MEASUREMENT_VERSION",""),"detail":probes}}
open(r"{LOG / f'verify_{tag.replace(chr(58), chr(95))}_r{round_no}.json'}", "w", encoding="utf-8").write(json.dumps(rec, ensure_ascii=False, indent=2))
print(json.dumps({{"passed":rec["passed"],"total":rec["total"],"failed":failed}}, ensure_ascii=False))
'''
    if not run([str(PY), "-c", code], f"verify_{tag.replace(':', '_')}_r{round_no}.log", 1200):
        return False
    # 取证门（§8.4）：基础设施失败（error 非空 / 探针空集，如标签 404、导入崩溃）判红；
    # genuine 探针失败（detail 非空、部分 passed=False）放行作基线数据，不冒充测量成功。
    # 旧实现内联代码捕获所有异常后仍 exit 0，使本包装对 404/空集恒 True —— FATAL 检查形同虚设。
    rec_path = LOG / f"verify_{tag.replace(':', '_')}_r{round_no}.json"
    try:
        rec = json.loads(rec_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return not rec.get("error") and bool(rec.get("detail"))


def build_modelfile(gguf_path: Path) -> str:
    """复用 v4 已验证 Modelfile 的 TEMPLATE/SYSTEM/PARAMETER，只换 FROM。

    裸 `FROM <gguf>` 会丢掉系统提示、采样参数与 stop 词，与 v3/v4 不同构，
    验收探针（show_template_gate / tool calling）必然失真 —— 2026-11-16 修复。
    参照件缺失即失败，不得退化为裸 Modelfile。
    """
    ref = ROOT / "checkpoints" / "_deploy_six_v4_local" / "virtu-six-software_v4.Modelfile"
    if not ref.is_file():
        raise FileNotFoundError(f"verified Modelfile reference missing: {ref}")
    lines = ref.read_text(encoding="utf-8").splitlines()
    if not lines or not lines[0].startswith("FROM "):
        raise ValueError(f"reference Modelfile has no FROM line: {ref}")
    gguf_abs = str(gguf_path.resolve()).replace("\\", "/")
    return "\n".join([f"FROM {gguf_abs}"] + lines[1:]) + "\n"


def main() -> int:
    if not wait_exclusive():
        return 1

    # Step 1: 干净基线（串行各 1 轮：v3 与 v7-repair 对照；已在本轮独占验证过则直接复用）
    log("=== STEP 1 干净基线复测 ===")
    for tag in ("virtu-six-software:v3", "virtu-six-software:v7-repair"):
        rec_p = LOG / f"verify_{tag.replace(':', '_')}_r1.json"
        if rec_p.is_file():
            try:
                rec = json.loads(rec_p.read_text(encoding="utf-8"))
                if not rec.get("error") and rec.get("detail"):
                    log(f"Reuse fresh baseline capture: {rec_p.name} ({rec.get('passed')}/{rec.get('total')})")
                    continue
            except Exception:
                pass
        if not verify_capture(tag, 1):
            log(f"[FATAL] baseline verify failed: {tag} r1")
            return 2
        time.sleep(5)

    # 训练前释放 Ollama 常驻内存（根因修复：基线加载的模型 keep_alive 常驻会耗尽 commit）
    if not free_ollama_ram():
        log("[FATAL] cannot free ollama host RAM before training")
        return 3

    # 若 v3 merged_hf 被清理则先由 _base_qwen3_8b + v3 adapter 无损重合成
    if not (BASE / "config.json").is_file():
        v3_raw_base = ROOT / "checkpoints" / "_base_qwen3_8b"
        v3_lora = ROOT / "checkpoints" / "_deploy_six_software_v3" / "unpacked" / "virtu_lora_adapter"
        log(f"Rematerializing missing v3 merged_hf: {BASE}")
        if not run([str(PY), "scripts/merge_numpy.py",
                    "--base", str(v3_raw_base), "--lora", str(v3_lora),
                    "--weight", "1.0", "--mode", "delta", "--out", str(BASE)],
                   "merge_v3_base.log", 3600):
            log("[FATAL] failed to rematerialize v3 merged_hf base")
            return 3

    # Step 2: v5 训练
    log("=== STEP 2 v5 QLoRA 训练 ===")
    if not run([str(PY), "scripts/train_vericut_local_qlora.py",
                "--base", str(BASE), "--data", str(DATA), "--out", str(OUT_LORA),
                "--epochs", "1", "--max-length", "640", "--grad-accum", "4",
                "--lr", "8e-5", "--save-every", "10", "--dev-max-items", "24", "--resume"],
               "train_v5.log", 7200):
        log("[FATAL] v5 training failed")
        return 3
    receipt = OUT_LORA / "training_receipt.json"
    if not receipt.is_file() or json.loads(receipt.read_text(encoding="utf-8")).get("status") != "COMPLETED":
        log("[FATAL] v5 training receipt not COMPLETED")
        return 4

    # Step 3: 合并 + GGUF + 部署
    log("=== STEP 3 合并/量化/部署 ===")
    if not run([str(PY), "scripts/merge_numpy.py",
                "--base", str(BASE), "--lora", str(OUT_LORA),
                "--mode", "delta", "--out", str(DEPLOY_DIR / "merged_hf")],
               "merge_v5.log", 3600):
        log("[FATAL] merge failed")
        return 5
    if not run([str(PY), "scripts/hf_to_gguf_numpy.py",
                "--model", str(DEPLOY_DIR / "merged_hf"), "--out", str(GGUF), "--dtype", "q4_0"],
               "gguf_v5.log", 3600):
        log("[FATAL] gguf failed")
        return 6
    modelfile = DEPLOY_DIR / "Modelfile"
    modelfile.write_text(build_modelfile(GGUF), encoding="utf-8")
    if not run(["ollama", "create", TAG, "-f", str(modelfile)], "ollama_create_v5.log", 1800):
        log("[FATAL] ollama create failed")
        return 7
    # 部署身份闸：新标签必须真实出现在服务里（防写错 store / 静默失败）
    try:
        import urllib.request
        op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with op.open("http://127.0.0.1:11434/api/tags", timeout=15) as resp:
            tags = {m["name"]: m["digest"] for m in json.loads(resp.read()).get("models", [])}
        if TAG not in tags:
            log(f"[FATAL] tag {TAG} absent from /api/tags after create (wrong store?)")
            return 7
        log(f"deployed {TAG} digest={tags[TAG][:16]}")
    except Exception as exc:
        log(f"[FATAL] cannot verify deployed tag: {exc}")
        return 7

    # Step 4: v9 独占验收 3 轮 + G71 语义门 + 泛化核验
    log("=== STEP 4 v9 验收 3 轮 ===")
    for rnd in (1, 2, 3):
        if not verify_capture(TAG, rnd):
            log(f"[FATAL] v9 verify failed r{rnd}")
            return 8
        time.sleep(5)

    # Step 5: 汇总报告（含连测最差值 gate 与 G71 语义门）
    log("=== STEP 5 汇总报告 ===")
    sys.path.insert(0, str(ROOT / "scripts"))
    sys.path.insert(0, str(ROOT / "cloud_train_pack"))
    import deploy_trained_adapter as grader
    from g71_semantic_check import check_g71_step_shaft
    import re as _re

    summary = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "tag": TAG,
        "basis": "measured",
        "corpus_sha256": None,
        "rounds": [],
    }
    import hashlib
    summary["corpus_sha256"] = hashlib.sha256(DATA.read_bytes()).hexdigest()
    v9_rounds = []
    for p in sorted(LOG.glob("verify_*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        g71_full = (d.get("detail") or {}).get("fanuc_g71_safety_probe", {}).get("full_response", "")
        g71_sem = check_g71_step_shaft(g71_full) if g71_full else {"passed": False, "violations": ["no_full_response"]}
        row_out = {
            "tag": d["tag"],
            "round": d["round"],
            "passed": d["passed"],
            "total": d["total"],
            "failed": d["failed"],
            "g71_semantic_passed": bool(g71_sem.get("passed")),
            "g71_semantic_violations": g71_sem.get("violations", []),
        }
        summary["rounds"].append(row_out)
        if d["tag"] == TAG:
            v9_rounds.append(row_out)

    # Generalization probes (different Di/Do/Pi & different bar/step shaft)
    r_lame = grader._probe_chat(
        TAG,
        [{"role": "user", "content": "按 Lamé 厚壁圆筒理论：内径 Di=50 mm，外径 Do=100 mm，内压 Pi=24 MPa。计算内壁环向应力 σ_θ（保留 2 位小数）与径向应力 σ_r，单位 MPa。"}],
        num_predict=420, keep_alive="180s", think=False,
    )
    vis_lame = grader._strip_think_blocks(str((r_lame.get("message") or {}).get("content", "")))
    nums_lame = [float(x) for x in _re.findall(r"[-+]?\d+(?:\.\d+)?", vis_lame)]
    gen_lame_ok = any(abs(v - 40.0) <= 0.15 for v in nums_lame) and bool(_re.search(r"(?:-|\u2212|\uff0d)\s*24(?:\.0+)?(?!\d|\.\d)", vis_lame))

    r_g71 = grader._probe_chat(
        TAG,
        [{"role": "user", "content": "用 FANUC ISO/G 格式为 Ø80 棒料编写 G71 粗车+G70 精车台阶轴程序（第一台阶 Ø46 长 25 mm，总长 60 mm），含 G50 S1800、G96 S150 M03、T0101、F0.25 与 M30，只输出程序。"}],
        num_predict=420, keep_alive="180s", think=False,
    )
    vis_g71 = grader._strip_think_blocks(str((r_g71.get("message") or {}).get("content", "")))
    tok_g71 = grader.evaluate_fanuc_g71_safety_probe(vis_g71)
    up_g71 = vis_g71.upper()
    gen_g71_ok = bool(tok_g71.get("passed")) and all(
        bool(_re.search(pat, up_g71))
        for pat in (r"X\s*46(?:\.0*)?", r"X\s*80(?:\.0*)?", r"Z\s*-25(?:\.0*)?", r"Z\s*-60(?:\.0*)?")
    )

    worst = min(v9_rounds, key=lambda r: (r["passed"], 1 if r["g71_semantic_passed"] else 0)) if v9_rounds else {}
    summary["gate"] = {
        "rule": "连测最差值做门禁 (project §8.2) + G71 语义门",
        "v9_rounds_passed": [r["passed"] for r in v9_rounds],
        "v9_g71_semantic_passed": [r["g71_semantic_passed"] for r in v9_rounds],
        "worst_passed": worst.get("passed"),
        "worst_total": worst.get("total"),
        "worst_round": worst.get("round"),
        "worst_failed": worst.get("failed"),
    }
    summary["generalization"] = {
        "gen_lame_Di50_Do100_Pi24": {"passed": gen_lame_ok, "sample": vis_lame[:220]},
        "gen_g71_D80_d46_L25_T60": {"passed": gen_g71_ok, "token_gate": tok_g71.get("passed"), "sample": vis_g71[:280]},
    }
    out_report = ROOT / "reports" / "FULL_REPAIR_V9_2026-11-18.json"
    out_report.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    free_ollama_ram()
    log(f"[DONE] 报告已落盘 {out_report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
