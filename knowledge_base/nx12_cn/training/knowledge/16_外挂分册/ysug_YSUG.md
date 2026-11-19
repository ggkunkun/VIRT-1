# 外挂分册：YSUG 模具外挂（`ysug`）

> 版本：**NX12.0-CN**　|　厂商目录：`YANGJEE/YSUG`
> 命令数：284（中文标签 100）
> 风险等级：**HIGH**　|　证据：E1-MEDIA（GBK/UTF-8 嗅探解码，直接解析介质 .men；已按 NX12 版本目录过滤）
> **非 Siemens 官方功能**，输出时必须向用户明确标注为第三方外挂。

## 一、能力卡

- 菜单文件：19 个，已排除其它 NX 版本菜单 22 个
- 文件编码：{'gbk': 17, 'utf-8': 2}
- 菜单版本：{'130': 1, '120': 9}（NX12 应为 120）
- 动作形态：{'模块文件': 61, '其他': 122, '绝对路径': 38, '环境变量': 1, '无ACTIONS': 62}
- 硬编码绝对路径：38 处，示例：`D:\YSUG\application\feed.grx`
- 环境变量依赖：1 处，示例：`${KASA_DIR}\application\Open_Prt_Dir.grx`
- 跨外挂重名命令 ID：0 个（必须用复合键 `ysug:<ID>`）

## 二、调用前的硬性检查

- ⛔ **版本不兼容**：以下菜单 `VERSION != 120`，NX12 下可能不加载：

  - `YANGJEE/YSUG/Kasa/64bit/startup/Kas.men`

- ⚠️ **路径绑定**：ACTIONS 为绝对路径，外挂未装在原路径则调用失败；上线前用 `plugin_router.py doctor` 核对。

- ⚠️ **环境变量**：ACTIONS 依赖环境变量，NX 启动前必须已设置。

- ✅ 命令键必须用命名空间：`plugin_id:command_id`；裸 ID 会被判为歧义。

## 三、命令清单

### 动作类型：其他（122 条）

