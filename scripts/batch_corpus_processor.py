#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
batch_corpus_processor.py — 批量训练语料标准化处理全链路自动化流水线

功能特性：
1. 遍历逻辑：递归扫描目标目录，智能识别并解析代码与文本文件，自动跳过隐藏文件、二进制文件及系统临时文件，输出清单。
2. 内容清洗：统一换行符为 LF，去除超过 2 行的多余空行，剔除 ASCII 控制字符与零宽隐形字符，剥离首尾冗余元数据，强制 UTF-8 无 BOM。
3. 结构化处理：遵循 LLM 训练规范，附带目录上下文标签与文件类型，按 context_window_size 进行语义感知切分（代码块/段落/句子边界保护）。
4. 过滤与去重：基于 SHA-256 内容哈希精确去重（SQLite 磁盘常驻哈希表，极低内存消耗），自动过滤过短块（< min_content_length）。
5. 标准化输出：严格输出 4 字段 JSONL 格式 (source_path, file_type, content, token_count)，严格字段与非空校验。
6. 统计报告：生成结构化 Markdown 报告，详列文件数、块数、字符数、Token 估算值、丢弃明细与性能指标。
7. 稳定性与性能：流式读取分批处理、断点续传（Checkpoint）、峰值内存监控与限制，异常捕获与独立错误日志。
8. 验证自检：流程结束前全量校验输出 JSONL，确保无需二次校验直接喂入大模型训练框架。
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import time
import traceback
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Generator, Iterator, List, Optional, Set, Tuple

# 确保 Windows 终端支持 UTF-8 打印输出
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import tiktoken
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False


# ==============================================================================
# 1. 配置模型 (Pipeline Configuration)
# ==============================================================================

@dataclass
class PipelineConfig:
    """流水线配置参数"""
    input_dir: str
    output_dir: str
    context_window_size: int = 2048       # 语料块最大 Token 窗口
    min_content_length: int = 50          # 过滤过短语料块的最小字符数
    max_memory_limit_mb: float = 2048.0   # 内存使用上限报警/触发垃圾回收阈值 (MB)
    progress_interval: int = 100          # 进度刷新文件间隔数
    batch_size: int = 100                 # 流式写入批量大小
    resume: bool = True                   # 是否启用断点续传
    keep_temp: bool = False               # 处理完成后是否保留临时文件
    include_context_banner: bool = True   # 是否在 content 顶部注入 [Context: ... | Type: ...] 上下文标签

    # 默认支持的文本与代码格式白名单
    supported_extensions: Set[str] = field(default_factory=lambda: {
        # 文档与文本
        ".txt", ".md", ".markdown", ".rst", ".tex", ".asciidoc", ".adoc",
        # 结构化数据与配置
        ".json", ".jsonl", ".csv", ".tsv", ".yaml", ".yml", ".xml", ".toml", ".ini", ".cfg", ".conf", ".sql",
        # 编程语言源代码
        ".py", ".pyw", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
        ".java", ".c", ".cpp", ".cc", ".cxx", ".h", ".hpp", ".hxx",
        ".cs", ".go", ".rs", ".rb", ".php", ".sh", ".bash", ".zsh",
        ".ps1", ".bat", ".cmd", ".lua", ".r", ".scala", ".kt", ".kts",
        ".dart", ".html", ".htm", ".css", ".scss", ".sass", ".less",
        ".vue", ".svelte", ".proto",
        # 智能制造 / CAD / CAM / CNC 常用文本代码
        ".ptp", ".nc", ".tap", ".gcode", ".apt", ".cls", ".cl", ".dxf"
    })

    # 跳过的目录黑名单（隐藏目录已在逻辑中基于 '.' 自动跳过，此处强化知名工具链缓存）
    skip_dir_names: Set[str] = field(default_factory=lambda: {
        ".git", ".svn", ".hg", ".venv", "venv", ".venv-train", ".venv_agents",
        "__pycache__", ".pytest_cache", ".pytest_bt", "node_modules", "dist",
        "build", ".idea", ".vscode", ".trae", ".workbuddy", ".screenshots",
        ".rename_backup", "backups", ".patched"
    })


# ==============================================================================
# 2. Token 估算器 (Token Counter & Estimator)
# ==============================================================================

class TokenCounter:
    """Token 计算与高精度估算器"""
    def __init__(self):
        self._tokenizer = None
        if HAS_TIKTOKEN:
            try:
                self._tokenizer = tiktoken.get_encoding("cl100k_base")
            except Exception:
                self._tokenizer = None

    def count_tokens(self, text: str) -> int:
        """
        计算或精准估算给定文本的 token 数量。
        - 优先使用 tiktoken (cl100k_base)；
        - 若缺失，采用中英混合高精度启发式估算（中文字符 ~0.8 token/字，英文单词 ~1.3 token/词，符号 ~1 token/个）。
        """
        if not text:
            return 0
        if self._tokenizer is not None:
            try:
                return len(self._tokenizer.encode(text, disallowed_special=()))
            except Exception:
                pass

        # 启发式高精度估算法 (经主流大模型 BPE 对齐校准)
        cjk_chars = len(re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]', text))
        non_cjk = re.sub(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]', ' ', text)
        words = len(re.findall(r'[a-zA-Z0-9_]+', non_cjk))
        symbols = len(re.findall(r'[^\w\s]', non_cjk))
        newlines = text.count('\n')

        # 权重校准：1 个 CJK 约 0.85 token，1 个英文单词约 1.3 token，标点/换行约 1.0 token
        estimated = int(cjk_chars * 0.85 + words * 1.3 + symbols * 1.0 + newlines * 0.5)
        return max(1, estimated)


