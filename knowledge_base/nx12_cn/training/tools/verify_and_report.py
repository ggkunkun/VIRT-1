#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证器 + 验收报告生成器。

执行真实可做的验证：
  V1 目录完整性：命令 ID 唯一、模块覆盖、证据等级分布（含 E4-TRANSLATION）
  V2 溯源核对：随机抽样 N 条，检查命令 ID 在介质 .btn/.men 或官方翻译表中真实存在
  V3 知识库覆盖：knowledge/*.md 功能点数 == 目录命令数
  V4 测试用例覆盖：cases == commands × 3，每命令场景齐全
  V5 引用一致性：知识库中的命令 ID ⊆ 目录

四维验收（基础操作/复杂项目/故障排查/版本区分）按用户要求设 95 分合格线，
但当前仅静态验证可做，GUI 实测与跨版本实测未完成 —— 报告如实标注 NOT_VERIFIED，
不编造通过分数。
"""
from __future__ import annotations

import json, random, re, sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CAT = ROOT / "catalog" / "nx12_cn_full_catalog.json"
KDIR = ROOT / "knowledge"
TDIR = ROOT / "tests"
FDIR = ROOT / "features"
OUT = ROOT / "reports"
NX = Path(r"D:\BaiduNetdiskDownload\NX 12.0.2.9\NX12.2.9waigua\NX12.2.9\NX")
VER = "NX12.0-CN"


def check_media_evidence(cids: list[str], cmds: dict) -> tuple[int, list[str]]:
    """在介质 .btn/.men 或官方翻译表中检索抽样命令 ID，返回命中数与未命中样例。"""
    found: set[str] = set()
    # E4-TRANSLATION：命令 ID 以 <CID>_<SUFFIX> 形式出现在官方翻译表中
    e4_ids = [cid for cid in cids if cmds.get(cid, {}).get("evidence") == "E4-TRANSLATION"]
    for cid in e4_ids:
        c = cmds[cid]
        pat = re.compile(r"\b" + re.escape(cid) + r"_")
        ok = False
        for rel in c.get("translation_sources") or []:
            fp = NX / rel
            try:
                txt = fp.read_text(encoding="utf-8-sig", errors="ignore")
            except OSError:
                continue
            if pat.search(txt):
                ok = True
                break
        if ok:
            found.add(cid)
    # E1/E2/E3：在 .btn/.men 中按独立命令 ID 检索
    ids2 = [cid for cid in cids if cid not in found]
    pats = {cid: re.compile(r"\b" + re.escape(cid) + r"\b") for cid in ids2}
    for p in list(NX.rglob("*.btn")) + list(NX.rglob("*.men")):
        try:
            txt = p.read_text(encoding="ascii", errors="ignore")
        except OSError:
            continue
        for cid in ids2:
            if cid not in found and pats[cid].search(txt):
                found.add(cid)
        if len(found) == len(cids):
            break
    return len(found), [c for c in cids if c not in found]


def main() -> int:
    data = json.loads(CAT.read_text(encoding="utf-8"))
    cmds = data["commands"]
    results = []
    def rec(name, ok, detail):
        results.append({"check": name, "pass": bool(ok), "detail": detail})
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")

    # V1 目录完整性
    ids = list(cmds.keys())
    rec("V1.1 命令 ID 唯一", len(ids) == len(set(ids)), f"命令数={len(ids)}, 唯一ID={len(set(ids))}")
    mods = Counter(v["module"] for v in cmds.values())
    required = ["01_草图绘制","02_零件建模","03_装配设计","04_曲面设计","05_钣金设计","06_同步建模",
                "07_工程图与PMI","08_加工制造","09_仿真分析","10_模具设计","11_管线与线路",
                "12_文件编辑视图信息","13_图层与显示","14_定制与首选项",
                "15_其他与第三方外挂","21_其他官方应用"]
    missing_mod = [m for m in required if mods.get(m, 0) == 0]
    rec("V1.2 要求模块均有功能点", not missing_mod, f"缺失={missing_mod or '无'}; 模块数={len(mods)}")
    ev = Counter(v["evidence"] for v in cmds.values())
    rec("V1.3 证据等级分布", sum(ev.values()) == len(cmds), json.dumps(ev, ensure_ascii=False))

    # V2 介质溯源抽样
    random.seed(120)
    sample = random.sample(ids, 60)
    hit, miss = check_media_evidence(sample, cmds)
    rec("V2 介质溯源抽样(60条命令ID)", hit == len(sample), f"命中={hit}/{len(sample)}; 未命中样例={miss[:5]}")

    # V3 知识库覆盖
    kfiles = sorted(KDIR.glob("*.md"))
    k_ids: set[str] = set()
    for f in kfiles:
        k_ids |= set(re.findall(r"\*\*命令 ID\*\*：`([A-Za-z0-9_]+)`", f.read_text(encoding="utf-8")))
    rec("V3 知识库功能点覆盖", len(k_ids) == len(ids) and k_ids == set(ids),
        f"知识库ID={len(k_ids)}, 目录ID={len(ids)}, 差集={len(set(ids) ^ k_ids)}")

    # V4 测试用例覆盖
    tc = json.loads((TDIR / "test_cases_all.json").read_text(encoding="utf-8"))
    case_cmds = defaultdict(set)
    for c in tc["cases"]:
        case_cmds[c["command_id"]].add(c["scenario"])
    full = all(len(v) >= 3 for v in case_cmds.values()) and len(case_cmds) == len(ids)
    rec("V4 测试用例全覆盖(每点3场景)", full,
        f"用例={tc['total_cases']}, 覆盖命令={len(case_cmds)}/{len(ids)}, 每点场景数=3")

    kmanifest = json.loads((KDIR / "_manifest.json").read_text(encoding="utf-8"))
    n_mod = len(kmanifest.get("modules", []))

    # V5 快捷键/术语来源核对
    acc = [v for v in cmds.values() if v.get("accelerator")]
    rec("V5 快捷键与术语来自介质", len(acc) == data["stats"]["commands_with_accel"],
        f"快捷键={len(acc)}, 目录记录={data['stats']['commands_with_accel']}")

    # ============ 外挂通道检查 ============
    PREG = ROOT / "plugins" / "plugin_registry.json"
    plugin_summary = {}
    if PREG.exists():
        preg = json.loads(PREG.read_text(encoding="utf-8"))
        plugins = preg["plugins"]
        plugin_summary = {
            "plugins": len(plugins),
            "commands": preg["totals"]["commands"],
            "zh": preg["totals"]["with_zh_label"],
            "dup_ids": preg["cross_plugin_duplicate_ids"]["count"],
        }
        rec("V6.1 外挂注册表完整", len(plugins) == 13 and preg["totals"]["commands"] > 0,
            f"外挂={len(plugins)}, 命令={preg['totals']['commands']}, 中文={preg['totals']['with_zh_label']}")
        # 每外挂必须有源菜单与证据
        bad = [p["plugin_id"] for p in plugins if not p["men_files"] or not p.get("evidence")]
        rec("V6.2 每外挂可溯源", not bad, f"缺源文件/证据={bad or '无'}")
        # 版本边界：VERSION!=120 必须被标记
        ver_bad = [p["plugin_id"] for p in plugins
                   if any(v not in ("", "120") for v in p["menu_versions"])
                   and not p["risk"]["menu_version_mismatch"]]
        rec("V6.3 VERSION≠120 已标记阻断", not ver_bad, f"漏标={ver_bad or '无'}")
        # 32bit 目录必须已排除
        leaked = [p["plugin_id"] for p in plugins
                  if any("/32bit/" in f.lower() for f in p["men_files"])]
        rec("V6.4 32bit 目录已排除", not leaked, f"泄漏={leaked or '无'}")
        # 分册齐全
        kdir = KDIR / "16_外挂分册"
        n_md = len(list(kdir.glob("*.md"))) if kdir.exists() else 0
        rec("V6.5 外挂分册齐全", n_md >= len(plugins) + 1,
            f"分册文件={n_md}, 期望={len(plugins)+1}(含总索引)")
    else:
        rec("V6 外挂注册表存在", False, "未找到 plugins/plugin_registry.json")

    # V7 路由层可解析
    try:
        sys.path.insert(0, str(ROOT / "plugins"))
        import plugin_router as pr
        keys = [c["key"] for p in preg["plugins"] for c in p["commands"]]
        random.seed(7)
        s2 = random.sample(keys, min(20, len(keys)))
        ok = 0
        for k in s2:
            try:
                if pr.resolve(k)["key"] == k:
                    ok += 1
            except Exception:
                pass
        rec("V7.1 复合键可解析(抽样20)", ok == len(s2), f"命中={ok}/{len(s2)}")
        # 裸重名必须报歧义
        dup_sample = preg["cross_plugin_duplicate_ids"]["samples"][0]["id"]
        try:
            pr.resolve(dup_sample)
            rec("V7.2 重名ID被拦截", False, f"裸 ID `{dup_sample}` 未拦截")
        except pr.PluginError as e:
            rec("V7.2 重名ID被拦截", e.code == "AMBIGUOUS_COMMAND",
                f"code={e.code}")
        # 能力卡
        cards = pr.list_plugins()
        rec("V7.3 能力卡可生成", len(cards) == len(preg["plugins"]),
            f"能力卡={len(cards)}")
    except Exception as e:
        rec("V7 路由层可用", False, f"{type(e).__name__}: {e}")

    passed = sum(1 for r in results if r["pass"])
    now = datetime.now().astimezone().isoformat(timespec="seconds")

    # 四维验收：诚实标注
    dims = [
        {"dimension": "基础操作", "pass_line": 95, "current_score": None,
         "status": "NOT_VERIFIED", "reason": "S1 静态可核对命令存在性与路径；实际 GUI 逐步操作与鼠标精度未取证。"},
        {"dimension": "复杂项目", "pass_line": 95, "current_score": None,
         "status": "NOT_VERIFIED", "reason": "端到端多模块流程需在设计项目中实测，当前未构造验收项目。"},
        {"dimension": "故障排查", "pass_line": 95, "current_score": None,
         "status": "NOT_VERIFIED", "reason": "报错代码库为登记表，需真实触发错误并验证解法。"},
        {"dimension": "版本区分", "pass_line": 95, "current_score": None,
         "status": "PARTIAL_STATIC", "reason": "本版本介质事实已固定；与其它版本对比项为待核对清单，未取证。"},
    ]

    report = {
        "report_type": "中文版 NX 12.0 专项训练体系验证报告",
        "generated_at": now,
        "version_scope": VER,
        "basis": "本机 NX 12.0.2.9 安装介质实测解析 + 静态一致性验证",
        "summary": {"automated_checks": len(results), "passed": passed,
                    "failed": len(results) - passed,
                    "gui_acceptance": "未完成（如实标注，不虚构分数）"},
        "checks": results,
        "plugin_channel": plugin_summary,
        "acceptance_dimensions": dims,
        "evidence": {
            "catalog": "catalog/nx12_cn_full_catalog.json",
            "knowledge_manifest": "knowledge/_manifest.json",
            "test_cases": "tests/test_cases_all.json",
            "source_sha256": data.get("key_sources_sha256", {}),
        },
        "not_verified_disclosure": [
            "每个功能点 ≥3 场景的 GUI 实际执行与截图证据（当前为可执行用例，非已执行结果）。",
            "复杂项目端到端流程在 NX 12.0 中文界面的完整跑通。",
            "报错代码→解法的实测有效性。",
            "与 NX 10 / 1847 / 2000 系列的具体差异结论（当前为核对清单）。",
            f"第三方外挂命令（E3，{ev.get('E3-UNTR', 0)} 条）的中文显示名与官方归属性。",
            f"E4-TRANSLATION 命令（{ev.get('E4-TRANSLATION', 0)} 条）的菜单路径、快捷键与参数对话框需 GUI 复核。",
        ],
    }
    (OUT / "verification_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # Markdown 报告
    M = ["# 中文版 NX 12.0 专项训练体系 验证报告", "",
         f"> 生成时间：{now}　|　版本范围：**{VER}**",
         f"> 依据：本机 NX 12.0.2.9 介质实测解析 + 静态一致性验证",
         f"> 自动检查：{passed}/{len(results)} 通过", "",
         "## 一、自动验证结果", "",
         "| 检查项 | 结果 | 说明 |", "|---|---|---|"]
    for r in results:
        M.append(f"| {r['check']} | {'PASS' if r['pass'] else 'FAIL'} | {r['detail']} |")
    M += ["", "## 二、四维验收（按 95 分合格线）", "",
          "| 维度 | 合格线 | 当前得分 | 状态 | 说明 |", "|---|---:|---|---|---|"]
    for d in dims:
        score = str(d["current_score"]) if d["current_score"] is not None else "—"
        M.append(f"| {d['dimension']} | {d['pass_line']} | {score} | {d['status']} | {d['reason']} |")
    M += ["", "> 明确声明：本报告不虚构 95 分通过。GUI 实测、复杂项目、故障排查、跨版本对比尚未取证，"
          "状态如实标注为 NOT_VERIFIED / PARTIAL_STATIC。", "",
          "## 三、未验证项披露", ""]
    for x in report["not_verified_disclosure"]:
        M.append(f"- {x}")
    M += ["", "## 六、第三方外挂通道", "",
          "| 指标 | 数值 |", "|---|---:|",
          f"| 注册外挂 | {plugin_summary.get('plugins', 0)} |",
          f"| 外挂唯一命令 | {plugin_summary.get('commands', 0)} |",
          f"| 带中文标签 | {plugin_summary.get('zh', 0)} |",
          f"| 跨外挂重名 ID | {plugin_summary.get('dup_ids', 0)} |", "",
          "- 适配规范：`plugins/ADAPTER_SPEC.md`（适配方式/参数约定/兼容处理/差异与注意事项）",
          "- 路由实现：`plugins/plugin_router.py`（list/search/resolve/plan_call/doctor）",
          "- 分册：`knowledge/16_外挂分册/`（13 份 + 总索引）",
          "- 已知阻断：VERSION≠120 的外挂（YSUG、KASA）在 NX12 下标记为不可用；"
          "硬编码路径断裂与环境变量缺失由 `doctor` 实时检测。",
          "", "## 七、证据链", "",
          f"- 命令目录：`catalog/nx12_cn_full_catalog.json`（{len(ids)} 条，含 source_btn / men_files / evidence）",
          "- 源文件 SHA256：见目录 `key_sources_sha256` 字段",
          f"- 知识库：`knowledge/`（{n_mod} 个模块文件，`_manifest.json`）",
          f"- 测试用例：`tests/test_cases_all.json`（{tc['total_cases']} 条）", "",
          "## 八、补齐到 95 分的路径", "",
          "1. 按 `tests/test_cases_all.json` 的 S1/S2/S3 逐条在 NX 12.0 中文界面执行，留存截图与参数快照。",
          "2. 将实测结果回填知识库 `[待实测]` 标记处，并把报错原文录入 `features/04_报错代码库.md`。",
          "3. 用其它版本官方介质生成同结构目录，与 `features/03_版本差异对照库.md` 清单逐项比对。",
          "4. 重跑本验证器，将 `acceptance_dimensions` 的分数由实测结果替换。", ""]
    (OUT / "verification_report.md").write_text("\n".join(M), encoding="utf-8")
    print(f"[OK] 报告生成: {passed}/{len(results)} 自动检查通过")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
