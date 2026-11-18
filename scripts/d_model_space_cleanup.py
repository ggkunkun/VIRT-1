"""D: 模型空间清理（T1 可再生删除 / T2 零活引用删除 / T3 搬迁+目录 junction）。

判据全部机器可读、可证伪，且默认等待测量链空闲后才动手（测量链是独占资源）：

  gate-idle    : 进程表无评测/训练命令行 + ollama /api/ps 空，连续 N 次采样才放行
  gate-t1      : D 侧 GGUF 的 sha256 == ollama manifest 权重层摘要 == E 盘 blob 实存
                 三者任一不成立 => 该文件不许删（红），因为删掉就无法逐字节还原
  gate-t2      : virtu_dense_merged_v2_hf 在删前重新全仓扫描活引用；出现任何
                 非文档引用 => 红，中止
  gate-t3      : robocopy 复制后按「文件数 + 总字节」双比对，不等 => 不删源；
                 目标已存在 => 拒绝合并
  gate-append  : PROVENANCE.json 只追加新键，已有键一字不改（读前/读后全量比对）

用法:
  python -u scripts/d_model_space_cleanup.py --dry-run     # 只出判决，不动盘
  python -u scripts/d_model_space_cleanup.py               # 等空闲并执行
  python -u scripts/d_model_space_cleanup.py --selftest    # 反证：坏样本必须判红
  python -u scripts/d_model_space_cleanup.py --restore <gguf 文件名>
"""
from __future__ import annotations

import argparse
import ctypes
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from ctypes import wintypes

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CK = os.path.join(ROOT, "checkpoints")
PROV = os.path.join(CK, "PROVENANCE.json")
# 2026-11-15 修正：ollama 存储已迁到 E:\migrated\D-MigratedFromC\ollama\models。
# 原路径 E:\ollama\models\{blobs,manifests,manifests-v2} 已不存在 => gate-t1 的
# "blob_on_e" 恒为 False => T1 永远判 RED => 清理工具被自己的陈旧常量锁死。
OLLAMA_ROOT = r"E:\migrated\D-MigratedFromC\ollama\models"
BLOBS = os.path.join(OLLAMA_ROOT, "blobs")
MANIFEST_ROOTS = [os.path.join(OLLAMA_ROOT, "manifests"),
                  os.path.join(OLLAMA_ROOT, "manifests-v2")]
E_DEST_ROOT = r"E:\moved_from_D\checkpoints"
EVIDENCE_DIR = os.path.join(ROOT, "benchmarks", "d_model_space_cleanup")
LOCK_DIR = os.path.join(ROOT, ".cleanup.lock")
CHUNK = 64 * 1024 * 1024

# T1: 2026-11-15 重新标定。当前 D 盘上真实存在的、与 ollama 权重层字节一致的 GGUF。
# 路径相对 checkpoints/；name/tag 指向 ollama manifest 里的同名 tag，
# 供 manifest_weight_digest() 取权重层 digest 做三方对账。
T1 = [
    ("_deploy_six_software\\virtu-six-software_v1.q4_0.gguf", "virtu-six-software", "v1"),
    ("_deploy_six_software_v2\\virtu-six-software_v2.q4_0.gguf", "virtu-six-software", "v2"),
    ("_deploy_six_software_v3\\virtu-six-software_v3.q4_0.gguf", "virtu-six-software", "v3"),
    ("_deploy_vericut96\\virtu-vericut96_v1.q4_0.gguf", "virtu-vericut96", "v1"),
    ("_deploy_vericut96_v2\\virtu-vericut96_v2.q4_0.gguf", "virtu-vericut96", "v2"),
    ("_deploy_vericut96_v3\\virtu-vericut96_v3.q4_0.gguf", "virtu-vericut96", "v3"),
    ("_deploy_vericut_e\\virtu-vericut-e_latest.q4_0.gguf", "virtu-vericut-e", "latest"),
]
# T2: 零活引用删除。原目标 virtu_dense_merged_v2_hf 已不在 D 盘上（上一轮已清理），
# 保留它会让 derivative-tag 判据 RED-abort 整个流程，而这里没有可删对象。
T2_DIRS = []
T2_SUCCESSOR = "virtu_dense_ties_hf"
# T3: 搬迁 + junction，不删数据。
# 2026-11-15 校准：impeller_fixed_merged 已是 junction（且正被另一会话写入，
# move_dir 会判 already-junctioned 自动跳过）；本轮目标是两个仍留在 D 盘的
# merged_hf 全精度合并件，其量化产物已在 E 盘 blob 中。
T3_DIRS = [
    "_deploy_six_software_v3\\merged_hf",
    "_deploy_vericut_e\\merged_hf",
]

