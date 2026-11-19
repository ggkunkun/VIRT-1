# 外挂分册：LXH 工具集（`lxh_tool`）

> 版本：**NX12.0-CN**　|　厂商目录：`YANGJEE/LXH_TOOL_12.26`
> 命令数：121（中文标签 121）
> 风险等级：**LOW**　|　证据：E1-MEDIA（GBK/UTF-8 嗅探解码，直接解析介质 .men；已按 NX12 版本目录过滤）
> **非 Siemens 官方功能**，输出时必须向用户明确标注为第三方外挂。

## 一、能力卡

- 菜单文件：1 个，已排除其它 NX 版本菜单 0 个
- 文件编码：{'gbk': 1}
- 菜单版本：{'120': 1}（NX12 应为 120）
- 动作形态：{'其他': 119, '模块文件': 2}
- 硬编码绝对路径：0 处
- 环境变量依赖：0 处
- 跨外挂重名命令 ID：0 个（必须用复合键 `lxh_tool:<ID>`）

## 二、调用前的硬性检查

- ✅ 命令键必须用命名空间：`plugin_id:command_id`；裸 ID 会被判为歧义。

## 三、命令清单

### 动作类型：其他（119 条）

| 复合键 | 中文名 | 菜单 | ACTIONS | 快捷键 |
|---|---|---|---|---|
| `lxh_tool:3D_LINE` | 3D_平分线 | LXH_TOOL_1 | `3D_LINE` | — |
| `lxh_tool:About_Lxh` | 关于... | LXH_TOOL | `About_Lxh` | — |
| `lxh_tool:LT_ADD_NCGROUP` | 叠加程序 | LXH_TOOL_3 | `LT_ADD_NCGROUP` | — |
| `lxh_tool:LT_ADD_SHANK_HOLDER` | 刀具夹持器 | LXH_TOOL_3 | `LT_ADD_SHANK_HOLDER` | — |
| `lxh_tool:LT_AUTO_ALL_CAM` | 电极批量编程 | LXH_TOOL_3 | `LT_AUTO_ALL_CAM` | — |
| `lxh_tool:LT_AUTO_CAM` | 电极编程 | LXH_TOOL_3 | `LT_AUTO_CAM` | — |
| `lxh_tool:LT_AUTO_GROUP` | 程式分组 | LXH_TOOL_3 | `LT_AUTO_GROUP` | — |
| `lxh_tool:LT_AddTempPlate` | 钢料模板编程(极致) | LXH_TOOL_3 | `MyNxTool` | — |
| `lxh_tool:LT_Analysis_measurement` | BOX_检查 | LXH_TOOL_5 | `LT_Analysis_measurement` | — |
| `lxh_tool:LT_BODY_COLOR` | 模型拔模着色 | LXH_TOOL_5 | `LT_BODY_COLOR` | — |
| `lxh_tool:LT_BODY_SIZE` | 实体测量 | LXH_TOOL_5 | `LT_BODY_SIZE` | — |
| `lxh_tool:LT_BOX_SUCAI` | 盒子素材 | LXH_TOOL_1 | `LT_BOX_SUCAI` | — |
| `lxh_tool:LT_BatchEditCamParamL` | 钢料模板编程(左) | LXH_TOOL_3 | `LT_BatchEditCamParamL` | — |
| `lxh_tool:LT_BatchEditCamParamR` | 钢料模板编程(右) | LXH_TOOL_3 | `LT_BatchEditCamParamR` | — |
| `lxh_tool:LT_Blank_point_line_Plane` | 隐藏点线片体 | LXH_TOOL_1 | `LT_Blank_point_line_Plane` | — |
| `lxh_tool:LT_CAM_CHECK_AREA` | 检查面 | LXH_TOOL_3 | `LT_CAM_CHECK_AREA` | — |
| `lxh_tool:LT_CAM_MARK` | CAM加工注析 | LXH_TOOL_3 | `LT_CAM_MARK` | — |
| `lxh_tool:LT_CAM_SEL_FACE_dlx` | 指定切削区域 | LXH_TOOL_3 | `LT_CAM_SEL_FACE_dlx` | — |
| `lxh_tool:LT_CAM_SEL_POINT_dlx` | 进刀点 | LXH_TOOL_3 | `LT_CAM_SEL_POINT_dlx` | — |
| `lxh_tool:LT_CENTER_LINE` | 中心线 | LXH_TOOL_1 | `LT_CENTER_LINE` | — |
| `lxh_tool:LT_CORNER_AVOID_V2` | 角落避空2 | LXH_TOOL_1 | `LT_CORNER_AVOID_V2` | — |
| `lxh_tool:LT_CREATE_ISOCURVE` | 流道辅助线/面 | LXH_TOOL_3 | `LT_CREATE_ISOCURVE` | — |
| `lxh_tool:LT_CREATE_NAME` | 电极命名(层) | LXH_TOOL_2 | `LT_CREATE_NAME` | — |
| `lxh_tool:LT_CREATE_NCGROUP` | 创建和编辑程序 | LXH_TOOL_3 | `LT_CREATE_NCGROUP` | — |
| `lxh_tool:LT_CREATE_NOTE` | 创建引线注解 | LXH_TOOL_4 | `LT_CREATE_NOTE` | — |
| `lxh_tool:LT_CREATE_Single_NCGROUP` | 创建单个程序组 | LXH_TOOL_3 | `LT_CREATE_Single_NCGROUP` | — |
| `lxh_tool:LT_CREATE_TEXT` | 创建单线字 | LXH_TOOL_3 | `LT_CREATE_TEXT` | — |
| `lxh_tool:LT_CREATE_TOOL` | 批量创建刀具 | LXH_TOOL_3 | `LT_CREATE_TOOL` | — |
| `lxh_tool:LT_CREATE_VIEW` | 创建视图 | LXH_TOOL_4 | `LT_CREATE_VIEW` | — |
| `lxh_tool:LT_CUT_LEVELS_EDIT` | 切削层操作 | LXH_TOOL_3 | `LT_CUT_LEVELS_EDIT` | — |
| `lxh_tool:LT_CamBlankBnd` | 批量毛坯边界 | LXH_TOOL_3 | `LT_CamBlankBnd` | — |
| `lxh_tool:LT_CamNonCutting` | 非切削参数 | LXH_TOOL_3 | `LT_CamNonCutting` | — |
| `lxh_tool:LT_CamPartBnd` | 批量部件边界 | LXH_TOOL_3 | `LT_CamPartBnd` | — |
| `lxh_tool:LT_Cam_Clear` | CAM一键清除 | LXH_TOOL_3 | `LT_Cam_Clear` | — |
| `lxh_tool:LT_Cam_Sel_Blank` | 批量指定毛坯 | LXH_TOOL_3 | `LT_Cam_Sel_Blank` | — |
| `lxh_tool:LT_Cam_Sel_Part` | 批量指定部件 | LXH_TOOL_3 | `LT_Cam_Sel_Part` | — |
| `lxh_tool:LT_Corner_Avoid` | 角落避空 | LXH_TOOL_1 | `LT_Corner_Avoid` | — |
| `lxh_tool:LT_DIM_QIANHOUZHUI` | 标注前后缀 | LXH_TOOL_4 | `LT_DIM_QIANHOUZHUI` | — |
| `lxh_tool:LT_DISP_name` | 名称显示开关 | LXH_TOOL_5 | `LT_DISP_name` | — |
| `lxh_tool:LT_Display_Dir` | 打开当前图档文件夹 | LXH_TOOL_6 | `LT_Display_Dir` | — |
| `lxh_tool:LT_EDITING_OPERATING_PARAMETERS` | 批量更改加工参数 | LXH_TOOL_3 | `LT_EDITING_OPERATING_PARAMETERS` | — |
| `lxh_tool:LT_ELEC_BASE` | 基准台 | LXH_TOOL_2 | `LT_ELEC_BASE` | — |
| `lxh_tool:LT_ELEC_CHECK_EDM` | 电极漏拆检查 | LXH_TOOL_2 | `LT_ELEC_CHECK_EDM` | — |
| `lxh_tool:LT_ELEC_EDM` | EDM放电图 | LXH_TOOL_2 | `LT_ELEC_EDM` | — |
| `lxh_tool:LT_ELEC_EXPORT` | 电极导出 | LXH_TOOL_2 | `LT_ELEC_EXPORT` | — |
| `lxh_tool:LT_ELEC_GW` | 拆电极工具集 | LXH_TOOL_2 | `LT_ELEC_GW` | — |
| `lxh_tool:LT_ELEC_GW_R` | 圆形骨位加强 | LXH_TOOL_2 | `LT_ELEC_GW_R` | — |
| `lxh_tool:LT_ELEC_INFO` | 电极信息管理 | LXH_TOOL_2 | `LT_ELEC_INFO` | — |
| `lxh_tool:LT_ELEC_MOVE_ORIGIN` | 电极回原点 | LXH_TOOL_2 | `LT_ELEC_MOVE_ORIGIN` | — |
| `lxh_tool:LT_ELEC_PB` | 电极排板 | LXH_TOOL_2 | `LT_ELEC_PB` | — |
| `lxh_tool:LT_ELEC_PW` | 电极排条 | LXH_TOOL_2 | `LT_ELEC_PW` | — |
| `lxh_tool:LT_ELEC_PW_RESET` | 条料间距重设 | LXH_TOOL_2 | `LT_ELEC_PW_RESET` | — |
| `lxh_tool:LT_ELEC_SINGE_LIST` | 单个电极开料 | LXH_TOOL_2 | `LT_ELEC_SINGE_LIST` | — |
| `lxh_tool:LT_ELEC_TEXT` | 电极刻字 | LXH_TOOL_2 | `LT_ELEC_TEXT` | — |
| `lxh_tool:LT_ELES_LIST` | 电极条料开料 | LXH_TOOL_2 | `LT_ELES_LIST` | — |
| `lxh_tool:LT_ELE_BJ` | 电极报价 | LXH_TOOL_2 | `LT_ELE_BJ` | — |
| `lxh_tool:LT_EXTRUDED_SHEET` | 片体拉伸 | LXH_TOOL_1 | `LT_EXTRUDED_SHEET` | — |
| `lxh_tool:LT_Extruded` | 批量拉伸 | LXH_TOOL_1 | `LT_Extruded` | — |
| `lxh_tool:LT_FACE_ANG` | 斜度测量 | LXH_TOOL_5 | `LT_FACE_ANG` | — |
| `lxh_tool:LT_FACE_YAPING` | 曲面压平 | LXH_TOOL_1 | `LT_FACE_YAPING` | — |
| `lxh_tool:LT_Faceinfo` | 动态分析 | LXH_TOOL_5 | `LT_Faceinfo` | — |
| `lxh_tool:LT_HOLE_AVOID` | 孔底避空 | LXH_TOOL_1 | `LT_HOLE_AVOID` | — |
| `lxh_tool:LT_HOLE_DIM` | 孔径标注 | LXH_TOOL_4 | `LT_HOLE_DIM` | — |
| `lxh_tool:LT_IDENTICAL_BODYS` | 找相同 | LXH_TOOL_5 | `LT_IDENTICAL_BODYS` | — |
| `lxh_tool:LT_KEZI` | 刻字 | LXH_TOOL_1 | `LT_KEZI` | — |
| `lxh_tool:LT_MIN_ARC_BOX` | 最小圆柱 | LXH_TOOL_1 | `LT_MIN_ARC_BOX` | — |
| `lxh_tool:LT_MIN_BOX` | 最小盒子 | LXH_TOOL_1 | `LT_MIN_BOX` | — |
| `lxh_tool:LT_MOVE_OBJ` | 实体移动/复制 | LXH_TOOL_1 | `LT_MOVE_OBJ` | — |
| `lxh_tool:LT_Measure` | 测量小工具 | LXH_TOOL_5 | `LT_Measure` | — |
| `lxh_tool:LT_NCSHEET` | 程式单 | LXH_TOOL_3 | `LT_NCSHEET` | — |
| `lxh_tool:LT_NEXT_DRAWING` | 打开下一张图纸 | LXH_TOOL_4 | `LT_UP_DRAWING` | — |
| `lxh_tool:LT_Next_Layer` | 下一层 | LXH_TOOL_1 | `LT_Next_Layer` | — |
| `lxh_tool:LT_Next_Layer_Solid` | 下一层实体 | LXH_TOOL_1 | `LT_Next_Layer_Solid` | — |
| `lxh_tool:LT_OBJ_CDW` | 工件定位 | LXH_TOOL_1 | `LT_OBJ_CDW` | — |
| `lxh_tool:LT_OBJ_CDW2` | 工件定位2 | LXH_TOOL_1 | `LT_OBJ_CDW2` | — |
| `lxh_tool:LT_OBJ_DRAW_CSYS` | 定义出图坐标系 | LXH_TOOL_4 | `LT_OBJ_DRAW_CSYS` | — |
| `lxh_tool:LT_OPER_OFFICE_Z` | 批量Z偏置 | LXH_TOOL_3 | `LT_OPER_OFFICE_Z` | — |
| `lxh_tool:LT_Office_Face` | 批量偏置面 | LXH_TOOL_1 | `LT_Office_Face` | — |
| `lxh_tool:LT_Overlap` | 工件重合 | LXH_TOOL_1 | `LT_Overlap` | — |
| `lxh_tool:LT_PROTECT_THE_SURFACE` | 曲面保护 | LXH_TOOL_3 | `LT_PROTECT_THE_SURFACE` | — |
| `lxh_tool:LT_Rectangle_Split` | 矩形分割 | LXH_TOOL_1 | `LT_Rectangle_Split` | — |
| `lxh_tool:LT_SET_OBJ_LAYER` | 实体快速分层 | LXH_TOOL_1 | `LT_SET_OBJ_LAYER` | — |
| `lxh_tool:LT_Set_Translucency` | 透明 | LXH_TOOL_1 | `LT_Set_Translucency` | — |
| `lxh_tool:LT_Specify_Arc` | 动态圆 | LXH_TOOL_1 | `LT_Specify_Arc` | — |
| `lxh_tool:LT_Split_Body` | 分割实体(不选体) | LXH_TOOL_1 | `LT_Split_Body` | — |
| `lxh_tool:LT_Split_SelBody` | 分割实体(选体) | LXH_TOOL_1 | `LT_Split_SelBody` | — |
| `lxh_tool:LT_SteelTemplate` | 批量插入模板 | LXH_TOOL_3 | `LT_SteelTemplate` | — |
| `lxh_tool:LT_Tool2Curve` | 刀路转曲线 | LXH_TOOL_3 | `LT_Tool2Curve` | — |
| `lxh_tool:LT_Trim_Body` | 正向修剪实体 | LXH_TOOL_1 | `LT_Trim_Body` | — |
| `lxh_tool:LT_Trim_Body2` | 反向修剪实体 | LXH_TOOL_1 | `LT_Trim_Body2` | — |
| `lxh_tool:LT_Trim_boundaryDlx` | 批量修剪边界 | LXH_TOOL_3 | `LT_Trim_boundaryDlx` | — |
| `lxh_tool:LT_UP_DRAWING` | 打开上一张图纸 | LXH_TOOL_4 | `LT_UP_DRAWING` | — |
| `lxh_tool:LT_Up_Layer` | 上一层 | LXH_TOOL_1 | `LT_Up_Layer` | — |
| `lxh_tool:LT_Up_Layer_Solid` | 上一层实体 | LXH_TOOL_1 | `LT_Up_Layer_Solid` | — |
| `lxh_tool:LT_XD_BOX` | 斜顶定位柱 | LXH_TOOL_1 | `LT_XD_BOX` | — |
| `lxh_tool:LT_XD_KZ` | 斜顶/定制刻字 | LXH_TOOL_1 | `LT_XD_KZ` | — |
| `lxh_tool:LT_XD_PW` | 斜顶排位 | LXH_TOOL_1 | `LT_XD_PW` | — |
| `lxh_tool:LT_XJBODYS` | 批量修剪实体 | LXH_TOOL_1 | `LT_XJBODYS` | — |
| `lxh_tool:LT_XYZ` | XYZ标注 | LXH_TOOL_4 | `LT_XYZ` | — |
| `lxh_tool:LT_check_interference` | 干涉检查 | LXH_TOOL_2 | `LT_check_interference` | — |
| `lxh_tool:LT_ele_left_right_move` | 条料左右上下移 | LXH_TOOL_2 | `LT_ele_left_right_move` | — |
| `lxh_tool:LT_holder_lib` | 刀柄夹持器库 | LXH_TOOL_3 | `LT_holder_lib` | — |
| `lxh_tool:LT_initialize_ModlName` | 模号设置 | LXH_TOOL_0 | `LT_initialize_ModlName` | — |
| `lxh_tool:LT_polygon_Split` | 多边形分割 | LXH_TOOL_1 | `LT_polygon_Split` | — |
| `lxh_tool:LT_prt_to_xt` | PRT转低版本 | LXH_TOOL_1 | `LT_prt_to_xt` | — |
| `lxh_tool:LT_removehighlight` | 清除高亮 | LXH_TOOL_1 | `LT_removehighlight` | — |
| `lxh_tool:LT_removeparams` | 实体去参 | LXH_TOOL_1 | `LT_removeparams` | — |
| `lxh_tool:LT_replace_face` | 批量替换面 | LXH_TOOL_1 | `LT_replace_face` | — |
| `lxh_tool:LT_set_color` | 着色 | LXH_TOOL_1 | `LT_set_color` | — |
| `lxh_tool:LT_set_note_size` | 更改注析大小 | LXH_TOOL_4 | `LT_set_note_size` | — |
| `lxh_tool:LT_specify_wall` | 指定壁几何体 | LXH_TOOL_3 | `LT_specify_wall` | — |
| `lxh_tool:LT_transform_component` | 变换组件 | LXH_TOOL_7 | `LT_transform_component` | — |
| `lxh_tool:LT_unite_bodies` | 批量布尔加 | LXH_TOOL_1 | `LT_unite_bodies` | — |
| `lxh_tool:LtToolParameters` | 刀具刀库参数批设 | LXH_TOOL_3 | `LtToolParameters` | — |
| `lxh_tool:Lt_BuKong` | 补孔 | LXH_TOOL_1_2 | `Lt_BuKong` | — |
| `lxh_tool:Lt_DelBlendFace` | 删除倒角 | LXH_TOOL_1_2 | `Lt_DelBlendFace` | — |
| `lxh_tool:Lt_DelKong` | 删除孔 | LXH_TOOL_1_2 | `Lt_DelKong` | — |
| `lxh_tool:Lt_MinToolLen` | 批量生成最短刀长 | LXH_TOOL_3 | `Lt_MinToolLen` | — |
| `lxh_tool:TOOL_ATTR` | 属性设置 | LXH_TOOL_0 | `TOOL_ATTR` | — |

### 动作类型：模块文件（2 条）

| 复合键 | 中文名 | 菜单 | ACTIONS | 快捷键 |
|---|---|---|---|---|
| `lxh_tool:LT_GRIP_xd_pw` | 斜顶排位(面) | LXH_TOOL_1 | `LT_GRIP_xd_pw.grx` | — |
| `lxh_tool:LT_rotate` | 零件旋转 | LXH_TOOL_1 | `LT_rotate.grx` | — |

## 四、标准调用流程（Agent 必须按此执行）

1. `list_plugins()` 确认该外挂已注册、`version_ok_for_nx12=true`。
2. `search('<中文名>', plugin='lxh_tool')` 定位候选，拿到复合键。
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

