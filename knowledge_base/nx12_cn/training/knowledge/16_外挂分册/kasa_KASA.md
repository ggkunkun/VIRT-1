# 外挂分册：KASA 工具（`kasa`）

> 版本：**NX12.0-CN**　|　厂商目录：`YANGJEE/YSUG/Kasa`
> 命令数：60（中文标签 60）
> 风险等级：**HIGH**　|　证据：E1-MEDIA（GBK/UTF-8 嗅探解码，直接解析介质 .men；已按 NX12 版本目录过滤）
> **非 Siemens 官方功能**，输出时必须向用户明确标注为第三方外挂。

## 一、能力卡

- 菜单文件：1 个，已排除其它 NX 版本菜单 2 个
- 文件编码：{'gbk': 1}
- 菜单版本：{'130': 1}（NX12 应为 120）
- 动作形态：{'模块文件': 60}
- 硬编码绝对路径：0 处
- 环境变量依赖：0 处
- 跨外挂重名命令 ID：60 个（必须用复合键 `kasa:<ID>`）

## 二、调用前的硬性检查

- ⛔ **版本不兼容**：以下菜单 `VERSION != 120`，NX12 下可能不加载：

  - `YANGJEE/YSUG/Kasa/64bit/startup/Kas.men`

- ✅ 命令键必须用命名空间：`plugin_id:command_id`；裸 ID 会被判为歧义。

## 三、命令清单

### 动作类型：模块文件（60 条）

| 复合键 | 中文名 | 菜单 | ACTIONS | 快捷键 |
|---|---|---|---|---|
| `kasa:3264` | 8.位数匹配检测 | K_XGGJ | `3264.grx` | — |
| `kasa:3views` | 2.零件三视图 | K_BCFZ | `3view.grx` | — |
| `kasa:BATCHPOST5` | 1.NC批处理 | K_BCFZ | `Batch_Post.dll` | — |
| `kasa:BODYCOLORS` | 3.实体着色 | K_MXZL | `BodyColor.grx` | — |
| `kasa:BodyMass` | 4.干涉检查 | K_JCSC | `Intfer1.5.grx` | — |
| `kasa:ClearGroup` | 24.图层清理 | K_MXZL | `ClearGroup.grx` | — |
| `kasa:Comp_rename` | 7.装配改名 | K_MXZL | `CompRename.utd` | — |
| `kasa:Cursor_circle` | 1.动态圆圈 | K_JCSC | `Cursor_Circle.dll` | — |
| `kasa:FACEANGLE` | 2.报告斜度 | K_JCSC | `FaceAngle.grx` | — |
| `kasa:GenSave` | 5.计算刀路并关机 | K_BCFZ | `GenSave.dll` | — |
| `kasa:INCH2M` | 1.公英制转换 | K_XGGJ | `Inch2M.grx` | — |
| `kasa:KROTATE` | 6.零件旋转 | K_MXZL | `rotate.grx` | — |
| `kasa:K_Bear` | 15.熊族看看 | K_BCFZ | `K_Bear.grx` | — |
| `kasa:K_Calc` | 6.计算器 | K_XGGJ | `K_Calc.grx` | — |
| `kasa:K_Chajiao` | 12.插角辅助几何 | K_BCFZ | `Chajiao.utd` | — |
| `kasa:K_Moon` | 7.月光宝盒 | K_XGGJ | `K_moon.grx` | — |
| `kasa:K_OpRemarkAtt` | 3.程序单备注 | K_BCFZ | `K_OpRemarkAtt.grx` | — |
| `kasa:K_PATH2CURVE` | 14.刀路转曲线 | K_BCFZ | `K_path2curve.grx` | — |
| `kasa:K_Paralist` | 11.查看程序参数 | K_BCFZ | `Para_list.dll` | — |
| `kasa:K_Rcolor` | 4.R角着色 | K_MXZL | `Color_R.grx` | — |
| `kasa:K_Scallop` | 16.步距计算 | K_BCFZ | `K_Scallop.grx` | — |
| `kasa:K_Snap` | 5.截图工具 | K_XGGJ | `K_Snap.grx` | — |
| `kasa:K_ToTop` | 11.三花聚顶 | K_MXZL | `K_ToTop.grx` | — |
| `kasa:K_ToolAction` | 13.刀具位置验证 | K_BCFZ | `ToolAction.grx` | — |
| `kasa:K_Zcolor` | 5.Z平面着色 | K_MXZL | `Color_Z.grx` | — |
| `kasa:K_export` | 5.导出部件 | K_JCSC | `K_export.grx` | — |
| `kasa:K_geom_set` | 10.批量更换坐标系 | K_BCFZ | `geom_set.dll` | — |
| `kasa:K_partnumber` | 4.标记编号 | K_SJFZ | `PartNumber.grx` | — |
| `kasa:K_shop` | 4.NC程序单 | K_BCFZ | `K_shop2.60.grx` | — |
| `kasa:K_stockset` | 7.批量修改程序参数 | K_BCFZ | `Stock_set.dll` | — |
| `kasa:K_toolchange` | 9.批量更换刀具 | K_BCFZ | `ToolChange.dll` | — |
| `kasa:K_toolnumber` | 8.批量修改刀号 | K_BCFZ | `K_ToolNum.grx` | — |
| `kasa:K_trans` | 10.增量复制 | K_MXZL | `K_trans.grx` | — |
| `kasa:Kcylinderline` | 15.两点圆柱 | K_MXZL | `2p-cylinder.grx` | — |
| `kasa:LayerNames` | 8.图层工具 | K_MXZL | `Layer.utd` | — |
| `kasa:NCPROG5` | 6.NC程序组 | K_BCFZ | `Prog_Edit.dll` | — |
| `kasa:Openprtdir` | 2.文件路径 | K_XGGJ | `Open_Prt_Dir.grx` | — |
| `kasa:PartBackup` | 3.文件备份 | K_XGGJ | `beifen.grx` | — |
| `kasa:Remove_Para` | 1.删除参数 | K_MXZL | `Remove_Parameters.dll` | — |
| `kasa:SETTRANSL` | 2.设置透明 | K_MXZL | `Set_translucency.grx` | — |
| `kasa:Sizeinfor` | 8.尺寸盒子 | K_JCSC | `Sizeinfor.grx` | — |
| `kasa:TransFace55` | 16.斗转星移 | K_MXZL | `TransFace.dll` | — |
| `kasa:attbom` | 3.零件BOM | K_SJFZ | `K_bom.grx` | — |
| `kasa:atttools` | 2.属性工具 | K_SJFZ | `att.utd` | — |
| `kasa:booleansubtract` | 19.多对多布尔减 | K_MXZL | `Subtract.grx` | — |
| `kasa:color_circle` | 22.圆圈染色 | K_MXZL | `color_circle.grx` | — |
| `kasa:createtext` | 20.刻字 | K_MXZL | `kz.grx` | — |
| `kasa:cylinder245` | 12.孔柱工具 | K_MXZL | `cylinder.grx` | — |
| `kasa:guanyuhaoq` | 6.更多more... | KASA | `guanyu.grx` | — |
| `kasa:hebing` | 4.多文件合并 | K_XGGJ | `hebing.grx` | — |
| `kasa:inline5` | 9.排料工具 | K_MXZL | `in_line.grx` | — |
| `kasa:isocrv` | 13.曲面中线 | K_MXZL | `isocrv.grx` | — |
| `kasa:offset5` | 17.批量偏置面 | K_MXZL | `Offset_face.dll` | — |
| `kasa:protocolor` | 21.穿透染色 | K_MXZL | `ProtoColor.grx` | — |
| `kasa:pt_rect` | 23.中心点矩形 | K_MXZL | `Pt_Rect.grx` | — |
| `kasa:replacefaces1` | 18.批量替换面 | K_MXZL | `Replace_face.dll` | — |
| `kasa:standpart5` | 1.标准零件 | K_SJFZ | `standard_v2.60.grx` | — |
| `kasa:tolerplus` | 9.添加公差 | K_JCSC | `tolerplus.grx` | — |
| `kasa:ug2dxf` | 7.图纸转DXF | K_JCSC | `UG2DXF.dll` | — |
| `kasa:xyzzuobiao` | 6.xyz坐标 | K_JCSC | `xyz.grx` | — |

