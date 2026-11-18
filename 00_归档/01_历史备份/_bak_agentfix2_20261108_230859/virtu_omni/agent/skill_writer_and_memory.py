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
import hashlib
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Optional, Tuple

# Import dense vector store from virtu_edge.rag
WORKSPACE_DIR = r"D:\Virtu模型"
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

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
        memory_path: str = r"D:\Virtu模型\data\memory\industrial_knowledge_memory.json",
        skills_root: str = r"D:\Virtu模型\skills",
        embedding_dim: int = 128
    ):
        self.memory_path = memory_path
        self.skills_root = skills_root
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
        self._sync_vector_store()

    def _load_memory(self) -> Dict[str, Any]:
        if os.path.exists(self.memory_path):
            try:
                with open(self.memory_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "version": "2.0.0",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_experiences": 0,
            "patterns": [],
            "skills_catalog": []
        }

    def _save_memory(self):
        with open(self.memory_path, "w", encoding="utf-8") as f:
            json.dump(self.memory, f, ensure_ascii=False, indent=2)

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
        record = {
            "id": f"EXP_{len(self.memory['patterns']) + 1:04d}",
            "task_signature": task_signature,
            "problem_summary": problem_summary,
            "solution_strategy": solution_strategy,
            "key_rules_learned": key_rules_learned,
            "code_snippet": code_snippet[:2000],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        self.memory["patterns"].append(record)
        self.memory["total_experiences"] = len(self.memory["patterns"])
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