| 复合键 | 中文名 | 菜单 | ACTIONS | 快捷键 |
|---|---|---|---|---|
| `ysug:quick_cam_about` | About StarCAM | quick_cam | `quick_cam_about` | — |
| `ysug:quick_cam_abs` | To ABS | quick_cam_small_tools / quick_cam_tools | `quick_cam_abs` | — |
| `ysug:quick_cam_add_data` | Use Para From ToolLib | quick_cam_Cam_Tools | `quick_cam_add_data` | — |
| `ysug:quick_cam_antocam_pro_vnt` | Transform Operate From Pre v7.1 | quick_cam_System_Tools | `quick_cam_antocam_pro_vnt` | — |
| `ysug:quick_cam_ask_body_size` | Box Size | quick_cam_tools | `quick_cam_ask_body_size` | — |
| `ysug:quick_cam_ask_ele_inf` | Elec Attributes Edit | quick_cam_Ele_Tools | `quick_cam_ask_ele_inf` | — |
| `ysug:quick_cam_ask_min_r` | Min R | quick_cam_tools | `quick_cam_ask_min_r` | — |
| `ysug:quick_cam_attr_convert` | Foreign Attributes To StarCAM | quick_cam_Ele_Tools | `quick_cam_attr_convert` | — |
| `ysug:quick_cam_auto_cam` | Elec AutoCAM | quick_cam_Cam_Tools | `quick_cam_auto_cam` | — |
| `ysug:quick_cam_auto_ele` | Auto Electrode | quick_cam_Ele_Tools | `quick_cam_auto_ele` | — |
| `ysug:quick_cam_auto_save` | AutoSave Lock | quick_cam_System_Tools | `quick_cam_auto_save` | — |
| `ysug:quick_cam_cam_manage` | ToolPath Edit | quick_cam_Cam_Tools | `quick_cam_cam_manage` | — |
| `ysug:quick_cam_cancel_highlight` | Kill Highlight | quick_cam_small_tools | `quick_cam_cancel_highlight` | — |
| `ysug:quick_cam_cancel_transparent` | Kill Transparent | quick_cam_small_tools / quick_cam_tools | `quick_cam_cancel_transparent` | — |
| `ysug:quick_cam_center_line` | Center Line | quick_cam_tools | `quick_cam_center_line` | — |
| `ysug:quick_cam_check_dim_more` | CMM Label | quick_cam_Check_Tools | `quick_cam_check_dim_more` | — |
| `ysug:quick_cam_check_draw` | CMM Sheet | quick_cam_Check_Tools | `quick_cam_check_draw` | — |
| `ysug:quick_cam_check_inter` | Interfer Elec | quick_cam_Ele_Tools | `quick_cam_check_inter` | — |
| `ysug:quick_cam_check_missing_elec` | Check Missing Elec | quick_cam_Ele_Tools | `quick_cam_check_missing_elec` | — |
| `ysug:quick_cam_close_computer` | Computer Shutdown | quick_cam_System_Tools | `quick_cam_close_computer` | — |
| `ysug:quick_cam_command_reiterate` | Repeat Cmd | quick_cam_System_Tools | `quick_cam_command_reiterate` | — |
| `ysug:quick_cam_convert_xt` | Translate Prt File To Low Ug Format | quick_cam_tools | `quick_cam_convert_xt` | — |
| `ysug:quick_cam_copy_layer` | Copy Elec To CAM Layer | quick_cam_Cam_Tools | `quick_cam_copy_layer` | — |
| `ysug:quick_cam_copy_oper` | Elec Copy Toolpath | quick_cam_Cam_Tools | `quick_cam_copy_oper` | — |
| `ysug:quick_cam_corner_avoid` | Corner Avoid | quick_cam_tools | `quick_cam_corner_avoid` | — |
| `ysug:quick_cam_create_base_pt` | Datum Electrode Point | quick_cam_Ele_Tools | `quick_cam_create_base_pt` | — |
| `ysug:quick_cam_create_holder` | Add/Edit Holder | quick_cam_Cam_Tools | `quick_cam_create_holder` | — |
| `ysug:quick_cam_create_tool` | Create Tools | quick_cam_Cam_Tools | `quick_cam_create_tool` | — |
| `ysug:quick_cam_delete_attr` | Elec Attributes Delete | quick_cam_Ele_Tools | `quick_cam_delete_attr` | — |
| `ysug:quick_cam_dog_setting` | SoftDog Setting | quick_cam_System_Tools | `quick_cam_dog_setting` | — |
| `ysug:quick_cam_dynamic_cir` | Fly Circle | quick_cam_tools | `quick_cam_dynamic_cir` | — |
| `ysug:quick_cam_edit_modl` | Edit MoldNum | quick_cam_Draw_Tools | `quick_cam_edit_modl` | — |
| `ysug:quick_cam_edm_draw` | EDM Drafting | quick_cam_Ele_Draw | `quick_cam_edm_draw` | — |
| `ysug:quick_cam_edm_draw_multi` | Multi EDM Drafting | quick_cam_Ele_Draw | `quick_cam_edm_draw_multi` | — |
| `ysug:quick_cam_ele_ass` | Elec Assembly | quick_cam_Ele_Tools | `quick_cam_ele_ass` | — |
| `ysug:quick_cam_ele_base` | Electrode Base | quick_cam_Ele_Tools | `quick_cam_ele_base` | — |
| `ysug:quick_cam_ele_layout` | Elec BoardUp | quick_cam_Ele_Tools | `quick_cam_ele_layout` | — |
| `ysug:quick_cam_ele_list` | Elec Bom | quick_cam_Ele_Draw | `quick_cam_ele_list` | — |
| `ysug:quick_cam_ele_rank` | Elec LineUp | quick_cam_Ele_Tools | `quick_cam_ele_rank` | — |
| `ysug:quick_cam_ele_rename` | Component Rename | quick_cam_Ele_Tools | `quick_cam_ele_rename` | — |
| `ysug:quick_cam_ele_set_name` | Electrode Name(Category) | quick_cam_Ele_Tools | `quick_cam_ele_set_name` | — |
| `ysug:quick_cam_ele_text` | Dressing Elec Name | quick_cam_Ele_Tools | `quick_cam_ele_text` | — |
| `ysug:quick_cam_erase_body` | Erase Object From View | quick_cam_Draw_Tools | `quick_cam_erase_body` | — |
| `ysug:quick_cam_export_2d` | Export 2D | quick_cam_Draw_Tools / quick_cam_System_Tools | `quick_cam_export_2d` | — |
| `ysug:quick_cam_export_ele` | Elec Export | quick_cam_Ele_Tools | `quick_cam_export_ele` | — |
| `ysug:quick_cam_export_to_icam` | Export to ICAM | quick_cam_Ele_Tools | `quick_cam_export_to_icam` | — |
| `ysug:quick_cam_export_to_jm` | Export to JM | quick_cam_Ele_Tools | `quick_cam_export_to_jm` | — |
| `ysug:quick_cam_export_to_pm` | Export to PM | quick_cam_Ele_Tools | `quick_cam_export_to_pm` | — |
| `ysug:quick_cam_face_analysis` | Solid Analysis | quick_cam_tools | `quick_cam_face_analysis` | — |
| `ysug:quick_cam_face_info` | Geom Properties | quick_cam_tools | `quick_cam_face_info` | — |
| `ysug:quick_cam_high_box` | Max Box | quick_cam_tools | `quick_cam_high_box` | — |
| `ysug:quick_cam_holder_library` | Holder Library | quick_cam_System_Tools | `quick_cam_holder_library` | — |
| `ysug:quick_cam_hole_hollow` | Bottom Flatting | quick_cam_tools | `quick_cam_hole_hollow` | — |
| `ysug:quick_cam_import_draw` | Import Sheet | quick_cam_Draw_Tools | `quick_cam_import_draw` | — |
| `ysug:quick_cam_input_inf` | Elec Attributes | quick_cam_Ele_Tools | `quick_cam_input_inf` | — |
| `ysug:quick_cam_layer_set` | Layer Set | quick_cam_small_tools / quick_cam_tools | `quick_cam_layer_set` | — |
| `ysug:quick_cam_min_tool_len` | Report Shortest Tool | quick_cam_Cam_Tools | `quick_cam_min_tool_len` | — |
| `ysug:quick_cam_mirror` | Mirroring | quick_cam_Ele_Tools | `quick_cam_mirror` | — |
| `ysug:quick_cam_move_body_up` | Right Position | quick_cam_tools | `quick_cam_move_body_up` | — |
| `ysug:quick_cam_move_to_origin` | Elec Move Back | quick_cam_Ele_Tools | `quick_cam_move_to_origin` | — |
| `ysug:quick_cam_multi_auto_cam` | Elec AutoCAM Batch | quick_cam_Cam_Tools | `quick_cam_multi_auto_cam` | — |
| `ysug:quick_cam_multi_base` | Elec Base Batching | quick_cam_Ele_Tools | `quick_cam_multi_base` | — |
| `ysug:quick_cam_multi_group` | Create Program Group | quick_cam_Cam_Tools | `quick_cam_multi_group` | — |
| `ysug:quick_cam_multi_post_sheet` | Batch Post/Shopdoc | quick_cam_Cam_Tools | `quick_cam_multi_post_sheet` | — |
| `ysug:quick_cam_multi_subtract` | Batch Subtract | quick_cam_Ele_Tools | `quick_cam_multi_subtract` | — |
| `ysug:quick_cam_name_switch` | Name Display | quick_cam_Ele_Tools | `quick_cam_name_switch` | — |
| `ysug:quick_cam_next_body_layer` | Layer Next With Solid | quick_cam_small_tools | `quick_cam_next_body_layer` | — |
| `ysug:quick_cam_next_drawing` | Sheet Next | quick_cam_small_tools | `quick_cam_next_drawing` | — |
| `ysug:quick_cam_next_layer` | Layer Next | quick_cam_small_tools / quick_cam_tools | `quick_cam_next_layer` | — |
| `ysug:quick_cam_note` | Quick Note | quick_cam_Draw_Tools | `quick_cam_note` | — |
| `ysug:quick_cam_offset_extrude` | Offset  Extrude | quick_cam_Ele_Tools | `quick_cam_offset_extrude` | — |
| `ysug:quick_cam_open_part_folder` | Current Dir | quick_cam_small_tools | `quick_cam_open_part_folder` | — |
| `ysug:quick_cam_part_origin` | Part Positioning | quick_cam_tools | `quick_cam_part_origin` | — |
| `ysug:quick_cam_plunge_corner` | Plunge Corner | quick_cam_Cam_Tools | `quick_cam_plunge_corner` | — |
| `ysug:quick_cam_points_split` | 2Point Split | quick_cam_tools | `quick_cam_points_split` | — |
| `ysug:quick_cam_polyon_split` | Polygon Split | quick_cam_tools | `quick_cam_polyon_split` | — |
| `ysug:quick_cam_polyon_trim` | Polygon Trim | quick_cam_tools | `quick_cam_polyon_trim` | — |
| `ysug:quick_cam_post_excel` | Excel Shopdoc | quick_cam_Cam_Tools | `quick_cam_post_excel` | — |
| `ysug:quick_cam_post_sheet` | Post/Shopdoc | quick_cam_Cam_Tools | `quick_cam_post_sheet` | — |
| `ysug:quick_cam_print` | 批量打印 | quick_cam_System_Tools | `quick_cam_print` | — |
| `ysug:quick_cam_print1` | Print | quick_cam_Draw_Tools | `quick_cam_print1` | — |
| `ysug:quick_cam_queue_list` | Elec Line Bom | quick_cam_Ele_Draw | `quick_cam_queue_list` | — |
| `ysug:quick_cam_rectangle_split` | Rect Split | quick_cam_tools | `quick_cam_rectangle_split` | — |
| `ysug:quick_cam_rectangle_trim` | Rect Trim | quick_cam_tools | `quick_cam_rectangle_trim` | — |
| `ysug:quick_cam_remove_parameters` | Remove Parameters | quick_cam_small_tools / quick_cam_tools | `quick_cam_remove_parameters` | — |
| `ysug:quick_cam_replace_face` | Replace Face | quick_cam_tools | `quick_cam_replace_face` | — |
| `ysug:quick_cam_rib_ele` | Rib Strengthen | quick_cam_Ele_Tools | `quick_cam_rib_ele` | — |
| `ysug:quick_cam_set_face_color` | Face Color | quick_cam_small_tools | `quick_cam_set_face_color` | — |
| `ysug:quick_cam_set_layer` | Elec Layering | quick_cam_Ele_Tools | `quick_cam_set_layer` | — |
| `ysug:quick_cam_set_only_display` | Only Display | quick_cam_small_tools | `quick_cam_set_only_display` | — |
| `ysug:quick_cam_set_oper_param` | Set CAM Param | quick_cam_Cam_Tools | `quick_cam_set_oper_param` | — |
| `ysug:quick_cam_set_translucency` | Make Transparent | quick_cam_small_tools / quick_cam_tools | `quick_cam_set_translucency` | — |
| `ysug:quick_cam_set_wcs` | WCS Set | quick_cam_tools | `quick_cam_set_wcs` | — |
| `ysug:quick_cam_show_sheet` | Browse Sheet | quick_cam_Draw_Tools | `quick_cam_show_sheet` | — |
| `ysug:quick_cam_solbox` | Simple MaxBox | quick_cam_tools | `quick_cam_solbox` | — |
| `ysug:quick_cam_specify_floor` | Elec Bottom Face | quick_cam_Ele_Tools | `quick_cam_specify_floor` | — |
| `ysug:quick_cam_split` | Smart Split | quick_cam_tools | `quick_cam_split` | — |
| `ysug:quick_cam_split2` | Smart Split(NoNeedSolid) | quick_cam_tools | `quick_cam_split2` | — |
| `ysug:quick_cam_split_body` | Number Split | quick_cam_tools | `quick_cam_split_body` | — |
| `ysug:quick_cam_steady_line` | Runner Line | quick_cam_tools | `quick_cam_steady_line` | — |
| `ysug:quick_cam_steel_cam` | Steel CAM | quick_cam_Cam_Tools | `quick_cam_steel_cam` | — |
| `ysug:quick_cam_surface_flatten` | Face Flatting | quick_cam_tools | `quick_cam_surface_flatten` | — |
| `ysug:quick_cam_system_setting` | StarCAM Customer Defaults | quick_cam_System_Tools | `quick_cam_system_setting` | — |
| `ysug:quick_cam_text` | Texting | quick_cam_tools | `quick_cam_text` | — |
| `ysug:quick_cam_tool_offset` | Tool Z Offset | quick_cam_Cam_Tools | `quick_cam_tool_offset` | — |
| `ysug:quick_cam_toollib_manage` | Tool Library | quick_cam_System_Tools | `quick_cam_toollib_manage` | — |
| `ysug:quick_cam_total_draw` | EDM Draft All In One | quick_cam_Ele_Draw | `quick_cam_total_draw` | — |
| `ysug:quick_cam_transf_config_data` | Transform config File | quick_cam_System_Tools | `quick_cam_transf_config_data` | — |
| `ysug:quick_cam_transform` | Move Object | quick_cam_tools | `quick_cam_transform` | — |
| `ysug:quick_cam_trim_body` | Solid Dresser | quick_cam_tools | `quick_cam_trim_body` | — |
| `ysug:quick_cam_trim_high` | Batch Z Triming | quick_cam_Ele_Tools | `quick_cam_trim_high` | — |
| `ysug:quick_cam_up_body_layer` | Layer Back With Solid | quick_cam_small_tools | `quick_cam_up_body_layer` | — |
| `ysug:quick_cam_up_drawing` | Sheet Back | quick_cam_small_tools | `quick_cam_up_drawing` | — |
| `ysug:quick_cam_up_layer` | Layer Back | quick_cam_small_tools / quick_cam_tools | `quick_cam_up_layer` | — |
| `ysug:quick_cam_wcs_back` | BACK | quick_cam_wcs_view | `quick_cam_wcs_back` | — |
| `ysug:quick_cam_wcs_bottom` | BOTTOM | quick_cam_wcs_view | `quick_cam_wcs_bottom` | — |
| `ysug:quick_cam_wcs_front` | FRONT | quick_cam_wcs_view | `quick_cam_wcs_front` | — |
| `ysug:quick_cam_wcs_left` | LEFT | quick_cam_wcs_view | `quick_cam_wcs_left` | — |
| `ysug:quick_cam_wcs_right` | RIGHT | quick_cam_wcs_view | `quick_cam_wcs_right` | — |
| `ysug:quick_cam_wcs_tfr` | TFR-ISO | quick_cam_wcs_view | `quick_cam_wcs_tfr` | — |
| `ysug:quick_cam_wcs_top` | TOP | quick_cam_wcs_view | `quick_cam_wcs_top` | — |
| `ysug:quick_cam_wedm_hole` | WEDM PreHole | quick_cam_tools | `quick_cam_wedm_hole` | — |

