# Virtu 工程能力训练镜像（可复现锁定版本）
# 构建：docker build -t virtu-ect:1.0.0 -f engineering_capability_train/Dockerfile .
# 运行：docker run --gpus all -e VIRTU_BASE=/models/Qwen3-8B \
#        -v /path/to/models:/models:ro -v /path/to/workspace:/workspace virtu-ect:1.0.0
#
# 说明：工作区原先没有 Dockerfile，这里补齐；镜像只负责「训练」，
#       LoRA 合并 / GGUF / Ollama 注册 / 真实 GUI 评测一律在本机做。
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TOKENIZERS_PARALLELISM=false \
    PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
    VIRTU_REPO_ROOT=/workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.11 python3.11-venv python3-pip git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && python3.11 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /workspace
COPY engineering_capability_train/requirements-cloud.txt /tmp/requirements-cloud.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements-cloud.txt

# 源码与语料通过卷挂载，不烤进镜像，保证每次训练用的都是 manifest 校验过的那一版
COPY engineering_capability_train /workspace/engineering_capability_train
COPY engineering_capability_train/cloud/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