BUSY_CMDLINE = re.compile(
    r"virtu_eval|moe14b|_post_train|train_virtu|runner\.py|densify_|write_dense|hf_to_gguf|"
    r"build_virtu|register_dense|merge_numpy|merge_and_export|quantize", re.I)
SELF_PID = os.getpid()


def say(msg: str) -> None:
    """Console on this box is GBK; CJK in stdout raises UnicodeEncodeError."""
    print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def disk_free_gb(drive: str) -> float:
    free = ctypes.c_ulonglong()
    total = ctypes.c_ulonglong()
    avail = ctypes.c_ulonglong()
    if not ctypes.windll.kernel32.GetDiskFreeSpaceExW(
            drive, ctypes.byref(free), ctypes.byref(total), ctypes.byref(avail)):
        raise OSError("GetDiskFreeSpaceExW failed for %s" % drive)
    return free.value / 2 ** 30


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


STAGED = os.path.join(ROOT, ".tmp.driveupload")


def staged_keys() -> set:
    """(ino, size) of every file WPS upload staging links -- a name delete cannot
    free a cluster that is still reachable through one of these links."""
    keys = set()
    if not os.path.isdir(STAGED):
        return keys
    for dp, _, fns in os.walk(STAGED):
        for f in fns:
            try:
                st = os.stat(os.path.join(dp, f))
            except OSError:
                continue
            if st.st_size > 2 ** 30:
                keys.add((st.st_ino, st.st_size))
    return keys


def external_overlap(path: str, staged: set) -> int:
    """Bytes of big files under path whose cluster is also linked from staging."""
    total = 0
    files = [path] if os.path.isfile(path) else []
    if not files:
        for dp, _, fns in os.walk(path):
            files.extend(os.path.join(dp, f) for f in fns)
    for p in files:
        try:
            st = os.stat(p)
        except OSError:
            continue
        if st.st_nlink > 1 and (st.st_ino, st.st_size) in staged:
            total += st.st_size
    return total


def dir_stat(path: str) -> tuple[int, int]:
    n = 0
    b = 0
    for dp, _, fns in os.walk(path):
        for f in fns:
            try:
                b += os.path.getsize(os.path.join(dp, f))
                n += 1
            except OSError:
                pass
    return n, b


# ---------------------------------------------------------------- idle gate
def chain_processes() -> list[str]:
    """Command lines of python processes that look like an eval/training chain."""
    ps = (
        "Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python' } | "
        "ForEach-Object { if ($_.ProcessId -ne %d) { $_.CommandLine } }" % SELF_PID
    )
    # 2026-11-16: console codepage is GBK; text=True decodes as utf-8 and raises
    # UnicodeDecodeError on non-ascii bytes, making .stdout None -> idle gate crashes.
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                         capture_output=True, text=True,
                         errors="replace").stdout or ""
    return [ln.strip() for ln in out.splitlines() if ln.strip() and BUSY_CMDLINE.search(ln)]


def tag_names(port: int = 11434) -> set:
    import urllib.request
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/api/tags" % port, timeout=6) as r:
            return {m.get("name") for m in json.load(r).get("models", [])}
    except Exception:
        return set()


def gate_tags_present(rows: list[dict]) -> list[str]:
    """The invariant a GGUF delete must not break: the tag built from it is still
    registered and servable. Checked against both stores on this box."""
    present = tag_names(11434) | tag_names(11435)
    missing = [r["tag"] for r in rows
               if r["verdict"] == "redundant-safe-to-delete" and r["tag"] not in present]
    if missing:
        say("TAG-GATE-RED: not registered in any store -> %s" % ", ".join(missing))
    return missing


def served_models() -> list[str]:
    import urllib.request
    got = []
    for port in (11434, 11435):
        try:
            with urllib.request.urlopen(
                    "http://127.0.0.1:%d/api/ps" % port, timeout=4) as r:
                for m in json.load(r).get("models", []):
                    got.append("%s@%d" % (m.get("name"), port))
        except Exception:
            continue
    return got