### 动作类型：无ACTIONS（62 条）

| 复合键 | 中文名 | 菜单 | ACTIONS | 快捷键 |
|---|---|---|---|---|
| `ysug:UGMGR_SHOW_TC_INFO_ON_DISPLAYED_PART` | （无标签） | — | `—` | — |
| `ysug:UG_ASSY_WORK_ON_DISPLAYED_ASSEMBLY` | （无标签） | — | `—` | — |
| `ysug:UG_EDIT_PASTE` | （无标签） | — | `—` | — |
| `ysug:UG_EDIT_PASTE_SPECIAL` | （无标签） | — | `—` | — |
| `ysug:UG_SKETCH_ORIENT_VIEW_TO_SKETCH` | （无标签） | — | `—` | — |
| `ysug:UG_TOOLS_REPEAT_LAST_COMMAND_0` | （无标签） | UG_TOOLS_REPEAT_VIEW_MENU | `—` | — |
| `ysug:UG_TOOLS_REPEAT_LAST_COMMAND_1` | （无标签） | UG_TOOLS_REPEAT_VIEW_MENU | `—` | — |
| `ysug:UG_TOOLS_REPEAT_LAST_COMMAND_2` | （无标签） | UG_TOOLS_REPEAT_VIEW_MENU | `—` | — |
| `ysug:UG_TOOLS_REPEAT_LAST_COMMAND_3` | （无标签） | UG_TOOLS_REPEAT_VIEW_MENU | `—` | — |
| `ysug:UG_TOOLS_REPEAT_LAST_COMMAND_4` | （无标签） | UG_TOOLS_REPEAT_VIEW_MENU | `—` | — |
| `ysug:UG_TOOLS_REPEAT_LAST_COMMAND_5` | （无标签） | UG_TOOLS_REPEAT_VIEW_MENU | `—` | — |
| `ysug:UG_TOOLS_REPEAT_LAST_COMMAND_6` | （无标签） | UG_TOOLS_REPEAT_VIEW_MENU | `—` | — |
| `ysug:UG_TOOLS_REPEAT_LAST_COMMAND_7` | （无标签） | UG_TOOLS_REPEAT_VIEW_MENU | `—` | — |
| `ysug:UG_TOOLS_REPEAT_LAST_COMMAND_8` | （无标签） | UG_TOOLS_REPEAT_VIEW_MENU | `—` | — |
| `ysug:UG_TOOLS_REPEAT_LAST_COMMAND_9` | （无标签） | UG_TOOLS_REPEAT_VIEW_MENU | `—` | — |
| `ysug:UG_VIEW_POPUP_CLEAR_ROTATION_REFERENCE` | （无标签） | — | `—` | — |
| `ysug:UG_VIEW_POPUP_EXIT_CUSTOM_SYMBOL_EDIT` | （无标签） | — | `—` | — |
| `ysug:UG_VIEW_POPUP_FACE_ANALYSIS` | （无标签） | UG_VIEW_POPUP_RENDERING_STYLE | `—` | — |
| `ysug:UG_VIEW_POPUP_FINISH_CUSTOM_SYMBOL_EDIT` | （无标签） | — | `—` | — |
| `ysug:UG_VIEW_POPUP_FIT` | （无标签） | — | `—` | — |
| `ysug:UG_VIEW_POPUP_FIT_ALL` | （无标签） | — | `—` | — |
| `ysug:UG_VIEW_POPUP_NAV_APPLY` | （无标签） | — | `—` | — |
| `ysug:UG_VIEW_POPUP_NAV_BACK` | （无标签） | — | `—` | — |
| `ysug:UG_VIEW_POPUP_NAV_CANCEL` | （无标签） | — | `—` | — |
| `ysug:UG_VIEW_POPUP_NAV_OK` | （无标签） | — | `—` | — |
| `ysug:UG_VIEW_POPUP_ORIENT_BACK` | （无标签） | UG_VIEW_POPUP_ORIENT_VIEW | `—` | — |
| `ysug:UG_VIEW_POPUP_ORIENT_BOTTOM` | （无标签） | UG_VIEW_POPUP_ORIENT_VIEW | `—` | — |
| `ysug:UG_VIEW_POPUP_ORIENT_FRONT` | （无标签） | UG_VIEW_POPUP_ORIENT_VIEW | `—` | — |
| `ysug:UG_VIEW_POPUP_ORIENT_LEFT` | （无标签） | UG_VIEW_POPUP_ORIENT_VIEW | `—` | — |
| `ysug:UG_VIEW_POPUP_ORIENT_MD` | （无标签） | UG_VIEW_POPUP_ORIENT_VIEW | `—` | — |
| `ysug:UG_VIEW_POPUP_ORIENT_RIGHT` | （无标签） | UG_VIEW_POPUP_ORIENT_VIEW | `—` | — |
| `ysug:UG_VIEW_POPUP_ORIENT_TFRISO` | （无标签） | UG_VIEW_POPUP_ORIENT_VIEW | `—` | — |
| `ysug:UG_VIEW_POPUP_ORIENT_TFRTRI` | （无标签） | UG_VIEW_POPUP_ORIENT_VIEW | `—` | — |
| `ysug:UG_VIEW_POPUP_ORIENT_TOP` | （无标签） | UG_VIEW_POPUP_ORIENT_VIEW | `—` | — |
| `ysug:UG_VIEW_POPUP_PARTIALLY_SHADED` | （无标签） | UG_VIEW_POPUP_RENDERING_STYLE | `—` | — |
| `ysug:UG_VIEW_POPUP_QUICK_PICK` | （无标签） | — | `—` | — |
| `ysug:UG_VIEW_POPUP_REFRESH` | （无标签） | — | `—` | — |
| `ysug:UG_VIEW_POPUP_REPLACE_BACK` | （无标签） | UG_VIEW_POPUP_REPLACE_VIEW | `—` | — |
| `ysug:UG_VIEW_POPUP_REPLACE_BOTTOM` | （无标签） | UG_VIEW_POPUP_REPLACE_VIEW | `—` | — |
| `ysug:UG_VIEW_POPUP_REPLACE_FRONT` | （无标签） | UG_VIEW_POPUP_REPLACE_VIEW | `—` | — |
| `ysug:UG_VIEW_POPUP_REPLACE_LEFT` | （无标签） | UG_VIEW_POPUP_REPLACE_VIEW | `—` | — |
| `ysug:UG_VIEW_POPUP_REPLACE_MD` | （无标签） | UG_VIEW_POPUP_REPLACE_VIEW | `—` | — |
| `ysug:UG_VIEW_POPUP_REPLACE_RIGHT` | （无标签） | UG_VIEW_POPUP_REPLACE_VIEW | `—` | — |
| `ysug:UG_VIEW_POPUP_REPLACE_TFRISO` | （无标签） | UG_VIEW_POPUP_REPLACE_VIEW | `—` | — |
| `ysug:UG_VIEW_POPUP_REPLACE_TFRTRI` | （无标签） | UG_VIEW_POPUP_REPLACE_VIEW | `—` | — |
| `ysug:UG_VIEW_POPUP_REPLACE_TOP` | （无标签） | UG_VIEW_POPUP_REPLACE_VIEW | `—` | — |
| `ysug:UG_VIEW_POPUP_RESTORE_ORIGINAL` | （无标签） | — | `—` | — |
| `ysug:UG_VIEW_POPUP_SELECT_WORK` | （无标签） | — | `—` | — |
| `ysug:UG_VIEW_POPUP_SET_ROTATION_REFERENCE` | （无标签） | — | `—` | — |
| `ysug:UG_VIEW_POPUP_SHADED` | （无标签） | UG_VIEW_POPUP_RENDERING_STYLE | `—` | — |
| `ysug:UG_VIEW_POPUP_SHADED_WITH_EDGES` | （无标签） | UG_VIEW_POPUP_RENDERING_STYLE | `—` | — |
| `ysug:UG_VIEW_POPUP_STATIC_WIREFRAME` | （无标签） | UG_VIEW_POPUP_RENDERING_STYLE | `—` | — |
| `ysug:UG_VIEW_POPUP_STUDIO` | （无标签） | UG_VIEW_POPUP_RENDERING_STYLE | `—` | — |
| `ysug:UG_VIEW_POPUP_UNDO` | （无标签） | — | `—` | — |
| `ysug:UG_VIEW_POPUP_UPDATE` | （无标签） | — | `—` | — |
| `ysug:UG_VIEW_POPUP_WIREFRAME_WITH_DIM_EDGES` | （无标签） | UG_VIEW_POPUP_RENDERING_STYLE | `—` | — |
| `ysug:UG_VIEW_POPUP_WIREFRAME_WITH_HIDDEN_EDGES` | （无标签） | UG_VIEW_POPUP_RENDERING_STYLE | `—` | — |
| `ysug:UG_VIEW_SHADED_BACKGROUND_BLACK` | （无标签） | UG_VIEW_POPUP_BACKGROUND_MENU | `—` | — |
| `ysug:UG_VIEW_SHADED_BACKGROUND_GRADUATED_DARK_GREY` | （无标签） | UG_VIEW_POPUP_BACKGROUND_MENU | `—` | — |
| `ysug:UG_VIEW_SHADED_BACKGROUND_GRADUATED_LIGHT_GREY` | （无标签） | UG_VIEW_POPUP_BACKGROUND_MENU | `—` | — |
| `ysug:UG_VIEW_SHADED_BACKGROUND_PURE_WHITE` | （无标签） | UG_VIEW_POPUP_BACKGROUND_MENU | `—` | — |
| `ysug:UG_VIEW_SHADED_BACKGROUND_WHITE` | （无标签） | UG_VIEW_POPUP_BACKGROUND_MENU | `—` | — |

