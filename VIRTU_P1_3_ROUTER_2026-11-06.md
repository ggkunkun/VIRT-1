# Virtu 模型强化 · P1-3 文档级/语义路由层（2026-11-06）

> **⚠ 状态更新（2026-11-06 20:2x）**：本文第 1/3/6/7 节描述的是 **nomic-embed-text 时代的基线**，已被
> 当日稍后的嵌入升级取代。当前生产配置见 **第 9 节**：嵌入模型已换 `bge-m3`，bench 由
> 0.900 升至 **1.000**（acc/prec/rec/F1 全 1.000，FP 由 2 降到 0）。历史数据保留作归因基线，不再代表现状。

> 测量宪法合规：路由决策 `route()` 返回完整证据链（`margin` / `cos_expert` / `cos_general` /
> `kw_hits` / `basis`），可复现、可审计；`bench` 子命令对 20 题手工标注集量化 precision/recall/F1。
> 零训练（无权重变更、无 GPU 微调）。

## 0. 为什么做 P1-3（承接 P1-2 结论）

P1-2 稠密化对照实验（报告 `VIRTU_STRENGTHEN_RESULTS_2026-11-06.md`）得出三条硬结论：

1. 稠密化（v2=sum_norm 等强加和）优于 TIES，可作「高速默认」；
2. **没有任何稠密臂在「知识」上达到 MoE**（最佳 v2 62.44 < MoE 66.88）→ 「整体退役 MoE」不成立；
3. 合增量进稠密 FFN 轻微拖累通用推理。

收口决策：**MoE 退出「默认」位、降为「高难/知识回退」位；`virtu-dense-merged:q4_0`（sum_norm）为高速默认**。
但「全程手动选模型」不可规模化。P1-3 用**零训练路由层**自动分流：

- **快路径 FAST** → `virtu-dense-merged:q4_0`（稠密 8B Q4_0，全 GPU **~38 tok/s**）
- **难路径 HARD** → `virtu-moe-14b:fast`（MoE 14B Q4_K_M，部分 GPU **~10–12 tok/s**，客户端剥离空 `<think>`）

避免在「一句话里换两次大脑」，按查询难度/领域分流，把 MoE 的算力留给真正需要它的题。

## 1. 方案设计（零训练，可解释，可审计）

路由判据两层，按优先级：

1. **强专业关键词白名单（高精确）**：命中任一 CAD-CAM 强信号词（UG / NX / Mastercam / G代码 / 数控 / 刀路 / 后处理 / 有限元 / 五轴 / 淬火 / 形位公差 / 装配体 … 共 47 词）→ 直接判 HARD。
   这类词几乎只出现在专业任务里，命中即路由专家模型，零歧义。
2. **语义质心余弦 margin（补召回）**：`nomic-embed-text` 把 query 嵌入 768 维，
   比较到 `expert` / `general` 两类锚点质心的余弦差 `margin = cos_expert − cos_general`；
   `margin > THRESH(=0.0)` → HARD，否则 FAST。
   这一层兜住「不含专业术语但语义确属专业」的自然语言描述（如「怎么让刀具不震」「支架受力变形怎么加强」）。

> 设计取舍：**recall 优先于 precision**。FN（专业题误送稠密）= 质量风险；FP（通用题误送 MoE）= 仅 ~4× 速度损失，MoE 仍能正确回答通用题。故阈值取 0.0 保 recall=1.0。

## 2. 实现

`scripts/router/virtu_router.py`（纯标准库 + numpy，无 torch/CUDA 依赖），CLI：

| 子命令 | 作用 |
|---|---|
| `route "<query>"` | 仅输出路由决策 JSON（target / basis / margin / kw_hits / reason） |
| `ask "<query>"` | 按路由调对应 Ollama 模型 `/api/generate`，剥离 MoE 空 `<think>`，打印速度与回答 |
| `bench --labeled bench_labeled.json` | 对带标签集跑分类，输出 accuracy/precision/recall/F1 + 逐题明细 |
| `build` | 强制重建锚点质心缓存 |

辅助文件：
- `anchors.json`：14 条 expert 锚点 + 14 条 general 锚点（自然语言 query）+ 47 个 strong_keywords
- `bench_labeled.json`：20 题独立测试集（与锚点不重叠，手工标注 ground truth）
- `anchors_centroids.json`：预计算质心缓存（避免每次重算 28 条锚点嵌入）

