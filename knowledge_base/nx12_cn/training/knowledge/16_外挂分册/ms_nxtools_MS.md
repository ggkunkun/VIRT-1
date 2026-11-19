# 外挂分册：MS 工具箱（`ms_nxtools`）

> 版本：**NX12.0-CN**　|　厂商目录：`MS_NXTOOLS`
> 命令数：146（中文标签 0）
> 风险等级：**MEDIUM**　|　证据：E1-MEDIA（GBK/UTF-8 嗅探解码，直接解析介质 .men；已按 NX12 版本目录过滤）
> **非 Siemens 官方功能**，输出时必须向用户明确标注为第三方外挂。

## 一、能力卡

- 菜单文件：5 个，已排除其它 NX 版本菜单 0 个
- 文件编码：{'utf-8': 5}
- 菜单版本：{'120': 5}（NX12 应为 120）
- 动作形态：{'环境变量': 69, '其他': 77}
- 硬编码绝对路径：0 处
- 环境变量依赖：69 处，示例：`${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll`
- 跨外挂重名命令 ID：0 个（必须用复合键 `ms_nxtools:<ID>`）

## 二、调用前的硬性检查

- ⚠️ **环境变量**：ACTIONS 依赖环境变量，NX 启动前必须已设置。

- ✅ 命令键必须用命名空间：`plugin_id:command_id`；裸 ID 会被判为歧义。

## 三、命令清单

### 动作类型：其他（77 条）

