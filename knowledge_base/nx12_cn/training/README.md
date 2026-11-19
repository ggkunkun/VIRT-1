# 中文版 NX 12.0 专项能力训练体系

> **唯一适配版本**：NX 12.0（本机介质 12.0.2.9，简体中文）
> **数据基准**：直接解析本机 NX 安装介质（measured），非模型记忆、非推断
> **生成时间**：2026-11-18
> **可证事实**：4424 条官方命令 / 128 个菜单文件 / 9 个按钮定义 / 128126 条中文翻译条目
> **外挂通道**：13 个第三方外挂 / 1639 条唯一命令 / 180 个跨外挂重名 ID

---

## 0. 先读这一节：能力边界与真实性声明

本体系把"已实测验证"和"待 GUI 实测"严格分开，**不虚构任何验收分数**：

| 类别 | 状态 | 依据 |
|---|---|---|
| 命令 ID / 中文名 / 菜单路径 / 快捷键 / 官方提示 | ✅ 已从介质提取并校验 | `.btn`/`.men`/`simpl_chinese` 翻译表，含源文件 SHA256 |
| 六级知识结构、13272 条测试用例 | ✅ 已生成，7/7 静态检查通过 | 见 `reports/verification_report.md` |
| 每功能点 ≥3 场景的 **GUI 实际执行** | ⏳ 未取证 | 当前为可执行用例，非已执行结果 |
| 四维验收 95 分合格线 | ⏳ 未达标 | 报告如实标 NOT_VERIFIED，无虚构分数 |
| 与 NX 10/1847/2000 的具体差异 | ⏳ 未取证 | 仅列核对清单，不臆造差异 |

**关于你附带的 `中文版NX12.0.exe`**：经核验为 4.24 MB 的 i386 控制台程序（含 COM 注册字符串），**不是 NX 12.0 安装包**（原版介质 4–6 GB），无法用于安装。真正的 NX 介质在本机 `D:\BaiduNetdiskDownload\NX 12.0.2.9\...`，许可证服务 `ugslmd.exe` 正在运行。

---

## 1. 目录结构

```
training/
├── README.md                         本文件（总览 + 使用说明）
├── catalog/
│   └── nx12_cn_full_catalog.json     全量命令目录 4424 条（唯一命名基准，含 evidence 字段）
├── knowledge/
│   ├── 01_草图绘制.md ... 15_其他与第三方外挂.md   六级知识库（15 模块）
│   ├── 16_外挂分册/                  第三方外挂命令分册（13 份 + 总索引）
│   └── _manifest.json                模块清单
├── plugins/
│   ├── ADAPTER_SPEC.md               ★ 外挂接入规范（适配/参数/兼容/差异）
│   ├── plugin_registry.json          外挂能力注册表（1639 条唯一命令）
│   └── plugin_router.py              外挂路由层（list/search/resolve/plan_call/doctor）
├── features/
│   ├── 01_快捷键体系.md              75 条快捷键（介质实测）+ 自定义规则
│   ├── 02_中文术语对照.md            2456 条中英对照
│   ├── 03_版本差异对照库.md          本版本可证事实 + 待核对清单
│   ├── 04_报错代码库.md              开放式登记表 + 取证方法（不编造代码）
│   └── 05_性能优化配置.md            官方入口 + 调优核对清单
├── tests/
│   ├── test_cases_all.json           13272 条用例（4424×3 场景）
│   └── README_测试用例集.md          用例索引与验收映射
├── reports/
│   ├── verification_report.md        验收报告（含四维状态与未验证披露）
│   └── verification_report.json      机器可读版
└── tools/
    ├── extract_full_catalog_v2.py    ① 全量提取器（重建目录）
    ├── build_knowledge_base.py       ② 六级知识库生成器
    ├── build_features.py             ③ 专属特性库生成器
    ├── build_test_cases.py           ④ 测试用例生成器
    ├── build_plugin_registry.py      ⑤ 外挂注册表生成器（GBK 解码 + 版本过滤）
    ├── build_plugin_knowledge.py     ⑥ 外挂分册生成器
    └── verify_and_report.py          ⑦ 验证器 + 报告生成器
```

## 2. 六级知识架构

每个模块文档严格采用：**模块 → 子模块 → 功能点 → 操作步骤 → 参数说明 → 注意事项**。

