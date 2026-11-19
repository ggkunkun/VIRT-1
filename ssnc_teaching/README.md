# 斯沃数控仿真软件（SSCNC 7.2.2.0）全流程教学体系与能力构建

> 交付版本 v1.0　|　适用软件 SSCNC 7.2.2.0　|　交付日期 2026-11-18
> 本体系所有软件操作描述均基于**本机真实实测**与**软件自带官方资料**，凡一手资料未覆盖者均显式标注，不虚构。

---

## 一、交付物导航

| 册 | 文档 | 内容 | 行数 |
| --- | --- | --- | --- |
| 00 | `docs/00_软件认知安装与版本手册.md` | 软件识别、真实路径、安装激活、37系统清单、版本管理规范 | 179 |
| 01 | `docs/01_核心模块全覆盖教学.md` | 7大核心模块：系统选择/坐标系/刀具/程序/仿真/干涉观察/精度校验 | 830 |
| 02 | `docs/02_全场景实操与标准化SOP.md` | 铣削+车削全流程、SOP手册、最优方案决策 | 923 |
| 03 | `docs/03_报警异常故障库与FAQ.md` | 159条官方报警速查、30条深度解析、软件异常、48条FAQ | 1222 |
| 04 | `docs/04_测试用例集与能力考核.md` | 134用例说明、L1-L4分阶段考核、验收现状（诚实口径） | 418 |

**一手资料与证据**
- `SOURCE_INDEX.md` — 唯一资料索引（所有写作依据）
- `evidence/menu_structure_measured.json` — Win32 API 实测的 9 大菜单全结构
- `evidence/sscnc_main.png` 等 — 真实软件界面截图
- `source/chm_cn/` — 官方中文帮助反编译（5826 文件：251 htm + 3600 jpg + 1553 gif）
- `source/help_kb_md/` — 253 主题结构化知识库（69.8 万字）+ `_index.json`
- `source/alarms_fanuc_extracted.json` — 159 条官方 FANUC 报警编号→含义

**测试与工具链**
- `tests/sscnc_testcases.jsonl` — 134 个测试用例（10 大类）
- `tests/answer_key.json` — 答案键（分布 A34/B34/C33/D33）
- `scripts/` — 提取/截图/校验/判分/自检脚本（全部可复跑）

---

## 二、一手证据基础（本体系的"真实性"来源）

| 证据 | 获取方式 | 结果 |
| --- | --- | --- |
| 软件实体 | 解析桌面快捷方式 + 全盘定位 | 真实路径 `E:\仿真软件\2斯沃7.2（内含安装说明）\SSCNC\CNCLogin.exe`（快捷方式指向的 `E:\SSCNC\` 已失效） |
| 版本 | 安装说明 + general.ini | SSCNC 7.2.2.0，CNC=37 |
| 真实运行 | 启动 + 进程/窗口枚举 + 截图 | 1×CNCLogin + 多×sscnc；主窗口类 `ClassName_Swansoft_CNC_Simulation`；实测加载 MITSUBISHI M80 |
| 菜单结构 | Win32 GetMenu/GetSubMenu API | 9 大菜单全部子项（实测，最高优先级依据） |
| 官方功能 | CHM 反编译（hh.exe -decompile） | 295 标题 / 253 主题 / 69.8 万字 / 5000+ 官方截图 |
| 报警库 | GBK 解析 fanuc_alarmlist_cn.ini | 308 编号，159 条中文含义 |
| 官方示例 | 官方 SAMPLES 目录 | FANUC/SIEMENS/华中/广数等成套 .cnc 程序与工程配置 |

---

## 三、验收状态（诚实口径）

用户提出的 5 项质量要求，本体系的完成状态：

| # | 要求 | 状态 | 说明 |
| --- | --- | --- | --- |
| 1 | 核心模块全覆盖、与实际版本 100% 匹配 | ✅ 已交付 | 7 模块齐全；菜单/坐标/G代码等核心描述有实测+官方双重依据；无独立"碰撞检测"按钮已如实说明 |
| 2 | 全场景实操、异常复现验证有效 | 🟡 部分交付 | 铣削/车削全流程 SOP 已交付；报警含义来自官方库，**但逐条触发复现尚未在软件中完成** |
| 3 | 标准化规范体系、可复用 SOP | ✅ 已交付 | 分步指引、参数标准、避坑要点、校验节点、失败回退齐备 |
| 4 | 可落地输出物、能力考核 | 🟡 部分交付 | 文档+FAQ+134 用例+判分工具链已交付；**真实软件操作考核待执行** |
| 5 | 100+ 用例、≥98% 通过、版本标注 | 🟡 待验证 | 134 用例（>100）✅；版本标注 ✅；**98% 准确率当前未宣称达成**——检索式自检基线为 87.3%（近似方法，不等同准确率） |

> **诚实红线**：本体系已建成"教学文档 + 证据 + 用例 + 判分工具链"，但"98% 准确率"与"报警逐条复现"属于必须在真实软件操作 + 人工评审下才能确认的验收项，本次**不宣称已达成**。详见 `docs/04` 第四部分。

---

## 四、复跑与验证命令

在 `D:\Virtu模型` 目录下：

```bash
# 重新提取官方帮助知识库
python ssnc_teaching/scripts/extract_help_kb.py

# 生成并重排测试用例
python ssnc_teaching/scripts/gen_testcases.py
python ssnc_teaching/scripts/rebalance_options.py

# 校验用例一致性
python ssnc_teaching/scripts/validate_testcases.py

# 运行检索式覆盖自检（真实基线约 87.3%，已排除考核文档污染）
python ssnc_teaching/scripts/run_self_assessment.py

# 校验文档路径引用
python ssnc_teaching/scripts/validate_refs2.py

# 软件截图取证（需软件已启动）
python ssnc_teaching/scripts/capture_sscnc.py
```

---

## 五、版本与迭代

- 文档版本：v1.0；软件版本：SSCNC 7.2.2.0
- 软件升级后：须重新实测枚举菜单、核对 CHM，再升版文档
- 各分册末尾均含"事实核查清单"与"修订记录"
