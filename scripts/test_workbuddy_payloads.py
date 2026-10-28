import json
import urllib.request

def test_endpoint(url, payload, desc):
    print(f"\n--- Testing: {desc} ({url}) ---")
    data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data_bytes, headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            if payload.get("stream"):
                print(f"  [OK] Streaming response received (len: {len(body)})")
            else:
                data = json.loads(body)
                content = data["choices"][0]["message"]["content"]
                print(f"  [OK] Received response ({len(content)} chars):\n  Preview: {content[:150]}...")
    except Exception as e:
        print(f"  [FAILED] Error: {e}")

# 1. Block list format (WorkBuddy format)
test_endpoint(
    "http://127.0.0.1:8000/v1/chat/completions",
    {
        "model": "virtu-cad-cam-10b",
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": "你好"}]}
        ],
        "stream": False
    },
    "WorkBuddy Block-List Format (你好)"
)

# 2. Block list format with CAD inquiry
test_endpoint(
    "http://127.0.0.1:8000/v1/chat/completions",
    {
        "model": "virtu-cad-cam-10b",
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": "我想制造一款精密轮模外径53mm内孔14mm"}]}
        ],
        "stream": False
    },
    "WorkBuddy CAD Manufacturing Wish"
)

# 3. Streaming with block list
test_endpoint(
    "http://127.0.0.1:8000/v1/chat/completions",
    {
        "model": "virtu-cad-cam-10b",
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": "你好"}]}
        ],
        "stream": True
    },
    "WorkBuddy Streaming Block-List"
)

# 4. Path variation /chat/completions
test_endpoint(
    "http://127.0.0.1:8000/chat/completions",
    {
        "model": "virtu-cad-cam-10b",
        "messages": [
            {"role": "user", "content": "测试"}
        ],
        "stream": False
    },
    "Non-v1 Path /chat/completions"
)