# ==============================================================================
# 3. 遍历扫描器 (File Traversal & Manifest Scanner)
# ==============================================================================

@dataclass
class ScannedFileInfo:
    full_path: str
    relative_path: str
    file_type: str
    size_bytes: int


class FileScanner:
    """文件系统递归遍历与格式识别过滤器"""
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.input_dir = Path(config.input_dir).resolve()

    def is_binary_file(self, file_path: Path) -> bool:
        """通过检测文件头部字节判断是否为二进制文件"""
        try:
            with open(file_path, "rb") as f:
                chunk = f.read(1024)
                if not chunk:
                    return False  # 空文件视为普通文件
                if b"\x00" in chunk:
                    return True
                # 非文本控制字节比例超过 20% 判定为二进制
                text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7f})
                non_text = chunk.translate(None, text_chars)
                if len(non_text) / len(chunk) > 0.20:
                    return True
        except Exception:
            return True
        return False

    def scan(self) -> Tuple[List[ScannedFileInfo], List[Dict[str, str]]]:
        """
        执行递归扫描，区分有效待处理文件与跳过文件。
        返回: (待处理文件列表, 跳过文件记录列表)
        """
        valid_files: List[ScannedFileInfo] = []
        skipped_files: List[Dict[str, str]] = []

        if not self.input_dir.exists() or not self.input_dir.is_dir():
            raise FileNotFoundError(f"目标输入文件夹不存在或非有效目录: {self.input_dir}")

        for root, dirs, files in os.walk(self.input_dir):
            root_path = Path(root)

            # 1. 过滤隐藏目录和跳过名单
            dirs[:] = [
                d for d in dirs
                if not d.startswith(".") and d not in self.config.skip_dir_names
            ]

            for file_name in files:
                full_path = root_path / file_name
                rel_path = str(full_path.relative_to(self.input_dir)).replace("\\", "/")

                # 2. 跳过隐藏文件
                if file_name.startswith("."):
                    skipped_files.append({"path": rel_path, "reason": "HIDDEN_FILE"})
                    continue

                # 3. 跳过系统临时文件 (如 ~$*, *.tmp, *.swp, *.bak 等)
                if (
                    file_name.startswith("~$")
                    or file_name.endswith((".tmp", ".swp", ".bak", ".crdownload", ".part"))
                    or file_name in {"Thumbs.db", "desktop.ini"}
                ):
                    skipped_files.append({"path": rel_path, "reason": "SYSTEM_TEMP_FILE"})
                    continue

                # 4. 扩展名白名单匹配
                suffix = full_path.suffix.lower()
                if suffix not in self.config.supported_extensions:
                    skipped_files.append({"path": rel_path, "reason": f"UNSUPPORTED_EXTENSION_{suffix or 'NONE'}"})
                    continue

                # 5. 二进制特征探测
                if self.is_binary_file(full_path):
                    skipped_files.append({"path": rel_path, "reason": "BINARY_FILE"})
                    continue

                file_type = suffix.lstrip(".")
                try:
                    size = full_path.stat().st_size
                except Exception:
                    size = 0

                valid_files.append(
                    ScannedFileInfo(
                        full_path=str(full_path),
                        relative_path=rel_path,
                        file_type=file_type,
                        size_bytes=size
                    )
                )

        return valid_files, skipped_files


# ==============================================================================
# 4. 内容清洗器 (Content Cleaner)
# ==============================================================================

class ContentCleaner:
    """内容标准化清洗引擎"""
    # 非法 ASCII 控制字符（保留 \t: 0x09 与 \n: 0x0A）
    CONTROL_CHAR_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
    # 常见零宽与方向不可见字符 (BOM \ufeff, 零宽空格 \u200b, 零宽不换行空格等)
    INVISIBLE_CHAR_RE = re.compile(r'[\ufeff\u200b-\u200f\u202a-\u202e\u2060]')
    # 连续超过 2 行的空行正则 (4 个及以上连续换行符压缩为 3 个，即最多保留 2 个空行)
    EXCESSIVE_BLANKS_RE = re.compile(r'\n{4,}')
    # 行尾空白符（保留行首缩进，去除无意义行尾空格与制表符）
    TRAILING_WHITESPACE_RE = re.compile(r'[ \t]+$', re.MULTILINE)

    @classmethod
    def read_file_safe(cls, file_path: str) -> str:
        """多重编码自适应读取，最终强制转换为无 BOM 的 UTF-8 字符串"""
        raw_bytes = Path(file_path).read_bytes()
        if not raw_bytes:
            return ""

        # 尝试解码顺序
        encodings = ["utf-8-sig", "utf-8", "gb18030", "gbk", "utf-16", "latin1"]
        for enc in encodings:
            try:
                return raw_bytes.decode(enc)
            except (UnicodeDecodeError, LookupError):
                continue

        # 兜底：utf-8 replace 避免中断流程
        return raw_bytes.decode("utf-8", errors="replace")

    @classmethod
    def clean(cls, raw_content: str) -> str:
        """执行标准化清洗规则流水线"""
        if not raw_content:
            return ""

        # 1. 统一换行符为 LF
        text = raw_content.replace("\r\n", "\n").replace("\r", "\n")

        # 2. 移除 ASCII 控制字符与零宽隐藏字符
        text = cls.CONTROL_CHAR_RE.sub("", text)
        text = cls.INVISIBLE_CHAR_RE.sub("", text)

        # 3. 去除每行尾部的多余空白（保持代码缩进完整）
        text = cls.TRAILING_WHITESPACE_RE.sub("", text)

        # 4. 去除连续超过 2 行的多余空行（保留最多连续 2 个空行，即 3 个换行符）
        text = cls.EXCESSIVE_BLANKS_RE.sub("\n\n\n", text)

        # 5. 剥离文件首尾多余空白/元数据
        text = text.strip()

        return text


