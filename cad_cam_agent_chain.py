# -*- coding: utf-8 -*-
"""
cad_cam_agent_chain.py — Virtu CAD/CAM 六大软件 Agent 链编排器

把用户的「许愿式」制造意图，经 virtu_omni 的 WishCADCAMEngine 分解为
六大工业软件的全套工程代码/配置，并按真实制造流水线顺序
（设计 → CAM → 出图 → 数控 → 仿真 → 实训）组织成带数据交接关系的工程包：
  - 每个阶段的工件独立落盘（.swb / .py / .lsp / .opt / .nc / .md）
  - manifest.json：阶段、依赖、文件、交接说明、各 app 真实入口
  - pipeline.json：节点 + 有向边，可直接喂给可视化
  - CHAIN_REPORT.md：人读版链路报告

用法:
  python cad_cam_agent_chain.py --wish "我想制造一款精密成型轮模 材质Cr12MoV 外径53mm 轴孔14mm 宽度45mm 三道圆弧槽R15 R12 R10"
  python cad_cam_agent_chain.py            # 用内置示例愿望
"""

import os
import sys
import re
import json
import datetime
import argparse

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from virtu_omni.agent.process_memory_reclaimer import ProcessMemoryReclaimer

# 六大软件在桌面上的真实入口（用户已安装），供后续「自动拉起」深度使用。
# 这里仅记录 lnk 路径，并在可能时解析出真实 exe 路径（实测证据）。
DESKTOP_LNK = {
    "sw2021":    r"C:\Users\Public\Desktop\SOLIDWORKS 2021.lnk",
    "cimco2026": r"C:\Users\Public\Desktop\CIMCO Edit 2026.lnk",
    "sscnc72":   r"C:\Users\Public\Desktop\斯沃数控仿真软件.lnk",
    "acad2026":  r"C:\Users\Public\Desktop\AutoCAD 2026 - 简体中文 (Simplified Chinese).lnk",
    "nx12":      r"C:\Users\Administrator\Desktop\中文版NX12.0.lnk",
    "vericut96": r"C:\Users\Public\Desktop\Vericut 9.6.lnk",
}

# 制造流水线：有序的 7 个 Agent 阶段（识图 -> 标注 -> 绘图 -> 建模 -> CAM -> 仿真 -> 加工）
STAGES = [
    {
        "key": "blueprint", "tool": "图纸识读与标注", "role": "图纸解析与GD&T基准标注",
        "method": "generate_blueprint_annotation", "ext": ".md",
        "depends_on": [],
        "handoff": "第一步：严格识读图纸标题栏、基准坐标系A/B、主次尺寸链与配合公差(H7/h7)，生成标准化标注清单，作为下游唯一几何基准。",
    },
    {
        "key": "acad2026", "tool": "AutoCAD 2026", "role": "国标工程图 / 2D绘图",
        "method": "generate_autocad_lisp", "ext": ".lsp",
        "depends_on": ["blueprint"],
        "handoff": "第二步：依据识图标注尺寸，在 AutoCAD 中分层绘制 2D 工程图（中心线/轮廓/尺寸标注/剖面线），完成平面图纸设计。",
    },
    {
        "key": "sw2021", "tool": "SOLIDWORKS 2021", "role": "参数化三维建模",
        "method": "generate_solidworks_macro", "ext": ".swb",
        "depends_on": ["blueprint", "acad2026"],
        "handoff": "第三步：将 2D 图纸尺寸映射为 3D 特征树（方程式驱动全局变量），构建旋转/拉伸实体并导出 STEP 实体模型。",
    },
    {
        "key": "nx12", "tool": "Siemens NX 12.0", "role": "复杂曲面 / CAM多轴刀路",
        "method": "generate_nx12_script", "ext": ".py",
        "depends_on": ["sw2021"],
        "handoff": "第四步：导入 STEP 实体，在 NX 中执行基于特征的加工(FBM)与复杂多轴刀路规划，输出加工刀位轨迹。",
    },
    {
        "key": "cimco2026", "tool": "CIMCO Edit 2026", "role": "FANUC Macro B 数控编程",
        "method": "generate_cimco_macro", "ext": ".nc",
        "depends_on": ["nx12", "sw2021"],
        "handoff": "第五步：编制/反演优化数控车削 Macro B 宏程序（G71粗车/G70精车/螺纹/割槽），配置刀具补偿。",
    },
    {
        "key": "vericut96", "tool": "Vericut 9.6", "role": "机床切削动力学仿真",
        "method": "generate_vericut_config", "ext": ".opt",
        "depends_on": ["cimco2026", "sw2021"],
        "handoff": "第六步：以 NC 代码 + 3D 模型装入虚拟五轴/卧加机床，执行防碰撞、Force 切削力与 Auto-Diff 0.003mm 过切检查。",
    },
    {
        "key": "sscnc72", "tool": "斯沃数控仿真 7.2", "role": "现场实训 / 虚拟走刀加工",
        "method": "generate_sscnc_setup_guide", "ext": ".md",
        "depends_on": ["cimco2026", "vericut96"],
        "handoff": "第七步：基于已校验 NC 代码，在斯沃数控系统设置 G54 工件坐标系、试切对刀，提交控制器执行闭环走刀加工。",
    },
]

