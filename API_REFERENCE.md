# Virtu-Omni-10B RESTful 接口参考规范文档
**接口版本**: v1.0.0  
**通信协议**: HTTP/1.1, HTTP/2, Server-Sent Events (SSE)  
**默认基准路径**: `http://<HOST>:<PORT>/v1`  
**遵循标准**: OpenAPI 3.1.0 & OpenAI Compatible Spec  

---

## 1. 认证与全局请求头 (Headers)
| 标头名称 (Header) | 类型 | 必填 | 说明 |
| :--- | :--- | :---: | :--- |
| `Authorization` | String | 是 | Bearer Token，格式：`Bearer sk-virtu-xxxxxx` |
| `Content-Type` | String | 是 | `application/json` |
| `X-Request-ID` | String | 否 | 链路追踪 UUID，不提供时系统自动生成 |

---

## 2. 核心接口规范

### 2.1 文本与多模态对话补全 (Chat Completions)
- **请求方式**: `POST /v1/chat/completions`
- **功能描述**: 支持纯文本上下文问答与图文多模态推理，支持流式 SSE 输出。

#### 请求体参数 (Request Body)
```json
{
  "model": "Virtu-Omni-10B",
  "messages": [
    {
      "role": "user",
      "content": "请分析下方图像中的缺陷类型并给出维修建议。",
      "image_base64": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQ..."
    }
  ],
  "max_tokens": 512,
  "temperature": 0.7,
  "top_p": 0.9,
  "stream": false
}
```

#### 响应体 (Response Body, stream=false)
```json
{
  "id": "chatcmpl-virtu-1729876543000",
  "object": "chat.completion",
  "created": 1729876543,
  "model": "Virtu-Omni-10B",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Virtu-Omni-10B 分析结果：图像表面呈现微米级疲劳裂纹，位于结构连接应力集中区。建议立即执行超声波无损探伤，并调整载荷参数。"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 1056,
    "completion_tokens": 48,
    "total_tokens": 1104
  },
  "performance": {
    "latency_ms": 118.4,
    "target_threshold_ms": 200.0,
    "slo_satisfied": true
  }
}
```

---

### 2.2 跨模态文本到图像生成 (Text-to-Image Generation)
- **请求方式**: `POST /v1/multimodal/generate_image`
- **功能描述**: 原生端到端利用统一 Transformer 生成高保真图像。

#### 请求体参数 (Request Body)
```json
{
  "prompt": "智能工厂流水线上的高精度六轴工业机器人，超高画质，工程制图细节清晰，电影级光照",
  "height": 512,
  "width": 512,
  "num_inference_steps": 25,
  "guidance_scale": 7.5
}
```

#### 响应体 (Response Body)
```json
{
  "created": 1729876545,
  "prompt": "智能工厂流水线上的高精度六轴工业机器人...",
  "height": 512,
  "width": 512,
  "image_base64": "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBD...",
  "generation_time_ms": 142.6,
  "status": "SUCCESS"
}
```

---

### 2.3 细粒度图像理解与问答 (Visual Understanding & QA)
- **请求方式**: `POST /v1/multimodal/understand`
- **功能描述**: 提供图像目标定位、属性描述与推理。

#### 请求体参数
```json
{
  "image_base64": "/9j/4AAQSkZJRg...",
  "question": "图中一共有几个装配件？每个部件的空间几何位置关系是什么？"
}
```

#### 响应体
```json
{
  "question": "图中一共有几个装配件？...",
  "analysis": {
    "primary_objects": ["基座组件", "驱动轴承", "液压阀门"],
    "text_response": "经全自研连续视觉 Patch 投影解析，视野内识别出 3 个核心装配件...",
    "confidence_score": 0.992
  },
  "latency_ms": 125.1,
  "slo_met": true
}
```

---

### 2.4 集群服务健康度探针 (Health & Telemetry)
- **请求方式**: `GET /v1/health`
- **响应体**:
```json
{
  "status": "HEALTHY",
  "model": "Virtu-Omni-10B",
  "version": "1.0.0",
  "device": "cuda:0",
  "gpu_memory_allocated_gb": 22.05,
  "paged_attention_enabled": true,
  "target_latency_ms": 200.0
}
```
