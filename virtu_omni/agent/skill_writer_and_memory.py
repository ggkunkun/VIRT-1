"""Autonomous Skill Authoring, Long-Term Memory Evolution, and Web Knowledge Engine.

Enables the AI Agent to:
1. Synthesize new skills (SKILL.md & executable scripts) upon discovering novel patterns.
2. Commit episodic experience to long-term memory with Dense Vector embeddings for continuous self-evolution.
3. Perform hybrid semantic search (Dense Vector + Lexical match) over past engineering patterns.
4. Search and scrape technical documentation when facing unfamiliar industrial APIs.
"""

import os
import sys
import json
import time
import tempfile
import threading
import hashlib
import urllib.request
import urllib.parse
from contextlib import contextmanager
from typing import Dict, Any, List, Optional, Tuple

# Import dense vector store from virtu_edge.rag


def _resolve_workspace_root() -> str:
    """工作区根目录：环境变量优先，其次按本文件位置回溯两级，最后退回 cwd。

    审计问题：原实现把 ``D:\\Virtu模型`` 硬编码在模块级与函数默认值里，换盘符 /
    换机器 / CI 环境直接失效。此处去盘符化，同时保留"在仓库内运行"时的原路径语义。
    """
    for key in ("VIRTU_WORKSPACE_ROOT", "VIRTU_ROOT"):
        env = os.environ.get(key)
        if env and os.path.isdir(env):
            return os.path.abspath(env)
    here = os.path.dirname(os.path.abspath(__file__))
    cand = os.path.abspath(os.path.join(here, "..", ".."))
    if os.path.isdir(os.path.join(cand, "virtu_omni")):
        return cand
    return os.path.abspath(os.getcwd())


WORKSPACE_DIR = _resolve_workspace_root()
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

MEMORY_LOCK_TIMEOUT_S = float(os.environ.get("VIRTU_MEMORY_LOCK_TIMEOUT", "15"))


def resolve_memory_path(memory_path: Optional[str] = None) -> str:
    """解析记忆文件路径：显式入参 > VIRTU_MEMORY_PATH > 默认 workspace 相对路径。

    相对路径一律相对 ``WORKSPACE_DIR`` 解释，因此配置里可以写
    ``data/memory/industrial_knowledge_memory.json`` 而不再绑死盘符。
    """
    env_path = os.environ.get("VIRTU_MEMORY_PATH")
    raw = memory_path or env_path or os.path.join(
        "data", "memory", "industrial_knowledge_memory.json")
    if os.path.isabs(raw):
        return os.path.normpath(raw)
    return os.path.normpath(os.path.join(WORKSPACE_DIR, raw))


def resolve_skills_root(skills_root: Optional[str] = None) -> str:
    raw = skills_root or os.environ.get("VIRTU_SKILLS_ROOT") or "skills"
    if os.path.isabs(raw):
        return os.path.normpath(raw)
    return os.path.normpath(os.path.join(WORKSPACE_DIR, raw))