DEFAULT_WISH = (
    "我想制造一款精密成型轮模（材质Cr12MoV，外径53mm、轴孔14mm、宽度45mm，"
    "三道圆弧槽R15、R12、R10）"
)


def resolve_lnk_target(lnk_path):
    """从 .lnk 解析出真实入口路径（WScript.Shell COM，回退 UTF-16LE 扫描）。失败返回 None。"""
    if not os.path.exists(lnk_path):
        return None
    # 首选：WScript.Shell COM（最可靠，能解析 MSI 广告入口等）
    try:
        import win32com.client
        ws = win32com.client.Dispatch("WScript.Shell")
        t = ws.CreateShortcut(lnk_path).TargetPath
        if t:
            return t
    except Exception:
        pass
    # 回退：UTF-16LE 字符串扫描
    try:
        with open(lnk_path, "rb") as f:
            data = f.read()
        text = data.decode("utf-16-le", errors="ignore")
        candidates = re.findall(r"[A-Za-z]:\\(?:[^\x00\\]+\\)*[^\x00\\]+\.(?:exe|bat|lnk)", text)
        best = None
        for c in candidates:
            c = c.strip().rstrip("\x00").strip()
            if c and os.path.exists(c):
                if best is None or len(c) > len(best):
                    best = c
        return best
    except Exception:
        return None


