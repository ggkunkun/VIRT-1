# -*- coding: utf-8 -*-
"""多智能体装配体理解框架（P3 解法）。

核心思想：把「读懂装配体」拆给 3 个确定性 facet 并行解析，
LLM 只做最后的语义综合——几何噪声不进大模型上下文。

  ┌ StructureFacet : 装配树 / 层级 / 父子 / 零件名
  ├ GeometryFacet  : 每零件实体·面数 / 图元谱(圆柱·平面·锥·环·样条) / 包围盒 / 半径谱
  └ PoseFacet      : 4x4 变换 / 摆放原点 / 装配关系数
            ↓
     Synthesizer   : 三路 JSON → 一段紧凑语义 prompt（给 13.63B）
            ↓ (可选 --llm)
     本地 Ollama（指挥 qwen2.5:3b@:11434 / 感知 wpt2-main@:8799）

默认完全离线、纯标准库；--llm 才尝试调用，失败自动降级为「只产出 prompt」。
用法:
  python3 bridges/multiagent_assembly.py assets/wheel_mold_P0.step
  python3 bridges/multiagent_assembly.py assets/wheel_mold_P0.step \
      --json reports/multiagent.json --prompt reports/multiagent_prompt.txt
  python3 bridges/multiagent_assembly.py assets/wheel_mold_P0.step --llm --model qwen2.5:3b
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.request
from collections import Counter
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from step_bom import StepBOM  # noqa: E402

PRIMITIVES = (
    "PLANE", "CYLINDRICAL_SURFACE", "CONICAL_SURFACE", "SPHERICAL_SURFACE",
    "TOROIDAL_SURFACE", "B_SPLINE_SURFACE_WITH_KNOTS", "B_SPLINE_SURFACE",
    "SURFACE_OF_REVOLUTION", "SURFACE_OF_LINEAR_EXTRUSION",
)
CURVES = ("CIRCLE", "LINE", "B_SPLINE_CURVE_WITH_KNOTS", "ELLIPSE")


class FacetResult:
    def __init__(self, name: str, data: Dict[str, Any], evidence: List[str]):
        self.name = name
        self.data = data
        self.evidence = evidence
        self.elapsed_ms = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {"facet": self.name, "status": "ok", "elapsed_ms": self.elapsed_ms,
                "evidence": self.evidence, "data": self.data}


class AssemblyMultiAgent:
    def __init__(self, step_path: str):
        if not os.path.isfile(step_path):
            raise FileNotFoundError(step_path)
        self.path = step_path
        self.raw = open(step_path, "rb").read()
        self.bom = StepBOM(step_path)
        self.d = self.bom.to_dict()
        self.sha256 = hashlib.sha256(self.raw).hexdigest()

    # -- Facet 1: 结构 ----------------------------------------------------
    def structure(self) -> FacetResult:
        t0 = time.perf_counter()
        nodes: List[Dict[str, Any]] = []

        def walk(n, depth=0, parent=None):
            nodes.append({
                "name": n["name"], "depth": depth, "parent": parent,
                "children_count": len(n.get("children", [])),
            })
            for c in n.get("children", []):
                walk(c, depth + 1, n["name"])

        for root in self.d["tree"]:
            walk(root)
        data = {
            "is_assembly": self.d["is_assembly"],
            "ap_version": self.d["ap_version"],
            "encoding": self.d["encoding"],
            "product_count": self.d["product_count"],
            "component_links": self.d["component_count"],
            "hierarchy": nodes,
            "max_depth": max((x["depth"] for x in nodes), default=0),
        }
        r = FacetResult("structure", data, [
            "NEXT_ASSEMBLY_USAGE_OCCURRENCE / PRODUCT_DEFINITION_USAGE",
            "PRODUCT_DEFINITION_SHAPE → PRODUCT_DEFINITION → PRODUCT",
            "FILE_SCHEMA / FILE_DESCRIPTION (AP 版本)",
        ])
        r.elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        return r

    # -- Facet 2: 几何图元谱 ---------------------------------------------
    def geometry(self) -> FacetResult:
        t0 = time.perf_counter()
        txt = self.raw.decode(self.d["encoding"], errors="replace")
        prim = Counter()
        for p in PRIMITIVES:
            prim[p] = len(re.findall(r"(?m)^\s*#\d+\s*=\s*" + p + r"\b", txt))
        curv = Counter()
        for c in CURVES:
            curv[c] = len(re.findall(r"(?m)^\s*#\d+\s*=\s*" + c + r"\b", txt))
        # CIRCLE 半径谱（CNC 领域关键：孔径/圆角）
        radii = Counter()
        for m in re.finditer(r"CIRCLE\s*\(\s*'[^']*'\s*,\s*#\d+\s*,\s*([-+0-9.Ee]+)\s*\)", txt):
            try:
                radii[round(float(m.group(1)), 3)] += 1
            except ValueError:
                pass
        per_part = []

        def walk(n):
            per_part.append({
                "name": n["name"],
                "solids": n["solids"],
                "faces": n["faces"],
                "features": n.get("features", []),
                "bbox_mm": n.get("bbox"),
            })
            for c in n.get("children", []):
                walk(c)

        for root in self.d["tree"]:
            walk(root)
        data = {
            "entity_count": self.d["entity_count"],
            "surface_primitives": {k: v for k, v in prim.items() if v},
            "curve_primitives": {k: v for k, v in curv.items() if v},
            "circle_radius_spectrum_mm": [
                {"radius_mm": k, "count": v} for k, v in sorted(radii.items())[:20]],
            "per_part": per_part,
            "total_solids": sum(x["solids"] for x in per_part),
            "total_faces": sum(x["faces"] for x in per_part),
        }
        r = FacetResult("geometry", data, [
            "MANIFOLD_SOLID_BREP / BREP_WITH_VOIDS / CLOSED_SHELL / ADVANCED_FACE",
            "PLANE/CYLINDRICAL_SURFACE/CONICAL_SURFACE… 实体计数",
            "CIRCLE('#',#axis,r) 半径谱",
            "CARTESIAN_POINT 包围盒 BFS",
        ])
        r.elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        return r

    # -- Facet 3: 位姿 ----------------------------------------------------
    def pose(self) -> FacetResult:
        t0 = time.perf_counter()
        placed = []

        def walk(n):
            if n.get("placement"):
                placed.append({
                    "name": n["name"],
                    "origin_mm": n["placement"]["origin_mm"],
                    "matrix_3x4": n["placement"]["matrix"],
                })
            for c in n.get("children", []):
                walk(c)

        for root in self.d["tree"]:
            walk(root)
        data = {
            "is_assembly": self.d["is_assembly"],
            "assembly_links": self.d["component_count"],
            "placements": placed,
            "placement_count": len(placed),
            "unit": "mm",
            "matrix_convention": "[X|Y|Z|T] 3x4，列向量式",
        }
        r = FacetResult("pose", data, [
            "REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION",
            "ITEM_DEFINED_TRANSFORMATION → AXIS2_PLACEMENT_3D → CARTESIAN_POINT",
        ])
        r.elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        return r

    # -- 合成 -------------------------------------------------------------
    def synthesize(self, facets: List[FacetResult]) -> str:
        s, g, p = (f.data for f in facets)
        L = [
            "你是 CNC/模具领域的装配体分析专家。以下三路解析结果由确定性 STEP 解析器"
            "实跑产出（非推测），请据此给出准确的装配体语义结论。",
            "",
            f"【文件】{self.d['source']} | AP {s['ap_version']} | 编码 {s['encoding']} "
            f"| 原始实体 {g['entity_count']} 个 | sha256 {self.sha256[:16]}",
            "",
            "【Facet-1 结构】" + ("装配体" if s["is_assembly"] else "单一零件") +
            f"，{s['product_count']} 个零件定义，{s['component_links']} 处装配关系，"
            f"层级最大深度 {s['max_depth']}。",
        ]
        for x in s["hierarchy"]:
            L.append("  " + "  " * x["depth"] + "└ " + x["name"] +
                     (f"（{x['children_count']} 个子件）" if x["children_count"] else ""))
        L += ["", "【Facet-2 几何】共 %d 个实体、%d 个面。" %
              (g["total_solids"], g["total_faces"])]
        if g["surface_primitives"]:
            L.append("  曲面图元谱: " + ", ".join(
                "%s=%d" % (k, v) for k, v in sorted(
                    g["surface_primitives"].items(), key=lambda kv: -kv[1])[:8]))
        if g["circle_radius_spectrum_mm"]:
            L.append("  圆半径谱(mm): " + ", ".join(
                "R%s×%d" % (x["radius_mm"], x["count"])
                for x in g["circle_radius_spectrum_mm"][:8]))
        for x in g["per_part"]:
            if x["solids"] > 0:
                L.append("  · %s: %d 实体 / %d 面%s%s" % (
                    x["name"], x["solids"], x["faces"],
                    ("，特征 " + "、".join(x["features"])) if x["features"] else "",
                    ("，包围盒 %s" % x["bbox_mm"]) if x["bbox_mm"] else ""))
        L += ["", "【Facet-3 位姿】%d 个子件有摆放坐标（单位 mm，3x4 矩阵 [X|Y|Z|T]）。" %
              p["placement_count"]]
        for x in p["placements"]:
            L.append("  · %s @ (%s)" % (
                x["name"], ", ".join(str(v) for v in x["origin_mm"])))
        L += ["", "【紧凑 DSL】", "```dsl", self.bom.to_dsl(), "```", "",
              "请输出：① 装配体构成与层级；② 各零件几何特征与可能的加工工艺；"
              "③ 装配定位关系；④ 若信息不足请明确指出，不要臆测未给出的尺寸。"]
        return "\n".join(L)

    def run(self, with_llm: bool = False, model: str = "qwen2.5:3b",
            endpoint: str = "http://127.0.0.1:11434") -> Dict[str, Any]:
        facets = [self.structure(), self.geometry(), self.pose()]
        prompt = self.synthesize(facets)
        out: Dict[str, Any] = {
            "status": "ok",
            "tool": "bridges.multiagent_assembly",
            "basis": "measured",
            "source": self.d["source"],
            "source_sha256": self.sha256,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "architecture": "3 deterministic facets (structure/geometry/pose) + 1 LLM synthesizer",
            "facets": [f.to_dict() for f in facets],
            "synthesis_prompt_chars": len(prompt),
            "synthesis_prompt": prompt,
            "llm_response": None,
        }
        if with_llm:
            out["llm_response"] = self._call_ollama(prompt, model, endpoint)
        return out

    def _call_ollama(self, prompt: str, model: str, endpoint: str) -> Dict[str, Any]:
        """可选：调用本地 Ollama；失败优雅降级（不抛异常）。"""
        payload = json.dumps({
            "model": model, "prompt": prompt, "stream": False,
            "options": {"temperature": 0.1, "num_ctx": 8192},
        }).encode("utf-8")
        req = urllib.request.Request(
            endpoint.rstrip("/") + "/api/generate", data=payload,
            headers={"Content-Type": "application/json"})
        try:
            # 绕过工具侧透明代理，直连本机 Ollama
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(req, timeout=90) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            return {"status": "ok", "model": model,
                    "response": body.get("response", ""),
                    "eval_count": body.get("eval_count")}
        except Exception as exc:  # noqa: BLE001
            return {"status": "unavailable", "model": model,
                    "error": "%s: %s" % (type(exc).__name__, exc),
                    "fallback": "已产出 synthesis_prompt，可离线交由其它模型消费"}


def main(argv=None):
    ap = argparse.ArgumentParser(description="多智能体装配体理解")
    ap.add_argument("step")
    ap.add_argument("--json", default="")
    ap.add_argument("--prompt", default="", help="单独写出综合 prompt")
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--model", default="qwen2.5:3b")
    ap.add_argument("--endpoint", default="http://127.0.0.1:11434")
    a = ap.parse_args(argv)
    agent = AssemblyMultiAgent(a.step)
    rep = agent.run(with_llm=a.llm, model=a.model, endpoint=a.endpoint)
    print("[multiagent] %s | %s | 实体 %d | facet 耗时 %s ms" % (
        rep["source"], rep["architecture"],
        rep["facets"][1]["data"]["entity_count"],
        [f["elapsed_ms"] for f in rep["facets"]]))
    print("  合成 prompt: %d 字符" % rep["synthesis_prompt_chars"])
    if rep["llm_response"]:
        lr = rep["llm_response"]
        print("  LLM: %s %s" % (lr["status"], lr.get("error", "")))
    print()
    print(rep["synthesis_prompt"][:1800])
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)), exist_ok=True)
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(rep, f, ensure_ascii=False, indent=2)
        print("\n[+] 写出 JSON: %s" % a.json)
    if a.prompt:
        os.makedirs(os.path.dirname(os.path.abspath(a.prompt)), exist_ok=True)
        with open(a.prompt, "w", encoding="utf-8") as f:
            f.write(rep["synthesis_prompt"])
        print("[+] 写出 prompt: %s" % a.prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