### 动作类型：模块文件（61 条）

| 复合键 | 中文名 | 菜单 | ACTIONS | 快捷键 |
|---|---|---|---|---|
| `ysug:3264` | 8.位数匹配检测 | K_XGGJ | `3264.grx` | — |
| `ysug:3views` | 2.零件三视图 | K_BCFZ | `3view.grx` | — |
| `ysug:BATCHPOST5` | 1.NC批处理 | K_BCFZ | `Batch_Post.dll` | — |
| `ysug:BODYCOLORS` | 3.实体着色 | K_MXZL | `BodyColor.grx` | — |
| `ysug:BodyMass` | 4.干涉检查 | K_JCSC | `Intfer1.5.grx` | — |
| `ysug:ClearGroup` | 24.图层清理 | K_MXZL | `ClearGroup.grx` | — |
| `ysug:Comp_rename` | 7.装配改名 | K_MXZL | `CompRename.utd` | — |
| `ysug:Cursor_circle` | 1.动态圆圈 | K_JCSC | `Cursor_Circle.dll` | — |
| `ysug:FACEANGLE` | 2.报告斜度 | K_JCSC | `FaceAngle.grx` | — |
| `ysug:GenSave` | 5.计算刀路并关机 | K_BCFZ | `GenSave.dll` | — |
| `ysug:INCH2M` | 1.公英制转换 | K_XGGJ | `Inch2M.grx` | — |
| `ysug:KROTATE` | 6.零件旋转 | K_MXZL | `rotate.grx` | — |
| `ysug:K_Bear` | 15.熊族看看 | K_BCFZ | `K_Bear.grx` | — |
| `ysug:K_Calc` | 6.计算器 | K_XGGJ | `K_Calc.grx` | — |
| `ysug:K_Chajiao` | 12.插角辅助几何 | K_BCFZ | `Chajiao.utd` | — |
| `ysug:K_Moon` | 7.月光宝盒 | K_XGGJ | `K_moon.grx` | — |
| `ysug:K_OpRemarkAtt` | 3.程序单备注 | K_BCFZ | `K_OpRemarkAtt.grx` | — |
| `ysug:K_PATH2CURVE` | 14.刀路转曲线 | K_BCFZ | `K_path2curve.grx` | — |
| `ysug:K_Paralist` | 11.查看程序参数 | K_BCFZ | `Para_list.dll` | — |
| `ysug:K_Rcolor` | 4.R角着色 | K_MXZL | `Color_R.grx` | — |
| `ysug:K_Scallop` | 16.步距计算 | K_BCFZ | `K_Scallop.grx` | — |
| `ysug:K_Snap` | 5.截图工具 | K_XGGJ | `K_Snap.grx` | — |
| `ysug:K_ToTop` | 11.三花聚顶 | K_MXZL | `K_ToTop.grx` | — |
| `ysug:K_ToolAction` | 13.刀具位置验证 | K_BCFZ | `ToolAction.grx` | — |
| `ysug:K_Zcolor` | 5.Z平面着色 | K_MXZL | `Color_Z.grx` | — |
| `ysug:K_export` | 5.导出部件 | K_JCSC | `K_export.grx` | — |
| `ysug:K_geom_set` | 10.批量更换坐标系 | K_BCFZ | `geom_set.dll` | — |
| `ysug:K_partnumber` | 4.标记编号 | K_SJFZ | `PartNumber.grx` | — |
| `ysug:K_shop` | 4.NC程序单 | K_BCFZ | `K_shop2.60.grx` | — |
| `ysug:K_stockset` | 7.批量修改程序参数 | K_BCFZ | `Stock_set.dll` | — |
| `ysug:K_toolchange` | 9.批量更换刀具 | K_BCFZ | `ToolChange.dll` | — |
| `ysug:K_toolnumber` | 8.批量修改刀号 | K_BCFZ | `K_ToolNum.grx` | — |
| `ysug:K_trans` | 10.增量复制 | K_MXZL | `K_trans.grx` | — |
| `ysug:Kcylinderline` | 15.两点圆柱 | K_MXZL | `2p-cylinder.grx` | — |
| `ysug:LayerNames` | 8.图层工具 | K_MXZL | `Layer.utd` | — |
| `ysug:NCPROG5` | 6.NC程序组 | K_BCFZ | `Prog_Edit.dll` | — |
| `ysug:Openprtdir` | 2.文件路径 | K_XGGJ | `Open_Prt_Dir.grx` | — |
| `ysug:PartBackup` | 3.文件备份 | K_XGGJ | `beifen.grx` | — |
| `ysug:Remove_Para` | 1.删除参数 | K_MXZL | `Remove_Parameters.dll` | — |
| `ysug:SETTRANSL` | 2.设置透明 | K_MXZL | `Set_translucency.grx` | — |
| `ysug:Sizeinfor` | 8.尺寸盒子 | K_JCSC | `Sizeinfor.grx` | — |
| `ysug:TransFace55` | 16.斗转星移 | K_MXZL | `TransFace.dll` | — |
| `ysug:attbom` | 3.零件BOM | K_SJFZ | `K_bom.grx` | — |
| `ysug:atttools` | 2.属性工具 | K_SJFZ | `att.utd` | — |
| `ysug:booleansubtract` | 19.多对多布尔减 | K_MXZL | `Subtract.grx` | — |
| `ysug:color_circle` | 22.圆圈染色 | K_MXZL | `color_circle.grx` | — |
| `ysug:createtext` | 20.刻字 | K_MXZL | `kz.grx` | — |
| `ysug:cylinder245` | 12.孔柱工具 | K_MXZL | `cylinder.grx` | — |
| `ysug:guanyuhaoq` | 6.更多more... | KASA | `guanyu.grx` | — |
| `ysug:hebing` | 4.多文件合并 | K_XGGJ | `hebing.grx` | — |
| `ysug:inline5` | 9.排料工具 | K_MXZL | `in_line.grx` | — |
| `ysug:isocrv` | 13.曲面中线 | K_MXZL | `isocrv.grx` | — |
| `ysug:offset5` | 17.批量偏置面 | K_MXZL | `Offset_face.dll` | — |
| `ysug:protocolor` | 21.穿透染色 | K_MXZL | `ProtoColor.grx` | — |
| `ysug:pt_rect` | 23.中心点矩形 | K_MXZL | `Pt_Rect.grx` | — |
| `ysug:quick_cam_calculator` | Calculator | quick_cam_System_Tools | `calc.grx` | — |
| `ysug:replacefaces1` | 18.批量替换面 | K_MXZL | `Replace_face.dll` | — |
| `ysug:standpart5` | 1.标准零件 | K_SJFZ | `standard_v2.60.grx` | — |
| `ysug:tolerplus` | 9.添加公差 | K_JCSC | `tolerplus.grx` | — |
| `ysug:ug2dxf` | 7.图纸转DXF | K_JCSC | `UG2DXF.dll` | — |
| `ysug:xyzzuobiao` | 6.xyz坐标 | K_JCSC | `xyz.grx` | — |