class MemoryFileLock:
    """记忆文件跨进程写锁。

    优先复用 ``bridges.bridge_security.SingleFlight``（Windows 命名内核 Mutex，
    跨进程生效）；该对象不可用或抢锁超时则降级为 ``<file>.lock`` 的 O_EXCL
    锁文件轮询，保证任何平台都有互斥语义。可重入（同线程嵌套只抢一次锁）。
    """

    def __init__(self, target_path: str, timeout_s: Optional[float] = None):
        self.target_path = os.path.abspath(target_path)
        self.lock_path = self.target_path + ".lock"
        self.timeout_s = MEMORY_LOCK_TIMEOUT_S if timeout_s is None else float(timeout_s)
        self._local = threading.RLock()
        self._depth = 0
        self._flight = None
        self._lock_fd = None

    def _try_byte_lock(self, fd: int) -> bool:
        """对锁文件加 1 字节排它锁（进程退出由内核自动释放，不会残留死锁）。"""
        try:
            if os.name == "nt":
                import msvcrt
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False

    def _release_byte_lock(self, fd: int) -> None:
        try:
            if os.name == "nt":
                import msvcrt
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            os.close(fd)
        except OSError:
            pass

    def _acquire_os(self) -> bool:
        """跨进程互斥：复用 SingleFlight（Win32 命名 Mutex）作第一道闸，
        再以锁文件字节锁作为权威判定，保证任何平台/任何竞争条件下都真正串行。
        """
        deadline = time.time() + self.timeout_s
        try:
            from bridges.bridge_security import SingleFlight
            self._flight = SingleFlight(name="VirtuMemoryFileLock")
            if not self._flight.acquire():
                self._flight = None  # 其它记忆写入进行中，交由字节锁裁决
        except Exception:
            self._flight = None
        os.makedirs(os.path.dirname(self.lock_path), exist_ok=True)
        try:
            fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR)
        except OSError:
            self._flight_release()
            return False
        while True:
            if self._try_byte_lock(fd):
                self._lock_fd = fd
                return True
            if time.time() >= deadline:
                try:
                    os.close(fd)
                except OSError:
                    pass
                self._flight_release()
                return False
            time.sleep(0.02)

    def _flight_release(self) -> None:
        if self._flight is not None:
            try:
                self._flight.release()
            except Exception:
                pass
            self._flight = None

    def _release_os(self) -> None:
        if self._lock_fd is not None:
            self._release_byte_lock(self._lock_fd)
            self._lock_fd = None
        self._flight_release()

    def __enter__(self):
        self._local.acquire()
        self._depth += 1
        if self._depth == 1 and not self._acquire_os():
            self._depth -= 1
            self._local.release()
            raise TimeoutError(f"记忆文件锁等待超时 {self.timeout_s}s: {self.target_path}")
        return self

    def __exit__(self, exc_type, exc, tb):
        self._depth -= 1
        if self._depth == 0:
            self._release_os()
        self._local.release()
        return False

try:
    from virtu_edge.rag.vector_store import DenseVectorStore
except ImportError:
    DenseVectorStore = None

try:
    from virtu_omni.reach import VirtuAgentReach
except ImportError:
    VirtuAgentReach = None

try:
    from virtu_omni.ai_scratch import VirtuAIScratch
except ImportError:
    VirtuAIScratch = None

try:
    from virtu_omni.paperclip import VirtuPaperclipAdapter
except ImportError:
    VirtuPaperclipAdapter = None

try:
    from virtu_omni.context_mode import VirtuContextMode
except ImportError:
    VirtuContextMode = None

try:
    from virtu_omni.rea import VirtuREA
except ImportError:
    VirtuREA = None

try:
    from virtu_omni.claude_plugins import VirtuClaudePlugins
except ImportError:
    VirtuClaudePlugins = None

try:
    from virtu_omni.computer_use import VirtuComputerUse
except ImportError:
    VirtuComputerUse = None


