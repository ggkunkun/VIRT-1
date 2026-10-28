"""Language identification and binary/dependency filtering.

Accurately detects:
- Java, Python, JavaScript, TypeScript, C, C++, Go, Rust.
Filters out:
- Binary/compiled artifacts, package dependencies, configs, and documentation.
"""

from __future__ import annotations
import os
from typing import Optional, Tuple, Set


class LanguageDetector:
    """Robust language classifier and binary artifact detector."""

    EXTENSION_MAP = {
        ".py": "python",
        ".java": "java",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".c": "c",
        ".h": "c",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".hpp": "cpp",
        ".go": "go",
        ".rs": "rust",
    }

    BINARY_EXTENSIONS: Set[str] = {
        ".exe", ".dll", ".so", ".dylib", ".class", ".pyc", ".pyo",
        ".o", ".obj", ".a", ".lib", ".bin", ".dat",
        ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".bmp",
        ".zip", ".tar", ".gz", ".7z", ".bz2", ".xz", ".rar",
        ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    }

    DEPENDENCY_DIRS: Set[str] = {
        "node_modules", "vendor", "target", "build", "dist", "out",
        "bin", "obj", ".git", ".github", "__pycache__", ".venv",
        "venv", "env", "site-packages", ".cargo", ".gradle",
    }

    NON_CODE_EXTENSIONS: Set[str] = {
        ".md", ".markdown", ".txt", ".rst", ".adoc",
        ".json", ".yaml", ".yml", ".xml", ".toml", ".ini", ".cfg",
        ".html", ".htm", ".css", ".scss", ".less",
        ".lock", ".map", ".log", ".csv", ".tsv",
    }

    @classmethod
    def is_binary_content(cls, content: bytes) -> bool:
        """Detect binary content via null bytes and magic headers."""
        if not content:
            return False
        # Null byte check (typical in binary executables and bytecode)
        if b"\x00" in content[:1024]:
            return True
        # Magic bytes check: ELF, PE, Java Class, Mach-O, Zip
        magic = content[:4]
        if magic in [b"\x7fELF", b"\xca\xfe\xba\xbe", b"PK\x03\x04"] or magic[:2] == b"MZ":
            return True
        return False

    @classmethod
    def is_dependency_or_build_path(cls, file_path: str) -> bool:
        """Check if file belongs to vendor dependencies or build output."""
        normalized = file_path.replace("\\", "/").lower()
        parts = normalized.split("/")
        return any(dep in parts for dep in cls.DEPENDENCY_DIRS)

    @classmethod
    def classify_file(
        cls, file_path: str, raw_bytes: Optional[bytes] = None
    ) -> Tuple[bool, Optional[str], str]:
        """Classify file into supported programming language or return rejection reason."""
        if cls.is_dependency_or_build_path(file_path):
            return False, None, "REJECTED_DEPENDENCY_OR_BUILD_DIRECTORY"

        _, ext = os.path.splitext(file_path)
        ext = ext.lower()

        if ext in cls.BINARY_EXTENSIONS:
            return False, None, f"REJECTED_BINARY_EXTENSION: '{ext}'"

        if ext in cls.NON_CODE_EXTENSIONS:
            return False, None, f"REJECTED_NON_CODE_FILE: '{ext}'"

        lang = cls.EXTENSION_MAP.get(ext)
        if not lang:
            return False, None, f"REJECTED_UNSUPPORTED_LANGUAGE_EXT: '{ext}'"

        if raw_bytes is not None and cls.is_binary_content(raw_bytes):
            return False, None, "REJECTED_BINARY_CONTENT_DETECTED"

        return True, lang, f"ACCEPTED_{lang.upper()}"
