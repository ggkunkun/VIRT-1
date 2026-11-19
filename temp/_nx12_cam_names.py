# -*- coding: utf-8 -*-
import csv, io
from pathlib import Path

loc = Path(r"D:\BaiduNetdiskDownload\NX 12.0.2.9\NX12.2.9waigua\NX12.2.9\NX\LOCALIZATION\translations\simpl_chinese")
out = io.StringIO()
hits = []
for fp in sorted(loc.glob("*_simpl_chinese.txt")):
    try:
        with fp.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                try:
                    parts = next(csv.reader([s], delimiter=" ", quotechar='"', skipinitialspace=True))
                except Exception:
                    continue
                if len(parts) < 4:
                    continue
                en, zh = parts[2], parts[3]
                if ("Mill" in en or "Milling" in en or "Drill" in en) and ("铣" in zh or "钻" in zh) and len(zh) <= 20:
                    hits.append(f"{parts[0]} | {parts[1]} | {en} | {zh}")
    except OSError:
        pass
out.write(f"hits: {len(hits)}\n")
for h in hits[:300]:
    out.write(h + "\n")
open(r"d:\Virtu模型\temp\nx12_cn_cam_names.txt", "w", encoding="utf-8").write(out.getvalue())
print("ok", len(hits))
