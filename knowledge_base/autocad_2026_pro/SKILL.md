---
name: autocad-2026-zh-proficiency
description: AutoCAD 2026 简体中文正式版（内部版本 R25.1）全功能专业知识体系。当用户咨询 AutoCAD 2026 的中文命令、别名、快捷键、命令行格式、参数选项、菜单/功能区/右键路径、功能局限、二维绘图、标注、图层、块与动态块、外部参照、布局打印、三维建模、参数化约束、数据提取、图纸集、2026 新增特性（智能块/活动见解/我的见解/Autodesk 助手/标记导入/跟踪/计数等），或需要机械/建筑/土木/室内行业绘图工作流、故障排查、效率优化、模板配置时使用。数据源为随软件安装的官方简体中文 CUIX 界面定义、官方 acad.pgp 命令别名表与 Autodesk 官网 2026 功能说明，确保版本精确、中文界面一致。
---

# AutoCAD 2026 简体中文专业能力与知识体系

> 本 Skill 是 AutoCAD 2026 简体中文正式版（内部版本 **R25.1**，语言 **chs/zh-CN**）的可查询能力体系。
> 全部命令数据来自随正式版安装的**官方权威一手数据源**，非第三方教程、非旧版本推断。

## 1. 权威数据源（唯一来源）

| 数据源 | 路径 / 位置 | 用途 |
| :--- | :--- | :--- |
| 官方简体中文界面定义 | `D:\cad2026\AutoCAD 2026\UserDataCache\zh-cn\Support\acad.CUIX` | 中文命令名、命令宏、菜单路径、功能区路径、快捷键、帮助说明（1937 实体） |
| 官方命令别名表 | `C:\Users\Administrator\AppData\Roaming\Autodesk\AutoCAD 2026\R25.1\chs\Support\acad.pgp` | 322 条命令别名（A→ARC、L→LINE、CO→COPY 等） |
| 官方命令参考 CHM | `D:\cad2026\AutoCAD 2026\Help\AdRefMan.chm` | 外部参照等专题命令参考 |
| Autodesk 官网 2026 功能 | `https://www.autodesk.com.cn/products/autocad/features` | 2026 版本专属新增功能清单 |

**版本一致性铁证**：配置目录 `R25.1\chs` = AutoCAD 2026（R25.1）+ 简体中文（chs）；快捷方式启动参数 `/product ACAD /language "zh-CN"`。查询时不得混用其他版本或英文界面习惯。

## 2. 知识库文件

- `command_index.json` — 命令主库（877 条唯一命令，含中文名/别名/快捷键/命令行格式/菜单路径/功能区路径/命令宏/右键选项/局限性）+ 410 条别名反查索引。
- `modules_knowledge_base.json` — 18 个功能模块的全覆盖命令体系（每模块含四维度信息）。
- `command_function_scene_map.json` — 命令-功能-场景映射库（1214 条）。
- `features_2026.json` — 2026 版本专属新特性（17 项，含命令）。
- `industry_workflows.json` — 机械/建筑/土木/室内四大行业工作流、故障排查（10 项）、效率优化、模板配置。
- `query_engine.py` — 智能体查询引擎（本地检索，单次响应 <60ms）。

## 3. 18 个功能模块（无遗漏全覆盖）

初始界面布局与自定义配置 · 命令行交互机制与语法规范 · 二维基础绘图工具集 · 图形编辑与修改功能体系 · 专业标注与注释体系 · 图层与特性管理系统 · 块与属性定义 · 动态块创建与编辑 · 外部参照与光栅图像管理 · 布局空间与页面设置 · 批量打印与发布 · 三维基础与高级建模 · 参数化设计与约束管理 · 数据提取与属性导出 · 图纸集管理 · 选择集与查询工具 · 实用工具与系统管理 · AutoCAD 2026 专属新增功能。

## 4. 查询引擎用法（响应 <1 秒）

```bash
cd "D:\Virtu模型\knowledge_base\autocad_2026_pro"
python query_engine.py LINE            # 命令四维度信息
python query_engine.py DLI             # 别名反查 -> DIMLINEAR
python query_engine.py "标注直径"       # 场景问答 -> DIMDIAMETER 等
python query_engine.py --scene 机械     # 行业工作流
python query_engine.py --fix "文字乱码"  # 故障排查
python query_engine.py --new            # 2026 新特性
```

## 5. 强制工作流（回答 AutoCAD 2026 咨询时）

1. **命令/别名/快捷键类**：先查 `command_index.json`，返回中文名 + 命令 + 别名 + 快捷键 + 输入格式 + 菜单/功能区路径 + 局限性。不确定时明说，不得编造。
2. **操作步骤类**：查对应模块 `modules_knowledge_base.json` 的四维度信息 + `industry_workflows.json` 的标准流程，按国内行业习惯（GB/T）给出可执行步骤。
3. **版本特性类**：只依据 `features_2026.json`（Autodesk 官网）；明确区分"全新/增强/技术预览"，不得把其他版本特性安到 2026。
4. **故障排查类**：查 `industry_workflows.json` 的 troubleshooting，给出"现象→原因→处置"闭环。
5. **中文界面一致性**：命令名一律用官方简体中文名（如"直线/圆/复制/线性标注"），命令行输入为英文命令（AutoCAD 命令行不识别中文命令名），二者必须区分清楚。

## 6. 边界与诚实原则

- 仅覆盖随正式版安装 + Autodesk 官方发布的功能；非官方插件（如第三方 Express 扩展）不作为内置能力声称。
- 局限性说明基于官方功能边界与行业已知约束；对无法从官方数据确认的参数细节，明确标注"需以软件实际提示为准"。
- 准确率与 100% 覆盖率的实测证据见同目录 `validation/` 下的三轮验证报告。