| 复合键 | 中文名 | 菜单 | ACTIONS | 快捷键 |
|---|---|---|---|---|
| `ms_nxtools:MS_BISECTOR_LINE_BTN` | Bisector Line | MS_GENERAL_MENU_BTN | `MS_BISECTOR_LINE` | — |
| `ms_nxtools:MS_BLEND_OR_CHAMFER_BTN` | Blend/Chamfer | MS_GENERAL_MENU_BTN | `MS_BLEND_OR_CHAMFER` | — |
| `ms_nxtools:MS_BODIES_TO_ASSEM_BTN` | Bodies To Assembly | MS_GENERAL_MENU_BTN | `MS_BODIES_TO_ASSEM` | — |
| `ms_nxtools:MS_BODIES_WEIGHT_BTN` | Quality Analysis | MS_ANALYSIS_TOOLS_MENU_BTN | `MS_BODIES_WEIGHT` | — |
| `ms_nxtools:MS_BODY_INFORMATION_BTN` | Body Information | MS_ANALYSIS_TOOLS_MENU_BTN | `MS_BODY_INFORMATION` | — |
| `ms_nxtools:MS_BOUNDING_BODY_BTN` | Bounding Box | MS_GENERAL_MENU_BTN | `MS_BOUNDING_BODY` | — |
| `ms_nxtools:MS_CAM_EDIT_PARAMETERS_BTN` | Operation Parameters | MS_CAM_SETTING_BTN | `MS_CAM_EDIT_PARAMETERS` | — |
| `ms_nxtools:MS_CAM_ENGAGE_POINTS_BTN` | Engage Points | MS_CAM_SETTING_BTN | `MS_CAM_ENGAGE_POINTS` | — |
| `ms_nxtools:MS_CAM_GROUP_FEATURES_BTN` | Group Features | — | `MS_CAM_GROUP_FEATURES` | — |
| `ms_nxtools:MS_CAM_MCS_TO_WCS_BTN` | MCS To WCS | — | `MS_CAM_MCS_TO_WCS` | — |
| `ms_nxtools:MS_CAM_PROGRAM_GROUP_BTN` | Program Group | — | `MS_CAM_PROGRAM_GROUP` | — |
| `ms_nxtools:MS_CAM_WCS_TO_MCS_BTN` | WCS To MCS | — | `MS_CAM_WCS_TO_MCS` | — |
| `ms_nxtools:MS_CENTER_LINE_BTN` | Center Line | MS_GENERAL_MENU_BTN | `MS_CENTER_LINE` | — |
| `ms_nxtools:MS_COLOR_TOOL_BTN` | Color Tool | MS_ANALYSIS_TOOLS_MENU_BTN | `MS_COLOR_TOOL` | — |
| `ms_nxtools:MS_COORDINATE_NOTE_BTN` | Coordinate Note | MS_ANALYSIS_TOOLS_MENU_BTN | `MS_COORDINATE_NOTE` | — |
| `ms_nxtools:MS_CORNER_DESIGN_BTN` | Corner Design | MS_GENERAL_MENU_BTN | `MS_CORNER_DESIGN` | — |
| `ms_nxtools:MS_DELETE_FACE_BTN` | Delete Face | MS_GENERAL_MENU_BTN | `MS_DELETE_FACE` | — |
| `ms_nxtools:MS_DEL_IDENTICAL_OBJS_BTN` | Delete Identical Objects | MS_GENERAL_MENU_BTN | `MS_DEL_IDENTICAL_OBJS` | — |
| `ms_nxtools:MS_DRF_COORDINATE_NOTE_BTN` | Coordinate Note | MS_DRAFTING_MENU_BTN | `MS_DRF_COORDINATE_NOTE` | — |
| `ms_nxtools:MS_DRF_GRID_LINE_BTN` | Grid Line | MS_DRAFTING_MENU_BTN | `MS_DRF_GRID_LINE` | — |
| `ms_nxtools:MS_DRF_HOLE_NOTE_BTN` | Hole Note | MS_DRAFTING_MENU_BTN | `MS_DRF_HOLE_NOTE` | — |
| `ms_nxtools:MS_DRF_MULTIPLE_TEMPLATES_BTN` | Multiple Templates | MS_DRAFTING_MENU_BTN | `MS_DRF_MULTIPLE_TEMPLATES` | — |
| `ms_nxtools:MS_DYNAMIC_CIRCLE_BTN` | Dynamic Circle | MS_ANALYSIS_TOOLS_MENU_BTN | `MS_DYNAMIC_CIRCLE` | — |
| `ms_nxtools:MS_ELE_ARRANGEMENT_BTN` | Electrode Arrangement | MS_ELE_DESIGN_BTN | `MS_ELE_ARRANGEMENT` | — |
| `ms_nxtools:MS_ELE_AUTO_DRAWING_BTN` | Automatic Electrode Drawing | MS_ELE_DWG_BTN | `MS_ELE_AUTO_DRAWING` | — |
| `ms_nxtools:MS_ELE_BLANK_BTN` | Design Electrode Blank | MS_ELE_DESIGN_BTN | `MS_ELE_BLANK` | — |
| `ms_nxtools:MS_ELE_BOSS_BTN` | Electrode Boss | MS_ELE_DESIGN_BTN | `MS_ELE_BOSS` | Ctrl+Shift+Alt+F12 |
| `ms_nxtools:MS_ELE_CARVE_TEXT_BTN` | Electrode Carve Text | MS_ELE_DESIGN_BTN | `MS_ELE_CARVE_TEXT` | — |
| `ms_nxtools:MS_ELE_EXPORT_BTN` | Export Electrode | MS_ELE_DESIGN_BTN | `MS_ELE_EXPORT` | — |
| `ms_nxtools:MS_ELE_INFORMATION_BTN` | Manage Ele Attribute | MS_ELE_DESIGN_BTN | `MS_ELE_INFORMATION` | — |
| `ms_nxtools:MS_ELE_SET_GAP_INFO_BTN` | Set Ele Infos | MS_ELE_DESIGN_BTN | `MS_ELE_SET_GAP_INFO` | — |
| `ms_nxtools:MS_ELE_STOCK_LIST_BTN` | Electrode Stock List | MS_ELE_DWG_BTN | `MS_ELE_STOCK_LIST` | — |
| `ms_nxtools:MS_EXTRUDE_HOLE_BTN` | Extrude Hole | MS_GENERAL_MENU_BTN | `MS_EXTRUDE_HOLE` | — |
| `ms_nxtools:MS_FILTER_TO_CURVE_BTN` | Select Curve | MS_SELECTION_CASCADE_BTN | `MS_FILTER_TO_CURVE` | — |
| `ms_nxtools:MS_FILTER_TO_EDGE_BTN` | Select Edge | MS_SELECTION_CASCADE_BTN | `MS_FILTER_TO_EDGE` | — |
| `ms_nxtools:MS_FILTER_TO_FACE_BTN` | Select Face | MS_SELECTION_CASCADE_BTN | `MS_FILTER_TO_FACE` | — |
| `ms_nxtools:MS_FILTER_TO_NONE_BTN` | No Selection Filter | MS_SELECTION_CASCADE_BTN | `MS_FILTER_TO_NONE` | — |
| `ms_nxtools:MS_FILTER_TO_POINT_BTN` | Select Point | MS_SELECTION_CASCADE_BTN | `MS_FILTER_TO_POINT` | — |
| `ms_nxtools:MS_FILTER_TO_SHEET_BODY_BTN` | Sheet Body | MS_SELECTION_CASCADE_BTN | `MS_FILTER_TO_SHEET_BODY` | — |
| `ms_nxtools:MS_FILTER_TO_SOLID_BODY_BTN` | Select Body | MS_SELECTION_CASCADE_BTN | `MS_FILTER_TO_SOLID_BODY` | — |
| `ms_nxtools:MS_GEOMTRIC_PROPERTIES_BTN` | Geometric Properties | MS_ANALYSIS_TOOLS_MENU_BTN | `MS_GEOMTRIC_PROPERTIES` | — |
| `ms_nxtools:MS_HIDE_ALL_LAYER_BTN` | Hide All Layer | MS_LAYER_CASCADE_BTN | `MS_HIDE_ALL_LAYER` | — |
| `ms_nxtools:MS_HOLE_COLOR_BTN` | Hole Color | MS_ANALYSIS_TOOLS_MENU_BTN | `MS_HOLE_COLOR` | — |
| `ms_nxtools:MS_IMPORT_EXPORT_BTN` | Import/Export | MS_GENERAL_MENU_BTN | `MS_IMPORT_EXPORT` | — |
| `ms_nxtools:MS_JOIN_CURVE_BTN` | Join Curve | MS_GENERAL_MENU_BTN | `MS_JOIN_CURVE` | — |
| `ms_nxtools:MS_LAYER_SETTINGS_BTN` | Layer Settings | MS_GENERAL_MENU_BTN | `MS_LAYER_SETTINGS` | — |
| `ms_nxtools:MS_MODEL_ANALYSIS_BTN` | Model Analysis | MS_ANALYSIS_TOOLS_MENU_BTN | `MS_MODEL_ANALYSIS` | — |
| `ms_nxtools:MS_MOLD_CHECK_CHANNEL_BTN` | Check Channel | MS_GENERAL_MENU_BTN / MS_MOLD_MENU_BTN | `MS_MOLD_CHECK_CHANNEL` | — |
| `ms_nxtools:MS_NEXT_LAYER_BTN` | Next Layer | MS_LAYER_CASCADE_BTN | `MS_NEXT_LAYER` | — |
| `ms_nxtools:MS_NEXT_OBJECT_LAYER_BTN` | Next Object Layer | MS_LAYER_CASCADE_BTN | `MS_NEXT_OBJECT_LAYER` | — |
| `ms_nxtools:MS_NEXT_SOLID_LAYER_BTN` | Next Solid Layer | MS_LAYER_CASCADE_BTN | `MS_NEXT_SOLID_LAYER` | — |
| `ms_nxtools:MS_NOTE_TO_CURVE_BTN` | Recognition Text | MS_GENERAL_MENU_BTN | `MS_RECOGNITION_TEXT` | — |
| `ms_nxtools:MS_OPEN_PART_DIRECTORY_BTN` | Open Part Directory | MS_SYSTEM_TOOLS_MENU_BTN | `MS_OPEN_PART_DIRECTORY` | — |
| `ms_nxtools:MS_OPER_ENGRAVE_BTN` | Engrave Text | — | `MS_OPER_ENGRAVE` | — |
| `ms_nxtools:MS_OPER_V_CHAMFER_BTN` | Vertical Chamfer Milling | — | `MS_OPER_V_CHAMFER` | — |
| `ms_nxtools:MS_ORIENTATION_BODY_BTN` | Orientation Body | MS_GENERAL_MENU_BTN | `MS_ORIENTATION_BODY` | — |
| `ms_nxtools:MS_ORIENT_BODY_BTN` | Orient | MS_GENERAL_MENU_BTN | `MS_ORIENT_BODY` | — |
| `ms_nxtools:MS_PART_OUTLINE_BTN` | Part Outline | MS_GENERAL_MENU_BTN | `MS_PART_OUTLINE` | — |
| `ms_nxtools:MS_PATH_TO_CURVES_BTN` | Path To Curves | — | `MS_PATH_TO_CURVES` | — |
| `ms_nxtools:MS_PLUNGE_MILLING_BTN` | Plunge Milling | — | `MS_PLUNGE_MILLING` | — |
| `ms_nxtools:MS_PREFERENCES_BTN` | Preferences | MS_SYSTEM_TOOLS_MENU_BTN | `MS_PREFERENCES` | — |
| `ms_nxtools:MS_PREVIOUS_LAYER_BTN` | Previous Layer | MS_LAYER_CASCADE_BTN | `MS_PREVIOUS_LAYER` | — |
| `ms_nxtools:MS_PREVIOUS_OBJECT_LAYER_BTN` | Previous Object Layer | MS_LAYER_CASCADE_BTN | `MS_PREVIOUS_OBJECT_LAYER` | — |
| `ms_nxtools:MS_PREVIOUS_SOLID_LAYER_BTN` | Previous Solid Layer | MS_LAYER_CASCADE_BTN | `MS_PREVIOUS_SOLID_LAYER` | — |
| `ms_nxtools:MS_RADIUS_INFORMATION_BTN` | Radius Information | MS_ANALYSIS_TOOLS_MENU_BTN | `MS_RADIUS_INFORMATION` | — |
| `ms_nxtools:MS_REMOVE_HIGHLIGHTS_BTN` | Remove Highlights | MS_ANALYSIS_TOOLS_MENU_BTN | `MS_REMOVE_HIGHLIGHTS` | — |
| `ms_nxtools:MS_REMOVE_PARAMS_BTN` | Remove Parameters | MS_GENERAL_MENU_BTN | `MS_REMOVE_PARAMS` | — |
| `ms_nxtools:MS_RESET_COLOR_BTN` | Reset Object Color | MS_ANALYSIS_TOOLS_MENU_BTN | `MS_RESET_COLOR` | — |
| `ms_nxtools:MS_RESET_LAYER_BTN` | Reset Layer | MS_LAYER_CASCADE_BTN | `MS_RESET_LAYER` | — |
| `ms_nxtools:MS_RESIZE_BODY_BTN` | Resize Body | MS_GENERAL_MENU_BTN | `MS_RESIZE_BODY` | — |
| `ms_nxtools:MS_REVERSE_NOTE_BTN` | Reverse Note | MS_GENERAL_MENU_BTN | `MS_REVERSE_NOTE` | — |
| `ms_nxtools:MS_SHAPE_SEARCH_BTN` | Shape Search | MS_ANALYSIS_TOOLS_MENU_BTN | `MS_SHAPE_SEARCH` | — |
| `ms_nxtools:MS_SHOW_ALL_LAYER_BTN` | Show All Layer | MS_LAYER_CASCADE_BTN | `MS_SHOW_ALL_LAYER` | — |
| `ms_nxtools:MS_SPLIT_BODY_BTN` | Split Body | MS_GENERAL_MENU_BTN | `MS_SPLIT_BODY` | — |
| `ms_nxtools:MS_TF_ORIENTATION_BTN` | TF Orientation | MS_GENERAL_MENU_BTN | `MS_TF_ORIENTATION` | — |
| `ms_nxtools:MS_TRANSLUCENCY_TOOL_BTN` | Translucency | MS_ANALYSIS_TOOLS_MENU_BTN | `MS_TRANSLUCENCY_TOOL` | — |
| `ms_nxtools:MS_UPDATE_MOSM_BTN` | Update Tool | MS_TOOLS_MENU_MAIN | `MS_UPDATE_MOSM` | — |

