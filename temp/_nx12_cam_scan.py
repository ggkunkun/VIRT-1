# -*- coding: utf-8 -*-
import io, os, time
from pathlib import Path

nx = Path(r"D:\BaiduNetdiskDownload\NX 12.0.2.9\NX12.2.9waigua\NX12.2.9\NX")
targets = ["型腔铣", "深度轮廓铣", "平面铣", "面铣", "钻孔"]
pats = []
for t in targets:
    pats.append((t, t.encode("utf-8")))
    pats.append((t, t.encode("utf-16-le")))

roots = [nx / "MACH", nx / "LOCALIZATION", nx / "UGII", nx / "NXPARTS"]
out = io.StringIO()
found = {t: [] for t in targets}
scanned = 0
t0 = time.time()
for root in roots:
    if not root.exists():
        continue
    for dirpath, dirnames, filenames in os.walk(root):
        if time.time() - t0 > 150:
            break
        for fn in filenames:
            fp = Path(dirpath) / fn
            try:
                if fp.stat().st_size > 8_000_000:
                    continue
                data = fp.read_bytes()
            except OSError:
                continue
            scanned += 1
            for t, b in pats:
                if b in data and len(found[t]) < 12:
                    found[t].append(str(fp.relative_to(nx)))
out.write(f"scanned={scanned} elapsed={time.time()-t0:.1f}s\n")
for t, lst in found.items():
    out.write(f"\n== {t} ({len(lst)}) ==\n")
    for f in lst:
        out.write("  " + f + "\n")
open(r"d:\Virtu模型\temp\nx12_cn_cam_scan.txt", "w", encoding="utf-8").write(out.getvalue())
print(out.getvalue()[:2000])
