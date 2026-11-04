---
name: fanuc-macro-b-post-gate
description: 用本仓执行器对 FANUC Macro B 数控程序做上机前的静态安全闸——G21/G20 下固定循环 Q/P/R 的单位、分布圆极坐标被重复换算、声明却未参与的宏变量、孔深对不上被加工段厚度、G96 缺 G50 钳制、模态(冷却/主轴/固定循环)未复位、WHILE-DO-END 配对、白名单外未知指令。当模型准备调用 cadcam_cimco_validate、改写 .nc/.mpf/.ptp 程序、或由 CAM 后处理产出 G 代码时使用。判"无阻断"只放行进仿真，绝不放行进切削。
metadata:
  version: "1.0.0"
  owner: "Virtu 自建（GitHub 无该域可落位技能源，2026-11-04 检索证实）"
  tools: [cadcam_cimco_validate, cadcam_extreme_chain, cadcam_run_full_chain]
  executor: scripts/validate_nc.py
  evidence: "对 Flange_Machining_O1001.nc 复现 5 类实质缺陷(8 条阻断)；对同题修正副本判 0 阻断"
---

# FANUC Macro B 后处理安全闸

## 什么时候用
任何"程序要上机"的判断点：CAM 后处理产出、手写宏程序、`cadcam_cimco_validate(action=validate_macro)` 之前先跑本闸，之后再用 CIMCO 视窗复核。

## 执行
```
python skills/fanuc-macro-b-post-gate/scripts/validate_nc.py <程序.nc> --json-out <报告.json>
```
退出码 0=无阻断项，1=有阻断项，2=程序不可解析。报告含 `findings[](line,code,severity,issue,fix)`、`blocker_codes`、`verdict`。

## 判据（每条都是可复算的，不是风格偏好）
- `NC-Q-UNIT` / `NC-R-PLANE`：G21 米制下 Q/R/P 按 mm 解析。`Q5000` 在米制是 5000 mm 啄深——固定循环直接退化为一次全深走刀，排屑与扭矩都不成立。英寸制写法搬进米制模板是本仓最常见的致命错。
- `NC-POLAR`：C 轴已经给了极角，X 又（直接或经宏变量传递）把同一变量的 COS 乘进去 —— 角度被算了两次。实测 6 孔分布圆的 X 直径序列会是 `125/62.5/-62.5/-125/...`，θ=90° 时 X=0，钻头落在主轴中心线。正确写法：X 固定为分布圆直径，只有 C 变角度。执行器会做宏变量依赖闭包，所以 `#123=[..*COS[#120]]` 再 `X[#123*2.0] C#120` 也照样抓到。
- `NC-DEAD-VAR`：赋了值却从不进入任何运动/补偿字的宏变量（如孔径 #102、盘厚 #103、螺栓径 #108），意味着图纸上那个尺寸根本没被加工。宁可阻断，也不能让它被读成"已做"。
- `NC-DEPTH-MISMATCH`：钻孔段 Z 深引用总长变量、而程序同时声明了更小的段厚变量 → 多走 (总长−段厚) mm 进夹持侧。必须按图确认穿透段。
- `NC-ENVELOPE` / `NC-NO-STOCK`：所有 X/Z 目标必须落在毛坯包络内；程序没声明 `BLANK: D.. x L..` 时直接阻断，不许跳过行程校验。
- `NC-G50-MISSING`：G96 恒线速没有 G50 上限，直径趋小时转速飞升。
- `NC-MODAL-*`：M08 未 M09、主轴未 M05、固定循环未 G80 取消、换刀未回参考点。
- `NC-UNKNOWN-CMD`：白名单外的 G/M 一律阻断 —— 未知指令不许臆测语义。

## 硬规则
- 本闸只证明"静态文本层无已知致命模式"，不证明刀路安全、不证明尺寸合格。放行去向只能是仿真/试切，不能是切削。
- 缺机床型号、控制器代次、刀具表、后处理身份时，按 `nc-static-safety-review` 的口径直接判 `REVIEW_REQUIRED`，不要用默认值补齐。
- `IF[..]THEN` 一类可移植性告警必须先在斯沃面板 AUTO 回放确认，再谈实机。
- 不许为了让闸通过而删除参数或改写注释；改的是运动本身。

## 输出契约
`{program, sha? , lines, units, stock_envelope, findings[], counts{FATAL,BLOCKING,WARN}, blocker_codes[], verdict}`。任何 `blocker_codes` 非空 → 回 CAD/后处理环节，不得进入 `cadcam_vericut_simulate`。