### 动作类型：环境变量（69 条）

| 复合键 | 中文名 | 菜单 | ACTIONS | 快捷键 |
|---|---|---|---|---|
| `ms_nxtools:MS_ABOUT_MOSM_BTN` | About Mosm | MS_TOOLS_MENU_MAIN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_BIN_PACKING_BTN` | Auto Bin Packing | MS_GENERAL_MENU_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_APPROVE_OBJECTS_BTN` | Approve | — | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_AUXILIARY_BTN` | CAM Assistant | — | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_BATCHES_BTN` | CAM Batches | MS_CAM_TOOLS_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_BATCH_RENAME` | Operation Rename | — | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_BATCH_TOOL_LEN_BTN` | Pattern Path | — | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_BLANK_BOUNDARY_BTN` | Blank Boundary | MS_CAM_SETTING_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_CHECK_BODY_BTN` | Check Body | — | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_CHECK_BOUNDARY_BTN` | Check Boundary | MS_CAM_SETTING_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_CLEANUP_OPER_OBJ_BTN` | Cleanup | MS_CAM_SETTING_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_CREATE_NOTE_BTN` | Note | MS_CAM_DATA_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_CURVE_DRIVE_BTN` | Curve Drive | MS_CAM_SETTING_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_CUTTER_LIBRARY_BTN` | Cutter Library | MS_CAM_DATA_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_CUTTER_SELECTOR_BTN` | Cutter Selector | MS_CAM_DATA_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_CUTTER_Z_OFFSET_BTN` | Z Offset | — | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_CUT_LEVEL_BTN` | Cut Levels | — | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_CUT_PARAM_TEMPLATE_BTN` | Cut Param Template | — | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_EDIT_CUTTER_BTN` | Edit Cutter | MS_CAM_DATA_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_EDIT_HOLDER_BTN` | Edit Holder | — | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_EXPAND_SEL_GROUP_BTN` | Expand Selected Group | — | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_EXPORT_CUTTER_BTN` | Export Cutter | MS_CAM_DATA_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_FAST_COPY` | Fast Copy | — | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_GOUGE_CHECK_BTN` | Gouge Check | — | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_HOLE_GEOMS_BTN` | Hole Geometry | MS_CAM_SETTING_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_HOLE_PARAMS_BTN` | Hole Parameter | MS_CAM_SETTING_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_HOLE_SEQUENCE_BTN` | Hole Sequence | MS_CAM_SETTING_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_INHERIT_SETTING_BTN` | Inherit Setting | MS_CAM_SETTING_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_NEW_CUTTER_BTN` | Create Tool | MS_CAM_DATA_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_NON_CUTTING_MOVES_BTN` | Non Cutting Moves | — | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_OFFSET_SHEET_BTN` | Area Protection | MS_GENERAL_MENU_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_PARAM_SHEET_TEMPLATE_BTN` | Program Sheet Template | MS_CAM_DATA_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_PART_BOUNDARY_BTN` | Part Boundary | MS_CAM_SETTING_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_PASTE_INSIDE_BTN` | Paste Inside | — | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_POST_SHEET_BTN` | Post Process | — | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_PRETREATMENT_BTN` | CAM Positioning | — | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_PROFILE_3D_BTN` | Profile 3D | — | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_RAMP_ANGLE_BTN` | Ramp Angle | MS_CAM_SETTING_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_REPORT_SHORTEST_TOOL_BTN` | Report Shortest Tool | — | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_RUNNER_OPER_BTN` | Runner Operation | — | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_SAVE_CUTTER_BTN` | Save Cutter | MS_CAM_DATA_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_SET_CUT_AREA_BTN` | Cut Area | MS_CAM_SETTING_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_SET_DESCRIBE` | Setting description | — | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_SET_HOLDER_BTN` | Setting Holder | — | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_SET_LPLANE_FLOOR_BTN` | Specify Floor | MS_CAM_SETTING_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_SET_OPER_TEXT_BTN` | Planar Text | MS_CAM_SETTING_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_SHOW_GEOMETRY_BTN` | Show Geometry | — | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_SPECIFY_BLANK_BTN` | Specify Blank | MS_CAM_SETTING_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_SPECIFY_CHECK_BODY_BTN` | Specify Check | MS_CAM_SETTING_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_SPECIFY_PART_BTN` | Specify Part | MS_CAM_SETTING_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_SPECIFY_WALL` | Specify Walls | MS_CAM_SETTING_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_TOOL_NUMBER_BTN` | Tool Number | — | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_TRIM_BOUNDARY_BTN` | Trim Boundary | MS_CAM_SETTING_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CAM_UNAPPROVE_OBJECTS_BTN` | Unapprove | — | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_CURVE_TEXT_BTN` | Curve Text | MS_GENERAL_MENU_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_DIVIDE_TOOL_PATH_BTN` | Tool Path Divide | — | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_DRAWING_PREVIEW_BTN` | Drawing Preview | MS_GENERAL_MENU_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\libmsmfctools.dll` | — |
| `ms_nxtools:MS_EDIT_TOOL_PATH_BTN` | Edit Tool Path | — | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_ELE_AUTO_PROGRAM_BTN` | Ele Auto Cam | MS_CAM_TOOLS_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_ELE_TOUCH_BODY_BTN` | Touch Body | MS_ELE_DESIGN_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_FILL_HOLE_BTN` | Fill Hole | MS_GENERAL_MENU_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_FREE_PLANE_MILL_BTN` | Free Plane Mill | — | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_HASP_PASSWORD_BTN` | Hasp Password | MS_SYSTEM_TOOLS_MENU_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_MODEL_COMPARE_BTN` | Model Compare | MS_ANALYSIS_TOOLS_MENU_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_PATH_DISPLAY_BTN` | Path Display | — | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_PATH_FIRST_CUT_BTN` | First Cut | — | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_REFIT_FACE_BTN` | Refit Face | MS_GENERAL_MENU_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_SELECT_OBJECTS_BTN` | Select Object | MS_GENERAL_MENU_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |
| `ms_nxtools:MS_SUPER_TOOLBAR_BTN` | Super Toolbar | MS_GENERAL_MENU_BTN | `${MS_NX_BASE_DIR}\application\dlls\x64\MSLoaddll.dll` | — |

## 四、标准调用流程（Agent 必须按此执行）

1. `list_plugins()` 确认该外挂已注册、`version_ok_for_nx12=true`。
2. `search('<中文名>', plugin='ms_nxtools')` 定位候选，拿到复合键。
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

