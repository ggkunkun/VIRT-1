# -*- coding: utf-8 -*-
"""
test_batch_corpus_processor.py — 针对批量训练语料处理流水线 8 大要求的全量单元测试与集成测试
"""

import json
import os
import shutil
import tempfile
from pathlib import Path
import pytest

from scripts.batch_corpus_processor import (
    BatchCorpusPipeline,
    CheckpointManager,
    ContentCleaner,
    CorpusChunk,
    FileScanner,
    PipelineConfig,
    SemanticChunker,
    SQLiteDedupStore,
    TokenCounter,
)


@pytest.fixture
def temp_env():
    """创建临时输入与输出目录"""
    temp_dir = tempfile.mkdtemp(prefix="test_corpus_")
    input_dir = Path(temp_dir) / "input"
    output_dir = Path(temp_dir) / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    yield input_dir, output_dir

    shutil.rmtree(temp_dir, ignore_errors=True)


def test_content_cleaner_line_endings_and_blanks():
    """测试要求 2：换行符统一为 LF、去除连续超过 2 行的空行、保留缩进"""
    raw = "def hello():\r\n    print('A')\r\n\r\n\r\n\r\n\r\n    return True\r"
    cleaned = ContentCleaner.clean(raw)
    assert "\r" not in cleaned
    assert "\n" in cleaned
    # 不允许连续超过 2 个空行 (即最多 3 个 \n)
    assert "\n\n\n\n" not in cleaned
    assert "    return True" in cleaned  # 保留缩进


def test_content_cleaner_control_characters_and_invisible():
    """测试要求 2：移除控制字符与不可见字符（保留 \\t 和 \\n）"""
    raw = "\ufeff\u200bHello\x00\x01\x07World\tCode\nLine 2\x7f\u200e"
    cleaned = ContentCleaner.clean(raw)
    assert cleaned.startswith("Hello")
    assert "World\tCode\nLine 2" in cleaned
    assert "\x00" not in cleaned
    assert "\x01" not in cleaned
    assert "\x7f" not in cleaned
    assert "\ufeff" not in cleaned
    assert "\u200b" not in cleaned


def test_content_cleaner_gbk_decoding(temp_env):
    """测试要求 2：GBK / GB18030 工业常见编码自动检测转 UTF-8"""
    input_dir, _ = temp_env
    gbk_file = input_dir / "gbk_test.txt"
    chinese_text = "智能制造与数控机床CADCAM流水线处理指令集。"
    gbk_file.write_bytes(chinese_text.encode("gbk"))

    read_text = ContentCleaner.read_file_safe(str(gbk_file))
    cleaned = ContentCleaner.clean(read_text)
    assert "智能制造与数控机床CADCAM" in cleaned


def test_file_scanner_filtering(temp_env):
    """测试要求 1：递归扫描、支持格式白名单、跳过隐藏/临时/二进制文件"""
    input_dir, output_dir = temp_env

    # 1. 有效文本与代码文件
    (input_dir / "sub1").mkdir(parents=True, exist_ok=True)
    (input_dir / "test.txt").write_text("Valid text content for test.", encoding="utf-8")
    (input_dir / "sub1" / "script.py").write_text("print('hello world')", encoding="utf-8")
    (input_dir / "sub1" / "data.json").write_text('{"key": "value"}', encoding="utf-8")

    # 2. 隐藏文件与目录
    (input_dir / ".hidden_file.txt").write_text("Hidden file content", encoding="utf-8")
    (input_dir / ".git").mkdir()
    (input_dir / ".git" / "config").write_text("git config", encoding="utf-8")

    # 3. 系统临时文件
    (input_dir / "~$temp_doc.tmp").write_text("Temp doc", encoding="utf-8")
    (input_dir / "editor.swp").write_text("Vim swap", encoding="utf-8")
    (input_dir / "Thumbs.db").write_text("Thumbnail", encoding="utf-8")

    # 4. 二进制文件
    (input_dir / "binary.bin").write_bytes(b"\x00\x01\x02\x03\x00\x05BinaryData")

    config = PipelineConfig(input_dir=str(input_dir), output_dir=str(output_dir))
    scanner = FileScanner(config)
    valid_files, skipped_files = scanner.scan()

    valid_rel_paths = {f.relative_path for f in valid_files}
    assert "test.txt" in valid_rel_paths
    assert "sub1/script.py" in valid_rel_paths
    assert "sub1/data.json" in valid_rel_paths

    assert ".hidden_file.txt" not in valid_rel_paths
    assert ".git/config" not in valid_rel_paths
    assert "~$temp_doc.tmp" not in valid_rel_paths
    assert "editor.swp" not in valid_rel_paths
    assert "binary.bin" not in valid_rel_paths

    skipped_reasons = {s["reason"] for s in skipped_files}
    assert "HIDDEN_FILE" in skipped_reasons
    assert "SYSTEM_TEMP_FILE" in skipped_reasons
    assert any("BINARY" in r or "UNSUPPORTED" in r for r in skipped_reasons)


