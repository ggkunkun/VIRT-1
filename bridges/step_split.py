# -*- coding: utf-8 -*-
"""把装配 STEP 按子件拆成独立 STEP（字节级保留实体，供 SolidWorks 逐件导入）。

为什么需要拆分：AddComponent5 只接受 .SLDPRT/.SLDASM，且带真实几何；
直接导入装配 STEP 得到的是 SW 自动摆位的整包装配，无法建立真实配合。
拆出的每个文件包含该子件的 PRODUCT 链 + 几何闭包，SolidWorks LoadFile4
可独立导入为零件，从而在总装里按 BOM 位姿插入并加配合。

纪律：原始实体按字节复制（源文件可能是 GBK），新增脚手架全 ASCII；
写出后必须用 StepBOM 回读并核对 实体数/面数/包围盒 与源子件一致。
"""
from __future__ import annotations

import os
import re
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bridges.step_bom import StepBOM  # noqa: E402


def _closure(bom: StepBOM, roots: List[int]) -> List[int]:
    seen, stack = set(), list(roots)
    while stack:
        eid = stack.pop()
        if eid in seen or eid not in bom.raws:
            continue
        seen.add(eid)
        stack.extend(bom.ref_adj.get(eid, []))
    return sorted(seen)


def split_parts(step_path: str, out_dir: str, prefix: str = "part") -> Dict[str, Any]:
    bom = StepBOM(step_path)
    if not bom.tree:
        return {"status": "error", "message": "no product tree"}
    root = bom.tree[0]
    if not root.get("children"):
        return {"status": "error", "message": "not an assembly (no children)"}

    os.makedirs(out_dir, exist_ok=True)
    out_dir = os.path.abspath(out_dir)
    parent_pd = root["pd_id"]
    parent_rep = bom.pd_rep.get(parent_pd)

    parts, failures = [], []
    children = [c for c in root["children"] if c.get("solids", 0) > 0]
    for idx, node in enumerate(children):
        pd = node["pd_id"]
        rep = bom.pd_rep.get(pd)
        if rep is None:
            failures.append({"name": node["name"], "error": "no representation"})
            continue
        solids, faces, _ = bom._geometry_of_pd(pd)
        # 几何可能挂在同 context 的独立 ADVANCED_BREP_SHAPE_REPRESENTATION 上，
        # 并不在 PD 直属 rep 的 items 里；把这些 rep 一起纳入闭包根。
        ctx = bom.rep_ctx.get(rep)
        abrep_roots = [ab for ab, brs in bom.abrep_breps.items()
                       if ctx is not None and bom.rep_ctx.get(ab) == ctx]
        pds = next((s for s, (p, r) in bom.sdr.items()
                    if bom.pds_to_pd.get(p) == pd and r == rep), None)
        chain = [rep, pds, pd, bom.pd_to_formation.get(pd),
                 bom.formation_to_product.get(bom.pd_to_formation.get(pd))]
        roots = [x for x in chain if x is not None] + solids + abrep_roots
        ids = _closure(bom, roots)
        # 几何闭包里可能通过上下文反向带上装配根 rep；剔除根 rep 及其专属位姿链
        exclude = {parent_rep} if parent_rep and parent_rep != rep else set()
        ids = [i for i in ids if i not in exclude]

        name = f"{prefix}_{idx}"
        out_path = os.path.join(out_dir, name + ".step")
        header = (
            "ISO-10303-21;\n"
            "HEADER;\n"
            "FILE_DESCRIPTION ( ( 'STEP AP203' ), '1' );\n"
            "FILE_NAME ( '%s.step', '2026-11-07T00:00:00', ( '' ), ( '' ), "
            "'VirtuStepSplit', 'Virtu 13.63B', '' );\n"
            "FILE_SCHEMA ( ( 'CONFIG_CONTROL_DESIGN' ) );\n"
            "ENDSEC;\nDATA;\n" % name
        ).encode("ascii")
        body = bytearray()
        for eid in ids:
            body += b"#%d = " % eid + bom.raws[eid].strip() + b";\n"
        footer = b"ENDSEC;\nEND-ISO-10303-21;\n"
        with open(out_path, "wb") as f:
            f.write(header + bytes(body) + footer)

        check = StepBOM(out_path)
        chk_solids, chk_faces, _ = check._geometry_of_pd(
            next((k for k in check.pd_rep), list(check.pd_name)[0]))
        chk_bbox = check._bbox_of(chk_solids)
        src_bbox = node.get("bbox")
        ok = (len(chk_solids) == len(solids) and chk_faces == faces)
        detail = None
        if ok and chk_bbox and src_bbox:
            ok = all(abs(a - b) <= 1e-3 for a, b in zip(chk_bbox, src_bbox))
        if not ok:
            detail = {"solids": [len(solids), len(chk_solids)],
                      "faces": [faces, chk_faces],
                      "bbox": [src_bbox, chk_bbox]}
            failures.append({"name": node["name"], "error": "roundtrip mismatch", "detail": detail})
            continue
        parts.append({
            "index": idx, "name": node["name"], "part_name": name,
            "step_file": out_path, "solids": len(solids), "faces": faces,
            "bbox": src_bbox, "placement": node.get("placement"),
            "bytes": os.path.getsize(out_path),
        })

    return {
        "status": "ok" if parts and not failures else ("partial" if parts else "error"),
        "source": os.path.basename(step_path),
        "part_count": len(parts), "parts": parts, "failures": failures,
    }


if __name__ == "__main__":
    import json
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(src), "parts")
    print(json.dumps(split_parts(src, out), ensure_ascii=False, indent=2))
