# Virtu 模型改良执行台账（2026-11-05 · 全面强化短板）

> 档位：**RSI + 后端缺陷同修（最全面）**。原则：真实、可复现、不越红线（不改权重/生产路由；不拿评测题当训练语料；不按标签名引用分数）。

## 0. 一句话结论

- **后端 toolcall 覆写缺陷：已修复并验证**（真实、可复现）。这是唯一一条确凿会"把模型答对的工具调用改错"的服务层缺陷，已消除。
- **弱项 SFT 候选：已产出 108 条**（求解器可验 + 污染校验 PASS，GPU-free），是权重级训练素材，直接对应 physics/derivation 与 reasoning 里的数值短板。
- **RSI 权重级长任务：中止（让路）**。本机 6GB GPU 正被另一条在跑的 `base_qwen3_8b` 测量 leg 占用，模型在 6GB 卡上来回换载（70s/次），我的 RSI 与它互相拖死且注定在 3600s 预算处 `blocked`；按 AGENTS.md §8.6「独占资源」主动让路。命令已就绪，待静默窗口/云端。

---

## 1. 后端 toolcall 覆写缺陷（已修复）★

**根因**（`virtu_real_backend.py`）：
- `_looks_like_tool_json` 只截取首个 `{` 到末个 `}`，对正确的 `[{...},{...}]` 数组切出非法 JSON → 判成"模型没调工具"。
- 于是落到 `_compile_toolcall_from_prompt` 用单对象**无条件覆写**正确数组；且 `_normalize_tool_obj` 把工具真实字段 `nc_file_path`（见 `bridges/tool_calling_specs.py:158`）改名成 `nc_path`。

**修复**：
- 新增 `_parse_tool_payload` / `_is_call_payload`：扫描每个 `{`/`[` 用 `raw_decode`，对象或"全为调用的数组"都算已作答。
- `_verify_arithmetic_response`：对象/数组都已作答 → 仅归一 tool/action 别名并**保留模型写的字段名**；仅当完全无调用时才编译。
- `_normalize_tool_obj`：删除错误的 `nc_file_path → nc_path` 改名。

**证据**：
- `tests/test_backend_toolcall_batch_defect.py`：5 passed（原 3 条 `xfail(strict=True)` 已转正常；新增 2 条反证：非调用 JSON 误报、三项批调用保留）。
- 关联三文件 `pytest`：41 passed / 4 subtests，0 failed。
- 端到端：双项数组 `len=2` 且含 `runs/b.nc`；单对象保留 `nc_file_path`、不再出现 `nc_path`。
- 离线复算（冻结 leg `board7__frozen_comp_v5__v4`，toolcall n=30）：修复前 old 均分 32.22 vs 修复后 new 32.22，**Δ=+0.00、无一例变坏**。
  ⚠️ 口径诚实标注：该 leg 存盘 `toolcall-h04=100`，但**用当前判分器复评 raw 只得 33.33**——判分器已漂移，故离线复算只能证明"修复不伤任何答案"，**不可**当作与已发布 `toolcall 79.76` 可比的绝对分。

**改动文件**：`virtu_real_backend.py`、`tests/test_backend_toolcall_batch_defect.py`。

---

## 2. 弱项 SFT 候选（已产出，GPU-free）★

用仓内 RSI 同一批解析求解器（`virtu_omni/rsi/candidates.build_sft_candidates`），针对解析可验的 9 类弱任务各合成 12 条，**不调用模型、不改权重**：

- 产出：`data/sft/rsi_synth_weak_2026-11-05.jsonl`
- 规模：**108 行**；任务：`adapt_machine/adapt_material/collision/fea_fos/geom_delta/process/removal/roughness/tolerance` 各 12；跳过 0。
- 校验：`contamination_check.py` → `eval_cases=240 train=108 hard_leaks=0 numeric_proxy_only=23 blocking=0`，**PASS (hard)**（23 条仅共享金标数值、非 prompt/ngram 泄漏）。
- 每条 `meta.verified=true`、答案由求解器双重校验（`physics_invariant` + `world_state_verified`）。
- RSI 运行目录：`runs/rsi/20261105T050146Z_7bc32c91f2ef`。

> 用途：下一轮云端/大显存 LoRA 的训练素材（本机 6GB 训不了 8B）。红线：这不等于"模型已提升"，需训练 + 同尺复评才算。

---

## 3. RSI 权重级长任务（中止·让路）

- 命令（已试跑，`dev=36/val=24` 预算切分正确）：
  ```bash
  .venv/Scripts/python.exe -m virtu_omni.rsi.cli run \
    --model-id virtu-disciplined:v1 \
    --case-dir data/benchmark/virtu_eval_phys_v1 --dims physics,derivation \
    --limit 60 --min-validation 24 --rounds 2 --max-calls 200 --max-seconds 3600
  ```
- 中止原因（实测证据）：`base_qwen3_8b__v4` 测量 leg 正在活跃推进（150→153/210，mtime 持续更新）；`ollama ps` 显示 `virtu-disciplined` 与 `qwen3:8b` 在同一块 6GB 卡上来回换载（"Stopping…"），单次生成 70s，5 分钟仅出 1 条。继续跑会拖垮对方 leg 且自己必在 3600s 处 `blocked`。
- 处置：`taskkill` 终止我启动的 RSI（PID 14316/6720），GPU 已归还基准 leg（现 ollama 独占 qwen3:8b）。
- 待办：等所有 `runner.py/run_chain*/eval_disciplined_ab` 静默 ≥120s 且 `ollama ps` 空后，再跑上述命令；或走云端。

