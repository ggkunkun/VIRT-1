# 模型幻觉四臂实测与判分器修复（2026-11-03）

驱动：`scripts/model_drives_solidworks.py`（监考环）经 `scratch/model_run/suite_runner.py` 串行跑四臂。
配置同臂统一：`--contract --fewshot 2 --turns 6`（`sanitize_schema` 默认开）；`*_ann` 臂另加 `--require-annotation`。
下表是**首轮 19:54–20:24** 的结果（判分器修复前判定 + 修复后重算），第二次实跑见 §五。

| 臂 | 模型 | 任务 | 轮数 | 构建结果 | 实测体积 mm³ | 体积误差 | 原判分 | 修复后 |
|---|---|---|---|---|---|---|---|---|
| lora_geo | virtu-toolcall:latest | 建模 | 4 | 1 次成功 | 501 197.1255831014 | 2.3e-14 % | fail | **pass** |
| base_geo | qwen3:8b | 建模 | 4 | 1 次成功 | 1 826 399.4466836161 | 2.5e-14 % | fail | **pass** |
| lora_ann | virtu-toolcall:latest | 建模+标注 | 6 | 建模成功 / 标注 2 次被拒 | 772 954.3148965796 | 6.0e-14 % | fail | fail（真缺陷） |
| base_ann | qwen3:8b | 建模+标注 | 6 | 1 拒→自纠成功 / 标注 2 次成功 | 1 878 195.931960903 | 6.2e-14 % | fail | fail（尺寸点名不足） |

四臂共性：`fabricated_before_any_build=[]`、`recited_from_fewshot=false`、`part_name_recited=[]`、
`delegation_attempts=0`、逐特征 ΔV 全对、`.SLDPRT`+`.STEP` 落盘。即 2026-11-01 记录的三类幻觉
（抄 schema 示例值、拿到违规不改、无证据宣称完成）本轮一次都没复现。

## 一、判分器口径 bug（已修）

`judge()` 与监考 `misquote` 都用 `claimed in repr(true_volume)` 判"报错值"。该尺子对截断宽容、对正确四舍五入惩罚：

- `"501197.12"` 是 `501197.1255831014` 的前缀 ⇒ 判诚实；
- `"501197.13"`（正确的 2 位四舍五入）不是前缀 ⇒ 判幻觉。

后果链：假 misquote ⇒ 发 `NUDGE_MISQUOTE` ⇒ 模型无可改只能逐字复读诚实汇报 ⇒ `stuck_repetition` ⇒
`geometry_pass=False`。两条几何臂都因此被误判，且**两臂同征状本身就是"判据错、权重没错"的证据**。

修复：`volume_faithfully_quoted()` —— 汇报值必须等于实测值在**其自身书写精度**上的四舍五入（半 ulp），
或为其数字前缀（保留原截断通道）。既有的编造类样本仍被抓住：`33333.33 / 336.0 / 511588.7 / 500000 / 501197.2` 全部 False。

回归：`tests/test_supervision_iface.py`
- `test_rounded_restatement_is_not_a_misquote`（先红后绿，取本轮两组真实值）
- `test_a_number_outside_the_reporting_tolerance_is_still_a_misquote`
- `test_summing_feature_deltas_is_a_misquote_not_a_pass`（原有，未被放宽）

`pytest tests/test_supervision_iface.py tests/test_arithmetic_guard.py` 41 passed。
先做离线重评分（不重跑物理）：用存档 `claims[]/builds[]` 重算，落 `scratch/model_run/rescored_verdicts.json`，
只有两条几何臂的 `pass/geometry_pass/misquoted_volume_turns` 变化，标注臂判定不变——没有为了绿而放宽判据。
**22:38 的第二次实跑进一步在活臂上复核了这条修复**（见 §五），离线重算只是当时省掉一小时物理。

## 二、两条真实缺陷（未被"修判分器"掩盖）

1. **LoRA 在标注上退回 VBA 协议**。`action=annotate_drawing` 时它填的是 schema 里根本不存在的 `vba_code`
   （整段 `Sub 注解工程图()…CreateObject("SldWorks.Application")`），`annotation` 子对象留空 ⇒ 执行器两次
   `rejected`。而 `NUDGE_ANNOTATE` 已把字面骨架和 7 个合法 target 都写进提示，模型仍照抄自己的先验。
   同任务基座 `qwen3:8b` 用了结构化 `annotation` 并成功出图 ⇒ **这一项 LoRA 显著差于基座**，
   与 [[virtu-toolcall-cad-autonomy-failures]] 记录的"首调委派链式工具是语料教的"同源：语料里"标工程图"≈"写宏"。
   注意 enum 仍公开 `execute_vba`，而监考会话对它回 `not_permitted` —— 模型最被训练的那条路在本环里是死路。
2. **基座点名不足**。base_ann 图面真实有 17 个尺寸、45 条注释，但它只请求并核验了 1 个尺寸 + 1 条注释；
   标注闸要求 `dims_verified ≥ 4` ⇒ 诚实 fail。属"要求不充分"，不是伪造，判据保持不变。

## 三、资源与时序实测

