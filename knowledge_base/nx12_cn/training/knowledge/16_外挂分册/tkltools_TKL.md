# 外挂分册：TKL 工具集（`tkltools`）

> 版本：**NX12.0-CN**　|　厂商目录：`YANGJEE/TKLTOOLS`
> 命令数：29（中文标签 29）
> 风险等级：**LOW**　|　证据：E1-MEDIA（GBK/UTF-8 嗅探解码，直接解析介质 .men；已按 NX12 版本目录过滤）
> **非 Siemens 官方功能**，输出时必须向用户明确标注为第三方外挂。

## 一、能力卡

- 菜单文件：2 个，已排除其它 NX 版本菜单 0 个
- 文件编码：{'gbk': 2}
- 菜单版本：{'120': 2}（NX12 应为 120）
- 动作形态：{'模块文件': 29}
- 硬编码绝对路径：0 处
- 环境变量依赖：0 处
- 跨外挂重名命令 ID：0 个（必须用复合键 `tkltools:<ID>`）

## 二、调用前的硬性检查

- ✅ 命令键必须用命名空间：`plugin_id:command_id`；裸 ID 会被判为歧义。

## 三、命令清单

### 动作类型：模块文件（29 条）

| 复合键 | 中文名 | 菜单 | ACTIONS | 快捷键 |
|---|---|---|---|---|
| `tkltools:CAM_AUTO_PROG_NAME` | 自动设置程序名 | JIAGONG | `NX10_DRAW.dll` | — |
| `tkltools:CAM_PARAM_SET` | 设置加工参数 | JIAGONG | `NX10_DRAW.dll` | — |
| `tkltools:CAM_POST` | 后处理程序单 | JIAGONG | `NX10_DRAW.dll` | — |
| `tkltools:CAM_PROGS` | 程序组 | JIAGONG | `NX10_DRAW.dll` | — |
| `tkltools:CAM_ZDX` | 隐藏同心圆 | JIAGONG | `NX10_DRAW.dll` | — |
| `tkltools:CAM_ZHU_CE` | 注册 | XXX | `NX10_DRAW.dll` | — |
| `tkltools:CSETCOLOR` | 圆上色 | JIAGONG | `NX10_DRAW.dll` | — |
| `tkltools:FONT_TEXT` | 单线字体 | JIAGONG | `NX10_DRAW.dll` | — |
| `tkltools:GUAN_YU` | 关于 | XXX | `NX10_DRAW.dll` | — |
| `tkltools:LISTTOOL` | 一键排刀 | JIAGONG | `NX10_DRAW.dll` | — |
| `tkltools:TOOLHEAD` | 设置或删除夹持器 | JIAGONG | `NX10_DRAW.dll` | — |
| `tkltools:TOOLLENGTH` | 报告最短刀长 | JIAGONG | `NX10_DRAW.dll` | — |
| `tkltools:TOOLPATHTOLINE` | 刀路转曲线 | JIAGONG | `NX10_DRAW.dll` | — |
| `tkltools:VOIDE` | 工具视频教程 | JIAGONG | `NX10_DRAW.dll` | — |
| `tkltools:YESTOOL` | 检查刀具转速MCS | JIAGONG | `NX10_DRAW.dll` | — |
| `tkltools:ZDCAM_CIN_PASS` | 内部粘贴 | JIAGONG | `NX10_DRAW.dll` | — |
| `tkltools:ZDCAM_COPY` | 复制 | JIAGONG | `NX10_DRAW.dll` | — |
| `tkltools:ZDCAM_CUT` | 剪切 | JIAGONG | `NX10_DRAW.dll` | — |
| `tkltools:ZDCAM_PASS` | 粘贴 | JIAGONG | `NX10_DRAW.dll` | — |
| `tkltools:ZDDELETE` | 删除 | JIAGONG | `NX10_DRAW.dll` | — |
| `tkltools:ZDDPITCHCUT` | 2D螺距轮廓 | lian_wang_gong_neng | `NX10_DRAW.dll` | — |
| `tkltools:ZDHIDE` | 隐藏 | JIAGONG | `NX10_DRAW.dll` | — |
| `tkltools:ZDMEASURE` | 测量距离 | JIAGONG | `NX10_DRAW.dll` | — |
| `tkltools:ZDMONEY` | 材料报价 | JIAGONG | `NX10_DRAW.dll` | — |
| `tkltools:ZDPATHEDIT1` | 修改刀路1 | lian_wang_gong_neng | `NX10_DRAW.dll` | — |
| `tkltools:ZDSETTOOLSUM` | 设置刀号 | JIAGONG | `NX10_DRAW.dll` | — |
| `tkltools:ZDSURVEYANG` | 测量角度 | JIAGONG | `NX10_DRAW.dll` | — |
| `tkltools:ZDUPDATE` | 检查更新 | XXX | `NX10_DRAW.dll` | — |
| `tkltools:ZD_MACH_DATA` | 加工数据库 | JIAGONG | `NX10_DRAW.dll` | — |

## 四、标准调用流程（Agent 必须按此执行）

1. `list_plugins()` 确认该外挂已注册、`version_ok_for_nx12=true`。
2. `search('<中文名>', plugin='tkltools')` 定位候选，拿到复合键。
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

