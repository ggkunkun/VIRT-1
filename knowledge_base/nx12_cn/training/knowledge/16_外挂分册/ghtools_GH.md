# 外挂分册：GH 工具（`ghtools`）

> 版本：**NX12.0-CN**　|　厂商目录：`YANGJEE/GHTOOLS`
> 命令数：14（中文标签 14）
> 风险等级：**LOW**　|　证据：E1-MEDIA（GBK/UTF-8 嗅探解码，直接解析介质 .men；已按 NX12 版本目录过滤）
> **非 Siemens 官方功能**，输出时必须向用户明确标注为第三方外挂。

## 一、能力卡

- 菜单文件：1 个，已排除其它 NX 版本菜单 1 个
- 文件编码：{'gbk': 1}
- 菜单版本：{'120': 1}（NX12 应为 120）
- 动作形态：{'其他': 14}
- 硬编码绝对路径：0 处
- 环境变量依赖：0 处
- 跨外挂重名命令 ID：0 个（必须用复合键 `ghtools:<ID>`）

## 二、调用前的硬性检查

- ✅ 命令键必须用命名空间：`plugin_id:command_id`；裸 ID 会被判为歧义。

## 三、命令清单

### 动作类型：其他（14 条）

| 复合键 | 中文名 | 菜单 | ACTIONS | 快捷键 |
|---|---|---|---|---|
| `ghtools:Straighten_workpiece` | 摆正工件 | NU2 | `GHTOOLS` | — |
| `ghtools:ghaotocam` | 自动编程 | NU2 | `GHTOOLS` | — |
| `ghtools:mcsgroup` | 坐标程序分组 | NU2 | `GHTOOLS` | — |
| `ghtools:ncedit` | 刀轨编缉 | NU2 | `GHTOOLS` | — |
| `ghtools:ncgcard` | 程序单后处理 | NU2 | `GHTOOLS` | — |
| `ghtools:ncgroup` | 程序组 | NU2 | `GHTOOLS` | — |
| `ghtools:ncnum` | 改刀号 | NU2 | `GHTOOLS` | — |
| `ghtools:openncdir` | 打开NC文件夹 | NU1 | `GHTOOLS` | — |
| `ghtools:openpartdir` | 打开部件文件夹 | NU1 | `GHTOOLS` | — |
| `ghtools:operpram` | 工序参数 | NU2 | `GHTOOLS` | — |
| `ghtools:print` | 输出PDF并打印 | NU2 | `GHTOOLS` | — |
| `ghtools:set` | 系统设置 | NU2 | `GHTOOLS` | — |
| `ghtools:setmcs` | 加工坐标 | NU2 | `GHTOOLS` | — |
| `ghtools:speed` | 转速进给 | NU2 | `GHTOOLS` | — |

## 四、标准调用流程（Agent 必须按此执行）

1. `list_plugins()` 确认该外挂已注册、`version_ok_for_nx12=true`。
2. `search('<中文名>', plugin='ghtools')` 定位候选，拿到复合键。
3. `plan_call(key)` 取调用计划；**`callable=false` 时禁止执行**，按 `blockers` 的 code 处置。
4. 检查 `preconditions` 全部满足；参数按 `param_contract` 组织，未实测字段不得编造。
5. 在 NX GUI 中按 `menu_path` 逐层展开并点击命令；外挂无 COM/批处理，只能交互执行。
6. 结果核验：几何/文件是否按预期变化；失败时先 Ctrl+Z，再按错误码上报。

## 五、参数说明

- 外挂 `.men` 只定义菜单与 ACTIONS，**不含参数默认值/取值范围**。
- 因此本分册所有命令的参数状态为 `[待实测]`；Agent 不得向用户承诺具体参数值。
- 需在 NX 12 中文界面打开该命令对话框后，按 `param_contract.schema` 回填并复跑验证。

## 六、注意事项

- 该外挂与其它外挂共享 0 个短 ID，禁止省略命名空间。
- 外挂升级后菜单可能重排，命令键以本注册表（介质实测）为准，升级后需重跑 `build_plugin_registry.py`。
- 外挂写文件、批量改属性等操作可能绕过 NX 撤消栈，执行前必须提示用户备份。
- 回复用户时按此格式标注：`[第三方外挂] {外挂名} › {命令名}`，不得与官方命令混述。

