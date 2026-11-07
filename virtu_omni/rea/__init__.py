"""Virtu Omni x REA (Reverse Engineer Anything) Toolbox.

Complete multi-architecture binary inspection, PE/ELF/Mach-O parsing,
Shannon entropy mapping, suspicious string extraction, and decompilation routing.
"""

from virtu_omni.rea.adapter import VirtuREA
from virtu_omni.rea.inspector import BinaryInspector

__all__ = [
    "VirtuREA",
    "BinaryInspector",
]