class CADCAMAgentChain:
    """六软件 Agent 链编排器。"""

    def __init__(self, wish_text, out_root=None):
        self.wish = wish_text
        self.out_root = out_root or os.path.join(ROOT, "runs", "cad_cam_chain")
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_id = ts
        self.out_dir = os.path.join(self.out_root, ts)
        self.engine = None
        self.spec = None
        self.artifacts = []  # [{key, tool, role, file, rel, method, depends_on, handoff, launch}]
        self._load_engine()
        self.reclaimer = ProcessMemoryReclaimer(log_path=os.path.join(self.out_dir, 'memory_reclamation.json'))

    def _load_engine(self):
        try:
            from virtu_omni.engine.wish_cad_cam_engine import WishCADCAMEngine
            self.engine = WishCADCAMEngine()
        except Exception as e:  # pragma: no cover
            raise RuntimeError("无法加载 WishCADCAMEngine：%s" % e)

    def run(self, execute=False, memory_safe=True):
        os.makedirs(self.out_dir, exist_ok=True)
        self.spec = self.engine.parse_wish_intent(self.wish)

        for idx, stage in enumerate(STAGES, start=1):
            gen = getattr(self.engine, stage["method"])
            content = gen(self.spec)
            fname = "%02d_%s%s" % (idx, stage["tool"].replace(" ", "_"), stage["ext"])
            fpath = os.path.join(self.out_dir, fname)
            with open(fpath, "w", encoding="utf-8") as fh:
                fh.write(content)
            lnk = DESKTOP_LNK.get(stage["key"])
            exe = resolve_lnk_target(lnk) if lnk else None
            self.artifacts.append({
                "order": idx,
                "key": stage["key"],
                "tool": stage["tool"],
                "role": stage["role"],
                "file": fname,
                "path": fpath,
                "rel": os.path.relpath(fpath, ROOT),
                "method": stage["method"],
                "depends_on": stage["depends_on"],
                "handoff": stage["handoff"],
                "launch": {"lnk": lnk, "exe": exe} if lnk else None,
            })
            print("  [%02d] %-22s -> %s" % (idx, stage["tool"], fname))

        self._write_manifest()
        self._write_pipeline()
        self._write_report()

        if execute:
            print("\n>>> 激活真实工业软件阶段式执行（内存安全保活机制）...")
            import agent_chain_executor
            agent_chain_executor.run_chain(self.wish, out_root=self.out_root, memory_safe=memory_safe)
        return self.out_dir

    def _write_manifest(self):
        manifest = {
            "chain": "Virtu CAD/CAM Six-Software Agent Chain",
            "run_id": self.run_id,
            "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "wish": self.wish,
            "spec": self.spec,
            "stage_count": len(self.artifacts),
            "artifacts": [
                {k: v for k, v in a.items() if k != "path"} for a in self.artifacts
            ],
        }
        with open(os.path.join(self.out_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

    def _write_pipeline(self):
        nodes = []
        edges = []
        order_map = {a["key"]: a["order"] for a in self.artifacts}
        for a in self.artifacts:
            nodes.append({
                "id": a["key"],
                "label": a["tool"],
                "role": a["role"],
                "file": a["file"],
                "exe": (a["launch"] or {}).get("exe"),
            })
            for dep in a["depends_on"]:
                if dep in order_map:
                    edges.append({"from": dep, "to": a["key"],
                                  "note": "数据交接：%s" % a["handoff"]})
        mermaid = ["flowchart LR"]
        for n in nodes:
            mermaid.append('  %s["%s<br/>%s"]' % (n["id"], n["label"], n["role"]))
        for e in edges:
            mermaid.append("  %s -->|交接| %s" % (e["from"], e["to"]))
        graph = {
            "nodes": nodes,
            "edges": edges,
            "mermaid": "\n".join(mermaid),
        }
        with open(os.path.join(self.out_dir, "pipeline.json"), "w", encoding="utf-8") as f:
            json.dump(graph, f, ensure_ascii=False, indent=2)

    def _write_report(self):
        lines = []
        lines.append("# Virtu CAD/CAM 六大软件 Agent 链 · 工程包报告\n")
        lines.append("- **运行 ID**: `%s`" % self.run_id)
        lines.append("- **制造愿望**: %s" % self.wish)
        lines.append("- **几何规格**: 外径 %.2f mm | 内孔 %.2f mm | 总长 %.2f mm | 圆角 R %.2f | 特征数 %d | 材质 %s"
                     % (self.spec["d_outer"], self.spec["d_inner"], self.spec["overall_len"],
                        self.spec["fillet_r"], self.spec["num_features"], self.spec["material"]))
        lines.append("- **多轴复杂曲面**: %s | **模具工装**: %s" % (self.spec["is_multiaxis"], self.spec["is_die_mold"]))
        lines.append("")
        lines.append("## 制造流水线（Agent 阶段与数据交接）\n")
        lines.append("```mermaid")
        # 重新生成 mermaid 给报告
        lines.append("flowchart LR")
        for a in self.artifacts:
            lines.append('  %s["%s<br/>%s"]' % (a["key"], a["tool"], a["role"]))
        for a in self.artifacts:
            for dep in a["depends_on"]:
                lines.append("  %s -->|交接| %s" % (dep, a["key"]))
        lines.append("```")
        lines.append("")
        lines.append("| # | 软件 | 角色 | 工件文件 | 依赖 | 数据交接 |")
        lines.append("| :-- | :-- | :-- | :-- | :-- | :-- |")
        for a in self.artifacts:
            deps = ", ".join(a["depends_on"]) or "（几何真值源）"
            lines.append("| %d | %s | %s | `%s` | %s | %s |"
                         % (a["order"], a["tool"], a["role"], a["file"], deps, a["handoff"]))
        lines.append("")
        lines.append("## 各软件真实入口（桌面 lnk / 解析出的 exe）\n")
        for a in self.artifacts:
            if a["launch"]:
                exe = a["launch"]["exe"] or "（未能从 lnk 解析，见 lnk 路径）"
                lines.append("- **%s**: lnk=`%s`  exe=`%s`" % (a["tool"], a["launch"]["lnk"], exe))
        lines.append("")
        lines.append("> 本工程包为「编排 + 全代码生成」层产出：六款软件工件已按流水线顺序生成并标注数据交接，")
        lines.append("> 尚未拉起 app。后续「自动拉起 / 全链路 GUI 执行」深度可直接复用本 manifest 中的 `launch.exe`。\n")
        with open(os.path.join(self.out_dir, "CHAIN_REPORT.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def summarize(self):
        print("\n=== Virtu CAD/CAM Agent 链 · 完成 ===")
        print("愿望   : %s" % self.wish)
        print("规格   : 外径 %.1f / 内孔 %.1f / 长 %.1f / R%.1f / %s"
              % (self.spec["d_outer"], self.spec["d_inner"], self.spec["overall_len"],
                 self.spec["fillet_r"], self.spec["material"]))
        print("输出目录: %s" % self.out_dir)
        print("工件数 : %d（含 manifest.json / pipeline.json / CHAIN_REPORT.md）" % len(self.artifacts))


def main():
    ap = argparse.ArgumentParser(description="Virtu CAD/CAM 六大软件 Agent 链编排器")
    ap.add_argument("--wish", default=DEFAULT_WISH, help="许愿式制造意图（自然语言）")
    ap.add_argument("--out", default=None, help="工程包输出根目录（默认 runs/cad_cam_chain）")
    ap.add_argument("--execute", action="store_true", help="按流水线调用原生工业软件执行并每步释放内存")
    args = ap.parse_args()

    print(">>> 启动 Virtu CAD/CAM Agent 链编排 ...")
    chain = CADCAMAgentChain(args.wish, out_root=args.out)
    chain.run(execute=args.execute)
    chain.summarize()


if __name__ == "__main__":
    main()
