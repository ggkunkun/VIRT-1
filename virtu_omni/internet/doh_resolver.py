# -*- coding: utf-8 -*-
"""DNS-over-HTTPS 自救解析器（独立零依赖模块）。

系统 DNS 被阻断/污染时，用可信 DoH（默认阿里公共 DoH 223.5.5.5 / 223.6.6.6）
把域名解析成 IP，再直连 IP（带 Host 头）访问公网，使联网搜索在受限网络下可用。

仅依赖标准库：http.client / ssl / socket / urllib。
这样 DoH 自救逻辑可以脱离 bs4 / safety_filter 等重依赖被独立单元测试。
"""

from __future__ import annotations

import http.client
import json
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, Optional, Tuple

_DOH_SERVERS = ("223.5.5.5", "223.6.6.6")   # 阿里公共 DoH（RFC8484 JSON）
_ONLINE_ENGINES = frozenset({"duckduckgo_lite", "wikipedia"})


class DohResolver:
    """用 DoH 把域名解析成 IP，绕开被阻断的系统 DNS。

    仅在 urllib 系统解析失败（_is_dns_error）时被调用，作为自救路径；
    正常 DNS 可用时不会走这里，避免无谓 overhead。
    """

    def __init__(self, doh_ips: Tuple[str, ...] = _DOH_SERVERS, timeout: float = 6.0):
        self.doh_ips = list(doh_ips)
        self.timeout = timeout
        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE

    def resolve(self, hostname: str) -> Optional[str]:
        if not hostname:
            return None
        for ip in self.doh_ips:
            try:
                conn = http.client.HTTPSConnection(ip, 443, context=self.ctx, timeout=self.timeout)
                conn.request("GET", f"/dns-query?name={hostname}&type=A",
                             headers={"Accept": "application/dns-json", "Host": ip})
                resp = conn.getresponse()
                body = resp.read().decode("utf-8", "replace")
                conn.close()
                data = json.loads(body)
                for ans in data.get("Answer", []):
                    if ans.get("type") == 1 and ans.get("data"):
                        return ans["data"]
            except Exception:
                continue
        return None


def _is_dns_error(exc: Exception) -> bool:
    """判断异常是否由 DNS 解析失败引起（而非其他网络错误）。"""
    if isinstance(exc, socket.gaierror):
        return True
    msg = str(exc).lower()
    return any(k in msg for k in (
        "getaddrinfo", "name or service not known", "nodename nor servname",
        "name resolution", "no address associated", "temporary failure in name",
        "dns", "nxdomain",
    ))


def _fetch(method: str, url: str, data: Optional[bytes], headers: Dict[str, str],
           timeout: float, resolver: Optional[DohResolver]) -> bytes:
    """抓取 URL：优先系统 DNS；DNS 失败时经 DoH 解析并直连 IP（带 Host 头）。"""
    try:
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except (urllib.error.URLError, socket.gaierror, OSError) as exc:
        if resolver is not None and _is_dns_error(exc):
            return _fetch_via_doh(method, url, data, headers, timeout, resolver)
        raise


def _fetch_via_doh(method: str, url: str, data: Optional[bytes], headers: Dict[str, str],
                   timeout: float, resolver: DohResolver) -> bytes:
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname
    ip = resolver.resolve(host)
    if not ip:
        raise RuntimeError(f"DoH 无法解析主机 {host!r}")
    new_headers = dict(headers)
    new_headers["Host"] = host
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    conn = http.client.HTTPSConnection(ip, 443, context=ctx, timeout=timeout)
    conn.request(method, path, body=data, headers=new_headers)
    resp = conn.getresponse()
    body = resp.read()
    status = resp.status
    conn.close()
    if status >= 400:
        raise urllib.error.HTTPError(url, status, "DoH-direct request failed", resp.headers, None)
    return body
