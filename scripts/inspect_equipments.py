# -*- coding: utf-8 -*-
import os
import sys
import json

sys.stdout.reconfigure(encoding='utf-8')

eq_dir = r'e:\迅雷下载\100台3C、锂电自动化设备量产图纸'

equipments = []
for item in sorted(os.listdir(eq_dir)):
    ip = os.path.join(eq_dir, item)
    if os.path.isdir(ip):
        sldasm = []
        sldprt = []
        slddrw = []
        dwg = []
        pdf = []
        for root, dirs, files in os.walk(ip):
            for f in files:
                low = f.lower()
                if low.endswith('.sldasm'):
                    sldasm.append(f)
                elif low.endswith('.sldprt'):
                    sldprt.append(f)
                elif low.endswith('.slddrw'):
                    slddrw.append(f)
                elif low.endswith('.dwg'):
                    dwg.append(f)
                elif low.endswith('.pdf'):
                    pdf.append(f)
        equipments.append({
            "name": item,
            "assemblies_count": len(sldasm),
            "parts_count": len(sldprt),
            "drawings_count": len(slddrw) + len(dwg) + len(pdf),
            "sample_asms": sldasm[:3],
            "sample_prts": sldprt[:5]
        })

print(f"Total equipment folders: {len(equipments)}")
for eq in equipments[:10]:
    print(f"\nEquipment: {eq['name']}")
    print(f"   Assemblies: {eq['assemblies_count']} | Parts: {eq['parts_count']} | Drawings: {eq['drawings_count']}")
    print(f"   Sample ASMs: {eq['sample_asms']}")
    print(f"   Sample PRTs: {eq['sample_prts']}")
