# 第三方外挂 Agent 接入规范（ADAPTER SPEC）

> 适用：**NX 12.0 简体中文 / 12.0.2.9 介质**
> 数据基准：`plugins/plugin_registry.json`（从介质 GBK 解码实测，非推断）
> 实测规模：**13 个外挂 / 2779 条命令 / 2194 条带中文标签 / 180 个跨外挂重名 ID**

---

## 0. 术语与边界

| 概念 | 定义 | 处理通道 |
|---|---|---|
| **内置 Agent** | NX 官方功能（UG_/MW_/TOOLING_ 前缀），含 `LOCALIZATION/prc` 官方中国包 GC Toolkit | 官方通道，按训练知识库 01–15 分册 |
| **外挂 Agent** | 第三方插件被封装成的可调用能力单元，如 `ysug`、`yanxiu`、`ms_nxtools` | 外挂通道，本文档 + `plugin_router.py` |
| **外挂命令键** | `plugin_id:command_id`（如 `yanxiu:YX_buyweb`） | **唯一合法调用标识** |

> ⚠️ 关键辨析：`LOCALIZATION/prc` 是 **Siemens 官方中国包**（齿轮建模/弹簧/部件加密/制图工具，附官方 PDF 手册），走官方翻译表，**不是第三方外挂**。误判会导致参数规则用错。

---

## 1. 适配方式（五层）

### 1.1 目录层：按 NX 版本切分，禁止全量加载

外挂普遍按 NX 版本分目录：`NX4.0 / NX6.0 / NX10.0 / NX11.0 / NX12.0 / NX1926 / NX64 / 32bit / 64bit`。

- **规则**：只加载路径含 `NX12` 的目录 + 无版本段的通用目录；其余整段排除。
- **实测效果**：未过滤时 YSUG 采到 2604 条命令，过滤后 **1272 条**（排除 1524 条其它版本菜单）。
- **后果**：全量加载会把 NX10/NX13 的菜单塞进 NX12，表现为菜单错乱、命令点了没反应、或 NX 启动即报菜单解析错误。

### 1.2 编码层：GBK/UTF-8 嗅探

外挂 `.men` 的中文 LABEL **不是 UTF-8**：

| 外挂 | 实测编码 |
|---|---|
| YSUG / KASA / 燕秀 / 美雷 / LXH / GH / 超凡 / QuickCAM / TKL / 金雨 | `gbk` |
| LM 插件 / 古月 / MS 工具箱 | `utf-8` |

- **规则**：按 `utf-8 → gbk → latin1` 顺序嗅探解码，并以"是否解出中文"作为校验。
- **后果**：用 ASCII/UTF-8 硬读，中文标签会变成 `��������`，Agent 就无法按中文识别外挂命令——这是外挂识别失败的头号原因。

### 1.3 命名层：复合键命名空间

外挂按钮 ID 常为 `1`、`2`、`FEED`、`YS`、`dir` 这类极短串，**跨外挂重名 180 个**（YSUG 与 KASA 共享同一套命令，因 KASA 装在 `YANGJEE/YSUG/Kasa` 下）。

- **规则**：一切对外暴露的标识必须用 `plugin_id:command_id`；裸 ID 一律判歧义。
- **示例**：`guanyuhaoq` → 歧义（`ysug:guanyuhaoq` 与 `kasa:guanyuhaoq` 都存在）；必须显式指定。

### 1.4 能力层：注册表 → 能力卡

`plugin_router.list_plugins()` 返回能力卡，字段含 `command_count / zh_commands / risk_level / version_ok_for_nx12 / actions_profile`。Agent 先看能力卡再决定是否加载，避免把不可用外挂推荐给用户。

### 1.5 调用层：计划先行，阻断即停

`plan_call(key)` 返回 `callable / blockers / warnings / preconditions / param_contract`：

- `callable=false` → **禁止执行**，按 `blockers[].code` 处置；
- `callable=true` → 满足 `preconditions` 后在 GUI 执行；
- 执行通道固定为 **NX GUI 交互**（外挂无官方 COM/批处理接口）。

---

## 2. 参数约定

### 2.1 调用签名

```python
plan_call(
    key: str,                      # "plugin_id:command_id"，必填
    params: dict | None = None     # 见 2.2，未实测时传 None
) -> dict
```

### 2.2 params 三层结构

```json
{
  "inputs":      { "字段语义键": "值" },   // 对应对话框控件，需实测确认字段名
  "selection":   ["对象引用"],             // 预选集；外挂多为交互式 GRIP，选中状态依赖 GUI
  "dialog_mode": "gui"                     // 默认 gui；仅有 .utd/.dlg 的命令可能支持 batch
}
```