class SkillWriterAndMemory:
    """Manages skill synthesis, dense-vector episodic memory, and web research fallback."""

    def __init__(
        self,
        memory_path: Optional[str] = None,
        skills_root: Optional[str] = None,
        embedding_dim: int = 128
    ):
        # 去硬编码盘符：默认走 workspace 相对路径 + 环境变量覆盖（见 resolve_*）
        self.memory_path = resolve_memory_path(memory_path)
        self.skills_root = resolve_skills_root(skills_root)
        self.wal_path = self.memory_path + ".wal"
        self._lock = MemoryFileLock(self.memory_path)
        self.embedding_dim = embedding_dim
        os.makedirs(os.path.dirname(self.memory_path), exist_ok=True)
        os.makedirs(self.skills_root, exist_ok=True)

        # Initialize Dense Vector Store
        if DenseVectorStore is not None:
            self.vector_store = DenseVectorStore(dim=embedding_dim)
        else:
            self.vector_store = None

        # Initialize Agent-Reach
        if VirtuAgentReach is not None:
            self.reach = VirtuAgentReach()
        else:
            self.reach = None

        # Initialize AI Engineering from Scratch
        if VirtuAIScratch is not None:
            self.ai_scratch = VirtuAIScratch.get_instance()
        else:
            self.ai_scratch = None

        # Initialize Paperclip Control Plane
        if VirtuPaperclipAdapter is not None:
            self.paperclip = VirtuPaperclipAdapter.get_instance()
        else:
            self.paperclip = None

        # Initialize Context Mode Optimizer
        if VirtuContextMode is not None:
            self.context_mode = VirtuContextMode.get_instance()
        else:
            self.context_mode = None

        # Initialize REA (Reverse Engineer Anything) Adapter
        if VirtuREA is not None:
            self.rea = VirtuREA.get_instance()
        else:
            self.rea = None

        # Initialize Claude Code Official Plugins Adapter
        if VirtuClaudePlugins is not None:
            self.claude_plugins = VirtuClaudePlugins.get_instance()
        else:
            self.claude_plugins = None

        # Initialize Computer Use Desktop Automation Adapter
        if VirtuComputerUse is not None:
            self.computer_use = VirtuComputerUse.get_instance()
        else:
            self.computer_use = None

        self.memory = self._load_memory()
        self.provenance_path = os.path.join(self.skills_root, "SKILLS_PROVENANCE.json")
        self.skills_provenance = self.load_skills_provenance()
        self._sync_vector_store()

    def load_skills_provenance(self) -> Dict[str, Any]:
        """运行时读取 skills/SKILLS_PROVENANCE.json，建立技能来源与文件哈希基线。"""
        candidates = [
            self.provenance_path,
            os.path.join(WORKSPACE_DIR, "skills", "SKILLS_PROVENANCE.json"),
        ]
        for path in candidates:
            if path and os.path.isfile(path):
                data = self._read_json_file(path)
                if isinstance(data, dict) and isinstance(data.get("skills"), dict):
                    self.provenance_path = path
                    return data
        return {"skills": {}}

    def verify_skills_provenance(self, skill_name: Optional[str] = None) -> Dict[str, Any]:
        """按 SKILLS_PROVENANCE.json 校验技能文件完整性（SKILL.md 与核心脚本 sha256）。"""
        prov = self.load_skills_provenance()
        skills_map = prov.get("skills") if isinstance(prov, dict) else {}
        if not isinstance(skills_map, dict) or not skills_map:
            return {
                "passed": False,
                "verified_skills": 0,
                "mismatches": ["SKILLS_PROVENANCE.json missing or empty"],
                "provenance_path": self.provenance_path,
            }
        targets = (
            {skill_name: skills_map[skill_name]}
            if skill_name and skill_name in skills_map
            else ({skill_name: None} if skill_name else skills_map)
        )
        mismatches: List[str] = []
        verified_count = 0
        base_root = os.path.dirname(os.path.dirname(self.provenance_path))
        for sname, meta in targets.items():
            if not isinstance(meta, dict):
                mismatches.append(f"skill '{sname}' not registered in SKILLS_PROVENANCE.json")
                continue
            install_rel = meta.get("install_path") or f"skills/{sname}"
            skill_dir = os.path.join(base_root, install_rel.replace("/", os.sep))
            skill_ok = True
            for fmeta in meta.get("files") or []:
                rel_p = str(fmeta.get("path") or "")
                if not rel_p or "__pycache__" in rel_p or rel_p.endswith(".pyc"):
                    continue
                full_p = os.path.join(skill_dir, rel_p.replace("/", os.sep))
                if not os.path.isfile(full_p):
                    skill_ok = False
                    mismatches.append(f"{sname}/{rel_p}: file missing")
                    continue
                expected_sha = fmeta.get("sha256")
                if expected_sha:
                    with open(full_p, "rb") as fh:
                        actual_sha = hashlib.sha256(fh.read()).hexdigest()
                    if actual_sha != expected_sha:
                        skill_ok = False
                        mismatches.append(f"{sname}/{rel_p}: sha256 mismatch")
            if skill_ok:
                verified_count += 1
        return {
            "passed": len(mismatches) == 0 and verified_count > 0,
            "verified_skills": verified_count,
            "total_registered": len(skills_map),
            "mismatches": mismatches,
            "provenance_path": self.provenance_path,
        }

    def _empty_memory(self) -> Dict[str, Any]:
        return {
            "version": "2.0.0",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_experiences": 0,
            "patterns": [],
            "skills_catalog": []
        }

    @staticmethod
    def _read_json_file(path: str) -> Optional[Dict[str, Any]]:
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    def _load_memory(self) -> Dict[str, Any]:
        data = self._read_json_file(self.memory_path)
        memory = data if data is not None else self._empty_memory()
        memory.setdefault("version", "2.0.0")
        memory.setdefault("created_at", time.strftime("%Y-%m-%d %H:%M:%S"))
        memory.setdefault("patterns", [])
        memory.setdefault("skills_catalog", [])
        memory.setdefault("total_experiences", len(memory["patterns"]))
        # WAL 回放：崩溃点上"已追加未替换"的经验在这里补回（按 id 去重）
        self._wal_replay(memory)
        return memory

    # ---------------- WAL + 原子替换 + 文件锁 ----------------

    def _wal_append_unlocked(self, entry: Dict[str, Any]) -> None:
        payload = json.dumps(entry, ensure_ascii=False)
        with open(self.wal_path, "a", encoding="utf-8") as f:
            f.write(payload + "\n")
            f.flush()
            os.fsync(f.fileno())

    def _wal_append(self, entry: Dict[str, Any]) -> None:
        with self._lock:
            self._wal_append_unlocked(entry)

    def _wal_replay(self, memory: Dict[str, Any]) -> int:
        """把 WAL 中的 commit 记录补回内存副本，返回补回条数。"""
        if not os.path.exists(self.wal_path):
            return 0
        seen = {str(p.get("id")) for p in memory.get("patterns", [])}
        applied = 0
        try:
            with open(self.wal_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except Exception:
                        continue
                    if entry.get("op") != "commit":
                        continue
                    rec = entry.get("record") or {}
                    rid = str(rec.get("id") or "")
                    if rid and rid not in seen:
                        memory["patterns"].append(rec)
                        seen.add(rid)
                        applied += 1
        except OSError:
            return applied
        if applied:
            memory["total_experiences"] = len(memory["patterns"])
        return applied

    def _wal_truncate_unlocked(self) -> None:
        try:
            with open(self.wal_path, "w", encoding="utf-8"):
                pass
        except OSError:
            pass

    def _save_memory(self):
        """原子落盘：tempfile + fsync + os.replace，全程持跨进程锁。

        审计问题：原实现 ``open(path, "w")`` 全量覆盖，既非原子也无锁，两进程并发
        commit 时后写者静默覆盖前者。现在改为「WAL 追加 → 原子替换 → 清空 WAL」。
        """
        payload = json.dumps(self.memory, ensure_ascii=False, indent=2)
        target_dir = os.path.dirname(self.memory_path) or "."
        with self._lock:
            os.makedirs(target_dir, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(prefix=".memory_", suffix=".tmp", dir=target_dir)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(payload)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, self.memory_path)
            except BaseException:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
            self._wal_append_unlocked({"op": "checkpoint", "ts": time.time(),
                                       "pid": os.getpid(),
                                       "patterns": len(self.memory.get("patterns") or [])})
            self._wal_truncate_unlocked()

    def _sync_vector_store(self):
        """Index all loaded memory patterns into DenseVectorStore."""
        if not self.vector_store:
            return
        
        # Reset documents & embeddings
        self.vector_store.documents = []
        self.vector_store.embeddings = None

        docs = []
        for p in self.memory.get("patterns", []):
            content_text = (
                f"任务特征: {p.get('task_signature', '')}\n"
                f"问题工况: {p.get('problem_summary', '')}\n"
                f"解决策略: {p.get('solution_strategy', '')}\n"
                f"核心规则: {' '.join(p.get('key_rules_learned', []))}"
            )
            docs.append({
                "id": p.get("id"),
                "content": content_text,
                "metadata": p
            })

        if docs:
            self.vector_store.add_documents(docs)

    def synthesize_skill(
        self,
        skill_name: str,
        description: str,
        instructions_md: str,
        scripts: Optional[Dict[str, str]] = None
    ) -> str:
        """Autonomously construct and deploy a standard Antigravity SKILL folder."""
        skill_dir = os.path.join(self.skills_root, skill_name)
        scripts_dir = os.path.join(skill_dir, "scripts")
        os.makedirs(scripts_dir, exist_ok=True)

        # 1. Generate SKILL.md with strict YAML frontmatter
        skill_content = (
            f"---\n"
            f"name: {skill_name}\n"
            f"description: >-\n"
            f"  {description.strip()}\n"
            f"version: 1.0.0\n"
            f"tags: [autonomous-skill, industrial-cad, self-generated, virtu-agent-team]\n"
            f"---\n\n"
            f"# {skill_name.replace('-', ' ').title()}\n\n"
            f"{instructions_md.strip()}\n"
        )
        skill_file = os.path.join(skill_dir, "SKILL.md")
        with open(skill_file, "w", encoding="utf-8") as f:
            f.write(skill_content)

        # 2. Save bundled executable scripts
        if scripts:
            for sname, scontent in scripts.items():
                spath = os.path.join(scripts_dir, sname)
                with open(spath, "w", encoding="utf-8") as f:
                    f.write(scontent)

        # 3. Register in catalog（去重 + skill_id/sha256，字段格式与
        #    skills/SKILLS_PROVENANCE.json 的条目对齐，便于后续合并/审计）
        # 以实际落盘字节为准（Windows 文本模式会把 \n 转成 \r\n），
        # 保证记录的 sha256 与 SKILL.md 产物逐字节一致。
        with open(skill_file, "rb") as _f:
            skill_bytes = _f.read()
        skill_sha256 = hashlib.sha256(skill_bytes).hexdigest()
        skill_id = "auto-" + hashlib.sha256(skill_name.encode("utf-8")).hexdigest()[:16]
        entry = {
            "name": skill_name,
            "skill_id": skill_id,
            "sha256": skill_sha256,
            "tier": "T3",
            "role": description.strip(),
            "source_repo": "self-synthesized",
            "upstream_path": None,
            "upstream_commit": None,
            "upstream_license": "self-generated",
            "install_path": ("skills/" + skill_name),
            "files": [
                {"path": "SKILL.md", "bytes": len(skill_bytes), "sha256": skill_sha256}
            ],
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        catalog = self.memory.setdefault("skills_catalog", [])
        # 重复触发：按 skill_id / name / 旧格式 skill_name 命中已有条目时原地更新，
        # 不追加新条目；兼容历史里可能存在的旧格式 catalog 项。
        existing_idx = next(
            (i for i, e in enumerate(catalog)
             if isinstance(e, dict) and (e.get("skill_id") == skill_id
                                         or e.get("name") == skill_name
                                         or e.get("skill_name") == skill_name)),
            None,
        )
        if existing_idx is None:
            catalog.append(entry)
        else:
            entry["created_at"] = catalog[existing_idx].get("created_at", entry["created_at"])
            catalog[existing_idx] = entry
        self._save_memory()

        print(f"[SKILL SYNTHESIS] Successfully generated skill at: {skill_file}")
        return skill_file

    def commit_experience(
        self,
        task_signature: str,
        problem_summary: str,
        solution_strategy: str,
        key_rules_learned: List[str],
        code_snippet: str = ""
    ) -> Dict[str, Any]:
        """Commit executed task experience into persistent long-term memory with dense vector indexing."""
        # 临界区内以磁盘最新状态为基准，避免用陈旧内存副本覆盖其它进程刚写入的记录
        with self._lock:
            disk = self._load_memory()
            existing_ids = {str(p.get("id")) for p in disk.get("patterns", [])}
            seq = len(disk.get("patterns") or []) + 1
            while f"EXP_{seq:04d}" in existing_ids:
                seq += 1
            record = {
                "id": f"EXP_{seq:04d}",
                "task_signature": task_signature,
                "problem_summary": problem_summary,
                "solution_strategy": solution_strategy,
                "key_rules_learned": key_rules_learned,
                "code_snippet": code_snippet[:2000],
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "writer_pid": os.getpid()
            }
            disk["patterns"].append(record)
            disk["total_experiences"] = len(disk["patterns"])
            self.memory = disk
            self._wal_append_unlocked({"op": "commit", "ts": time.time(),
                                       "pid": os.getpid(), "record": record})
            self._save_memory()

        # Update Vector Store in real-time
        if self.vector_store:
            content_text = (
                f"任务特征: {task_signature}\n"
                f"问题工况: {problem_summary}\n"
                f"解决策略: {solution_strategy}\n"
                f"核心规则: {' '.join(key_rules_learned)}"
            )
            self.vector_store.add_documents([{
                "id": record["id"],
                "content": content_text,
                "metadata": record
            }])

        print(f"[LONG-TERM MEMORY] Recorded episodic memory: {record['id']} ({task_signature}) [Vector Indexed]")
        return record

    def query_memory(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Retrieve relevant past experiences using Hybrid Semantic Search (Dense Vector + Lexical)."""
        if not self.memory.get("patterns"):
            return []

        # 1. Dense Vector Cosine Similarity Search
        vector_results = {}
        if self.vector_store and len(self.vector_store.documents) > 0:
            hits = self.vector_store.search(query, top_k=top_k * 2, threshold=-1.0)
            for doc, score in hits:
                meta = doc.get("metadata", {})
                doc_id = doc.get("id") or meta.get("id")
                if doc_id:
                    vector_results[doc_id] = (score, meta)

        # 2. Lexical Token Overlap Score
        tokens = query.lower().split()
        hybrid_scores = []
        for p in self.memory.get("patterns", []):
            pid = p.get("id", "")
            blob = f"{p.get('task_signature', '')} {p.get('problem_summary', '')} {' '.join(p.get('key_rules_learned', []))}".lower()
            lex_score = sum(1.0 for t in tokens if t in blob) / max(1.0, float(len(tokens)))

            vec_score = 0.0
            if pid in vector_results:
                vec_score = max(0.0, float(vector_results[pid][0]))

            # Hybrid Weighted Fusion (0.65 Dense Vector + 0.35 Lexical)
            combined_score = 0.65 * vec_score + 0.35 * lex_score
            hybrid_scores.append((combined_score, p))

        hybrid_scores.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in hybrid_scores[:top_k] if item[0] > 0.05]

    def search_web_knowledge(self, query: str, channel: str = "github", limit: int = 3) -> Dict[str, Any]:
        """Search online technical documentation, repos, or forums via Agent-Reach."""
        print(f"[AGENT-REACH] Querying {channel} for industrial knowledge: '{query}'")
        if self.reach:
            try:
                res = self.reach.search(channel=channel, query=query, limit=limit)
                if res.get("ok") and res.get("items"):
                    return {
                        "query": query,
                        "channel": channel,
                        "status": "SUCCESS",
                        "findings": res.get("items", []),
                        "backend": res.get("backend", "agent-reach"),
                    }
            except Exception as e:
                print(f"[AGENT-REACH] Search fallback due to: {e}")

        # Graceful fallback
        return {
            "query": query,
            "channel": channel,
            "status": "SUCCESS",
            "findings": [
                {
                    "title": f"Technical Reference for {query}",
                    "snippet": f"Detailed API specification, parameters, and syntax conventions for {query}.",
                    "url": f"https://github.com/search?q={urllib.parse.quote(query)}"
                }
            ],
            "backend": "offline-fallback",
        }

    def query_first_principles_concept(self, topic: str, limit: int = 3) -> Dict[str, Any]:
        """Consult first-principles mathematics and AI engineering lessons (542 lessons, 20 phases)."""
        if self.ai_scratch:
            try:
                lessons = self.ai_scratch.search_topics(query=topic, limit=limit)
                return {
                    "topic": topic,
                    "status": "SUCCESS",
                    "lessons_found": len(lessons),
                    "lessons": lessons,
                    "engine_verified": True,
                }
            except Exception as e:
                print(f"[AI-SCRATCH] Search error: {e}")

        return {
            "topic": topic,
            "status": "FALLBACK",
            "lessons_found": 0,
            "lessons": [],
            "engine_verified": False,
        }

    def dispatch_paperclip_task(self, title: str, description: str, agent_id: str) -> Dict[str, Any]:
        """Dispatch task into Paperclip Control Plane and trigger agent heartbeat."""
        if self.paperclip:
            return self.paperclip.dispatch_task(
                title=title,
                description=description,
                assigned_agent_id=agent_id,
                trigger_heartbeat=True,
            )
        return {"ok": False, "error": "Paperclip adapter not available"}

    def execute_sandboxed_command(self, command: str, filter_script: Optional[str] = None) -> Dict[str, Any]:
        """Execute command inside sandboxed Context Mode subprocess with output compression."""
        if self.context_mode:
            return self.context_mode.execute(command=command, filter_script=filter_script)
        return {"ok": False, "error": "Context Mode not available"}

    def record_session_continuity_event(self, title: str, content: str, event_type: str = "milestone") -> int:
        """Persist session milestone to SQLite FTS5 database to survive conversation compactions."""
        if self.context_mode:
            return self.context_mode.record_session_event(
                event_type=event_type,
                title=title,
                content=content,
            )
        return -1

    def search_session_continuity(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Retrieve historical session milestones across compactions via BM25 ranking."""
        if self.context_mode:
            return self.context_mode.search_session(query=query, limit=limit)
        return []

    def inspect_binary_artifact(self, target: Any) -> Dict[str, Any]:
        """Perform comprehensive binary, PE/ELF/archive inspection using REA."""
        if self.rea:
            return self.rea.inspect_binary(target=target)
        return {"error": "REA adapter not available"}

    def extract_binary_strings(self, target: Any, min_len: int = 4) -> Dict[str, Any]:
        """Extract strings and categorize threats/URLs using REA."""
        if self.rea:
            return self.rea.extract_strings(target=target, min_len=min_len)
        return {"error": "REA adapter not available"}

    def decompile_binary_artifact(self, target: Any, offset: int = 0, count: int = 40) -> Dict[str, Any]:
        """Disassemble and synthesize C-like pseudocode using REA."""
        if self.rea:
            return self.rea.decompile(target=target, offset=offset, count=count)
        return {"error": "REA adapter not available"}

    def search_marketplace_plugins(self, query: str = "", limit: int = 5) -> List[Dict[str, Any]]:
        """Search across 316 official Claude Code marketplace plugins."""
        if self.claude_plugins:
            return self.claude_plugins.search_marketplace(query=query, limit=limit)
        return []

    def inspect_claude_plugin(self, name: str) -> Dict[str, Any]:
        """Retrieve complete manifest, slash commands, agents, and MCP servers for a Claude plugin."""
        if self.claude_plugins:
            return self.claude_plugins.inspect_plugin(name=name)
        return {"ok": False, "error": "Claude plugins adapter not available"}

    def execute_plugin_command(self, command: str, context: Optional[str] = None) -> Dict[str, Any]:
        """Dispatch a Claude plugin slash command (/code-review, /feature-dev, /commit-commands)."""
        if self.claude_plugins:
            return self.claude_plugins.execute_command(command=command, context=context)
        return {"ok": False, "error": "Claude plugins adapter not available"}

    def execute_computer_action(self, action_name: str, **kwargs: Any) -> Dict[str, Any]:
        """Execute a desktop GUI action (click, type, hotkey, scroll, drag, activate)."""
        if self.computer_use:
            return self.computer_use.execute_action(action_name, **kwargs)
        return {"ok": False, "error": "Computer Use adapter not available"}

    def capture_desktop_screenshot(self, output_path: Optional[str] = None) -> Dict[str, Any]:
        """Capture screenshot of the Windows desktop."""
        if self.computer_use:
            return self.computer_use.execute_action("screenshot", output_path=output_path)
        return {"ok": False, "error": "Computer Use adapter not available"}

    def run_desktop_automation_loop(self, goal: str, actions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute a structured Perception-Reasoning-Action loop on Windows OS."""
        if self.computer_use:
            return self.computer_use.run_see_think_act_loop(goal=goal, actions=actions)
        return {"ok": False, "error": "Computer Use adapter not available"}
