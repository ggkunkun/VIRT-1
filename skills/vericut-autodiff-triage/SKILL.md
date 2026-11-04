---
name: vericut-autodiff-triage
description: VERICUT Auto-Diff 结论的证据审计——判"合格"之前先证明这张偏差图真的有东西可判：有效像素非零、三色占比自洽、绿色比例与像素重算一致、过切像素与结论不矛盾，并把碰撞日志与图像结论交叉核对。当调用 cadcam_vericut_simulate、cadcam_visual_inspect(task=autodiff_inspection)，或任何地方说"仿真通过"时使用。
metadata:
  version: "1.0.0"
  owner: "Virtu 自建（VERICUT 域 GitHub 只有仿真库与模板，无技能源）"
  tools: [cadcam_vericut_simulate, cadcam_visual_inspect, cadcam_desktop_gui]
  executor: scripts/triage_autodiff.py
  evidence: "四个夹具：健康绿图 ACCEPTED、全零像素图 INSUFFICIENT_EVIDENCE、有过切却判合格 STOP_AND_FIX、日志报碰撞而图像判零 STOP_AND_FIX"
---

# VERICUT Auto-Diff 分诊

## 执行
```
python skills/vericut-autodiff-triage/scripts/triage_autodiff.py --inspection-json <视觉返回.json> --sim-log <仿真日志.log> --json-out <报告.json>
```
退出码 0=可进入下一工序，1=停机整改，2=证据不足。

## 三色分诊（AGENTS.md §2E 的落地口径）
- 红 = 过切/碰撞 → 致命：`STOP_AND_FIX` / `REVIEW_GOUGE`，回改刀路或 Z 深，禁止"微调补偿"糊过去。
- 蓝 = 残料 → `ADD_SEMI_FINISHING`：加半精加工走刀，别指望精加工一刀吃干净。
- 绿 = 公差内 → 才允许 `AUTODIFF_ACCEPTED`。

## 硬规则（这一步才是本技能的价值）
- **空场不算绿**：有效像素为 0（截了空白窗口、图还没渲染、截错窗口）一律 `INSUFFICIENT_EVIDENCE`，绝不因为"没检测到红色"而判通过。
- 三类占比之和必须 ≈100%，绿色自报值必须与按像素重算一致，否则分类器口径不一致 → 阻断。
- 有红色像素却给出 PASS → 直接 `STOP_AND_FIX`（结论与证据打架时，以证据为准）。
- 日志/图像必须交叉核对：日志报碰撞而图像零过切，或日志含 error 而结论为通过 → 阻断，先查日志再查图。
- 仿真未收敛（`cadcam_vericut_simulate` 未给出完整日志、或 `check_collision` 未跑完）时，"没有报警"不等于"安全"。
- 截图只对自己启动的 PID 链取窗口，别拿用户开着的 VERICUT 窗口当证据（`cadcam_desktop_gui(action=capture, software=vericut)`）。

## 输出契约
`{checks[], escalations[]{code,detail,block}, totals{red,blue,green,machined}, log?, verdict}`，`verdict ∈ AUTODIFF_ACCEPTED / REVIEW_GOUGE / ADD_SEMI_FINISHING / STOP_AND_FIX / INSUFFICIENT_EVIDENCE`。只有 `AUTODIFF_ACCEPTED` 才允许流向 `cadcam_sscnc_control`。
