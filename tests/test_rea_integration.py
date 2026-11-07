"""Unit tests for Virtu REA (Reverse Engineer Anything) Toolbox Integration.

Tests binary inspection (PE/ELF), Shannon entropy, string categorization,
disassembly/decompilation, and autonomous agent skill-writer integration.
"""

from __future__ import annotations

from pathlib import Path
import struct
import sys
import unittest

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from virtu_omni.rea import VirtuREA, BinaryInspector
from virtu_omni.agent.skill_writer_and_memory import SkillWriterAndMemory


class TestREAIntegration(unittest.TestCase):
    """Test suite for Virtu REA integration."""

    @classmethod
    def setUpClass(cls):
        cls.rea = VirtuREA.get_instance()
        cls.inspector = cls.rea.inspector

    def _generate_pe64_sample(self) -> bytes:
        buf = bytearray(512)
        buf[0:2] = b"MZ"
        struct.pack_into("<I", buf, 0x3C, 0x40)
        # PE signature
        buf[0x40:0x44] = b"PE\x00\x00"
        # COFF: machine 0x8664, 1 section, opt size 240
        struct.pack_into("<HHIIIHH", buf, 0x44, 0x8664, 1, 0, 0, 0, 240, 0x0022)
        # Opt PE32+
        struct.pack_into("<H", buf, 0x58, 0x020B)
        # Entry point 0x1000
        struct.pack_into("<I", buf, 0x58 + 16, 0x1000)
        # Subsystem CUI (3)
        struct.pack_into("<H", buf, 0x58 + 68, 3)
        # Mitigations: ASLR (0x40) | DEP (0x100)
        struct.pack_into("<H", buf, 0x58 + 70, 0x0140)
        # Section 1: .text
        sec_pos = 0x58 + 240
        buf[sec_pos:sec_pos+8] = b".text\x00\x00\x00"
        struct.pack_into("<IIIIIIHHI", buf, sec_pos + 8, 0x100, 0x1000, 0x100, 0x150, 0, 0, 0, 0, 0x60000020)
        # Code bytes at 0x150: push rbp, mov rbp, rsp, ret
        buf[0x150:0x155] = bytes.fromhex("554889e5c3")
        return bytes(buf)

    def test_rea_status(self):
        status = self.rea.get_status()
        self.assertEqual(status["status"], "READY")
        self.assertEqual(status["tool_capabilities_count"], 170)
        self.assertTrue(status["skill_installed"])
        self.assertTrue(len(status["supported_formats"]) >= 5)

    def test_rea_pe_inspection(self):
        pe_bytes = self._generate_pe64_sample()
        res = self.rea.inspect_binary(pe_bytes)
        self.assertEqual(res["format"], "PE32+")
        self.assertEqual(res["format_details"]["machine"], "AMD64 (x86-64 64-bit)")
        self.assertTrue(res["format_details"]["mitigations"]["aslr"])
        self.assertTrue(res["format_details"]["mitigations"]["dep_nx"])
        self.assertEqual(res["format_details"]["section_count"], 1)
        self.assertEqual(res["rea_route"]["route"], "open_binary")

    def test_rea_elf_inspection(self):
        elf_buf = bytearray(64)
        elf_buf[0:4] = b"\x7fELF"
        elf_buf[4] = 2  # 64-bit
        elf_buf[5] = 1  # Little endian
        struct.pack_into("<HH", elf_buf, 16, 2, 0x3E)  # ET_EXEC, x86-64
        struct.pack_into("<Q", elf_buf, 24, 0x400080)  # Entry

        res = self.rea.inspect_binary(bytes(elf_buf))
        self.assertEqual(res["format"], "ELF")
        self.assertEqual(res["format_details"]["machine"], "x86-64 (AMD x86-64)")
        self.assertEqual(res["format_details"]["entry_point"], "0x00400080")
        self.assertEqual(res["rea_route"]["route"], "inspect_binary_layout")

    def test_rea_entropy_calculation(self):
        flat_data = b"A" * 1000
        entropy_flat = self.inspector.calculate_entropy(flat_data)
        self.assertEqual(entropy_flat, 0.0)

        # High entropy pseudorandom data
        import os
        random_data = os.urandom(2048)
        entropy_rand = self.inspector.calculate_entropy(random_data)
        self.assertGreater(entropy_rand, 7.5)

    def test_rea_strings_categorization(self):
        test_payload = (
            b"GARBAGE_PREFIX\x00"
            b"https://cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2026-1000\x00"
            b"10.0.0.1\x00"
            b"C:\\Program Files\\CNC\\simulator.exe\x00"
            b"VirtualAlloc\x00CreateRemoteThread\x00cmd.exe\x00"
        )
        res = self.rea.extract_strings(test_payload, min_len=4)
        self.assertGreaterEqual(res["total_extracted"], 4)
        self.assertTrue(any("cve.mitre.org" in u for u in res["urls"]))
        self.assertIn("10.0.0.1", res["ips"])
        self.assertTrue(any("simulator.exe" in p for p in res["paths"]))
        self.assertTrue(any("VirtualAlloc" in k or "cmd.exe" in k for k in res["suspicious_apis"]))

    def test_rea_decompilation(self):
        # Code: push rbp, mov rbp, rsp, sub rsp, 0x20, xor rax, rax, ret
        code = bytes.fromhex("554889e54883ec204831c0c3")
        res = self.rea.decompile(code, offset=0, count=10)
        self.assertGreaterEqual(res["instruction_count"], 4)
        pseudo = res["pseudocode"]
        self.assertIn("void reconstructed_function()", pseudo)
        self.assertIn("frame_pointer = stack_pointer", pseudo)
        self.assertIn("return return_value;", pseudo)

    def test_rea_skill_writer_integration(self):
        writer = SkillWriterAndMemory()
        self.assertIsNotNone(writer.rea)
        pe_bytes = self._generate_pe64_sample()
        inspect_res = writer.inspect_binary_artifact(pe_bytes)
        self.assertEqual(inspect_res["format"], "PE32+")

        strings_res = writer.extract_binary_strings(b"http://industrial-iot.org\x00")
        self.assertIn("http://industrial-iot.org", strings_res["urls"])


if __name__ == "__main__":
    unittest.main()