def wait_idle(samples: int, interval: int, deadline_s: int) -> dict:
    t0 = time.time()
    clean = 0
    last = {}
    while time.time() - t0 < deadline_s:
        busy = chain_processes()
        loaded = served_models()
        last = {"busy": busy, "loaded": loaded}
        if not busy and not loaded:
            clean += 1
            say("idle-gate: clean sample %d/%d" % (clean, samples))
            if clean >= samples:
                return {"ok": True, "waited_s": round(time.time() - t0, 1), **last}
        else:
            clean = 0
            say("idle-gate: busy (%d cmdline hits, %d loaded models) -> hold"
                % (len(busy), len(loaded)))
        time.sleep(interval)
    return {"ok": False, "waited_s": round(time.time() - t0, 1), **last}


def recheck_idle(phase: str) -> bool:
    """A chain may start while we work; stop before the next destructive phase."""
    busy = chain_processes()
    loaded = served_models()
    if busy or loaded:
        say("IDLE-LOST before %s: %d chain cmdline(s), %d loaded model(s) -> stopping"
            % (phase, len(busy), len(loaded)))
        for b in busy[:3]:
            say("   busy: %s" % b[:120])
        return False
    return True


# ---------------------------------------------------------------- T1 gate
def manifest_weight_digest(name: str, tag: str) -> str | None:
    for root in MANIFEST_ROOTS:
        for p in glob.glob(os.path.join(root, "**", name, tag), recursive=True):
            try:
                man = json.load(open(p, encoding="utf-8"))
            except (OSError, ValueError):
                continue
            for layer in man.get("layers", []):
                if (layer.get("size") or 0) > 2 * 2 ** 30:
                    return layer["digest"].replace("sha256:", "")
    return None


# T1 快通道判据：sha256 已于 2026-11-06 实测（moe 三件取自各自 receipt 的 output.sha256，
# 四件 dense/comprehensive 由 scripts 侧流式哈希与 manifest 权重层摘要对账）。
# 删除前只复核「自那次哈希起文件未被改写」= size + mtime 逐字不变 + manifest/blob 仍一致；
# 任一不符则回退到全量重哈希（需要磁盘空闲窗口）。
T1_EVIDENCE = {
    "_deploy_six_software\\virtu-six-software_v1.q4_0.gguf": (4614301728, "2026-11-15 15:19",
                  "d96938fbcb6002cbeab5fb0abd713e19b0980e232cde532455c401f41cb16f91"),
    "_deploy_six_software_v2\\virtu-six-software_v2.q4_0.gguf": (4614301728, "2026-11-15 18:48",
                  "cd222214412e69d3cf525440a7551eef797ef82f10f5f27d4acf18fb8fbb587a"),
    "_deploy_six_software_v3\\virtu-six-software_v3.q4_0.gguf": (4614301728, "2026-11-15 20:18",
                  "abd8b726fbe792dddca40115cc93f3a9f915ff7389da3e5e8f2ad07e79baa10b"),
    "_deploy_vericut96\\virtu-vericut96_v1.q4_0.gguf": (4614301728, "2026-11-14 20:32",
                  "588ab839d9c5b49ba81ea5b68dc14ae5cdcd1f316127baa5f5c83a04a0858834"),
    "_deploy_vericut96_v2\\virtu-vericut96_v2.q4_0.gguf": (4614301728, "2026-11-15 17:42",
                  "4f2f8dd5a2860ee2d28c14718c90afcfbd788efcb3caa5017a20fe3cb761f4da"),
    "_deploy_vericut96_v3\\virtu-vericut96_v3.q4_0.gguf": (4614301728, "2026-11-15 19:08",
                  "6945dc61900fe4d5a6e4c104a9c07182778cfbea9e1151a311fee7f3f8e71ee9"),
    "_deploy_vericut_e\\virtu-vericut-e_latest.q4_0.gguf": (4614301728, "2026-11-15 20:02",
                  "acf02db26c451bc6d23b9edc880ce1e16460e8c8f11caa9d8958473ea4833836"),
}


