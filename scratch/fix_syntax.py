from pathlib import Path

ROOT = Path(r"D:\Virtu模型")

sw_path = ROOT / "bridges" / "solidworks_bridge.py"
sw_text = sw_path.read_text(encoding="utf-8")
sw_text = sw_text.replace(
    'if re.search(r"(?i)\\b(Shell|CreateObject\\s*\\(\\s*[\"\']WScript\\.Shell|cmd\\.exe|powershell|FileSystemObject|Kill\\b|RmDir\\b|Environ\\b)", vba_code or ""):',
    'if re.search(r"(?i)\\b(Shell|CreateObject|cmd\\.exe|powershell|FileSystemObject|Kill\\b|RmDir\\b|Environ\\b)", vba_code or ""):'
)
sw_path.write_text(sw_text, encoding="utf-8")

acad_path = ROOT / "bridges" / "autocad_bridge.py"
acad_text = acad_path.read_text(encoding="utf-8")
acad_text = acad_text.replace(
    'if re.search(r"(?i)\\b(startapp|vl-file-delete|vl-file-copy|vl-file-rename|command\\s+[\"\']sh)\\b", lisp_code or ""):',
    'if re.search(r"(?i)\\b(startapp|vl-file-delete|vl-file-copy|vl-file-rename|command\\s+.*sh)\\b", lisp_code or ""):'
)
acad_path.write_text(acad_text, encoding="utf-8")

print("Fixed syntax in bridges!")
