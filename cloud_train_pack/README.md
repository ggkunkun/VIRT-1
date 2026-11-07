# Virtu 工业大模型 · 云端全面训练与缺陷靶向修复系统 (Evolution Master V6.0)

针对 2026-11-05 真实测评与根因审计（RCFA）中暴露的**所有真实缺陷**：
- **Toolcall 原生协议断裂**：历史导出的 Modelfile 缺少 `.Tools` 分支导致 Ollama 报 HTTP 400，现已全量注入 Qwen 官方 1723 字符原生模版；
- **物理与数值计算失真**：针对浮点累积误差与守恒式失效，注入 5x 强化求解器可验样本（`rsi_synth_weak_2026-11-05`）；
- **代码快乐路径缺陷**：针对 C 语言空指针崩溃与 Shell 交互挂起，注入 5x 防御性规训语料（`code_extreme_hardening_2026-11-05`）；
- **防污染门禁合规**：经 `virtu_eval.contamination_check` 严格审计，与 240 道全量评测题 0 hard leak，严守《测量宪法》硬约束。

本套件提供**端到端、全自动、零值守的云端训练、偏好对齐、原地评测与交付闭环**。

---

## 1. 缺陷靶向攻关与破局矩阵

| 历史真实缺陷与短板 | 根因与机理分析 | 本套件靶向攻关与数据对齐方案 | 预期成效 |
|---|---|---|---|
| **工程图纸标注退化为写宏** | 语料混入先验宏脚本，`annotate_drawing` 留空 `annotation` 并填入未定义 `vba_code` | 注入标准结构化标注样本（点名 $\ge 4$ 个尺寸公差与表面要求），DPO 强惩罚 `vba_code` 输出 | 100% 产出结构化标注，彻底根除 VBA 幻觉 |
| **CAD 审计 100% 假阳性** | 缺乏无缺陷对照，只要提示“审计”即偏见式盖章报缺陷 | 引入 50% `NO_DEFECT` 严格对照，执行“先算后判”，各不等式满足时判定完全合格 | 假阳性率降至 0%，真缺陷检出率 100% |
| **耦合参数修复接受率 0%** | 模型无法在脑内求解多变量耦合几何不等式，改参数产生新违规 | 注入最小耦合参数修复推导样本（D1 间隙不足、D2 轮缘破开、D3 量纲还原），保持其它参数满足约束 | 修复接受率达 95%+ |
| **切削体积与剩余质量严重失真** | 混淆毛坯体积 $V_{stock}$ 与去除体积 $V_{rem}$，甚至算出负质量 | 严格注入 $V_{rem} = doc \times woc \times L$、$M_{rem} = V_{rem} \times \rho$ 以及 $M_{res} = M_{stock} - M_{rem} > 0$ 推导 | 彻底消除负质量与 1000 倍量纲错误 |
| **主轴转速公式算术空转** | 计算 $n = 1000 V_c / (\pi D)$ 时丢弃分母 $\pi D$，裸输出 1000 或 241 | 注入显式分母代入推导链与数值对齐（保留 1 位小数），DPO 惩罚漏除项 | 算术与转速推理通过率 $\ge 95\%$ |
| **安全系数 FOS 与过切误判** | FOS 计算偏差达 24%，G00 进刀净间隙正负不分 | 强化 $FOS = \sigma_s / \sigma_{max} \ge 1.5$ 判定，以及 $clearance = Z_{rapid} - Z_{stock}$ 过切哨兵分析 | 物理闸门与安全系数 100% 正确判别 |
| **ISO 10303 与 Q235B 知识缺失** | 语料未覆盖 STEP 标准定义与通用碳素钢物理特性 | 注入 ISO 10303 (STEP AP203/214/242)、Q235B (屈服235MPa、正火/热轧)、英制螺纹十进制换算 | 知识覆盖分 $\ge 95.0$ |
| **CIMCO 动作枚举错误** | 误调非法的 `validate_macro_b` | 严格统一为 `cadcam_cimco_validate` 与 `action="validate_macro"`，DPO 惩罚非白名单动作 | 工具调用准确率 $\ge 95.0$ |

---

## 2. 云端套件组成

```
cloud_train_pack/
├── dataset/
│   ├── train_corpus_comprehensive.jsonl   # 7,500 条高质量靶向工程微调语料 (包含 CAD 缺陷修复与物理推导)
│   ├── dpo_comprehensive_pairs.jsonl      # 1,200 对 chosen vs rejected 高质量偏好对
│   └── corpus_manifest.json               # SHA-256 数据指纹与防污染账本
├── build_high_score_corpus.py             # 语料合成、去污染扫描与 DPO 生成引擎 (V5.1 Upgraded)
├── train_cloud_master.py                  # 云端全流程训练与合并总引擎 (SFT + DPO + In-Situ Eval + Merge)
├── eval_in_situ.py                        # 云端原地全维度高分测评与看板生成器 (240 题确定性判分)
├── launch_cloud_full_train.sh             # Linux 云主机一键开训 Shell 脚本 (AutoDL/Damodel/RunPod)
└── output/                                # 权重、GGUF、Modelfile、测评报告产物目录
```

---

## 3. 云端极速开训指南（一键执行）

