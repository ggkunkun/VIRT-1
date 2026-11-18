"""毛坯定位规范与联网标准查询单元测试。"""
from __future__ import annotations

from cam_autogen.contracts import Feature, ProcessType, WorkpieceSpec
from cam_autogen.examples import EXAMPLES
from cam_autogen.stock_positioning import compute_stock_setup, lookup_positioning_standards


def test_milling_vise_setup_and_zones():
    wp = WorkpieceSpec.model_validate(EXAMPLES["block"])
    ss = compute_stock_setup(wp, ProcessType.MILLING)
    assert ss.fixture == "vise"
    assert ss.grip_mm >= 5.0
    assert ss.stickout_mm > 20.0
    assert {z.kind for z in ss.fixture_zones} == {"vise_jaw", "parallel"}


def test_turning_overhang_tailstock_and_bore_rules():
    # 短轴 L/D <= 3 -> three_jaw_chuck
    wp_short = WorkpieceSpec.model_validate(EXAMPLES["shaft"])
    ss_short = compute_stock_setup(wp_short, ProcessType.TURNING)
    assert ss_short.fixture == "three_jaw_chuck"

    # 长轴 L/D > 3 -> chuck_tailstock
    wp_long = WorkpieceSpec.model_validate({
        "part_id": "LONG-01",
        "material": {"name": "C45"},
        "envelope": {"type": "cylindrical", "diameter": 25, "length": 130},
        "stock": {"type": "bar", "diameter": 28, "length": 165},
        "features": [{"id": "F1", "type": "od_cylinder", "params": {"diameter": 24, "z_start": 0, "z_end": -130}}],
    })
    ss_long = compute_stock_setup(wp_long, ProcessType.TURNING)
    assert ss_long.fixture == "chuck_tailstock"
    assert any(z.kind == "tailstock" for z in ss_long.fixture_zones)

    # 长轴但带中心孔 -> 不能用尾座顶尖，警示改用中心架
    wp_long_bore = wp_long.model_copy(update={
        "features": [
            wp_long.features[0],
            Feature.model_validate({"id": "F2", "type": "bore_axial", "params": {"diameter": 12, "depth": 40}, "on_axis": True}),
        ]
    })
    ss_bore = compute_stock_setup(wp_long_bore, ProcessType.TURNING)
    assert ss_bore.fixture == "three_jaw_chuck"
    assert any("中心架" in w for w in ss_bore.warnings)


def test_web_lookup_hermetic_and_mocked(monkeypatch):
    # 默认测试环境下 VIRTU_INTERNET=off，必须不联网并老实标注 basis
    res_off = lookup_positioning_standards("TURNING", enable_web=True)
    assert res_off["web_status"] == "disabled_by_env"
    assert res_off["basis"] == "local_verified_standard"

    # 显式开启联网 + 注入 mock fetcher -> 正常解析并标注 web_verified
    monkeypatch.setenv("VIRTU_INTERNET", "on")
    res_on = lookup_positioning_standards(
        "TURNING", enable_web=True,
        fetcher=lambda url, _t: "<html><body>Three-jaw chuck clamping length and tailstock 3:1 overhang rule.</body></html>",
    )
    assert res_on["web_status"] == "ok"
    assert res_on["basis"] == "web_verified+local_standard"
    assert len(res_on["web_references"]) >= 1

    # 网络异常时安全回退
    def _fail(_u, _t):
        raise ConnectionError("offline")
    res_err = lookup_positioning_standards("MILLING", enable_web=True, fetcher=_fail)
    assert res_err["web_status"] == "fallback_on_error"
    assert res_err["basis"] == "local_standard_fallback"
