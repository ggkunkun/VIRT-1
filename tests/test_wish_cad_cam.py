"""Unit tests for WishCADCAMEngine and Software Ontology Knowledge Base."""

import pytest
from virtu_omni.knowledge.software_plugin_ontology import SOFTWARE_ONTOLOGY
from virtu_omni.engine.wish_cad_cam_engine import WishCADCAMEngine


def test_software_ontology_completeness():
    """Verify all 6 core software tools are properly cataloged with plugins."""
    expected_software = [
        "SOLIDWORKS 2021",
        "中文版NX12.0",
        "AutoCAD 2026",
        "Vericut 9.6",
        "CIMCO Edit 2026",
        "斯沃数控仿真软件 (SSCNC)"
    ]
    for sw in expected_software:
        assert sw in SOFTWARE_ONTOLOGY, f"Missing software ontology: {sw}"
        assert "plugins_and_addins" in SOFTWARE_ONTOLOGY[sw]
        assert len(SOFTWARE_ONTOLOGY[sw]["plugins_and_addins"]) >= 3


def test_wish_intent_parsing():
    """Verify natural language intent parsing extracts dimensions and material."""
    engine = WishCADCAMEngine()
    wish = "我需要一个航空钛合金Ti-6Al-4V的闭式12叶片高压压气机整体叶轮，外径180mm，内孔60mm，总长55mm，叶片根部圆角R3mm"
    spec = engine.parse_wish_intent(wish)
    
    assert spec["material"] == "Ti-6Al-4V"
    assert spec["d_outer"] == 180.0
    assert spec["d_inner"] == 60.0
    assert spec["overall_len"] == 55.0
    assert spec["fillet_r"] == 3.0
    assert spec["num_features"] == 12
    assert spec["is_multiaxis"] is True


def test_solidworks_macro_synthesis():
    """Verify SOLIDWORKS VBA macro generation contains required equations and features."""
    engine = WishCADCAMEngine()
    spec = {
        "material": "Cr12MoV",
        "d_outer": 53.0,
        "d_inner": 14.0,
        "overall_len": 45.0,
        "fillet_r": 3.0,
        "num_features": 3,
        "is_multiaxis": False,
        "is_die_mold": True
    }
    macro = engine.generate_solidworks_macro(spec)
    assert "SldWorks" in macro
    assert "D_Outer" in macro
    assert "FeatureExtrusion3" in macro
    assert "Cr12MoV" in macro


def test_nx12_script_synthesis():
    """Verify NX 12.0 Python Open API script generation."""
    engine = WishCADCAMEngine()
    spec = {
        "material": "AL7075-T6",
        "d_outer": 80.0,
        "d_inner": 25.0,
        "overall_len": 60.0,
        "fillet_r": 4.0,
        "num_features": 4,
        "is_multiaxis": False,
        "is_die_mold": False
    }
    script = engine.generate_nx12_script(spec)
    assert "import NXOpen" in script
    assert "the_uf_session.ModlFeatures.CreateCyl1" in script
    assert "D_OUTER" in script
    assert "80.0" in script


def test_autocad_lisp_synthesis():
    """Verify AutoCAD 2026 AutoLISP generation with layer discipline."""
    engine = WishCADCAMEngine()
    spec = {
        "material": "Steel45",
        "d_outer": 50.0,
        "d_inner": 20.0,
        "overall_len": 40.0,
        "fillet_r": 2.0,
        "num_features": 2,
        "is_multiaxis": False,
        "is_die_mold": False
    }
    lisp = engine.generate_autocad_lisp(spec)
    assert "(defun c:DRAWWHEELMOLD" in lisp
    assert "01_CENTERLINE" in lisp
    assert "02_PROFILE" in lisp
    assert "04_HATCH" in lisp
    assert "ANSI31" in lisp


def test_vericut_config_synthesis():
    """Verify Vericut 9.6 `.opt` machine simulation & OptiPath/Force config."""
    engine = WishCADCAMEngine()
    spec = {
        "material": "Ti-6Al-4V",
        "d_outer": 110.0,
        "d_inner": 35.0,
        "overall_len": 70.0,
        "fillet_r": 3.0,
        "num_features": 4,
        "is_multiaxis": True,
        "is_die_mold": False
    }
    config = engine.generate_vericut_config(spec)
    assert "[SETUP]" in config
    assert "FORCE_OPTIMIZATION" in config
    assert "AUTO_DIFF" in config
    assert "GOUGE_TOLERANCE: 0.005" in config


def test_cimco_macro_synthesis():
    """Verify CIMCO Edit 2026 Macro B program synthesis."""
    engine = WishCADCAMEngine()
    spec = {
        "material": "Cr12MoV",
        "d_outer": 53.0,
        "d_inner": 14.0,
        "overall_len": 45.0,
        "fillet_r": 3.0,
        "num_features": 3,
        "is_multiaxis": False,
        "is_die_mold": True
    }
    macro = engine.generate_cimco_macro(spec)
    assert "#101 =" in macro
    assert "#102 =" in macro
    assert "G71" in macro
    assert "G70" in macro
    assert "G42" in macro


def test_sscnc_setup_guide_synthesis():
    """Verify SSCNC 7.2 shop-floor touch-off manual synthesis."""
    engine = WishCADCAMEngine()
    spec = {
        "material": "Cr12MoV",
        "d_outer": 53.0,
        "d_inner": 14.0,
        "overall_len": 45.0,
        "fillet_r": 3.0,
        "num_features": 3,
        "is_multiaxis": False,
        "is_die_mold": True
    }
    guide = engine.generate_sscnc_setup_guide(spec)
    assert "FANUC 0i-TF" in guide
    assert "G54" in guide
    assert "T0101" in guide
    assert "3号" in guide
    assert "8号" in guide