## 四、标准调用流程（Agent 必须按此执行）

1. `list_plugins()` 确认该外挂已注册、`version_ok_for_nx12=true`。
2. `search('<中文名>', plugin='kasa')` 定位候选，拿到复合键。
3. `plan_call(key)` 取调用计划；**`callable=false` 时禁止执行**，按 `blockers` 的 code 处置。
4. 检查 `preconditions` 全部满足；参数按 `param_contract` 组织，未实测字段不得编造。
5. 在 NX GUI 中按 `menu_path` 逐层展开并点击命令；外挂无 COM/批处理，只能交互执行。
6. 结果核验：几何/文件是否按预期变化；失败时先 Ctrl+Z，再按错误码上报。

## 五、参数说明

- 外挂 `.men` 只定义菜单与 ACTIONS，**不含参数默认值/取值范围**。
- 因此本分册所有命令的参数状态为 `[待实测]`；Agent 不得向用户承诺具体参数值。
- 需在 NX 12 中文界面打开该命令对话框后，按 `param_contract.schema` 回填并复跑验证。

## 六、注意事项

- 该外挂与其它外挂共享 60 个短 ID，禁止省略命名空间。
- 外挂升级后菜单可能重排，命令键以本注册表（介质实测）为准，升级后需重跑 `build_plugin_registry.py`。
- 外挂写文件、批量改属性等操作可能绕过 NX 撤消栈，执行前必须提示用户备份。
- 回复用户时按此格式标注：`[第三方外挂] {外挂名} › {命令名}`，不得与官方命令混述。

