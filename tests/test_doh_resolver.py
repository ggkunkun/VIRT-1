# -*- coding: utf-8 -*-
"""DoH 自救解析器 + 真联网 online 标志 单元测试。

目标：在受限/沙箱环境也能验证
  1. _is_dns_error 能正确识别 DNS 失败（而非其他网络错误）
  2. DohResolver.resolve 经 DoH 把域名解析成 IP
  3. _fetch 在系统 DNS 失败时自动走 DoH 直连并返回目标 body
  4. WebSearchEngine.search 的 online 标志：真在线=True，仅本地KB兜底=False
     （修复"假联网"：之前只要不抛异常就 online=True）
  5. design_web_self_correction 的 CorrectionReport.online 透传真实在线状态

沙箱缺 bs4 / safety_filter 时自动注入 dummy 并 retry，使 search_engine 可导入。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import types
from unittest import mock
import urllib.error
import socket


def _load_search_engine():
    """在缺 bs4 / safety_filter 时注入 dummy 并重试，确保 search_engine 可导入。"""
    for _ in range(4):
        try:
            from virtu_omni.internet.search_engine import WebSearchEngine
            return WebSearchEngine
        except ImportError as e:
            msg = str(e).lower()
            if "bs4" in msg and "bs4" not in sys.modules:
                bs4 = types.ModuleType("bs4")

                class _FakeTag:
                    def __init__(self, text, href=""):
                        self._t = text
                        self._h = href

                    def get_text(self, strip=False):
                        return self._t

                    def get(self, k, d=None):
                        return self._h if k == "href" else d

                class _DummyBS:
                    def __init__(self, html, parser):
                        pass

                    def find_all(self, tag, class_=None):
                        # 让 duckduckgo 解析"产出"一个含 Ra/IT 证据的结果
                        return [_FakeTag("铝合金 7075 推荐表面粗糙度 Ra0.8 公差 IT7"),
                                _FakeTag("snippet", "https://example.com/x")]

                bs4.BeautifulSoup = _DummyBS
                sys.modules["bs4"] = bs4
            elif "safety_filter" in msg and \
                    "virtu_omni.internet.safety_filter" not in sys.modules:
                sf = types.ModuleType("virtu_omni.internet.safety_filter")

                class _Audit:
                    is_safe = True
                    verdict = "ok"
                    sanitized_text = None
                    blocked_reasons = []

                class _Filter:
                    def audit_query(self, q):
                        return _Audit()

                    def filter_web_content(self, *a, **k):
                        return _Audit()

                sf.HarmfulContentFilter = _Filter
                sf.get_safety_filter = lambda: _Filter()
                sys.modules["virtu_omni.internet.safety_filter"] = sf
            else:
                raise
    raise RuntimeError("无法导入 search_engine")


WebSearchEngine = _load_search_engine()
from virtu_omni.internet.doh_resolver import (  # noqa: E402
    DohResolver, _fetch, _is_dns_error, _ONLINE_ENGINES,
)
from design_web_self_correction import verify_and_correct, SearchProvider  # noqa: E402


# ---------------------------------------------------------------------------
# 网络 mock：FakeConn 根据请求 path 区分 DoH 解析 vs 目标抓取
# ---------------------------------------------------------------------------
class FakeResp:
    def __init__(self, body, status=200):
        self._b = body
        self.status = status

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


DDG_HTML = b'<a class="result-link">result title</a>' \
          b'<td class="result-snippet">snippet body</td>'


class FakeConn:
    """DoH 解析成功 + 目标抓取成功的 mock。"""

    def __init__(self, host, port, context=None, timeout=None):
        self.host = host

    def request(self, method, path, body=None, headers=None):
        self.path = path

    def getresponse(self):
        if "dns-query" in self.path:
            return FakeResp(b'{"Status":0,"Answer":[{"type":1,"data":"203.0.113.7"}]}')
        if self.path.startswith("/lite"):
            return FakeResp(DDG_HTML)
        return FakeResp(b'[]')  # wikipedia 兜底（空）

    def close(self):
        pass


class FakeConnNoDoh(FakeConn):
    """DoH 解析失败（无 Answer） -> 触发本地 KB 兜底。"""

    def getresponse(self):
        if "dns-query" in self.path:
            return FakeResp(b'{"Status":3}')  # NXDOMAIN / 无答案
        return FakeResp(b'[]')


# ---------------------------------------------------------------------------
# 测试用例
# ---------------------------------------------------------------------------
def test_is_dns_error():
    assert _is_dns_error(socket.gaierror("nodename nor servname"))
    assert _is_dns_error(urllib.error.URLError("[Errno 11001] getaddrinfo failed"))
    assert not _is_dns_error(urllib.error.URLError("403 Forbidden"))
    assert not _is_dns_error(ValueError("not a network error"))


def test_doh_resolver_resolve():
    with mock.patch("virtu_omni.internet.doh_resolver.http.client.HTTPSConnection", FakeConn):
        ip = DohResolver().resolve("duckduckgo.com")
    assert ip == "203.0.113.7", ip


def test_fetch_falls_back_to_doh():
    urlopen = mock.patch(
        "virtu_omni.internet.doh_resolver.urllib.request.urlopen",
        side_effect=urllib.error.URLError("getaddrinfo failed"))
    conn = mock.patch(
        "virtu_omni.internet.doh_resolver.http.client.HTTPSConnection", FakeConn)
    with urlopen, conn:
        body = _fetch("GET", "https://lite.duckduckgo.com/lite/", None, {}, 6.0, DohResolver())
    assert DDG_HTML in body, "系统 DNS 失败时应经 DoH 直连拿回目标 body"


def test_search_online_true():
    urlopen = mock.patch(
        "virtu_omni.internet.search_engine.urllib.request.urlopen",
        side_effect=urllib.error.URLError("getaddrinfo failed"))
    conn = mock.patch(
        "virtu_omni.internet.doh_resolver.http.client.HTTPSConnection", FakeConn)
    with urlopen, conn:
        eng = WebSearchEngine(enable_cache=False)
        resp = eng.search("铝合金 7075 表面粗糙度 公差", num_results=3)
    assert resp.online is True, resp.source_engines_used
    assert resp.results, "应有在线检索结果"


def test_search_online_false_when_doh_also_fails():
    urlopen = mock.patch(
        "virtu_omni.internet.search_engine.urllib.request.urlopen",
        side_effect=urllib.error.URLError("getaddrinfo failed"))
    conn = mock.patch(
        "virtu_omni.internet.doh_resolver.http.client.HTTPSConnection", FakeConnNoDoh)
    with urlopen, conn:
        eng = WebSearchEngine(enable_cache=False)
        resp = eng.search("铝合金 7075 表面粗糙度 公差")
    # 在线全失败 -> 仅本地 KB 兜底，online 必须为 False（不得谎称联网）
    assert resp.online is False, resp.source_engines_used
    assert resp.results, "本地 KB 兜底应非空"


def test_online_passthrough_to_report():
    class FakeProvider(SearchProvider):
        online = True

        def search(self, q, n=5):
            return [{"title": "t", "url": "u",
                     "snippet": "铝合金 7075 推荐 Ra0.8 公差 IT7"}]

    rep = verify_and_correct(
        {"surface_finish": "Ra6.3", "tolerance": "IT10"},
        "铝合金 7075 表面粗糙度 公差", provider=FakeProvider())
    assert rep.online is True
    assert rep.has_changes, "应据在线证据产生修正"

    FakeProvider.online = False
    rep2 = verify_and_correct(
        {"surface_finish": "Ra6.3", "tolerance": "IT10"},
        "铝合金 7075 表面粗糙度 公差", provider=FakeProvider())
    assert rep2.online is False


def test_online_flag_logic():
    assert bool(_ONLINE_ENGINES.intersection({"duckduckgo_lite"})) is True
    assert bool(_ONLINE_ENGINES.intersection({"engineering_fallback_kb"})) is False


if __name__ == "__main__":
    cases = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in cases:
        try:
            fn()
            print(f"  [PASS] {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {fn.__name__}: {e}")
        except Exception as e:  # noqa
            print(f"  [ERROR] {fn.__name__}: {type(e).__name__} {e}")
    print("=" * 60)
    print(f"总结: {passed}/{len(cases)} PASS")
    raise SystemExit(0 if passed == len(cases) else 1)
