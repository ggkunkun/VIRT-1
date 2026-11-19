# 外挂分册：超凡工具 ChaoFan（`chaofan`）

> 版本：**NX12.0-CN**　|　厂商目录：`YANGJEE/ChaoFan`
> 命令数：32（中文标签 30）
> 风险等级：**HIGH**　|　证据：E1-MEDIA（GBK/UTF-8 嗅探解码，直接解析介质 .men；已按 NX12 版本目录过滤）
> **非 Siemens 官方功能**，输出时必须向用户明确标注为第三方外挂。

## 一、能力卡

- 菜单文件：1 个，已排除其它 NX 版本菜单 0 个
- 文件编码：{'gbk': 1}
- 菜单版本：{'120': 1}（NX12 应为 120）
- 动作形态：{'绝对路径': 30, '无ACTIONS': 2}
- 硬编码绝对路径：30 处，示例：`D:\ChaoFan\Application\About.grx`
- 环境变量依赖：0 处
- 跨外挂重名命令 ID：0 个（必须用复合键 `chaofan:<ID>`）

## 二、调用前的硬性检查

- ⚠️ **路径绑定**：ACTIONS 为绝对路径，外挂未装在原路径则调用失败；上线前用 `plugin_router.py doctor` 核对。

- ✅ 命令键必须用命名空间：`plugin_id:command_id`；裸 ID 会被判为歧义。

## 三、命令清单

### 动作类型：绝对路径（30 条）

| 复合键 | 中文名 | 菜单 | ACTIONS | 快捷键 |
|---|---|---|---|---|
| `chaofan:About_CF` | 关于.... | CF_MOULD | `D:\ChaoFan\Application\About.grx` | — |
| `chaofan:CF_AddNote` | 快速颜色 | cf_DrawTool | `D:\ChaoFan\DLL\FaceColor_X64.dll` | — |
| `chaofan:CF_AddTolerance` | 添加公差 | cf_DrawTool | `D:\ChaoFan\Application\Tolerance.grx` | — |
| `chaofan:CF_Color117` | 凸模偏面加大 + 0.05 | CF_COLOR | `D:\ChaoFan\Application\color117.grx` | — |
| `chaofan:CF_Color123` | 型面偏移面缩小 - 0.1 | CF_COLOR | `D:\ChaoFan\Application\color123.grx` | — |
| `chaofan:CF_Color160` | 细牙孔颜色 | CF_COLOR | `D:\ChaoFan\Application\color160.grx` | — |
| `chaofan:CF_Color162` | 浮升销孔浮块孔面 | CF_COLOR | `D:\ChaoFan\Application\color162.grx` | — |
| `chaofan:CF_Color186` | 导套孔滑配面 | CF_COLOR | `D:\ChaoFan\Application\color186.grx` | — |
| `chaofan:CF_ForceCal` | 中心线 | CF_SOLID | `D:\ChaoFan\Application\CenterLine1.grx` | — |
| `chaofan:CF_MianHuanYuan` | 无组件自动出图 | CF_TouMing | `D:\ChaoFan\GRX\Daotu.grx` | — |
| `chaofan:CF_MianTou` | 面透明 | CF_TouMing | `D:\ChaoFan\Application\SetTranslucencyFace.grx` | — |
| `chaofan:CF_QD10` | M10起吊螺丝 | cf_QiDiaoLuoSi | `D:\ChaoFan\Application\M10_QiDiaoLuoSi.grx` | — |
| `chaofan:CF_QD12` | M12起吊螺丝 | cf_QiDiaoLuoSi | `D:\ChaoFan\Application\M12_QiDiaoLuoSi.grx` | — |
| `chaofan:CF_QD16` | M16起吊螺丝 | cf_QiDiaoLuoSi | `D:\ChaoFan\Application\M16_QiDiaoLuoSi.grx` | — |
| `chaofan:CF_QD20` | M20起吊螺丝 | cf_QiDiaoLuoSi | `D:\ChaoFan\Application\M20_QiDiaoLuoSi.grx` | — |
| `chaofan:CF_QD8` | M8起吊螺丝 | cf_QiDiaoLuoSi | `D:\ChaoFan\Application\M8_QiDiaoLuoSi.grx` | — |
| `chaofan:CF_ShiTou` | 实体透明 | CF_TouMing | `D:\ChaoFan\Application\SetTranslucencySolid.grx` | — |
| `chaofan:CF_ShiTouHuanYuan` | 实体透明还原 | CF_TouMing | `D:\ChaoFan\Application\SetTranslucencySolidOld.grx` | — |
| `chaofan:CF_translucency` | 透明/不透明（新） | CF_TouMing | `D:\ChaoFan\Application\translucency.dll` | — |
| `chaofan:CN_DRAFT_MERGE_SHEET_BTN` | 组件批量转PDF | cf_Draw1 | `D:\ChaoFan\GRX\asm2pdf.grx` | — |
| `chaofan:Cf_Regist` | 软件注册.... | CF_MOULD | `D:\ChaoFan\Application\regist.grx` | — |
| `chaofan:Color100` | 高度准 - 绿色 | CF_COLOR | `D:\ChaoFan\Application\color100.grx` | — |
| `chaofan:Color14` | 产品型面精锣 | CF_COLOR | `D:\ChaoFan\Application\color14.grx` | — |
| `chaofan:Color211` | 避位粗加工面 | CF_COLOR | `D:\ChaoFan\Application\color211.grx` | — |
| `chaofan:Color31` | 慢割-紧配面、销孔、基本准孔，导柱孔 | CF_COLOR | `D:\ChaoFan\Application\color31.grx` | — |
| `chaofan:Color6` | 改模 - 黄色 | CF_COLOR | `D:\ChaoFan\Application\color6.grx` | — |
| `chaofan:Color78` | 型面R角避空 | CF_COLOR | `D:\ChaoFan\Application\color78.grx` | — |
| `chaofan:ColorHelp` | 颜色说明 | CF_COLOR | `D:\ChaoFan\Application\ColorHelp.grx` | — |
| `chaofan:PDW_CUT_POCKET` | 一键删除重合对象 | CF_SOLID | `D:\ChaoFan\Application\DeleteDuplicateObj.dll` | — |
| `chaofan:SetColor` | 快速颜色设置 | CF_COLOR | `D:\ChaoFan\GRX\SetColor.grx` | — |

### 动作类型：无ACTIONS（2 条）

| 复合键 | 中文名 | 菜单 | ACTIONS | 快捷键 |
|---|---|---|---|---|
| `chaofan:PDW_TOOLS_BOX` | Create Box | CF_SOLID | `—` | — |
| `chaofan:PDW_TOOLS_STOCK_SIZE` | PDW_TOOLS_STOCK_SIZE | CF_SOLID | `—` | — |

## 四、标准调用流程（Agent 必须按此执行）

1. `list_plugins()` 确认该外挂已注册、`version_ok_for_nx12=true`。
2. `search('<中文名>', plugin='chaofan')` 定位候选，拿到复合键。
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