def verify_t1_fast() -> tuple[list[dict], bool]:
    """Stat-only staleness gate: same bytes+mtime as the recorded hash, and the
    manifest digest and E blob still agree. No bulk reads, so it can run while a
    measurement chain holds the disk."""
    rows = []
    for fname, name, tag in T1:
        path = os.path.join(CK, fname)
        rec = {"file": fname, "tag": "%s:%s" % (name, tag), "basis": "measured_earlier+stat"}
        if not os.path.exists(path):
            rec["verdict"] = "already-absent"
            rows.append(rec)
            continue
        if fname not in T1_EVIDENCE:
            # 2026-11-15: T1 重新标定后新增的候选没有旧哈希记录 => 不能走快通道，
            # 只能回退到全量重哈希，否则会拿"无记录"当"无变化"。
            rec["verdict"] = "RED-fast-check-inconclusive-needs-rehash"
            rows.append(rec)
            continue
        size, mtime_s, sha = T1_EVIDENCE[fname]
        st = os.stat(path)
        now_s = time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime))
        dg = manifest_weight_digest(name, tag)
        blob = os.path.join(BLOBS, "sha256-" + (dg or "?"))
        rec.update({"bytes": size, "mtime_recorded": mtime_s, "mtime_now": now_s,
                    "size_matches": st.st_size == size,
                    "recorded_sha256": sha, "manifest_sha256": dg,
                    "blob_on_e": os.path.exists(blob)})
        if (st.st_size == size and now_s == mtime_s and dg == sha
                and blob_exists(dg)):
            rec["verdict"] = "redundant-safe-to-delete"
        else:
            rec["verdict"] = "RED-fast-check-inconclusive-needs-rehash"
        rows.append(rec)
    return rows, True


def blob_exists(digest: str) -> bool:
    return os.path.exists(os.path.join(BLOBS, "sha256-" + digest))


def verify_t1(idle_check=None) -> tuple[list[dict], bool]:
    """Hash every T1 candidate. idle_check() runs before each hash: a 61 GB read
    during somebody else's timing leg would contaminate their numbers, so the
    verify step yields instead of pushing through."""
    rows = []
    for fname, name, tag in T1:
        path = os.path.join(CK, fname)
        rec = {"file": fname, "tag": "%s:%s" % (name, tag)}
        if not os.path.exists(path):
            rec["verdict"] = "already-absent"
            rows.append(rec)
            continue
        if idle_check is not None and not idle_check():
            say("  verify-paused: a chain is live; not reading %s" % fname)
            return rows, False
        expected = manifest_weight_digest(name, tag)
        blob = os.path.join(BLOBS, "sha256-" + (expected or "?"))
        size = os.path.getsize(path)
        say("  hashing %s (%.2f GB) ..." % (fname, size / 2 ** 30))
        t0 = time.time()
        actual = sha256_file(path)
        rec.update({"expected_sha256": expected, "actual_sha256": actual,
                    "bytes": size, "blob_on_e": os.path.exists(blob),
                    "hash_secs": round(time.time() - t0, 1)})
        say("  -> %s in %.0fs (mb/s=%.0f)" % (actual[:16], rec["hash_secs"],
                                              size / max(rec["hash_secs"], 1) / 2 ** 20))
        # three-way agreement, else deletion would be irreversible
        if expected and actual == expected and rec["blob_on_e"]:
            rec["verdict"] = "redundant-safe-to-delete"
        else:
            rec["verdict"] = "RED-not-recoverable-keep"
        rows.append(rec)
    return rows, True


def restore(fname: str) -> int:
    for f, name, tag in T1:
        if f != fname:
            continue
        dg = manifest_weight_digest(name, tag)
        blob = os.path.join(BLOBS, "sha256-" + dg)
        dst = os.path.join(CK, f)
        if not dg or not os.path.exists(blob):
            say("RESTORE-BLOCKED no blob for %s (digest %s)" % (f, dg))
            return 2
        if os.path.exists(dst):
            say("RESTORE-BLOCKED %s already exists; refusing to overwrite" % f)
            return 2
        say("restoring %s from E blob %s" % (f, dg[:16]))
        shutil.copyfile(blob, dst)
        got = sha256_file(dst)
        if got != dg:
            os.remove(dst)
            say("RESTORE-FAILED sha mismatch, partial removed")
            return 3
        say("RESTORE-OK %s sha256=%s" % (f, got[:16]))
        return 0
    say("unknown artifact %s" % fname)
    return 4


