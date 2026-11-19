# 外挂分册：LM 插件（`lm_nxplugins`）

> 版本：**NX12.0-CN**　|　厂商目录：`YANGJEE/LM_NXPlugins`
> 命令数：112（中文标签 0）
> 风险等级：**LOW**　|　证据：E1-MEDIA（GBK/UTF-8 嗅探解码，直接解析介质 .men；已按 NX12 版本目录过滤）
> **非 Siemens 官方功能**，输出时必须向用户明确标注为第三方外挂。

## 一、能力卡

- 菜单文件：1 个，已排除其它 NX 版本菜单 0 个
- 文件编码：{'utf-8': 1}
- 菜单版本：{'120': 1}（NX12 应为 120）
- 动作形态：{'其他': 112}
- 硬编码绝对路径：0 处
- 环境变量依赖：0 处
- 跨外挂重名命令 ID：0 个（必须用复合键 `lm_nxplugins:<ID>`）

## 二、调用前的硬性检查

- ✅ 命令键必须用命名空间：`plugin_id:command_id`；裸 ID 会被判为歧义。

## 三、命令清单

### 动作类型：其他（112 条）

| 复合键 | 中文名 | 菜单 | ACTIONS | 快捷键 |
|---|---|---|---|---|
| `lm_nxplugins:nx_about` | About NXPlugins | NX_TOOL | `nx_about` | — |
| `lm_nxplugins:nx_abs_wcs` | Set absolute coordinates | NX_TOOL_common | `nx_abs_wcs` | — |
| `lm_nxplugins:nx_analysis_measuring` | Analytical measurement entity | NX_TOOL_analysis | `nx_analysis_measuring` | — |
| `lm_nxplugins:nx_atc_ele` | Atc electrode head | NX_TOOL_electrode | `nx_atc_ele` | — |
| `lm_nxplugins:nx_batch_create_tool` | Batch creation tool | NX_TOOL_program | `nx_batch_create_tool` | — |
| `lm_nxplugins:nx_batch_name` | Batch electrode naming | NX_TOOL_electrode | `nx_batch_name` | — |
| `lm_nxplugins:nx_batch_print` | Batch print | NX_TOOL_drawing | `nx_batch_print` | — |
| `lm_nxplugins:nx_boundary_box` | Multi-function boundary box | NX_TOOL_common | `nx_boundary_box` | — |
| `lm_nxplugins:nx_calc` | calculator | NX_TOOL_other | `nx_calc` | — |
| `lm_nxplugins:nx_cam_set_ele_param` | Batch set spark a | NX_TOOL_program | `nx_cam_set_ele_param` | — |
| `lm_nxplugins:nx_centre_line_point` | Entity center line/point | NX_TOOL_common | `nx_centre_line_point` | — |
| `lm_nxplugins:nx_changing_mcs` | Batch change coordinates | NX_TOOL_program | `nx_changing_mcs` | — |
| `lm_nxplugins:nx_changing_tool` | Batch tool replacement | NX_TOOL_program | `nx_changing_tool` | — |
| `lm_nxplugins:nx_clear_highlight` | Clear highlighted object | NX_TOOL_other | `nx_clear_highlight` | — |
| `lm_nxplugins:nx_coloring` | Colored object | NX_TOOL_common | `nx_coloring` | — |
| `lm_nxplugins:nx_come_key_set` | Combination shortcut Settings | NX_TOOL_system | `nx_come_key_set` | — |
| `lm_nxplugins:nx_creat_ele_base` | Creat base | NX_TOOL_electrode | `nx_creat_ele_base` | — |
| `lm_nxplugins:nx_creat_ld_line_face` | Flow center line/surface | NX_TOOL_common | `nx_creat_ld_line_face` | — |
| `lm_nxplugins:nx_decimals` | Set the decimal point | NX_TOOL_other | `nx_decimals` | — |
| `lm_nxplugins:nx_def_cam_points` | Batch specified feed point | NX_TOOL_program | `nx_def_cam_points` | — |
| `lm_nxplugins:nx_def_ele_inf` | Set electrode information | NX_TOOL_electrode | `nx_def_ele_inf` | — |
| `lm_nxplugins:nx_del_disp_objects` | Delete  displayed object | NX_TOOL_other | `nx_del_disp_objects` | — |
| `lm_nxplugins:nx_del_ele_names` | Delete electrode name | NX_TOOL_electrode | `nx_del_ele_names` | — |
| `lm_nxplugins:nx_down_drawing` | Open next sheet | NX_TOOL_drawing | `nx_down_drawing` | — |
| `lm_nxplugins:nx_down_have_obj_layer` | Open down object layer | NX_TOOL_other | `nx_down_have_obj_layer` | — |
| `lm_nxplugins:nx_down_work_layer` | Set down work layer | NX_TOOL_other | `nx_down_work_layer` | — |
| `lm_nxplugins:nx_dwg_annotation` | Drawings annotation | NX_TOOL_drawing | `nx_dwg_annotation` | — |
| `lm_nxplugins:nx_dynamic_analysis` | Geometric dynamic attribute | NX_TOOL_analysis | `nx_dynamic_analysis` | — |
| `lm_nxplugins:nx_dynamic_circle` | Dynamic circle 2D | NX_TOOL_common | `nx_dynamic_circle` | — |
| `lm_nxplugins:nx_edm_drawing` | Edm sheet | NX_TOOL_drawing | `nx_edm_drawing` | — |
| `lm_nxplugins:nx_ele_check` | Electrode check | NX_TOOL_electrode | `nx_ele_check` | — |
| `lm_nxplugins:nx_ele_color` | Analytical electrode color | NX_TOOL_electrode | `nx_ele_color` | — |
| `lm_nxplugins:nx_ele_home_origin` | Electrode return origin | NX_TOOL_electrode | `nx_ele_home_origin` | — |
| `lm_nxplugins:nx_ele_inf_edit` | Edit electrode information | NX_TOOL_electrode | `nx_ele_inf_edit` | — |
| `lm_nxplugins:nx_ele_oper_sheet` | Electrode post/sheet | NX_TOOL_program | `nx_ele_oper_sheet` | — |
| `lm_nxplugins:nx_ele_ranking` | Electrode arrangement | NX_TOOL_electrode | `nx_ele_ranking` | — |
| `lm_nxplugins:nx_ele_stock_list` | Single electrode bom | NX_TOOL_electrode | `nx_ele_stock_list` | — |
| `lm_nxplugins:nx_ele_tl_stock_list` | Long electrode bom | NX_TOOL_electrode | `nx_ele_tl_stock_list` | — |
| `lm_nxplugins:nx_enhance_rib` | Add rib | NX_TOOL_electrode | `nx_enhance_rib` | — |
| `lm_nxplugins:nx_export_electrode` | Batch export electrode | NX_TOOL_electrode | `nx_export_electrode` | — |
| `lm_nxplugins:nx_extract_boundary` | Extract the boundary | NX_TOOL_common | `nx_extract_boundary` | — |
| `lm_nxplugins:nx_extruded_sheet` | Quickly extension sheet | NX_TOOL_common | `nx_extruded_sheet` | — |
| `lm_nxplugins:nx_hole_floor_favoid` | Batch to avoid floor | NX_TOOL_common | `nx_hole_floor_favoid` | — |
| `lm_nxplugins:nx_ini_modl_number` | Initialize/edit mold number | NX_TOOL_drawing | `nx_ini_modl_number` | — |
| `lm_nxplugins:nx_inquire_min_r` | Query minimum R value | NX_TOOL_analysis | `nx_inquire_min_r` | — |
| `lm_nxplugins:nx_kz` | Parts lettering | NX_TOOL_common | `nx_kz` | — |
| `lm_nxplugins:nx_measure_angle` | Quick measurement Angle | NX_TOOL_analysis | `nx_measure_angle` | — |
| `lm_nxplugins:nx_modl_color` | Steel analysis of color | NX_TOOL_common | `nx_modl_color` | — |
| `lm_nxplugins:nx_nc_program` | Create program group | NX_TOOL_program | `nx_nc_program` | — |
| `lm_nxplugins:nx_onekey_notlucency_no` | A key no transparent | NX_TOOL_other | `nx_onekey_tlucency_no` | — |
| `lm_nxplugins:nx_onekey_tlucency` | A key transparent | NX_TOOL_other | `nx_onekey_tlucency` | — |
| `lm_nxplugins:nx_open_the_folder` | Open the current parts directory | NX_TOOL_common | `nx_open_the_folder` | — |
| `lm_nxplugins:nx_part_names` | Parts named | NX_TOOL_common | `nx_part_names` | — |
| `lm_nxplugins:nx_plane_trim_body` | Plane trimmed solid | NX_TOOL_common | `nx_plane_trim_body` | — |
| `lm_nxplugins:nx_planish_surface` | Planish surface | NX_TOOL_common | `nx_planish_surface` | — |
| `lm_nxplugins:nx_point_split_x` | Point division [X direction] | NX_TOOL_common | `nx_point_split_x` | — |
| `lm_nxplugins:nx_point_split_y` | Point division [Y direction] | NX_TOOL_common | `nx_point_split_y` | — |
| `lm_nxplugins:nx_point_split_z` | Point division [Z direction] | NX_TOOL_common | `nx_point_split_z` | — |
| `lm_nxplugins:nx_polyline_split` | Polygon split entities | NX_POL_ST | `nx_polyline_split` | — |
| `lm_nxplugins:nx_polyline_trim` | Polygon trim entities | NX_POL_ST | `nx_polyline_trim` | — |
| `lm_nxplugins:nx_preview_drawings` | Preview  sheet | NX_TOOL_drawing | `nx_preview_drawings` | — |
| `lm_nxplugins:nx_quick_ele_kz` | Batch electrode lettering | NX_TOOL_electrode | `nx_quick_ele_kz` | — |
| `lm_nxplugins:nx_quick_extruded` | Quickly extension entity | NX_TOOL_common | `nx_quick_extruded` | — |
| `lm_nxplugins:nx_quick_mirror` | Fast mirror | NX_TOOL_common | `nx_quick_mirror` | — |
| `lm_nxplugins:nx_quick_split` | Split entities quickly | NX_QUICK_ST | `nx_quick_split` | — |
| `lm_nxplugins:nx_quick_split_1` | Split entities quickly(choose body) | NX_QUICK_ST | `nx_quick_split_1` | — |
| `lm_nxplugins:nx_rectangular_split` | Rectangle split entities | NX_REC_ST | `nx_rectangular_split` | — |
| `lm_nxplugins:nx_rectangular_trim` | Rectangle trim entities | NX_REC_ST | `nx_rectangular_trim` | — |
| `lm_nxplugins:nx_relocation_objects` | Quickly location part | NX_TOOL_common | `nx_relocation_objects` | — |
| `lm_nxplugins:nx_remove_parameters` | Remove parameters | NX_TOOL_other | `nx_remove_parameters` | — |
| `lm_nxplugins:nx_replace_face` | Advanced replace surface | NX_TOOL_common | `nx_replace_face` | — |
| `lm_nxplugins:nx_rotate_objects` | Quickly rotate part | NX_TOOL_common | `nx_rotate_objects` | — |
| `lm_nxplugins:nx_select_area` | Batch Select area | NX_TOOL_program | `nx_select_area` | — |
| `lm_nxplugins:nx_set_adjust` | Batch set adjust register | NX_TOOL_program | `nx_set_adjust` | — |
| `lm_nxplugins:nx_set_cut_methot` | Batch set cut method | NX_TOOL_program | `nx_set_cut_methot` | — |
| `lm_nxplugins:nx_set_cutcom` | Batch set cutcom register | NX_TOOL_program | `nx_set_cutcom` | — |
| `lm_nxplugins:nx_set_dk` | Batch change tool toollibrary | NX_TOOL_program | `nx_set_dk` | — |
| `lm_nxplugins:nx_set_engage_retract` | Batch set engage retract | NX_TOOL_program | `nx_set_engage_retract` | — |
| `lm_nxplugins:nx_set_feed` | Batch set feed | NX_TOOL_program | `nx_set_feed` | — |
| `lm_nxplugins:nx_set_sf` | Batch change speed | NX_TOOL_program | `nx_set_sf` | — |
| `lm_nxplugins:nx_set_speed` | Batch set speed | NX_TOOL_program | `nx_set_speed` | — |
| `lm_nxplugins:nx_set_st` | Batch change stock tol | NX_TOOL_program | `nx_set_st` | — |
| `lm_nxplugins:nx_set_tolerance` | Batch set tolerance | NX_TOOL_program | `nx_set_tolerance` | — |
| `lm_nxplugins:nx_set_tool_number` | Batch set tool number | NX_TOOL_program | `nx_set_tool_number` | — |
| `lm_nxplugins:nx_set_transfermd` | Batch jump cut method | NX_TOOL_program | `nx_set_transfermd` | — |
| `lm_nxplugins:nx_set_traverse` | Batch set traverse | NX_TOOL_program | `nx_set_traverse` | — |
| `lm_nxplugins:nx_set_zoffset` | Batch offset Z | NX_TOOL_program | `nx_set_zoffset` | — |
| `lm_nxplugins:nx_simple_box` | Simple boundary box | NX_TOOL_common | `nx_simple_box` | — |
| `lm_nxplugins:nx_simple_measuring` | Simple measuring | NX_TOOL_analysis | `nx_simple_measuring` | — |
| `lm_nxplugins:nx_single_ele_name` | Single electrode naming | NX_TOOL_electrode | `nx_single_ele_name` | — |
| `lm_nxplugins:nx_specify_dface` | Electrode underside identification | NX_TOOL_electrode | `nx_specify_dface` | — |
| `lm_nxplugins:nx_specify_dpoint` | Specify electrode reference points | NX_TOOL_electrode | `nx_specify_dpoint` | — |
| `lm_nxplugins:nx_steel_oper_sheet` | General post/sheet | NX_TOOL_program | `nx_steel_oper_sheet` | — |
| `lm_nxplugins:nx_straighten_object` | Quickly True up part | NX_TOOL_common | `nx_straighten_object` | — |
| `lm_nxplugins:nx_switch_name` | Name display switch | NX_TOOL_other | `nx_switch_name` | — |
| `lm_nxplugins:nx_tr_jm` | Property transfer jm | NX_TOOL_other | `nx_tr_jm` | — |
| `lm_nxplugins:nx_transform_object` | move objects | NX_TOOL_common | `nx_transform_object` | — |
| `lm_nxplugins:nx_transparency` | Entity/surface transparency | NX_TOOL_common | `nx_transparency` | — |
| `lm_nxplugins:nx_trim_full_size` | Trim solid shape | NX_TOOL_common | `nx_trim_full_size` | — |
| `lm_nxplugins:nx_two_define_plane` | Two draw face | NX_TOOL_common | `nx_two_define_plane` | — |
| `lm_nxplugins:nx_two_points_split` | Two draw split | NX_TOOL_common | `nx_two_points_split` | — |
| `lm_nxplugins:nx_up_drawing` | Open last sheet | NX_TOOL_drawing | `nx_up_drawing` | — |
| `lm_nxplugins:nx_up_have_obj_layer` | Open up object layer | NX_TOOL_other | `nx_up_have_obj_layer` | — |
| `lm_nxplugins:nx_up_work_layer` | Set up work layer | NX_TOOL_other | `nx_up_work_layer` | — |
| `lm_nxplugins:nx_user_settings` | User default Settings | NX_TOOL_system | `nx_user_settings` | — |
| `lm_nxplugins:nx_wcs_view_back` | Relative coordinates back view | NX_WCS_VIEW | `nx_wcs_view_back` | — |
| `lm_nxplugins:nx_wcs_view_bottom` | Relative coordinates bottom view | NX_WCS_VIEW | `nx_wcs_view_bottom` | — |
| `lm_nxplugins:nx_wcs_view_front` | Relative coordinates front view | NX_WCS_VIEW | `nx_wcs_view_front` | — |
| `lm_nxplugins:nx_wcs_view_left` | Relative coordinates left view | NX_WCS_VIEW | `nx_wcs_view_left` | — |
| `lm_nxplugins:nx_wcs_view_right` | Relative coordinates right view | NX_WCS_VIEW | `nx_wcs_view_right` | — |
| `lm_nxplugins:nx_wcs_view_tfr_iso` | Relative coordinates tfr-iso view | NX_WCS_VIEW | `nx_wcs_view_tfr_iso` | — |
| `lm_nxplugins:nx_wcs_view_top` | Relative coordinates top view | NX_WCS_VIEW | `nx_wcs_view_top` | — |

## 四、标准调用流程（Agent 必须按此执行）

1. `list_plugins()` 确认该外挂已注册、`version_ok_for_nx12=true`。
2. `search('<中文名>', plugin='lm_nxplugins')` 定位候选，拿到复合键。
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

