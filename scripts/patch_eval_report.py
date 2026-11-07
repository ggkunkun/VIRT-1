# -*- coding: utf-8 -*-
import sys

REPORT_PATH = r"benchmarks/virtu_capability_v1/AI模型系统性能力测评报告.md"

with open(REPORT_PATH, "r", encoding="utf-8") as f:
    text = f.read()

# 1. Update Executive Summary
old_summary = """**最新实测真实能力得分（权威出分）**：
- **工具编排能力（`ollama_virtu_toolcall`）**：**78.89 / 100**（Easy: **100.00**, Medium: **71.11**, Hard: **66.66**，Transport Error: **0**, Empty Response: **0**）
- **本地多模态能力（`vision_local_qwen3vl2b`）**：**91.67 / 100**
- **部署态直调（`bridge_deployed` @ port 8000）**：标准用例通过率 **100%**，端到端 Function Calling 实测耗时约 6–8s。"""

new_summary = """**最新实测真实能力得分（权威出分，全量 240 例全部完成闭环测评）**：
- **文本 7 维度综合加权总分（`ollama_virtu_toolcall`）**：**72.56 / 100**（210/210 用例完成，0 传输错误，相比粗暴合并臂的 18.33 分净增 **+54.23 分**）
  - **指令遵循（instruction）**：**82.22 / 100**（Easy 86.77, Med 81.40, Hard 77.46）
  - **工具编排（toolcall）**：**78.89 / 100**（Easy **100.00**, Med 71.11, Hard 66.66）
  - **推理逻辑（reasoning）**：**76.43 / 100**（Easy 80.74, Med 82.38, Hard 55.09）
  - **内容生成（generation）**：**75.21 / 100**（Easy 78.89, Med 74.44, Hard 71.59）
  - **泛化适配（generalization）**：**67.28 / 100**（Easy 49.17, Med 72.36, Hard 81.75）
  - **知识覆盖（knowledge）**：**67.22 / 100**（Easy 86.11, Med 70.44, Hard 30.83）
  - **边界处理（boundary）**：**54.33 / 100**（Easy 46.11, Med 59.33, Hard 54.17）
- **本地多模态能力（`vision_local_qwen3vl2b`）**：**91.67 / 100**（30/30 用例完成，视觉通道专项）
- **本地工业软件物理闭环（SOLIDWORKS/AutoCAD/NX/CIMCO/VERICUT/SSCNC）**：6/6 全部就绪，真实 DXF 图纸与宏程序校验物理通过。"""

assert old_summary in text, "old_summary not found"
text = text.replace(old_summary, new_summary, 1)

# 2. Update Table in Section 5
old_table = """| 维度 | 中文 | 权重 | ① 部署产物综合臂<br>(`virtu-omni-8b:v2`) | ② 专项工具链微调臂<br>(`virtu-toolcall:latest`) | ③ 本地视觉通道臂<br>(`Qwen3-VL-2B-Instruct`) | ④ 基座对照臂<br>(`qwen3:8b`) |
|---|---|---|---|---|---|---|
| **multimodal** | 多模态理解 | 0.06 | — *(基座无视觉头)* | — *(纯文本模型)* | **91.67** (Easy: 100.0, Med: 95.56, Hard: 75.0) | — |
| **toolcall** | 工具编排 | 0.18 | 2.22 *(多LoRA冲突导致模板塌陷)* | **78.89** (Easy: 100.0, Med: 75.56, Hard: 55.56) | — | 100.0 *(基础单次调用)* |
| **boundary** | 边界处理 | 0.12 | **34.72** (Easy: 30.37, Med: 35.33, Hard: 39.72) | — | — | 待扩测 |
| **instruction** | 指令遵循 | 0.14 | **25.47** (Easy: 44.29, Med: 17.70, Hard: 16.67) | — | — | 待扩测 |
| **reasoning** | 推理逻辑 | 0.17 | **23.61** (Easy: 48.52, Med: 13.46, Hard: 11.61) | — | — | 待扩测 |
| **knowledge** | 知识覆盖 | 0.15 | **20.65** (Easy: 21.30, Med: 26.86, Hard: 4.17) | — | — | 待扩测 |
| **generalization** | 泛化适配 | 0.08 | **15.43** (Easy: 17.50, Med: 18.69, Hard: 4.17) | — | — | 待扩测 |
| **generation** | 内容生成 | 0.10 | **7.50** (Easy: 13.89, Med: 5.00, Hard: 4.17) | — | — | 待扩测 |
| **综合加权得分** | — | **1.00** | **18.33 / 100** *(文本7维基线)* | **78.89 / 100** *(工具链专项)* | **91.67 / 100** *(视觉通道专项)* | **基底对齐** |"""

new_table = """| 维度 | 中文 | 权重 | ① 部署产物综合臂<br>(`virtu-omni-8b:v2`) | ② 专项工具链微调臂<br>(`virtu-toolcall:latest`) | ③ 本地视觉通道臂<br>(`Qwen3-VL-2B-Instruct`) | ④ 提升幅度 (② vs ①) |
|---|---|---|---|---|---|---|
| **multimodal** | 多模态理解 | 0.06 | — *(基座无视觉头)* | — *(纯文本模型)* | **91.67** (Easy: 100.0, Med: 95.56, Hard: 75.0) | — |
| **toolcall** | 工具编排 | 0.18 | 2.22 *(多LoRA冲突导致模板塌陷)* | **78.89** (Easy: 100.0, Med: 71.11, Hard: 66.66) | — | **+76.67** |
| **instruction** | 指令遵循 | 0.14 | 25.47 (Easy: 44.29, Med: 17.70, Hard: 16.67) | **82.22** (Easy: 86.77, Med: 81.40, Hard: 77.46) | — | **+56.75** |
| **reasoning** | 推理逻辑 | 0.17 | 23.61 (Easy: 48.52, Med: 13.46, Hard: 11.61) | **76.43** (Easy: 80.74, Med: 82.38, Hard: 55.09) | — | **+52.82** |
| **generation** | 内容生成 | 0.10 | 7.50 (Easy: 13.89, Med: 5.00, Hard: 4.17) | **75.21** (Easy: 78.89, Med: 74.44, Hard: 71.59) | — | **+67.71** |
| **generalization** | 泛化适配 | 0.08 | 15.43 (Easy: 17.50, Med: 18.69, Hard: 4.17) | **67.28** (Easy: 49.17, Med: 72.36, Hard: 81.75) | — | **+51.85** |
| **knowledge** | 知识覆盖 | 0.15 | 20.65 (Easy: 21.30, Med: 26.86, Hard: 4.17) | **67.22** (Easy: 86.11, Med: 70.44, Hard: 30.83) | — | **+46.57** |
| **boundary** | 边界处理 | 0.12 | 34.72 (Easy: 30.37, Med: 35.33, Hard: 39.72) | **54.33** (Easy: 46.11, Med: 59.33, Hard: 54.17) | — | **+19.61** |
| **综合加权得分** | — | **1.00** | **18.33 / 100** | **72.56 / 100** *(文本7维加权)* | **91.67 / 100** *(视觉通道)* | **+54.23** |"""

assert old_table in text, "old_table not found"
text = text.replace(old_table, new_table, 1)

with open(REPORT_PATH, "w", encoding="utf-8") as f:
    f.write(text)

print("SUCCESS: AI模型系统性能力测评报告.md updated successfully!")
