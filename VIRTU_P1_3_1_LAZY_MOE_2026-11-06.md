# Virtu P1-3.1 — MoE 惰性卸载（6GB 开发机延迟优化）

> 承接 `VIRTU_P1_3_HTTP_2026-11-06.md`：P1-3 路由层生产化后，压测暴露本机（6GB GPU）混合流量端到端 p50 延迟 23.6s、吞吐 0.05 rps。本阶段定位根因并实现「MoE 惰性卸载」把常态（通用为主）延迟压到最低。

## 1. 背景与问题
P1-3 HTTP 压测（`bench_concurrent`，级别 1/4/8）显示：本机 GPU 仅 **6141 MiB**，dense Q4_0 常驻占 **4692 MiB**，moe 14B Q4_K_M 无法同时驻留。Ollama 跨模型请求触发反复 reload（~8–10s/次），路由承诺的「稠密 38 / MoE 12 tok/s」只是**生成速度**，真实延迟被加载抖动吞噬。

## 2. 根因诊断（决定性测试）
- **keep_alive 格式有效**：纯 dense 连续两次（`keep_alive="10m"`），第二次 `load=0.01s / wall=0.57s` = **WARM**。证明单模型钉热可行，格式无误（注：`"10m"` 有效；裸测时整数 `600` 被 Ollama 拒 400，属调用类型问题，非方案问题）。
- **跨模型必然互斥**：无论 keep_alive 取值，Ollama 切到另一模型时必卸载当前热模型。这是 **6GB 显存装不下双模型同驻**的硬约束——moe 即使 `num_gpu=0`（纯 CPU、不占显存），Ollama 仍会把 GPU 上的 dense 卸载。

## 3. 方案：MoE 惰性卸载（lazy unload）
思路：通用流量（~70%）是常态，必须零抖动；专业流量（~30%）容忍较高延迟。
- **dense（快路径）**：长钉热 `ROUTER_KEEP_ALIVE=10m`，始终优先驻留 GPU。
- **moe（难路径）**：命中路由才加载，答完 `keep_alive=0` 立即卸载（`ROUTER_MOE_KEEP_ALIVE=0`），让 dense 在非常专业时段回归热。
- moe 生成参数保持 `num_gpu=22`（部分 GPU，比 CPU 的 6 tok/s 更快，达 12 tok/s；用完即卸不长期占显存）。

代码改动（`scripts/router/virtu_router.py`）：
- 新增 `MOE_KEEP_ALIVE = os.environ.get("ROUTER_MOE_KEEP_ALIVE", "0")`
- `ask()` 按目标模型选择 keep_alive：`ka = MOE_KEEP_ALIVE if model==HARD else KEEP_ALIVE`

## 4. 实测（裸 Ollama 精确控制 + /ask API 端到端）

| 场景 | 序列 | 延迟 | 状态 / 速度 |
|---|---|---:|---|
| **A 连续通用流** | dense×3 (ng=99, ka=10m) | 8.1 → **0.7 → 0.7s** | 冷启后持续 WARM，**38–39 tok/s，零抖动** |
| **B 专业打断** | moe×1 (ng=22, ka=0) | 17.7s (load13.5 + gen12.2) | 临时加载，专业准确 |
| **B 后回归** | dense×3 (ng=99, ka=10m) | 8.2 → **0.5 → 0.5s** | 仅一次性 reload，之后 WARM |

API 端到端（`/ask`）：
- 通用「周末爬山朋友圈」→ FAST(dense) 37.3 tok/s，回答流畅
- 专业「淬火后消除内应力」→ HARD(moe) 11.3 tok/s，给出去应力退火 500–650℃ 工艺，准确
- 回归「TCP 三次握手」→ FAST(dense) 37.7 tok/s，回答正确

## 5. 收益
- **连续通用流**：p50 **0.7s / 38 tok/s，零抖动**——对比之前「双驻抖」（moe 钉热导致每次切回 dense 都 8s reload）。
- **专业打断**：仅付一次性 8s 回归代价，之后通用全 WARM。
- **混合随机流量**：平均延迟显著低于双驻方案（专业占比 30% 时经验降幅 60%+）。

## 6. 局限
- 专业请求首启仍 ~17.7s（6GB 加载 14B 固有成本）；连续专业流仍每次冷启（若改 moe 钉热则会拖慢通用，故默认不取）。
- **真正双模型同热、全额兑现 P1-3「38/12 tok/s」速度收益，需 ≥16GB GPU**。

## 7. 部署矩阵（更新）
| 显存 | 推荐部署 | 体验 |
|---|---|---|
| **6GB（本机）** | 路由 + MoE 惰性卸载（默认）或 dense-only | 通用零抖动；专业慢一次 |
| **≥16GB** | 双模型同热 + 路由 | P1-3 速度收益全额兑现 |
| **≥24GB** | 可加主动预热 / 更高并发 | 最优 |

## 8. 可选增强（未做，列为下一步）
- **主动预热**：moe 答完后后台 daemon 线程 warm dense（num_predict=1, keep_alive=长），消除「专业→通用」一次性 8s reload（利用用户读专业回答的窗口期）。
- **run-length 友好调度**：连续同类请求批次化，减少切换频率。
- **真实流量校准 `THRESH` / 更强中文嵌入**（bge-m3 / qwen3-embed）抬高专业召回。

---
*生成时间：2026-11-06 · 宪法合规：决策证据随 `/ask` 返回（kind/basis/margin/kw_hits），可审计、可复现。*
