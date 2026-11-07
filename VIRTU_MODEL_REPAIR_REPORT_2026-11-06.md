# Virtu 模型族修复验收报告（2026-11-06）

> 口径：本报告所有数字均来自 `GET /api/tags`、`POST /api/show`、`GET /api/ps`、`ollama list/show`、磁盘 `find`/GGUF 头解析，`basis = measured`。
> 修复窗口：2026-11-06 01:46 – 08:52 CST。终检时间：08:52 CST。

## 1. 修复前后对比

| 项 | 修复前（01:46 实测） | 修复后（08:52 终检） | 状态 |
|---|---|---|---|
| `/api/tags` 中的 virtu 标签 | 17 个，其中 **4 个 `/api/show` 404** | **13 个，逐个 `ollama show` 全 OK，0 损坏** | ✅ |
| 404 ghost 标签 | `virtu-toolcall:latest`、`virtu-boundary-sft:latest`、`virtu-toolcall:latest.bak_pre_params_repair`、`virtu-production:v3` | 全部清除（`ollama rm` 触发索引重建后消失） | ✅ |
| `virtu-10b:a45b3427` 空 template | `template_source=null`，capabilities 仅 `completion` | 曾修复为 `go_template` + `completion+tools` + `num_ctx 8192`；随后**用户决策下线删除**（见 §2） | ⚠️ 已下线 |
| 10B 权重与 receipt | `checkpoints/virtu-10b-d46-q4_0.gguf`（~5.7 GB）+ receipt 存在 | 均不存在（`ollama list` 0 条、磁盘 >100 MB 匹配 0 个） | ✅ 归零 |
| `virtu-moe-14b` receipt | 无独立 receipt 文件 | 两份 receipt 补齐（真实 sha256） | ✅ |
| MoE 激活参数量 | `6,813,424,128`（total/2 朴素估算，**错误**） | **`8,191,030,272`**（= total − 未激活专家 FFN） | ✅ |
| `virtu-moe-14b:bf16` 注册状态 | receipt 写 `not_registered`（与事实不符） | `registered_in_ollama`（02:07 已注册，`num_gpu=0` 纯 CPU） | ✅ |
| README 在役清单 | 称 10B 在役、moe-bf16 未注册 | 13 标签口径；moe-bf16 已注册；10B 移入「已下线资产」并附重建命令 | ✅ |
| `VIRTU_10B_UPSCALE_PLAN.md` | 停在「阶段 A 已达成、阶段 B/C 待算力」 | 新增 §12「计划终止与资产下线」 | ✅ |
| `PROVENANCE.json` | 无下线记录、无激活参数裁定 | 新增 `retirement_2026_11_06` + `param_arithmetic_2026_11_06`（16 键，JSON 合法） | ✅ |
| 运行态 `/api/ps` | 空（冷） | 驻留 `virtu-moe-14b:latest` 1 个 | — |

## 2. 10B 下线记录（用户决策）

- **决定人**：用户。原话：「10B需要大量资源进行预训练我没有那么多资源所以删掉了」。
- **删除对象**：`virtu-10b:a45b3427`（Ollama tag）、`checkpoints/virtu-10b-d46-q4_0.gguf`（~5.7 GB，46 层 / 509 张量 / 10,120,199,680 参数）、对应 `*.receipt.json`。
- **保留**：`scripts/gguf_depth_upscale.py`（确定性重建脚本，阶段 A 本机 65.6 s）、`Modelfile_virtu_10b_fixed`（已修好空 template 的注册配方）。
- **重建命令**：
  ```bash
  python scripts/gguf_depth_upscale.py --src checkpoints/virtu-comprehensive-q4_0.gguf \
      --out checkpoints/virtu-10b-d46-q4_0.gguf --target-layers 46 --copy-from 18
  ollama create virtu-10b:a45b3427 -f Modelfile_virtu_10b_fixed
  ```
- **能力边界（永久有效）**：L1 结构真实曾达成、L2 能力从未激活；不得表述为「dense 10B 训练达标」。

## 3. MoE 激活参数的可复算裁定

实测超参（`/api/show model_info`）：`block_count=36`、`expert_count=2`、`expert_used_count=1`、`expert_feed_forward_length=12288`、`expert_shared_feed_forward_length=0`、`embedding_length=4096`。

```
总参                    = 13,626,848,256
未激活专家 FFN          = 3 × 4096 × 12288 × 36 = 5,435,817,984
激活量（canonical）     = 13,626,848,256 − 5,435,817,984 = 8,191,030,272
路由 W_gate             = 2 × 4096 × 36 = 294,912
交叉校验                = 8,191,030,272 − 8,190,735,360(=Qwen3-8B dense 基座) = 294,912 ✅
```

- 「总参 × used/expert = 6.81B」是**错的**：两专家共享注意力与嵌入层，不能整体折半。
- 8,190,735,360 是「不含路由」口径，与 canonical 差 294,912，属口径差非错误。对外统一 **≈8.19B**，精确值以 `PROVENANCE.json#param_arithmetic_2026_11_06.canonical` 为准。

## 4. 终检清单

- [x] 13 个 virtu 标签逐一 `ollama show` 全 OK（0 损坏）
- [x] 10B 在 `ollama list` 与磁盘（>100 MB）双向归零
- [x] 两份 MoE receipt 为合法 JSON，`active_parameters_per_token = 8191030272`
- [x] `PROVENANCE.json` 合法（16 键），含 `retirement_2026_11_06` / `param_arithmetic_2026_11_06`
- [x] README / 计划 §12 / 雷达图 三处对 10B 下线表述一致
- [x] 台账备份：`checkpoints/PROVENANCE.json.bak_20261106_0845`

## 5. 遗留与建议

1. **并发写入风险**：02:05–02:13 期间另一进程同时改动同一批模型（删 10B、注册 `moe-14b:bf16`、patch 雷达图）。后续对 Ollama/共享文件的任何操作，须以「动手前重测」为准。
2. **`virtu-moe-14b:bf16` 未做推理 smoke**：27.26 GB、`num_gpu=0` 纯 CPU，加载代价高，仅作精度基准底座保留。
3. **8.2B 族仍为 5 个别名共享同一 blob**（`sha256:c3b78c77…`）：非缺陷，但任何 A/B 必须按 blob 内容寻址，不能按 tag 名归因。