## 4. disciplined 新臂无回归（部分）

`_eval_disciplined_text_v2/raw.jsonl` 停在 **45/60**（reasoning 维未出、knowledge 仅 5 条，未收口）。已出维均高于旧生产基线：

| 维 | disciplined v2 | 旧生产基线 |
|---|---:|---:|
| boundary | 66.50 (n=10) | 37% |
| generalization | 54.38 (n=10) | 27% |
| generation | 56.83 (n=10) | — |
| instruction | 93.33 (n=10) | — |
| knowledge | 95.00 (n=5, 半) | — |

> 只能读作"方向正向、未发现退化"，**不足以**下"全面不降"结论（未跑完 reasoning）。

---

## 5. 下一步（按价值）

1. 等基准 leg 收口/静默窗口 → 跑 §3 的 RSI，拿 `gate.eligible` 与 `awaiting_approval` 候选（`weights_updated=false`）。
2. 把 §2 的 108 条并入下一轮训练集（先 `contamination_check` 复跑），云端 8B QLoRA 训练 → merge → GGUF → 同尺复评。
3. 修掉/复核判分器漂移（`toolcall-h04` 存盘 100 vs 现评 33.33），否则任何"修复增益"都不可比。
4. ~~把 `_compile_toolcall_from_prompt` 里遗留的 `nc_path` 统一为 `nc_file_path`~~ —— 已修，见 §7。

---

## 6. 静默门禁（13:1x 新增工具，替代人工盯屏）

- 工具：`scripts/rsi_quiet_gate.py`；反证测试：`tests/test_rsi_quiet_gate.py`（13 项全绿）。
- 为什么需要它：§3 的失败不是预算写错，而是**被另一条腿挤死**。人工盯屏无法判断"到底空没空"，需要一个可审计的门。

**判据三源合并**（单看任何一源都会被骗）：
1. 进程命令行（复用仓内 foreign-runner 概念，`scripts/eval_disciplined_ab.py` 已记录"只看进程表会在 60 个 GPU 用例在飞时宣布空闲"）；
2. `ollama /api/ps` 是否持有模型；
3. 测量文件 150s 内是否被写过——命令行认不出来的腿，`raw.jsonl` 仍在写；
4. **空监视集判红**（§8.4），不判静默。

**真机干跑证据**（13:12:40，`scratch/_rsi_gate_dry.jsonl`）：判忙，理由为 6 个外来评测进程（`run_chain`/`run_chain2`/`run_chain4`/`drift_watch.py`/`virtu_eval/runner.py`/另一会话的 `virtu_eval.py`）+ `ollama holds qwen3:8b` + `raw.jsonl 42s ago`。判据不是空话。

**反证测试当场抓出我自己两个致命缺陷**（这就是 §8.4 的价值）：
- 若用裸 `virtu_eval` 当判据，会把我自己的 `--case-dir data/benchmark/virtu_eval_phys_v1` 判成外来腿 → 判据收窄为 `virtu_eval.runner` / `virtu_eval.py` / `rsi.cli` 等具体入口；
- 我起的 RSI 子进程命令行含 `rsi.cli`，若只按字符串排除自己（`rsi_quiet_gate`），运行中会把**自己的子进程**判成外来腿并杀掉 → 改为 `proc_lines(exclude_pids=(proc.pid,))` 按 PID 排除。

**换载治本**：`virtu_eval/arms.py` 的 ollama 请求体里**没有 `keep_alive`**，默认 5 分钟租约 —— 这是 70s/条的真因。门禁起跑前 pin `keep_alive=45m`，并在"RSI 100s 未落盘"的 CPU 合成阶段刷新租约。不改任何被 `source_hashes` 纳入的文件。

**运行中让路**：连续 3 次探测到外来腿即 `terminate` RSI 并记 `yielded`，不重演"跑到一半被挤死还占着卡"。

当前状态：13:12:51 起挂起，`--hold 150 --poll 20 --max-wait 14400`，持续判忙（基准腿 167/210 推进中），台账 `scratch/_rsi_gate_receipt.jsonl`。

---

## 7. 编译器字段不一致（同源第二处，已修）

`virtu_real_backend.py:242` 的编译兜底产出 `args["nc_path"]`，但执行器 `bridges/tool_calling_specs.py:476/541` 读的是 `args["nc_file_path"]` —— 即兜底编译出的调用**永远找不到文件**。已改为 `nc_file_path`。

- 安全性核查：`nc_path` 其余出现只在 pipeline 内部 stage 键（`tests/test_extreme_cadcam_pipeline.py:41` 断言的是 stage 字典，与工具参数无关），判分器不引用该字段。
- 回归：新增 `test_the_compiler_emits_the_argument_name_the_tool_actually_reads`。
- 合并测试：`test_backend_toolcall_batch_defect + test_arithmetic_guard + test_real_backend_protocol + test_rsi_quiet_gate` = **57 passed**。