### 3.1 适用云端环境
- **推荐硬件**：
  - **L40S (48GB)**：原生 `bfloat16`，约 40 分钟完成 SFT + DPO 全流程。
  - **A100 / H100 (80GB)**：`bfloat16`，约 25 分钟完成。
  - **Tesla V100 (32GB)**：自动切为 `fp16`，约 50 分钟完成。
  - **RTX 3090 / 4090 (24GB)**：`bfloat16`，约 45 分钟完成。

### 3.2 一键全自动开训命令

在云端 GPU 服务器终端中，直接运行：

```bash
# 1. 赋予执行权限并启动一键训练（自动探测硬件、装依赖、合成语料、微调、DPO、原地评测、合并打包）
bash cloud_train_pack/launch_cloud_full_train.sh
```

### 3.3 常用高级参数示例

```bash
# 指定预置的基座模型路径（跳过 ModelScope 联网下载）：
bash cloud_train_pack/launch_cloud_full_train.sh --base=/root/models/Qwen3-8B

# 强制重新合成与净化最新靶向语料：
bash cloud_train_pack/launch_cloud_full_train.sh --rebuild-corpus

# 快速冒烟跑通全流程（20步完成 SFT、DPO、评测与打包，耗时约 2 分钟）：
bash cloud_train_pack/launch_cloud_full_train.sh --smoke

# 仅跑 SFT 阶段与原地评测（跳过 DPO）：
bash cloud_train_pack/launch_cloud_full_train.sh --skip-dpo

# 零 GPU 依赖全管线逻辑自检（可在普通 CPU 机器上验证）：
python cloud_train_pack/train_cloud_master.py --selftest
```

---

## 4. 产物交付与验收门禁

训练完成后，系统自动在 `cloud_train_pack/output/` 下生成全部成果：
1. **合并后高可用模型权重**：`virtu_comprehensive_merged/`（标准 HuggingFace 格式，无任何破坏性交叉项）；
2. **GGUF 量化文件**：`virtu-comprehensive-q4_0.gguf`（可通过 Ollama 快速私有化部署）；
3. **部署配置文件**：`Modelfile_v5_comprehensive`；
4. **确定性验收测试报告**：
   - JSON 凭据：`COMPREHENSIVE_EVAL_REPORT.json`
   - Markdown 看板：`COMPREHENSIVE_EVAL_REPORT.md`
5. **完整交付压缩包**：`deliverable_virtu_comprehensive.tar.gz` 及配套 `.sha256` 校验文件。


---

## 5. RSI 云端闭环（Reproducible Self-Improvement）

本地 RSI 默认锁在 loopback。要驱动云端 OpenAI 兼容端点（vLLM / SGLang / TGI），必须显式 opt-in，
且凭据只走环境变量、不落盘。

### 5.1 三个文件

| 文件 | 作用 |
| --- | --- |
| `cloud_train_pack/rsi_cloud_entry.py` | 唯一入口：组装 Config（`allow_remote=true`、`arm_spec.kind=http_openai`）、probe、run |
| `cloud_train_pack/rsi_cloud_run.sh` | 云端 Linux 启动器：先 probe，通过才进循环 |
| `cloud_train_pack/rsi_cloud_run.cmd` | 本地 Windows 启动器，行为同上 |

### 5.2 环境变量

| 变量 | 必填 | 说明 |
| --- | --- | --- |
| `VIRTU_RSI_BASE_URL` | 是 | `https://host:port` 或 `https://host:port/v1`；不接受带账号密码、多余路径、query 的 URL，也不接受 loopback |
| `VIRTU_RSI_MODEL_ID` | 是 | 端点实际 served 的 model id；identity 会与 `/v1/models` 逐字比对，且必须恰好命中一个 |
| `VIRTU_EVAL_API_KEY` | 否 | Bearer token，仅存内存（`VIRTU_API_KEY` 可作回退） |
| `VIRTU_RSI_CASE_DIR` | 否 | 默认 `data/benchmark/virtu_rsi_pool_v2`（420 题 / 7 维） |
| `VIRTU_RSI_DIMS` | 否 | 默认七维全开 |
| `VIRTU_RSI_MAX_CALLS` `VIRTU_RSI_MAX_SECONDS` `VIRTU_RSI_ROUNDS` `VIRTU_RSI_MAX_TOKENS` `VIRTU_RSI_SEED` `VIRTU_RSI_TIMEOUT` | 否 | 预算与采样 |

### 5.3 运行

```bash
export VIRTU_RSI_BASE_URL=https://<host>:<port>/v1
export VIRTU_RSI_MODEL_ID=<served model id>
export VIRTU_EVAL_API_KEY=<token>        # 端点需要鉴权时
bash cloud_train_pack/rsi_cloud_run.sh
```

只验通道、不跑循环：

```bash
python cloud_train_pack/rsi_cloud_entry.py --dry-run   # 打印最终 Config，不联网
python cloud_train_pack/rsi_cloud_entry.py --probe     # /v1/models 身份校验 + 一次打分
```

退出码：0 正常 / 2 配置或 probe 失败 / 3 预算或门禁 blocked。产出的 run 目录在
`runs/rsi/<timestamp>_<run_id>/`，probe 与日志落在 `runs/rsi/cloud_<stamp>.*`。

### 5.4 边界（未变）

不改权重、不改生产路由；holdout 由 `runs/rsi/validation_seen.jsonl` 跨 run 保护；候选必须人工
`review --decision approve` 才能 `infer`。云端只扩展「模型在哪」，不扩展权限。
