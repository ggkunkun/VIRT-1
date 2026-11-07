# -*- coding: utf-8 -*-
import os
import sys
import pypdf
import fitz # pymupdf

sys.stdout.reconfigure(encoding='utf-8')

pdf_dir = r'e:\迅雷下载\机械设计手册 第六版  PDF(高清)'
print("=== INSPECTING MECHANICAL DESIGN HANDBOOK (PDFs) ===")
pdf_files = [f for f in os.listdir(pdf_dir) if f.endswith('.PDF') or f.endswith('.pdf')]
for f in sorted(pdf_files):
    fp = os.path.join(pdf_dir, f)
    sz = os.path.getsize(fp) / (1024*1024)
    try:
        doc = fitz.open(fp)
        page_count = len(doc)
        toc = doc.get_toc()
        # test text extraction from page 10
        test_page = min(page_count - 1, 10)
        sample_text = doc[test_page].get_text()[:120].replace('\n', ' ')
        doc.close()
        print(f"{f}: {page_count} pages | {sz:.1f} MB | TOC items: {len(toc)} | Sample: {sample_text[:60]}")
    except Exception as e:
        print(f"{f}: Error {e}")
