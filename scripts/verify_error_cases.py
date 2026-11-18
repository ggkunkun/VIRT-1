# -*- coding: utf-8 -*-
"""核验 ``knowledge_base/training_case_index.json`` 里的错误案例是否真的能复现。

两种核验路径，证据分开记，不混为一谈：

* ``dynamic_vericut_batch``：把工程复制到可写工作目录，用
  ``E:\\windows64\\commands\\vericut.bat BATCH batchp <project>`` 实际跑 VERICUT 9.6，
  从 ``vericut.log`` 里比对讲义给出的错误行号/碰撞对象。日志由
  ``reports/vericut_error_case_logs/`` 保存。
* ``static_measured``：不跑仿真也能证伪的缺陷——机床组件坐标与讲义要求不符
  （103L/M/MT 的 Z/W 轴位置为 0）、NC 里讲义点名的行确实存在（VDAF line 27/M501）、
  刀库 Optimization 数据确实存在（254FL/FM）。

用法::

    python scripts/verify_error_cases.py
    python scripts/verify_error_cases.py --strict        # 有 false 就返回 1

注意：脚本本身**不会**启动 VERICUT；动态日志需先用工作目录跑出来放进
``reports/vericut_error_case_logs/``。这样核验过程可复跑、可审计，也不会在
后台悄悄占用 license。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from virtu_omni.knowledge.training_case_catalog import project_references  # noqa: E402

DEFAULT_INDEX = ROOT / "knowledge_base" / "training_case_index.json"
DEFAULT_LOGS = ROOT / "reports" / "vericut_error_case_logs"
DEFAULT_OUT = ROOT / "knowledge_base" / "error_case_verification.json"
DEFAULT_TRAINING = Path("E:/training")
VERICUT_BAT = Path(r"E:\windows64\commands\vericut.bat")
WORKDIR = Path(r"E:\vericut_verify_work")


# 动态核验：日志里必须同时出现讲义给出的「行号/坐标」与「碰撞对象」。
DYNAMIC_CASES: Dict[str, Dict[str, Any]] = {
    "lathe_session_day1": {
        "log": "lathe_session_day1.log",
        "must": [r"N1100\s*Z-1\.81", r"碰撞.*Jaws"],
        "expected": 'Session 3L: 刀具 "1" 碰撞 "Jaws"，第 23 行 N1100 Z-1.81',
        "command": 'vericut.bat BATCH batchp lathe_session_day1.vcproject',
    },
    "mill_session_day1": {
        "log": "mill_session_day1.log",
        "must": [r"Holder1", r"Fixture", r"碰撞"],
        "expected": 'Session 3M: 刀具 "9" 的刀柄 "Holder1" 与 "Fixture" 碰撞（第 280/281 行）',
        "command": 'vericut.bat BATCH batchp printargs mill_session_day1.vcproject',
        "note": "仿真完整结束：错误数 12、警告数 3；printargs 只打印命令行，不改变仿真模式",
    },
    "millturn_session_day1": {
        "log": "millturn_session_day1.log",
        "must": [r"G1\s*A0\.\s*F20\.", r"Sub_Fixture", r"碰撞"],
        "expected": 'Session 3MT: 第 165 行 G1 A0. F20. 时 Tool HOLDER 与 Sub_Fixture 碰撞',
        "command": 'vericut.bat BATCH batchp millturn_session_day1.vcproject',
        "note": "仿真完整结束（END-OF-FILE），另有 5 条警告",
    },
    "session_112_setting_up_and_using_basic_debugging_tools": {
        "log": "session_112.log",
        "must": [r"工作偏置未设置", r"寄存器\s*=\s*54"],
        "expected": "Session 112: 仿真在第一个 G54 块停下，Work Offset Register 54 未设置",
        "command": 'vericut.bat BATCH batchp printargs session_112_setting_up_and_using_basic_debugging_tools.vcproject',
        "note": "日志在 240s 截止；第 3 行即出现讲义所述错误，并在第 12/1662 行重复",
    },
    "session_14_MDI_to_validate_part_setup": {
        "log": "session_14_console_excerpt.log",
        "must": [r"Holder1", r"Fixture", r"碰撞"],
        "expected": "Session 14: 刀具过短，刀柄 Holder1 与 Fixture 碰撞",
        "command": 'vericut.bat BATCH batchp printargs session_14_MDI_to_validate_part_setup.VcProject',
        "partial": True,
    },
}


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8", "gbk"):
        try:
            text = raw.decode(enc)
            if "碰撞" in text or "VERICUT" in text:
                return text
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _clip(text: str, limit: int = 300) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[:limit] + "…"


def _matched_lines(text: str, patterns: List[str], limit: int = 4) -> List[str]:
    rx = [re.compile(p, re.I) for p in patterns]
    out = []
    for line in text.splitlines():
        if all(r.search(line) for r in rx):
            out.append(line.strip())
            if len(out) >= limit:
                break
    return out


def _case(catalog: Dict[str, Any], case_id: str) -> Dict[str, Any]:
    for case in catalog["cases"]:
        if case["case_id"] == case_id:
            return case
    raise KeyError(case_id)


def _component_position(mch: Path, component: str) -> Optional[Dict[str, str]]:
    try:
        root = ET.parse(mch).getroot()
    except (ET.ParseError, OSError):
        return None
    for comp in root.iter("Component"):
        if (comp.attrib.get("Name") or "").strip().upper() != component.upper():
            continue
        pos = comp.find("Position")
        if pos is not None:
            return dict(pos.attrib)
    return None


def _expected_offset(quote: str) -> Optional[Tuple[float, str]]:
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(mm|”|\"|inch)", quote, re.I)
    if not m:
        return None
    return float(m.group(1)), m.group(2)


def _verify_machine_offset(case: Dict[str, Any], training: Path) -> Dict[str, Any]:
    quote = (case.get("defect_evidence") or [{}])[0].get("quote", "")
    expected = _expected_offset(quote)
    machine = (case.get("machine") or {}).get("file")
    axis = "W" if re.search(r"\bW\s*axis", quote, re.I) else "Z"
    pos = _component_position(training / machine, axis) if machine else None
    actual = None
    if pos:
        actual = float(pos.get("Z", "nan"))
    reproduced = bool(expected and actual is not None and abs(actual) < 1e-9 and expected[0] > 0)
    return {
        "method": "static_measured",
        "submethod": "machine_component_offset",
        "reproduced": reproduced,
        "confidence": "measured",
        "expected": f"{axis} 轴应偏移 {expected[0]} {expected[1]}" if expected else "讲义未给出可解析的偏移值",
        "observed": f"{machine} 的 {axis} 组件 Position={pos}" if pos else "未找到组件坐标",
        "evidence": _clip(quote, 220),
    }


def _verify_tool_optimization(case: Dict[str, Any], training: Path) -> Dict[str, Any]:
    refs = project_references(training / case["path"])
    tls_files = [r for r in refs if Path(r).suffix.lower() == ".tls"]
    found = []
    for name in tls_files:
        path = training / name
        if not path.is_file():
            continue
        text = _read_text(path)
        opt = len(re.findall(r"<Optimization\b", text))
        limits = len(re.findall(r"<StockMaterialCuttingLimits\b", text))
        if opt or limits:
            found.append({"file": name, "optimization_nodes": opt,
                          "stock_cutting_limit_nodes": limits})
    quote = (case.get("defect_evidence") or [{}])[0].get("quote", "")
    return {
        "method": "static_manual_attestation",
        "submethod": "tool_library_optimization_data",
        "reproduced": "attested" if (found and "incorrect" in quote.lower()) else False,
        "confidence": "manual_attestation",
        "expected": "讲义明确：该工程保存的 Tool Library Optimization values 是错误的",
        "observed": found,
        "evidence": _clip(quote, 220),
        "note": "能证明「错误数据确实存在」，不能独立算出正确值（讲义用截图给参考值）",
    }


def _verify_vdaf(case: Dict[str, Any], training: Path) -> Dict[str, Any]:
    case_id = case["case_id"]
    quote = (case.get("defect_evidence") or [{}])[0].get("quote", "")
    if "simulation" in case_id:
        nc = training / "rotisserie.nc"
        lines = nc.read_text(encoding="utf-8", errors="replace").splitlines()
        line27 = lines[26].strip() if len(lines) > 26 else ""
        line28 = lines[27].strip() if len(lines) > 27 else ""
        xml = training / "Kuka_Rotisserie_VDAF_Training.xml"
        xml_text = xml.read_text(encoding="utf-8", errors="replace")
        skin = re.search(
            r'<Stack Name="\(Fuselage Skin\.stl\)"[^/]*Thickness="([0-9.]+)"', xml_text)
        thickness = float(skin.group(1)) if skin else None
        ok = bool(line27) and "M501" in line28 and thickness is not None
        return {
            "method": "static_measured+manual_attestation",
            "submethod": "vdaf_nc_line_and_stack_data",
            "reproduced": "partial" if ok else False,
            "confidence": "measured_partial",
            "expected": "Session 501: 第 27 行碰撞；第 108 行 M501 期望首层厚度 7.7，实测 10.0",
            "observed": {
                "rotisserie_nc_line_27": line27,
                "rotisserie_nc_line_28": line28,
                "fuselage_skin_thickness_xml": thickness,
            },
            "evidence": _clip(quote, 220),
            "note": "NC 行与 7.7 叠层数据已核实；VDAF 模块未做动态仿真，10.0 实测值来自讲义",
        }
    refs = project_references(training / case["path"])
    machine = [r for r in refs if r.lower().endswith(".xmch")]
    asset = training / machine[0] if machine else None
    return {
        "method": "static_manual_attestation",
        "submethod": "vdaf_project_asset",
        "reproduced": "attested" if (asset and asset.is_file()) else False,
        "confidence": "manual_attestation",
        "expected": "Session 502: Lower Ram 与结构模型碰撞",
        "observed": {"project": case["path"], "machine": machine,
                     "machine_exists": bool(asset and asset.is_file())},
        "evidence": _clip(quote, 220),
        "note": "VDAF 编程工程与 Brotje 机床资产存在；碰撞由讲义明示，未做 VDAF 动态仿真",
    }


def _verify_detect_collision(catalog: Dict[str, Any], training: Path) -> Dict[str, Any]:
    item = next((p for p in catalog.get("standalone_programs", [])
                 if p["file"] == "detect_collision.mcd"), None)
    if not item:
        return {"method": "static_asset", "reproduced": False,
                "confidence": "inferred", "observed": "standalone 条目缺失"}
    text = (training / "detect_collision.mcd").read_text(encoding="utf-8", errors="replace")
    has_5axis = "5-AXIS" in text.upper()
    has_ab = bool(re.search(r"(?<![A-Za-z_])[AB][-+]?\d", text))
    return {
        "method": "static_asset",
        "submethod": "collision_demo_asset",
        "reproduced": "inferred_only",
        "confidence": "inferred",
        "expected": "独立碰撞检测演示（资源名/用途）",
        "observed": {"file": "detect_collision.mcd", "five_axis_comment": has_5axis,
                     "rotary_words": has_ab},
        "note": "没有对应的 .vcproject，未做动态仿真；只按资产用途标注，不冒充实测",
    }


def build_report(index_path: Path, logs_dir: Path, training: Path) -> Dict[str, Any]:
    catalog = json.loads(index_path.read_text(encoding="utf-8"))
    cases: List[Dict[str, Any]] = []

    for case in catalog["cases"]:
        if case["status"] != "error_demo":
            continue
        case_id = case["case_id"]
        entry: Dict[str, Any] = {
            "case_id": case_id,
            "index_status": case["status"],
            "index_capability": case["required_capability"],
            "source_path": case["path"],
            "index_sha256": case["sha256"],
        }
        if case_id in DYNAMIC_CASES:
            spec = DYNAMIC_CASES[case_id]
            log_path = logs_dir / spec["log"]
            if log_path.is_file():
                text = _read_text(log_path)
                missing = [p for p in spec["must"] if not re.search(p, text, re.I)]
                hits = _matched_lines(text, spec["must"])
                entry.update({
                    "method": "dynamic_vericut_batch",
                    "reproduced": (not missing) and bool(hits),
                    "confidence": "measured_partial" if spec.get("partial") else "measured",
                    "expected": spec["expected"],
                    "observed": hits,
                    "log_path": _rel(log_path),
                    "command": spec["command"],
                    "note": spec.get("note") or (
                        "日志为 420s 截断的运行片段（已出现碰撞）" if spec.get("partial") else ""),
                })
                if missing:
                    entry["missing_patterns"] = missing
            else:
                entry.update({
                    "method": "dynamic_vericut_batch",
                    "reproduced": None,
                    "confidence": "unmeasured",
                    "expected": spec["expected"],
                    "observed": [],
                    "log_path": None,
                    "command": spec["command"],
                    "note": "缺少动态日志：先运行脚本头部说明的 VERICUT BATCH 命令",
                })
        elif "103" in case_id and "_add_3d_models" in case_id:
            entry.update(_verify_machine_offset(case, training))
        elif "254" in case_id and "optimization" in case_id:
            entry.update(_verify_tool_optimization(case, training))
        elif case_id.startswith("VDAF_"):
            entry.update(_verify_vdaf(case, training))
        else:
            entry.update({
                "method": "unclassified",
                "reproduced": None,
                "confidence": "unmeasured",
                "expected": "",
                "observed": [],
                "note": "没有为该案例定义核验规则",
            })
        cases.append(entry)

    if any(p.get("file") == "detect_collision.mcd"
           for p in catalog.get("standalone_programs", [])):
        detect = _verify_detect_collision(catalog, training)
        detect.update({
            "case_id": "detect_collision.mcd",
            "index_status": "error_demo",
            "index_capability": "milling_5axis_positioning",
            "source_path": "detect_collision.mcd",
            "index_sha256": "",
        })
        cases.append(detect)

    by_method: Dict[str, int] = {}
    for entry in cases:
        by_method[entry["method"]] = by_method.get(entry["method"], 0) + 1
    full = [e["case_id"] for e in cases if e.get("reproduced") is True]
    attested = [e["case_id"] for e in cases if e.get("reproduced") == "attested"]
    partial = [e["case_id"] for e in cases if e.get("reproduced") == "partial"]
    inferred = [e["case_id"] for e in cases if e.get("reproduced") == "inferred_only"]
    missing = [e["case_id"] for e in cases if e.get("reproduced") in (None, False)]
    dynamic = [e["case_id"] for e in cases if e["method"] == "dynamic_vericut_batch"]
    return {
        "schema_version": "1.0.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "index_path": _rel(index_path),
        "index_generated_at_utc": catalog.get("generated_at_utc"),
        "vericut": {
            "install": "E:/windows64",
            "launcher": str(VERICUT_BAT),
            "batch_args": "BATCH batchp",
            "workdir": str(WORKDIR),
        },
        "method": (
            "动态：VERICUT 9.6 BATCH 实际仿真，日志比对讲义行号/碰撞对象；"
            "静态：机床组件坐标、NC 指定行、刀库优化数据；"
            "VDAF/detect_collision 未做动态仿真，明确标注 manual_attestation / inferred"
        ),
        "summary": {
            "error_cases": len(cases),
            "fully_reproduced": len(full),
            "attested_by_manual": len(attested),
            "partial_static": len(partial),
            "inferred_only": len(inferred),
            "not_reproduced_or_unmeasured": len(missing),
            "dynamic_vericut_cases": len(dynamic),
            "by_method": by_method,
            "fully_reproduced_cases": full,
            "attested_cases": attested,
            "partial_cases": partial,
            "inferred_cases": inferred,
            "missing_cases": missing,
        },
        "cases": cases,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Verify error cases in the VERICUT training case index")
    ap.add_argument("--index", default=str(DEFAULT_INDEX))
    ap.add_argument("--logs", default=str(DEFAULT_LOGS))
    ap.add_argument("--training", default=str(DEFAULT_TRAINING))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--strict", action="store_true", help="exit 1 if any case is not reproduced")
    args = ap.parse_args(argv)

    report = build_report(Path(args.index), Path(args.logs), Path(args.training))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print()
    for entry in report["cases"]:
        print(f"{entry['case_id']:62s} {entry['method']:32s} {entry.get('reproduced')}")
    print(f"\n[report] {out}")
    if args.strict and report["summary"]["not_reproduced_or_unmeasured"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
