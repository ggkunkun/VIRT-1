# -*- coding: utf-8 -*-
"""
industrial_toolbox.py — Virtu Agent 本地工业知识与国标查表工具库
数据源: e:\\数据 (GB型材库, 自动化标准件库, 《机械设计手册 第六版》6632条知识切片)

【设计原则】
1. 0 显存占用，0 训练成本，纯本地 Python 执行；
2. 100% 确定性查表，杜绝大模型在尺寸、米重、配合公差上的数字幻觉；
3. 为 Agent (WorkBuddy / LangChain / 自研网桥) 提供标准 Tool Calling 接口。
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

DATA_ROOT = os.environ.get("VIRTU_DATA_ROOT", r"e:\数据")
PROFILES_PATH = os.path.join(DATA_ROOT, "05_STANDARDS_AND_COMPONENTS_LIBRARY", "gb_profiles_catalog.json")
PARTS_PATH = os.path.join(DATA_ROOT, "05_STANDARDS_AND_COMPONENTS_LIBRARY", "standard_parts_taxonomy.json")
HANDBOOK_PATH = os.path.join(DATA_ROOT, "03_MECHANICAL_HANDBOOK_RAG_AND_QA", "mechanical_handbook_knowledge_chunks.jsonl")


class IndustrialToolbox:
    _instance: Optional["IndustrialToolbox"] = None

    def __init__(self, data_root: str = DATA_ROOT):
        self.data_root = data_root
        self.profiles_path = os.path.join(data_root, "05_STANDARDS_AND_COMPONENTS_LIBRARY", "gb_profiles_catalog.json")
        self.parts_path = os.path.join(data_root, "05_STANDARDS_AND_COMPONENTS_LIBRARY", "standard_parts_taxonomy.json")
        self.handbook_path = os.path.join(data_root, "03_MECHANICAL_HANDBOOK_RAG_AND_QA", "mechanical_handbook_knowledge_chunks.jsonl")
        
        self._profiles_data: Optional[Dict[str, Any]] = None
        self._parts_data: Optional[Dict[str, Any]] = None
        self._handbook_chunks: Optional[List[Dict[str, Any]]] = None

    @classmethod
    def get_instance(cls) -> "IndustrialToolbox":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # -------------------------------------------------------------------------
    # 1. GB 国标焊接结构型材检索 (100% 确定性物理参数)
    # -------------------------------------------------------------------------
    def _load_profiles(self) -> Dict[str, Any]:
        if self._profiles_data is None:
            if not os.path.exists(self.profiles_path):
                return {"error": f"型材库文件不存在: {self.profiles_path}"}
            with open(self.profiles_path, "r", encoding="utf-8") as f:
                self._profiles_data = json.load(f)
        return self._profiles_data

    def query_gb_profile(self, spec_query: str, category: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """
        检索 GB 国标型材参数（外径/壁厚/米重）。
        例如: query_gb_profile("100 x 100 x 4") 或 query_gb_profile("方管 80")
        """
        data = self._load_profiles()
        if "error" in data:
            return [data]

        clean_q = re.sub(r"[\s*xX×]+", " ", spec_query).strip().lower()
        query_tokens = clean_q.split()

        matches = []
        categories = data.get("categories", {})
        for cat_name, cat_obj in categories.items():
            if category and category.lower() not in cat_name.lower():
                continue
            for spec in cat_obj.get("specs", []):
                spec_str = spec.get("profile_spec", "")
                clean_spec = re.sub(r"[\s*xX×]+", " ", spec_str).strip().lower()
                
                # 计算匹配度
                score = 0
                if clean_q == clean_spec:
                    score += 100
                elif all(t in clean_spec for t in query_tokens):
                    score += 50
                elif any(t in clean_spec for t in query_tokens):
                    score += 10
                
                if score > 0:
                    matches.append({
                        "category": cat_name,
                        "profile_spec": spec.get("profile_spec"),
                        "filename": spec.get("filename"),
                        "parsed_dimensions": spec.get("parsed_dimensions"),
                        "linear_density_kg_m": spec.get("estimated_linear_density_kg_m"),
                        "score": score
                    })

        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches[:limit]

    # -------------------------------------------------------------------------
    # 2. 工业自动化标准件与外购件检索 (COTS 部件体系)
    # -------------------------------------------------------------------------
    def _load_parts(self) -> Dict[str, Any]:
        if self._parts_data is None:
            if not os.path.exists(self.parts_path):
                return {"error": f"标准件库文件不存在: {self.parts_path}"}
            with open(self.parts_path, "r", encoding="utf-8") as f:
                self._parts_data = json.load(f)
        return self._parts_data

    def query_standard_part(self, keyword: str, category: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """
        检索工业自动化常用标准件（气缸/丝杠座/电机/导轨/传感器等）。
        例如: query_standard_part("LEB01") 或 query_standard_part("CCD")
        """
        data = self._load_parts()
        if "error" in data:
            return [data]

        kw = keyword.strip().lower()
        matches = []
        categories = data.get("categories", {})
        for cat_name, cat_obj in categories.items():
            if category and category.lower() not in cat_name.lower():
                continue
            for comp in cat_obj.get("components", []):
                code = comp.get("component_code", "").lower()
                fname = comp.get("file_name", "").lower()
                if kw in code or kw in fname or kw in cat_name.lower():
                    matches.append({
                        "category": cat_name,
                        "component_code": comp.get("component_code"),
                        "file_name": comp.get("file_name"),
                        "type": comp.get("type")
                    })
                    if len(matches) >= limit:
                        return matches
        return matches

    # -------------------------------------------------------------------------
    # 3. 《机械设计手册》本地知识检索 (RAG 核心切片，6,632 条)
    # -------------------------------------------------------------------------
    def _load_handbook(self) -> List[Dict[str, Any]]:
        if self._handbook_chunks is None:
            if not os.path.exists(self.handbook_path):
                return []
            chunks = []
            with open(self.handbook_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        chunks.append(json.loads(line))
            self._handbook_chunks = chunks
        return self._handbook_chunks

    def search_mechanical_handbook(self, query: str, volume: Optional[int] = None, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        检索《机械设计手册 第六版》权威公式、材料参数与工程规则。
        例如: search_mechanical_handbook("圆柱齿轮模数计算") 或 search_mechanical_handbook("轴承配合公差", volume=1)
        """
        chunks = self._load_handbook()
        if not chunks:
            return [{"error": f"机械手册切片库未就绪: {self.handbook_path}"}]

        tokens = [t.strip().lower() for t in re.split(r"[\s,;，。；]+", query) if len(t.strip()) > 1]
        if not tokens:
            tokens = [query.lower()]

        scored = []
        for ch in chunks:
            if volume and ch.get("volume") != volume:
                continue
            text = ch.get("text_chunk", "")
            vol_title = ch.get("volume_title", "")
            
            # 统计词频命中与覆盖度
            score = 0
            for tk in tokens:
                count = text.lower().count(tk)
                if count > 0:
                    score += min(count, 5) * 2
                if tk in vol_title.lower():
                    score += 10
            
            if score > 0:
                scored.append((score, ch))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for s, ch in scored[:top_k]:
            results.append({
                "chunk_id": ch.get("chunk_id"),
                "volume": ch.get("volume"),
                "volume_title": ch.get("volume_title"),
                "page_range": f"p.{ch.get('page_start')}-{ch.get('page_end')}",
                "relevance_score": s,
                "text_snippet": ch.get("text_chunk", "")[:500] + "..."
            })
        return results

    # -------------------------------------------------------------------------
    # 4. Agent 工具调用通用分发器
    # -------------------------------------------------------------------------
    def dispatch(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """为 Agent 框架提供统一的 Tool Calling 分发入口"""
        if tool_name in ("cad.query_gb_profile", "query_gb_profile"):
            return {
                "status": "success",
                "tool": tool_name,
                "data": self.query_gb_profile(
                    spec_query=arguments.get("spec_query", arguments.get("keyword", "")),
                    category=arguments.get("category"),
                    limit=int(arguments.get("limit", 5))
                )
            }
        elif tool_name in ("cad.query_standard_part", "query_standard_part", "cad.query_standard_parts_library"):
            return {
                "status": "success",
                "tool": tool_name,
                "data": self.query_standard_part(
                    keyword=arguments.get("keyword", arguments.get("standard_code", "")),
                    category=arguments.get("category"),
                    limit=int(arguments.get("limit", 5))
                )
            }
        elif tool_name in ("cad.search_mechanical_handbook", "search_mechanical_handbook"):
            return {
                "status": "success",
                "tool": tool_name,
                "data": self.search_mechanical_handbook(
                    query=arguments.get("query", ""),
                    volume=arguments.get("volume"),
                    top_k=int(arguments.get("top_k", 3))
                )
            }
        else:
            return {"status": "error", "error": f"未知的知识工具: {tool_name}"}


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    toolbox = IndustrialToolbox.get_instance()
    
    print("\n--- 1. 测试 GB 型材查表 ---")
    res1 = toolbox.query_gb_profile("100 x 100 x 4")
    print(json.dumps(res1, ensure_ascii=False, indent=2))
    
    print("\n--- 2. 测试 自动化标准件检索 ---")
    res2 = toolbox.query_standard_part("LEB01")
    print(json.dumps(res2, ensure_ascii=False, indent=2))
    
    print("\n--- 3. 测试 机械设计手册知识检索 ---")
    res3 = toolbox.search_mechanical_handbook("圆柱齿轮 模数", volume=3, top_k=2)
    print(json.dumps(res3, ensure_ascii=False, indent=2))
