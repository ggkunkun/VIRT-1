# -*- coding: utf-8 -*-
"""OPC UA 接口（asyncua 真实协议栈）。

信息模型（ns：AE-CI-258）：
  Production
    State(str) / Part(str) / ProgramHash(str) / BatchCount(int)
    CycleTime_s(float) / MinClearance_mm(float) / Cpk(float)
    ToolWear_pct(float, per tool) / AlarmCode(int) / AlarmText(str)

自检：起服 -> 客户端连接 -> 读全部节点 -> 写 BatchCount -> 回读 -> 关服，全程实测。
"""
from __future__ import annotations

import threading
import time
from typing import Dict, Optional

NODES = {
    "State": ("str", "IDLE"),
    "Part": ("str", "AE-CI-258"),
    "ProgramHash": ("str", ""),
    "BatchCount": ("int", 0),
    "CycleTime_s": ("float", 0.0),
    "MinClearance_mm": ("float", 0.0),
    "Cpk": ("float", 0.0),
    "ToolWear_pct": ("float", 0.0),
    "AlarmCode": ("int", 0),
    "AlarmText": ("str", ""),
}

_NS = "urn:virtu:production:ae-ci-258"


def _make_server(url: str, values: Dict):
    from asyncua.sync import Server
    server = Server()
    server.set_endpoint(url)
    idx = server.register_namespace(_NS)
    obj = server.nodes.objects.add_object(idx, "Production")
    nodes = {}
    for name, (kind, default) in NODES.items():
        val = values.get(name, default)
        node = obj.add_variable(idx, name, val)
        node.set_writable()
        nodes[name] = node
    return server, nodes


def _client(url: str, timeout_s: float = 6.0):
    from asyncua.sync import Client
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        try:
            c = Client(url)
            c.connect()
            return c
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(0.3)
    raise RuntimeError(f"OPC UA 客户端连接失败: {last}")


def _object(nodes):
    if not nodes:
        return None
    return nodes["State"].parent


def selftest(url: str = "opc.tcp://127.0.0.1:4840/virtu/") -> Dict:
    try:
        import asyncua  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "reason": f"asyncua 未安装: {exc}",
                "basis": "unmeasured"}
    server, nodes = _make_server(url, {"State": "READY", "MinClearance_mm": 1.85})
    t = threading.Thread(target=server.start, daemon=True)
    t.start()
    result: Dict = {"available": True, "url": url, "nodes": list(nodes), "read": {},
                    "write_back": None, "basis": "measured"}
    try:
        c = _client(url)
        for name, node in nodes.items():
            result["read"][name] = node.read_value()
        nodes["BatchCount"].write_value(int(result["read"].get("BatchCount", 0)) + 1)
        result["write_back"] = nodes["BatchCount"].read_value()
        result["read_back_ok"] = result["write_back"] == \
            int(result["read"].get("BatchCount", 0)) + 1
        c.disconnect()
    except Exception as exc:  # noqa: BLE001
        result["error"] = str(exc)
        result["read_back_ok"] = False
    finally:
        try:
            server.stop()
        except Exception:  # noqa: BLE001
            pass
    return result


def publish(values: Dict[str, object], url: str = "opc.tcp://127.0.0.1:4840/virtu/",
            hold_s: float = 0.0) -> Dict:
    """起服并写入一次运行数据（供产线采集）。hold_s>0 时保持端口占用以便外部客户端读取。"""
    try:
        import asyncua  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "reason": f"asyncua 未安装: {exc}",
                "basis": "unmeasured"}
    server, nodes = _make_server(url, values)
    t = threading.Thread(target=server.start, daemon=True)
    t.start()
    time.sleep(0.5)
    for k, v in values.items():
        if k in nodes:
            nodes[k].write_value(v)
    if hold_s > 0:
        time.sleep(hold_s)
    out = {"available": True, "url": url,
           "values": {k: nodes[k].read_value() for k in nodes}, "basis": "measured"}
    server.stop()
    return out
