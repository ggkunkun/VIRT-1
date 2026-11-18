"""Virtu REA (Reverse Engineer Anything) Binary Inspector.

Pure-Python binary analysis, PE/ELF/archive inspection, entropy calculation,
string extraction/categorization, and disassembly/decompilation routing.
Completely standalone with zero required external dependencies; supports
delegation to Capstone, Pwntools, or REA CLI/MCP when present.
"""

from __future__ import annotations

import hashlib
import io
import math
import os
from pathlib import Path
import re
import struct
from typing import Any, Dict, List, Optional, Tuple, Union
import zipfile

# Try optional capstone
try:
    import capstone
    HAS_CAPSTONE = True
except ImportError:
    HAS_CAPSTONE = False


class BinaryInspector:
    """Multi-format binary inspection engine for Reverse Engineer Anything (REA)."""

    PE_MACHINE_MAP = {
        0x014C: "i386 (x86 32-bit)",
        0x8664: "AMD64 (x86-64 64-bit)",
        0x01C0: "ARM (Little Endian)",
        0xAA64: "ARM64 (Little Endian)",
        0x0200: "Intel Itanium (IA-64)",
    }

    PE_SUBSYSTEM_MAP = {
        1: "Native",
        2: "Windows GUI",
        3: "Windows CUI (Console)",
        7: "POSIX CUI",
        9: "Windows CE GUI",
        10: "EFI Application",
        11: "EFI Boot Service Driver",
        12: "EFI Runtime Driver",
    }

    ELF_MACHINE_MAP = {
        0x03: "x86 (Intel 80386)",
        0x3E: "x86-64 (AMD x86-64)",
        0x28: "ARM (32-bit)",
        0xB7: "AArch64 (ARM 64-bit)",
        0x08: "MIPS",
        0xF3: "RISC-V",
        0x14: "PowerPC",
        0x15: "PowerPC 64-bit",
    }

    ELF_TYPE_MAP = {
        1: "ET_REL (Relocatable object)",
        2: "ET_EXEC (Executable file)",
        3: "ET_DYN (Shared object / Position Independent Executable)",
        4: "ET_CORE (Core dump)",
    }

    SUSPICIOUS_KEYWORDS = [
        "virtualalloc", "virtualprotect", "writeprocessmemory", "createremotethread",
        "loadlibrary", "getprocaddress", "winresume", "inject", "hook", "keyboard",
        "urltodownloadfile", "internetopen", "winhttpopen", "cmd.exe", "powershell",
        "certutil", "regsvr32", "rundll32", "shellexecute", "winexec", "isdebuggerpresent",
        "checkremotedebuggerpresent", "ntqueryinformationprocess", "outputdebugstring",
        "base64", "aes", "rsa", "xor", "password", "token", "secret", "private_key"
    ]

    def __init__(self) -> None:
        self.url_pattern = re.compile(r'https?://[a-zA-Z0-9_\-\./\?#=&%+:;,@]+', re.IGNORECASE)
        self.ipv4_pattern = re.compile(r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b')
        self.win_path_pattern = re.compile(r'[a-zA-Z]:[\\/]+(?:[a-zA-Z0-9_\.\- ]+[\\/]+)*[a-zA-Z0-9_\.\- ]+')
        self.unix_path_pattern = re.compile(r'/(?:bin|etc|usr|var|tmp|home|opt|proc|sys|dev)/[a-zA-Z0-9_\.\-/]+')

    @staticmethod
    def calculate_entropy(data: bytes) -> float:
        """Calculate Shannon entropy: H(X) = -sum(p_i * log2(p_i)). Range 0.0 to 8.0."""
        if not data:
            return 0.0
        entropy = 0.0
        length = len(data)
        counts = [0] * 256
        for b in data:
            counts[b] += 1
        for count in counts:
            if count > 0:
                p = count / length
                entropy -= p * math.log2(p)
        return round(entropy, 4)

    @staticmethod
    def calculate_hashes(data: bytes, *, include_legacy: bool = False) -> Dict[str, str]:
        """Compute file fingerprints.

        V-10：原先无条件产出 md5/sha1。这两个算法已有实际可行的碰撞构造，
        一旦下游用它做"文件是否被篡改"的判断，即可被伪造命中。默认只给 sha256；
        需要与历史结果对齐时显式传 ``include_legacy=True``（或设置
        ``VIRTU_REA_LEGACY_HASHES=1``），并在使用处标注其非安全用途。
        """
        digests = {"sha256": hashlib.sha256(data).hexdigest()}
        if include_legacy or os.environ.get("VIRTU_REA_LEGACY_HASHES") == "1":
            digests["md5"] = hashlib.md5(data).hexdigest()
            digests["sha1"] = hashlib.sha1(data).hexdigest()
        return digests

    def detect_format(self, data: bytes) -> str:
        """Detect binary target type."""
        if not data:
            return "empty"
        if data.startswith(b"MZ"):
            # Check PE signature offset at 0x3C
            if len(data) > 0x40:
                pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
                if pe_offset + 4 <= len(data) and data[pe_offset:pe_offset+4] == b"PE\x00\x00":
                    return "PE"
            return "DOS_MZ"
        if data.startswith(b"\x7fELF"):
            return "ELF"
        if data.startswith(b"\xca\xfe\xba\xbe") or data.startswith(b"\xce\xfa\xed\xfe") or data.startswith(b"\xcf\xfa\xed\xfe") or data.startswith(b"\xfe\xed\xfa\xce") or data.startswith(b"\xfe\xed\xfa\xcf"):
            return "Mach-O"
        if data.startswith(b"PK\x03\x04"):
            # Check if Android APK or Java JAR
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as zf:
                    namelist = zf.namelist()
                    if "AndroidManifest.xml" in namelist or any(n.endswith(".dex") for n in namelist):
                        return "Android_APK"
                    if "META-INF/MANIFEST.MF" in namelist:
                        return "JAR"
            except Exception:
                pass
            return "ZIP"
        if data.startswith(b"\x00asm"):
            return "WebAssembly"
        if data.startswith(b"dex\n"):
            return "Android_DEX"
        if len(data) >= 8 and data[4:8] == b"ftyp":
            return "ISOBMFF"
        # Check EVM bytecode (hex string or starts with 0x60 PUSH1)
        if data.startswith(b"6080604052") or data.startswith(b"\x60\x80\x60\x40\x52"):
            return "EVM_Bytecode"
        return "Raw_Binary"

    def parse_pe(self, data: bytes) -> Dict[str, Any]:
        """Parse Portable Executable (PE/PE+) headers, sections, and security mitigations."""
        if len(data) < 0x40 or not data.startswith(b"MZ"):
            return {"error": "Invalid MZ header"}

        pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
        if pe_offset + 24 > len(data) or data[pe_offset:pe_offset+4] != b"PE\x00\x00":
            return {"error": "Invalid PE signature"}

        # COFF File Header (20 bytes)
        coff_offset = pe_offset + 4
        machine, num_sections, timedate, sym_ptr, num_syms, opt_hdr_size, characteristics = struct.unpack_from(
            "<HHIIIHH", data, coff_offset
        )

        arch_name = self.PE_MACHINE_MAP.get(machine, f"Unknown (0x{machine:04X})")

        # Optional Header
        opt_offset = coff_offset + 20
        magic = struct.unpack_from("<H", data, opt_offset)[0] if opt_hdr_size >= 2 else 0
        is_pe32_plus = (magic == 0x020B)  # 64-bit PE

        entry_point = 0
        image_base = 0
        subsystem = 0
        dll_characteristics = 0

        if is_pe32_plus:
            # PE32+
            if opt_hdr_size >= 72:
                entry_point = struct.unpack_from("<I", data, opt_offset + 16)[0]
                image_base = struct.unpack_from("<Q", data, opt_offset + 24)[0]
                subsystem = struct.unpack_from("<H", data, opt_offset + 68)[0]
                dll_characteristics = struct.unpack_from("<H", data, opt_offset + 70)[0]
        else:
            # PE32
            if opt_hdr_size >= 70:
                entry_point = struct.unpack_from("<I", data, opt_offset + 16)[0]
                image_base = struct.unpack_from("<I", data, opt_offset + 28)[0]
                subsystem = struct.unpack_from("<H", data, opt_offset + 68)[0]
                dll_characteristics = struct.unpack_from("<H", data, opt_offset + 70)[0]

        # Security Mitigations
        mitigations = {
            "aslr": bool(dll_characteristics & 0x0040),
            "dep_nx": bool(dll_characteristics & 0x0100),
            "high_entropy_va": bool(dll_characteristics & 0x0020),
            "control_flow_guard": bool(dll_characteristics & 0x4000),
            "no_seh": bool(dll_characteristics & 0x0400),
        }

        # Parse Sections
        sections_offset = opt_offset + opt_hdr_size
        sections: List[Dict[str, Any]] = []

        for i in range(num_sections):
            sec_pos = sections_offset + (i * 40)
            if sec_pos + 40 > len(data):
                break
            name_bytes = data[sec_pos:sec_pos+8].split(b"\x00")[0]
            name = name_bytes.decode("ascii", errors="replace").strip()

            vsize, vaddr, raw_size, raw_offset = struct.unpack_from("<IIII", data, sec_pos + 8)
            sec_chars = struct.unpack_from("<I", data, sec_pos + 36)[0]

            # Slice section content for entropy
            sec_data = b""
            if raw_offset < len(data):
                sec_data = data[raw_offset:min(len(data), raw_offset + raw_size)]
            sec_entropy = self.calculate_entropy(sec_data)

            is_exec = bool(sec_chars & 0x20000000)
            is_read = bool(sec_chars & 0x40000000)
            is_write = bool(sec_chars & 0x80000000)

            sections.append({
                "name": name,
                "virtual_address": f"0x{vaddr:08X}",
                "virtual_size": vsize,
                "raw_size": raw_size,
                "raw_offset": f"0x{raw_offset:08X}",
                "entropy": sec_entropy,
                "packed_suspicion": sec_entropy > 7.1 and (is_exec or name.lower() in [".text", ".code", ".upx0", ".upx1"]),
                "permissions": f"{'R' if is_read else '-'}{'W' if is_write else '-'}{'X' if is_exec else '-'}",
            })

        return {
            "format": "PE32+" if is_pe32_plus else "PE32",
            "machine": arch_name,
            "is_64bit": is_pe32_plus,
            "entry_point": f"0x{entry_point:08X}",
            "image_base": f"0x{image_base:016X}" if is_pe32_plus else f"0x{image_base:08X}",
            "subsystem": self.PE_SUBSYSTEM_MAP.get(subsystem, f"Unknown ({subsystem})"),
            "mitigations": mitigations,
            "section_count": len(sections),
            "sections": sections,
        }

    def parse_elf(self, data: bytes) -> Dict[str, Any]:
        """Parse Executable and Linkable Format (ELF) header and sections."""
        if len(data) < 52 or not data.startswith(b"\x7fELF"):
            return {"error": "Invalid ELF header"}

        ei_class = data[4]  # 1 = 32-bit, 2 = 64-bit
        ei_data = data[5]   # 1 = Little Endian, 2 = Big Endian
        endian = "<" if ei_data == 1 else ">"
        is_64bit = (ei_class == 2)

        e_type, e_machine = struct.unpack_from(f"{endian}HH", data, 16)
        arch_name = self.ELF_MACHINE_MAP.get(e_machine, f"Unknown (0x{e_machine:04X})")
        type_name = self.ELF_TYPE_MAP.get(e_type, f"Unknown ({e_type})")

        entry_point = 0
        sh_offset = 0
        sh_num = 0
        sh_strndx = 0

        if is_64bit:
            if len(data) >= 64:
                entry_point = struct.unpack_from(f"{endian}Q", data, 24)[0]
                sh_offset = struct.unpack_from(f"{endian}Q", data, 40)[0]
                sh_num = struct.unpack_from(f"{endian}H", data, 60)[0]
                sh_strndx = struct.unpack_from(f"{endian}H", data, 62)[0]
        else:
            entry_point = struct.unpack_from(f"{endian}I", data, 24)[0]
            sh_offset = struct.unpack_from(f"{endian}I", data, 32)[0]
            sh_num = struct.unpack_from(f"{endian}H", data, 48)[0]
            sh_strndx = struct.unpack_from(f"{endian}H", data, 50)[0]

        return {
            "format": f"ELF{'64' if is_64bit else '32'}",
            "machine": arch_name,
            "is_64bit": is_64bit,
            "endianness": "Little-Endian" if ei_data == 1 else "Big-Endian",
            "type": type_name,
            "entry_point": f"0x{entry_point:08X}",
            "section_header_count": sh_num,
        }

    def parse_archive(self, data: bytes) -> Dict[str, Any]:
        """Inspect package members (APK, JAR, ZIP)."""
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                namelist = zf.namelist()
                has_dex = any(n.endswith(".dex") for n in namelist)
                has_manifest = "AndroidManifest.xml" in namelist
                native_libs = [n for n in namelist if n.startswith("lib/") and n.endswith(".so")]

                return {
                    "format": "Android_APK" if (has_dex or has_manifest) else "ZIP_Archive",
                    "member_count": len(namelist),
                    "has_dex": has_dex,
                    "has_manifest": has_manifest,
                    "native_libraries": native_libs[:10],
                    "sample_members": namelist[:15],
                }
        except Exception as e:
            return {"error": f"Failed to parse archive: {e}"}

    def extract_strings(
        self,
        data: bytes,
        min_len: int = 4,
        max_strings: int = 500,
    ) -> Dict[str, Any]:
        """Extract ASCII and UTF-16LE strings and categorize by threat / interest."""
        ascii_matches = re.findall(rb'[ -~]{' + str(min_len).encode() + rb',}', data)
        # Extract unicode (UTF-16LE)
        utf16_matches = re.findall(rb'(?:[\x20-\x7e]\x00){' + str(min_len).encode() + rb',}', data)

        all_strings: List[str] = []
        for s in ascii_matches:
            try:
                all_strings.append(s.decode("ascii"))
            except Exception:
                pass
        for s in utf16_matches:
            try:
                all_strings.append(s.decode("utf-16le"))
            except Exception:
                pass

        # Deduplicate while preserving order
        seen = set()
        unique_strings: List[str] = []
        for s in all_strings:
            if s not in seen:
                seen.add(s)
                unique_strings.append(s)

        urls: List[str] = []
        ips: List[str] = []
        paths: List[str] = []
        suspicious: List[str] = []

        for s in unique_strings:
            # Check URLs
            url_found = self.url_pattern.findall(s)
            if url_found:
                urls.extend(url_found)
            # Check IPs
            ip_found = self.ipv4_pattern.findall(s)
            if ip_found:
                ips.extend(ip_found)
            # Check Windows or Unix paths
            wp = self.win_path_pattern.findall(s)
            if wp:
                paths.extend(wp)
            up = self.unix_path_pattern.findall(s)
            if up:
                paths.extend(up)
            # Check suspicious keywords
            s_lower = s.lower()
            if any(k in s_lower for k in self.SUSPICIOUS_KEYWORDS):
                suspicious.append(s)

        return {
            "total_extracted": len(unique_strings),
            "urls": list(set(urls))[:50],
            "ips": list(set(ips))[:50],
            "paths": list(set(paths))[:50],
            "suspicious_apis": list(set(suspicious))[:100],
            "sample_strings": unique_strings[:max_strings],
        }

    def disassemble(
        self,
        data: bytes,
        arch: str = "x86_64",
        offset: int = 0,
        count: int = 40,
    ) -> List[Dict[str, Any]]:
        """Disassemble instructions using Capstone (if present) or pure Python fallback."""
        if HAS_CAPSTONE:
            try:
                cs_arch = capstone.CS_ARCH_X86
                cs_mode = capstone.CS_MODE_64 if "64" in arch else capstone.CS_MODE_32
                if "arm64" in arch.lower() or "aarch64" in arch.lower():
                    cs_arch = capstone.CS_ARCH_ARM64
                    cs_mode = capstone.CS_MODE_ARM
                elif "arm" in arch.lower():
                    cs_arch = capstone.CS_ARCH_ARM
                    cs_mode = capstone.CS_MODE_ARM

                md = capstone.Cs(cs_arch, cs_mode)
                instructions = []
                for ins in md.disasm(data[offset:], offset):
                    instructions.append({
                        "address": f"0x{ins.address:08X}",
                        "mnemonic": ins.mnemonic,
                        "op_str": ins.op_str,
                        "bytes": ins.bytes.hex(),
                    })
                    if len(instructions) >= count:
                        break
                if instructions:
                    return instructions
            except Exception:
                pass

        # Pure Python fallback x86/x64 instruction recognizer
        return self._disassemble_fallback_x86(data, offset=offset, count=count)

    def _disassemble_fallback_x86(self, data: bytes, offset: int = 0, count: int = 40) -> List[Dict[str, Any]]:
        """Lightweight pure Python x86/x64 instruction disassembler."""
        instructions: List[Dict[str, Any]] = []
        pos = offset
        length = len(data)

        # Common single-byte / prefix mappings
        ONE_BYTE_OPS = {
            0x90: ("nop", ""),
            0xCC: ("int3", ""),
            0xC3: ("ret", ""),
            0xCB: ("retf", ""),
            0x50: ("push", "rax"),
            0x51: ("push", "rcx"),
            0x52: ("push", "rdx"),
            0x53: ("push", "rbx"),
            0x54: ("push", "rsp"),
            0x55: ("push", "rbp"),
            0x56: ("push", "rsi"),
            0x57: ("push", "rdi"),
            0x58: ("pop", "rax"),
            0x59: ("pop", "rcx"),
            0x5A: ("pop", "rdx"),
            0x5B: ("pop", "rbx"),
            0x5C: ("pop", "rsp"),
            0x5D: ("pop", "rbp"),
            0x5E: ("pop", "rsi"),
            0x5F: ("pop", "rdi"),
        }

        while pos < length and len(instructions) < count:
            b = data[pos]
            addr_str = f"0x{pos:08X}"

            if b in ONE_BYTE_OPS:
                mnemonic, op_str = ONE_BYTE_OPS[b]
                instructions.append({
                    "address": addr_str,
                    "mnemonic": mnemonic,
                    "op_str": op_str,
                    "bytes": f"{b:02x}",
                })
                pos += 1
            elif b == 0x48 and pos + 2 < length and data[pos+1] == 0x89 and data[pos+2] == 0xE5:
                # 48 89 e5: mov rbp, rsp
                instructions.append({
                    "address": addr_str,
                    "mnemonic": "mov",
                    "op_str": "rbp, rsp",
                    "bytes": "4889e5",
                })
                pos += 3
            elif b == 0x48 and pos + 2 < length and data[pos+1] == 0x83 and data[pos+2] == 0xEC:
                # 48 83 ec imm8: sub rsp, imm8
                imm = data[pos+3] if pos + 3 < length else 0
                instructions.append({
                    "address": addr_str,
                    "mnemonic": "sub",
                    "op_str": f"rsp, 0x{imm:02x}",
                    "bytes": data[pos:pos+4].hex(),
                })
                pos += 4
            elif b == 0x48 and pos + 2 < length and data[pos+1] == 0x31 and data[pos+2] == 0xC0:
                # 48 31 c0: xor rax, rax
                instructions.append({
                    "address": addr_str,
                    "mnemonic": "xor",
                    "op_str": "rax, rax",
                    "bytes": "4831c0",
                })
                pos += 3
            elif b == 0xE8 and pos + 4 < length:
                # E8 rel32: call target
                rel = struct.unpack_from("<i", data, pos + 1)[0]
                target = pos + 5 + rel
                instructions.append({
                    "address": addr_str,
                    "mnemonic": "call",
                    "op_str": f"0x{target:08X}",
                    "bytes": data[pos:pos+5].hex(),
                })
                pos += 5
            elif b == 0xE9 and pos + 4 < length:
                # E9 rel32: jmp target
                rel = struct.unpack_from("<i", data, pos + 1)[0]
                target = pos + 5 + rel
                instructions.append({
                    "address": addr_str,
                    "mnemonic": "jmp",
                    "op_str": f"0x{target:08X}",
                    "bytes": data[pos:pos+5].hex(),
                })
                pos += 5
            elif b == 0xEB and pos + 1 < length:
                # EB rel8: jmp short target
                rel = struct.unpack_from("<b", data, pos + 1)[0]
                target = pos + 2 + rel
                instructions.append({
                    "address": addr_str,
                    "mnemonic": "jmp",
                    "op_str": f"short 0x{target:08X}",
                    "bytes": data[pos:pos+2].hex(),
                })
                pos += 2
            elif b == 0x0F and pos + 1 < length and data[pos+1] == 0x05:
                # 0F 05: syscall
                instructions.append({
                    "address": addr_str,
                    "mnemonic": "syscall",
                    "op_str": "",
                    "bytes": "0f05",
                })
                pos += 2
            else:
                # Unknown/generic byte representation
                instructions.append({
                    "address": addr_str,
                    "mnemonic": "db",
                    "op_str": f"0x{b:02X}",
                    "bytes": f"{b:02x}",
                })
                pos += 1

        return instructions

    def decompile_pseudocode(self, instructions: List[Dict[str, Any]]) -> str:
        """Synthesize high-level C-like pseudocode from disassembled instructions."""
        lines: List[str] = [
            "// --- REA Decompiled Function Pseudocode ---",
            "void reconstructed_function() {",
        ]
        indent = "    "
        stack_allocated = False

        for ins in instructions:
            mnem = ins.get("mnemonic", "")
            ops = ins.get("op_str", "")

            if mnem == "push" and "rbp" in ops:
                lines.append(f"{indent}// Enter function stack frame")
            elif mnem == "mov" and "rbp, rsp" in ops:
                lines.append(f"{indent}frame_pointer = stack_pointer;")
            elif mnem == "sub" and "rsp" in ops:
                lines.append(f"{indent}stack_frame_alloc({ops.split(',')[-1].strip()});")
                stack_allocated = True
            elif mnem == "xor" and any(r in ops for r in ["rax, rax", "eax, eax"]):
                lines.append(f"{indent}return_value = 0;")
            elif mnem == "call":
                lines.append(f"{indent}subroutine_call({ops});")
            elif mnem == "jmp":
                lines.append(f"{indent}goto {ops};")
            elif mnem in ("je", "jz"):
                lines.append(f"{indent}if (condition_zero) goto {ops};")
            elif mnem in ("jne", "jnz"):
                lines.append(f"{indent}if (!condition_zero) goto {ops};")
            elif mnem == "syscall":
                lines.append(f"{indent}os_syscall();")
            elif mnem == "ret":
                lines.append(f"{indent}return return_value;")
            elif mnem == "nop":
                continue
            else:
                lines.append(f"{indent}__asm__(\"{mnem} {ops}\");")

        lines.append("}")
        return "\n".join(lines)

    def route_target(self, fmt: str, filename: str = "") -> Dict[str, str]:
        """Determine optimal REA toolchain route according to REA SKILL.md."""
        fname_lower = filename.lower()
        if fmt == "Android_APK" or fname_lower.endswith(".apk"):
            return {
                "route": "inspect_android_package",
                "category": "mobile",
                "recommended_tool": "inspect_android_package",
                "description": "Android APK code, classes, methods, or incoming references.",
            }
        if fname_lower.endswith(".asar") or "electron" in fname_lower:
            return {
                "route": "analyze_javascript_application",
                "category": "javascript_electron",
                "recommended_tool": "analyze_javascript_application",
                "description": "ASAR or extracted JavaScript/Electron tree.",
            }
        if fmt in ("PE32", "PE32+", "DOS_MZ"):
            return {
                "route": "open_binary",
                "category": "native_pe",
                "recommended_tool": "open_binary / inspect_pe_resources",
                "description": "Native Windows PE/PE+ executable or library.",
            }
        if fmt.startswith("ELF"):
            return {
                "route": "inspect_binary_layout",
                "category": "native_elf",
                "recommended_tool": "inspect_binary_layout / open_binary",
                "description": "Linux ELF binary for layout, symbols, relocations, or static mitigations.",
            }
        if fmt in ("ZIP", "JAR"):
            return {
                "route": "open_binary",
                "category": "archive",
                "recommended_tool": "open_binary / inspect_artifact",
                "description": "Package member inventory and artifact extraction.",
            }
        if fmt == "EVM_Bytecode":
            return {
                "route": "inspect_evm_interface",
                "category": "blockchain_bytecode",
                "recommended_tool": "inspect_evm_interface",
                "description": "EVM bytecode carrier interface inspection without chain lookup.",
            }
        return {
            "route": "open_binary",
            "category": "raw_binary",
            "recommended_tool": "open_binary",
            "description": "General binary inspection and disassembly.",
        }

    def inspect(self, target: Union[Path, str, bytes]) -> Dict[str, Any]:
        """Comprehensive inspection of a binary target."""
        filepath_str = ""
        if isinstance(target, (str, Path)):
            p = Path(target)
            if not p.is_file():
                return {"error": f"Target file does not exist: {p}"}
            data = p.read_bytes()
            filepath_str = str(p.resolve())
            filename = p.name
        else:
            data = target
            filename = "memory_buffer"

        total_bytes = len(data)
        fmt = self.detect_format(data)
        hashes = self.calculate_hashes(data)
        overall_entropy = self.calculate_entropy(data)

        format_details: Dict[str, Any] = {}
        if fmt in ("PE32", "PE32+", "DOS_MZ", "PE"):
            format_details = self.parse_pe(data)
            # Refine format string from parser
            if "format" in format_details:
                fmt = format_details["format"]
        elif fmt.startswith("ELF"):
            format_details = self.parse_elf(data)
        elif fmt in ("Android_APK", "ZIP", "JAR"):
            format_details = self.parse_archive(data)

        # Strings & threats extraction
        strings_info = self.extract_strings(data, min_len=4, max_strings=200)

        # Routing decision
        route_info = self.route_target(fmt, filename=filename)

        # Packed heuristic
        is_packed = overall_entropy > 7.2 or any(
            sec.get("packed_suspicion", False) for sec in format_details.get("sections", [])
        )

        return {
            "target": filepath_str or filename,
            "size_bytes": total_bytes,
            "format": fmt,
            "overall_entropy": overall_entropy,
            "is_likely_packed": is_packed,
            "hashes": hashes,
            "format_details": format_details,
            "strings_summary": {
                "total_strings": strings_info["total_extracted"],
                "url_count": len(strings_info["urls"]),
                "ip_count": len(strings_info["ips"]),
                "path_count": len(strings_info["paths"]),
                "suspicious_api_count": len(strings_info["suspicious_apis"]),
                "sample_suspicious_apis": strings_info["suspicious_apis"][:10],
                "sample_urls": strings_info["urls"][:5],
            },
            "rea_route": route_info,
        }