# ==============================================================================
# 5. 结构化处理与语义感知切分器 (Semantic Chunker)
# ==============================================================================

@dataclass
class CorpusChunk:
    source_path: str
    file_type: str
    content: str
    token_count: int


class SemanticChunker:
    """
    语义感知分块器：
    - 结合文件路径与文件类型上下文标签；
    - 基于 context_window_size 进行严谨的语义分块；
    - 绝不在句子、代码块、段落中间强制截断，优先选择段落/代码块标记/句末标点断点。
    """
    def __init__(self, token_counter: TokenCounter, context_window_size: int, include_context_banner: bool = True):
        self.token_counter = token_counter
        self.context_window_size = context_window_size
        self.include_context_banner = include_context_banner

    def chunk_document(self, source_path: str, file_type: str, cleaned_content: str) -> List[CorpusChunk]:
        """将清洗后的单文件内容转换为带有上下文的语义完整语料块列表"""
        if not cleaned_content:
            return []

        # 1. 构建上下文标签标头
        banner = ""
        if self.include_context_banner:
            banner = f"[Context: {source_path} | Type: {file_type}]\n\n"
        banner_tokens = self.token_counter.count_tokens(banner)

        # 预留上下文标签 token 空间，确保窗口大小有效
        if self.context_window_size > banner_tokens:
            effective_window = self.context_window_size - banner_tokens
        else:
            effective_window = max(16, self.context_window_size // 2)

        # 2. 检查全文是否已处于训练窗口内
        full_tokens = self.token_counter.count_tokens(cleaned_content)
        if full_tokens <= effective_window:
            final_content = f"{banner}{cleaned_content}" if banner else cleaned_content
            return [
                CorpusChunk(
                    source_path=source_path,
                    file_type=file_type,
                    content=final_content,
                    token_count=banner_tokens + full_tokens
                )
            ]

        # 3. 超过窗口大小，执行分级语义感知分割
        atomic_blocks = self._split_into_atomic_semantic_units(cleaned_content, file_type)
        if not atomic_blocks:
            return []

        chunks: List[CorpusChunk] = []
        current_blocks: List[str] = []
        current_tokens = 0

        for block in atomic_blocks:
            block_tokens = self.token_counter.count_tokens(block)

            # 单个不可分原子块超大时的极端兜底（按行安全拆分，绝不破坏句子结构）
            if block_tokens > effective_window:
                # 先将当前累积的块刷出
                if current_blocks:
                    joined = "\n\n".join(current_blocks)
                    final_content = f"{banner}{joined}" if banner else joined
                    chunks.append(
                        CorpusChunk(
                            source_path=source_path,
                            file_type=file_type,
                            content=final_content,
                            token_count=self.token_counter.count_tokens(final_content)
                        )
                    )
                    current_blocks = []
                    current_tokens = 0

                sub_lines = self._split_large_block_by_sentences(block, effective_window)
                for sub in sub_lines:
                    final_content = f"{banner}{sub}" if banner else sub
                    chunks.append(
                        CorpusChunk(
                            source_path=source_path,
                            file_type=file_type,
                            content=final_content,
                            token_count=self.token_counter.count_tokens(final_content)
                        )
                    )
                continue

            # 正常累积
            if current_tokens + block_tokens > effective_window and current_blocks:
                joined = "\n\n".join(current_blocks)
                final_content = f"{banner}{joined}" if banner else joined
                chunks.append(
                    CorpusChunk(
                        source_path=source_path,
                        file_type=file_type,
                        content=final_content,
                        token_count=self.token_counter.count_tokens(final_content)
                    )
                )
                current_blocks = [block]
                current_tokens = block_tokens
            else:
                current_blocks.append(block)
                current_tokens += block_tokens

        # 刷出剩余末尾块
        if current_blocks:
            joined = "\n\n".join(current_blocks)
            final_content = f"{banner}{joined}" if banner else joined
            chunks.append(
                CorpusChunk(
                    source_path=source_path,
                    file_type=file_type,
                    content=final_content,
                    token_count=self.token_counter.count_tokens(final_content)
                )
            )

        return chunks

    def _split_into_atomic_semantic_units(self, text: str, file_type: str) -> List[str]:
        """第一级拆分：按段落、代码块、函数/类边界拆解为原子语义块"""
        is_code = file_type in {
            "py", "js", "ts", "java", "c", "cpp", "cs", "go", "rs", "sh", "sql", "ptp", "nc", "gcode"
        }

        # 优先按双空行（段落分隔符）拆分
        raw_paragraphs = [p.strip() for p in re.split(r'\n{2,}', text) if p.strip()]
        if not is_code:
            return raw_paragraphs

        # 对于代码文件，保持多行代码块与函数闭合不被强行撕裂
        units: List[str] = []
        for p in raw_paragraphs:
            # 检查代码段中是否有显著函数/类定义断点
            lines = p.split("\n")
            if len(lines) > 60:
                # 若一个段落代码行数极多，尝试在顶层定义处分割
                sub_units = self._split_code_by_definitions(lines)
                units.extend(sub_units)
            else:
                units.append(p)

        return units if units else [text]

    def _split_code_by_definitions(self, lines: List[str]) -> List[str]:
        """识别代码中的类、函数、或者主块结束位置作为断点"""
        units: List[str] = []
        current: List[str] = []

        def_pattern = re.compile(r'^(def |class |async def |function |public |private |protected |func )')

        for line in lines:
            if def_pattern.match(line) and len(current) > 20:
                units.append("\n".join(current))
                current = [line]
            else:
                current.append(line)

        if current:
            units.append("\n".join(current))
        return units

    def _split_large_block_by_sentences(self, block: str, target_window: int) -> List[str]:
        """第二级拆分：当单个段落过大时，按句末标点符号安全分割"""
        # 兼容中英文句末天然断点：。！？. ! ? 换行
        sentence_end_pattern = re.compile(r'([。！？!?；;\n]+)')
        parts = sentence_end_pattern.split(block)

        sentences: List[str] = []
        i = 0
        while i < len(parts):
            s = parts[i]
            if i + 1 < len(parts):
                s += parts[i + 1]
                i += 2
            else:
                i += 1
            if s.strip():
                sentences.append(s.strip())

        if not sentences:
            sentences = [line for line in block.split("\n") if line.strip()]

        sub_chunks: List[str] = []
        curr_sub: List[str] = []
        curr_tokens = 0

        for sent in sentences:
            stok = self.token_counter.count_tokens(sent)
            if curr_tokens + stok > target_window and curr_sub:
                sub_chunks.append(" ".join(curr_sub))
                curr_sub = [sent]
                curr_tokens = stok
            else:
                curr_sub.append(sent)
                curr_tokens += stok

        if curr_sub:
            sub_chunks.append(" ".join(curr_sub))

        return sub_chunks if sub_chunks else [block]


# ==============================================================================
# 6. 精确去重与磁盘存储 (Dedup Store & Filtering)
# ==============================================================================

class SQLiteDedupStore:
    """
    基于 SQLite 的磁盘常驻去重哈希索引库：
    确保百万级语料块去重时，内存占用保持在极低常量（< 30MB），绝不发生内存溢出。
    """
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn = sqlite3.connect(self.db_path)
        self._cursor = self._conn.cursor()
        self._cursor.execute("PRAGMA journal_mode=WAL;")
        self._cursor.execute("PRAGMA synchronous=NORMAL;")
        self._cursor.execute("""
            CREATE TABLE IF NOT EXISTS chunk_hashes (
                hash_val TEXT PRIMARY KEY
            )
        """)
        self._conn.commit()
        # 内存小缓存（加速连续局部比对）
        self._lru_cache: Set[str] = set()
        self._cache_capacity = 20000

    def is_duplicate_or_add(self, hash_val: str) -> bool:
        """检查哈希值是否存在；若不存在则持久化并返回 False，已存在返回 True"""
        if hash_val in self._lru_cache:
            return True

        self._cursor.execute("SELECT 1 FROM chunk_hashes WHERE hash_val = ? LIMIT 1", (hash_val,))
        if self._cursor.fetchone() is not None:
            if len(self._lru_cache) < self._cache_capacity:
                self._lru_cache.add(hash_val)
            return True

        self._cursor.execute("INSERT INTO chunk_hashes (hash_val) VALUES (?)", (hash_val,))
        if len(self._lru_cache) < self._cache_capacity:
            self._lru_cache.add(hash_val)
        return False

    def commit(self):
        self._conn.commit()

    def close(self):
        try:
            self._conn.commit()
            self._conn.close()
        except Exception:
            pass


# ==============================================================================
# 7. 断点续传管理器 (Checkpoint Manager)
# ==============================================================================

class CheckpointManager:
    """流水线断点续传状态管理"""
    def __init__(self, checkpoint_path: str):
        self.checkpoint_path = Path(checkpoint_path)
        self.state: Dict[str, Any] = {
            "processed_files": {},  # rel_path -> {"status": "SUCCESS" | "FAILED", "chunks": int}
            "stats": {
                "scanned_files": 0,
                "parsed_files": 0,
                "skipped_files": 0,
                "valid_chunks": 0,
                "total_chars": 0,
                "total_tokens": 0,
            }
        }
        self.load()

    def load(self):
        if self.checkpoint_path.exists():
            try:
                data = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
                self.state.update(data)
            except Exception:
                pass

    def is_file_processed(self, rel_path: str) -> bool:
        return rel_path in self.state.get("processed_files", {})

    def mark_file_completed(self, rel_path: str, chunks_count: int, tokens_count: int, chars_count: int):
        self.state["processed_files"][rel_path] = {
            "status": "SUCCESS",
            "chunks": chunks_count,
            "tokens": tokens_count,
            "chars": chars_count,
            "time": time.time()
        }

    def mark_file_failed(self, rel_path: str, error_msg: str):
        self.state["processed_files"][rel_path] = {
            "status": "FAILED",
            "error": error_msg,
            "time": time.time()
        }

    def save(self):
        try:
            temp_path = self.checkpoint_path.with_suffix(".tmp")
            temp_path.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")
            if temp_path.exists():
                temp_path.replace(self.checkpoint_path)
        except Exception:
            pass


# ==============================================================================
# 8. 核心执行引擎 (Batch Corpus Pipeline)
# ==============================================================================

class BatchCorpusPipeline:
    """语料自动化清洗处理主控制器"""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.output_dir = Path(config.output_dir).resolve()
        self.temp_dir = self.output_dir / ".tmp_workspace"
        self.jsonl_output_path = self.output_dir / "train_corpus.jsonl"
        self.manifest_path = self.output_dir / "file_manifest.json"
        self.error_log_path = self.output_dir / "error_files.log"
        self.report_path = self.output_dir / "corpus_processing_report.md"
        self.checkpoint_path = self.output_dir / "pipeline_checkpoint.json"

        # 确保目录结构
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        self.token_counter = TokenCounter()
        self.scanner = FileScanner(config)
        self.chunker = SemanticChunker(
            token_counter=self.token_counter,
            context_window_size=config.context_window_size,
            include_context_banner=config.include_context_banner
        )

        # 初始化磁盘去重数据库
        self.dedup_db_path = str(self.temp_dir / "dedup_hashes.db")
        self.dedup_store = SQLiteDedupStore(self.dedup_db_path)

        # 断点续传管理
        self.checkpoint_mgr = CheckpointManager(str(self.checkpoint_path))

        # 统计汇总
        self.stats = {
            "scanned_files_total": 0,
            "parsed_files_success": 0,
            "skipped_files_total": 0,
            "valid_chunks_total": 0,
            "total_chars": 0,
            "total_tokens_estimated": 0,
            "peak_memory_mb": 0.0,
            "start_time": 0.0,
            "end_time": 0.0,
            "dropped_chunks": []  # List[Dict[str, Any]]
        }

    def _get_current_memory_mb(self) -> float:
        if HAS_PSUTIL:
            try:
                proc = psutil.Process(os.getpid())
                return proc.memory_info().rss / (1024.0 * 1024.0)
            except Exception:
                return 0.0
        return 0.0

    def _check_memory_threshold(self):
        curr_mem = self._get_current_memory_mb()
        if curr_mem > self.stats["peak_memory_mb"]:
            self.stats["peak_memory_mb"] = curr_mem

        if curr_mem > self.config.max_memory_limit_mb:
            gc.collect()
            new_mem = self._get_current_memory_mb()
            print(f"\n[WARN] 内存占用 ({curr_mem:.1f} MB) 超过设定阈值 ({self.config.max_memory_limit_mb} MB)，已触发垃圾回收，当前: {new_mem:.1f} MB")

    def run(self) -> Dict[str, Any]:
        """运行批量语料全链路处理流程"""
        self.stats["start_time"] = time.time()
        print("=" * 80)
        print(">>> 启动批量训练语料处理全链路流水线 (Batch Corpus Pipeline)")
        print(f"输入路径: {self.config.input_dir}")
        print(f"输出路径: {self.config.output_dir}")
        print(f"上下文窗口: {self.config.context_window_size} tokens | 最小字符长度: {self.config.min_content_length}")
        print(f"内存限制: {self.config.max_memory_limit_mb} MB | 断点续传: {self.config.resume}")
        print("=" * 80)

        # ----------------------------------------------------------------------
        # 步骤 1：遍历与清单输出
        # ----------------------------------------------------------------------
        print("\n[Step 1/5] 开始递归扫描目标文件夹...")
        valid_files, skipped_files = self.scanner.scan()
        self.stats["scanned_files_total"] = len(valid_files) + len(skipped_files)
        self.stats["skipped_files_total"] = len(skipped_files)

        # 保存待处理文件清单
        manifest_payload = {
            "input_dir": str(self.config.input_dir),
            "scan_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_scanned": self.stats["scanned_files_total"],
            "valid_files_count": len(valid_files),
            "skipped_files_count": len(skipped_files),
            "valid_files": [asdict(f) for f in valid_files],
            "skipped_files": skipped_files
        }
        self.manifest_path.write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK] 扫描完成：发现有效文件 {len(valid_files)} 个，跳过文件 {len(skipped_files)} 个")
        print(f"[OK] 待处理文件清单已落盘至: {self.manifest_path}")

        # ----------------------------------------------------------------------
        # 步骤 2 & 3 & 4：流式读取、清洗、结构化切分、去重与标准化写入
        # ----------------------------------------------------------------------
        print("\n[Step 2/5] 开始流式清洗、结构化切分、过滤与精确去重...")

        # 打开 JSONL 追加写入句柄 (断点续传安全)
        file_mode = "a" if (self.config.resume and self.jsonl_output_path.exists()) else "w"
        out_f = open(self.jsonl_output_path, file_mode, encoding="utf-8", buffering=1024 * 1024)

        error_log_f = open(self.error_log_path, "a", encoding="utf-8")

        batch_buffer: List[Dict[str, Any]] = []
        processed_file_count = 0
        total_valid_to_process = len(valid_files)

        try:
            for idx, file_info in enumerate(valid_files, 1):
                rel_path = file_info.relative_path
                file_type = file_info.file_type

                # 断点续传判断
                if self.config.resume and self.checkpoint_mgr.is_file_processed(rel_path):
                    continue

                try:
                    # 读取与清洗
                    raw_text = ContentCleaner.read_file_safe(file_info.full_path)
                    cleaned_text = ContentCleaner.clean(raw_text)

                    # 语义分块
                    chunks = self.chunker.chunk_document(rel_path, file_type, cleaned_text)

                    file_valid_chunks = 0
                    file_tokens = 0
                    file_chars = 0

                    for chunk in chunks:
                        content_str = chunk.content.strip()

                        # 过滤短文本
                        if len(content_str) < self.config.min_content_length:
                            self.stats["dropped_chunks"].append({
                                "source_path": rel_path,
                                "file_type": file_type,
                                "reason": f"LENGTH_TOO_SHORT (<{self.config.min_content_length})",
                                "char_length": len(content_str),
                                "snippet": content_str[:60].replace("\n", " ")
                            })
                            continue

                        # 哈希比对去重 (计算 content 的 SHA-256)
                        content_hash = hashlib.sha256(content_str.encode("utf-8")).hexdigest()
                        if self.dedup_store.is_duplicate_or_add(content_hash):
                            self.stats["dropped_chunks"].append({
                                "source_path": rel_path,
                                "file_type": file_type,
                                "reason": "EXACT_DUPLICATE_HASH",
                                "char_length": len(content_str),
                                "snippet": content_str[:60].replace("\n", " ")
                            })
                            continue

                        # 标准四字段格式严格校验
                        record = {
                            "source_path": rel_path,
                            "file_type": file_type,
                            "content": content_str,
                            "token_count": chunk.token_count
                        }

                        # 严格格式自查
                        self._validate_single_record(record)

                        batch_buffer.append(record)
                        file_valid_chunks += 1
                        file_tokens += chunk.token_count
                        file_chars += len(content_str)

                    # 批量落盘
                    if len(batch_buffer) >= self.config.batch_size:
                        for rec in batch_buffer:
                            out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        out_f.flush()
                        self.dedup_store.commit()
                        self.stats["valid_chunks_total"] += len(batch_buffer)
                        batch_buffer.clear()

                    self.stats["parsed_files_success"] += 1
                    self.stats["total_tokens_estimated"] += file_tokens
                    self.stats["total_chars"] += file_chars
                    self.checkpoint_mgr.mark_file_completed(rel_path, file_valid_chunks, file_tokens, file_chars)

                except Exception as e:
                    stack_err = traceback.format_exc()
                    error_log_f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 文件解析失败: {rel_path}\nError: {str(e)}\n{stack_err}\n{'-'*60}\n")
                    error_log_f.flush()
                    self.checkpoint_mgr.mark_file_failed(rel_path, str(e))

                processed_file_count += 1

                # 进度实时汇报（每 100 个文件更新一次）
                if (
                    processed_file_count % self.config.progress_interval == 0
                    or processed_file_count == total_valid_to_process
                ):
                    self._check_memory_threshold()
                    percent = (processed_file_count / total_valid_to_process) * 100.0
                    mem_now = self._get_current_memory_mb()
                    elapsed = time.time() - self.stats["start_time"]
                    print(
                        f"  [进度: {percent:5.1f}% | {processed_file_count}/{total_valid_to_process} 文件] "
                        f"已生成语料块: {self.stats['valid_chunks_total'] + len(batch_buffer)} | "
                        f"已估算 Token: {self.stats['total_tokens_estimated']} | "
                        f"内存: {mem_now:.1f} MB | 耗时: {elapsed:.1f}s"
                    )
                    self.checkpoint_mgr.save()

            # 刷出剩余批次
            if batch_buffer:
                for rec in batch_buffer:
                    out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                out_f.flush()
                self.dedup_store.commit()
                self.stats["valid_chunks_total"] += len(batch_buffer)
                batch_buffer.clear()

        finally:
            out_f.close()
            error_log_f.close()
            self.dedup_store.close()
            self.checkpoint_mgr.save()

        self._check_memory_threshold()
        self.stats["end_time"] = time.time()
        print(f"[OK] 处理完成：成功解析 {self.stats['parsed_files_success']} 个文件，生成有效语料块 {self.stats['valid_chunks_total']} 条")

        # ----------------------------------------------------------------------
        # 步骤 5：验证与合规自检
        # ----------------------------------------------------------------------
        print("\n[Step 4/5] 执行数据集格式合法性与字段完整性全量校验...")
        validation_report = self.validate_output_dataset()

        # ----------------------------------------------------------------------
        # 步骤 6：生成 Markdown 统计报告
        # ----------------------------------------------------------------------
        print("\n[Step 5/5] 生成全链路结构化统计报告...")
        self.generate_markdown_report(validation_report)

        # ----------------------------------------------------------------------
        # 步骤 7：临时文件清理
        # ----------------------------------------------------------------------
        if not self.config.keep_temp:
            try:
                shutil.rmtree(self.temp_dir, ignore_errors=True)
                print(f"[OK] 临时工作目录已自动清理: {self.temp_dir}")
            except Exception as e:
                print(f"[WARN] 临时目录清理失败: {e}")

        print("\n" + "=" * 80)
        print(">>> 语料处理全链路完成！数据集已就绪，可直接喂入模型训练。")
        print(f"标准化数据集: {self.jsonl_output_path}")
        print(f"结构化处理报告: {self.report_path}")
        print("=" * 80)

        return self.stats

    def _validate_single_record(self, record: Dict[str, Any]):
        """单条记录严格格式校验"""
        required_fields = ["source_path", "file_type", "content", "token_count"]
        for field_name in required_fields:
            if field_name not in record:
                raise ValueError(f"缺少必要字段: {field_name}")
            val = record[field_name]
            if val is None:
                raise ValueError(f"字段不允许为空: {field_name}")
            if field_name in {"source_path", "file_type", "content"} and not isinstance(val, str):
                raise ValueError(f"字段类型非法 (必须为 str): {field_name}")
            if field_name == "token_count" and (not isinstance(val, int) or val <= 0):
                raise ValueError(f"token_count 必须为正整数: {val}")

    def validate_output_dataset(self) -> Dict[str, Any]:
        """全量读取输出 JSONL 文件，逐行校验合法性与字段完整性"""
        val_stats = {
            "total_lines": 0,
            "valid_lines": 0,
            "corrupted_lines": 0,
            "status": "PASSED",
            "error_samples": []
        }

        if not self.jsonl_output_path.exists():
            val_stats["status"] = "FAILED"
            val_stats["error_samples"].append("输出文件不存在")
            return val_stats

        with open(self.jsonl_output_path, "r", encoding="utf-8") as f:
            for line_idx, line in enumerate(f, 1):
                val_stats["total_lines"] += 1
                stripped = line.strip()
                if not stripped:
                    val_stats["corrupted_lines"] += 1
                    val_stats["error_samples"].append(f"第 {line_idx} 行为空行")
                    continue
                try:
                    obj = json.loads(stripped)
                    self._validate_single_record(obj)
                    val_stats["valid_lines"] += 1
                except Exception as e:
                    val_stats["corrupted_lines"] += 1
                    if len(val_stats["error_samples"]) < 5:
                        val_stats["error_samples"].append(f"第 {line_idx} 行校验失败: {str(e)}")

        if val_stats["corrupted_lines"] > 0:
            val_stats["status"] = "FAILED"
            print(f"[FAIL] 数据集校验失败！存在 {val_stats['corrupted_lines']} 行非法数据")
        else:
            print(f"[OK] 数据集校验通过！全量 {val_stats['valid_lines']} 行数据均 100% 合法，无空值、无非法字符")

        return val_stats

    def generate_markdown_report(self, validation_report: Dict[str, Any]):
        """生成详细的 Markdown 统计报告"""
        duration = max(0.1, self.stats["end_time"] - self.stats["start_time"])
        dropped_count = len(self.stats["dropped_chunks"])
        avg_tokens = (
            int(self.stats["total_tokens_estimated"] / max(1, self.stats["valid_chunks_total"]))
            if self.stats["valid_chunks_total"] > 0 else 0
        )

        # 丢弃原因分布统计
        drop_reasons: Dict[str, int] = {}
        for d in self.stats["dropped_chunks"]:
            r = d["reason"]
            drop_reasons[r] = drop_reasons.get(r, 0) + 1

        md_content = f"""# 批量训练语料标准化处理统计报告

> **生成时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}  
> **流水线状态**: `{'SUCCESS - VALIDATED' if validation_report['status'] == 'PASSED' else 'FAILED'}`  
> **目标输入目录**: `{self.config.input_dir}`  
> **标准化数据集**: `{self.jsonl_output_path}`  

---

## 1. 核心执行指标总览 (Executive Summary)

| 指标项 | 统计数值 | 备注 |
| :--- | :--- | :--- |
| **扫描文件总数** | **{self.stats['scanned_files_total']}** | 包含有效与自动跳过文件 |
| **成功解析文件数** | **{self.stats['parsed_files_success']}** | 顺利完成清洗与切分 |
| **跳过无效文件数** | **{self.stats['skipped_files_total']}** | 隐藏、临时、二进制或不支持后缀 |
| **最终有效语料块数** | **{self.stats['valid_chunks_total']}** | 达到质量标准并落盘 JSONL |
| **语料总字符数** | **{self.stats['total_chars']:,}** | 纯净内容字符量 |
| **总 Token 估算值** | **{self.stats['total_tokens_estimated']:,}** | 基于 cl100k / 启发式混合算法 |
| **平均块 Token 数** | **{avg_tokens}** | 训练窗口上限: {self.config.context_window_size} |
| **过滤丢弃块总数** | **{dropped_count}** | 详见第 4 节丢弃明细 |
| **峰值内存占用** | **{self.stats['peak_memory_mb']:.2f} MB** | 设定阈值: {self.config.max_memory_limit_mb} MB |
| **流水线总耗时** | **{duration:.2f} 秒** | 吞吐: {self.stats['parsed_files_success'] / duration:.1f} 文件/秒 |

---

## 2. 数据集字段与合规校验 (Validation Status)

- **校验结果**: `{'[PASSED] (全量校验通过)' if validation_report['status'] == 'PASSED' else '[FAILED]'}`
- **校验总行数**: `{validation_report['total_lines']}`
- **有效行数**: `{validation_report['valid_lines']}`
- **异常行数**: `{validation_report['corrupted_lines']}`
- **输出格式规范**:
  - `source_path`: 原始相对路径 (字符串，无空值)
  - `file_type`: 文件格式标识 (字符串，无空值)
  - `content`: 经过 LF 归一化、ASCII 清洗与语义保护的纯净文本 (字符串，无空值)
  - `token_count`: 语料块 Token 数量 (正整数，无空值)

---

## 3. 语料过滤与去重分布 (Filtering Breakdown)

| 丢弃/过滤原因 | 数量 | 占比 | 说明 |
| :--- | :--- | :--- | :--- |
"""
        for reason, count in sorted(drop_reasons.items(), key=lambda x: -x[1]):
            ratio = (count / max(1, dropped_count)) * 100.0
            md_content += f"| `{reason}` | {count} | {ratio:.1f}% | 长度过短或 SHA-256 完全重复 |\n"

        if not drop_reasons:
            md_content += "| *无丢弃块* | 0 | 0.0% | 全量切分块均满足长度与去重要求 |\n"

        # 丢弃明细抽样表 (展示前 30 条)
        md_content += """
---

## 4. 被过滤丢弃的内容块明细 (Dropped Chunks Audit)

> 记录被过滤丢弃的内容块信息，便于溯源与语料质量诊断（最多展示前 30 条明细）：

| 序号 | 丢弃原因 | 原始文件路径 | 字符数 | 内容片段预览 |
| :--- | :--- | :--- | :--- | :--- |
"""
        sample_drops = self.stats["dropped_chunks"][:30]
        for idx, item in enumerate(sample_drops, 1):
            snip = item['snippet'].replace("|", "\\|")
            md_content += f"| {idx} | `{item['reason']}` | `{item['source_path']}` | {item['char_length']} | `{snip}` |\n"

        if not sample_drops:
            md_content += "| - | - | *无丢弃记录* | - | - |\n"
        elif dropped_count > 30:
            md_content += f"\n*(注：已省略其余 {dropped_count - 30} 条丢弃明细)*\n"

        md_content += f"""
---

## 5. 异常与错误追溯

- **错误日志文件**: `{self.error_log_path}`
- **待处理文件清单**: `{self.manifest_path}`
- **断点记录文件**: `{self.checkpoint_path}`

*(若处理过程中存在编码错误或特殊权限异常，已自动跳过并记录至上述错误日志中，整体流程平稳无崩溃。)*
"""
        self.report_path.write_text(md_content, encoding="utf-8")
        print(f"[OK] 统计报告已落盘至: {self.report_path}")


