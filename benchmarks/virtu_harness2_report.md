# Virtu-Omni-10B x Harness 2 递归强化闭环官方评测报告

**模型**: Virtu-Omni-10B / Virtu-CAD-CAM-10B  
**引擎**: Google Research Harness 2 (Recursive Agent Harnessing for an Open World, arXiv:2610.14224)  
**递归阶数 (Budget)**: `k = 1` | **递归模式**: `parallel`  
**总任务数**: 2 | **通过数**: 2 | **综合达标率**: **100.0%**  
**总耗时**: 97.74s  

---

## 1. 核心改进与双重递归机制 (Dual-Level Recursion)

本次接入全面打通了 Harness 2 的两大核心机制，在**底座模型权重冻结（Frozen Weights）**的前提下实现了智能体运行环境的自主进化：

1. **任务级递归 (Task-Level Recursion: Propose–Probe–Compose)**：
   - **Propose (提案)**：针对工业任务特征自动生成不变量（Invariant）与领域（Domain）级脚手架补丁；
   - **Probe (探测)**：在沙箱环境中对比候选脚手架在同一任务上的代码执行轨迹与防干涉表现；
   - **Compose (合成)**：通过行为反差（Behavioral Contrast）零标签自动合成最优 Harness 配置。
2. **脚手架级递归 (Harnessing-Level Recursion: Continual Experience Accumulation)**：
   - 提取跨任务的高可信度工程教训（Lessons & Evidence），持久化归档至 `library.jsonl`，为后续未知工程任务提供先验引导。

---

## 2. 8 大组件调优拓扑 (The 8 Harness Components)

| 编号 | 组件名 | 运行时角色 | 本次接入定义与调优策略 |
| :--- | :--- | :--- | :--- |
| **c1** | `systemprompt.md` | 身份与上下文 | 注入六大工业软件体系与工具调用首选范式 |
| **c2** | `guardrails.md` | 工业安全护栏 | 强制生效壁厚底线 ($t \ge 2.0\text{mm}$)、防过切、主轴转速与切削液准入 |
| **c3** | `LongTermMEMORY.md` | 长期记忆库 | 归档 SS304、Ti-6Al-4V、AL7075 等金属材料力学切削参数与避坑经验 |
| **c4** | `tool_guidance.md` | 工具调用指引 | 10 大核心工业函数参数契约与 JSON Schema 约束 |
| **c5** | `sub_agents/` | 专家子智能体 | 细分 3D 建模师 (`modeler`) 与 CAM/数控专家 (`cam_engineer`) |
| **c6** | `skills/` | 可复用工作流 | 参数化特征树驱动、Windows 桌面工业自动化工作流 |
| **c7** | `scripts/` | 确定性代码助手 | 几何物理有效性校验、方程式转义验证脚本 |
| **c8** | `plugin/` (hooks) | 运行时中间件 | 工具调用前参数拦截校验与沙箱仿真后置审计 |

---

## 3. 工业基准任务测试明细

| 任务 ID | 工业领域 | 零件制造意图简述 | 物理壁厚与参数校验 | 方程式与宏代码 | 评测结论 |
| :--- | :--- | :--- | :---: | :---: | :---: |
| `cad-sleeve-01` | die_and_mold | 我想要一个材质为SS304的回转模具套筒，要求最大外径为110.... | 100% 达标 | 语法完备 | ✅ **PASS** |
| `shaft-cr12mov-04` | die_and_mold | 制造一款微型机冷挤压冲头轴模具，材质为Cr12MoV，外径53m... | 100% 达标 | 语法完备 | ✅ **PASS** |

---

## 4. 交付与接入总结

- **无缝兼容**：完全适配 Google Research 原生 `google-research/harness2` 框架；
- **原生支持 Windows 环境**：完成了核心文件锁跨平台原子化修补；
- **支持多端消费**：通过 `workbuddy_virtu_bridge.py` 暴露标准 OpenAI API 与 `/v1/harness2/*` 状态热插拔接口，支持 WorkBuddy 与自定义工业客户端直接消费进化后的脚手架能力。