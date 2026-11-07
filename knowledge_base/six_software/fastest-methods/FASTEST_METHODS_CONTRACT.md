# 最快方法证据基准契约（FASTEST_METHODS_CONTRACT）— 阶段 A

> 本文件是 `D:\Virtu模型\knowledge_base\six_software\fastest-methods\` 的唯一格式契约（阶段 A）。
> 目标：让 Virtu 模型学会「自己找画图/建模/仿真/加工的最快方法」——为四大任务族 × 六软件建立候选路线全集、7 维度量、最快结论与跨软件选型矩阵。
> 生成基准：2026-11-04。硬边界不变：无许可证/激活机制内容；一切断言可回溯知识库 E-ID；**禁止臆造新实测**。

## 1. 目录结构（固定）

```
D:\Virtu模型\knowledge_base\six_software\fastest-methods\
├── FASTEST_METHODS_CONTRACT.md        ← 本文件
├── <software>.md × 6                  ← 分片子代理各写其 2 个软件（solidworks/autocad/nx/cimco/vericut/sscnc）
├── fastest-methods.md                 ← 组织者归并：每软件 × 每任务族最快结论总表
└── toolchain_choice_matrix.md         ← 组织者合成：跨软件选型矩阵
```

每份 `<software>.md` 内容 = **候选路线全集 + 度量评分 + 最快结论**（该软件完整自主文档）。

## 2. 四大任务族 × 六软件适用性（先声明 N/A）

| 任务族 | SOLIDWORKS | AutoCAD | NX | CIMCO | VERICUT | SSCNC |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| 画图 2D drafting | ✅ 草图→工程图 | ✅ 主职 | ✅ Drawing 制图 | N/A（NC 编辑器，无 2D 绘图） | N/A（仿真验证，无 2D 绘图） | N/A（数控操作仿真，无绘图） |
| 建模 3D modeling | ✅ 参数化主职 | ⚠️ 仅 2.5D 拉伸 | ✅ 高端主职 | N/A | N/A | N/A |
| 仿真 | ✅ Simulation FEA(FOS≥1.5) | N/A | ✅ CAE/Nastran | N/A | ✅ 切削仿真主职 | ✅ 面板级虚拟加工 |
| 加工 | ⚠️ 辅助（CAM add-in） | N/A | ✅ CAM 主职 | ✅ NC 校验/后处理 | ✅ 加工验证 Auto-Diff | ✅ 循环启动验证 |

- N/A 必须给出**一句原因**（如"CIMCO Edit 2026 为 NC 编辑器，无 2D 绘图任务域"），不得空标。

## 3. 候选路线全集格式（每任务族 × 该软件适用路线）

每路线一行/一小节：

```
### R-<family>-<n>：<路线名>
- 通道类型：GUI / API / 插件 / 批处理 / 文档化 / 混合（可组合，如 API+批处理）
- 调用路径：可复现描述（菜单路径 / COM 调用 / NXOpen journal / bat 参数 / 快捷键）
- 证据链接：knowledge_base 对应文件与 E-ID / runbook 节 / commands.md 命令 ID（必须具体）
- 度量：见 §4
```

路线必须覆盖该软件知识库中真实存在的通道（from automation_api.md / plugins.md / workflows.md / commands.md），**不得发明不存在的通道**。

## 4. 度量维度（7 项，每路线逐项标注）

| 维度 | 取值 | 规则 |
| :-- | :-- | :-- |
| 步骤数 | 整数 | 从启动/准备到产出结果的用户/调用步数（含必要前置，如开软件、选模板） |
| 命令/API 调用数 | 整数 | 该路线涉及的 API 调用或命令行条数（GUI 路线计为菜单操作数） |
| 启动开销 | 冷/温/常驻 + 说明 | 冷启动（需启动软件进程）、温（软件常驻仅切换）、常驻（无额外启动）；说明估算（如 SLDWORKS 冷启动 30-60s [高] 历史经验） |
| 可并行度 | 高/中/低 | 能否批量并行（如 accoreconsole/ezdxf 可并发多进程=高；COM 单实例=低） |
| 证据等级 | verified-working（历史实测）/ documented-not-probed / 官方文档 | 三态与 knowledge_base 一致 |
| 确定性 | 高/中/低 | API/文件级=高；GUI 坐标点击=低（分辨率/焦点脆弱） |
| 失败风险 | 高/中/低 + 具体风险 | 如 COM 判死(-2147221005)、ROT 未注册、batch 不可靠、GUI 误点 |

## 5. 历史实测必引清单（来自知识库，不得臆造；某软件无记录则标注"无记录"）

- VERICUT：batchp/batcht 批处理（不可靠/部分判死，confirmed-negative）、事务日志 ActionMainPlay 381 条、COM 6 ProgID 判死 -2147221005、GUI 播放按钮坐标 1890,860 @1920×1080、.vcreview 227MB 回读、CGTECH_VCPROJECT/CGTECH_TRANSACTION_LOG=Yes。
- SOLIDWORKS：ROT 未注册（GetActiveObject confirmed-negative）、RunMacro 仅认 .swp、COM 早绑定 verified-working、单位米制。
- NX：run_journal.exe NXOpen journal verified-working、STEP214 导出 verified-working。
- AutoCAD：accoreconsole /i /s verified-working、ezdxf R2018 文件级 verified-working、COM SendCommand verified-working。
- CIMCO：外部 Python Macro B 校验 verified-working、G00 背绘哨兵 verified-working（桥接）、无 COM。
- SSCNC：进程拉起 + win32gui 找窗 + 对刀量离线计算 verified-working（桥接）、面板按键 documented-not-probed。

## 6. 最快结论格式（每任务族，写于该软件 .md 末尾）

```
## 最快结论（<software>）
| 任务族 | 最快路线 | 次优备选 | 判定依据（引 E-ID/runbook/度量对比） | 置信度 |
```

- 判定依据必须是**可比的度量对比**（如"ezdxf：0 步骤（无进程）、确定性高、可并行=高 vs GUI：启动 30s、坐标脆弱——故文件级通道最快"）；
- 置信度：[高]/[中]/[低]，历史实测结论 [高]，纯文档化推断 [低]/[中]。

## 7. 防幻觉与边界

- 每路线证据链接必须真实存在于 knowledge_base（E-ID/命令 ID/runbook 节）；
- 禁止臆造任何"实测耗时/实测步骤数"；时间量级可用知识库记录的或常识性标 `[估算]`；
- N/A 任务族必须说明原因；CIMCO/SSCNC 的 N/A 画图要写清"该软件职责域不含 2D 绘图"；
- 无许可证/激活机制内容。