### 2.3 参数状态规则（硬约束）

- 外挂 `.men` **只定义菜单与 ACTIONS，不含参数默认值、取值范围、单位**；
- 因此 `param_contract.verified` 默认 `false`，**Agent 不得向用户承诺任何具体参数值**；
- 传了 `params` 会触发 `PARAM_UNVERIFIED` 警告——可以执行，但必须告知用户"参数未实测"；
- 参数取证后才可把 `verified` 置 `true`，并把字段快照回填外挂分册。

### 2.4 选择集与坐标系

- 选择集按 NX 选择意图（特征/面/边/体）传递，外挂常直接吃当前选择；
- 坐标系沿用 WCS；外挂若内部固定 ABS，需在调用前提示用户切换；
- 单位统一 mm / 度（NX 12 中文版默认），外挂不做单位换算，禁止混用英寸。

---

## 3. 兼容处理

| 兼容问题 | 判定方式 | 处理策略 | 实测证据 |
|---|---|---|---|
| **版本不匹配** | 菜单 `VERSION != 120` | 阻断，提示该外挂为其它 NX 版本编写 | YSUG 2 个、KASA 全部为 `VERSION 130` |
| **目录版本污染** | 路径含非 NX12 版本段 | 加载时整段排除 | 已排除 1524 个菜单文件 |
| **编码错乱** | 解码后中文变乱码 | 按 utf-8→gbk→latin1 嗅探 | 11 个外挂为 GBK |
| **硬编码路径失效** | ACTIONS 为 `X:\...` 且文件不存在 | 阻断 + 提示重装/改路径 | YSUG 304/304 断、超凡 30/30 断 |
| **环境变量缺失** | ACTIONS 含 `%VAR%`/`${VAR}` 且未设置 | 阻断 + 列出缺失变量 | MS 工具箱 69 条、YSUG 8 个变量 |
| **命令重名** | 裸 ID 命中多个外挂 | 要求复合键 | 180 个 ID 重名 |
| **外挂未安装** | 目录不存在 | 不注册该能力，不向用户推荐 | `doctor().installed` |
| **菜单被卸载/未加载** | 目录在但 NX 菜单无该项 | 提示检查外挂加载配置与 NX 启动日志 | 需 GUI 复核 |
| **外挂间共享命令** | YSUG 与 KASA 同源 | 优先按用户所装外挂路由，不跨外挂混用 | `ysug:*` 与 `kasa:*` 成对出现 |

> 健康检查入口：`python plugins/plugin_router.py doctor`
> 当前实测：13/13 已安装、11/13 版本兼容、2 个外挂存在断路径、2 个存在缺失环境变量。

---

## 4. 外挂 Agent 与内置 Agent 的差异

### 4.1 能力差异

| 维度 | 内置 Agent（官方） | 外挂 Agent（第三方） |
|---|---|---|
| 功能文档 | 官方中文翻译表 + 消息文本，可溯源 | 仅菜单 LABEL/MESSAGE，多数无说明 |
| 参数默认值 | 可从对话框与官方资料获得 | **介质中不存在，必须 GUI 实测** |
| 自动化接口 | NXOpen/COM/批处理（部分） | **基本只有 GUI 交互**，靠 GRIP/.grx/.dll |
| 功能稳定性 | 随版本受控 | 随外挂作者更新，菜单可能重排 |
| 版本适配 | 版本内自洽 | 需按目录/`VERSION` 双重过滤 |
| 命令标识 | 长 ID，全局唯一 | 短 ID，跨外挂重名 |

### 4.2 调用流程差异

| 步骤 | 内置 Agent | 外挂 Agent |
|---|---|---|
| 1 识别 | 直接查 4424 条官方目录 | 查外挂注册表，先看能力卡 |
| 2 定位 | 命令 ID 精确匹配 | 中文/英文/ID 检索 + **必须带命名空间** |
| 3 前置检查 | 版本标签即可 | 版本 + 编码 + 路径 + 环境变量 + 重名 **五查** |
| 4 执行 | 菜单/快捷键，可直接给步骤 | 固定 GUI 交互，禁止承诺批处理 |
| 5 参数 | 可给默认值与范围 | 只能给字段清单，标 `[待实测]` |
| 6 回退 | `Ctrl+Z` 撤消 | 撤消 + **文件级备份**（写文件类外挂可能绕过撤消栈） |

### 4.3 异常处理差异

