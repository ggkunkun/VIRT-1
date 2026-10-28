"""Unit tests for Code Preprocessing Pipeline."""

import os
import tempfile
from virtu_code.config import PreprocessingConfig
from virtu_code.preprocessing.language_detect import LanguageDetector
from virtu_code.preprocessing.ast_cleaner import CodeCleaner
from virtu_code.preprocessing.pipeline import CodePreprocessingPipeline


def test_language_detection() -> None:
    valid, lang, _ = LanguageDetector.classify_file("src/model.py")
    assert valid is True
    assert lang == "python"

    valid, lang, _ = LanguageDetector.classify_file("pkg/server.go")
    assert valid is True
    assert lang == "go"

    valid, lang, _ = LanguageDetector.classify_file("src/main.rs")
    assert valid is True
    assert lang == "rust"

    # Dependency path
    valid, _, reason = LanguageDetector.classify_file("node_modules/pkg/index.js")
    assert valid is False
    assert "DEPENDENCY" in reason

    # Binary extension
    valid, _, reason = LanguageDetector.classify_file("src/app.exe")
    assert valid is False
    assert "BINARY" in reason

    # Non-code file
    valid, _, reason = LanguageDetector.classify_file("README.md")
    assert valid is False
    assert "NON_CODE" in reason


def test_binary_content_detection() -> None:
    # Null byte
    assert LanguageDetector.is_binary_content(b"Hello\x00World") is True
    # Clean text
    assert LanguageDetector.is_binary_content(b"def add(a, b):\n    return a + b\n") is False


def test_indentation_and_blank_lines() -> None:
    raw = "\tdef foo():\r\n\t\treturn 1\r\n\n\n\n\n"
    normalized = CodeCleaner.normalize_line_endings_and_indentation(raw, tab_size=4)
    assert "\t" not in normalized
    assert "\r" not in normalized
    assert "    def foo():\n        return 1" in normalized
    # Consecutive blank lines collapsed
    assert "\n\n\n" not in normalized


def test_comment_separation_python() -> None:
    code = (
        "# File header\n"
        "def compute(x: int) -> int:\n"
        "    # Step 1\n"
        "    return x * 2 # double\n"
    )
    cleaned, comments = CodeCleaner.separate_comments_and_code(code, "python")
    assert "def compute" in cleaned
    assert len(comments) >= 2
    assert "File header" in comments
    assert "Step 1" in comments


def test_comment_separation_c_family() -> None:
    code = (
        "// Header comment\n"
        "int main() {\n"
        "    /* block comment */\n"
        "    return 0; // return zero\n"
        "}\n"
    )
    cleaned, comments = CodeCleaner.separate_comments_and_code(code, "cpp")
    assert "int main()" in cleaned
    assert "Header comment" in comments
    assert "block comment" in comments
    assert "return zero" in comments


def test_syntax_integrity_check() -> None:
    # Valid Python
    valid, reason = CodeCleaner.verify_syntax_integrity("x = 1 + 2\n", "python")
    assert valid is True
    assert reason == "AST_PARSE_SUCCESS"

    # Invalid Python
    invalid, reason = CodeCleaner.verify_syntax_integrity("def foo(:\n", "python")
    assert invalid is False
    assert "AST_SYNTAX_ERROR" in reason

    # Valid Java/C++
    valid_c, _ = CodeCleaner.verify_syntax_integrity("void test() { int x = (1 + 2); }", "java")
    assert valid_c is True

    # Unbalanced brackets
    invalid_c, _ = CodeCleaner.verify_syntax_integrity("void test() { int x = (1 + 2;", "java")
    assert invalid_c is False


def test_preprocessing_pipeline_end_to_end() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        meta_idx = os.path.join(tmp_dir, "meta.jsonl")
        cfg = PreprocessingConfig(output_dir=tmp_dir, metadata_index_path=meta_idx)
        pipeline = CodePreprocessingPipeline(cfg)

        records = [
            {
                "file_path": "main.py",
                "repo_url": "https://github.com/test/repo",
                "license_spdx": "MIT",
                "raw_content": "# Hello\ndef run():\n\treturn True\n",
            },
            # Duplicate
            {
                "file_path": "main_copy.py",
                "repo_url": "https://github.com/test/repo",
                "license_spdx": "MIT",
                "raw_content": "# Hello\ndef run():\n\treturn True\n",
            },
            # Binary
            {
                "file_path": "app.class",
                "repo_url": "https://github.com/test/repo",
                "license_spdx": "MIT",
                "raw_content": b"\xca\xfe\xba\xbe\x00\x00",
            },
        ]

        results = pipeline.process_raw_files(records)
        assert results["stats"]["valid_clean_files"] == 1
        assert results["stats"]["duplicate_files_filtered"] == 1
        assert results["stats"]["binary_or_dependency_filtered"] == 1

        rep_path = os.path.join(tmp_dir, "report.md")
        pipeline.export_report(results, rep_path)
        assert os.path.exists(rep_path)
