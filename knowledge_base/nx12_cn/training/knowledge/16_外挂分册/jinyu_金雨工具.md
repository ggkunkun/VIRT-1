# 外挂分册：金雨工具 jinyu（`jinyu`）

> 版本：**NX12.0-CN**　|　厂商目录：`YANGJEE/jinyu`
> 命令数：201（中文标签 201）
> 风险等级：**MEDIUM**　|　证据：E1-MEDIA（GBK/UTF-8 嗅探解码，直接解析介质 .men；已按 NX12 版本目录过滤）
> **非 Siemens 官方功能**，输出时必须向用户明确标注为第三方外挂。

## 一、能力卡

- 菜单文件：1 个，已排除其它 NX 版本菜单 0 个
- 文件编码：{'gbk': 1}
- 菜单版本：未声明（NX12 应为 120）
- 动作形态：{'环境变量': 201}
- 硬编码绝对路径：0 处
- 环境变量依赖：201 处，示例：`${UGII_BASE_DIR}\ugii\ju\application\create_face_box_ju.dll`
- 跨外挂重名命令 ID：0 个（必须用复合键 `jinyu:<ID>`）

## 二、调用前的硬性检查

- ⚠️ **环境变量**：ACTIONS 依赖环境变量，NX 启动前必须已设置。

- ✅ 命令键必须用命名空间：`plugin_id:command_id`；裸 ID 会被判为歧义。

## 三、命令清单

### 动作类型：环境变量（201 条）

