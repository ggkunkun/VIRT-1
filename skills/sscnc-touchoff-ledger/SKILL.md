---
name: sscnc-touchoff-ledger
description: 对刀台账算术复核——逐轴验 机座标 = 工件坐标系偏置 + 相对座标，抓符号写反、偏置缺项、无火花/接触确认、刀号重复、缺几何值、磨损量超限、未声明生效坐标系。当调用 cadcam_sscnc_control(calculate_offsets/find_window)、按 G54 对刀后、或循环启动(Cycle Start)之前使用。
metadata:
  version: "1.0.0"
  owner: "Virtu 自建（SSCNC 面板域 GitHub 无技能源）"
  tools: [cadcam_sscnc_control, cadcam_visual_inspect, cadcam_desktop_gui]
  executor: scripts/touchoff_ledger.py
  evidence: "5 个夹具：自洽台账 OK，反号偏置 TOUCH-SIGN-ERROR，重复刀号 TOUCH-DUP-TOOL，缺火花确认 TOUCH-NO-SPARK，磨损 1.8mm TOUCH-WEAR-LIMIT"
---

# 斯沃对刀台账闭环

## 执行
```
python skills/sscnc-touchoff-ledger/scripts/touchoff_ledger.py <台账.json> --wear-limit 0.5 --json-out <报告.json>
```
台账结构：`{active_wcs, axes{X,Y,Z:{machine,work}}, wcs[{no,axis,offset,spark_confirmed}], tools[{t,h,d,wear_h,wear_d}]}`。

## 判据
- `TOUCH-ARITH` / `TOUCH-SIGN-ERROR`：偏置必须等于 `machine − work`。数值恰好等于 `work − machine` 时单独判符号写反——这是面板对刀最典型、也最容易在 CRT 上看不出问题的错。
- `TOUCH-NO-SPARK`：MG 触点式对刀没有火花/接触确认记录，就不能认为该轴已对齐（AGENTS.md §2F 的"touch-off spark alignment"）。
- `TOUCH-NO-OFFSET` / `TOUCH-NO-ACTIVE-WCS`：某轴缺偏置、或没声明生效 G54 → 循环启动前必须阻断。
- `TOUCH-DUP-TOOL` / `TOUCH-MISSING-GEOM`：刀号重复或缺 H/D 几何，补偿号就会张冠李戴。
- `TOUCH-WEAR-LIMIT`：磨损超允许值应换刀，不能用磨损补偿把刀补数值吃掉——补偿掩盖会让下一件继续偏。

## 硬规则
- 面板读数必须来自 `cadcam_visual_inspect(task=cnc_screen_perception)` 对**自己启动的 SSCNC 实例**截图的识别结果，或 `cadcam_sscnc_control(calculate_offsets)` 的回读；两者都没有就写"未观测"，不许由程序注释反推座标。
- 区分 MACHINE / RELATIVE / ABSOLUTE 三种显示：只有 MACHINE 与 G54 偏置的差才等于工件座标，混用必错。
- 车床 U 轴是 X 的直径/半径增量，不能与 X 混记；`W` 同理。
- 台账不自洽时禁止 `Cycle Start`；改完台账要重跑本核验，不要凭肉眼再看一遍 CRT。
- 只回收本次自己启动的实例，别动用户开着的仿真窗口。

## 输出契约
`{active_wcs, axes_checked[], tools_checked, problems[]{code,detail,block}, verdict}`，`verdict ∈ TOUCHOFF_CONSISTENT / TOUCHOFF_INVALID / READ_FAILED`。