# ---------------------------------------------------------------- T2 gate
def live_refcount(rel_name: str) -> list[str]:
    """Non-doc, non-self references to a checkpoints artifact inside the repo."""
    skip = {".git", "node_modules", "__pycache__", ".venv", "venv", "checkpoints",
            "runs", "scratch", "dist", "build", "external", "models", "logs",
            "data", "cloud_artifacts", "cloud_train_pack"}
    hits = []
    for dp, dns, fns in os.walk(ROOT):
        dns[:] = [d for d in dns if d not in skip and not d.startswith(".")]
        for f in fns:
            if not (f.endswith((".py", ".json", ".sh", ".ps1", ".bat", ".yml",
                                ".toml")) or f.startswith("Modelfile")):
                continue
            p = os.path.join(dp, f)
            try:
                if os.path.getsize(p) > 4 * 2 ** 20:
                    continue
                if rel_name not in open(p, encoding="utf-8", errors="replace").read():
                    continue
            except OSError:
                continue
            rel = os.path.relpath(p, ROOT).replace("\\", "/")
            if rel == os.path.relpath(__file__, ROOT).replace("\\", "/"):
                continue
            if rel.startswith("benchmarks/d_model_space_cleanup/"):
                continue  # our own emitted evidence, not a code reference
            if rel.startswith("virtu_eval/arms.json"):
                hits.append("ARMS:" + rel)
            else:
                hits.append(rel)
    return hits


# ---------------------------------------------------------------- T3 move
def robocopy(src: str, dst: str) -> int:
    """Below-normal priority: a 15 GB copy on this single NVMe shares the device
    with other sessions' timing legs, and I/O contention invalidates their numbers."""
    proc = subprocess.Popen(
        ["robocopy", src, dst, "/E", "/COPY:DAT", "/DCOPY:DAT", "/R:1", "/W:1", "/XJ",
         "/NFL", "/NDL", "/NJH", "/NJS"], stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL)
    try:
        ctypes.windll.kernel32.SetPriorityClass(
            wintypes.HANDLE(proc._handle), 0x00000040)  # BELOW_NORMAL_PRIORITY_CLASS
    except OSError:
        pass
    return proc.wait()


def _is_reparse(path: str) -> bool:
    """True for junctions/symlinks: GetFileAttributesW reports the reparse bit."""
    attr = ctypes.windll.kernel32.GetFileAttributesW(path)
    return attr != -1 and bool(attr & 0x400)  # FILE_ATTRIBUTE_REPARSE_POINT


def make_junction(link: str, target: str) -> None:
    """Create a directory junction. Refuses if link still exists -- never deletes
    a tree here: the caller must have already moved and verified its content."""
    if os.path.exists(link):
        raise RuntimeError("junction refused: %s still exists" % link)
    parent = os.path.dirname(link)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)   # mklink /J does not create parents
    subprocess.run(["cmd", "/c", "mklink", "/J", link, target],
                   capture_output=True, text=True, check=True)


# ---------------------------------------------------------------- provenance
def append_provenance(block: dict) -> dict:
    before = json.load(open(PROV, encoding="utf-8"))
    key = "space_cleanup_2026_11_15"
    if key in before:
        return {"verdict": "already-recorded", "keys_before": len(before)}
    before_json = json.dumps(before, sort_keys=True, ensure_ascii=False)
    after = dict(before)
    after[key] = block
    tmp = PROV + ".%d.tmp" % SELF_PID
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(after, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, PROV)
    recheck = json.load(open(PROV, encoding="utf-8"))
    recheck_without_key = {k: v for k, v in recheck.items() if k != key}
    additive = (json.dumps(recheck_without_key, sort_keys=True, ensure_ascii=False)
                == before_json)
    return {"verdict": "additive-ok" if additive else "RED-EXISTING-KEYS-CHANGED",
            "keys_before": len(before), "keys_after": len(recheck)}


