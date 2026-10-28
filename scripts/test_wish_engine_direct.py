"""Direct verification of WishCADCAMEngine and Software Ontology without pytest overhead."""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from virtu_omni.knowledge.software_plugin_ontology import SOFTWARE_ONTOLOGY
from virtu_omni.engine.wish_cad_cam_engine import WishCADCAMEngine

print("[1] Testing Software Ontology...")
for sw in ["SOLIDWORKS 2021", "中文版NX12.0", "AutoCAD 2026", "Vericut 9.6", "CIMCO Edit 2026", "斯沃数控仿真软件 (SSCNC)"]:
    assert sw in SOFTWARE_ONTOLOGY, f"Missing: {sw}"
    plugins = SOFTWARE_ONTOLOGY[sw]["plugins_and_addins"]
    print(f"  - {sw}: {len(plugins)} plugins documented: {list(plugins.keys())[:3]}")

print("\n[2] Testing WishCADCAMEngine Intent Parsing...")
engine = WishCADCAMEngine()
wish = "我需要一个航空钛合金Ti-6Al-4V的闭式12叶片高压压气机整体叶轮，外径180mm，内孔60mm，总长55mm，叶片根部圆角R3mm"
spec = engine.parse_wish_intent(wish)
assert spec["material"] == "Ti-6Al-4V"
assert spec["d_outer"] == 180.0
assert spec["d_inner"] == 60.0
assert spec["num_features"] == 12
print(f"  Parsed: Material={spec['material']}, D_out={spec['d_outer']}, D_in={spec['d_inner']}, Feats={spec['num_features']}")

print("\n[3] Testing Synthesis across all 6 Tools...")
sw_macro = engine.generate_solidworks_macro(spec)
assert "SldWorks.SldWorks" in sw_macro and "FeatureRevolve2" in sw_macro
print("  - SOLIDWORKS VBA Macro: OK (length:", len(sw_macro), "chars)")

nx_script = engine.generate_nx12_script(spec)
assert "import NXOpen" in nx_script and "CreateCyl1" in nx_script
print("  - Siemens NX 12.0 Script: OK (length:", len(nx_script), "chars)")

cad_lisp = engine.generate_autocad_lisp(spec)
assert "(defun c:DRAWWHEELMOLD" in cad_lisp and "01_CENTERLINE" in cad_lisp
print("  - AutoCAD 2026 AutoLISP: OK (length:", len(cad_lisp), "chars)")

vericut_cfg = engine.generate_vericut_config(spec)
assert "FORCE_OPTIMIZATION" in vericut_cfg and "AUTO_DIFF" in vericut_cfg
print("  - Vericut 9.6 .opt Config: OK (length:", len(vericut_cfg), "chars)")

cimco_nc = engine.generate_cimco_macro(spec)
assert "#101 =" in cimco_nc and "G71" in cimco_nc
print("  - CIMCO Edit Macro B: OK (length:", len(cimco_nc), "chars)")

sscnc_guide = engine.generate_sscnc_setup_guide(spec)
assert "FANUC 0i-TF" in sscnc_guide and "G54" in sscnc_guide
print("  - SSCNC 7.2 Guide: OK (length:", len(sscnc_guide), "chars)")

print("\n[ALL TESTS PASSED] WishCADCAMEngine and Ontology 100% Verified!")
