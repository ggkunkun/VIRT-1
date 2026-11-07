import os
import sys
import glob
import json
import math
import argparse
import requests
import numpy as np

OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
if not OLLAMA_URL.startswith("http"):
    OLLAMA_URL = "http://" + OLLAMA_URL

EMBED_MODEL = "nomic-embed-text:latest"
DEFAULT_LLM = "virtu-longctx:latest"

def get_embedding(text):
    url = f"{OLLAMA_URL}/api/embeddings"
    res = requests.post(url, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    res.raise_for_status()
    return res.json()["embedding"]

def chunk_text(text, chunk_size=800, overlap=100):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks

class LocalRAGIndex:
    def __init__(self, index_path="D:\\Virtu模型\\.rag_index.json"):
        self.index_path = index_path
        self.data = []  # list of {"doc": path, "chunk": str, "vector": list}

    def load(self):
        if os.path.exists(self.index_path):
            with open(self.index_path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
            print(f"[RAG] 已加载现有索引，包含 {len(self.data)} 个文本块。")

    def save(self):
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False)
        print(f"[RAG] 索引已保存至 {self.index_path}")

    def index_files(self, paths):
        count = 0
        for p in paths:
            if not os.path.exists(p) or os.path.isdir(p):
                continue
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                chunks = chunk_text(content)
                print(f"[RAG] 正在索引文件: {os.path.basename(p)} ({len(chunks)} 块)...")
                for c in chunks:
                    vec = get_embedding(c)
                    self.data.append({"doc": os.path.basename(p), "chunk": c, "vector": vec})
                    count += 1
            except Exception as e:
                print(f"[RAG] 读取文件失败 {p}: {e}")
        self.save()
        print(f"[RAG] 索引完成！新增 {count} 个检索块。")

    def search(self, query, top_k=4):
        if not self.data:
            return []
        query_vec = np.array(get_embedding(query), dtype=np.float32)
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return []

        scored = []
        for item in self.data:
            doc_vec = np.array(item["vector"], dtype=np.float32)
            doc_norm = np.linalg.norm(doc_vec)
            if doc_norm == 0:
                score = 0.0
            else:
                score = float(np.dot(query_vec, doc_vec) / (query_norm * doc_norm))
            scored.append((score, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:top_k]

    def ask(self, query, llm_model=DEFAULT_LLM, top_k=4):
        results = self.search(query, top_k=top_k)
        if not results:
            return "未找到相关文档内容，请先建立索引。"

        context_blocks = []
        for i, (score, item) in enumerate(results):
            context_blocks.append(f"【参考片段 {i+1} - 来自《{item['doc']}》(相关度: {score:.3f})】:\n{item['chunk']}")

        context_str = "\n\n".join(context_blocks)
        prompt = f"""请根据以下检索到的背景资料，准确严谨地回答问题。如果背景资料中未提及相关细节，请明确说明，严禁编造。

【背景参考资料】
{context_str}

【用户问题】
{query}

【回答】"""

        print(f"[RAG] 匹配到 {len(results)} 个高相关片段，正在调用 {llm_model} 生成回答...")
        res = requests.post(f"{OLLAMA_URL}/api/generate", json={
            "model": llm_model,
            "prompt": prompt,
            "stream": False
        }, timeout=120).json()

        return res.get("response", "").strip()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="本地海量文档极速 RAG 检索管线")
    parser.add_argument("--index", nargs="+", help="待索引的文件或通配符，如 data/*.md")
    parser.add_argument("--ask", type=str, help="基于知识库的提问")
    parser.add_argument("--model", type=str, default=DEFAULT_LLM, help="用于总结回答的模型")
    args = parser.parse_args()

    rag = LocalRAGIndex()
    rag.load()

    if args.index:
        all_files = []
        for pattern in args.index:
            all_files.extend(glob.glob(pattern))
        rag.index_files(all_files)

    if args.ask:
        ans = rag.ask(args.ask, llm_model=args.model)
        print("\n================ AI 回答 ================\n")
        print(ans)
