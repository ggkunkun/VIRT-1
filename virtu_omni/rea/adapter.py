"""Virtu REA (Reverse Engineer Anything) Adapter.

Unifies static binary analysis, PE/ELF/archive inspection, string/entropy telemetry,
disassembly/decompilation routing, and the 170-tool REA ecosystem for the
Virtu Foundation Model.
"""

from __future__ import annotations

import logging
from pathlib import Path
import subprocess
from typing import Any, Dict, List, Optional, Union

from virtu_omni.rea.inspector import BinaryInspector, HAS_CAPSTONE

logger = logging.getLogger("virtu_omni.rea.adapter")


class VirtuREA:
    """Master adapter for Reverse Engineer Anything (REA) inside Virtu Foundation Model."""

    _instance: Optional[VirtuREA] = None

    def __init__(self, workspace_root: Optional[Union[Path, str]] = None) -> None:
        self.workspace_root = Path(workspace_root or "d:/Virtu模型").resolve()
        self.inspector = BinaryInspector()
        self.skill_path = self.workspace_root / "skills" / "reverse-engineer-anything" / "SKILL.md"
        self.external_rea_dir = self.workspace_root / "external" / "rea"

    @classmethod
    def get_instance(cls, workspace_root: Optional[Union[Path, str]] = None) -> VirtuREA:
        if cls._instance is None:
            cls._instance = cls(workspace_root=workspace_root)
        return cls._instance

    def inspect_binary(self, target: Union[Path, str, bytes]) -> Dict[str, Any]:
        """Perform comprehensive binary inspection and REA routing."""
        return self.inspector.inspect(target)

    def extract_strings(
        self,
        target: Union[Path, str, bytes],
        min_len: int = 4,
        max_strings: int = 500,
    ) -> Dict[str, Any]:
        """Extract strings and categorize into URLs, IPs, paths, and sensitive APIs."""
        data: bytes
        if isinstance(target, (str, Path)):
            p = Path(target)
            if not p.is_file():
                return {"error": f"File not found: {p}"}
            data = p.read_bytes()
        else:
            data = target
        return self.inspector.extract_strings(data, min_len=min_len, max_strings=max_strings)

    def calculate_entropy(self, target: Union[Path, str, bytes]) -> float:
        """Calculate Shannon entropy for target binary or payload."""
        data: bytes
        if isinstance(target, (str, Path)):
            p = Path(target)
            if not p.is_file():
                return 0.0
            data = p.read_bytes()
        else:
            data = target
        return self.inspector.calculate_entropy(data)

    def disassemble(
        self,
        target: Union[Path, str, bytes],
        offset: int = 0,
        count: int = 40,
        arch: str = "x86_64",
    ) -> List[Dict[str, Any]]:
        """Disassemble machine code at given offset."""
        data: bytes
        if isinstance(target, (str, Path)):
            p = Path(target)
            if not p.is_file():
                return []
            data = p.read_bytes()
        else:
            data = target
        return self.inspector.disassemble(data, arch=arch, offset=offset, count=count)

    def decompile(
        self,
        target: Union[Path, str, bytes],
        offset: int = 0,
        count: int = 40,
        arch: str = "x86_64",
    ) -> Dict[str, Any]:
        """Disassemble instructions and synthesize high-level pseudocode."""
        instructions = self.disassemble(target=target, offset=offset, count=count, arch=arch)
        pseudocode = self.inspector.decompile_pseudocode(instructions)
        return {
            "instruction_count": len(instructions),
            "instructions": instructions,
            "pseudocode": pseudocode,
        }

    def get_status(self) -> Dict[str, Any]:
        """Report REA environment status, tool capability count, and engine readiness."""
        has_skill = self.skill_path.is_file()
        has_external_repo = self.external_rea_dir.is_dir()
        
        # Check node
        node_available = False
        try:
            res = subprocess.run(["node", "-v"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True, timeout=3, encoding="utf-8", errors="replace")
            node_available = res.returncode == 0
        except Exception:
            pass

        return {
            "status": "READY",
            "rea_version": "v37 (6.4.0)",
            "tool_capabilities_count": 170,
            "skill_installed": has_skill,
            "skill_path": str(self.skill_path) if has_skill else None,
            "external_repo_cloned": has_external_repo,
            "external_repo_path": str(self.external_rea_dir) if has_external_repo else None,
            "capstone_native_engine": HAS_CAPSTONE,
            "node_runtime_available": node_available,
            "supported_formats": [
                "PE32/PE32+ (Windows)",
                "ELF32/ELF64 (Linux)",
                "Mach-O (macOS/iOS)",
                "Android APK/DEX",
                "Electron ASAR/JS",
                "EVM Bytecode",
                "WebAssembly (WASM)",
                "ZIP/JAR Packages",
            ],
            "analysis_engines": [
                "VirtuREA Native Inspector",
                "Shannon Entropy Calculator",
                "Static String & Threat Categorizer",
                "x86/x64 Fallback Disassembler & Pseudocode Synthesizer",
                "Ghidra/IDA/Cutter REA Bridge Router",
            ],
        }
