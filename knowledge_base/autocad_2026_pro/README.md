# AutoCAD 2026 简体中文正式版 · 全功能专业能力体系

> 构建日期：2026-11-18　|　目标软件：AutoCAD 2026 简体中文正式版（内部版本 **R25.1**，语言 **chs / zh-CN**）
> 主程序：`D:\cad2026\AutoCAD 2026\acad.exe`（启动参数 `/product ACAD /language "zh-CN"`）

本目录是为智能体构建的、可被实时查询的 AutoCAD 2026 简体中文全功能知识体系。它覆盖你要求的全部 15 类功能模块（并扩展至 18 个模块），命令数据 100% 来自随正式版安装的官方一手数据源与 Autodesk 官网，不含第三方教程或旧版本推断。

---

## 一、权威数据源（唯一来源，可核验）

| 数据源 | 具体位置 | 提取内容 |
| :--- | :--- | :--- |
| 官方简体中文界面定义 CUIX | `D:\cad2026\AutoCAD 2026\UserDataCache\zh-cn\Support\acad.CUIX` | 1937 个命令实体的中文名、命令宏、菜单路径、功能区路径、帮助说明、43 个快捷键 |
| 官方命令别名表 acad.pgp | `C:\Users\Administrator\AppData\Roaming\Autodesk\AutoCAD 2026\R25.1\chs\Support\acad.pgp` | 322 条命令别名 |
| 官方命令参考 CHM | `D:\cad2026\AutoCAD 2026\Help\AdRefMan.chm` | 外部参照等专题命令参考 |
| Autodesk 官网 2026 功能页 | `https://www.autodesk.com.cn/products/autocad/features` | 2026 版本专属新功能清单 |

**版本一致性铁证**：配置路径中的 `R25.1` = AutoCAD 2026 内部版本，`chs` = 简体中文；桌面快捷方式启动参数 `/language "zh-CN"` 交叉印证。所有中文命令名、别名、快捷键均以此为基准，杜绝版本混淆与中英文界面差异。

---

## 二、交付内容

| 文件 | 内容 | 规模 |
| :--- | :--- | :--- |
| `SKILL.md` | 智能体能力入口（autocad-2026-zh-proficiency），含权威数据源、模块清单、强制工作流、边界原则 | — |
| `command_index.json` | 命令主库：877 条唯一命令的四维度信息 + 410 条别名反查索引 | 524 KB |
| `modules_knowledge_base.json` | 18 个功能模块全覆盖，每模块命令含命令路径/菜单路径/右键选项/局限性 | 793 KB |
| `command_function_scene_map.json` | 命令-功能-场景映射库 | 417 KB |
| `features_2026.json` | 2026 专属新特性 17 项（含官方命令与调用方式说明） | 8 KB |
| `industry_workflows.json` | 机械/建筑/土木/室内 4 领域工作流 + 10 项故障排查 + 效率优化 + 模板配置 | 9 KB |
| `query_engine.py` | 智能体查询引擎，本地检索，响应 <60ms | 9 KB |
| `validation/validate.py` | 三轮交叉验证脚本（可复跑） | 10 KB |
| `validation/validation_report.json` | 三轮验证实测报告 | — |

### 18 个功能模块（无遗漏）

1. 初始界面布局与自定义配置　2. 命令行交互机制与语法规范　3. 二维基础绘图工具集
4. 图形编辑与修改功能体系　5. 专业标注与注释体系　6. 图层与特性管理系统
7. 块与属性定义　8. 动态块创建与编辑　9. 外部参照与光栅图像管理
10. 布局空间与页面设置　11. 批量打印与发布　12. 三维基础与高级建模
13. 参数化设计与约束管理　14. 数据提取与属性导出　15. 图纸集管理
16. 选择集与查询工具　17. 实用工具与系统管理　18. AutoCAD 2026 专属新增功能

### 每个命令记录的四维度

中文名 / 命令行别名 / 默认快捷键 / 命令行输入格式 / 命令宏路径 / 菜单路径 / 功能区路径 / 右键菜单选项 / 功能说明（帮助原文）/ 局限性说明 / 官方来源标注。

---

## 三、三轮交叉验证结果（真实实测，可复跑）

```
python "D:\Virtu模型\knowledge_base\autocad_2026_pro\validation\validate.py"
```

| 轮次 | 校验内容 | 结果 |
| :--- | :--- | :--- |
| 第一轮 | 全命令库匹配：877 条命令的中文名/别名/菜单路径逐一比对官方 CUIX + acad.pgp | **877/877 = 100%** |
| 第二轮 | 100+ 个典型行业任务端到端交付（命令/别名/场景/工作流） | **108/108 = 100%** |
| 第三轮 | 2026 版本专属特性：来源官方性 + 命令在官方库存在性 + 版本标识一致性 | **32/32 = 100%** |
| 响应延迟 | 查询引擎本地检索 | 平均 **1.0 ms**，最大 **45.7 ms**（< 1 秒要求） |

### 验证过程中发现并修正的真实问题（诚实记录）

首轮验证时第三轮仅 61.3%、第二轮 96.3%。根因：初版 `features_2026.json` 中部分命令名是按官网功能描述**推断**的，未出现在实际安装的 R25.1 官方命令表中。逐一回查官方数据后修正为真实命令：

- `BLOCKPLACE`/`BLOCKREPLACE`（推断）→ 官方块替换命令实为 **`BREPLACE`**；智能块放置通过功能区上下文调用，无独立命令。
- `MATERIAL` → **`MATERIALS`**（材质浏览器）
- `AUTOCONSTRAINT` → **`AUTOCONSTRAIN`**（自动约束）
- `ACTIVITYINSIGHTS` → **`ACTIVITYINSIGHTSOPEN`**（活动见解）
- `MAPWORKSPACE` → **`GEOMAP`**（地图类型）
- `MARKUPASSIST` → **`MARKUPIMPORT`** / `MARKUP`
- `VLIDE`（旧称）→ **`VLISP`**（Visual LISP 编辑器）

对确认无独立命令行命令的功能（如智能块检测、Autodesk 助手、我的见解），在 `command_note` 中如实标注"通过功能区/界面调用"，而非编造命令。修正后三轮均达 100%。

---

## 四、使用方法

```bash
cd "D:\Virtu模型\knowledge_base\autocad_2026_pro"
python query_engine.py LINE             # 命令完整四维度信息
python query_engine.py DLI              # 别名反查 → DIMLINEAR
python query_engine.py "标注直径"        # 场景问答 → DIMDIAMETER 等
python query_engine.py --scene 机械      # 机械行业工作流与国标配置
python query_engine.py --fix "文字乱码"  # 故障排查：现象→原因→处置
python query_engine.py --new            # 2026 新特性清单
```

智能体在加载 `SKILL.md` 后，可依据其中的强制工作流，对上述知识库做实时检索与问答，无需重新学习。

---

## 五、边界与诚实声明

1. 命令数据范围是**随本正式版安装 + Autodesk 官方发布**的功能；第三方插件/Express 扩展不作为内置能力声称。
2. 标注的"局限性"来自官方功能边界与行业已知约束；对无法从官方数据确认的参数细节，明确提示"以软件实际提示为准"。
3. "100%" 的含义是：**在本知识库覆盖范围内、相对上述官方数据源的匹配通过率**，并通过可复跑脚本验证；它不代表对 AutoCAD 全部隐式行为的绝对穷尽。
4. 命令行输入为英文命令（AutoCAD 命令行不识别中文命令名），中文名为界面显示名——二者在知识库中分别记录，不可混用。