- 每个功能点带版本标签 `[NX12.0-CN]` 与证据等级 `[E1-MEDIA]` / `[E2-MENU]` / `[E3-UNTR]`。
- 操作步骤的菜单路径来自真实 `.men` 解析，快捷键来自 `.btn` 的 `ACCELERATOR`，官方说明来自翻译表原文。
- 无官方说明处显式标 `[待实测]`，不臆造参数默认值。

证据等级：
- **E1-MEDIA**（1675 条）：来自 `definitions_*.btn` + 官方中文翻译，可点名源文件。
- **E2-MENU**（1039 条）：仅出现在菜单定义中，有官方中文名。
- **E3-UNTR**（1710 条）：菜单中出现但无官方中文翻译，多为第三方外挂，需 GUI 复核显示名。

## 3. 复用与扩展（可复跑工具链）

按顺序在 `training/tools/` 下执行：

```bash
python extract_full_catalog_v2.py      # 从介质重建 catalog（换版本时改 --nx-root）
python build_knowledge_base.py         # 重建 knowledge/
python build_features.py               # 重建 features/
python build_test_cases.py             # 重建 tests/
python build_plugin_registry.py        # 重建外挂注册表（含 GBK 解码 + 版本过滤）
python build_plugin_knowledge.py       # 重建外挂分册
python verify_and_report.py            # 跑验证 + 出报告
```

扩展路径：
- **补 GUI 实测**：按 `tests/test_cases_all.json` 的 S1/S2/S3 执行，回填知识库 `[待实测]` 处，重跑验证器。
- **补报错代码**：按 `features/04_报错代码库.md` 的取证流程登记实测解法。
- **扩展到其它版本**：用其它版本介质生成同结构目录，与 `features/03_版本差异对照库.md` 逐项比对。

## 4. 给 AI Agent 的使用规则

1. 回答任何操作问题前，先确认用户环境为 NX 12.0；否则声明本知识不适用。
2. 输出步骤时引用知识库功能点的真实菜单路径与命令 ID；`[待实测]` 处必须如实告知用户需现场确认。
3. 步骤粒度：菜单逐层展开 → 点击项 → 对话框参数 → 确定/取消；快捷键优先给出。
4. 遇到报错，先查 `features/04_报错代码库.md`；无登记项时引导用户按取证流程提供日志，不编造解法。
5. 涉及第三方外挂（E3）命令时，明确标注"非 Siemens 官方功能"。

## 5. 第三方外挂通道（外挂 Agent）

外挂不是"被隔离的噪声"，而是可被 Agent 正确路由和调用的独立能力单元。详见 `plugins/ADAPTER_SPEC.md`。

**实测规模**：13 个外挂 / 1639 条唯一命令 / 1055 条带中文标签 / 180 个跨外挂重名 ID。

**四条硬约束**：

1. **命名空间**：一切外挂调用必须用 `plugin_id:command_id`（如 `yanxiu:YX_buyweb`）；裸短 ID 会判歧义。
2. **版本双过滤**：目录版本段（排除 NX4/6/10/11/1926/32bit）+ 菜单 `VERSION`（NX12 必须为 120）。
3. **编码嗅探**：外挂 `.men` 多为 GBK，按 utf-8→gbk→latin1 解码，否则中文标签全是乱码。
4. **计划先行**：`plan_call()` 返回 `callable=false` 时禁止执行，按 `blockers[].code` 处置。

**已知真实阻断（介质实测）**：

| 外挂 | 阻断类型 | 实测证据 |
|---|---|---|
| YSUG | 版本不兼容 + 路径断裂 | 2 个菜单 `VERSION 130`；304/304 绝对路径失效 |
| KASA | 版本不兼容 | 菜单全为 `VERSION 130`（NX13+） |
| 超凡 | 路径断裂 | 30/30 绝对路径失效 |
| MS 工具箱 | 环境变量缺失 | 69 条命令依赖未设置变量 |

**调用示例**：

```bash
python plugins/plugin_router.py list          # 能力卡
python plugins/plugin_router.py search 燕秀    # 检索
python plugins/plugin_router.py plan yanxiu:YX_buyweb   # 调用计划
python plugins/plugin_router.py doctor        # 健康检查
```

**官方中国包辨析**：`LOCALIZATION/prc`（GC Toolkit：齿轮/弹簧/部件加密/制图）是 Siemens 官方本地化功能，**不是第三方外挂**，走内置通道，不套用外挂的参数未验证规则。
