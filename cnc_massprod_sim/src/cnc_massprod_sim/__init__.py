# -*- coding: utf-8 -*-
"""cnc_massprod_sim — 量产级数控加工仿真 Agent.

工作流（全部可证伪、逐段留证）：
  config → blank/allowance/clamp/safety → NC(三方言) → static audit
  → deterministic controller execution (逐块/逐帧) → 干涉/撞机扫描
  → 精度校验 → 节拍统计 → 量产保障(磨损/SPC/换产) → OPC UA → 报告

诚实边界（遵循《AGENTS.md》§8 测量宪法）：
  * 每个数值带 basis=measured / derived / asserted / unmeasured。
  * 控制器逻辑对齐 FANUC 0i / 840D sl / HNC-8 公开编程手册，
    由确定性解释器实测；不等于任何具体机床的现场标定结果。
  * 干涉为「刀尖+刀轴+刀具/刀柄圆柱」对夹具 KeepOut 盒体的逐帧几何实测，
    不是 VERICUT 逐布尔材料去除；现场仍须首件试切与 VERICUT Auto-Diff。
  * 良品率/Cpk 若基于仿真样本，basis=simulated，绝不冒充实测。
"""
from __future__ import annotations

__version__ = "1.0.0"