def test_semantic_chunker_context_and_window():
    """测试要求 3：携带上下文标签、语义感知分割（不破坏句子/代码块）"""
    token_counter = TokenCounter()
    chunker = SemanticChunker(
        token_counter=token_counter,
        context_window_size=60,  # 设定较小窗口测试触发分割
        include_context_banner=True
    )

    source_path = "modules/cam_kernel.py"
    file_type = "py"
    cleaned_code = (
        "def compute_toolpath(part_id: int):\n"
        "    '''计算刀具轨迹段落一'''\n"
        "    path = [0.0, 1.0, 2.0]\n"
        "    return path\n\n"
        "def postprocess_gcode(path: list):\n"
        "    '''后处理 G 码段落二'''\n"
        "    gcode = ['G00 X0 Y0', 'G01 Z-5.0 F200']\n"
        "    return gcode\n"
    )

    chunks = chunker.chunk_document(source_path, file_type, cleaned_code)
    assert len(chunks) >= 1
    for ch in chunks:
        assert f"[Context: {source_path} | Type: {file_type}]" in ch.content
        assert ch.token_count > 0
        assert ch.token_count <= 80  # 保证在窗口范围内


def test_sqlite_dedup_store(temp_env):
    """测试要求 4：精确去重与哈希比对"""
    _, output_dir = temp_env
    db_path = str(output_dir / "test_dedup.db")
    store = SQLiteDedupStore(db_path)

    hash1 = "abc123456789"
    hash2 = "def987654321"

    assert store.is_duplicate_or_add(hash1) is False
    assert store.is_duplicate_or_add(hash1) is True  # 第二次即判定为重复
    assert store.is_duplicate_or_add(hash2) is False

    store.close()