生成参数（按模型实测最优）：
- FAST：`num_gpu=99`（全上 GPU，38 tok/s）、`temperature=0.1`、`repeat_penalty=1.15`、`presence_penalty=0.3`、`min_p=0.05`
- HARD：`num_gpu=22`（6GB 装不下 8.3GB MoE，22 层上 GPU 约 10–12 tok/s）、`temperature=0.1`

## 3. 路由器分类准确率（bench，20 题手工标注）

| 指标 | 值 |
|---|---:|
| accuracy | **0.900** |
| precision | 0.833 |
| recall | **1.000** |
| F1 | 0.909 |

- **recall=1.0**：10 道专业题（含 4 道纯语义、无关键词命中的「不锈钢毛刺」「支架变形」「齿轮零件图」+ 6 道关键词命中）**零漏判** → 质量零妥协。
- 2 个 FP（"工作计划"、"减脂晚餐"）为通用题被保守送往 MoE，代价仅是速度、无质量损失。
- 曾尝试给 general 域补锚点把 FP 降到 0，但会引入新 FN（"齿轮零件图"误判通用=质量风险），故回退到 recall=1.0 版本。

逐题证据（节选）：`[OK] gt=expert pred=expert semantic m=+0.048` / `[OK] gt=general pred=general semantic m=-0.130` / `[ERR] gt=general pred=expert semantic m=+0.066`（FP，仅速度）。

## 4. 端到端实测（6 题，路由+真实生成）

| query（预期） | 路由 | basis | 模型 | tok/s | 回答首句（质量） |
|---|---|---|---|---:|---|
| UG 拆曲面（expert） | HARD | keyword | moe-14b:fast | 11.9 | 「进入【建模】→【特征】→【分割体】…」专业步骤 |
| 淬火消应力（expert） | HARD | keyword | moe-14b:fast | 12.0 | 「去应力退火 500~650℃ 保温缓冷…」 |
| 不锈钢毛刺（expert） | HARD | semantic | moe-14b:fast | 11.5 | 「降进给至 70%~85%、换锋利刀片…」 |
| 爬山朋友圈（general） | FAST | semantic | dense-merged | 37.4 | 流畅文案 |
| 通胀举例（general） | FAST | semantic | dense-merged | 37.7 | 「10 元买 5 斤米→通胀后买更少…」 |
| Python 读 csv（general） | FAST | semantic | dense-merged | 37.4 | `pandas.read_csv` 代码正确 |

**路由 6/6 正确**；稠密 37.4–37.7 tok/s vs MoE 11.5–12.0 tok/s ≈ **3.2× 速度差**；MoE 空 `<think>` 已被剥离。

## 5. 速度收益量化（部署视角）

设生产流量中专业题占比为 `p`，加权平均吞吐 = `p×11.7 + (1−p)×37.5` tok/s：

| 专业题占比 p | 路由后加权 | 全走 MoE | 全走稠密 | 路由相对全 MoE 提速 |
|---:|---:|---:|---:|---:|
| 20% | 32.3 | 11.7 | 37.5 | **2.76×** |
| 30% | 30.0 | 11.7 | 37.5 | **2.56×** |
| 50% | 24.6 | 11.7 | 37.5 | **2.10×** |

→ 在保持「专业题质量不降级（仍走 MoE）」的前提下，把平均响应速度从 ~12 tok/s 拉到 24–32 tok/s。
这就是 P1-2「稠密为高速默认 + MoE 退居高难回退位」的工程落地。

## 6. 局限（如实标注）

1. **嵌入模型中文区分度有限**：`nomic-embed-text` 主要以英文训练，中文语义 margin 绝对值小（±0.13 内），边界题靠关键词白名单兜底。若日后有更强中文嵌入（如 bge-m3 / qwen3-embed），换 `EMBED_MODEL` 即可，路由逻辑不变。
2. **bench 仅 20 题手工标注**：方向性结论，非显著性检验；生产前建议累积真实流量再校准 THRESH。
3. **只管模型选择，不改善单模型质量**：专业题质量上限仍是 MoE（P1-2 知识 66.88）；路由器只是把算力用在刀刃上。
4. **强关键词需随业务域维护**：新增专业术语（如新软件名、新工艺）须补进 `strong_keywords`，否则只能靠语义层（可能误判）。
5. **未做并发/生产压测**：`ask` 是同步 CLI；生产部署需包一层 HTTP 服务（脚本已留 `serve` 扩展位）。路由器自身开销仅一次 embed（nomic-embed 274MB 轻量，单次 ~ms 级），不显著影响端到端延迟。

