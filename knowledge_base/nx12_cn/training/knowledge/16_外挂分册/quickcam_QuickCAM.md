# 外挂分册：QuickCAM 快速编程（`quickcam`）

> 版本：**NX12.0-CN**　|　厂商目录：`YANGJEE/QuickCAM`
> 命令数：121（中文标签 1）
> 风险等级：**MEDIUM**　|　证据：E1-MEDIA（GBK/UTF-8 嗅探解码，直接解析介质 .men；已按 NX12 版本目录过滤）
> **非 Siemens 官方功能**，输出时必须向用户明确标注为第三方外挂。

## 一、能力卡

- 菜单文件：1 个，已排除其它 NX 版本菜单 1 个
- 文件编码：{'gbk': 1}
- 菜单版本：未声明（NX12 应为 120）
- 动作形态：{'其他': 120, '模块文件': 1}
- 硬编码绝对路径：0 处
- 环境变量依赖：0 处
- 跨外挂重名命令 ID：121 个（必须用复合键 `quickcam:<ID>`）

## 二、调用前的硬性检查

- ✅ 命令键必须用命名空间：`plugin_id:command_id`；裸 ID 会被判为歧义。

## 三、命令清单

### 动作类型：其他（120 条）

| 复合键 | 中文名 | 菜单 | ACTIONS | 快捷键 |
|---|---|---|---|---|
| `quickcam:K_PATH2CURVE` | 自动刀具号 | quick_cam_Cam_Tools | `LYP-daohao` | — |
| `quickcam:quick_cam_abs` | To ABS | quick_cam_small_tools | `quick_cam_abs` | — |
| `quickcam:quick_cam_add_data` | Use Para From ToolLib | quick_cam_Cam_Tools | `quick_cam_add_data` | — |
| `quickcam:quick_cam_antocam_pro_vnt` | Transform Operate From Pre v7.1 | quick_cam_System_Tools | `quick_cam_antocam_pro_vnt` | — |
| `quickcam:quick_cam_ask_body_size` | Box Size | quick_cam_tools | `quick_cam_ask_body_size` | — |
| `quickcam:quick_cam_ask_ele_inf` | Elec Attributes Edit | quick_cam_Ele_Tools | `quick_cam_ask_ele_inf` | — |
| `quickcam:quick_cam_ask_min_r` | Min R | quick_cam_tools | `quick_cam_ask_min_r` | — |
| `quickcam:quick_cam_attr_convert` | Foreign Attributes To StarCAM | quick_cam_Ele_Tools | `quick_cam_attr_convert` | — |
| `quickcam:quick_cam_auto_cam` | Elec AutoCAM | quick_cam_Cam_Tools | `quick_cam_auto_cam` | — |
| `quickcam:quick_cam_auto_ele` | Auto Electrode | quick_cam_Ele_Tools | `quick_cam_auto_ele` | — |
| `quickcam:quick_cam_auto_save` | AutoSave Lock | quick_cam_System_Tools | `quick_cam_auto_save` | — |
| `quickcam:quick_cam_cam_manage` | ToolPath Edit | quick_cam_Cam_Tools | `quick_cam_cam_manage` | — |
| `quickcam:quick_cam_cancel_highlight` | Kill Highlight | quick_cam_small_tools | `quick_cam_cancel_highlight` | — |
| `quickcam:quick_cam_cancel_transparent` | Kill Transparent | quick_cam_small_tools | `quick_cam_cancel_transparent` | — |
| `quickcam:quick_cam_center_line` | Center Line | quick_cam_tools | `quick_cam_center_line` | — |
| `quickcam:quick_cam_check_dim_more` | CMM Label | quick_cam_Check_Tools | `quick_cam_check_dim_more` | — |
| `quickcam:quick_cam_check_draw` | LYP-daohao | quick_cam_Check_Tools | `LYP-daohao` | — |
| `quickcam:quick_cam_check_inter` | Interfer Elec | quick_cam_Ele_Tools | `quick_cam_check_inter` | — |
| `quickcam:quick_cam_check_missing_elec` | Check Missing Elec | quick_cam_Ele_Tools | `quick_cam_check_missing_elec` | — |
| `quickcam:quick_cam_close_computer` | Computer Shutdown | quick_cam_System_Tools | `quick_cam_close_computer` | — |
| `quickcam:quick_cam_command_reiterate` | Repeat Cmd | quick_cam_System_Tools | `quick_cam_command_reiterate` | — |
| `quickcam:quick_cam_convert_xt` | Translate Prt File To Low Ug Format | quick_cam_tools | `quick_cam_convert_xt` | — |
| `quickcam:quick_cam_copy_layer` | Copy Elec To CAM Layer | quick_cam_Cam_Tools | `quick_cam_copy_layer` | — |
| `quickcam:quick_cam_copy_oper` | Elec Copy Toolpath | quick_cam_Cam_Tools | `quick_cam_copy_oper` | — |
| `quickcam:quick_cam_corner_avoid` | Corner Avoid | quick_cam_tools | `quick_cam_corner_avoid` | — |
| `quickcam:quick_cam_create_base_pt` | Datum Electrode Point | quick_cam_Ele_Tools | `quick_cam_create_base_pt` | — |
| `quickcam:quick_cam_create_holder` | Add/Edit Holder | quick_cam_Cam_Tools | `quick_cam_create_holder` | — |
| `quickcam:quick_cam_create_tool` | Create Tools | quick_cam_Cam_Tools | `quick_cam_create_tool` | — |
| `quickcam:quick_cam_delete_attr` | Elec Attributes Delete | quick_cam_Ele_Tools | `quick_cam_delete_attr` | — |
| `quickcam:quick_cam_dynamic_cir` | Fly Circle | quick_cam_tools | `quick_cam_dynamic_cir` | — |
| `quickcam:quick_cam_edit_modl` | Edit MoldNum | quick_cam_Draw_Tools | `quick_cam_edit_modl` | — |
| `quickcam:quick_cam_edm_draw` | EDM Drafting | quick_cam_Ele_Draw | `quick_cam_edm_draw` | — |
| `quickcam:quick_cam_edm_draw_multi` | Multi EDM Drafting | quick_cam_Ele_Draw | `quick_cam_edm_draw_multi` | — |
| `quickcam:quick_cam_ele_ass` | Elec Assembly | quick_cam_Ele_Tools | `quick_cam_ele_ass` | — |
| `quickcam:quick_cam_ele_base` | Electrode Base | quick_cam_Ele_Tools | `quick_cam_ele_base` | — |
| `quickcam:quick_cam_ele_layout` | Elec BoardUp | quick_cam_Ele_Tools | `quick_cam_ele_layout` | — |
| `quickcam:quick_cam_ele_list` | Elec Bom | quick_cam_Ele_Draw | `quick_cam_ele_list` | — |
| `quickcam:quick_cam_ele_rank` | Elec LineUp | quick_cam_Ele_Tools | `quick_cam_ele_rank` | — |
| `quickcam:quick_cam_ele_rename` | Component Rename | quick_cam_Ele_Tools | `quick_cam_ele_rename` | — |
| `quickcam:quick_cam_ele_set_name` | Electrode Name(Category) | quick_cam_Ele_Tools | `quick_cam_ele_set_name` | — |
| `quickcam:quick_cam_ele_text` | Dressing Elec Name | quick_cam_Ele_Tools | `quick_cam_ele_text` | — |
| `quickcam:quick_cam_erase_body` | Erase Object From View | quick_cam_Draw_Tools | `quick_cam_erase_body` | — |
| `quickcam:quick_cam_export_2d` | Export 2D | quick_cam_Draw_Tools | `quick_cam_export_2d` | — |
| `quickcam:quick_cam_export_ele` | Elec Export | quick_cam_Ele_Tools | `quick_cam_export_ele` | — |
| `quickcam:quick_cam_export_to_icam` | Export to ICAM | quick_cam_Ele_Tools | `quick_cam_export_to_icam` | — |
| `quickcam:quick_cam_export_to_jm` | Export to JM | quick_cam_Ele_Tools | `quick_cam_export_to_jm` | — |
| `quickcam:quick_cam_export_to_pm` | Export to PM | quick_cam_Ele_Tools | `quick_cam_export_to_pm` | — |
| `quickcam:quick_cam_face_analysis` | Solid Analysis | quick_cam_tools | `quick_cam_face_analysis` | — |
| `quickcam:quick_cam_face_info` | Geom Properties | quick_cam_tools | `quick_cam_face_info` | — |
| `quickcam:quick_cam_high_box` | Max Box | quick_cam_tools | `quick_cam_high_box` | — |
| `quickcam:quick_cam_holder_library` | Holder Library | quick_cam_System_Tools | `quick_cam_holder_library` | — |
| `quickcam:quick_cam_hole_hollow` | Bottom Flatting | quick_cam_tools | `quick_cam_hole_hollow` | — |
| `quickcam:quick_cam_import_draw` | Import Sheet | quick_cam_Draw_Tools | `quick_cam_import_draw` | — |
| `quickcam:quick_cam_input_inf` | Elec Attributes | quick_cam_Ele_Tools | `quick_cam_input_inf` | — |
| `quickcam:quick_cam_layer_set` | Layer Set | quick_cam_small_tools | `quick_cam_layer_set` | — |
| `quickcam:quick_cam_min_tool_len` | Report Shortest Tool | quick_cam_Cam_Tools | `quick_cam_min_tool_len` | — |
| `quickcam:quick_cam_mirror` | Mirroring | quick_cam_Ele_Tools | `quick_cam_mirror` | — |
| `quickcam:quick_cam_move_body_up` | Right Position | quick_cam_tools | `quick_cam_move_body_up` | — |
| `quickcam:quick_cam_move_to_origin` | Elec Move Back | quick_cam_Ele_Tools | `quick_cam_move_to_origin` | — |
| `quickcam:quick_cam_multi_auto_cam` | Elec AutoCAM Batch | quick_cam_Cam_Tools | `quick_cam_multi_auto_cam` | — |
| `quickcam:quick_cam_multi_base` | Elec Base Batching | quick_cam_Ele_Tools | `quick_cam_multi_base` | — |
| `quickcam:quick_cam_multi_group` | Create Program Group | quick_cam_Cam_Tools | `quick_cam_multi_group` | — |
| `quickcam:quick_cam_multi_post_sheet` | Batch Post/Shopdoc | quick_cam_Cam_Tools | `quick_cam_multi_post_sheet` | — |
| `quickcam:quick_cam_multi_subtract` | Batch Subtract | quick_cam_Ele_Tools | `quick_cam_multi_subtract` | — |
| `quickcam:quick_cam_name_switch` | Name Display | quick_cam_Ele_Tools | `quick_cam_name_switch` | — |
| `quickcam:quick_cam_next_body_layer` | Layer Next With Solid | quick_cam_small_tools | `quick_cam_next_body_layer` | — |
| `quickcam:quick_cam_next_drawing` | Sheet Next | quick_cam_small_tools | `quick_cam_next_drawing` | — |
| `quickcam:quick_cam_next_layer` | Layer Next | quick_cam_small_tools | `quick_cam_next_layer` | — |
| `quickcam:quick_cam_note` | Quick Note | quick_cam_Draw_Tools | `quick_cam_note` | — |
| `quickcam:quick_cam_offset_extrude` | Offset  Extrude | quick_cam_Ele_Tools | `quick_cam_offset_extrude` | — |
| `quickcam:quick_cam_open_part_folder` | Current Dir | quick_cam_small_tools | `quick_cam_open_part_folder` | — |
| `quickcam:quick_cam_part_origin` | Part Positioning | quick_cam_tools | `quick_cam_part_origin` | — |
| `quickcam:quick_cam_plunge_corner` | Plunge Corner | quick_cam_Cam_Tools | `quick_cam_plunge_corner` | — |
| `quickcam:quick_cam_points_split` | 2Point Split | quick_cam_tools | `quick_cam_points_split` | — |
| `quickcam:quick_cam_polyon_split` | Polygon Split | quick_cam_tools | `quick_cam_polyon_split` | — |
| `quickcam:quick_cam_polyon_trim` | Polygon Trim | quick_cam_tools | `quick_cam_polyon_trim` | — |
| `quickcam:quick_cam_post_excel` | Excel Shopdoc | quick_cam_Cam_Tools | `quick_cam_post_excel` | — |
| `quickcam:quick_cam_post_sheet` | Post/Shopdoc | quick_cam_Cam_Tools | `quick_cam_post_sheet` | — |
| `quickcam:quick_cam_print1` | Print | quick_cam_Draw_Tools | `quick_cam_print1` | — |
| `quickcam:quick_cam_queue_list` | Elec Line Bom | quick_cam_Ele_Draw | `quick_cam_queue_list` | — |
| `quickcam:quick_cam_rectangle_split` | Rect Split | quick_cam_tools | `quick_cam_rectangle_split` | — |
| `quickcam:quick_cam_rectangle_trim` | Rect Trim | quick_cam_tools | `quick_cam_rectangle_trim` | — |
| `quickcam:quick_cam_remove_parameters` | Remove Parameters | quick_cam_small_tools | `quick_cam_remove_parameters` | — |
| `quickcam:quick_cam_replace_face` | Replace Face | quick_cam_tools | `quick_cam_replace_face` | — |
| `quickcam:quick_cam_rib_ele` | Rib Strengthen | quick_cam_Ele_Tools | `quick_cam_rib_ele` | — |
| `quickcam:quick_cam_set_face_color` | Face Color | quick_cam_small_tools | `quick_cam_set_face_color` | — |
| `quickcam:quick_cam_set_layer` | Elec Layering | quick_cam_Ele_Tools | `quick_cam_set_layer` | — |
| `quickcam:quick_cam_set_only_display` | Only Display | quick_cam_small_tools | `quick_cam_set_only_display` | — |
| `quickcam:quick_cam_set_oper_param` | Set CAM Param | quick_cam_Cam_Tools | `quick_cam_set_oper_param` | — |
| `quickcam:quick_cam_set_translucency` | Make Transparent | quick_cam_small_tools | `quick_cam_set_translucency` | — |
| `quickcam:quick_cam_set_wcs` | WCS Set | quick_cam_tools | `quick_cam_set_wcs` | — |
| `quickcam:quick_cam_show_sheet` | Browse Sheet | quick_cam_Draw_Tools | `quick_cam_show_sheet` | — |
| `quickcam:quick_cam_solbox` | Simple MaxBox | quick_cam_tools | `quick_cam_solbox` | — |
| `quickcam:quick_cam_specify_floor` | Elec Bottom Face | quick_cam_Ele_Tools | `quick_cam_specify_floor` | — |
| `quickcam:quick_cam_split` | Smart Split | quick_cam_tools | `quick_cam_split` | — |
| `quickcam:quick_cam_split2` | Smart Split(NoNeedSolid) | quick_cam_tools | `quick_cam_split2` | — |
| `quickcam:quick_cam_split_body` | Number Split | quick_cam_tools | `quick_cam_split_body` | — |
| `quickcam:quick_cam_steady_line` | Runner Line | quick_cam_tools | `quick_cam_steady_line` | — |
| `quickcam:quick_cam_steel_cam` | Steel CAM | quick_cam_Cam_Tools | `quick_cam_steel_cam` | — |
| `quickcam:quick_cam_surface_flatten` | Face Flatting | quick_cam_tools | `quick_cam_surface_flatten` | — |
| `quickcam:quick_cam_system_setting` | StarCAM Customer Defaults | quick_cam_System_Tools | `quick_cam_system_setting` | — |
| `quickcam:quick_cam_text` | Texting | quick_cam_tools | `quick_cam_text` | — |
| `quickcam:quick_cam_tool_offset` | Tool Z Offset | quick_cam_Cam_Tools | `quick_cam_tool_offset` | — |
| `quickcam:quick_cam_toollib_manage` | Tool Library | quick_cam_System_Tools | `quick_cam_toollib_manage` | — |
| `quickcam:quick_cam_total_draw` | EDM Draft All In One | quick_cam_Ele_Draw | `quick_cam_total_draw` | — |
| `quickcam:quick_cam_transf_config_data` | Transform config File | quick_cam_System_Tools | `quick_cam_transf_config_data` | — |
| `quickcam:quick_cam_transform` | Move Object | quick_cam_tools | `quick_cam_transform` | — |
| `quickcam:quick_cam_trim_body` | Solid Dresser | quick_cam_tools | `quick_cam_trim_body` | — |
| `quickcam:quick_cam_trim_high` | Batch Z Triming | quick_cam_Ele_Tools | `quick_cam_trim_high` | — |
| `quickcam:quick_cam_up_body_layer` | Layer Back With Solid | quick_cam_small_tools | `quick_cam_up_body_layer` | — |
| `quickcam:quick_cam_up_drawing` | Sheet Back | quick_cam_small_tools | `quick_cam_up_drawing` | — |
| `quickcam:quick_cam_up_layer` | Layer Back | quick_cam_small_tools | `quick_cam_up_layer` | — |
| `quickcam:quick_cam_wcs_back` | BACK | quick_cam_wcs_view | `quick_cam_wcs_back` | — |
| `quickcam:quick_cam_wcs_bottom` | BOTTOM | quick_cam_wcs_view | `quick_cam_wcs_bottom` | — |
| `quickcam:quick_cam_wcs_front` | FRONT | quick_cam_wcs_view | `quick_cam_wcs_front` | — |
| `quickcam:quick_cam_wcs_left` | LEFT | quick_cam_wcs_view | `quick_cam_wcs_left` | — |
| `quickcam:quick_cam_wcs_right` | RIGHT | quick_cam_wcs_view | `quick_cam_wcs_right` | — |
| `quickcam:quick_cam_wcs_tfr` | TFR-ISO | quick_cam_wcs_view | `quick_cam_wcs_tfr` | — |
| `quickcam:quick_cam_wcs_top` | TOP | quick_cam_wcs_view | `quick_cam_wcs_top` | — |
| `quickcam:quick_cam_wedm_hole` | WEDM PreHole | quick_cam_tools | `quick_cam_wedm_hole` | — |

