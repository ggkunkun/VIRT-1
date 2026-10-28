import json
import urllib.request

url = "http://127.0.0.1:8000/v1/chat/completions"
payload = {
    "model": "virtu-cad-cam-10b",
    "messages": [
        {"role": "user", "content": "请介绍你支持的六大工业软件体系与功能插件"}
    ],
    "stream": True
}

req = urllib.request.Request(
    url,
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)

chunks_received = 0
total_text = ""

with urllib.request.urlopen(req, timeout=10) as resp:
    for line in resp:
        line_str = line.decode("utf-8").strip()
        if line_str.startswith("data: ") and line_str != "data: [DONE]":
            chunk_data = json.loads(line_str[6:])
            delta = chunk_data["choices"][0]["delta"].get("content", "")
            total_text += delta
            chunks_received += 1

print(f"Streaming test: SUCCESS! Received {chunks_received} SSE chunks.")
print(f"Total Text ({len(total_text)} chars):\n{total_text[:350]}...")
