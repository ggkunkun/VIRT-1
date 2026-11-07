# D 盘模型占比账本与清理判决（2026-11-06）

工具：`scripts/d_model_space_cleanup.py` ｜ 证据目录：`benchmarks/d_model_space_cleanup/`
口径：**独占字节**（按 NTFS 文件 ID 把硬链接聚成簇后，只统计"每个存活路径都落在该构件内"的字节）。
判据：构件是否"无用"由三方证据决定 —— ①全仓引用面（活引用 = arms.json / Modelfile / scripts / tests；历史引用 = 文档与报告）②`checkpoints/PROVENANCE.json` 是否记账 ③ollama manifest 权重层摘要与 E 盘 blob 是否三方一致。体积与日期一律不作判据。

## 1. 实测账本

| 项 | 名义 | 独占（真正可回收） | 口径 |
|---|---|---|---|
| D: 总/已用/可用 | 366.00 / 348.71 / **17.29 GB** | — | measured |
| `D:\Virtu模型` | 270.92 GB | **228.24 GB**（占 D 已用 65%） | measured |
| └ `checkpoints/` | 198.83 GB | **197.25 GB**（占 D 已用 56.6%） | measured |
| └ `.venv` | 5.41 GB | 5.41 GB | measured |
| └ `models/`（Qwen3-VL-2B） | 3.97 GB | 3.97 GB | measured |
| └ `external/` | 3.07 GB | 3.05 GB | measured |
| `D:\pagefile.sys` | 10.59 GB | — | measured（11-02 限到 8192/16384 已生效，原 40 GB） |
| `D:\AIApps` | 34.59 GB | 不属模型口径 | measured |

`checkpoints/` 内按构件的独占字节（= 删掉它实际回收多少）：

| 构件 | 独占 GB | 活引用 | 判决 |
|---|---|---|---|
| 散装 GGUF ×7 | 58.67 | 见 §3 | **T1 删**（字节已在 E） |
| `virtu_moe_14b_hf` | 25.40 | 3（build/receipt/verify 脚本） | 保留：moe 系列唯一 HF 源 |
| `_base_qwen3_8b` | 15.27 | arms.json 活引用 | **红线** |
| `virtu_cad_cam_merged_v3` + `virtu_ties_v1` | 各 0.01（互为硬链接，合计 15.27） | canonical | **红线** |
| `virtu_dense_merged_v2_hf` | 15.27 | 0（仅 1 处文档提及） | **T2 删** |
| `virtu_dense_merged_hf` / `virtu_dense_ties_hf` | 15.27 / 15.27 | 各 4 / 3（build + verify 脚本） | 保留 |
| `virtu_v2_all90_merged` / `virtu_v3_all90_merged` | 各 15.27 | 各 1（`_post_train_v2/v3.py` 单脚本） | **T3 搬 E + junction** |
| `virtu_boundary_sft_merged` | 15.27 | 3（deploy 脚本） | 保留 |
| 8 个 LoRA adapter | 各 0.32–0.34 | PROVENANCE 记账 | **红线** |

## 2. 三条被否证的直觉（都靠实测翻案）

1. **`.tmp.driveupload` 的 27.43 GB 不是垃圾。** 3118 个文件全部是 `checkpoints/` 内分片的硬链接（nlink=2/3，簇与 `virtu_cad_cam_merged_v3`、`_base_qwen3_8b`、`virtu_v2_all90_merged` 重合），独占字节 **0.00 GB**。它同时是 WPS 云文档上传暂存，本轮观测到仍在写入（最新文件距检查 1.6 分钟）。删它回收 0 字节且打断同步。
2. **看起来重复的合并目录并不重复。** 六个 16.4 GB 目录的 `model.safetensors.index.json`、`config.json`、分片名+长度指纹完全相同 —— 但 LoRA/TIES 合并只改数值不改张量形状，指纹相同是必然。逐分片 sha256 实测：`virtu_dense_merged_hf` / `v2_hf` / `ties_hf` 首个分片三个哈希互不相同；`v3_all90_merged` 与 canonical `merged_v3` 只有第 5 分片相同。**没有可白捡的去重收益**；真正互为硬链接的只有 `merged_v3`↔`ties_v1`（已被历史清理做成硬链接）。
3. **`ollama list` 的 SIZE 与目录名义体积都不可相加。** 同一条铁律在两个地方成立：派生 tag 与孪生 tag 共享同一权重层；同名构件的多份硬链接路径各算一遍。全部数字改按簇去重后重算，D 盘 repo 独占 228.24 GB 而非 270.92 GB。

## 3. T1 的可再生证明（三方一致）

| GGUF | 独占 GB | D 侧 sha256 == manifest 权重层摘要 | E 盘 blob 实存 |
|---|---|---|---|
| `virtu-moe-14b-bf16.gguf` | 27.26 | ✅ `9f5c34f33f05a68a` | ✅ |
| `virtu-moe-14b-q4_k_m.gguf` | 8.32 | ✅ `a2103c68d9e881ac` | ✅ |
| `virtu-moe-14b-semantic-q4_k_m.gguf` | 8.32 | ✅ `0106872590e5b4fb` | ✅ |
| `virtu-dense-merged-q4_0.gguf` | 4.30 | ✅ `df83b71eeacef0a0` | ✅ |
| `virtu-dense-merged-v2-q4_0.gguf` | 4.30 | ✅ `97a7eb763837c37d` | ✅ |
| `virtu-dense-ties-q4_0.gguf` | 4.30 | ✅ `36f5d7bd63578bbf` | ✅ |
| `virtu-comprehensive-q4_0.gguf` | 4.30 | ✅ `c3b78c7735c9ac1f` | ✅ |

