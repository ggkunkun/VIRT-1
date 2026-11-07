# Virtu Foundation Model x Hindsight Memory Report

> **Architecture**: Vectorize Hindsight (arXiv:2512.12818)
> **Generated**: 2026-10-29 17:27:02
> **Total Banks**: 4 | **Total Units**: 10

## 1. Banks Overview

| Bank ID | Description | Units |
| :--- | :--- | :--- |
| `default` | Default general memory bank for cross-task engineering context | 0 |
| `virtu_cad_cam` | 3D parametric CAD modeling, equations, and FeatureTree rules | 5 |
| `virtu_cnc_machining` | CNC toolpaths, G-code cycles, feeds/speeds, and machine dynamics | 4 |
| `virtu_quality_audit` | Geometric tolerances, GD&T, safety guardrails, and collision audits | 1 |

## 2. Sample Memory Units by Type

### Bank: `virtu_cad_cam`
- **[WORLD_FACTS]** (`MEM_VIRT_0003_6022`): SS304 奥氏体不锈钢密度 7.93g/cm3，抗拉强度 >= 520MPa，粗加工线速度推荐 90-140 m/min，易加工硬化，切削液需充分供应。
  - *Entities*: `SS304`
- **[MENTAL_MODELS]** (`MEM_VIRT_0004_6022`): SOLIDWORKS 2021 VBA 宏中方程式管理器添加变量时，双引号必须双重转义，例如 swEqnMgr.AddEquation 0, "\"D_Outer\" = 110.0"，以防运行时异常 13。
  - *Entities*: `SOLIDWORKS`
- **[AGENT_EXPERIENCES]** (`MEM_VIRT_0005_6022`): 自动化精密法兰套筒 3D CAD 原生特征树建立完成：包含基准面、草图旋转凸台、退刀槽切除与方程式关联，ForceRebuild3 刷新无几何报错。
  - *Entities*: `ForceRebuild3`

### Bank: `virtu_cnc_machining`
- **[WORLD_FACTS]** (`MEM_VIRT_0002_6022`): Ti-6Al-4V 钛合金热导率极低，粗车切速必须严格控制在 35-55 m/min，精车 60-80 m/min，必须配备耐热涂层硬质合金刀具与高压内冷 M08。
  - *Entities*: `Ti-6Al-4V`
- **[MENTAL_MODELS]** (`MEM_VIRT_0003_6022`): CIMCO FANUC Macro B 宏程序中，G71 粗车循环第二行中的 U 为单边径向余量，而轮廓起止 X 坐标为直径编程，必须留足 0.4mm 余量供 G70 精修。
  - *Entities*: `Macro B, FANUC, G71, CIMCO, G70`
- **[AGENT_EXPERIENCES]** (`MEM_VIRT_0004_6022`): 完成轴承外套圈 G71 复合循环数控车削仿真：主轴转速 S1800，进给 F0.15，对刀仪 G54 校准无误，Vericut 刀路无碰撞无干涉过切。
  - *Entities*: `G71, G54, Vericut`

### Bank: `virtu_quality_audit`
- **[MENTAL_MODELS]** (`MEM_VIRT_0001_6022`): 回转体内外孔壁厚底线强制护栏：(d_outer - d_inner)/2 必须 >= 2.0mm，严禁薄壁加工振刀与开裂变形。