| 异常类型 | 内置 Agent | 外挂 Agent |
|---|---|---|
| 错误来源 | NX 错误码、特征报错 | 路径/环境/版本/编码/歧义五类 |
| 错误码体系 | NX 原生错误码 | `PluginError.code` 稳定枚举（见下表） |
| 处置方式 | 查报错库，按特征修复 | 按 code 分支：能修则修，不能修则明确告知不可用 |
| 失败兜底 | 撤消重做 | 撤消 + 还原备份 + 建议改走官方等效命令 |

**外挂异常码（`PluginError.code`）**

| code | 含义 | Agent 应做什么 |
|---|---|---|
| `PLUGIN_NOT_INSTALLED` | 外挂目录缺失 | 告知未安装，不推荐该能力 |
| `PLUGIN_VERSION_INCOMPATIBLE` | 菜单 `VERSION≠120` | 阻断，说明为其它 NX 版本编写 |
| `COMMAND_NOT_FOUND` | 命令不在该外挂 | 用 `search()` 重新检索 |
| `AMBIGUOUS_COMMAND` | 跨外挂重名 | 要求用户指定外挂，改用复合键 |
| `ACTION_PATH_BROKEN` | 绝对路径不存在 | 提示按原路径重装或修正配置 |
| `ENV_VAR_UNSET` | 环境变量未设置 | 列出变量名，提示 NX 启动前设置 |
| `OFFICIAL_ALIAS` | 实为转发官方命令 | 转官方通道获取准确参数 |
| `PARAM_UNVERIFIED` | 参数未实测 | 执行但明确告知结果不保证 |
| `REGISTRY_MISSING` | 注册表缺失 | 先跑 `build_plugin_registry.py` |

---

## 5. 注意事项（Agent 硬规则）

1. **必须标注来源**：外挂输出统一前缀 `[第三方外挂] 外挂名 › 命令名`，禁止与官方命令混述。
2. **不得裸用短 ID**：任何 `1`/`2`/`FEED` 类 ID 必须补 `plugin_id:` 前缀。
3. **不得承诺未实测参数**：外挂参数一律 `[待实测]`，除非已完成 GUI 取证。
4. **不得声称支持批处理**：除非该命令 ACTIONS 指向 `.utd/.dlg` 且经实测。
5. **阻断即停**：`callable=false` 时不执行、不"试试看"，直接按 code 回复。
6. **写文件前必须提示备份**：外挂可绕过 NX 撤消栈。
7. **版本漂移**：外挂升级或换机后必须重跑 `build_plugin_registry.py` + `doctor`，旧键可能失效。
8. **官方中国包走官方通道**：`LOCALIZATION/prc` 不套用本文档的参数未验证规则。
9. **不跨外挂混用**：YSUG 与 KASA 同源，按用户实际安装的那个路由。
10. **许可与合规**：外挂为第三方软件，商用前提示用户确认授权，Agent 不代为判断合法性。

---

## 6. 最小接入示例

```python
import plugin_router as r

# 1) 看有哪些外挂
for card in r.list_plugins():
    print(card["plugin_id"], card["display_name"], card["command_count"], card["risk_level"])

# 2) 检索并定位（必须带 plugin_id）
hits = r.search("燕秀", plugin="yanxiu")

# 3) 生成调用计划
plan = r.plan_call("yanxiu:YX_buyweb")
if not plan["callable"]:
    for b in plan["blockers"]:
        print("阻断:", b["code"], b["detail"])
else:
    print("按菜单执行:", plan["menu_path"])

# 4) 健康检查
print(r.doctor()["summary"])
```

CLI 等价：

```bash
python plugins/plugin_router.py list
python plugins/plugin_router.py search 燕秀
python plugins/plugin_router.py plan yanxiu:YX_buyweb
python plugins/plugin_router.py doctor
```

---

## 7. 接入验收清单

- [ ] 外挂注册表已生成，`totals.plugins=13`、`totals.commands=2779`
- [ ] 每个外挂 `men_files` 只含 NX12/通用目录，`excluded_men_files` 已记录
- [ ] 中文标签可读（非乱码），`zh_commands` 与分册一致
- [ ] 裸 ID 解析返回 `AMBIGUOUS_COMMAND` 或 `COMMAND_NOT_FOUND`，不误命中
- [ ] `doctor` 输出断路径/缺环境变量清单，且与实际部署一致
- [ ] `VERSION≠120` 的外挂被标记阻断（当前 YSUG、KASA）
- [ ] 外挂分册 13 份齐全，`_总索引.md` 可跳转
- [ ] 回复模板含 `[第三方外挂]` 前缀