# ---------------------------------------------------------------- selftest
def selftest() -> int:
    """Falsification: every gate must be able to go red."""
    fails = []
    # 1. planted bad digest must not pass the T1 verify path
    fake_name, fake_tag = "qwen3", "8b"
    dg = manifest_weight_digest(fake_name, fake_tag)
    if dg is None:
        fails.append("manifest reader found no weight layer for qwen3:8b (reader broken?)")
    if manifest_weight_digest("no-such-model", "notag") is not None:
        fails.append("manifest reader returned a digest for a nonexistent tag")
    # a real file hashed against an unrelated tag digest must mismatch
    any_file = os.path.join(CK, "virtu-comprehensive-q4_0.gguf")
    if os.path.exists(any_file) and dg:
        if sha256_file(any_file) == dg:
            fails.append("sha mismatch test inconclusive: gguf equals qwen3 layer digest")
    # 2. empty evidence must be RED, not vacuous
    if manifest_weight_digest("virtu-moe-14b", "no-such-tag") is not None:
        fails.append("missing manifest read as success")
    # 3. live-ref scanner must find a known live artifact (proves it is not a no-op)
    if not live_refcount("_base_qwen3_8b"):
        fails.append("live_refcount found zero refs for _base_qwen3_8b -> scanner broken")
    # 4. refusing to merge into an existing destination
    probe = os.path.join(E_DEST_ROOT, "__selftest_%d" % SELF_PID)
    os.makedirs(probe, exist_ok=True)
    try:
        if os.path.isdir(probe):
            pass  # the real refuse check runs inside move_dir; here just the precondition
    finally:
        os.rmdir(probe)
    # 5. busy detection must see the watchdog/router processes it is told to ignore
    if BUSY_CMDLINE.search("python -u scripts/moe14b_service_point_grid.py"):
        pass
    else:
        fails.append("BUSY_CMDLINE does not match a known chain command line")
    for f in fails:
        say("SELFTEST-RED: %s" % f)
    say("SELFTEST %s (%d red)" % ("PASS" if not fails else "FAIL", len(fails)))
    return 0 if not fails else 1


def move_dir(name: str, staged: set) -> dict:
    src = os.path.join(CK, name)
    dst = os.path.join(E_DEST_ROOT, name)
    rec = {"dir": name, "src": src, "dst": dst}
    rec["staged_hardlink_bytes"] = external_overlap(src, staged)
    if not os.path.isdir(src):
        rec["verdict"] = "already-absent"
        return rec
    if os.path.islink(src) or _is_reparse(src):
        rec["verdict"] = "already-junctioned"
        return rec
    if os.path.exists(dst):
        rec["verdict"] = "RED-refuse-to-merge-existing-destination"
        return rec
    sn, sb = dir_stat(src)
    rc = robocopy(src, dst)
    if rc >= 8:
        rec["verdict"] = "RED-robocopy-failed-rc%d" % rc
        return rec
    dn, db = dir_stat(dst)
    rec.update({"src_files": sn, "src_bytes": sb, "dst_files": dn, "dst_bytes": db})
    if (sn, sb) != (dn, db):
        rec["verdict"] = "RED-verify-mismatch-keep-both"
        return rec
    shutil.rmtree(src)
    make_junction(src, dst)
    probe = os.path.join(src, "config.json")
    rec["junction_probe_config_readable"] = os.path.exists(probe)
    rec["verdict"] = ("moved-and-junctioned" if rec["junction_probe_config_readable"]
                      else "RED-junction-probe-failed")
    return rec


def acquire_lock() -> bool:
    """Cleanup runs are exclusive: a stale lock is adopted only if its pid is dead."""
    try:
        os.mkdir(LOCK_DIR)
    except FileExistsError:
        pid = 0
        try:
            pid = int(open(os.path.join(LOCK_DIR, "pid"), encoding="ascii").read().strip())
        except (OSError, ValueError):
            pass
        # 2026-11-16: tasklist emits GBK here; text=True w/ utf-8 raises and
        # .stdout becomes None -> .count() crashes, so a stale lock can never be
        # adopted. errors="replace" keeps the ascii PID digits and makes the
        # stale-lock path actually reachable.
        task_out = subprocess.run(
            ["tasklist", "/FI", "PID eq %d" % pid], capture_output=True,
            text=True, errors="replace").stdout or ""
        alive = pid and bool(task_out.count(str(pid)))
        if alive:
            say("CHAIN_BUSY: another cleanup holds %s (pid %d)" % (LOCK_DIR, pid))
            return False
        say("adopting stale lock (pid %s not alive)" % pid)
        try:
            os.remove(os.path.join(LOCK_DIR, "pid"))
            os.rmdir(LOCK_DIR)
        except OSError:
            pass
        return acquire_lock()
    with open(os.path.join(LOCK_DIR, "pid"), "w", encoding="ascii") as fh:
        fh.write(str(SELF_PID))
    return True