| 复合键 | 中文名 | 菜单 | ACTIONS | 快捷键 |
|---|---|---|---|---|
| `jinyu:jum_analyze_face` | 1  分析曲面 | jum_elec_1_9 | `${UGII_BASE_DIR}\ugii\ju\application\analyze_face_ju.dll` | — |
| `jinyu:jum_analyze_face_angle` | 2  分析曲面角度 | jum_elec_1_9 | `${UGII_BASE_DIR}\ugii\ju\application\analyze_face_angle_ju.d` | — |
| `jinyu:jum_analyze_solid_min_in_r` | C  分析实体的R | jum_elec_1_9 | `${UGII_BASE_DIR}\ugii\ju\application\analyze_solid_min_in_r.` | — |
| `jinyu:jum_auto_solid_color` | 1  实体自动著色 | jum_elec_1_12 | `${UGII_BASE_DIR}\ugii\ju\application\auto_solid_color_ju.dll` | — |
| `jinyu:jum_avoid_hsk` | L 孔底避空 | jum_elec_1_1 | `${UGII_BASE_DIR}\ugii\ju\application\avoid_hsk_ju.dll` | — |
| `jinyu:jum_background_calc_disp_mfc` | K  查看后台计算列表 | jum_elec_1_7 | `${UGII_BASE_DIR}\ugii\ju\application\background_calc_disp_mf` | — |
| `jinyu:jum_background_calc_mfc` | J  启动后台计算工具 | jum_elec_1_7 | `${UGII_BASE_DIR}\ugii\ju\application\background_calc_mfc_ju.` | — |
| `jinyu:jum_batch_calc_edm_area` | C  批量计算放电面积 | jum_elec_1_3 | `${UGII_BASE_DIR}\ugii\ju\application\batch_calc_edm_area.dll` | — |
| `jinyu:jum_batch_xd_reposition` | C  批量斜顶定位 | jum_elec_1_4 | `${UGII_BASE_DIR}\ugii\ju\application\batch_xd_reposition.dll` | — |
| `jinyu:jum_blank_mr` | 9  隐藏模仁 | jum_elec_1_13 | `${UGII_BASE_DIR}\ugii\ju\application\blank_mr.dll` | — |
| `jinyu:jum_calc_mach_time` | F  电极报价单 | jum_elec_1_6 | `${UGII_BASE_DIR}\ugii\ju\application\calc_mach_time.dll` | — |
| `jinyu:jum_cam_path_transform_line` | P  刀路转曲线 | jum_elec_1_7 | `${UGII_BASE_DIR}\ugii\ju\application\cam_path_transform_line` | — |
| `jinyu:jum_change_holder` | F  换或加刀头 | jum_elec_1_7 | `${UGII_BASE_DIR}\ugii\ju\application\change_holder_ju.dll` | — |
| `jinyu:jum_cleanup_highlight_display` | 8  清除高亮显示 | jum_elec_1_13 | `${UGII_BASE_DIR}\ugii\ju\application\cleanup_highlight_displ` | — |
| `jinyu:jum_config_file_updata` | 1  更新定义文件 | jum_elec_1_18 | `${UGII_BASE_DIR}\ugii\ju\application\config_file_updata_ju.d` | — |
| `jinyu:jum_copy_elec_info` | 7  复制电极信息 | jum_elec_1_3 | `${UGII_BASE_DIR}\ugii\ju\application\copy_elec_info_ju.dll` | — |
| `jinyu:jum_copy_elec_to_layer` | 4  复制实体(电极)到图层 | jum_elec_1_14 | `${UGII_BASE_DIR}\ugii\ju\application\copy_elec_to_layer.dll` | — |
| `jinyu:jum_create_3d_elec_info_note` | B  构建3D电极信息注释 | jum_elec_1_3 | `${UGII_BASE_DIR}\ugii\ju\application\create_3d_elec_info_not` | — |
| `jinyu:jum_create_add_id_symbol` | 8  构建增量ID符号 | jum_elec_1_10 | `${UGII_BASE_DIR}\ugii\ju\application\create_add_id_symbol.dl` | — |
| `jinyu:jum_create_cam_blank` | M  构建加工毛坯体 | jum_elec_1_7 | `${UGII_BASE_DIR}\ugii\ju\application\create_cam_blank_ju.dll` | — |
| `jinyu:jum_create_center_line` | 6  以曲面构建中心线 | jum_elec_1_12 | `${UGII_BASE_DIR}\ugii\ju\application\create_center_line_ju.d` | — |
| `jinyu:jum_create_center_line_with_solid` | B  以实体构建中心线 | jum_elec_1_12 | `${UGII_BASE_DIR}\ugii\ju\application\create_center_line_with` | — |
| `jinyu:jum_create_extrude` | O 拉  伸 | jum_elec_1_1 | `${UGII_BASE_DIR}\ugii\ju\application\create_extrude_ju.dll` | — |
| `jinyu:jum_create_extrude_and_offset` | P 面偏置和拉伸 | jum_elec_1_1 | `${UGII_BASE_DIR}\ugii\ju\application\create_extrude_and_offs` | — |
| `jinyu:jum_create_face_box` | 1 曲面 box | jum_elec_1_1 | `${UGII_BASE_DIR}\ugii\ju\application\create_face_box_ju.dll` | — |
| `jinyu:jum_create_face_line` | 5  以曲面构建对角线 | jum_elec_1_12 | `${UGII_BASE_DIR}\ugii\ju\application\create_face_line_ju.dll` | — |
| `jinyu:jum_create_ld_line` | L  构建流道线 | jum_elec_1_7 | `${UGII_BASE_DIR}\ugii\ju\application\create_ld_line_ju.dll` | — |
| `jinyu:jum_create_note` | 7  构建常用注释 | jum_elec_1_10 | `${UGII_BASE_DIR}\ugii\ju\application\create_note_ju.dll` | — |
| `jinyu:jum_create_prog_name` | 5  构建NC程式名 | jum_elec_1_7 | `${UGII_BASE_DIR}\ugii\ju\application\create_prog_name_ju.dll` | — |
| `jinyu:jum_create_solid_box` | 3 实体 box | jum_elec_1_1 | `${UGII_BASE_DIR}\ugii\ju\application\create_solid_box_ju.dll` | — |
| `jinyu:jum_create_solid_line` | 4  以实体构建对角线 | jum_elec_1_12 | `${UGII_BASE_DIR}\ugii\ju\application\create_solid_line_ju.dl` | — |
| `jinyu:jum_cut_solid_side_to_int` | T 切实体边到整数 | jum_elec_1_1 | `${UGII_BASE_DIR}\ugii\ju\application\cut_solid_side_to_int.d` | — |
| `jinyu:jum_cycle_order` | Q 循环命令 | jum_elec_1_1 | `${UGII_BASE_DIR}\ugii\ju\application\cycle_order_ju.dll` | — |
| `jinyu:jum_cylinder_elec` | R 圆柱体电极 | jum_elec_1_1 | `${UGII_BASE_DIR}\ugii\ju\application\cylinder_elec_ju.dll` | — |
| `jinyu:jum_delete_clamp` | 3  删除夹具 | jum_elec_1_15 | `${UGII_BASE_DIR}\ugii\ju\application\delete_clamp.dll` | — |
| `jinyu:jum_delete_elec_base` | X 删除基准台 | jum_elec_1_1 | `${UGII_BASE_DIR}\ugii\ju\application\delete_elec_base.dll` | — |
| `jinyu:jum_delete_elec_name` | 7  删除电极名称 | jum_elec_1_2 | `${UGII_BASE_DIR}\ugii\ju\application\delete_elec_name_ju.dll` | — |
| `jinyu:jum_delete_elec_name_part` | 3  删除零件名称 | jum_elec_1_16 | `${UGII_BASE_DIR}\ugii\ju\application\delete_elec_name_ju.dll` | — |
| `jinyu:jum_delete_elec_text` | E  删除电极刻字 | jum_elec_1_2 | `${UGII_BASE_DIR}\ugii\ju\application\delete_elec_text.dll` | — |
| `jinyu:jum_delete_layer_object` | 5  删除层中的元体 | jum_elec_1_14 | `${UGII_BASE_DIR}\ugii\ju\application\delete_layer_object_ju.` | — |
| `jinyu:jum_delete_layer_remark` | 2  删除与增加层备注 | jum_elec_1_14 | `${UGII_BASE_DIR}\ugii\ju\application\delete_layer_remark.dll` | — |
| `jinyu:jum_delete_side_edm_number` | 2  删除单边碰数点 | jum_elec_1_3 | `${UGII_BASE_DIR}\ugii\ju\application\delete_side_edm_number_` | — |
| `jinyu:jum_disp_clamp` | 5  显示隐藏的夹具 | jum_elec_1_15 | `${UGII_BASE_DIR}\ugii\ju\application\disp_clamp.dll` | — |
| `jinyu:jum_disp_elec_name_and_layer` | 9  列示电极与对应的层 | jum_elec_1_2 | `${UGII_BASE_DIR}\ugii\ju\application\disp_elec_name_and_laye` | — |
| `jinyu:jum_dynamic_arc` | 7  动态画圆 | jum_elec_1_9 | `${UGII_BASE_DIR}\ugii\ju\application\dynamic_arc_ju.dll` | — |
| `jinyu:jum_edit_prog_name` | 6  修改NC程式名 | jum_elec_1_7 | `${UGII_BASE_DIR}\ugii\ju\application\edit_prog_name_ju.dll` | — |
| `jinyu:jum_elec_base` | U 基 准 台 | jum_elec_1_1 | `${UGII_BASE_DIR}\ugii\ju\application\elec_base_ju.dll` | — |
| `jinyu:jum_elec_base_cylinder` | W 圆柱基准台 | jum_elec_1_1 | `${UGII_BASE_DIR}\ugii\ju\application\elec_base_cylinder.dll` | — |
| `jinyu:jum_elec_base_wcs` | V 基准台-工作坐标构建 | jum_elec_1_1 | `${UGII_BASE_DIR}\ugii\ju\application\elec_base_wcs.dll` | — |
| `jinyu:jum_elec_check_dim` | A  电极检测图 | jum_elec_1_6 | `${UGII_BASE_DIR}\ugii\ju\application\elec_check_dim_ju.dll` | — |
| `jinyu:jum_elec_draw` | 7  一张图纸出10个电极数 | jum_elec_1_6 | `${UGII_BASE_DIR}\ugii\ju\application\elec_draw_ju.dll` | — |
| `jinyu:jum_elec_draw1` | 4  一张图纸出1层电极数 | jum_elec_1_6 | `${UGII_BASE_DIR}\ugii\ju\application\elec_draw1_ju.dll` | — |
| `jinyu:jum_elec_draw15` | 8  一张图纸出15个电极数 | jum_elec_1_6 | `${UGII_BASE_DIR}\ugii\ju\application\elec_draw15_ju.dll` | — |
| `jinyu:jum_elec_draw3` | 5  一张图纸出3个电极数 | jum_elec_1_6 | `${UGII_BASE_DIR}\ugii\ju\application\elec_draw3_ju.dll` | — |
| `jinyu:jum_elec_draw5` | 6  一张图纸出5个电极数 | jum_elec_1_6 | `${UGII_BASE_DIR}\ugii\ju\application\elec_draw5_ju.dll` | — |
| `jinyu:jum_elec_draw_a_csys_view` | 2  大众化EDM图纸坐标系方向 | jum_elec_1_6 | `${UGII_BASE_DIR}\ugii\ju\application\elec_draw_a_csys_view_j` | — |
| `jinyu:jum_elec_draw_a_dis` | 1  大众化EDM图纸电极方向常用 | jum_elec_1_6 | `${UGII_BASE_DIR}\ugii\ju\application\elec_draw_a_dis_ju.dll` | — |
| `jinyu:jum_elec_draw_a_wcs` | 3  大众化EDM工作坐标系出图 | jum_elec_1_6 | `${UGII_BASE_DIR}\ugii\ju\application\elec_draw_a_wcs.dll` | — |
| `jinyu:jum_elec_draw_is_check` | C  检测电极能否出放电数 | jum_elec_1_6 | `${UGII_BASE_DIR}\ugii\ju\application\elec_draw_is_check_ju.d` | — |
| `jinyu:jum_elec_name_copy` | 5  拷贝电极名称 | jum_elec_1_2 | `${UGII_BASE_DIR}\ugii\ju\application\elec_name_copy_ju.dll` | — |
| `jinyu:jum_elec_pw` | 3  多个铜公排成条 | jum_elec_1_4 | `${UGII_BASE_DIR}\ugii\ju\application\elec_pw_ju.dll` | — |
| `jinyu:jum_elec_pw_y_re_dist` | 7  多条电极的Y轴距离重设 | jum_elec_1_4 | `${UGII_BASE_DIR}\ugii\ju\application\elec_pw_y_re_dist.dll` | — |
| `jinyu:jum_elec_sb_pw` | 9  以锁板(间距)排位 | jum_elec_1_4 | `${UGII_BASE_DIR}\ugii\ju\application\elec_sb_pw_ju.dll` | — |
| `jinyu:jum_elec_sb_pw_draw` | D  电极锁板位置图 | jum_elec_1_6 | `${UGII_BASE_DIR}\ugii\ju\application\elec_sb_pw_draw.dll` | — |
| `jinyu:jum_elec_sb_pw_to_point` | A  锁板电极移至点 | jum_elec_1_4 | `${UGII_BASE_DIR}\ugii\ju\application\elec_sb_pw_to_point.dll` | — |
| `jinyu:jum_elec_text` | B  电极刻字--侧边 | jum_elec_1_2 | `${UGII_BASE_DIR}\ugii\ju\application\elec_text_ju.dll` | — |
| `jinyu:jum_elec_text_top_word` | C  电极刻字--顶面 | jum_elec_1_2 | `${UGII_BASE_DIR}\ugii\ju\application\elec_text_top_word_ju.d` | — |
| `jinyu:jum_elec_wcut_draw` | B  电极线割图 | jum_elec_1_6 | `${UGII_BASE_DIR}\ugii\ju\application\elec_wcut_draw.dll` | — |
| `jinyu:jum_export_assem` | 1  导出装配图档 | jum_elec_1_17 | `${UGII_BASE_DIR}\ugii\ju\application\export_assem_ju.dll` | — |
| `jinyu:jum_extract_cylinder_center_point` | 2  析出圆柱(锥)孔中心点 | jum_elec_1_11 | `${UGII_BASE_DIR}\ugii\ju\application\extract_cylinder_center` | — |
| `jinyu:jum_extract_single_line_text` | 1  析出刻字的单线字 | jum_elec_1_11 | `${UGII_BASE_DIR}\ugii\ju\application\extract_single_line_tex` | — |
| `jinyu:jum_face_box_data` | 4  曲面BOX的数据 | jum_elec_1_9 | `${UGII_BASE_DIR}\ugii\ju\application\face_box_data_ju.dll` | — |
| `jinyu:jum_face_translucency` | 1  面透明/不透明 | jum_elec_1_13 | `${UGII_BASE_DIR}\ugii\ju\application\face_translucency_ju.dl` | — |
| `jinyu:jum_face_trim_add_offset` | D 面修剪后再延伸 | jum_elec_1_1 | `${UGII_BASE_DIR}\ugii\ju\application\face_trim_add_offset_ju` | — |
| `jinyu:jum_fill_face_hole` | B  补面上的孔 | jum_elec_1_13 | `${UGII_BASE_DIR}\ugii\ju\application\fill_face_hole.dll` | — |
| `jinyu:jum_find_not_name_elec` | 8  查找未命名的电极 | jum_elec_1_2 | `${UGII_BASE_DIR}\ugii\ju\application\find_not_name_elec_ju.d` | — |
| `jinyu:jum_geometric_properties` | 3  曲面几何属性 | jum_elec_1_9 | `${UGII_BASE_DIR}\ugii\ju\application\geometric_properties.dl` | — |
| `jinyu:jum_gw_jq` | M 骨位加强-侧边 | jum_elec_1_1 | `${UGII_BASE_DIR}\ugii\ju\application\gw_jq_ju.dll` | — |
| `jinyu:jum_gw_jq_top` | N 骨位加强-顶面 | jum_elec_1_1 | `${UGII_BASE_DIR}\ugii\ju\application\gw_jq_top.dll` | — |
| `jinyu:jum_hide_clamp` | 4  隐藏夹具 | jum_elec_1_15 | `${UGII_BASE_DIR}\ugii\ju\application\hide_clamp.dll` | — |
| `jinyu:jum_import_cgm` | 6  导入CGM图档 | jum_elec_1_10 | `${UGII_BASE_DIR}\ugii\ju\application\import_cgm.dll` | — |
| `jinyu:jum_info_ju_to_other` | L  进玉信息转出到其他外挂 | jum_elec_1_3 | `${UGII_BASE_DIR}\ugii\ju\application\info_ju_to_other.dll` | — |
| `jinyu:jum_info_other_to_ju` | K  其他外挂信息转入进玉电极 | jum_elec_1_3 | `${UGII_BASE_DIR}\ugii\ju\application\info_other_to_ju.dll` | — |
| `jinyu:jum_inner_angle_avoid` | S 内角避空 | jum_elec_1_1 | `${UGII_BASE_DIR}\ugii\ju\application\inner_angle_avoid.dll` | — |
| `jinyu:jum_int_cam_list` | 1  自动刀路_列表方式 | jum_elec_1_7 | `${UGII_BASE_DIR}\ugii\ju\application\int_cam_list.dll` | — |
| `jinyu:jum_int_elec_text` | 3  电极刀路刻字 | jum_elec_1_7 | `${UGII_BASE_DIR}\ugii\ju\application\int_elec_text.dll` | — |
| `jinyu:jum_int_ps_prog` | Q  构建配数程式 | jum_elec_1_7 | `${UGII_BASE_DIR}\ugii\ju\application\int_ps_prog.dll` | — |
| `jinyu:jum_int_set_defa_list_cam_template` | O  设定电极默认的列表刀路的加工方案 | jum_elec_1_7 | `${UGII_BASE_DIR}\ugii\ju\application\int_set_defa_list_cam_t` | — |
| `jinyu:jum_integration_cam_new` | 2  自动刀路(旧的) | jum_elec_1_7 | `${UGII_BASE_DIR}\ugii\ju\application\integration_cam_new_ju.` | — |
| `jinyu:jum_layer_manager` | 1  图层管理 | jum_elec_1_14 | `${UGII_BASE_DIR}\ugii\ju\application\layer_manager.dll` | — |
| `jinyu:jum_load_clamp` | 1  加载夹具 | jum_elec_1_15 | `${UGII_BASE_DIR}\ugii\ju\application\load_clamp.dll` | — |
| `jinyu:jum_look_clamp_info` | 2  查看夹具信息 | jum_elec_1_15 | `${UGII_BASE_DIR}\ugii\ju\application\look_clamp_info.dll` | — |
| `jinyu:jum_look_elec_data` | 6  查看电极数据 | jum_elec_1_3 | `${UGII_BASE_DIR}\ugii\ju\application\look_elec_data_ju.dll` | — |
| `jinyu:jum_look_oper_info` | H  查看操作信息 | jum_elec_1_7 | `${UGII_BASE_DIR}\ugii\ju\application\look_oper_info_ju.dll` | — |
| `jinyu:jum_look_side_edm_number` | 1  查看单边碰数点 | jum_elec_1_3 | `${UGII_BASE_DIR}\ugii\ju\application\look_side_edm_number_ju` | — |
| `jinyu:jum_more_elec_from_point_to_point` | 8  平移--从点到点 | jum_elec_1_4 | `${UGII_BASE_DIR}\ugii\ju\application\more_elec_from_point_to` | — |
| `jinyu:jum_more_elec_kl` | 4  以整条铜公开料 | jum_elec_1_5 | `${UGII_BASE_DIR}\ugii\ju\application\more_elec_kl_ju.dll` | — |
| `jinyu:jum_more_elec_space_reset` | 5  一条铜公的间距重设 | jum_elec_1_4 | `${UGII_BASE_DIR}\ugii\ju\application\more_elec_space_reset_j` | — |
| `jinyu:jum_more_elec_to_one_elec` | 6  一条加入一个铜公的左或右边 | jum_elec_1_4 | `${UGII_BASE_DIR}\ugii\ju\application\more_elec_to_one_elec_j` | — |
| `jinyu:jum_more_elec_to_origin` | 4  一组电极移至原点 | jum_elec_1_4 | `${UGII_BASE_DIR}\ugii\ju\application\more_elec_to_origin_ju.` | — |
| `jinyu:jum_more_export_part` | 8  导出整条电极 | jum_elec_1_12 | `${UGII_BASE_DIR}\ugii\ju\application\more_export_part_ju.dll` | — |
| `jinyu:jum_move_solid` | B  移动实体 | jum_elec_1_4 | `${UGII_BASE_DIR}\ugii\ju\application\move_solid.dll` | — |
| `jinyu:jum_move_solid_from_wcs_to_abs` | D  元体从工作到绝对坐标系 | jum_elec_1_4 | `${UGII_BASE_DIR}\ugii\ju\application\move_solid_from_wcs_to_` | — |
| `jinyu:jum_move_solid_to_ori_with_bot_face` | E  倾斜实体(电极)摆正 | jum_elec_1_4 | `${UGII_BASE_DIR}\ugii\ju\application\move_solid_to_ori_with_` | — |
| `jinyu:jum_move_solid_with_plane_inter_point` | F  以平面的交点移动实体 | jum_elec_1_4 | `${UGII_BASE_DIR}\ugii\ju\application\move_solid_with_plane_i` | — |
| `jinyu:jum_move_tool_path` | N  移动刀路 | jum_elec_1_7 | `${UGII_BASE_DIR}\ugii\ju\application\move_tool_path.dll` | — |
| `jinyu:jum_mr_elec_total_draw` | E  模仁中的电极清检图 | jum_elec_1_6 | `${UGII_BASE_DIR}\ugii\ju\application\mr_elec_total_draw.dll` | — |
| `jinyu:jum_mr_text` | 4  模仁刻字 | jum_elec_1_7 | `${UGII_BASE_DIR}\ugii\ju\application\mr_text_ju.dll` | — |
| `jinyu:jum_mr_text_solid` | D  模仁实体刻字 | jum_elec_1_2 | `${UGII_BASE_DIR}\ugii\ju\application\mr_text_solid.dll` | — |
| `jinyu:jum_name_disp` | 2  显 示 名 称 | jum_elec_1_2 | `${UGII_BASE_DIR}\ugii\ju\application\name_disp_ju.dll` | — |
| `jinyu:jum_name_switch` | 1  名称显示开关 | jum_elec_1_2 | `${UGII_BASE_DIR}\ugii\ju\application\name_switch_ju.dll` | — |
| `jinyu:jum_note_xyz` | 8  标注 XYZ 坐标 | jum_elec_1_9 | `${UGII_BASE_DIR}\ugii\ju\application\note_xyz_ju.dll` | — |
| `jinyu:jum_obj_with_wcs_rotate_180` | G  元体以wcs坐标系旋转180度 | jum_elec_1_4 | `${UGII_BASE_DIR}\ugii\ju\application\obj_with_wcs_rotate_180` | — |
| `jinyu:jum_open_current_part_file_dir` | C  打开当前图档目录 | jum_elec_1_13 | `${UGII_BASE_DIR}\ugii\ju\application\open_current_part_file_` | — |
| `jinyu:jum_open_nc_file_dir` | 6 打开NC文件目录 | jum_elec_1_8 | `${UGII_BASE_DIR}\ugii\ju\application\open_nc_file_dir.dll` | — |
| `jinyu:jum_open_next_draw` | 2  打开下一张图纸 | jum_elec_1_10 | `${UGII_BASE_DIR}\ugii\ju\application\open_next_draw_ju.dll` | — |
| `jinyu:jum_open_preceding_draw` | 1  打开上一张图纸 | jum_elec_1_10 | `${UGII_BASE_DIR}\ugii\ju\application\open_preceding_draw_ju.` | — |
| `jinyu:jum_part_export_single_solid` | 6  导出单个零件 | jum_elec_1_16 | `${UGII_BASE_DIR}\ugii\ju\application\part_export_single_soli` | — |
| `jinyu:jum_part_set_more_part_name` | 2  批量零件名称 | jum_elec_1_16 | `${UGII_BASE_DIR}\ugii\ju\application\part_set_more_part_name` | — |
| `jinyu:jum_part_set_part_info` | 4  零件信息 | jum_elec_1_16 | `${UGII_BASE_DIR}\ugii\ju\application\part_set_part_info.dll` | — |
| `jinyu:jum_part_single_kl` | 5  零件开料 | jum_elec_1_16 | `${UGII_BASE_DIR}\ugii\ju\application\part_single_kl.dll` | — |
| `jinyu:jum_part_tran` | 9  图档转换 | jum_elec_1_12 | `${UGII_BASE_DIR}\ugii\ju\application\part_tran.dll` | — |
| `jinyu:jum_part_version_tran` | A  UG高版本转低版本 | jum_elec_1_12 | `${UGII_BASE_DIR}\ugii\ju\application\part_version_tran.dll` | — |
| `jinyu:jum_post_prog_select_elec_auto` | 2 自动换刀--电极程式单 | jum_elec_1_8 | `${UGII_BASE_DIR}\ugii\ju\application\post_prog_select_elec_a` | — |
| `jinyu:jum_post_prog_select_elec_uni` | 1 非自动换刀--电极程式单 | jum_elec_1_8 | `${UGII_BASE_DIR}\ugii\ju\application\post_prog_select_elec_u` | — |
| `jinyu:jum_post_prog_select_mr` | 3 非自动换刀--钢件程式单 | jum_elec_1_8 | `${UGII_BASE_DIR}\ugii\ju\application\post_prog_select_mr_ju.` | — |
| `jinyu:jum_post_prog_select_mr_auto` | 4 自动换刀--钢件程式单 | jum_elec_1_8 | `${UGII_BASE_DIR}\ugii\ju\application\post_prog_select_mr_aut` | — |
| `jinyu:jum_print_sheet` | 4  打印图纸 | jum_elec_1_10 | `${UGII_BASE_DIR}\ugii\ju\application\print_sheet_ju.dll` | — |
| `jinyu:jum_rect_or_polygon_trim_solid` | F 矩形分割实体 | jum_elec_1_1 | `${UGII_BASE_DIR}\ugii\ju\application\rect_or_polygon_trim_so` | — |
| `jinyu:jum_rect_quick_trim_solid` | G 矩形快速修剪实体 | jum_elec_1_1 | `${UGII_BASE_DIR}\ugii\ju\application\rect_quick_trim_solid.d` | — |
| `jinyu:jum_refresh_navigator` | A  刷新导航器 | jum_elec_1_7 | `${UGII_BASE_DIR}\ugii\ju\application\refresh_navigator_ju.dl` | — |
| `jinyu:jum_remove_all_parameters` | 4  去除所有实体与片体参数 | jum_elec_1_13 | `${UGII_BASE_DIR}\ugii\ju\application\remove_all_parameters_j` | — |
| `jinyu:jum_remove_disp_parameters` | 5  去除屏幕中显示的实体参数 | jum_elec_1_13 | `${UGII_BASE_DIR}\ugii\ju\application\remove_disp_parameters.` | — |
| `jinyu:jum_rename_elec_name_by_extract` | 6  重命名与析取电极名称 | jum_elec_1_2 | `${UGII_BASE_DIR}\ugii\ju\application\rename_elec_name_by_ext` | — |
| `jinyu:jum_replace_prog_group` | 7  替换程式组群中的部份字符 | jum_elec_1_7 | `${UGII_BASE_DIR}\ugii\ju\application\replace_prog_group_char` | — |
| `jinyu:jum_screen_to_bitmap` | 5 增加图片到Excel中 | jum_elec_1_8 | `${UGII_BASE_DIR}\ugii\ju\application\screen_to_bitmap.dll` | — |
| `jinyu:jum_set_cam_param` | G  批量设定 CAM 参数 | jum_elec_1_7 | `${UGII_BASE_DIR}\ugii\ju\application\set_cam_param_ju.dll` | — |
| `jinyu:jum_set_check_point` | 9  检测点 | jum_elec_1_9 | `${UGII_BASE_DIR}\ugii\ju\application\set_check_point_ju.dll` | — |
| `jinyu:jum_set_clamp_type` | A  设定夹具类型 | jum_elec_1_3 | `${UGII_BASE_DIR}\ugii\ju\application\set_clamp_type_ju.dll` | — |
| `jinyu:jum_set_edm_sheet_ori_point_and_axis` | 9  设定放电原点与轴向 | jum_elec_1_6 | `${UGII_BASE_DIR}\ugii\ju\application\set_edm_sheet_ori_point` | — |
| `jinyu:jum_set_elec_base_bottom_translucency` | 3  基准台顶面透明 | jum_elec_1_13 | `${UGII_BASE_DIR}\ugii\ju\application\set_elec_base_bottom_tr` | — |
| `jinyu:jum_set_elec_belong_mold_part_no` | F  设定电极所属模号零件号 | jum_elec_1_3 | `${UGII_BASE_DIR}\ugii\ju\application\set_elec_belong_mold_pa` | — |
| `jinyu:jum_set_elec_edm_dir_face` | 9  设定放电方向面 | jum_elec_1_3 | `${UGII_BASE_DIR}\ugii\ju\application\set_elec_edm_dir_face_j` | — |
| `jinyu:jum_set_elec_note` | 4  电极注释 | jum_elec_1_3 | `${UGII_BASE_DIR}\ugii\ju\application\set_elec_note_ju.dll` | — |
| `jinyu:jum_set_elec_single_name` | 3  给单个电极命名 | jum_elec_1_2 | `${UGII_BASE_DIR}\ugii\ju\application\set_elec_single_name_ju` | — |
| `jinyu:jum_set_elec_single_name_part` | 1  单个零件命名 | jum_elec_1_16 | `${UGII_BASE_DIR}\ugii\ju\application\set_elec_single_name_ju` | — |
| `jinyu:jum_set_elec_space_and_number` | 5  电极信息 | jum_elec_1_3 | `${UGII_BASE_DIR}\ugii\ju\application\set_elec_space_and_numb` | — |
| `jinyu:jum_set_elec_space_and_number_single` | 8  设定单项电极信息 | jum_elec_1_3 | `${UGII_BASE_DIR}\ugii\ju\application\set_elec_space_and_numb` | — |
| `jinyu:jum_set_face_color` | 2  曲面手动著色 | jum_elec_1_12 | `${UGII_BASE_DIR}\ugii\ju\application\set_face_color_ju.dll` | — |
| `jinyu:jum_set_face_color_new` | 3  曲面手动著色_新的 | jum_elec_1_12 | `${UGII_BASE_DIR}\ugii\ju\application\set_face_color_new_ju.d` | — |
| `jinyu:jum_set_group_elec_info` | 5  设定整条电极信息 | jum_elec_1_5 | `${UGII_BASE_DIR}\ugii\ju\application\set_group_elec_info.dll` | — |
| `jinyu:jum_set_mach_tool_number` | B  设定加工机床的刀具号 | jum_elec_1_7 | `${UGII_BASE_DIR}\ugii\ju\application\set_mach_tool_number_ju` | — |
| `jinyu:jum_set_min_tool_len_nip_holder` | D  刀具装夹刀头最小长度计算开关 | jum_elec_1_7 | `${UGII_BASE_DIR}\ugii\ju\application\set_min_tool_len_nip_ho` | — |
| `jinyu:jum_set_more_elec_name` | 4  给多个电极命名 | jum_elec_1_2 | `${UGII_BASE_DIR}\ugii\ju\application\set_more_elec_name_ju.d` | — |
| `jinyu:jum_set_mr_info` | D  设定模仁信息 | jum_elec_1_3 | `${UGII_BASE_DIR}\ugii\ju\application\set_mr_info.dll` | — |
| `jinyu:jum_set_mr_kt_dim_face` | I  设定模仁(挂台)标数面 | jum_elec_1_3 | `${UGII_BASE_DIR}\ugii\ju\application\set_mr_kt_dim_face.dll` | — |
| `jinyu:jum_set_mr_z_0_plane` | G  设定模仁Z0位面位置 | jum_elec_1_3 | `${UGII_BASE_DIR}\ugii\ju\application\set_mr_z_0_plane.dll` | — |
| `jinyu:jum_set_prog_desc` | C  设定程式说明 | jum_elec_1_7 | `${UGII_BASE_DIR}\ugii\ju\application\set_prog_desc_ju.dll` | — |
| `jinyu:jum_set_share_elec_info` | E  设定电极共用信息 | jum_elec_1_3 | `${UGII_BASE_DIR}\ugii\ju\application\set_share_elec_info.dll` | — |
| `jinyu:jum_set_tilt_elec_edm_face` | H  设定(斜放)电极的EDM碰数面 | jum_elec_1_3 | `${UGII_BASE_DIR}\ugii\ju\application\set_tilt_elec_edm_face.` | — |
| `jinyu:jum_set_tool_nip_len` | E  以实体干涉设定刀具装夹刀头长度 | jum_elec_1_7 | `${UGII_BASE_DIR}\ugii\ju\application\set_tool_nip_len_ju.dll` | — |
| `jinyu:jum_set_work_csys` | 6  设定工作坐标系 | jum_elec_1_13 | `${UGII_BASE_DIR}\ugii\ju\application\set_work_csys_ju.dll` | — |
| `jinyu:jum_set_work_csys_to_abs` | 7  工作坐标系移至绝对坐标系 | jum_elec_1_13 | `${UGII_BASE_DIR}\ugii\ju\application\set_work_csys_to_abs.dl` | — |
| `jinyu:jum_set_xd_slope_plane` | J  设定斜顶的斜度面 | jum_elec_1_3 | `${UGII_BASE_DIR}\ugii\ju\application\set_xd_slope_plane.dll` | — |
| `jinyu:jum_sheet_to_bitmap` | 5  输出图纸 | jum_elec_1_10 | `${UGII_BASE_DIR}\ugii\ju\application\sheet_to_bitmap_ju.dll` | — |
| `jinyu:jum_side_edm_number` | 3  给电极注明单边碰数点 | jum_elec_1_3 | `${UGII_BASE_DIR}\ugii\ju\application\side_edm_number_ju.dll` | — |
| `jinyu:jum_single_elec_kl_gg_auto_dir_x_free` | 3  单个开料--宽高(yz)是规格料 | jum_elec_1_5 | `${UGII_BASE_DIR}\ugii\ju\application\single_elec_kl_gg_auto_` | — |
| `jinyu:jum_single_elec_kl_gg_auto_dir_z_free` | 2  单个开料--宽长(yx)是规格料 | jum_elec_1_5 | `${UGII_BASE_DIR}\ugii\ju\application\single_elec_kl_gg_auto_` | — |
| `jinyu:jum_single_elec_kl_read_auto_dir` | 1  单个开料--实际尺寸加余量-常用 | jum_elec_1_5 | `${UGII_BASE_DIR}\ugii\ju\application\single_elec_kl_read_aut` | — |
| `jinyu:jum_single_elec_rotate` | 2  单个电极旋转90度 | jum_elec_1_4 | `${UGII_BASE_DIR}\ugii\ju\application\single_elec_rotate_ju.d` | — |
| `jinyu:jum_single_elec_to_origin` | 1  单个电极移至原点 | jum_elec_1_4 | `${UGII_BASE_DIR}\ugii\ju\application\single_elec_to_origin_j` | — |
| `jinyu:jum_single_export_part` | 7  导出单个电极 | jum_elec_1_12 | `${UGII_BASE_DIR}\ugii\ju\application\single_export_part_ju.d` | — |
| `jinyu:jum_smart_elec` | 9 智能电极 | jum_elec_1_1 | `${UGII_BASE_DIR}\ugii\ju\application\smart_elec.dll` | — |
| `jinyu:jum_solid_auto_assign_layer` | 3  实体自动分层 | jum_elec_1_14 | `${UGII_BASE_DIR}\ugii\ju\application\solid_auto_assign_layer` | — |
| `jinyu:jum_solid_box_data` | 5  实体BOX的数据 | jum_elec_1_9 | `${UGII_BASE_DIR}\ugii\ju\application\solid_box_data_ju.dll` | — |
| `jinyu:jum_solid_interf` | A  实体干涉检查 | jum_elec_1_9 | `${UGII_BASE_DIR}\ugii\ju\application\solid_interf_ju.dll` | — |
| `jinyu:jum_solid_same_face_color` | B  实体相同面著色(漏拆电极) | jum_elec_1_9 | `${UGII_BASE_DIR}\ugii\ju\application\solid_same_face_color_j` | — |
| `jinyu:jum_solid_translucency` | 2  实体透明/不透明 | jum_elec_1_13 | `${UGII_BASE_DIR}\ugii\ju\application\solid_translucency_ju.d` | — |
| `jinyu:jum_split_solid_via_parallel_point` | B 平行一面通过一点分割实体 | jum_elec_1_1 | `${UGII_BASE_DIR}\ugii\ju\application\split_solid_via_paralle` | — |
| `jinyu:jum_split_solid_via_plane` | 7 以曲面快速分割实体 | jum_elec_1_1 | `${UGII_BASE_DIR}\ugii\ju\application\split_solid_via_plane_j` | — |
| `jinyu:jum_split_solid_via_sel_plane` | 8 选择实体和曲面分割实体 | jum_elec_1_1 | `${UGII_BASE_DIR}\ugii\ju\application\split_solid_via_sel_pla` | — |
| `jinyu:jum_split_solid_with_x_axis` | I 以X轴向分割实体 | jum_elec_1_1 | `${UGII_BASE_DIR}\ugii\ju\application\split_solid_with_x_axis` | — |
| `jinyu:jum_split_solid_with_xyz_axis_and_dist` | H 以坐标轴向加距离分割实体 | jum_elec_1_1 | `${UGII_BASE_DIR}\ugii\ju\application\split_solid_with_xyz_ax` | — |
| `jinyu:jum_split_solid_with_y_axis` | J 以Y轴向分割实体 | jum_elec_1_1 | `${UGII_BASE_DIR}\ugii\ju\application\split_solid_with_y_axis` | — |
| `jinyu:jum_split_solid_with_z_axis` | K 以Z轴向分割实体 | jum_elec_1_1 | `${UGII_BASE_DIR}\ugii\ju\application\split_solid_with_z_axis` | — |
| `jinyu:jum_tool_libref` | 8  刀具库 | jum_elec_1_7 | `${UGII_BASE_DIR}\ugii\ju\application\tool_libref_ju.dll` | — |
| `jinyu:jum_tool_libref_edit` | 9  编辑刀具库 | jum_elec_1_7 | `${UGII_BASE_DIR}\ugii\ju\application\tool_libref_edit.dll` | — |
| `jinyu:jum_trim_solid_via_parallel_point` | A 平行一面通过一点修剪实体 | jum_elec_1_1 | `${UGII_BASE_DIR}\ugii\ju\application\trim_solid_via_parallel` | — |
| `jinyu:jum_trim_solid_via_plane` | 4 以曲面快速修剪实体 | jum_elec_1_1 | `${UGII_BASE_DIR}\ugii\ju\application\trim_solid_via_plane_ju` | — |
| `jinyu:jum_trim_solid_via_plane_point` | C 通过一点一视图面修剪实体 | jum_elec_1_1 | `${UGII_BASE_DIR}\ugii\ju\application\trim_solid_via_plane_po` | — |
| `jinyu:jum_trim_solid_via_plane_select_dir` | 5 以曲面选择方向修剪实体 | jum_elec_1_1 | `${UGII_BASE_DIR}\ugii\ju\application\trim_solid_via_plane_se` | — |
| `jinyu:jum_trim_solid_with_enlarge_surface` | 6 以曲面扩展修剪实体 | jum_elec_1_1 | `${UGII_BASE_DIR}\ugii\ju\application\trim_solid_with_enlarge` | — |
| `jinyu:jum_two_point_box` | 2 两点建 box | jum_elec_1_1 | `${UGII_BASE_DIR}\ugii\ju\application\two_point_box.dll` | — |
| `jinyu:jum_two_point_dis` | 6  测量两点间的直角距离 | jum_elec_1_9 | `${UGII_BASE_DIR}\ugii\ju\application\two_point_dis_ju.dll` | — |
| `jinyu:jum_un_blank_mr` | A  恢复模仁隐藏 | jum_elec_1_13 | `${UGII_BASE_DIR}\ugii\ju\application\un_blank_mr.dll` | — |
| `jinyu:jum_view_border_switch` | 3  视图边框显示开关 | jum_elec_1_10 | `${UGII_BASE_DIR}\ugii\ju\application\view_border_switch_ju.d` | — |
| `jinyu:jum_with_name_find_elec` | A  以名称查找电极 | jum_elec_1_2 | `${UGII_BASE_DIR}\ugii\ju\application\with_name_find_elec_ju.` | — |
| `jinyu:jum_with_tool_para_set_oper_para` | I  以刀具库的刀具参数设定操作的参数 | jum_elec_1_7 | `${UGII_BASE_DIR}\ugii\ju\application\with_tool_para_set_oper` | — |
| `jinyu:jum_with_two_point_split_solid` | E 两点分割实体 | jum_elec_1_1 | `${UGII_BASE_DIR}\ugii\ju\application\with_two_point_split_so` | — |
| `jinyu:jum_work_layer_next` | 7  设定下一层为工作层 | jum_elec_1_14 | `${UGII_BASE_DIR}\ugii\ju\application\work_layer_next_ju.dll` | — |
| `jinyu:jum_work_layer_preceding` | 6  设定上一层为工作层 | jum_elec_1_14 | `${UGII_BASE_DIR}\ugii\ju\application\work_layer_preceding_ju` | — |

## 四、标准调用流程（Agent 必须按此执行）

1. `list_plugins()` 确认该外挂已注册、`version_ok_for_nx12=true`。
2. `search('<中文名>', plugin='jinyu')` 定位候选，拿到复合键。
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