合计 61.10 GB。三者任一不成立即判红不删；还原是一条命令：
`python -u scripts/d_model_space_cleanup.py --restore <文件名>`（按 blob 拷回、校验 sha、目标已存在则拒绝覆盖）。

T2 的非损失依据：`virtu_eval/arms.json` 里 `dense_merged_v2` / `dense_merged_v2_p11435` 两条臂都是
`kind=ollama_native → model_id=virtu-dense-merged-v2:q4_0`，评测吃的是 E 盘 tag 而非 HF 目录；
配方也记在臂的 note（增强直接加法 + TIES trim，ffn_scale=0.5）与 `scripts/densify_virtu_to_dense.py`
的入参里，且 `checkpoints/_base_qwen3_8b` 与全部 adapter 保留 ⇒ 可重算。

## 4. 闸与反证

| 闸 | 判红条件 | 反证 |
|---|---|---|
| idle-gate | 进程表命中评测/训练命令行，或 `/api/ps` 非空；每步破坏前复查 | 另一会话起 `moe14b_gate_random` 时实测保持"hold"未落任何删除 |
| T1 三方一致 | sha ≠ manifest，或 blob 缺失 | `--selftest` 用无关 tag 摘要比对真实文件，必须不等 |
| T2 活引用 | 文档以外任何引用（含 arms.json 前缀标记） | `--selftest` 断言 `_base_qwen3_8b` 必须扫到引用，扫不到即判扫描器失效 |
| T3 搬迁 | 目标已存在（拒绝合并）；robocopy 后文件数或总字节不等（两份都留）；junction 回探失败 | 同 |
| 台账写入 | `PROVENANCE.json` 已有键被改动 ⇒ 判红（读前/读后全量排序比对） | 同 |
| 记账本体 | 硬链接簇自检：路径数必须等于 nlink，且"文件簇数 < 1000"直接判红 | 首版因 `CreateFileW.restype` 未声明返回全 0 簇，正是靠这条非空洞闸暴露 |

`python -u scripts/d_model_space_cleanup.py --selftest` 实测 **SELFTEST PASS (0 red)**。

## 5. 执行结果（2026-11-06 21:21 实测）

**T1+T2 已完成**：`--fast-verify --stop-before-t3`（unlink/rmtree 是元数据操作，不产生批量 IO，
故可在评测链占用磁盘时执行；替代空闲闸的是「派生 tag 必须仍在库」这道不变量闸）。

| 量 | 实测 |
|---|---|
| D: 可用 | **18.55 → 91.89 GB（回收 73.35 GB）** |
| E: 可用 | 60.48 GB（本轮未动） |
| 删除 | 7 个 GGUF（61.10 GB）+ `virtu_dense_merged_v2_hf`（19 文件 / 15.27 GB，不可再生） |
| 台账 | `PROVENANCE.json` 追加 `space_cleanup_2026_11_06`，verdict=`additive-ok`（23→24 键，已有键值全等），备份 `PROVENANCE.json.bak_20261106_2121` |
| 删除后完整性 | 7 个派生 tag 逐一验「已注册 + manifest 权重层摘要 → blob 实存」：**0 broken** |
| 回归 | `tests/test_moe14b_asset_gates.py tests/test_cloud_bundle.py tests/test_gguf_metadata.py` → **55 passed** |
| T1 与暂存硬链接重叠 | 0.00 GB（GGUF 未被 WPS 链接，回收量全额生效） |

**T3 待空闲窗口**：`virtu_v2_all90_merged` + `virtu_v3_all90_merged`（30.54 GB）改由后台排队执行，
空闲门 3 次×20 s 连续干净样本才动手，robocopy 进程降为 BelowNormal 优先级（单盘设备，
拷贝带宽会直接进别人计时腿的数字）。预计再回收 ~29.4 GB（其中 `virtu_v2_all90_merged` 有
1.16 GB 与 `.tmp.driveupload` 同簇，那部分只有等 WPS 释放链接才真正回落）。

## 6. 本轮我自己的三处错，都已改正并留痕

1. **口头预测"D→约 93 GB"是算错**：61.10+15.27+30.54=106.9，17.29 起算应为 ~124 GB 量级。
   最终只报 `GetDiskFreeSpaceExW` 实测差值（73.35 GB 为 T1+T2 段）。
2. **首版硬链接记账返回 0 个簇却"自检通过"**：`CreateFileW` 未声明 `restype`，64 位句柄被截成 32 位
   → 所有查询失败 → 空集 → 空真。补上"簇数 < 1000 直接判红 + 金丝雀簇必须正好 3 条路径"后才抓到。
   同一类静默零值还有一次：`robocopy /PRIORITY:LOW` 在本机 robocopy 上是非法参数（rc=16），
   加上 `/BYTES` 输出是整数（无小数点），我按 `\d+\.\d+` 匹配 ⇒ 全盘扫描报"全 0 GB"。
3. **闸逮到了我自己**：dry-run 写出的证据 JSON 提到构件名，被活引用扫描当成引用 ⇒ T2 判红、整轮中止
   （未误删任何东西，方向是对的）。修正为只排除 `benchmarks/d_model_space_cleanup/` 自家产物，
   代码/配置/脚本引用一律照判；`--selftest` 里保留"`_base_qwen3_8b` 必须能扫到引用"的反证，
   确保这不是把扫描器调瞎。
4. 另有一次假警报：我临时手写的一次性校验脚本猜错了 manifest 目录布局，把 `virtu-comprehensive:latest`
   报成未注册；改用工具自带的 glob 解析器复查 ⇒ 7/7 完好。临时探针必须与正式实现同路，否则量的是自己。
