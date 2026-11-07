# -*- coding: utf-8 -*-
"""
run_fixture77_chain.py — 针对实际 UG 夹具数模 e:\\迅雷下载\\分享数模20-77套UG夹具图档\\77 (1).prt
执行完整的 7 阶段 CAD/CAM Agent 链：
1. 识图与基准公差标注 (Stage 1 Blueprint Annotation)
2. AutoCAD 2026 2D 工程出图 (Stage 2 AutoLISP)
3. SOLIDWORKS 2021 3D 特征树建模 (Stage 3 SW VBA/Macro)
4. Siemens NX 12.0 CAM 制造与多轴刀轨 (Stage 4 NXOpen Python)
5. CIMCO Edit 2026 FANUC 宏程序生成 (Stage 5 G-code NC)
6. Vericut 9.6 虚拟机床碰撞干涉仿真 (Stage 6 OptiPath/Force)
7. 斯沃数控 7.2 现场对刀走刀指导书 (Stage 7 Shop-floor Guide)
"""

import os
import sys
import json
import datetime

sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from virtu_omni.engine.wish_cad_cam_engine import WishCADCAMEngine

def build_fixture_spec():
    """根据 NX 12.0 实测提取的 77 (1).prt 物理数模参数构建高精工装规格字典。"""
    spec = {
        "part_name": "77_1_Upright_Support_Plate",
        "assembly_name": "77_1_Fixture_Assembly",
        "prt_source": r"E:\迅雷下载\分享数模20-77套UG夹具图档\77 (1).prt",
        "material": "Steel45",
        "material_zh": "45#优质碳素结构钢 (调质 HB220-250)",
        "total_envelope": {
            "dx": 1074.16, "dy": 1215.32, "dz": 651.60,
            "min": [-465.13, -85.42, -79.60],
            "max": [609.04, 1129.90, 572.00]
        },
        # 核心主支承立板（Body_001 / Layer 16）
        "d_outer": 374.4,     # 宽度方向特征
        "d_inner": 67.4,      # 厚度方向特征
        "overall_len": 520.0, # 高度/长度主基准
        "sweep_angle": 90.0,
        "fillet_r": 5.0,
        "num_features": 8,
        "is_multiaxis": True,
        "is_die_mold": False,
        "features": {
            "pin_holes": {"dia": 16.0, "tol": "H7 (+0.018/0)", "count": 2, "pitch": 320.0},
            "mount_bolts": {"dia": 17.5, "c_bore_dia": 26.0, "c_bore_dep": 18.0, "count": 8, "spec": "M16内六角螺栓沉头孔"},
            "step_guide": {"width": 67.4, "depth": 12.0, "tol": "h7 (0/-0.030)"},
            "weight_pocket": {"len": 280.0, "wid": 140.0, "depth": 35.0, "corner_r": 15.0},
            "lift_hole": {"spec": "M20 吊装螺纹孔", "depth": 30.0}
        },
        "gdt": {
            "datum_A": "底面大安装平面，平面度 0.02 mm，Ra 1.6 μm",
            "datum_B": "侧面主定位导向基准，垂直度 0.02 mm 对A，Ra 0.8 μm",
            "datum_C": "基准销孔中心轴线，位置度 Φ0.02 mm 对A/B",
            "roughness_general": "Ra 3.2 μm",
            "roughness_pocket": "Ra 6.3 μm"
        }
    }
    return spec

def main():
    print("=" * 72)
    print("【Virtu CAD/CAM Agent 链 — 77号 UG 夹具数模全流程执行】")
    print("=" * 72)

    spec = build_fixture_spec()
    engine = WishCADCAMEngine()
    
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(ROOT, "runs", "cad_cam_chain", f"fixture_77_{ts}")
    os.makedirs(out_dir, exist_ok=True)
    print(f"输出目录: {out_dir}\n")

    stages = [
        ("01_图纸识读与标注.md", "generate_blueprint_annotation", "图纸解析与GD&T基准标注"),
        ("02_AutoCAD_2026.lsp", "generate_autocad_lisp", "AutoCAD 2026 2D国标工程图"),
        ("03_SOLIDWORKS_2021.swb", "generate_solidworks_macro", "SOLIDWORKS 2021 3D参数化特征树"),
        ("04_Siemens_NX_12.py", "generate_nx12_script", "Siemens NX 12.0 CAM多轴刀路与工步"),
        ("05_CIMCO_Edit_2026.nc", "generate_cimco_macro", "CIMCO Edit 2026 FANUC宏程序编程"),
        ("06_Vericut_9.6.opt", "generate_vericut_config", "Vericut 9.6 机床切削干涉仿真校验"),
        ("07_斯沃数控仿真_7.2.md", "generate_sscnc_setup_guide", "斯沃数控 7.2 虚拟对刀与走刀指导卡")
    ]

    artifacts = []
    for fname, method_name, role_desc in stages:
        gen = getattr(engine, method_name)
        content = gen(spec)
        
        # 增加夹具专属物理头部注释与数据追溯
        header = (
            f"; ==========================================================================\n"
            f"; Virtu CAD/CAM Team Agent 成果交付 | 阶段: {role_desc}\n"
            f"; 原始数模: {spec['prt_source']}\n"
            f"; 总成外包络: {spec['total_envelope']['dx']:.1f} x {spec['total_envelope']['dy']:.1f} x {spec['total_envelope']['dz']:.1f} mm\n"
            f"; 核心加工构件: {spec['part_name']} ({spec['d_inner']:.1f} x {spec['d_outer']:.1f} x {spec['overall_len']:.1f} mm)\n"
            f"; 生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"; ==========================================================================\n\n"
        )
        if fname.endswith(".md"):
            header = header.replace("; ", "<!-- ").replace("\n", " -->\n")
        elif fname.endswith(".py"):
            header = header.replace("; ", "# ")
        elif fname.endswith(".swb"):
            header = header.replace("; ", "' ")
        elif fname.endswith(".nc"):
            header = header.replace("; ", "( ") + ")\n"
            
        full_content = header + content
        fpath = os.path.join(out_dir, fname)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(full_content)
            
        artifacts.append({
            "stage": role_desc,
            "filename": fname,
            "path": fpath,
            "size": len(full_content)
        })
        print(f"  ✅ [{role_desc}] -> {fname} ({len(full_content)} 字节)")

    # 写入清单文件 manifest.json
    manifest = {
        "project": "UG_Fixture_77_1_Agent_Chain",
        "source_prt": spec["prt_source"],
        "generated_at": datetime.datetime.now().isoformat(),
        "total_envelope_mm": spec["total_envelope"],
        "core_component": {
            "name": spec["part_name"],
            "dimensions_mm": [spec["d_inner"], spec["d_outer"], spec["overall_len"]],
            "material": spec["material_zh"],
            "features": spec["features"],
            "gdt": spec["gdt"]
        },
        "artifacts": artifacts
    }
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 72)
    print(f"✨ 7 阶段 CAD/CAM Agent 链执行成功！产物已入库：\n{out_dir}")
    print("=" * 72)

if __name__ == "__main__":
    main()