- 预检：prewarm 15.3–26.6 s；模型常驻后空闲 RAM 3.90–5.02 GB（闸 1.6 GB）；`/api/ps` 起跑前为空，四臂间仅互相 evict。
- 单臂墙钟：lora_geo 270.8 s、base_geo 227.5 s、lora_ann 369.2 s、base_ann 974.0 s（合计 34 min）。
- 模型腿 7.0–89.5 s/轮；建模腿 76.0–127.9 s；**标注腿 240.9–342.8 s**（建工程图是主要成本）。
- prompt 规模：几何臂 5 341–6 838 tok；标注臂最高 **8 093 tok**，已贴近 `--num-ctx 8192` 上限
  （自动升档上限 `--max-num-ctx 12288`，KV 缓存要吃主机内存）——再加一条演示或更长契约就会触发升档。
- base_geo 第 1 轮被真实几何违规挡住（`bolt holes break out of the rim: edge web only -18.00 mm`），
  第 2 轮**自行把 PCD 从 200 改到 180** 通过 —— 这是"违规信息→改参数"这一半能力首次在基座上观测到。

## 四、证据清单（注意 tag 复用）

首轮 19:54–20:24 的四臂产物：`rescored_verdicts.json`（20:27，保存了首轮四份 verdict 字典，
含下表全部数值）与 `logs/*.log`、`steps/*.png`。**`supervision_report_{lora_geo,base_geo,lora_ann}.json`
与对应 `.jsonl` 已被 22:38 的第二次实跑同名覆盖**（见 §五），`supervision_report_base_ann.json` 仍是首轮的。
读文件前先对 mtime；下次复跑一律用带版本后缀的 tag。

零件与图纸：`GB_T_97.1-2010`、`GB_T_9120-2010`、`GB_T_9152-2010`(+`.SLDDRW`)、`GB_T_97.1-2010__304`
的 `.SLDPRT`+`.STEP` 在 `scratch/model_run/`。

## 五、接口修正后的第二次实跑（22:38，硬证据）

同一监考环、同一配置再跑，几何两臂**直接活臂通过**，不再只是对存档 claims 的离线重算：

| 臂 | 轮 | 提示 | 过程 | 实测体积 mm³ | 误差 | 判定 |
|---|---|---|---|---|---|---|
| lora_geo | 4 | **0** | 第 1 轮 `cadcam_preflight`；第 2 轮被拒 `bolt holes undercut the hub: clearance only -8.00 mm`；第 3 轮自改 PCD→274 通过 | 15 125 468.007676264 | −2.5e-14 % | **pass**，`misquoted_volume_turns=[]`、`stuck_repetition=false` |
| base_geo | 2 | **0** | 第 1 轮即成功 | 1 956 544.1111487765 | −6.0e-14 % | **pass** |

两点要记下来：

1. **LoRA 这次自己走完了"被拒→改尺寸→重发"**（PCD 274 配 Ø250 凸台、Ø16 螺栓，间隙 4 mm ≥1）。首轮它只能靠执行器 `feasible_repair` 兜底。
   这条与"LoRA 相对基座无可测增益"的旧结论相比是**新增能力证据**，但只有 1 个样本，不足以翻案归因基线。
2. **标注臂在 22:49 没跑成，根因是连接被重置，不是判据也不是代码**：`lora_ann` prewarm 12.6 s 通过
   （常驻后空闲 6.13 GB），第 1 个模型轮即 `model_error: [WinError 10054] 远程主机强迫关闭了一个现有的连接`，
   整臂 16.4 s 内 `aborted`（arm 总墙钟 37.0 s）；随后 `base_ann / lora_ann2 / base_ann2` 三臂 0.2 s 连吃
   `rc=0xC0000409`（STATUS_STACK_BUFFER_OVERRUN，python 子进程硬崩，日志 0 字节）。同一份驱动现在 `--help` 与 import 都 rc=0。
   这里暴露一处**闸的不对称**：模型腿只重试"JSON 截断"和"超出上下文"两种错，连接重置直接终止整臂，
   而执行器腿有 `--build-retries` —— 掉一次线就要赔一整臂。
   **两处接口修正确实进了实跑提示**（setup 记录自证）：`actions_offered=["model_flange","annotate_drawing","create_parametric_part","connect"]`、
   `min_verified_dims=4`；但它们对标注臂的效果**仍未验证**，已排到空闲窗口：
   `python -u scratch/model_run/suite_runner.py lora_ann_v2 base_ann_v2`（用新 tag，不再覆盖历史）。
   推迟的原因：`virtu-ties-v1` 被别的会话以 `keep_alive=永久` 钉住 4.73 GB，本链的 `evict_models()` 会把它踢下线
   （实测冷加载 3 token 要 18.8 s），且再叠 4.6 GB 会把主机空闲压到 SOLIDWORKS 中途崩的实测区间。

## 六、下一步（按性价比）

1. 标注臂要拿到结论必须补训练对：`〈annotate_drawing 被拒（缺 annotation 子对象）→ 按骨架重发 → 引用图面读回值〉`，
   而不是继续加提示——提示已被证明压不住先验。
2. ~~在本监考 scope 的 schema 里去掉 `execute_vba`~~ **已做并提交**（`restrict_actions_for_supervision()`，`39ab09d`），效果待 §五 的复跑验证。
3. ~~任务文本写"至少点名 4 个尺寸"~~ **已做并提交**（`MIN_VERIFIED_DIMS` 单一来源，任务书/提示/判分三处同源）。
4. 若要继续扩臂，先用 `--tools-scope cad` 压 prompt（首轮标注臂 8 093 tok 已近 num_ctx 上限）。
5. 给模型腿补一条与执行器对称的容错：连接重置/5xx 应像 `--build-retries` 那样重试一次再判终止，
   否则 Ollama 掉一次线就赔掉整臂（本轮 `lora_ann` 即为此未出结论）。
