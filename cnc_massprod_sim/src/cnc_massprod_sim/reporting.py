# -*- coding: utf-8 -*-
"""交付物生成：仿真日志 / 干涉报告 / 精度校验 / 节拍统计 / 参数校验清单 /
操作与换产手册 / 完整验证报告。所有文件带 basis 与标准出处。"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from . import config as cfgmod


def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _tbl(rows: List[List[Any]], header: List[str]) -> str:
    out = ["| " + " | ".join(header) + " |",
           "|" + "|".join(["---"] * len(header)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def _gate_rows(gates: Dict[str, str]) -> List[List[str]]:
    return [[k, v] for k, v in gates.items()]


class ReportWriter:
    def __init__(self, outdir: Path):
        self.out = outdir
        self.out.mkdir(parents=True, exist_ok=True)
        for d in ("programs", "reports", "docs", "logs"):
            (self.out / d).mkdir(parents=True, exist_ok=True)

    def write_all(self, full: Dict[str, Any]) -> Dict[str, str]:
        paths: Dict[str, str] = {}
        runs = full["runs"]
        summary = full["summary"]

        # 1) 机器可读全量结果
        p = self.out / "reports" / "verification_result.json"
        p.write_text(json.dumps(full, ensure_ascii=False, indent=2, default=str),
                     encoding="utf-8")
        paths["result_json"] = str(p)

        # 2) NC 程序集（三方言 × 三工件）
        for r in runs:
            d = r["dialect"]
            ext = ".mpf" if d == "siemens" else ".nc"
            fn = f"{r['workpiece_id']}_{r['nc']['controller_id']}{ext}"
            (self.out / "programs" / fn).write_text(r["nc"]["code"], encoding="utf-8")

        # 3) 仿真运行日志（逐帧摘要）
        log_lines = [
            f"# CNC 量产仿真运行日志  generated={_ts()}",
            f"summary: total={summary['total']} passed={summary['passed']} "
            f"failed={summary['failed']} elapsed={summary['elapsed_s']}s",
            "basis: measured_deterministic_emulator + measured_geometry",
            "",
        ]
        for r in runs:
            sim = r["simulation"]
            log_lines.append(
                f"[{r['workpiece_id']}/{r['dialect']}] status={r['status']} "
                f"gates={json.dumps(r['gates'], ensure_ascii=False)} "
                f"frames={sim['frame_count']} segments={sim['segment_count']} "
                f"blocks={sim['execution']['blocks_executed']} "
                f"time_s={sim['execution']['total_time_s']} "
                f"alarms={sim['execution']['alarm_count']} "
                f"min_clearance_mm={sim['interference']['min_clearance_mm']} "
                f"program_sha256={r['nc']['program_sha256'][:16]}"
            )
        lp = self.out / "logs" / "simulation_run.log"
        lp.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
        paths["run_log"] = str(lp)

        # 4) 干涉检测报告
        paths["interference"] = str(self._interference(runs))

        # 5) 精度校验数据
        paths["precision"] = str(self._precision(runs))

        # 6) 节拍统计
        paths["takt"] = str(self._takt(runs))

        # 7) 工艺参数校验清单
        paths["checklist"] = str(self._checklist(runs))

        # 8) OPC UA 节点表
        from . import assurance
        node_rows = [[k, v] for k, v in assurance.opcua_node_map().items()]
        op = self.out / "reports" / "opcua_nodes.md"
        op.write_text("# OPC UA 信息模型（量产对接）\n\n"
                      + _tbl(node_rows, ["节点", "含义"]) + "\n", encoding="utf-8")
        paths["opcua"] = str(op)

        # 9) 操作与换产手册
        paths["manual"] = str(self._manual(runs))

        # 10) 主验证报告
        paths["report"] = str(self._report(runs, summary, full))

        return paths

    # ---------------------------------------------------------------- 干涉报告
    def _interference(self, runs: List[Dict[str, Any]]) -> Path:
        lines = ["# 干涉检测报告（逐帧扫掠实测）", "",
                 f"生成：{_ts()}",
                 "口径：刀尖+刀轴+刀具/刀柄圆柱表面，对工件原型 KeepOut 盒体逐帧求有符号间隙；",
                 "basis=measured（确定性几何实测，非 VERICUT 布尔材料去除）。",
                 "现场仍需 VERICUT Auto-Diff 与首件试切确认。", ""]
        rows = []
        for r in runs:
            i = r["simulation"]["interference"]
            rows.append([r["workpiece_id"], r["dialect"],
                         i["summary"]["verdict"],
                         i["summary"].get("frames", r["simulation"].get("frame_count", "—")),
                         i.get("min_clearance_mm"),
                         i["summary"]["violations"],
                         (i["min_clearance_where"].get("keepout") or "—")])
        lines.append(_tbl(rows, ["工件", "方言", "判定", "帧数", "最小间隙mm",
                                 "违规数", "最危险夹具"]))
        lines += ["", "## 逐门结果", ""]
        gate_rows = []
        for r in runs:
            for c in r["simulation"]["interference"]["checks"]:
                gate_rows.append([r["workpiece_id"], r["dialect"], c["gate"],
                                  c["status"], str(c.get("evidence"))[:80]])
        lines.append(_tbl(gate_rows, ["工件", "方言", "判据", "结果", "证据"]))
        lines += ["", "## 有界豁免（牺牲性背板通孔）", ""]
        ex_rows = []
        for r in runs:
            for c in r["simulation"]["interference"]["checks"]:
                if "EXEMPT" in c["gate"]:
                    ex_rows.append([r["workpiece_id"], r["dialect"], c["gate"],
                                    c["evidence"]])
        lines.append(_tbl(ex_rows or [["—", "—", "无豁免", "—"]],
                          ["工件", "方言", "豁免", "规则"]))
        p = self.out / "reports" / "interference_report.md"
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return p

    # ---------------------------------------------------------------- 精度校验
    def _precision(self, runs: List[Dict[str, Any]]) -> Path:
        lines = ["# 精度校验数据", "",
                 f"生成：{_ts()}",
                 "说明：Cpk/SPC 若有实测样本则 basis=measured；未提供实测样本时",
                 "按声明 σ 生成 basis=simulated 样本，绝不冒充实测。", ""]
        rows = []
        for r in runs:
            q = r.get("assurance", {}).get("spc", {})
            a = r.get("assurance", {})
            rows.append([r["workpiece_id"], r["dialect"],
                         q.get("cpk", "未测"), q.get("cp", "未测"),
                         q.get("target_cpk", "—"),
                         q.get("verdict_vs_target", "未测"),
                         q.get("assumed_sigma_mm", "—"),
                         a.get("yield_estimate_pct", "未测")])
        lines.append(_tbl(rows, ["工件", "方言", "Cpk(仿真)", "Cp", "目标Cpk",
                                 "对目标判定", "声明σ mm", "估算良品率%"]))
        lines += ["", "> 注：Cpk 为 basis=simulated（按目标能力反推声明 σ 生成样本），",
                  "> 非实测；`对目标判定=WARN` 表示仿真样本 Cpk 未达工件原型目标，",
                  "> 需现场首件实测复核。良品率为正态假设下由 Cpk 反推，同为仿真值。", ""]
        lines += ["", "## 关键特征公差（源自工件原型 / ISO 286）", ""]
        feat_rows = []
        seen = set()
        for r in runs:
            wid = r["workpiece_id"]
            if wid in seen:
                continue
            seen.add(wid)
            for f in r["process_config"]["quality"]["critical_features"]:
                feat_rows.append([wid, f["name"], f["nominal_mm"],
                                  f.get("tol_upper_mm"), f.get("tol_lower_mm")])
        lines.append(_tbl(feat_rows, ["工件", "特征", "公称mm", "上偏差", "下偏差"]))
        p = self.out / "reports" / "precision_report.md"
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return p

    # ---------------------------------------------------------------- 节拍统计
    def _takt(self, runs: List[Dict[str, Any]]) -> Path:
        lines = ["# 节拍统计数据", "",
                 f"生成：{_ts()}",
                 "口径：确定性解释器逐段时长累计（路径长/进给 + 快移），basis=measured_deterministic_emulator。",
                 "不含机床加减速与换刀确认耗时，现场需实测标定。", ""]
        rows = []
        for r in runs:
            s = r["simulation"]["execution"]
            t = r.get("assurance", {}).get("takt", {})
            rows.append([r["workpiece_id"], r["dialect"],
                         s["segment_count"], s["total_time_s"],
                         s["cutting_time_s"], s["rapid_time_s"],
                         t.get("target_s", "—"),
                         t.get("verdict", "—")])
        lines.append(_tbl(rows, ["工件", "方言", "段数", "总时长s", "切削s",
                                 "快移s", "目标s", "判定"]))
        lines += ["", "## 批量生产计划（源自 assurance.batch_plan）", ""]
        b_rows = []
        for r in runs:
            b = r.get("assurance", {}).get("batch_plan", {})
            b_rows.append([r["workpiece_id"], r["dialect"], b.get("batch_size"),
                           b.get("cycle_per_part_min"), b.get("tool_changes"),
                           b.get("total_h"), b.get("consistency", "")[:50]])
        lines.append(_tbl(b_rows, ["工件", "方言", "批量", "单件min", "换刀次数",
                                   "总工时h", "一致性保障"]))
        p = self.out / "reports" / "takt_report.md"
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return p

    # ---------------------------------------------------------------- 参数校验清单
    def _checklist(self, runs: List[Dict[str, Any]]) -> Path:
        lines = ["# 工艺参数校验清单（全维度）", "",
                 f"生成：{_ts()}",
                 "所有参数来源：process_standards（工艺标准库）/ controllers.yaml /",
                 "工件原型；带 handbook_ref / basis 可追溯。", ""]
        seen = set()
        for r in runs:
            wid = r["workpiece_id"]
            if wid in seen:
                continue
            seen.add(wid)
            c = r["process_config"]
            mat = c["material"]
            lines += [f"## {wid} — {c['name_zh']}", ""]
            stock = c["stock"]
            rows = [
                ["材质牌号", c["material_id"], mat.get("gb_standard", ""), "MATERIAL_HANDBOOK"],
                ["密度 g/cm³", mat.get("density_g_cm3"), "—", "材料手册"],
                ["屈服强度 MPa", mat.get("yield_strength_mpa"), "—", "材料手册"],
                ["抗拉强度 MPa", mat.get("tensile_strength_mpa"), "—", "材料手册"],
                ["硬度 HB", mat.get("hardness_hb"), "—", "材料手册"],
                ["毛坯形状", stock["shape"], "—", "stock_derivation"],
                ["毛坯尺寸 mm", str(stock["dims_mm"]), "由成品包络+余量派生", "stock_derivation"],
                ["毛坯包容性", stock["sanity"].get("ok"), str(stock["sanity"]), "stock_derivation"],
            ]
            allow = c["allowance"]
            for k in ("rough_single_side_mm", "semi_finish_single_side_mm",
                      "finish_single_side_mm", "corner_rest_allowance_mm",
                      "end_face_allowance_mm"):
                rows.append([k, allow.get(k), allow.get("handbook_ref", ""),
                             "《金属切削加工工艺手册》"])
            cl = c["clamping"]
            rows += [
                ["装夹方案", cl["name_zh"], cl["locating_principle"], cl["handbook_ref"]],
                ["定位自由度", cl["dof_constrained"], "3-2-1/5-DOF 定位", "《数控加工工艺规范》"],
                ["最小夹持深度 mm", cl["min_grip_depth_mm"], "—", "装夹标准"],
                ["最大悬伸比 L/D", cl["max_overhang_ld_ratio"], "—", "装夹标准"],
                ["重复定位精度 mm", cl["repeatability_mm"], cl["smed_interface"], "夹具手册"],
            ]
            sf = c["motion_safety"]
            for k in ("z_safe_global_mm", "z_r_plane_mm", "rapid_decel_zone_mm",
                      "xy_clearance_mm", "rapid_override_first_piece_pct"):
                rows.append([k, sf.get(k), "运动安全策略", "《数控加工工艺规范》"])
            rows.append(["配置门", c["_config_gate"]["passed"],
                         str(c["_config_gate"]["violations"]),
                         c["_config_gate"]["basis"]])
            lines.append(_tbl(rows, ["参数", "取值", "依据/来源", "标准出处"]))
            lines.append("")
        p = self.out / "reports" / "parameter_checklist.md"
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return p

    # ---------------------------------------------------------------- 操作手册
    def _manual(self, runs: List[Dict[str, Any]]) -> Path:
        lines = ["# 数控加工仿真系统 — 操作与换产配置手册", "",
                 f"版本 1.0.0  生成：{_ts()}", "",
                 "## 0. 系统定位与诚实边界", "",
                 "本系统为量产级数控加工仿真与验证 Agent，控制器逻辑对齐 FANUC 0i /",
                 "SINUMERIK 840D sl / 华中 HNC-8 公开编程手册，由确定性解释器实测。",
                 "**边界**：逻辑对齐公开规范 ≠ 任何具体机床的现场标定；逐帧干涉为几何",
                 "实测而非 VERICUT 布尔材料去除；Cpk/良品率若无实测样本标 simulated。",
                 "投入实际量产前必须完成：机床特定后处理核对、VERICUT 机床模型标定、",
                 "首件试切与三坐标实测。", "",
                 "## 1. 环境", "",
                 "- Python 3.12+（工作区 .venv），依赖 numpy / scipy / trimesh / pyyaml / asyncua",
                 "- 工作区：D:/Virtu模型", "",
                 "## 2. 运行", "",
                 "```bash",
                 "cd D:/Virtu模型/cnc_massprod_sim",
                 "../.venv/Scripts/python.exe run_sim.py            # 全部工件×方言",
                 "../.venv/Scripts/python.exe run_sim.py --step 0.5 --batch 50",
                 "../.venv/Scripts/python.exe run_sim.py --workpiece WP-SHAFT-3JAW --dialect fanuc",
                 "```", "",
                 "## 3. 支持的工件与控制系统", ""]
        rows = []
        seen = set()
        for r in runs:
            k = (r["workpiece_id"], r["nc"]["controller_id"])
            if k in seen:
                continue
            seen.add(k)
            rows.append([r["workpiece_id"], r["process_config"]["name_zh"],
                         r["process_config"]["material_id"], r["dialect"],
                         r["nc"]["controller_id"], r["nc"]["vericut_ctl_file"]])
        lines.append(_tbl(rows, ["工件ID", "名称", "材料", "方言", "控制器", "VERICUT CTL"]))
        lines += ["", "## 4. 换产配置（SMED，目标 ≤15 min）", ""]
        for r in runs[:1]:
            co = r.get("assurance", {}).get("changeover", {})
            lines.append(_tbl([[s["step"], s["planned_min"]] for s in co.get("steps", [])],
                              ["步骤", "计划分钟"]))
            lines.append(f"\n现场换装计划合计 {co.get('on_site_planned_min')} min；"
                         f"软件重构实测 {co.get('software_reconfig_s')} s；"
                         f"总 {co.get('total_min')} min（{co.get('verdict')}）。")
            lines.append(f"\n口径：{co.get('basis')}")
        lines += ["", "## 5. 断点续传与急停", "",
                 "- FANUC/HNC：程序头 #501=10/20/30/40 选择起始工序，GOTO 跳转；",
                 "  同时支持 N100/N200/N300/N400 顺序号搜索（Q-TYPE 刀具入口重启）。",
                 "- 西门子 840D sl：SERUPRO / 程序段搜索重启。",
                 "- 急停：CNC 面板 E-STOP 触发后 INTERLOCK 禁止进入 AUTO 模式；",
                 "  警报代码 EMG-001；复位需 release_e_stop_and_reset。",
                 "- 超程防护：双软限位（Stored Stroke Check 1&2）+ OT-X/Y/Z 报警。", "",
                 "## 6. 刀具补偿与换刀", "",
                 "- 长度补偿：FANUC/HNC G43 Hxx / G49；五轴 G43.4；西门子 T-D 刀沿。",
                 "- 半径补偿：G41/G42 Dxx，线性段引入/引出，G40 关闭（成对校验）。",
                 "- 换刀：G28 U0 W0 回参考点 → 换刀点 → Txxxx M06 → 补偿激活。",
                 "- ATC 校验：换刀前必须在换刀点（TOOL-CHANGE-POINT 判据）。", "",
                 "## 7. OPC UA 产线对接", "",
                 "端点：opc.tcp://<host>:4840/virtu/；命名空间 urn:virtu:production。",
                 "节点见 reports/opcua_nodes.md；自检见 verification_result.json.opcua。", "",
                 "## 8. 输出物", "",
                 "- programs/：三方言 × 三工件 NC 程序集（FANUC .nc / Siemens .mpf / HNC .nc）",
                 "- reports/：仿真验证报告、干涉检测报告、精度校验、节拍统计、参数清单",
                 "- logs/：仿真运行日志（逐条程序门结果）",
                 "- reports/verification_result.json：机器可读全量结果", "",
                 "## 9. 免责声明", "",
                 "本系统输出不得在未完成现场机床标定、后处理核对、首件试切与",
                 "VERICUT Auto-Diff 验证前直接用于实际生产。所有程序以仿真验证为目的。",
                 ]
        p = self.out / "docs" / "OPERATION_AND_CHANGEOVER_MANUAL.md"
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return p

    # ---------------------------------------------------------------- 主报告
    def _report(self, runs: List[Dict[str, Any]], summary: Dict[str, Any],
                full: Dict[str, Any]) -> Path:
        lines = ["# 量产级数控加工仿真验证报告", "",
                 f"生成：{_ts()}",
                 f"运行摘要：总计 {summary['total']}，通过 {summary['passed']}，"
                 f"失败 {summary['failed']}，耗时 {summary['elapsed_s']}s", "",
                 "## 口径声明", "",
                 "本报告遵循工作区《测量宪法》：每个数值带 basis；未实测项标未测，",
                 "禁止把源码字面量当实测结果。控制器执行 basis=measured_deterministic_emulator，",
                 "几何干涉 basis=measured，SPC/良品率若无实测样本 basis=simulated。", "",
                 "## 1. 总门结果", ""]
        rows = []
        for r in runs:
            rows.append([r["workpiece_id"], r["dialect"], r["nc"]["controller_id"],
                         r["status"],
                         " ".join(f"{k}:{v}" for k, v in r["gates"].items()),
                         r["nc"]["program_sha256"][:12]])
        lines.append(_tbl(rows, ["工件", "方言", "控制器", "总判定", "分项门", "程序SHA256"]))
        lines += ["", f"**总体判定：{'PASS' if summary['failed'] == 0 else 'FAILED'}**", "",
                  "## 1b. G/M 指令集匹配（控制器支持清单逐条比对）", ""]
        iset_rows = []
        for r in runs:
            s = r.get("instruction_set", {})
            iset_rows.append([r["workpiece_id"], r["dialect"], r["nc"]["controller_id"],
                              "PASS" if s.get("passed") else "FAIL",
                              len(s.get("used_g", [])), len(s.get("used_m", [])),
                              s.get("supported_g_count", "—"),
                              s.get("supported_m_count", "—"),
                              s.get("basis", "—")])
        lines.append(_tbl(iset_rows, ["工件", "方言", "控制器", "判定", "用G数",
                                      "用M数", "支持G数", "支持M数", "口径"]))
        lines += ["", "> 比对两侧用同一规范化（G4↔G04、M3↔M03），避免补零差异造成假阳性；",
                  "> 任一程序使用了控制器不支持的 G/M 代码即判红。", "",
                  "## 2. 静态与运行时审计", ""]
        a_rows = []
        for r in runs:
            a = r["audit"]
            a_rows.append([r["workpiece_id"], r["dialect"],
                           "PASS" if a["passed"] else "FAIL",
                           a["execution_summary"]["blocks_executed"],
                           a["execution_summary"]["segment_count"],
                           a["breakpoint_restart_op20_ok"],
                           len(a["issues"])])
        lines.append(_tbl(a_rows, ["工件", "方言", "审计", "执行块", "运动段",
                                   "断点重启", "问题数"]))
        lines += ["", "## 3. 逐帧仿真与干涉", ""]
        i_rows = []
        for r in runs:
            i = r["simulation"]["interference"]
            i_rows.append([r["workpiece_id"], r["dialect"],
                           i["summary"]["verdict"],
                           i["summary"].get("frames", r["simulation"].get("frame_count", "—")),
                           i.get("min_clearance_mm"), i["summary"]["violations"]])
        lines.append(_tbl(i_rows, ["工件", "方言", "判定", "帧数",
                                   "最小间隙mm", "违规"]))
        lines += ["", "## 4. 节拍与精度", ""]
        q_rows = []
        for r in runs:
            a = r.get("assurance", {})
            q_rows.append([r["workpiece_id"], r["dialect"],
                           r["simulation"]["execution"]["total_time_s"],
                           a.get("takt", {}).get("target_s", "—"),
                           a.get("spc", {}).get("cpk", "未测"),
                           a.get("yield_estimate_pct", "未测")])
        lines.append(_tbl(q_rows, ["工件", "方言", "节拍s", "目标s", "Cpk", "估算良品率%"]))
        lines += ["", "## 5. 量产保障", ""]
        w_rows = []
        for r in runs:
            a = r.get("assurance", {})
            w_rows.append([r["workpiece_id"], r["dialect"],
                           a.get("collision_risk", {}).get("level", "未测"),
                           a.get("changeover", {}).get("total_min", "未测"),
                           a.get("changeover", {}).get("verdict", "—"),
                           len(a.get("warnings", {}).get("alerts", []))])
        lines.append(_tbl(w_rows, ["工件", "方言", "撞机风险", "换产min",
                                   "换产判定", "预警数"]))
        lines += ["", "## 6. OPC UA 自检", ""]
        opcua = full.get("opcua", {})
        lines.append(f"- 协议栈可用：{opcua.get('available')}")
        lines.append(f"- 读写回读一致：{opcua.get('read_back_ok')}")
        lines.append(f"- basis：{opcua.get('basis', 'unmeasured')}")
        lines += ["", "## 7. 部署前必做（诚实边界）", "",
                  "1. 按具体机床型号/固件版本核对 G/M 代码支持表（controllers.yaml）。",
                  "2. VERICUT 导入对应 CTL 并加载机床模型，跑 Auto-Diff 偏差图。",
                  "3. 首件试切 + 三坐标实测关键特征，用实测样本重算 Cpk。",
                  "4. 现场标定软限位、刀具长度/半径补偿、G54 零点。",
                  "5. OPC UA 端点接入车间采集系统并验证节点写入。", ""]
        p = self.out / "reports" / "SIMULATION_VERIFICATION_REPORT.md"
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return p
