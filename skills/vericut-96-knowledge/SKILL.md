---
name: vericut-96-knowledge
description: VERICUT 9.6 全流程专属知识入口——从零基础操作到高级场景的完整能力支撑。当用户询问 VERICUT 9.6 的任何功能、界面入口、操作路径、参数含义与默认值、标准操作流程、报错排查、Auto-Diff/碰撞/结果异常、后处理匹配、多工序连续仿真、UG/Mastercam/PowerMILL 接口对接，或需要"怎么配置/怎么解决/默认值是多少/有没有快捷键"时使用。本技能路由到 knowledge_base/six_software/vericut/ 的完整知识体系，强制版本一致性与四段式可执行输出。
metadata:
  version: "1.0.0"
  owner: "Virtu 自建（VERICUT 9.6 专属知识体系）"
  tools: [cadcam_desktop_gui, cadcam_vericut_simulate, cadcam_visual_inspect]
  executor: "knowledge_base/six_software/vericut/knowledge_index.json"
  evidence: "E-V01~E-V15；官方 help96 交叉校验（version_consistency.md）"
  knowledge_base: "D:/Virtu模型/knowledge_base/six_software/vericut/"
  related_skill: "vericut-autodiff-triage"
---

# VERICUT 9.6 专属知识入口

## 何时用
凡是 VERICUT 9.6 相关的问题——操作、配置、仿真异常、结果异常、接口对接、高级场景——先经此技能路由，再按四段式输出。
**判定为其他 VERICUT 版本的功能 → 转 `version_consistency.md` 排除，不得当作 9.6 回答。**

## 知识库地图（先看索引，再读文档）
根目录：`D:/Virtu模型/knowledge_base/six_software/vericut/`
- `knowledge_index.json`：**机器可读路由表**（问题类别/场景 ID → 文档 → 章节 → 证据 ID），第一步先查它。
- `ui_reference.md`：需求1——全模块界面入口/操作路径/参数含义/默认值。
- `sop_library.md`：需求2——标准化操作流程（每步含操作节点/校验标准/注意事项）。
- `error_handbook.md`：需求2——报错与故障处理（现象/触发/排查/解决/验证）。
- `advanced_scenarios.md`：需求3——运动链/后处理优化/多工序/CAD-CAM 接口。
- `problem_kb.md`：需求4——五类问题的四段式应答协议与路由表。
- `version_consistency.md`：需求5——版本锚点/跨版本排除/交叉校验/输出前自检。
- 基础六件套：`README.md`/`modules.md`/`commands.md`/`file_formats.md`/`workflows.md`/`config.md`/`plugins.md`/`automation_api.md`/`module_inventory.json`/`evidence.md`。

## 路由（按问题类别）
| 类别 | 关键词 | 主读 |
| :-- | :-- | :-- |
| 操作类 | 怎么点/在哪/快捷键/界面/导出/保存/启动 | ui_reference + commands + sop_library |
| 配置类 | 参数/默认值/单位/刀具库/机床/控制/坐标系 | ui_reference + config + advanced_scenarios |
| 仿真异常类 | 不播放/卡死/碰撞/报错/无刀路/超程/批处理 | error_handbook + workflows + automation_api |
| 结果异常类 | Auto-Diff/过切/残料/全绿/体积/报告 | error_handbook + vericut-autodiff-triage 技能 |
| 接口对接类 | UG/NX/Mastercam/PowerMILL/接口/后处理/多工序 | advanced_scenarios + file_formats |

## 强制输出流程（每个回答四段式，可直接执行）
1. **现象描述**：复述现象 + 发生阶段（启动/配置/仿真/结果/接口）+ 取证项。
2. **原因定位**：可能原因按证据强度排序，引用 E-ID 与三态；跨版本问题转 `version_consistency.md`。
3. **分步解决**：编号步骤，一次改一个变量、可回退；引用 SOP/场景 ID。
4. **结果验证**：明确通过标准；未过则回到取证，不宣称完成。

## 硬规则（违反即阻断）
- **无证据不写**：关键断言带 E-ID 与 `[高]/[中]/[低]` 或三态 `verified-working / confirmed-negative / documented-not-probed`。
- **判死不翻案**：COM（`-2147221005`）、stdin IPC、UIA 深树、headless batch 全是 confirmed-negative（E-V02/E-V03）；解法是换 GUI+文件回读通道，不是改参数。
- **版本专属**：以 9.6 本机锚点为准（prefs=`cgtech_96_`、安装根 `E:\windows64`、主类 `com.cgtech.Vericut`、无 Play 快捷键）；官方滚动帮助仅作补充并按需降级（E-V14/E-V15）。
- **默认不臆造**：无来源的默认值写"依工程/以界面为准"。
- **安全门**：碰撞/过切必须排除——`parse_collision_log.is_safe==True` 且 Auto-Diff 三色自洽；**空场不算绿**，红=过切致命/蓝=残料加半精/绿=合格。结果异常类问题同时调用 `vericut-autodiff-triage` 技能审计图像与日志一致性。
- **许可隔离**：只描述功能与接口存在性，严禁触碰许可证/授权/激活机制。

## 输出前五门自检（advanced_scenarios.md §E / version_consistency.md §4）
版本门 → 证据门 → 安全门 → 许可门 → 通道门；五门全过才输出。

## 快速命令（本机 GUI+回读通道）
```
CMD: cmd /c E:\windows64\commands\vericut_agent.bat   # CGTECH_VCPROJECT 自动加载工程
播放: 鼠标点击 (1890,860)（1920×1080 基准，每次截图校准；无快捷键）
状态灯: (710,820) BUSY/READY 交替
复查: 点 (830,108) 存 .vcreview；几何导出 Apply (1576,451)
审计: CGTECH_TRANSACTION_LOG=Yes → %USERPROFILE%\cgtech_96_transaction.log
回读: parse_sim_log / parse_collision_log / read_vcreview / read_transaction_log
```