### 动作类型：绝对路径（38 条）

| 复合键 | 中文名 | 菜单 | ACTIONS | 快捷键 |
|---|---|---|---|---|
| `ysug:ABS_BTN` | 8 ABS的浇口推荐尺寸 | 1 | `D:\YSUG\application\ABS.dlg` | — |
| `ysug:COLDGATE_BTN` | 2 冷流道系统浇口计算 | 1 | `D:\YSUG\application\coldgate.dlg` | — |
| `ysug:COLDRUNNER_BTN` | 1 冷流道系统流道计算 | 1 | `D:\YSUG\application\coldrunner.dlg` | — |
| `ysug:CONNECTOR_BTN` | A DME喉咀 | 4 | `D:\YSUG\application\connector.grx` | — |
| `ysug:DME_SPRING_BTN` | F DME弹簧 | 4 | `D:\YSUG\application\dme_spring.grx` | — |
| `ysug:DP_BTN` | 5 DME管钉 | 3 | `D:\YSUG\application\dp.grx` | — |
| `ysug:EGP_BTN` | G DME中托边 | 4 | `D:\YSUG\application\egp.grx` | — |
| `ysug:EJP_BTN` | 6 DME顶针 | 3 | `D:\YSUG\application\ejp.grx` | — |
| `ysug:EJP_SUB` | 7 DME顶针修剪 | 3 | `D:\YSUG\application\ejp_sub.grx` | — |
| `ysug:EPS` | 0 DME司筒针 | 3 | `D:\YSUG\application\eps.grx` | — |
| `ysug:EXTENSION_BTN` | B DME加长喉咀 | 4 | `D:\YSUG\application\extension.grx` | — |
| `ysug:FEED` | 校核线速度Vc | YSUG2018 / YSUG | `D:\YSUG\application\feed.grx` | — |
| `ysug:FEP_BTN` | 9 DME扁顶针 | 3 | `D:\YSUG\application\fep.grx` | — |
| `ysug:FHCS_BTN` | 2 DME平头螺丝 | 3 | `D:\YSUG\application\fhcs.grx` | — |
| `ysug:FT_MT_BTN` | E DME圆对锁 | 4 | `D:\YSUG\application\ft_mt.grx` | — |
| `ysug:GATEBANANCE_BTN` | 4 多型腔浇口平衡值的计算 | 1 | `D:\YSUG\application\gatebanance.dlg` | — |
| `ysug:GBP_BTN` | H DME导柱导套 | 4 | `D:\YSUG\application\gbp.grx` | — |
| `ysug:GEAR2` | 变位齿轮 | 2 | `D:\YSUG\application\gear2.grx` | — |
| `ysug:GS_BTN` | 4 DME无头螺丝 | 3 | `D:\YSUG\application\gs.grx` | — |
| `ysug:INNERHOTRUNNER_BTN` | 5 内热式热流道系统 | 1 | `D:\YSUG\application\innerhotrunner.dlg` | — |
| `ysug:LOCATING_BTN` | 7 DME定位环 | 4 | `D:\YSUG\application\locating.grx` | — |
| `ysug:LRBS_BTN` | 6 DME司筒针 | 3 | `D:\YSUG\application\eps-in.grx` | — |
| `ysug:MULTICAVITY_BTN` | 3 冷流道多型腔分流道计算 | 1 | `D:\YSUG\application\multicavity.dlg` | — |
| `ysug:NYLON_BTN` | 9 尼龙类的浇口推荐值 | 1 | `D:\YSUG\application\nylon.dlg` | — |
| `ysug:ORING_BTN` | C 美国PARKER胶圈 | 4 | `D:\YSUG\application\oring.grx` | — |
| `ysug:OUTHOTRUNNER_BTN` | 6 外热式热流道系统 | 1 | `D:\YSUG\application\outhotrunner.dlg` | — |
| `ysug:PINPOINT_BTN` | 7 点浇口的直径与允许最大流率 | 1 | `D:\YSUG\application\pinpoint.dlg` | — |
| `ysug:PIPE_BTN` | 0 DME喉塞 | 4 | `D:\YSUG\application\pipe.grx` | — |
| `ysug:PLM_PLF_BTN` | D DME边锁 | 4 | `D:\YSUG\application\plm_plf.grx` | — |
| `ysug:SEP_BTN` | 8 DME有托顶针 | 3 | `D:\YSUG\application\sep.grx` | — |
| `ysug:SHCS_BTN` | 1 DME杯头螺丝 | 3 | `D:\YSUG\application\shcs.grx` | — |
| `ysug:SHSB_BTN` | 3 DME塞打螺丝 | 3 | `D:\YSUG\application\shsb.grx` | — |
| `ysug:SPRUE_BTN` | 8 DME唧咀 | 4 | `D:\YSUG\application\sprue.grx` | — |
| `ysug:SPRUE_SUB_BTN` | 9 唧咀司 | 4 | `D:\YSUG\application\sprue_sub.grx` | — |
| `ysug:VOLUME_BTN` | 0 依塑件体积选择点浇口直径 | 1 | `D:\YSUG\application\volume.dlg` | — |
| `ysug:YS` | D 外挂更新 | YSUG2018 / YSUG | `D:\YSUG\application\ys.grx` | — |
| `ysug:YSUG` | E 微信技术支持 | YSUG2018 / YSUG | `D:\YSUG\application\ysug.grx` | — |
| `ysug:spring` | 普通弹簧 | 2 | `D:\YSUG\application\spring.grx` | — |

### 动作类型：环境变量（1 条）

| 复合键 | 中文名 | 菜单 | ACTIONS | 快捷键 |
|---|---|---|---|---|
| `ysug:dir` | C 文件路径 | YSUG2018 / YSUG | `${KASA_DIR}\application\Open_Prt_Dir.grx` | — |

## 四、标准调用流程（Agent 必须按此执行）

1. `list_plugins()` 确认该外挂已注册、`version_ok_for_nx12=true`。
2. `search('<中文名>', plugin='ysug')` 定位候选，拿到复合键。
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