def test_full_pipeline_end_to_end(temp_env):
    """端到端集成测试：全链路自动化流程验证（要求 1~8 全覆盖）"""
    input_dir, output_dir = temp_env

    # 准备多样性语料测试集
    doc1 = (
        "# 智能制造与 CNC 编程规范指南\n\n"
        "本规范涵盖五轴数控加工、车铣复合中心及工业机器人的标准加工语料库。" * 3 + "\n\n"
        "## 1. 坐标系与安全平面\n\n"
        "机床编程必须严格对齐工件坐标系 WCS 与机床参考点 MCS。\n"
        "所有退刀与快速进给 (G00) 必须经过安全平面，严禁干涉与撞刀。"
    )
    (input_dir / "guide.md").write_text(doc1, encoding="utf-8")

    # 准备重复内容测试去重
    (input_dir / "guide_duplicate.md").write_text(doc1, encoding="utf-8")

    # 准备过短文本测试过滤 (< 50 字符)
    (input_dir / "short.txt").write_text("短文本。", encoding="utf-8")

    # 准备 Python 代码文件
    code1 = (
        "import math\n\n"
        "def calculate_spindle_speed(cutting_speed: float, tool_diameter: float) -> int:\n"
        "    '''根据切削速度与刀具直径计算主轴转速 n = (Vc * 1000) / (pi * D)'''\n"
        "    if tool_diameter <= 0:\n"
        "        raise ValueError('刀具直径必须大于 0')\n"
        "    speed = (cutting_speed * 1000.0) / (math.pi * tool_diameter)\n"
        "    return int(round(speed))\n"
    )
    (input_dir / "machining_calc.py").write_text(code1, encoding="utf-8")

    config = PipelineConfig(
        input_dir=str(input_dir),
        output_dir=str(output_dir),
        context_window_size=512,
        min_content_length=50,
        max_memory_limit_mb=1024.0,
        progress_interval=1,
        batch_size=5,
        resume=True
    )

    pipeline = BatchCorpusPipeline(config)
    stats = pipeline.run()

    # 验证输出文件存在性
    jsonl_file = output_dir / "train_corpus.jsonl"
    manifest_file = output_dir / "file_manifest.json"
    report_file = output_dir / "corpus_processing_report.md"

    assert jsonl_file.exists()
    assert manifest_file.exists()
    assert report_file.exists()

    # 验证 JSONL 每一行严格包含四个字段无空值
    records = []
    with open(jsonl_file, "r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line.strip())
            assert "source_path" in rec and rec["source_path"]
            assert "file_type" in rec and rec["file_type"]
            assert "content" in rec and len(rec["content"]) >= 50
            assert "token_count" in rec and rec["token_count"] > 0
            records.append(rec)

    assert len(records) > 0

    # 验证去重有效：guide_duplicate.md 的内容不应在最终有效语料中重复
    contents = [r["content"] for r in records]
    assert len(contents) == len(set(contents))

    # 验证报告内容包含核心指标
    report_text = report_file.read_text(encoding="utf-8")
    assert "核心执行指标总览" in report_text
    assert "扫描文件总数" in report_text
    assert "最终有效语料块数" in report_text
    assert "PASSED" in report_text
    assert "被过滤丢弃的内容块明细" in report_text


def test_checkpoint_resume_mechanism(temp_env):
    """测试要求 6：断点续传能力（中断后重启自动跳过已处理文件，不产生重复语料）"""
    input_dir, output_dir = temp_env

    # 创建 3 个独立文件
    (input_dir / "f1.txt").write_text("这是第一个独立文档内容，用于测试断点续传机制第一阶段。" * 2, encoding="utf-8")
    (input_dir / "f2.txt").write_text("这是第二个独立文档内容，用于测试断点续传机制第二阶段。" * 2, encoding="utf-8")
    (input_dir / "f3.txt").write_text("这是第三个独立文档内容，用于测试断点续传机制第三阶段。" * 2, encoding="utf-8")

    config = PipelineConfig(
        input_dir=str(input_dir),
        output_dir=str(output_dir),
        context_window_size=1024,
        min_content_length=50,
        resume=True,
        keep_temp=True  # 保留 temp 用于连续测试
    )

    # 阶段 1：模拟先处理 f1.txt，写入 checkpoint
    chk_mgr = CheckpointManager(str(output_dir / "pipeline_checkpoint.json"))
    chk_mgr.mark_file_completed("f1.txt", chunks_count=1, tokens_count=40, chars_count=80)
    chk_mgr.save()

    # 预先向 output.jsonl 写入 f1 的模拟语料
    out_jsonl = output_dir / "train_corpus.jsonl"
    with open(out_jsonl, "w", encoding="utf-8") as f:
        f.write(json.dumps({
            "source_path": "f1.txt",
            "file_type": "txt",
            "content": "预先写入的 f1 语料内容，用于验证断点续传不会重复写入该文件！",
            "token_count": 30
        }, ensure_ascii=False) + "\n")

    # 阶段 2：启动流水线，开启 resume=True
    pipeline = BatchCorpusPipeline(config)
    stats = pipeline.run()

    # 验证 f1 被跳过，f2 和 f3 被正常处理
    assert chk_mgr.is_file_processed("f1.txt")
    assert pipeline.checkpoint_mgr.is_file_processed("f2.txt")
    assert pipeline.checkpoint_mgr.is_file_processed("f3.txt")

    # 统计最终输出行数：应为 1 (预先) + 2 (新增) = 3 条
    with open(out_jsonl, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    assert len(lines) == 3


def test_error_handling_and_logging(temp_env, monkeypatch):
    """测试要求 7：单文件异常捕获，流程不崩溃，记录至 error_files.log"""
    input_dir, output_dir = temp_env

    (input_dir / "good.txt").write_text("正常文件内容，确保流水线在单个异常后仍能成功继续完成。" * 2, encoding="utf-8")
    (input_dir / "bad.txt").write_text("故意触发异常的文件内容。" * 2, encoding="utf-8")

    # 模拟在读取 bad.txt 时抛出 PermissionError
    orig_read = ContentCleaner.read_file_safe
    def mock_read(path):
        if "bad.txt" in path:
            raise PermissionError("模拟操作系统文件权限锁定异常")
        return orig_read(path)

    monkeypatch.setattr(ContentCleaner, "read_file_safe", mock_read)

    config = PipelineConfig(
        input_dir=str(input_dir),
        output_dir=str(output_dir),
        context_window_size=1024,
        min_content_length=50,
        resume=False
    )

    pipeline = BatchCorpusPipeline(config)
    stats = pipeline.run()

    # 验证 good.txt 处理成功，bad.txt 记录到错误日志
    assert stats["parsed_files_success"] == 1
    error_log = output_dir / "error_files.log"
    assert error_log.exists()
    log_content = error_log.read_text(encoding="utf-8")
    assert "bad.txt" in log_content
    assert "模拟操作系统文件权限锁定异常" in log_content