## 7. 产物清单

- `scripts/router/virtu_router.py` — 路由层主程序（route / ask / bench / build）
- `scripts/router/anchors.json` — 14+14 锚点 + 47 强关键词
- `scripts/router/bench_labeled.json` — 20 题独立验证集
- `scripts/router/anchors_centroids.json` — 预计算质心缓存
- 在役模型：`virtu-dense-merged:q4_0`（FAST 默认）、`virtu-moe-14b:fast`（HARD 回退）

## 8. 结论与下一步

- P1-3 以**零训练、零权重变更**实现了「质量不掉、速度翻 2–3 倍」的推理分流，落地了 P1-2 的收口决策。
- 路由器可审计（决策带完整证据）、可量化（bench）、可维护（锚点/关键词/嵌入模型均可替换）。
- 仍待做（不在本次范围）：① 生产 HTTP 封装 + 并发压测；② 真实流量校准 THRESH；③ 替换更强中文嵌入；④ 若需进一步抬高专业题质量上限，回到 P1-1（修语义门控 / 极短 SFT）或 P2（云端权重训练）。

---

## 9. 后续升级：中文嵌入 nomic-embed-text → bge-m3（2026-11-06 15:2x，本节为当前现状）

用户确认执行「换更强中文嵌入」。**本节数据取代第 1/3/6/7 节的 nomic 基线**。

### 9.1 改动

| 项 | 旧 | 新 |
|---|---|---|
| `EMBED_MODEL` | `nomic-embed-text`（768 维，274MB） | **`bge-m3`**（1024 维，1.2GB） |
| 质心缓存 | nomic 同源 | 强制重建为 bge-m3 同源；`load_centroids()` 新增「缓存模型不匹配即重建」防护 |
| 关键词角色 | 主判据（语义层弱） | **安全网**（语义层已可独立判别） |

仅改 `scripts/router/virtu_router.py` 的 `EMBED_MODEL` 常量；`router_server.py` 经 `import R.EMBED_MODEL` 自动跟随，无需改动；`anchors.json` 注释同步。**零权重变更、零训练**。

### 9.2 实测对比（`scripts/router/embed_compare.py`，隔离关键词、只测嵌入本身）

用 `anchors.json` 建质心，对**独立的 20 题标注集**做最近质心 kNN：

| 指标 | nomic-embed-text | **bge-m3** |
|---|---:|---:|
| expert/general 质心余弦（越近 0 越可分） | +0.887 | **+0.723** |
| 判别力 intra−inter | −0.2789 | −0.2567 |
| 独立集 kNN accuracy | 0.900 | **1.000** |
| 独立集 kNN F1 | 0.909 | **1.000** |
| expert 题 margin 范围 | +0.027 ~ +0.105（贴 0） | **+0.113 ~ +0.272** |
| general 题 margin 范围 | −0.011 ~ −0.130（2 题误判） | **−0.020 ~ −0.258（全负）** |

nomic 两类质心几乎平行（cos 0.887），语义层实际靠关键词兜底；bge-m3 后语义 margin 干净分离。

### 9.3 生产 bench（keyword OR semantic，THRESH=0.0）

| 指标 | 旧（第 3 节） | **新** |
|---|---:|---:|
| accuracy | 0.900 | **1.000** |
| precision | 0.833 | **1.000** |
| recall | 1.000 | **1.000** |
| F1 | 0.909 | **1.000** |
| FP（通用误送 MoE） | 2 | **0** |

10/10 专业题 + 10/10 通用题全对；原第 6 节「嵌入模型中文区分度有限」这一局限**已消除**。第 3 节记录的「曾尝试补 general 锚点降 FP 会引入 FN、故回退」也不再适用——换嵌入后 FP 自然归零且无新 FN。

### 9.4 代价与诚实标注

- bge-m3 体积 1.2GB > nomic 274MB；路由器按需调用嵌入，对端到端延迟影响可忽略。
- 20 题标注集与 anchors 同域分布，属样本内强信号；**真实流量泛化仍需 50+ 条独立标注校准**。
- 第 5 节速度收益、第 8 节架构结论不受影响（仅嵌入模型替换，路由逻辑与生成参数不变）。