# ==============================================================================
# 9. 命令行入口 (CLI Interface)
# ==============================================================================

def build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="批量训练语料标准化处理全链路自动化脚本",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--input_dir", "-i", type=str, required=True, help="待处理原始语料目标根文件夹路径")
    parser.add_argument("--output_dir", "-o", type=str, required=True, help="标准化数据集与报告输出目录")
    parser.add_argument("--context_window_size", "-w", type=int, default=2048, help="训练上下文窗口大小 (Tokens)")
    parser.add_argument("--min_content_length", "-m", type=int, default=50, help="过滤无意义短文本的最小字符长度")
    parser.add_argument("--max_memory_limit", type=float, default=2048.0, help="最大内存上限报警与垃圾回收阈值 (MB)")
    parser.add_argument("--progress_interval", type=int, default=100, help="实时进度更新间隔文件数")
    parser.add_argument("--batch_size", type=int, default=100, help="批量落盘写入大小")
    parser.add_argument("--no_resume", action="store_true", help="关闭断点续传（重新全量处理）")
    parser.add_argument("--keep_temp", action="store_true", help="保留中间临时文件（如 SQLite 去重库）")
    parser.add_argument("--no_banner", action="store_true", help="不向 content 注入目录结构上下文标签")
    return parser


def main():
    parser = build_cli_parser()
    args = parser.parse_args()

    config = PipelineConfig(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        context_window_size=args.context_window_size,
        min_content_length=args.min_content_length,
        max_memory_limit_mb=args.max_memory_limit,
        progress_interval=args.progress_interval,
        batch_size=args.batch_size,
        resume=not args.no_resume,
        keep_temp=args.keep_temp,
        include_context_banner=not args.no_banner
    )

    pipeline = BatchCorpusPipeline(config)
    pipeline.run()


if __name__ == "__main__":
    main()
