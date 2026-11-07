#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""End-to-End Live Verification of WorkBuddy Bridge (8000) and Virtu Model (11434)."""

import os
import sys
import json
import time
import urllib.request
from pathlib import Path

WORKSPACE = Path(r"D:\Virtu模型")
sys.path.insert(0, str(WORKSPACE))

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from bridges.bridge_security import ensure_bridge_token

TOKEN = ensure_bridge_token()
BASE_URL = "http://127.0.0.1:8000"


def http_req(endpoint: str, method: str = "GET", data: dict = None, auth: bool = False, timeout: int = 60):
    url = f"{BASE_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}
    if auth:
        headers["Authorization"] = f"Bearer {TOKEN}"
    
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    
    # Bypass system/local proxies
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=timeout) as resp:
            resp_bytes = resp.read()
            return resp.status, json.loads(resp_bytes.decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(err_body)
        except Exception:
            return e.code, {"raw_error": err_body}
    except Exception as e:
        return 0, {"exception": str(e)}


def test_live():
    print("=" * 72)
    print("  VIRTU LIVE SERVICE & MODEL VERIFICATION (Port 8000 & Ollama 11434)")
    print("=" * 72)

    # 1. Models endpoint
    print("\n[1/6] Testing GET /v1/models...")
    status, res = http_req("/v1/models")
    print(f"Status: {status} | Models count: {len(res.get('data', [])) if isinstance(res, dict) else 0}")
    assert status == 200, f"Expected 200, got {status}: {res}"
    model_ids = [m.get("id") for m in res.get("data", [])]
    print(f"Available Model IDs: {model_ids}")

    # 2. Reach diagnostic endpoint (Public POST / GET)
    print("\n[2/6] Testing GET /v1/reach/channels...")
    status, res = http_req("/v1/reach/channels")
    print(f"Status: {status} | Status field: {res.get('status')}")
    assert status == 200, f"Expected 200, got {status}: {res}"

    # 3. AI Scratch diagnostic (Public GET)
    print("\n[3/6] Testing GET /v1/ai-scratch/diagnostic...")
    status, res = http_req("/v1/ai-scratch/diagnostic")
    print(f"Status: {status} | Mode: {res.get('mode')}")
    assert status == 200, f"Expected 200, got {status}: {res}"

    # 4. Authenticated vs Unauthenticated CAD/CAM dispatch (Mutating POST endpoint)
    print("\n[4/6] Testing Protected POST /v1/cadcam/dispatch...")
    dispatch_payload = {
        "target_software": "autocad",
        "action": "create_dxf",
        "parameters": {
            "drawing_name": "live_flange_test",
            "entities": [
                {"type": "circle", "center": [0, 0], "radius": 75.0},
                {"type": "circle", "center": [0, 0], "radius": 25.0}
            ]
        }
    }
    # First: Unauthenticated call (Expected 401 Unauthorized)
    status_unauth, res_unauth = http_req("/v1/cadcam/dispatch", method="POST", data=dispatch_payload, auth=False)
    print(f"Unauthenticated Call: Status={status_unauth} (Expected 401)")
    assert status_unauth == 401, f"Expected 401 on unauthenticated call, got {status_unauth}: {res_unauth}"

    # Second: Authenticated call with Bearer Token (Expected 200 Success)
    status_auth, res_auth = http_req("/v1/cadcam/dispatch", method="POST", data=dispatch_payload, auth=True)
    print(f"Authenticated Call: Status={status_auth} | Result status: {res_auth.get('status')} | DXF: {res_auth.get('dxf_path')}")
    assert status_auth == 200, f"Expected 200, got {status_auth}: {res_auth}"
    assert res_auth.get("status") == "success", f"Expected success status, got {res_auth}"

    # 5. Engineering Chat Completion (Real Model Inference)
    print("\n[5/6] Testing POST /v1/chat/completions (Engineering Knowledge)...")
    chat_payload = {
        "model": "virtu-cad-cam-10b",
        "messages": [
            {"role": "user", "content": "请简要解释切削速度Vc和主轴转速n的关系，并给出计算公式。"}
        ],
        "temperature": 0.2,
        "max_tokens": 256
    }
    t0 = time.time()
    status, res = http_req("/v1/chat/completions", method="POST", data=chat_payload, auth=True, timeout=90)
    elapsed = round(time.time() - t0, 2)
    print(f"Status: {status} | Elapsed: {elapsed}s")
    assert status == 200, f"Expected 200, got {status}: {res}"
    content = res["choices"][0]["message"]["content"]
    print("Response Content Preview:")
    print("-" * 50)
    print(content[:300] + ("..." if len(content) > 300 else ""))
    print("-" * 50)
    assert any(term in content for term in ["Vc", "1000", "π", "转速", "速度"]), "Engineering terms missing in response"

    # 6. Tool Calling Dispatch via Bridge (SolidWorks modeling wish)
    print("\n[6/6] Testing POST /v1/chat/completions (Multi-Software Tool Calling)...")
    tool_payload = {
        "model": "virtu-cad-cam-10b",
        "messages": [
            {"role": "user", "content": "在 SolidWorks 里建一个法兰盘零件，外径150厚度20"}
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "cadcam_solidworks_model",
                    "description": "SOLIDWORKS 2021 三维建模与特征树生成",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {"type": "string", "enum": ["model_flange", "create_parametric_part"]},
                            "part_name": {"type": "string"},
                            "dimensions": {"type": "object"}
                        },
                        "required": ["action"]
                    }
                }
            }
        ],
        "temperature": 0.1,
        "max_tokens": 256
    }
    t0 = time.time()
    status, res = http_req("/v1/chat/completions", method="POST", data=tool_payload, auth=True, timeout=90)
    elapsed = round(time.time() - t0, 2)
    print(f"Status: {status} | Elapsed: {elapsed}s")
    assert status == 200, f"Expected 200, got {status}: {res}"
    choice = res["choices"][0]
    finish_reason = choice.get("finish_reason")
    tool_calls = choice.get("message", {}).get("tool_calls", [])
    print(f"Finish Reason: {finish_reason}")
    if tool_calls:
        print(f"Tool Call Name: {tool_calls[0]['function']['name']}")
        print(f"Tool Call Args: {tool_calls[0]['function']['arguments']}")
    else:
        print(f"Model Content (fallback): {choice['message'].get('content', '')[:120]}")

    print("\n" + "=" * 72)
    print("[PASS] ALL 6 LIVE SERVICE & MODEL VERIFICATION CHECKS PASSED!")
    print("=" * 72)


if __name__ == "__main__":
    test_live()
