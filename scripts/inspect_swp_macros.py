# -*- coding: utf-8 -*-
import os
import sys
import re

sys.stdout.reconfigure(encoding='utf-8')

macro_dir = r'e:\迅雷下载\青沐清晨宏命令'

def extract_strings_from_swp(file_path):
    with open(file_path, 'rb') as f:
        data = f.read()
    
    # Extract readable ASCII and GBK/UTF-8 tokens
    # SWP often stores VBA project text compressed or in plain chunks.
    # Look for VBA code markers: Sub, Function, Dim, As, Set, End Sub, etc.
    code_snippets = []
    
    # 1. Plain ASCII strings
    ascii_tokens = re.findall(b'[a-zA-Z0-9_ \t\.\(\)\,\=\+\-\*\/\\\"\'\:]{6,}', data)
    vba_keywords = [b'Sub ', b'Function ', b'Dim ', b'End Sub', b'End Function', b'Set ', b'SldWorks', b'ModelDoc', b'SelectionMgr', b'PartDoc', b'AssemblyDoc']
    
    meaningful_lines = []
    for token in ascii_tokens:
        if any(kw.lower() in token.lower() for kw in vba_keywords):
            try:
                line = token.decode('ascii', errors='ignore').strip()
                if len(line) > 8:
                    meaningful_lines.append(line)
            except:
                pass
    
    return meaningful_lines

print("=== TESTING VBA EXTRACTION FROM .SWP ===")
for root, dirs, files in os.walk(macro_dir):
    for f in files:
        if f.endswith('.swp'):
            fp = os.path.join(root, f)
            lines = extract_strings_from_swp(fp)
            if lines:
                print(f"{f}: found {len(lines)} VBA statement fragments")
                for l in lines[:3]:
                    print("   ", l[:80])
