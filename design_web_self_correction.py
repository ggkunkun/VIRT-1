# -*- coding: utf-8 -*-
"""design_web_self_correction.py — 把"联网搜索"接进设计-修正闭环。

现状痛点（见 virtu_omni/agent/super_agent.py:_solve_react_pipeline）：
    硬编码 6 步流水线里 *没有* 任何"搜索 -> 对照 -> 修正"步骤；
    facet_internet_deep_learning 只是"摄入知识"型，不在设计修正闭环中。
    设计是闭门造车，不会用外部工艺/标准/案例核对并改正自己。

本模块提供：
    1. SearchProvider 抽象：真实引擎走 virtu_omni.internet.search_engine，
       离线/沙箱走 MockProvider（保证可独立验证，不依赖外网）。
    2. verify_and_correct(design_spec, topic)：检索 -> 抽取关键建议 ->
       与当前设计参数比对 -> 产出 corrections（差异清单+修正建议）。
    3. 可直接在 REACT 循环的 generate_parametric_cad 之后调用。

用法：
    from design_web_self_correction import verify_and_correct
    report = verify_and_correct({"material":"7075","surface_finish":"Ra6.3",
                                 "tolerance":"IT10"}, "铝合金 7075 五轴铣削 表面粗糙度 公差")
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# 搜索提供方抽象
# ---------------------------------------------------------------------------
class SearchProvider:
    """搜索接口。真实实现走 virtu_omni 的 WebSearchEngine；离线用 Mock。"""

    def search(self, query: str, num_results: int = 5) -> List[Dict[str, str]]:
        raise NotImplementedError


class MockSearchProvider(SearchProvider):
    """离线 mock：返回与 query 关键词相关的固定证据，用于无网环境验证逻辑。"""

    _KB = {
        "铝合金": "铝合金 7075 五轴铣削 推荐表面粗糙度 Ra1.6，粗加工 Ra3.2；"
                  "标准公差等级常用 IT7~IT8，薄壁件取 IT7。",
        "钛合金": "钛合金 TC4 铣削线速度 30~50 m/min，每齿进给 0.05~0.1 mm；"
                  "表面粗糙度要求 Ra0.8 时需精铣+抛光。",
        "不锈钢": "不锈钢 316L 加工硬化严重，宜用锋利刃口，表面粗糙度 Ra1.6 可行。",
        "公差": "ISO 286 标准公差 IT7 对应基本尺寸 80~120mm 时公差带约 35μm。",
        "表面粗糙度": "机械加工表面粗糙度 Ra 值序列：Ra0.8 < Ra1.6 < Ra3.2 < Ra6.3。",
    }

    def search(self, query: str, num_results: int = 5) -> List[Dict[str, str]]:
        hits = []
        for key, snippet in self._KB.items():
            if key in query or key in snippet:
                hits.append({"title": f"工艺知识: {key}", "url": "mock://kb", "snippet": snippet})
        if not hits:
            hits.append({"title": "通用工艺知识", "url": "mock://kb",
                         "snippet": "未命中特定知识库条目，建议人工核对 GB/ISO 标准。"})
        return hits[:num_results]


class RealSearchProvider(SearchProvider):
    """真实引擎适配器：延迟导入 virtu_omni，避免无网/无包时崩溃。"""

    def __init__(self) -> None:
        try:
            from virtu_omni.internet.search_engine import get_search_engine
            self._engine = get_search_engine()
            self._ok = True
        except Exception as exc:  # pragma: no cover
            self._ok = False
            self._exc = exc

    def search(self, query: str, num_results: int = 5) -> List[Dict[str, str]]:
        if not self._ok:
            raise RuntimeError(f"真实搜索引擎不可用: {getattr(self, '_exc', 'unknown')}")
        resp = self._engine.search(query, num_results=num_results)
        # 透传"是否真在线"：DNS 失败静默退回本地 KB 时 online=False，避免假联网
        self.online: Optional[bool] = getattr(resp, "online", False)
        return [{"title": it.title, "url": it.url, "snippet": it.snippet}
                for it in resp.results]


def get_provider(force_mock: bool = False) -> SearchProvider:
    """真实联网优先；引擎不可用/离线时显式降级为本地知识库（并标注来源，绝不谎称联网）。"""
    if force_mock:
        return MockSearchProvider()
    try:
        provider = RealSearchProvider()
        if getattr(provider, "_ok", False):
            return provider
    except Exception:  # pragma: no cover
        pass
    return MockSearchProvider()


# ---------------------------------------------------------------------------
# 规则化抽取：从 snippet 抽取 Ra 值与公差等级
# ---------------------------------------------------------------------------
_RA_RE = re.compile(r"Ra\s*([0-9.]+)", re.IGNORECASE)
_IT_RE = re.compile(r"IT\s*([0-9]+)", re.IGNORECASE)


@dataclass
class Correction:
    field: str
    current: str
    suggested: str
    evidence: str
    source: str

    def __str__(self) -> str:
        return (f"  - {self.field}: 当前={self.current} -> 建议={self.suggested} "
                f"(依据: {self.evidence[:60]}… [{self.source}])")


@dataclass
class CorrectionReport:
    topic: str
    searched: bool
    provider: str = "unknown"   # RealSearchProvider=真联网；MockSearchProvider=离线知识库
    online: Optional[bool] = None   # 是否真正在线检索（False=仅本地KB兜底，不得谎称联网）
    corrections: List[Correction] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.corrections)


def verify_and_correct(
    design_spec: Dict[str, Any],
    topic: str,
    provider: Optional[SearchProvider] = None,
) -> CorrectionReport:
    """检索 topic 对应的工艺/标准证据，与 design_spec 比对并产出修正建议。"""
    provider = provider or get_provider()
    report = CorrectionReport(topic=topic, searched=False,
                              provider=type(provider).__name__, online=None)

    try:
        hits = provider.search(topic)
        report.searched = True
        report.online = getattr(provider, "online", None)
    except Exception as exc:
        report.notes.append(f"搜索失败，跳过联网修正: {exc}")
        return report

    corpus = " ".join(h.get("snippet", "") for h in hits)

    # 1) 表面粗糙度 Ra 比对：取证据里最优（最小）Ra，若设计值更粗则建议收紧
    ra_vals = [float(v) for v in _RA_RE.findall(corpus)]
    cur_ra = _RA_RE.search(str(design_spec.get("surface_finish", "")))
    if ra_vals and cur_ra:
        best = min(ra_vals)
        cur = float(cur_ra.group(1))
        if cur > best:
            report.corrections.append(Correction(
                "surface_finish", f"Ra{cur}", f"Ra{best}",
                f"检索到推荐表面粗糙度 Ra{best}", hits[0]["url"]))

    # 2) 公差等级 IT 比对：取证据里最高精度（最小 IT 数），若设计更粗则建议收紧
    it_vals = [int(v) for v in _IT_RE.findall(corpus)]
    cur_it = _IT_RE.search(str(design_spec.get("tolerance", "")))
    if it_vals and cur_it:
        best = min(it_vals)
        cur = int(cur_it.group(1))
        if cur > best:
            report.corrections.append(Correction(
                "tolerance", f"IT{cur}", f"IT{best}",
                f"检索到推荐公差等级 IT{best}", hits[0]["url"]))

    if not report.corrections:
        report.notes.append("联网核对：当前设计参数与检索证据一致，无需修正。")
    return report


if __name__ == "__main__":
    # ---- 自测：mock 下验证"搜索命中 -> 发现偏差 -> 产出修正" --------------------
    provider = MockSearchProvider()
    # 设计里表面粗糙度 Ra6.3、公差 IT10，明显比检索建议(Ra1.6/IT7)粗 -> 应被纠正
    spec = {"material": "7075", "surface_finish": "Ra6.3", "tolerance": "IT10"}
    rep = verify_and_correct(spec, "铝合金 7075 五轴铣削 表面粗糙度 公差", provider=provider)

    print("=" * 70)
    print("design_web_self_correction 自测结果")
    print("=" * 70)
    print(f"  检索是否执行: {rep.searched}")
    for c in rep.corrections:
        print(str(c))
    for n in rep.notes:
        print(f"  * {n}")
    ok = rep.searched and rep.has_changes and len(rep.corrections) >= 2
    print("=" * 70)
    print("总结:", "ALL PASS" if ok else "HAS FAILURE")
    raise SystemExit(0 if ok else 1)
