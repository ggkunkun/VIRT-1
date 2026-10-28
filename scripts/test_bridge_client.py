import json
import urllib.request

url = "http://127.0.0.1:8000/v1/chat/completions"
payload = {
    "model": "virtu-cad-cam-10b",
    "messages": [
        {
            "role": "user",
            "content": "许愿制造一款航空高压压气机级12叶片闭式整体叶轮（材质Ti-6Al-4V），外径180mm内孔60mm总长55mm"
        }
    ],
    "stream": False
}

req = urllib.request.Request(
    url,
    data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    headers={"Content-Type": "application/json; charset=utf-8"}
)

with urllib.request.urlopen(req, timeout=10) as resp:
    data = json.loads(resp.read().decode("utf-8"))

print(f"Status: SUCCESS")
print(f"Model ID: {data['model']}")
content = data["choices"][0]["message"]["content"]
print(f"Response Length: {len(content)} chars")
print(f"Content Preview:\n{content[:400]}")