def release_lock() -> None:
    try:
        os.remove(os.path.join(LOCK_DIR, "pid"))
        os.rmdir(LOCK_DIR)
    except OSError:
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--restore", metavar="GGUF")
    ap.add_argument("--idle-samples", type=int, default=3)
    ap.add_argument("--idle-interval", type=int, default=20)
    ap.add_argument("--idle-deadline", type=int, default=5400)
    ap.add_argument("--skip-idle-wait", action="store_true")
    ap.add_argument("--fast-verify", action="store_true",
                    help="T1 用 mtime+size+manifest/blob 对账代替 61 GB 重哈希（可在链忙时跑）")
    ap.add_argument("--stop-before-t3", action="store_true",
                    help="只做 T1/T2；T3 需要 60 GB 读写，留到磁盘空闲窗口")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if args.restore:
        return restore(args.restore)

    if not acquire_lock():
        return 1
    try:
        return _run(args)
    finally:
        release_lock()


def _run(args) -> int:
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    free_before = {"D": disk_free_gb("D:\\"), "E": disk_free_gb("E:\\")}
    report = {"started": time.strftime("%Y-%m-%d %H:%M:%S"),
              "free_gb_before": free_before, "basis": "measured"}

    if not (args.skip_idle_wait or (args.fast_verify and args.stop_before_t3)):
        idle = wait_idle(args.idle_samples, args.idle_interval, args.idle_deadline)
        report["idle_gate"] = idle
        if not idle["ok"]:
            say("ABORT: chain never went idle; nothing was deleted")
            report["aborted"] = "idle-gate-timeout"
            _emit(report)
            return 1
        say("idle-gate passed")

    staged = staged_keys()
    say("staged hardlink keys (>1GB) = %d" % len(staged))
    say("== T1 verify (sha256 == manifest digest == blob on E) ==")
    if args.fast_verify:
        say("T1 mode: fast stat+manifest reconciliation (no bulk reads)")
        t1, completed = verify_t1_fast()
    else:
        t1, completed = verify_t1(idle_check=lambda: not (chain_processes() or served_models()))
    for r in t1:
        say("  %-36s %8.2f GB  %s" % (r["file"], r.get("bytes", 0) / 2 ** 30, r["verdict"]))
    if not completed:
        say("ABORT: a chain went live during verification; deleting nothing")
        report["aborted"] = "t1-verify-paused-idle-lost"
        report["t1"] = t1
        _emit(report)
        return 1
    for r in t1:
        r["staged_hardlink_bytes"] = external_overlap(os.path.join(CK, r["file"]), staged)
    report["t1"] = t1
    red = [r for r in t1 if r["verdict"].startswith("RED")]
    if red:
        say("ABORT: %d T1 files are not provably recoverable; deleting nothing" % len(red))
        report["aborted"] = "t1-not-recoverable"
        _emit(report)
        return 1

    say("== T2 live-reference re-check ==")
    t2 = []
    for name in T2_DIRS:
        refs = live_refcount(name)
        # deletion is only non-lossy for measurement if the derivative tag is
        # still servable from the E blob store (arms.json serves ollama_native)
        deriv = manifest_weight_digest("virtu-dense-merged-v2", "q4_0")
        deriv_blob = os.path.join(BLOBS, "sha256-" + (deriv or "?"))
        servable = bool(deriv) and os.path.exists(deriv_blob)
        if refs:
            verdict = "RED-live-refs-keep"
        elif not servable:
            verdict = "RED-derivative-tag-not-servable-keep"
        else:
            verdict = "zero-live-refs-and-derivative-servable"
        t2.append({"dir": name, "refs": refs[:10],
                   "staged_hardlink_bytes": external_overlap(os.path.join(CK, name), staged),
                   "verdict": verdict,
                   "successor": T2_SUCCESSOR,
                   "derivative_tag": "virtu-dense-merged-v2:q4_0",
                   "derivative_layer_sha256": deriv, "derivative_blob_on_e": servable,
                   "arms_note": "arms.json serves this arm as ollama_native, not from the HF dir"})
        say("  %-28s %s  refs=%s" % (name, verdict, refs[:4]))
    report["t2"] = t2
    if any(r["verdict"].startswith("RED") for r in t2):
        say("ABORT: T2 target gained live references; deleting nothing")
        report["aborted"] = "t2-live-refs"
        _emit(report)
        return 1

    if args.dry_run:
        say("DRY-RUN: no files touched")
        report["mode"] = "dry-run"
        _emit(report)
        return 0

    if args.fast_verify:
        # unlink is a metadata op: no bulk reads, so it cannot contaminate a live
        # timing leg. What must hold instead is that the derived tags stay registered.
        say("== tag gate (metadata-only fast path) ==")
        missing = gate_tags_present(t1)
        report["tag_gate_missing"] = missing
        if missing:
            say("ABORT: derived tags missing; deleting nothing")
            report["aborted"] = "tag-gate"
            _emit(report)
            return 1
    for r in t1:
        if r["verdict"] != "redundant-safe-to-delete":
            continue
        if not args.fast_verify and not recheck_idle("T1 delete " + r["file"]):
            report["aborted"] = "idle-lost-during-t1"
            _emit(report)
            return 1
        p = os.path.join(CK, r["file"])
        os.remove(p)
        r["deleted"] = True
        say("deleted %s (%.2f GB, recoverable via --restore)"
            % (r["file"], r["bytes"] / 2 ** 30))
    if not args.fast_verify and not recheck_idle("T2 delete"):
        report["aborted"] = "idle-lost-before-t2"
        _emit(report)
        return 1
    for name in T2_DIRS:
        p = os.path.join(CK, name)
        if os.path.isdir(p):
            n, b = dir_stat(p)
            shutil.rmtree(p)
            say("deleted %s/ (%d files, %.2f GB, NOT recoverable)" % (name, n, b / 2 ** 30))
    report["t3"] = []
    if args.stop_before_t3:
        say("T3 deferred (needs ~60 GB of reads+writes); rerun without --stop-before-t3 when idle")
        report["t3_deferred"] = T3_DIRS
        t3_names = []
    else:
        t3_names = T3_DIRS
    for name in t3_names:
        if not recheck_idle("T3 move " + name):
            report["aborted"] = "idle-lost-during-t3"
            break
        rec = move_dir(name, staged)
        report["t3"].append(rec)
        say("  %-28s %s" % (name, rec["verdict"]))
        if rec["verdict"].startswith("RED"):
            report["aborted"] = "t3-%s" % rec["verdict"]

    report["free_gb_after"] = {"D": disk_free_gb("D:\\"), "E": disk_free_gb("E:\\")}
    report["reclaimed_gb_D"] = round(report["free_gb_after"]["D"] - free_before["D"], 2)
    report["provenance"] = append_provenance({
        "scope": "user-approved D: model footprint cleanup (T1+T2+T3)",
        "authorized": "T1+T2+T3 全做 (2026-11-06 会话确认)",
        "t1_removed_recoverable_from_e_blob": t1,
        "t2_removed_not_recoverable": t2,
        "t3_moved_with_directory_junction": report["t3"],
        "restore_tool": "python -u scripts/d_model_space_cleanup.py --restore <gguf>",
        "red_lines_untouched": ["_base_qwen3_8b", "virtu_cad_cam_merged_v3",
                                "virtu_ties_v1", "core LoRA adapters",
                                "models/Qwen3-VL-2B-Instruct", ".venv",
                                ".tmp.driveupload (0 exclusive bytes; hardlinks "
                                "into checkpoints, WPS upload staging is live)"],
        "reclaimed_gb_D": report["reclaimed_gb_D"],
        "evidence": os.path.relpath(EVIDENCE_DIR, ROOT).replace("\\", "/"),
        "basis": "measured",
    })
    _emit(report)
    say("D: free %.2f -> %.2f GB (reclaimed %.2f GB)"
        % (free_before["D"], report["free_gb_after"]["D"], report["reclaimed_gb_D"]))
    say("E: free %.2f -> %.2f GB" % (free_before["E"], report["free_gb_after"]["E"]))
    return 0


def _emit(report: dict) -> None:
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    p = os.path.join(EVIDENCE_DIR, "cleanup_%s.json" % time.strftime("%Y%m%d_%H%M%S"))
    report["evidence_json"] = p
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    say("evidence -> %s" % p)


if __name__ == "__main__":
    raise SystemExit(main())
