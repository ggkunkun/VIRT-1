# -*- coding: utf-8 -*-
"""virtu_omni/internet/search_engine.py — High-Performance Resilient Web Search Engine.

Provides multi-backend internet search, web page content extraction,
and deep research capabilities with strict safety filtering and offline fallback.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import logging
import os
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

from virtu_omni.internet.safety_filter import HarmfulContentFilter, get_safety_filter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# P1 SSRF guard for fetch_web_content
# ---------------------------------------------------------------------------
class UnsafeFetchURLError(ValueError):
    """Raised when a fetch target is rejected by the SSRF guard."""


_ALLOWED_SCHEMES = frozenset({"http", "https"})
_ALLOWED_PORTS = frozenset({80, 443})
_BLOCKED_HOSTNAMES = frozenset({
    "localhost", "localhost.localdomain", "metadata",
    "metadata.google.internal", "instance-data",
})


def _ip_rejection_reason(ip) -> Optional[str]:
    if ip.is_loopback:
        return "loopback"
    if ip.is_private:
        return "private"
    if ip.is_link_local:
        return "link-local"
    if ip.is_reserved:
        return "reserved"
    if ip.is_multicast:
        return "multicast"
    if ip.is_unspecified:
        return "unspecified"
    return None


def _validate_fetch_url(url: str, resolve=None) -> None:
    """Reject loopback / private / link-local / metadata / non-http(s) / odd-port targets."""
    if not isinstance(url, str) or not url.strip():
        raise UnsafeFetchURLError("url must be a non-empty string")
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError as exc:
        raise UnsafeFetchURLError(f"url could not be parsed: {exc}") from exc
    scheme = (parsed.scheme or "").lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise UnsafeFetchURLError(f"unsupported scheme {scheme!r} (only http/https allowed)")
    host = parsed.hostname
    if not host:
        raise UnsafeFetchURLError("url has no host")
    if parsed.username or parsed.password:
        raise UnsafeFetchURLError("url embeds credentials")
    try:
        port = parsed.port
    except ValueError as exc:
        raise UnsafeFetchURLError(f"invalid port: {exc}") from exc
    if port is None:
        port = 443 if scheme == "https" else 80
    if port not in _ALLOWED_PORTS:
        raise UnsafeFetchURLError(f"non-standard port {port} is not allowed")

    host_l = host.lower().rstrip(".")
    if (host_l in _BLOCKED_HOSTNAMES
            or host_l.endswith(".local")
            or host_l.endswith(".internal")):
        raise UnsafeFetchURLError(f"blocked hostname: {host_l}")

    # 1) IP literal
    try:
        literal_ip = ipaddress.ip_address(host_l)
    except ValueError:
        literal_ip = None
    if literal_ip is not None:
        reason = _ip_rejection_reason(literal_ip)
        if reason:
            raise UnsafeFetchURLError(f"{reason} address is not allowed: {literal_ip}")
        return

    # 2) hostname: resolve and reject if ANY address is internal
    resolver = resolve or socket.getaddrinfo
    try:
        infos = resolver(host_l, port, proto=socket.IPPROTO_TCP)
    except OSError as exc:
        raise UnsafeFetchURLError(f"could not resolve host {host_l!r}: {exc}") from exc
    if not infos:
        raise UnsafeFetchURLError(f"host {host_l!r} resolved to no addresses")
    for info in infos:
        sockaddr = info[4] if len(info) > 4 else None
        addr = sockaddr[0] if sockaddr else ""
        try:
            resolved_ip = ipaddress.ip_address(addr)
        except ValueError as exc:
            raise UnsafeFetchURLError(
                f"host {host_l!r} resolved to a non-IP address {addr!r}") from exc
        reason = _ip_rejection_reason(resolved_ip)
        if reason:
            raise UnsafeFetchURLError(
                f"host {host_l!r} resolves to {reason} address {resolved_ip}")


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Deny automatic redirects (prevents redirect-based SSRF pivot)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(
            req.full_url, code, f"automatic redirect denied: HTTP {code}", headers, fp)


def _open_and_read(url: str, headers: Dict[str, str], timeout: float) -> str:
    """Fetch a URL without following redirects, honoring the caller timeout."""
    opener = urllib.request.build_opener(_NoRedirectHandler())
    req = urllib.request.Request(url, headers=headers)
    with opener.open(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")

from virtu_omni.internet.doh_resolver import (
    DohResolver, _fetch, _is_dns_error, _ONLINE_ENGINES,
)

WORKSPACE_DIR = Path(__file__).resolve().parent.parent.parent
CACHE_FILE = WORKSPACE_DIR / "knowledge_base" / "web_cache.json"
CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class SearchResultItem:
    """Individual search result item."""
    title: str
    url: str
    snippet: str
    source_engine: str
    relevance_score: float = 1.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SearchResponse:
    """Aggregated web search response."""
    query: str
    is_safe: bool
    results: List[SearchResultItem]
    total_found: int
    source_engines_used: List[str]
    filter_verdict: str
    execution_time_ms: float
    online: bool = False   # 是否真正调用了在线引擎（duckduckgo_lite/wikipedia）；False=仅本地KB兜底
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["results"] = [r.to_dict() for r in self.results]
        return d


class WebSearchEngine:
    """Multi-source Web Search Engine with Safety Guardrails and Deep Extraction."""

    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    def __init__(
        self,
        safety_filter: Optional[HarmfulContentFilter] = None,
        timeout: float = 6.0,
        enable_cache: bool = True,
    ):
        self.safety_filter = safety_filter or get_safety_filter()
        self.timeout = timeout
        self.enable_cache = enable_cache
        # DoH 自救解析器：系统 DNS 被阻断时，让在线搜索仍能直连公网
        try:
            self.doh: Optional[DohResolver] = DohResolver()
        except Exception:  # pragma: no cover
            self.doh = None
        self._cache: Dict[str, Any] = self._load_cache()

    def _load_cache(self) -> Dict[str, Any]:
        if self.enable_cache and CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_cache(self) -> None:
        if not self.enable_cache:
            return
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to persist web cache: {e}")

    def search(
        self,
        query: str,
        num_results: int = 5,
        engine_preference: str = "auto",
    ) -> SearchResponse:
        """Execute a safe web search across multiple backends.

        1. Audits query via HarmfulContentFilter. If blocked, aborts immediately.
        2. Checks offline cache if available.
        3. Queries online engines (DuckDuckGo Lite, Wikipedia, or fallback).
        4. Filters snippets and masks any sensitive PII.
        """
        start_t = time.perf_counter()

        # Step 1: Pre-flight safety audit
        audit_res = self.safety_filter.audit_query(query)
        if not audit_res.is_safe:
            elapsed = (time.perf_counter() - start_t) * 1000.0
            return SearchResponse(
                query=query,
                is_safe=False,
                results=[],
                total_found=0,
                source_engines_used=["safety_filter"],
                filter_verdict=audit_res.verdict,
                execution_time_ms=elapsed,
                error_message=f"Query rejected by safety filter: {'; '.join(audit_res.blocked_reasons)}",
            )

        clean_query = audit_res.sanitized_text or query

        # Step 2: Cache lookup
        cache_key = hashlib.sha256(clean_query.strip().lower().encode("utf-8")).hexdigest()
        if self.enable_cache and cache_key in self._cache:
            cached_data = self._cache[cache_key]
            # Ensure fresh enough (24 hours)
            if time.time() - cached_data.get("timestamp", 0) < 86400:
                elapsed = (time.perf_counter() - start_t) * 1000.0
                items = [SearchResultItem(**item) for item in cached_data.get("results", [])]
                return SearchResponse(
                    query=clean_query,
                    is_safe=True,
                    results=items[:num_results],
                    total_found=len(items),
                    source_engines_used=["local_cache"],
                    filter_verdict=audit_res.verdict,
                    execution_time_ms=elapsed,
                )

        # Step 3: Query Backends
        results: List[SearchResultItem] = []
        engines_used: List[str] = []

        # Try DuckDuckGo Lite first
        ddg_results = self._search_duckduckgo_lite(clean_query, max_count=num_results)
        if ddg_results:
            results.extend(ddg_results)
            engines_used.append("duckduckgo_lite")

        # If insufficient or technical query, query Wikipedia
        if len(results) < num_results:
            wiki_results = self._search_wikipedia(clean_query, max_count=num_results - len(results))
            if wiki_results:
                results.extend(wiki_results)
                engines_used.append("wikipedia")

        # Step 4: If all online calls fail (e.g., offline or network partition), fall back to built-in knowledge
        if not results:
            fallback_results = self._fallback_engineering_knowledge(clean_query)
            if fallback_results:
                results.extend(fallback_results)
                engines_used.append("engineering_fallback_kb")

        # Filter snippets and mask PII
        sanitized_results = []
        for r in results[:num_results]:
            content_audit = self.safety_filter.filter_web_content(r.snippet, title=r.title, url=r.url)
            if content_audit.is_safe:
                clean_snippet = content_audit.sanitized_text or r.snippet
                sanitized_results.append(
                    SearchResultItem(
                        title=r.title,
                        url=r.url,
                        snippet=clean_snippet,
                        source_engine=r.source_engine,
                        relevance_score=r.relevance_score,
                    )
                )

        # Cache results
        if sanitized_results and self.enable_cache:
            self._cache[cache_key] = {
                "timestamp": time.time(),
                "query": clean_query,
                "results": [r.to_dict() for r in sanitized_results],
            }
            self._save_cache()

        elapsed = (time.perf_counter() - start_t) * 1000.0
        online = bool(_ONLINE_ENGINES.intersection(engines_used))
        return SearchResponse(
            query=clean_query,
            is_safe=True,
            results=sanitized_results,
            total_found=len(sanitized_results),
            source_engines_used=engines_used,
            filter_verdict=audit_res.verdict,
            execution_time_ms=elapsed,
            online=online,
        )

    def _search_duckduckgo_lite(self, query: str, max_count: int = 5) -> List[SearchResultItem]:
        """Scrape DuckDuckGo Lite search."""
        items: List[SearchResultItem] = []
        try:
            url = "https://lite.duckduckgo.com/lite/"
            data = urllib.parse.urlencode({"q": query}).encode("utf-8")
            raw = _fetch("POST", url, data, self.DEFAULT_HEADERS, self.timeout, self.doh)
            soup = BeautifulSoup(raw, "html.parser")
            links = soup.find_all("a", class_="result-link")
            snippets = soup.find_all("td", class_="result-snippet")
            for i in range(min(len(links), len(snippets), max_count)):
                title = links[i].get_text(strip=True)
                href = links[i].get("href", "")
                snippet = snippets[i].get_text(strip=True)
                if title and snippet:
                    items.append(
                        SearchResultItem(
                            title=title,
                            url=href,
                            snippet=snippet,
                            source_engine="duckduckgo_lite",
                        )
                    )
        except Exception as e:
            logger.debug(f"DuckDuckGo Lite search failed: {e}")
        return items

    def _search_wikipedia(self, query: str, max_count: int = 3) -> List[SearchResultItem]:
        """Query Wikipedia API."""
        items: List[SearchResultItem] = []
        try:
            # Query en or zh wikipedia based on characters
            is_chinese = any("\u4e00" <= char <= "\u9fff" for char in query)
            lang = "zh" if is_chinese else "en"
            api_url = f"https://{lang}.wikipedia.org/w/api.php?action=opensearch&search={urllib.parse.quote(query)}&limit={max_count}&namespace=0&format=json"
            raw = _fetch("GET", api_url, None, self.DEFAULT_HEADERS, self.timeout, self.doh)
            data = json.loads(raw.decode("utf-8"))
            if len(data) >= 4:
                titles = data[1]
                descriptions = data[2]
                urls = data[3]
                for i in range(min(len(titles), len(urls))):
                    t = titles[i]
                    u = urls[i]
                    d = descriptions[i] if i < len(descriptions) and descriptions[i] else f"Wikipedia article on {t}"
                    items.append(
                        SearchResultItem(
                            title=f"{t} - Wikipedia",
                            url=u,
                            snippet=d,
                            source_engine="wikipedia",
                        )
                    )
        except Exception as e:
            logger.debug(f"Wikipedia search failed: {e}")
        return items

    def _fallback_engineering_knowledge(self, query: str) -> List[SearchResultItem]:
        """Local domain knowledge fallback for CAD/CAM/CAE terms when offline."""
        lower_q = query.lower()
        items: List[SearchResultItem] = []

        kb_entries = [
            (
                "ISO 286 / GB/T 1800.1 公差等级与配合标准",
                "https://openstd.samr.gov.cn/gb/iso286",
                "ISO 286 标准公差等级共有 20 个（IT01, IT0, IT1~IT18）。标准基孔制以 H 为基准，基轴制以 h 为基准。例如 H7/g6 属于常用精密间隙配合。",
            ),
            (
                "GB/T 8129 工业自动化术语与 CNC 加工规范",
                "https://openstd.samr.gov.cn/gb/8129",
                "CNC = 计算机数字控制，CAM = 计算机辅助制造，CAD = 计算机辅助设计。MRR = 材料去除率。端面外圆倒角建议单次成形走刀：G0 定位 -> G1 切入 -> G1 倒角 -> M30。",
            ),
            (
                "Lamé 厚壁圆筒弹性力学理论与有限元应力验算",
                "https://engineering.mechanics/lame-theory",
                "对于受内压 P 的厚壁圆筒，内半径 a，外半径 b，径向应力与周向环向应力符合 Lamé 解。根据 von Mises 屈服准则计算等效应力并保证安全系数 FOS >= 1.5。",
            ),
            (
                "FANUC 0i-TF / Macro B 宏程序变量与编程手册",
                "https://fanuc.cnc/macro-b-manual",
                "局部变量 #1~#33，公共变量 #100~#199 与 #500~#999。条件分支使用 IF [条件] GOTO n 或 WHILE [条件] DO m ... END m。",
            ),
        ]

        for title, url, snippet in kb_entries:
            if any(term in title.lower() or term in snippet.lower() for term in lower_q.split()):
                items.append(
                    SearchResultItem(
                        title=title,
                        url=url,
                        snippet=snippet,
                        source_engine="engineering_fallback_kb",
                    )
                )

        if not items:
            items.append(
                SearchResultItem(
                    title=f"工业与制造工程综合知识库: {query}",
                    url="local://virtu/engineering_kb",
                    snippet=f"关于 '{query}' 的工业制造标准规范，系统遵循 GB/ISO 国标及力学安全守则（FOS >= 1.5，体积守恒 Delta V != 0）。",
                    source_engine="engineering_fallback_kb",
                )
            )

        return items

    def fetch_web_content(self, url: str, max_chars: int = 4000) -> Dict[str, Any]:
        """Fetch and extract clean text from a web page with safety filtering."""
        try:
            _validate_fetch_url(url)
        except UnsafeFetchURLError as exc:
            return {
                "success": False,
                "url": url,
                "title": "",
                "text": "",
                "error": f"URL rejected by SSRF guard: {exc}",
            }

        try:
            raw_html = _open_and_read(url, self.DEFAULT_HEADERS, self.timeout)

            soup = BeautifulSoup(raw_html, "html.parser")

            # Remove navigation, headers, scripts, styles
            for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
                tag.decompose()

            title = soup.title.string.strip() if soup.title and soup.title.string else "Untitled Page"

            # Prefer article, main, or paragraph tags
            body_text = ""
            main_elem = soup.find("article") or soup.find("main") or soup.find("div", class_=re.compile(r"content|article|body"))
            if main_elem:
                body_text = main_elem.get_text(separator="\n", strip=True)
            else:
                paragraphs = [p.get_text(strip=True) for p in soup.find_all("p")]
                body_text = "\n\n".join(p for p in paragraphs if len(p) > 20)

            if not body_text:
                body_text = soup.get_text(separator="\n", strip=True)

            # Limit text length
            truncated_text = body_text[:max_chars]

            # Audit extracted web content
            audit_res = self.safety_filter.filter_web_content(truncated_text, title=title, url=url)
            if not audit_res.is_safe:
                return {
                    "success": False,
                    "url": url,
                    "title": title,
                    "text": "",
                    "error": f"Content blocked by safety filter: {'; '.join(audit_res.blocked_reasons)}",
                }

            clean_text = audit_res.sanitized_text or truncated_text

            return {
                "success": True,
                "url": url,
                "title": title,
                "text": clean_text,
                "length": len(clean_text),
                "pii_redacted": audit_res.pii_redacted_count,
            }
        except Exception as e:
            logger.warning(f"Failed to fetch web content from {url}: {e}")
            return {
                "success": False,
                "url": url,
                "title": "",
                "text": "",
                "error": str(e),
            }

    def deep_research(self, topic: str, max_rounds: int = 2) -> Dict[str, Any]:
        """Perform recursive deep research on a topic, extracting and synthesizing facts."""
        start_t = time.perf_counter()

        # Step 1: Initial search
        search_res = self.search(topic, num_results=4)
        if not search_res.is_safe:
            return {
                "topic": topic,
                "is_safe": False,
                "error": search_res.error_message,
                "dossier": "",
            }

        gathered_materials: List[Dict[str, Any]] = []
        for item in search_res.results[:3]:
            gathered_materials.append({
                "title": item.title,
                "url": item.url,
                "snippet": item.snippet,
            })
            # If item has a valid external URL, attempt deeper extraction
            if item.url.startswith("http") and not "samr.gov.cn" in item.url:
                content_res = self.fetch_web_content(item.url, max_chars=1500)
                if content_res["success"] and content_res["text"]:
                    gathered_materials.append({
                        "title": f"{item.title} (Full Excerpt)",
                        "url": item.url,
                        "snippet": content_res["text"][:800],
                    })

        # Synthesize research dossier
        dossier_lines = [
            f"# 深度联网研究报告: {topic}",
            f"- 检索时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"- 检索引擎: {', '.join(search_res.source_engines_used)}",
            f"- 安全审计状态: 合规 ({search_res.filter_verdict})",
            "",
            "## 核心技术证据与资料摘要",
        ]
        for idx, mat in enumerate(gathered_materials, 1):
            dossier_lines.append(f"### 来源 {idx}: {mat['title']}")
            dossier_lines.append(f"**URL**: {mat['url']}")
            dossier_lines.append(f"> {mat['snippet']}")
            dossier_lines.append("")

        elapsed = (time.perf_counter() - start_t) * 1000.0
        return {
            "topic": topic,
            "is_safe": True,
            "sources_count": len(gathered_materials),
            "execution_time_ms": elapsed,
            "dossier": "\n".join(dossier_lines),
            "materials": gathered_materials,
        }


# Global singleton
_GLOBAL_SEARCH_ENGINE: Optional[WebSearchEngine] = None


def get_search_engine() -> WebSearchEngine:
    global _GLOBAL_SEARCH_ENGINE
    if _GLOBAL_SEARCH_ENGINE is None:
        _GLOBAL_SEARCH_ENGINE = WebSearchEngine()
    return _GLOBAL_SEARCH_ENGINE
