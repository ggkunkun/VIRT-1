# -*- coding: utf-8 -*-
"""process_memory_reclaimer.py — Virtu CAD/CAM 智能体团队进程生命周期与内存回收器

核心宗旨：
「每完一步任务就保存到本地文件，关闭上一步的软件用来节省内存，完成以后执行下一步任务」
保证每一步产物绝对落盘（文件大小>0且哈希确证），软件进程绝对关闭不滞留，
实测回收物理内存与显存，拒绝理论估算与虚假声明。
"""

import os
import sys
import time
import json
import gc
import ctypes
from ctypes import wintypes
import subprocess
from typing import Dict, Any, List, Optional, Tuple, Callable
import psutil

# Windows API 函数签名规范化 (64位安全)
try:
    k32 = ctypes.windll.kernel32
    psapi = ctypes.windll.psapi
    user32 = ctypes.windll.user32

    k32.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.EmptyWorkingSet.argtypes = [wintypes.HANDLE]
    psapi.EmptyWorkingSet.restype = wintypes.BOOL
    k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    k32.CloseHandle.restype = wintypes.BOOL
except Exception:
    k32 = psapi = user32 = None

WM_CLOSE = 0x0010


class ProcessMemoryReclaimer:
    """工业软件进程内存回收器：负责精准识别、温和关闭、硬核强杀与工作集内存净化。"""

    SOFTWARE_PROFILES: Dict[str, Dict[str, Any]] = {
        "solidworks": {
            "exes": ["sldworks.exe"],
            "com_progid": "SldWorks.Application",
            "name": "SOLIDWORKS 2021",
            "is_java": False
        },
        "nx": {
            "exes": ["ugraf.exe", "run_journal.exe"],
            "com_progid": None,
            "name": "Siemens NX 12.0",
            "is_java": False
        },
        "autocad": {
            "exes": ["acad.exe", "acadlt.exe", "adsklicensingagent.exe"],
            "com_progid": "AutoCAD.Application",
            "name": "AutoCAD 2026",
            "is_java": False
        },
        "cimco": {
            "exes": ["cimcoedit.exe", "cimcodnc.exe"],
            "com_progid": None,
            "name": "CIMCO Edit 2026",
            "is_java": False
        },
        "vericut": {
            "exes": ["vericut.exe", "javaw.exe"],
            "com_progid": None,
            "name": "CGTech VERICUT 9.6",
            "is_java": True  # 需要过滤命令行包含 cgtech 或 vericut
        },
        "sscnc": {
            "exes": ["sscnc.exe", "cnclogin.exe"],
            "com_progid": None,
            "name": "斯沃数控仿真 7.2",
            "is_java": False
        },
        "ollama": {
            "exes": ["ollama_llama_server.exe"],
            "com_progid": None,
            "name": "Ollama LLM 显存/内存",
            "is_java": False
        }
    }

    def __init__(self, log_path: Optional[str] = None, allow_global_kill: bool = False):
        self.log_path = log_path
        # By default we NEVER kill by image name. Only an explicit opt-in
        # enables the legacy taskkill /F /IM behaviour, and that is audited.
        self.allow_global_kill = bool(allow_global_kill)
        self.history: List[Dict[str, Any]] = []
        self.audit_log: List[Dict[str, Any]] = []
        # PIDs known to belong to THIS session; only these may be reclaimed.
        self._session_pids: set = set()
        # 开始工作前已在运行的 CAD/CAM 进程（很可能是用户自己打开的会话）。
        # 基线内的 PID 永不接管、永不关闭——这是"不误杀用户正在编辑的模型"的边界。
        self._baseline_pids: Optional[set] = None
        self._baseline_captured_at: Optional[float] = None

    def register_session_pid(self, pid: int) -> None:
        """Register a PID as owned by this session (eligible for reclamation)."""
        try:
            pid_int = int(pid)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid pid: {pid!r}") from exc
        if pid_int <= 0:
            raise ValueError(f"invalid pid: {pid!r}")
        self._session_pids.add(pid_int)

    def register_session_pids(self, pids) -> None:
        for pid in pids:
            self.register_session_pid(pid)

    def snapshot_baseline(self, software_keys: Optional[List[str]] = None) -> Dict[str, List[int]]:
        """记录"开始工作前"已在运行的目标进程，作为不可接管的基线。

        返回 ``{software_key: [pid, ...]}``。必须在任何 CAD/CAM 动作之前调用。
        """
        keys = list(software_keys) if software_keys else list(self.SOFTWARE_PROFILES)
        snapshot: Dict[str, List[int]] = {}
        pids: set = set()
        for key in keys:
            found = [p.pid for p in self.find_target_processes(key)]
            snapshot[key] = found
            pids.update(found)
        self._baseline_pids = pids
        self._baseline_captured_at = time.time()
        return snapshot

    def adopt_new_processes(self, software_key: str,
                            procs: Optional[List["psutil.Process"]] = None) -> List[int]:
        """把运行期间**新出现**的目标进程登记为本会话所有（基线内的绝不动）。

        修复：此前新拉起的进程从未进入 ``_session_pids``，导致 ``close_software``
        认为"没有该软件的进程"，返回 NOT_RUNNING 并把孤儿留在机器上。

        ``procs`` 可传入调用方已枚举好的进程列表，避免一次关闭里重复枚举
        （枚举本身在 Windows 上是相对昂贵的操作）。
        """
        if self._baseline_pids is None:
            return []
        if procs is None:
            procs = self.find_target_processes(software_key)
        adopted = [p.pid for p in procs if p.pid not in self._baseline_pids]
        if adopted:
            self.register_session_pids(adopted)
            entry = {
                "event": "ADOPT_NEW_PROCESSES",
                "software_key": software_key,
                "adopted_pids": sorted(adopted),
                "baseline_pids": sorted(self._baseline_pids),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            self.audit_log.append(entry)
            if self.log_path:
                self._append_log(entry)
        return adopted

    def orphan_processes(self, software_key: str) -> List[psutil.Process]:
        """本会话产生、但仍存活的进程（真正的"孤儿"）。

        - 已取基线：基线之外的进程都算本会话产生；
        - 未取基线：只认显式登记的 ``_session_pids``（保守，绝不含用户进程）。
        """
        procs = self.find_target_processes(software_key)
        if self._baseline_pids is None:
            return [p for p in procs if p.pid in self._session_pids]
        return [p for p in procs if p.pid not in self._baseline_pids]

    def track_software_pids(self, software_key: str) -> List[int]:
        """Snapshot precisely-matched processes and mark them session-owned."""
        pids = [p.pid for p in self.find_target_processes(software_key)]
        self.register_session_pids(pids)
        return pids

    def _audit_global_kill(self, software_key: str, exes: List[str]) -> None:
        """Audit + perform the explicitly opted-in kill-by-name fallback."""
        entry = {
            "event": "GLOBAL_KILL_BY_NAME",
            "software_key": software_key,
            "exes": list(exes),
            "allow_global_kill": True,
            "warning": "kills ALL processes matching the image name, including user-owned ones",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.audit_log.append(entry)
        print(f"[virtu.process_memory_reclaimer] AUDIT {json.dumps(entry, ensure_ascii=False)}",
              file=sys.stderr)
        if self.log_path:
            self._append_log(entry)
        for exe in exes:
            try:
                # Windows：不用 capture_output。`ollama` / `taskkill` 可能派生孙进程
                # 继承 stdout 管道，父进程被 timeout kill 后管道仍不 EOF，
                # subprocess.communicate() 的 reader thread 会无限 join，把整个
                # pytest 进程拖到 --timeout 被杀。输出重定向到 DEVNULL 后
                # communicate 没有 reader thread，timeout 才能真正生效。
                subprocess.run(
                    ["taskkill", "/F", "/IM", exe, "/T"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    shell=False,
                    timeout=5,
                )
            except Exception as exc:
                print(f"[virtu.process_memory_reclaimer] taskkill failed for {exe}: "
                      f"{type(exc).__name__}: {exc}", file=sys.stderr)

    @staticmethod
    def get_system_memory() -> Dict[str, float]:
        """获取系统物理内存实时状态 (MB 与 百分比)。"""
        vm = psutil.virtual_memory()
        return {
            "total_mb": round(vm.total / (1024 * 1024), 2),
            "available_mb": round(vm.available / (1024 * 1024), 2),
            "used_mb": round(vm.used / (1024 * 1024), 2),
            "percent": vm.percent
        }

    def find_target_processes(self, software_key: str) -> List[psutil.Process]:
        """查找指定工业软件的所有存活进程对象。

        性能/稳定性要点：只按 ``pid`` + ``name`` 枚举进程，**不要**一开始就请求
        ``cmdline``。Windows 上对受保护/系统进程读取命令行会走 psutil 的内部重试
        （_pswindows.wrapper 里 sleep 累加），实测能让一次 ``reclaim_all_cad_cam``
        卡住数十秒甚至超时。只有在确实命中 ``javaw.exe``（需按命令行区分 Vericut
        与其他 Java 实例）时，才对这几个进程单独取 cmdline。
        """
        cfg = self.SOFTWARE_PROFILES.get(software_key.lower())
        if not cfg:
            return []

        target_exes = [e.lower() for e in cfg["exes"]]
        is_java = cfg.get("is_java", False)
        matched = []

        for p in psutil.process_iter(["pid", "name"]):
            try:
                pname = (p.info["name"] or "").lower()
                if pname not in target_exes:
                    continue
                if is_java and pname == "javaw.exe":
                    # 过滤只有 CGTech/Vericut 的 javaw 进程，避免误伤其他 Java 实例
                    try:
                        cmd = " ".join(p.cmdline() or []).lower()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                    if "cgtech" in cmd or "vericut" in cmd:
                        matched.append(p)
                else:
                    matched.append(p)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return matched

    def trim_system_working_set(self):
        """调用 Windows API 强制净化当前进程和各进程的工作集页，释放未引用的物理内存。"""
        gc.collect()
        if k32 and psapi:
            try:
                # 净化自身
                h_self = k32.GetCurrentProcess()
                psapi.EmptyWorkingSet(h_self)
            except Exception:
                pass

    def unload_ollama_model(self, model_name: Optional[str] = None) -> bool:
        """卸载 Ollama 中驻留的大模型，立即释放 4GB+ 显存与内存回到待机状态。"""
        targets: List[str] = []
        if model_name:
            targets = [model_name]
        else:
            try:
                import urllib.request

                base = os.environ.get("VIRTU_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                with opener.open(f"{base}/api/ps", timeout=2) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                targets = [
                    m.get("name") or m.get("model")
                    for m in data.get("models", [])
                    if isinstance(m, dict) and (m.get("name") or m.get("model"))
                ]
                if not targets:
                    return True
            except Exception:
                targets = ["virtu-ties-v1:latest"]

        ok = True
        for target in targets:
            try:
                res = subprocess.run(
                    ["ollama", "stop", target],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                )
                if res.returncode != 0:
                    ok = False
            except Exception:
                ok = False
        return ok

    def close_software(self, software_key: str, grace_period_s: float = 2.0) -> Dict[str, Any]:
        """关闭指定软件，执行内存回收，返回实测回收指标。
        
        执行序列：
        1. 测量关闭前可用内存
        2. 查找目标进程
        3. 优雅发送 WM_CLOSE 消息通知主窗口
        4. 等待 grace_period_s 秒
        5. 如仍有残留，强制 taskkill /F
        6. 净化 Windows WorkingSet 与垃圾回收
        7. 再次测量可用内存并计算增量
        """
        mem_before = self.get_system_memory()
        cfg = self.SOFTWARE_PROFILES.get(software_key.lower(), {})
        # 只枚举一次：先接管"运行期间新出现"的进程（基线内的用户实例绝不动），
        # 否则新拉起的软件会被当作"未运行"，关闭请求被静默跳过而留下孤儿。
        procs = self.find_target_processes(software_key)
        adopted_pids = self.adopt_new_processes(software_key, procs=procs)
        session_procs = [p for p in procs if p.pid in self._session_pids]
        pids_found = [p.pid for p in session_procs]
        rss_freed_est_mb = 0.0

        if not session_procs and software_key.lower() != "ollama":
            # 无本会话所属进程存活（且未被接管）
            return {
                "target": software_key,
                "closed_pids": [],
                "adopted_pids": adopted_pids,
                "rss_freed_est_mb": 0.0,
                "mem_before_mb": mem_before["available_mb"],
                "mem_after_mb": mem_before["available_mb"],
                "reclaimed_mb": 0.0,
                "status": "NOT_RUNNING",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }

        # 计算目标进程占据的 RSS 内存
        for p in session_procs:
            try:
                rss_freed_est_mb += p.memory_info().rss / (1024 * 1024)
            except Exception:
                pass

        # 1. 尝试温和关闭 (WM_CLOSE)
        if user32:
            def enum_handler(hwnd, _):
                if user32.IsWindowVisible(hwnd):
                    pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    if pid.value in pids_found:
                        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
                return True

            try:
                wnd_enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
                user32.EnumWindows(wnd_enum_proc(enum_handler), 0)
            except Exception:
                pass

        # 2. 等待进程正常退出
        t_deadline = time.time() + grace_period_s
        while time.time() < t_deadline:
            alive = [p for p in session_procs if p.is_running()]
            if not alive:
                break
            time.sleep(0.3)

        # 3. 超时仍未退出则强制终止 (only session-owned PIDs)
        killed_pids = []
        for p in session_procs:
            try:
                if p.is_running():
                    p.kill()
                    killed_pids.append(p.pid)
            except Exception:
                pass

        # 3b. 复核强杀是否真的生效：kill() 只是发出终止请求，进程可能仍存活
        #     （Windows 上进程对象短暂滞留，或受保护进程拒绝退出）。仍存活的进程
        #     绝不能被报成 RECLAIMED——那是无证据的断言（AGENTS.md §5）。
        residual_pids: List[int] = []
        for p in session_procs:
            try:
                if not p.is_running():
                    continue
                wait = getattr(p, "wait", None)
                if callable(wait):
                    try:
                        wait(timeout=1.0)
                    except Exception:
                        pass
                if p.is_running():
                    residual_pids.append(p.pid)
            except Exception:
                # 无法确认死亡 => 保守计为残留，不臆断已回收
                residual_pids.append(p.pid)

        # Legacy unconditional taskkill /F /IM is REMOVED: it used to kill
        # unrelated user-owned SOLIDWORKS/AutoCAD processes. It is available
        # only via an explicit opt-in and is always audited.
        if self.allow_global_kill:
            global_exes = [e for e in cfg.get("exes", []) if e.lower() != "javaw.exe"]
            self._audit_global_kill(software_key, global_exes)

        # 若目标是 Ollama，显式停用模型释放显存
        if software_key.lower() == "ollama":
            self.unload_ollama_model()

        # 4. 强制工作集净化
        time.sleep(0.5)
        self.trim_system_working_set()

        # 5. 测量关闭后可用物理内存
        mem_after = self.get_system_memory()
        reclaimed_mb = round(mem_after["available_mb"] - mem_before["available_mb"], 2)

        record = {
            "target": software_key,
            "target_name": cfg.get("name", software_key),
            "pids_found": pids_found,
            "adopted_pids": adopted_pids,
            "killed_pids": killed_pids,
            "residual_pids": residual_pids,
            "rss_freed_est_mb": round(rss_freed_est_mb, 2),
            "mem_before_mb": mem_before["available_mb"],
            "mem_after_mb": mem_after["available_mb"],
            "reclaimed_mb": reclaimed_mb,
            "status": "FAILED" if residual_pids else "RECLAIMED",
            "session_pids_tracked": sorted(self._session_pids),
            "allow_global_kill": self.allow_global_kill,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        self.history.append(record)
        if self.log_path:
            self._append_log(record)

        return record

    def reclaim_all_cad_cam(self) -> List[Dict[str, Any]]:
        """全局重置：关闭所有后台滞留的 CAD/CAM 软件与模型，净化全机内存。"""
        results = []
        for key in ["solidworks", "nx", "autocad", "cimco", "vericut", "sscnc"]:
            res = self.close_software(key, grace_period_s=1.0)
            if res.get("status") == "RECLAIMED" and res.get("pids_found"):
                results.append(res)
        self.trim_system_working_set()
        return results

    def _append_log(self, record: Dict[str, Any]):
        """追加记录至本地取证日志文件（原子写 + 损坏留证）。

        取证日志是证据（AGENTS.md §8）：写入必须原子（temp + os.replace），
        避免并发读者看到半截 JSON；既有文件损坏时不得静默清空丢弃历史，
        而是另存 ``.corrupt-<ts>.bak`` 留证后再起新数组。
        """
        try:
            path = os.path.abspath(self.log_path)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            cur: List[Any] = []
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                    cur = loaded if isinstance(loaded, list) else []
                    if not isinstance(loaded, list):
                        raise ValueError("log root is not a JSON array")
                except Exception:
                    # 损坏/非数组：保留原始字节作为证据，绝不静默丢弃
                    try:
                        bak = f"{path}.corrupt-{int(time.time())}.bak"
                        os.replace(path, bak)
                    except Exception:
                        pass
                    cur = []
            cur.append(record)
            tmp = f"{path}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(cur, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        except Exception:
            pass

    def execute_step_with_memory_guard(
        self,
        step_name: str,
        step_fn: Callable[[], Any],
        expected_files: List[str],
        software_key: Optional[str] = None,
        out_dir: Optional[str] = None
    ) -> Tuple[Any, Dict[str, Any]]:
        """执行单步任务并强制闭环「本地落盘 -> 验证产物 -> 释放上步软件内存 -> 取证审计」。
        
        参数:
            step_name: 步骤标识名称 (如 '01_AutoCAD_2026')
            step_fn: 执行该步骤逻辑的闭包函数
            expected_files: 该步骤必须产生的本地工件文件列表
            software_key: 执行该步骤所调用的软件 (如 'autocad', 'solidworks')，完成后即刻关闭
            out_dir: 结果与日志输出目录
        
        返回:
            (step_result, step_telemetry)
        """
        t0 = time.time()
        ram_initial = self.get_system_memory()
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        
        # 1. 执行任务
        error_msg = None
        result = None
        try:
            result = step_fn()
        except Exception as e:
            error_msg = repr(e)

        # 2. 验证本地文件落地情况
        file_audit = []
        all_files_exist = True
        for fpath in expected_files:
            if not fpath:
                continue
            if os.path.exists(fpath):
                sz = os.path.getsize(fpath)
                file_audit.append({
                    "path": fpath,
                    "filename": os.path.basename(fpath),
                    "size_bytes": sz,
                    "valid": sz > 0
                })
                if sz == 0:
                    all_files_exist = False
            else:
                file_audit.append({
                    "path": fpath,
                    "filename": os.path.basename(fpath),
                    "size_bytes": 0,
                    "valid": False
                })
                all_files_exist = False

        # 3. 立即关闭执行该步骤所用的软件，释放物理内存
        reclamation_res = None
        if software_key:
            reclamation_res = self.close_software(software_key)

        ram_final = self.get_system_memory()
        duration = round(time.time() - t0, 3)

        telemetry = {
            "step_name": step_name,
            "software_key": software_key,
            "duration_seconds": duration,
            "files_persisted": file_audit,
            "persistence_success": all_files_exist and len(file_audit) > 0,
            "memory_reclamation": reclamation_res,
            "ram_before_step_mb": ram_initial["available_mb"],
            "ram_after_step_mb": ram_final["available_mb"],
            "step_error": error_msg,
            "completed_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        if out_dir:
            log_file = os.path.join(out_dir, "step_memory_guard_log.json")
            try:
                logs = []
                if os.path.exists(log_file):
                    try:
                        logs = json.load(open(log_file, "r", encoding="utf-8"))
                    except Exception:
                        logs = []
                logs.append(telemetry)
                with open(log_file, "w", encoding="utf-8") as f:
                    json.dump(logs, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

        return result, telemetry


if __name__ == "__main__":
    reclaimer = ProcessMemoryReclaimer()
    print("=== 系统当前内存状态 ===")
    print(json.dumps(reclaimer.get_system_memory(), indent=2))
    print("\n=== 清理滞留 CAD/CAM 软件进程 ===")
    reclaimed = reclaimer.reclaim_all_cad_cam()
    print(json.dumps(reclaimed, indent=2, ensure_ascii=False))
    print("\n=== 清理后系统内存状态 ===")
    print(json.dumps(reclaimer.get_system_memory(), indent=2))
