# -*- coding: utf-8 -*-
"""根据更新后的案例索引生成「错误类型 + 复现状态」案例分析报告（Markdown）。

    python scripts/render_case_analysis_report.py
    python scripts/render_case_analysis_report.py --out reports/case_analysis.md

数据源：
* ``knowledge_base/training_case_index.json``（含 error_type / verification_status / reproduction）
* ``knowledge_base/error_case_verification.json``（实测日志与静态测量明细）

报告只陈述索引与核验报告里已有的证据；没有证据的地方明确写「未动态验证」。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INDEX = ROOT / "knowledge_base" / "training_case_index.json"
DEFAULT_VERIFICATION = ROOT / "knowledge_base" / "error_case_verification.json"
DEFAULT_OUT = ROOT / "reports" / "vericut_case_analysis_2026-11-17.md"

STATUS_CN = {
    "reproduced": "已复现",
    "attested": "讲义明示 + 数据存在",
    "partial": "部分静态复现",
    "inferred": "仅推断",
    "not_reproduced": "未复现",
    "unmeasured": "未核验",
}
ERROR_ORDER = [
    "nc_error_collision",
    "setup_defect",
    "data_defect",
    "vdaf_error_collision",
    "nc_config_error",
    "tool_setup_error",
    "collision_demo",
    "other_error",
]
METHOD_CN = {
    "dynamic_vericut_batch": "VERICUT 动态仿真",
    "static_measured": "静态实测",
    "static_manual_attestation": "讲义明示 + 数据存在",
    "static_measured+manual_attestation": "静态实测 + 讲义明示",
    "static_asset": "资产用途推断",
    "unclassified": "未分类",
}


def _clip(text: Any, limit: int = 160) -> str:
    s = " ".join(str(text or "").split())
    return s if len(s) <= limit else s[:limit] + "…"


def _cell(text: Any, limit: int = 80) -> str:
    return _clip(text, limit).replace("|", "\\|")


def _load(path: Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _series(case_id: str) -> str:
    low = case_id.lower()
    if low.startswith("lathe"):
        return "车床 L"
    if low.startswith("millturn"):
        return "车铣 MT"
    if low.startswith("mill"):
        return "铣削 M"
    if low.startswith("vdaf"):
        return "VDAF"
    if low.startswith("detect_collision"):
        return "独立程序"
    return "通用"


def render(index: Dict[str, Any], verification: Dict[str, Any]) -> str:
    cases = index.get("cases", [])
    error_cases = [c for c in cases if c.get("status") == "error_demo"]
    error_standalone = [p for p in index.get("standalone_programs", [])
                        if p.get("status") == "error_demo"]
    verify_by_id = {c.get("case_id"): c for c in verification.get("cases", [])}
    summary = index.get("summary", {})
    ev = summary.get("error_case_verification", {})
    by_status = ev.get("by_verification_status", {})
    by_type = ev.get("by_error_type", {})
    caps = summary.get("by_capability", {})

    lines: List[str] = []
    add = lines.append
    add("# VERICUT 官方培训案例：错误分析与复现报告")
    add("")
    add(f"> 生成时间（UTC）：{datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    add("> 案例索引：`knowledge_base/training_case_index.json`")
    add(f"> 索引数据基准：`{index.get('generated_at_utc', '')}`；"
        f"核验报告：`{ev.get('report', '')}`（{ev.get('report_generated_at_utc', '')}）")
    add("> 口径：错误案例 = 官方讲义明确要求学员发现/修正的缺陷；"
        "参考案例 = 官方按正常工作流程使用、未发现故意缺陷证据，本次未重跑。")
    add("")
    add("## 1. 总览")
    add("")
    add("| 指标 | 数值 |")
    add("|---|---|")
    add(f"| 案例总数 | {len(cases)} |")
    add(f"| 错误案例（工程） | {len(error_cases)} |")
    add(f"| 错误案例（独立程序） | {len(error_standalone)} |")
    add(f"| 参考/正常案例 | {len(cases) - len(error_cases)} |")
    add(f"| 已复现（reproduced） | {by_status.get('reproduced', 0)} |")
    add(f"| 讲义明示 + 数据存在（attested） | {by_status.get('attested', 0)} |")
    add(f"| 部分静态复现（partial） | {by_status.get('partial', 0)} |")
    add(f"| 仅推断（inferred） | {by_status.get('inferred', 0)} |")
    add(f"| 未复现 / 未核验 | "
        f"{by_status.get('not_reproduced', 0) + by_status.get('unmeasured', 0)} |")
    add("")

    add("### 1.1 全部案例的加工能力分布")
    add("")
    add("| 所需能力 | 案例数 |")
    add("|---|---|")
    for key, count in caps.items():
        label = next((c.get("capability_label") for c in cases
                      if c.get("required_capability") == key), key)
        add(f"| {label} | {count} |")
    add("")

    add("## 2. 错误类型与复现状态")
    add("")
    add("| 错误类型 | 数量 | 已复现 | 讲义明示 | 部分 | 仅推断 |")
    add("|---|---|---|---|---|---|")
    for etype in ERROR_ORDER:
        if etype not in by_type:
            continue
        group = [c for c in error_cases if c.get("error_type") == etype]
        group += [p for p in error_standalone if p.get("error_type") == etype]
        label = group[0].get("error_type_cn", etype) if group else etype
        counts = {s: sum(1 for c in group if c.get("verification_status") == s)
                  for s in ("reproduced", "attested", "partial", "inferred")}
        add(f"| {label} | {by_type[etype]} | {counts['reproduced']} | "
            f"{counts['attested']} | {counts['partial']} | {counts['inferred']} |")
    add("")

    add("## 3. 错误案例总表")
    add("")
    add("| # | 案例 | 系列 | 错误类型 | 所需能力 | 复现状态 | 验证方法 |")
    add("|---|---|---|---|---|---|---|")
    all_errors = error_cases + error_standalone
    for i, case in enumerate(all_errors, 1):
        case_id = case.get("case_id") or case.get("file")
        status = case.get("verification_status", "unmeasured")
        repro = case.get("reproduction") or {}
        method = METHOD_CN.get(repro.get("method"), repro.get("method") or "—")
        cap = case.get("capability_label") or case.get("required_capability") or "—"
        add(f"| {i} | `{case_id}` | {_series(str(case_id))} | "
            f"{case.get('error_type_cn', '—')} | {cap} | "
            f"{STATUS_CN.get(status, status)} | {method} |")
    add("")

    add("## 4. 分类详情")
    add("")
    for etype in ERROR_ORDER:
        group = [c for c in error_cases if c.get("error_type") == etype]
        group += [p for p in error_standalone if p.get("error_type") == etype]
        if not group:
            continue
        label = group[0].get("error_type_cn", etype)
        add(f"### 4.{ERROR_ORDER.index(etype) + 1} {label}（{len(group)}）")
        add("")
        for case in group:
            case_id = case.get("case_id") or case.get("file")
            status = case.get("verification_status", "unmeasured")
            repro = case.get("reproduction") or {}
            verify = verify_by_id.get(case_id) or {}
            quote = ""
            evidence = case.get("defect_evidence") or []
            if evidence:
                quote = evidence[0].get("quote", "")
            add(f"#### `{case_id}`")
            add("")
            add(f"- 错误类型：{case.get('error_type_cn', label)}")
            add(f"- 复现状态：**{STATUS_CN.get(status, status)}**（`{status}`）")
            if repro:
                add(f"- 验证方法：{METHOD_CN.get(repro.get('method'), repro.get('method'))}"
                    f"；置信度 `{repro.get('confidence', '')}`")
            if quote:
                add(f"- 讲义证据：{_clip(quote, 260)}")
            expected = verify.get("expected")
            if expected:
                add(f"- 核验目标：{_clip(expected, 220)}")
            observed = verify.get("observed")
            if isinstance(observed, list) and observed:
                add("- 实测证据：")
                for item in observed[:3]:
                    add(f"  - `{_clip(item, 220)}`")
            elif isinstance(observed, dict) and observed:
                add("- 实测证据：")
                for key, value in list(observed.items())[:4]:
                    add(f"  - {key}: `{_clip(value, 180)}`")
            elif isinstance(observed, str) and observed:
                add(f"- 实测证据：`{_clip(observed, 240)}`")
            log_path = repro.get("log_path")
            if log_path:
                name = Path(log_path).name
                add(f"- 原始日志：[{name}](vericut_error_case_logs/{name})")
            note = repro.get("note") or verify.get("note")
            if note:
                add(f"- 说明：{_clip(note, 240)}")
            add("")

    add("## 5. 未能动态复现的部分（诚实边界）")
    add("")
    add("- **VDAF 501**：NC 第 27 行、第 28 行 `M501` 与紧固件叠层 7.7054 已静态核实；"
        "VDAF 模块未做动态仿真，碰撞结论来自讲义。")
    add("- **VDAF 502**：工程引用 `Brotje_CPAC.xmch` 已核实；Lower Ram 碰撞由讲义明示，"
        "未做 VDAF 动态仿真。")
    add("- **254FL / 254FM**：刀库中确有 Optimization 与 StockMaterialCuttingLimits 数据，"
        "讲义明说这些值错误；正确值以截图给出，无法独立复算，故标 `attested`。")
    add("- **detect_collision.mcd**：没有对应 `.vcproject`，只按资产用途标 `inferred`。")
    add("- **参考/正常案例**：未重跑 VERICUT，不能宣称「已仿真验证无错」。")
    add("")

    add("## 6. 复跑方法")
    add("")
    add("```powershell")
    add("# 1) 生成/更新案例索引（会合并核验报告）")
    add("python scripts/index_training_cases.py --root E:/training")
    add("python scripts/index_training_cases.py --check")
    add("")
    add("# 2) 重新核验错误案例（先按脚本头部说明跑 VERICUT BATCH）")
    add("python scripts/verify_error_cases.py --strict")
    add("")
    add("# 3) 重新生成本报告")
    add("python scripts/render_case_analysis_report.py")
    add("```")
    add("")
    add("VERICUT 动态复现命令（在 `E:\\vericut_verify_work` 可写副本中执行）：")
    add("")
    add("```text")
    add("E:\\windows64\\commands\\vericut.bat BATCH batchp <project.vcproject>")
    add("```")
    add("")
    add("## 7. Agent 查询方式")
    add("")
    add("```python")
    add('agent.call_tool("query_training_cases", {"payload": "哪些错误案例已复现"})')
    add('agent.call_tool("query_training_cases", {"status": "error_demo"})')
    add('agent.call_tool("query_training_cases", {"verification_status": "reproduced"})')
    add('agent.call_tool("query_training_cases", {"capability": "5axis_positioning"})')
    add("```")
    add("")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Render VERICUT error-case analysis report")
    ap.add_argument("--index", default=str(DEFAULT_INDEX))
    ap.add_argument("--verification", default=str(DEFAULT_VERIFICATION))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args(argv)

    index = _load(Path(args.index))
    verification = _load(Path(args.verification))
    missing = [c.get("case_id") for c in index.get("cases", [])
               if c.get("status") == "error_demo" and not c.get("verification_status")]
    if missing:
        print(f"[FAIL] index not enriched; missing verification for {missing[:5]}")
        return 1
    text = render(index, verification)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"[report] {out} ({len(text.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
