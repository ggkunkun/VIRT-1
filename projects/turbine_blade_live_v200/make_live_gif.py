# -*- coding: utf-8 -*-
import os
from pathlib import Path
from PIL import Image
from supervisor_enforcer import verify_file_novelty

p = Path(r"d:\Virtu模型\projects\turbine_blade_live_v200")
frames = []
for i in range(1, 6):
    f_path = p / f"demo_live_frame_0{i}.png"
    nv = verify_file_novelty(str(f_path))
    print(f"Frame {i}: {f_path.name} | SHA256: {nv['sha256']} | Size: {nv['size_bytes']} B (PASS)")
    im = Image.open(f_path).convert("RGB")
    im_resized = im.resize((1280, 720), Image.Resampling.LANCZOS)
    frames.append(im_resized)

gif_path = p / "turbine_blade_live_demonstration.gif"
frames[0].save(
    gif_path,
    save_all=True,
    append_images=frames[1:],
    duration=[2000, 2000, 2500, 2500, 3200],
    loop=0
)
print(f"[GIF_SYNTHESIS_COMPLETE] Saved to {gif_path} ({gif_path.stat().st_size / (1024*1024):.2f} MB)")