### 动作类型：模块文件（1 条）

| 复合键 | 中文名 | 菜单 | ACTIONS | 快捷键 |
|---|---|---|---|---|
| `quickcam:quick_cam_calculator` | Calculator | quick_cam_System_Tools | `calc.grx` | — |

## 四、标准调用流程（Agent 必须按此执行）

1. `list_plugins()` 确认该外挂已注册、`version_ok_for_nx12=true`。
2. `search('<中文名>', plugin='quickcam')` 定位候选，拿到复合键。
3. `plan_call(key)` 取调用计划；**`callable=false` 时禁止执行**，按 `blockers` 的 code 处置。
4. 检查 `preconditions` 全部满足；参数按 `param_contract` 组织，未实测字段不得编造。
5. 在 NX GUI 中按 `menu_path` 逐层展开并点击命令；外挂无 COM/批处理，只能交互执行。
6. 结果核验：几何/文件是否按预期变化；失败时先 Ctrl+Z，再按错误码上报。

## 五、参数说明

- 外挂 `.men` 只定义菜单与 ACTIONS，**不含参数默认值/取值范围**。
- 因此本分册所有命令的参数状态为 `[待实测]`；Agent 不得向用户承诺具体参数值。
- 需在 NX 12 中文界面打开该命令对话框后，按 `param_contract.schema` 回填并复跑验证。

## 六、注意事项

- 该外挂与其它外挂共享 121 个短 ID，禁止省略命名空间。
- 外挂升级后菜单可能重排，命令键以本注册表（介质实测）为准，升级后需重跑 `build_plugin_registry.py`。
- 外挂写文件、批量改属性等操作可能绕过 NX 撤消栈，执行前必须提示用户备份。
- 回复用户时按此格式标注：`[第三方外挂] {外挂名} › {命令名}`，不得与官方命令混述。

