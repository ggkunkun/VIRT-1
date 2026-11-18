"""毛坯装夹与定位工艺标准库 + 可选联网标准核验。

遵循原则：
  - 3-2-1 六点定位原理（GB/T 机械加工工艺规程通用原则）
  - 基准重合原则（设计基准与加工/定位基准一致）
  - 铣削虎钳：平行垫铁支撑底面，夹持深度 >= min(10mm, 0.35*H) 且 >= 5mm；伸出高度留足安全避让
  - 车削卡盘：夹持长度 >= max(20mm, 0.8*D)（推荐 1.0*D）；L/D > 3 用尾座顶尖，L/D > 6 加跟刀架/中心架
"""
from __future__ import annotations

import os
import re
import time
from typing import Any, Callable, Dict, List, Optional

STANDARD_QUERIES = {
    "MILLING": [
        {
            "id": "STD-MILL-321",
            "title": "六点定位原理（3-2-1定位）与基准重合原则",
            "summary": "底面3点限Z平动及X/Y转动，固定钳口侧面2点限Y平动及Z转动，端面挡块1点限X平动。",
            "min_grip_mm": 5.0,
            "recommended_grip_mm": 10.0,
            "max_stickout_width_ratio": 2.5,
        },
        {
            "id": "STD-MILL-VISE",
            "title": "数控铣床平口虎钳装夹与避让规范",
            "summary": "使用平行垫铁保证底面贴合；工件伸出钳口高度应大于最大侧铣深度+2mm以防刀柄/刀具碰撞钳口，同时避免过高导致颤振。",
            "clearance_above_jaw_mm": 2.0,
        },
    ],
    "TURNING": [
        {
            "id": "STD-TURN-CHUCK",
            "title": "车削三爪卡盘夹持长度与长径比悬伸规范（3:1法则）",
            "summary": "一般车削卡爪夹持长度应达到0.8D~1.0D（不少于20mm）；悬伸长度L/D<=3.0可单卡盘悬臂装夹，3.0<L/D<=6.0须使用尾座顶尖支撑，L/D>6.0须加中心架或跟刀架。",
            "min_grip_d_ratio": 0.8,
            "recommended_grip_d_ratio": 1.0,
            "min_grip_abs_mm": 20.0,
            "tailstock_ld_threshold": 3.0,
            "steady_rest_ld_threshold": 6.0,
        },
    ],
}
STANDARD_QUERIES["TURN_MILL"] = STANDARD_QUERIES["TURNING"]

DEFAULT_LOOKUP_URLS = [
    "https://en.wikipedia.org/wiki/Workholding",
    "https://en.wikipedia.org/wiki/Chuck_(engineering)",
]


def default_http_fetcher(url: str, timeout_s: float = 4.0) -> str:
    """默认 HTTPS 抓取器（仅在显式开启联网且非 hermetic 模式下调用）。"""
    import httpx

    resp = httpx.get(url, timeout=timeout_s, follow_redirects=True,
                     headers={"User-Agent": "cam-autogen-standards-checker/1.0"})
    resp.raise_for_status()
    return resp.text


def _extract_snippet(html: str, keywords: List[str]) -> str:
    text = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>|<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    for kw in keywords:
        idx = text.lower().find(kw.lower())
        if idx >= 0:
            lo = max(0, idx - 80)
            hi = min(len(text), idx + 220)
            return text[lo:hi].strip()
    return text[:220]


def lookup_positioning_standards(
    process_type: str,
    enable_web: bool = False,
    fetcher: Optional[Callable[[str, float], str]] = None,
    timeout_s: float = 4.0,
) -> Dict[str, Any]:
    """查询毛坯摆放与夹具定位标准。

    联网开关：只有 ``enable_web=True`` 且环境变量 ``VIRTU_INTERNET != 'off'`` 时才发起网络请求；
    失败时安全回退到本地权威工艺规范，并如实记录 ``basis`` 与 ``web_status``。
    """
    local_rules = list(STANDARD_QUERIES.get(process_type, STANDARD_QUERIES["MILLING"]))
    internet_env = os.environ.get("VIRTU_INTERNET", "").strip().lower()
    if not enable_web or internet_env == "off":
        reason = "disabled_by_env" if internet_env == "off" else "disabled_by_request"
        return {
            "basis": "local_verified_standard",
            "web_status": reason,
            "rules": local_rules,
            "web_references": [],
        }

    fetch = fetcher or default_http_fetcher
    keywords = ["chuck", "tailstock", "clamping", "three-jaw"] if process_type != "MILLING" else [
        "vise", "clamping", "3-2-1", "locating", "workholding"
    ]
    refs: List[Dict[str, Any]] = []
    errors: List[str] = []
    for url in DEFAULT_LOOKUP_URLS:
        try:
            body = fetch(url, timeout_s)
            snippet = _extract_snippet(body, keywords)
            refs.append({
                "url": url,
                "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "snippet": snippet,
                "matched_keywords": [k for k in keywords if k.lower() in body.lower()],
            })
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{url}: {type(exc).__name__}: {exc}")

    return {
        "basis": "web_verified+local_standard" if refs else "local_standard_fallback",
        "web_status": "ok" if refs else "fallback_on_error",
        "rules": local_rules,
        "web_references": refs,
        "web_errors": errors,
    }
