# 外挂分册：美雷工具 MeiLei2（`meilei2`）

> 版本：**NX12.0-CN**　|　厂商目录：`YANGJEE/MeiLei2_tool`
> 命令数：292（中文标签 280）
> 风险等级：**LOW**　|　证据：E1-MEDIA（GBK/UTF-8 嗅探解码，直接解析介质 .men；已按 NX12 版本目录过滤）
> **非 Siemens 官方功能**，输出时必须向用户明确标注为第三方外挂。

## 一、能力卡

- 菜单文件：3 个，已排除其它 NX 版本菜单 0 个
- 文件编码：{'utf-8': 1, 'gbk': 2}
- 菜单版本：{'120': 1}（NX12 应为 120）
- 动作形态：{'其他': 290, '模块文件': 2}
- 硬编码绝对路径：0 处
- 环境变量依赖：0 处
- 跨外挂重名命令 ID：0 个（必须用复合键 `meilei2:<ID>`）

## 二、调用前的硬性检查

- ✅ 命令键必须用命名空间：`plugin_id:command_id`；裸 ID 会被判为歧义。

## 三、命令清单

### 动作类型：其他（290 条）

| 复合键 | 中文名 | 菜单 | ACTIONS | 快捷键 |
|---|---|---|---|---|
| `meilei2:MeiLei2_4CornerMirrMoveCopy` | 4角镜像移动/复制 | MEILEI2_TRANSFORM_TOOL | `MeiLei2_4CornerMirrMoveCopy` | — |
| `meilei2:MeiLei2_ADDSelectFilterToNavigation` | 添加选择过滤到导航 | MEILEI2_SET_TOOLS | `MeiLei2_ADDSelectFilterToNavigation` | — |
| `meilei2:MeiLei2_AddDrawObject` | 添加出图对象 | MEILEI2_DWG_TOOLS | `MeiLei2_AddDrawObject` | — |
| `meilei2:MeiLei2_AddOjbectToGroup` | 添加对象到组 | MEILEI2_COMMON_TOOL | `MeiLei2_AddOjbectToGroup` | — |
| `meilei2:MeiLei2_AngleCalc` | 角度增量计算器 | MEILEI2_COMMON_TOOL | `MeiLei2_AngleCalc` | — |
| `meilei2:MeiLei2_ArcLength` | 弧长分析 | MEILEI2_GUI_TOOL4 / MEILEI2_ANALYSIS_TOOL | `MeiLei2_ArcLength` | — |
| `meilei2:MeiLei2_AreaSplitElectrode` | 区域拆电极 | MEILEI2_ELECTRODE_TOOLS | `MeiLei2_AreaSplitElectrode` | — |
| `meilei2:MeiLei2_AskCylConePkCode` | 获得圆柱圆锥Pk源代码 | MEILEI2_VERSION_TOOLS | `MeiLei2_AskCylConePkCode` | — |
| `meilei2:MeiLei2_AssemCopy` | 装配间复制对象 | MEILEI2_ASSEM_TOOL | `MeiLei2_AssemCopy` | — |
| `meilei2:MeiLei2_AssemblyRename` | 组件重命名 | MEILEI2_ASSEM_TOOL | `MeiLei2_AssemblyRename` | — |
| `meilei2:MeiLei2_AssyGrouping` | 装配分组 | MEILEI2_ASSEM_TOOL | `MeiLei2_AssyGrouping` | — |
| `meilei2:MeiLei2_AutoAssyByAtt` | 自动装配(根据属性) | MEILEI2_ASSEM_TOOL | `MeiLei2_AutoAssyByAtt` | — |
| `meilei2:MeiLei2_AutoAssyByLayer` | 自动装配(根据图层) | MEILEI2_ASSEM_TOOL | `MeiLei2_AutoAssyByLayer` | — |
| `meilei2:MeiLei2_BOM` | BOM清单 | MEILEI2_BOM_TOOL | `MeiLei2_BOM` | — |
| `meilei2:MeiLei2_BackGoroundColor1` | 天青色背景 | MEILEI2_PHOTO_TOOL | `MeiLei2_BackGoroundColor1` | — |
| `meilei2:MeiLei2_BackGoroundColorBlack` | 黑色背景 | MEILEI2_PHOTO_TOOL | `MeiLei2_BackGoroundColorBlack` | — |
| `meilei2:MeiLei2_BackGoroundColorWhite` | 白色背景 | MEILEI2_PHOTO_TOOL | `MeiLei2_BackGoroundColorWhite` | — |
| `meilei2:MeiLei2_BackGoroundColordefault` | 默认背景 | MEILEI2_PHOTO_TOOL | `MeiLei2_BackGoroundColordefault` | — |
| `meilei2:MeiLei2_BaseStopPin` | 顶针板零件 | MEILEI2_MB_TOOL | `MeiLei2_BaseStopPin` | — |
| `meilei2:MeiLei2_BatchExportPart` | 批量导出文件 | MEILEI2_PHOTO_TOOL | `MeiLei2_BatchExportPart` | — |
| `meilei2:MeiLei2_BatchReplaceFace` | 批量替换面 | MEILEI2_BATCH_TOOL | `MeiLei2_BatchReplaceFace` | — |
| `meilei2:MeiLei2_BatchThicken` | 批量加厚 | MEILEI2_BATCH_TOOL | `MeiLei2_BatchThicken` | — |
| `meilei2:MeiLei2_Block` | 创建方块 | MEILEI2_ELECTRODE_TOOLS | `MeiLei2_Block` | — |
| `meilei2:MeiLei2_BodyBoolean` | 批量布尔 | MEILEI2_BATCH_TOOL | `MeiLei2_BodyBoolean` | — |
| `meilei2:MeiLei2_BodyMoveLayer` | 1个体归1个层 | MEILEI2_GUI_TOOL2 / MEILEI2_SHOW_TOOL | `MeiLei2_BodyMoveLayer` | — |
| `meilei2:MeiLei2_BodyMoveLayer_1` | 1个体归1个层 | MEILEI2_DWG_TOOLS | `MeiLei2_BodyMoveLayer` | — |
| `meilei2:MeiLei2_BodySplit` | 实体分割 | MEILEI2_COMMON_TOOL | `MeiLei2_BodySplit` | — |
| `meilei2:MeiLei2_BodyZoom` | 产品放缩水 | MEILEI2_MOLD_FEATURE_TOOL | `MeiLei2_BodyZoom` | — |
| `meilei2:MeiLei2_ButtonClicks` | 命令统计 | MEILEI2_VERSION_TOOLS | `MeiLei2_ButtonClicks` | — |
| `meilei2:MeiLei2_CaseConversion` | 字母大小写转换 | MEILEI2_VERSION_TOOLS | `MeiLei2_CaseConversion` | — |
| `meilei2:MeiLei2_CenterArc` | 创建圆弧 | MEILEI2_CURVE_TOOL | `MeiLei2_CenterArc` | — |
| `meilei2:MeiLei2_CenterLine` | 中心线 | MEILEI2_CURVE_TOOL | `MeiLei2_CenterLine` | — |
| `meilei2:MeiLei2_CentroidAnalysis` | 分析重心 | MEILEI2_GUI_TOOL4 / MEILEI2_ANALYSIS_TOOL | `MeiLei2_CentroidAnalysis` | — |
| `meilei2:MeiLei2_ChangeToAssem` | 批量装配 | MEILEI2_ASSEM_TOOL | `MeiLei2_ChangeToAssem` | — |
| `meilei2:MeiLei2_CharToAscii` | Char转ASCII | MEILEI2_VERSION_TOOLS | `MeiLei2_CharToAscii` | — |
| `meilei2:MeiLei2_CheckBreakFaceLocation` | 查找破面位置 | MEILEI2_GUI_TOOL4 / MEILEI2_ANALYSIS_TOOL | `MeiLei2_CheckBreakFaceLocation` | — |
| `meilei2:MeiLei2_CheckInterference` | 零件干涉检查 | MEILEI2_GUI_TOOL4 / MEILEI2_ANALYSIS_TOOL | `MeiLei2_CheckInterference` | — |
| `meilei2:MeiLei2_ChineseChess` | 中国象棋 | MEILEI2_VERSION_TOOLS | `MeiLei2_ChineseChess` | — |
| `meilei2:MeiLei2_ClearHighlight` | 清除高亮 | MEILEI2_GUI_TOOL1 / MEILEI2_SHOW_TOOL | `MeiLei2_ClearHighlight` | — |
| `meilei2:MeiLei2_CloseAllLayer` | 关闭所有图层 | MEILEI2_GUI_TOOL3 / MEILEI2_SHOW_MIN_TOOL | `MeiLei2_CloseAllLayer` | — |
| `meilei2:MeiLei2_CloseGui` | 关闭搞个球 | MEILEI2_SET_TOOLS | `MeiLei2_CloseGui` | — |
| `meilei2:MeiLei2_CloseSelObjlayer` | 关闭选择的层 | MEILEI2_GUI_TOOL3 / MEILEI2_SHOW_MIN_TOOL | `MeiLei2_CloseSelObjlayer` | — |
| `meilei2:MeiLei2_CloseTbr` | 关闭梅雷工具条 | MEILEI2_VERSION_TOOLS | `MeiLei2_CloseTbr` | — |
| `meilei2:MeiLei2_CoincideObj` | 重合对象 | MEILEI2_TRANSFORM_TOOL | `MeiLei2_CoincideObj` | — |
| `meilei2:MeiLei2_Color` | 设置对象颜色 | MEILEI2_GUI_TOOL1 / MEILEI2_SHOW_TOOL | `MeiLei2_Color` | — |
| `meilei2:MeiLei2_ColorToolbar` | 配置颜色工具条 | MEILEI2_COLORBAR_TOOL | `MeiLei2_ColorToolbar` | — |
| `meilei2:MeiLei2_ColorToolbar_0` | 粉色 | MEILEI2_COLORBAR_TOOL | `MeiLei2_ColorToolbar_0` | — |
| `meilei2:MeiLei2_ColorToolbar_1` | 红色 | MEILEI2_COLORBAR_TOOL | `MeiLei2_ColorToolbar_1` | — |
| `meilei2:MeiLei2_ColorToolbar_10` | 164 | MEILEI2_COLORBAR_TOOL | `MeiLei2_ColorToolbar_10` | — |
| `meilei2:MeiLei2_ColorToolbar_11` | 125 | MEILEI2_COLORBAR_TOOL | `MeiLei2_ColorToolbar_11` | — |
| `meilei2:MeiLei2_ColorToolbar_12` | 216 | MEILEI2_COLORBAR_TOOL | `MeiLei2_ColorToolbar_12` | — |
| `meilei2:MeiLei2_ColorToolbar_13` | 白 | MEILEI2_COLORBAR_TOOL | `MeiLei2_ColorToolbar_13` | — |
| `meilei2:MeiLei2_ColorToolbar_14` | 灰 | MEILEI2_COLORBAR_TOOL | `MeiLei2_ColorToolbar_14` | — |
| `meilei2:MeiLei2_ColorToolbar_15` | 粉色 | MEILEI2_COLORBAR_TOOL | `MeiLei2_ColorToolbar_15` | — |
| `meilei2:MeiLei2_ColorToolbar_16` | 红色 | MEILEI2_COLORBAR_TOOL | `MeiLei2_ColorToolbar_16` | — |
| `meilei2:MeiLei2_ColorToolbar_17` | 78 | MEILEI2_COLORBAR_TOOL | `MeiLei2_ColorToolbar_17` | — |
| `meilei2:MeiLei2_ColorToolbar_18` | 黄色 | MEILEI2_COLORBAR_TOOL | `MeiLei2_ColorToolbar_18` | — |
| `meilei2:MeiLei2_ColorToolbar_2` | 78 | MEILEI2_COLORBAR_TOOL | `MeiLei2_ColorToolbar_2` | — |
| `meilei2:MeiLei2_ColorToolbar_3` | 6 | MEILEI2_COLORBAR_TOOL | `MeiLei2_ColorToolbar_3` | — |
| `meilei2:MeiLei2_ColorToolbar_4` | 11 | MEILEI2_COLORBAR_TOOL | `MeiLei2_ColorToolbar_4` | — |
| `meilei2:MeiLei2_ColorToolbar_5` | 36 | MEILEI2_COLORBAR_TOOL | `MeiLei2_ColorToolbar_5` | — |
| `meilei2:MeiLei2_ColorToolbar_6` | 108 | MEILEI2_COLORBAR_TOOL | `MeiLei2_ColorToolbar_6` | — |
| `meilei2:MeiLei2_ColorToolbar_7` | 31 | MEILEI2_COLORBAR_TOOL | `MeiLei2_ColorToolbar_7` | — |
| `meilei2:MeiLei2_ColorToolbar_8` | 103 | MEILEI2_COLORBAR_TOOL | `MeiLei2_ColorToolbar_8` | — |
| `meilei2:MeiLei2_ColorToolbar_9` | 211 | MEILEI2_COLORBAR_TOOL | `MeiLei2_ColorToolbar_9` | — |
| `meilei2:MeiLei2_ConfigurationGui` | 配置搞个球 | MEILEI2_SET_TOOLS | `MeiLei2_ConfigurationGui` | — |
| `meilei2:MeiLei2_ConfigurePrtAttr` | 配置参数零件 | MEILEI2_PARTS_LIBRARY_TOOL | `MeiLei2_ConfigurePrtAttr` | — |
| `meilei2:MeiLei2_ConnectionFace` | 批量实体面连接 | MEILEI2_BATCH_TOOL | `MeiLei2_ConnectionFace` | — |
| `meilei2:MeiLei2_ContactFace` | 接触面涂色 | MEILEI2_GUI_TOOL4 / MEILEI2_ANALYSIS_TOOL | `MeiLei2_ContactFace` | — |
| `meilei2:MeiLei2_CoolCsysTubeUI` | 复杂水路 | MEILEI2_COOLING_SYSTEM_TOOL | `MeiLei2_CoolCsysTubeUI` | — |
| `meilei2:MeiLei2_CopySameObject` | 复制相同 | MEILEI2_TRANSFORM_TOOL | `MeiLei2_CopySameObject` | — |
| `meilei2:MeiLei2_CreateBlockByObj` | 包容体 | MEILEI2_COMMON_TOOL | `MeiLei2_CreateBlockByObj` | — |
| `meilei2:MeiLei2_CreateBlockUICfgFileSCD` | 生成Dlx读写配置文件源代码 | MEILEI2_VERSION_TOOLS | `MeiLei2_CreateBlockUICfgFileSCD` | — |
| `meilei2:MeiLei2_CreateElectrodesDiagonals` | 创建电极对角线 | MEILEI2_ELECTRODE_TOOLS | `MeiLei2_CreateElectrodesDiagonals` | — |
| `meilei2:MeiLei2_CreateGroup` | 新建组 | MEILEI2_COMMON_TOOL | `MeiLei2_CreateGroup` | — |
| `meilei2:MeiLei2_CreateResidueDesign` | 渣包设计 | MEILEI2_INJECTION_SYSTEM_TOOL | `MeiLei2_CreateResidueDesign` | — |
| `meilei2:MeiLei2_CreateTemplate` | 制作图框 | MEILEI2_DWG_TOOLS | `MeiLei2_CreateTemplate` | — |
| `meilei2:MeiLei2_CrossBodyCopy` | 复制-区域面 | MEILEI2_BATCH_TOOL | `MeiLei2_CrossBodyCopy` | — |
| `meilei2:MeiLei2_CrossBodyDelete` | 删除-区域面 | MEILEI2_BATCH_TOOL | `MeiLei2_CrossBodyDelete` | — |
| `meilei2:MeiLei2_CrossBodyMirror` | 镜像-区域面 | MEILEI2_BATCH_TOOL | `MeiLei2_CrossBodyMirror` | — |
| `meilei2:MeiLei2_CrossBodyMove` | 移动-区域面 | MEILEI2_BATCH_TOOL | `MeiLei2_CrossBodyMove` | — |
| `meilei2:MeiLei2_CrossBodyRotate` | 旋转-区域面 | MEILEI2_BATCH_TOOL | `MeiLei2_CrossBodyRotate` | — |
| `meilei2:MeiLei2_CutCylBenchmark` | 切割圆柱基准 | MEILEI2_COMMON_TOOL | `MeiLei2_CutCylBenchmark` | — |
| `meilei2:MeiLei2_CuttingCurve` | 创建线切割曲线 | MEILEI2_CURVE_TOOL | `MeiLei2_CuttingCurve` | — |
| `meilei2:MeiLei2_DP` | 定位销 | MEILEI2_MB_TOOL | `MeiLei2_DP` | — |
| `meilei2:MeiLei2_DaLeTou` | 大乐透 | MEILEI2_VERSION_TOOLS | `MeiLei2_DaLeTou` | — |
| `meilei2:MeiLei2_DecimationEdge` | 抽取面边缘 | MEILEI2_CURVE_TOOL | `MeiLei2_DecimationEdge` | — |
| `meilei2:MeiLei2_DelObjectAtt` | 删除对象属性 | MEILEI2_BOM_TOOL | `MeiLei2_DelObjectAtt` | — |
| `meilei2:MeiLei2_DeleteDisplayObject` | 删除对象 | MEILEI2_BATCH_TOOL | `MeiLei2_DeleteDisplayObject` | — |
| `meilei2:MeiLei2_DeleteFaces` | 批量删除面 | MEILEI2_BATCH_TOOL | `MeiLei2_DeleteFaces` | — |
| `meilei2:MeiLei2_DeleteGroup` | 删除组 | MEILEI2_COMMON_TOOL | `MeiLei2_DeleteGroup` | — |
| `meilei2:MeiLei2_DeleteLnvalidObject` | 删除无效对象 | MEILEI2_BATCH_TOOL | `MeiLei2_DeleteLnvalidObject` | — |
| `meilei2:MeiLei2_DeleteObjectFromGroup` | 对象从组中删除 | MEILEI2_COMMON_TOOL | `MeiLei2_DeleteObjectFromGroup` | — |
| `meilei2:MeiLei2_DeleteOverlapBody` | 批量删除重叠 | MEILEI2_BATCH_TOOL | `MeiLei2_DeleteOverlapBody` | — |
| `meilei2:MeiLei2_DeleteSuppressionComps` | 清理部件 | MEILEI2_ASSEM_TOOL | `MeiLei2_DeleteSuppressionComps` | — |
| `meilei2:MeiLei2_DisplayTopAssembly` | 显示顶装配 | MEILEI2_ASSEM_TOOL | `MeiLei2_DisplayTopAssembly` | — |
| `meilei2:MeiLei2_DrawPageDown` | 下一张图纸 | MEILEI2_DWG_TOOLS | `MeiLei2_DrawPageDown` | — |
| `meilei2:MeiLei2_DrawPageUp` | 上一张图纸 | MEILEI2_DWG_TOOLS | `MeiLei2_DrawPageUp` | — |
| `meilei2:MeiLei2_DrawingPreferences` | 制图配置 | MEILEI2_DWG_TOOLS | `MeiLei2_DrawingPreferences` | — |
| `meilei2:MeiLei2_DynamicCircle` | 动态圆 | MEILEI2_GUI_TOOL4 / MEILEI2_ANALYSIS_TOOL | `MeiLei2_DynamicCircle` | — |
| `meilei2:MeiLei2_EditChamfer` | 编辑倒角 | MEILEI2_BATCH_TOOL | `MeiLei2_EditChamfer` | — |
| `meilei2:MeiLei2_EditObjectAtt` | 编辑属性 | MEILEI2_BOM_TOOL | `MeiLei2_EditObjectAtt` | — |
| `meilei2:MeiLei2_EditTextACenterLineLib` | 编辑刻字中心线库 | MEILEI2_CURVE_TOOL | `MeiLei2_EditTextACenterLineLib` | — |
| `meilei2:MeiLei2_Edm` | EDM电火花图 | MEILEI2_ELECTRODE_TOOLS | `MeiLei2_Edm` | — |
| `meilei2:MeiLei2_ElectrodeStage` | 电极台 | MEILEI2_ELECTRODE_TOOLS | `MeiLei2_ElectrodeStage` | — |
| `meilei2:MeiLei2_EmptyLayerObject` | 清空层对象 | MEILEI2_BATCH_TOOL | `MeiLei2_EmptyLayerObject` | — |
| `meilei2:MeiLei2_ExcelCheck` | 检查Excel数据库 | MEILEI2_VERSION_TOOLS | `MeiLei2_ExcelCheck` | — |
| `meilei2:MeiLei2_ExportImportPs` | 导出导入x_t | MEILEI2_PHOTO_TOOL | `MeiLei2_ExportImportPs` | — |
| `meilei2:MeiLei2_ExportPart` | 导出文件 | MEILEI2_PHOTO_TOOL | `MeiLei2_ExportPart` | — |
| `meilei2:MeiLei2_ExportPicture` | 批量导出部件模型图片 | MEILEI2_PHOTO_TOOL | `MeiLei2_ExportPicture` | — |
| `meilei2:MeiLei2_FaceColors` | 面涂色 | MEILEI2_SHOW_TOOL | `MeiLei2_FaceColors` | — |
| `meilei2:MeiLei2_FaceIntegral` | 面取整 | MEILEI2_BATCH_TOOL | `MeiLei2_FaceIntegral` | — |
| `meilei2:MeiLei2_FileEncryption` | 部件加密 | MEILEI2_PHOTO_TOOL | `MeiLei2_FileEncryption` | — |
| `meilei2:MeiLei2_FillTheHole` | 批量自动补圆孔 | MEILEI2_BATCH_TOOL | `MeiLei2_FillTheHole` | — |
| `meilei2:MeiLei2_FindHaveBreakFaceBody` | 查找含有破面的实体 | MEILEI2_GUI_TOOL4 / MEILEI2_ANALYSIS_TOOL | `MeiLei2_FindHaveBreakFaceBody` | — |
| `meilei2:MeiLei2_FindObjectById` | 根据ID查找对象 | MEILEI2_VERSION_TOOLS | `MeiLei2_FindObjectById` | — |
| `meilei2:MeiLei2_FourEdgesPunch` | 打孔 | MEILEI2_COMMON_TOOL | `MeiLei2_FourEdgesPunch` | — |
| `meilei2:MeiLei2_FrameAvoidance` | 避空角 | MEILEI2_MOLD_FEATURE_TOOL | `MeiLei2_FrameAvoidance` | — |
| `meilei2:MeiLei2_GearBody` | 齿轮 | MEILEI2_SLIDER_AND_LIFTER_TOOL | `MeiLei2_GearBody` | — |
| `meilei2:MeiLei2_GearRackBody` | 直齿条 | MEILEI2_SLIDER_AND_LIFTER_TOOL | `MeiLei2_GearRackBody` | — |
| `meilei2:MeiLei2_Geometric_Analysis` | 几何分析 | MEILEI2_GUI_TOOL4 / MEILEI2_ANALYSIS_TOOL | `MeiLei2_Geometric_Analysis` | — |
| `meilei2:MeiLei2_GetComputerinformation` | 计算机信息 | MEILEI2_VERSION_TOOLS | `MeiLei2_GetComputerinformation` | — |
| `meilei2:MeiLei2_HideAllObj` | 隐藏所有对象 | MEILEI2_GUI_TOOL3 / MEILEI2_SHOW_MIN_TOOL | `MeiLei2_HideAllObj` | — |
| `meilei2:MeiLei2_HideSetAttObj` | 隐藏设置过属性对象 | MEILEI2_BOM_TOOL | `MeiLei2_HideSetAttObj` | — |
| `meilei2:MeiLei2_HoleCenterline` | 管道中心线 | MEILEI2_CURVE_TOOL | `MeiLei2_HoleCenterline` | — |
| `meilei2:MeiLei2_HoleInformation` | 孔信息 | MEILEI2_GUI_TOOL4 / MEILEI2_ANALYSIS_TOOL | `MeiLei2_HoleInformation` | — |
| `meilei2:MeiLei2_HoleMeasurement` | 单孔分析 | MEILEI2_GUI_TOOL4 / MEILEI2_ANALYSIS_TOOL | `MeiLei2_HoleMeasurement` | — |
| `meilei2:MeiLei2_ImportFiles` | 批量导入部件 | MEILEI2_PHOTO_TOOL | `MeiLei2_ImportFiles` | — |
| `meilei2:MeiLei2_InitializeAssemTree` | 初始化装配树 | MEILEI2_ASSEM_TOOL | `MeiLei2_InitializeAssemTree` | — |
| `meilei2:MeiLei2_LayerGroup` | 层组操作 | MEILEI2_GUI_TOOL2 / MEILEI2_SHOW_TOOL | `MeiLei2_LayerGroup` | — |
| `meilei2:MeiLei2_LayerGroup_1` | 层组操作 | MEILEI2_DWG_TOOLS | `MeiLei2_LayerGroup` | — |
| `meilei2:MeiLei2_LayerOperation` | 层操作 | MEILEI2_SHOW_TOOL | `MeiLei2_LayerOperation` | — |
| `meilei2:MeiLei2_LayerToolbar` | 配置图层工具条 | MEILEI2_LAYERBAR_TOOL | `MeiLei2_LayerToolbar` | — |
| `meilei2:MeiLei2_LayerToolbar_0` | 1图层开关 | MEILEI2_LAYERBAR_TOOL | `MeiLei2_LayerToolbar_0` | — |
| `meilei2:MeiLei2_LayerToolbar_1` | 10图层开关 | MEILEI2_LAYERBAR_TOOL | `MeiLei2_LayerToolbar_1` | — |
| `meilei2:MeiLei2_LayerToolbar_10` | 产品 | MEILEI2_LAYERBAR_TOOL | `MeiLei2_LayerToolbar_10` | — |
| `meilei2:MeiLei2_LayerToolbar_11` | 全套模具 | MEILEI2_LAYERBAR_TOOL | `MeiLei2_LayerToolbar_11` | — |
| `meilei2:MeiLei2_LayerToolbar_12` | 前模组 | MEILEI2_LAYERBAR_TOOL | `MeiLei2_LayerToolbar_12` | — |
| `meilei2:MeiLei2_LayerToolbar_13` | 后模组 | MEILEI2_LAYERBAR_TOOL | `MeiLei2_LayerToolbar_13` | — |
| `meilei2:MeiLei2_LayerToolbar_14` | 前模胚 | MEILEI2_LAYERBAR_TOOL | `MeiLei2_LayerToolbar_14` | — |
| `meilei2:MeiLei2_LayerToolbar_15` | 后模胚 | MEILEI2_LAYERBAR_TOOL | `MeiLei2_LayerToolbar_15` | — |
| `meilei2:MeiLei2_LayerToolbar_16` | 前模仁 | MEILEI2_LAYERBAR_TOOL | `MeiLei2_LayerToolbar_16` | — |
| `meilei2:MeiLei2_LayerToolbar_17` | 后模仁 | MEILEI2_LAYERBAR_TOOL | `MeiLei2_LayerToolbar_17` | — |
| `meilei2:MeiLei2_LayerToolbar_18` | 前模镶件 | MEILEI2_LAYERBAR_TOOL | `MeiLei2_LayerToolbar_18` | — |
| `meilei2:MeiLei2_LayerToolbar_19` | 后模镶件 | MEILEI2_LAYERBAR_TOOL | `MeiLei2_LayerToolbar_19` | — |
| `meilei2:MeiLei2_LayerToolbar_2` | 18图层开关 | MEILEI2_LAYERBAR_TOOL | `MeiLei2_LayerToolbar_2` | — |
| `meilei2:MeiLei2_LayerToolbar_20` | 滑块 | MEILEI2_LAYERBAR_TOOL | `MeiLei2_LayerToolbar_20` | — |
| `meilei2:MeiLei2_LayerToolbar_21` | 斜顶 | MEILEI2_LAYERBAR_TOOL | `MeiLei2_LayerToolbar_21` | — |
| `meilei2:MeiLei2_LayerToolbar_22` | 顶针 | MEILEI2_LAYERBAR_TOOL | `MeiLei2_LayerToolbar_22` | — |
| `meilei2:MeiLei2_LayerToolbar_23` | 前模运水 | MEILEI2_LAYERBAR_TOOL | `MeiLei2_LayerToolbar_23` | — |
| `meilei2:MeiLei2_LayerToolbar_24` | 后模运水 | MEILEI2_LAYERBAR_TOOL | `MeiLei2_LayerToolbar_24` | — |
| `meilei2:MeiLei2_LayerToolbar_3` | 28图层开关 | MEILEI2_LAYERBAR_TOOL | `MeiLei2_LayerToolbar_3` | — |
| `meilei2:MeiLei2_LayerToolbar_4` | 30图层开关 | MEILEI2_LAYERBAR_TOOL | `MeiLei2_LayerToolbar_4` | — |
| `meilei2:MeiLei2_LayerToolbar_5` | 40图层开关 | MEILEI2_LAYERBAR_TOOL | `MeiLei2_LayerToolbar_5` | — |
| `meilei2:MeiLei2_LayerToolbar_6` | 70图层开关 | MEILEI2_LAYERBAR_TOOL | `MeiLei2_LayerToolbar_6` | — |
| `meilei2:MeiLei2_LayerToolbar_7` | 100图层开关 | MEILEI2_LAYERBAR_TOOL | `MeiLei2_LayerToolbar_7` | — |
| `meilei2:MeiLei2_LayerToolbar_8` | 110图层开关 | MEILEI2_LAYERBAR_TOOL | `MeiLei2_LayerToolbar_8` | — |
| `meilei2:MeiLei2_LayerToolbar_9` | 256图层开关 | MEILEI2_LAYERBAR_TOOL | `MeiLei2_LayerToolbar_9` | — |
| `meilei2:MeiLei2_LocatingBlockUI` | 精定位 | MEILEI2_MB_TOOL | `MeiLei2_LocatingBlockUI` | — |
| `meilei2:MeiLei2_MaxShapeDim` | 建模标注外形尺寸 | MEILEI2_CURVE_TOOL | `MeiLei2_MaxShapeDim` | — |
| `meilei2:MeiLei2_MeasureBodySize` | 测量实体大小 | MEILEI2_GUI_TOOL4 / MEILEI2_ANALYSIS_TOOL | `MeiLei2_MeasureBodySize` | — |
| `meilei2:MeiLei2_MeasuringEntity` | 测量实体尺寸和重量 | MEILEI2_GUI_TOOL4 / MEILEI2_ANALYSIS_TOOL | `MeiLei2_MeasuringEntity` | — |
| `meilei2:MeiLei2_MetalWeightCalc` | 金属重量计算器 | MEILEI2_COMMON_TOOL | `MeiLei2_MetalWeightCalc` | — |
| `meilei2:MeiLei2_ModifPartInformation` | 设置项目信息(部件属性) | MEILEI2_BOM_TOOL | `MeiLei2_ModifPartInformation` | — |
| `meilei2:MeiLei2_ModifPartInformation_1` | 设置项目信息(部件属性) | MEILEI2_DWG_TOOLS | `MeiLei2_ModifPartInformation` | — |
| `meilei2:MeiLei2_MoldBase` | 模胚 | MEILEI2_MB_TOOL | `MeiLei2_MoldBase` | — |
| `meilei2:MeiLei2_MouldChineseEnglish` | 模具术语 | MEILEI2_COMMON_TOOL | `MeiLei2_MouldChineseEnglish` | — |
| `meilei2:MeiLei2_MoveBodyToOrigin` | 移动实体到原点 | MEILEI2_TRANSFORM_TOOL | `MeiLei2_MoveBodyToOrigin` | — |
| `meilei2:MeiLei2_NAME_OFF` | 隐藏名称 | MEILEI2_BOM_TOOL | `MeiLei2_NAME_OFF` | — |
| `meilei2:MeiLei2_NAME_ON` | 显示名称 | MEILEI2_BOM_TOOL | `MeiLei2_NAME_ON` | — |
| `meilei2:MeiLei2_NewDrawing` | 新建图纸 | MEILEI2_DWG_TOOLS | `MeiLei2_NewDrawing` | — |
| `meilei2:MeiLei2_NumberStatistical` | 数量统计 | MEILEI2_COMMON_TOOL | `MeiLei2_NumberStatistical` | — |
| `meilei2:MeiLei2_NxBmp` | UG图标大全 | MEILEI2_VERSION_TOOLS | `MeiLei2_NxBmp` | — |
| `meilei2:MeiLei2_Object257Layer` | 对象257层操作 | MEILEI2_GUI_TOOL2 / MEILEI2_SHOW_TOOL | `MeiLei2_Object257Layer` | — |
| `meilei2:MeiLei2_ObjectColor` | 对象颜色 | MEILEI2_GUI_TOOL1 / MEILEI2_SHOW_TOOL | `MeiLei2_ObjectColor` | — |
| `meilei2:MeiLei2_ObjectCommonlyOperation` | 对象常用操作 | MEILEI2_GUI_TOOL1 / MEILEI2_SHOW_TOOL | `MeiLei2_ObjectCommonlyOperation` | — |
| `meilei2:MeiLei2_ObjectDraw` | 对象所在图纸 | MEILEI2_DWG_TOOLS | `MeiLei2_ObjectDraw` | — |
| `meilei2:MeiLei2_ObjectInformation` | 对象信息 | MEILEI2_GUI_TOOL4 / MEILEI2_ANALYSIS_TOOL | `MeiLei2_ObjectInformation` | — |
| `meilei2:MeiLei2_ObjectMoveLayer` | 对象移层 | MEILEI2_GUI_TOOL2 / MEILEI2_SHOW_TOOL | `MeiLei2_ObjectMoveLayer` | — |
| `meilei2:MeiLei2_ObjectMoveLayer_1` | 对象移层 | MEILEI2_DWG_TOOLS | `MeiLei2_ObjectMoveLayer` | — |
| `meilei2:MeiLei2_ObjectShow` | 显示操作 | MEILEI2_SHOW_TOOL | `MeiLei2_ObjectShow` | — |
| `meilei2:MeiLei2_OenSelObjlayer` | 关闭选取外层 | MEILEI2_GUI_TOOL3 / MEILEI2_SHOW_MIN_TOOL | `MeiLei2_OenSelObjlayer` | — |
| `meilei2:MeiLei2_OffsetAndStretch` | 偏置和拉伸 | MEILEI2_ELECTRODE_TOOLS | `MeiLei2_OffsetAndStretch` | — |
| `meilei2:MeiLei2_OneselfRotatingMoveCopy` | 实体自转移动/复制 | MEILEI2_TRANSFORM_TOOL | `MeiLei2_OneselfRotatingMoveCopy` | — |
| `meilei2:MeiLei2_OpenAllLayer` | 打开所有图层 | MEILEI2_GUI_TOOL3 / MEILEI2_SHOW_MIN_TOOL | `MeiLei2_OpenAllLayer` | — |
| `meilei2:MeiLei2_OpenAllLayerOrShow` | 打开所有层并显示所有对象 | MEILEI2_GUI_TOOL3 / MEILEI2_SHOW_MIN_TOOL | `MeiLei2_OpenAllLayerOrShow` | — |
| `meilei2:MeiLei2_OpenBotObjWork` | 下一个有对象层 | MEILEI2_GUI_TOOL3 / MEILEI2_SHOW_MIN_TOOL | `MeiLei2_OpenBotObjWork` | — |
| `meilei2:MeiLei2_OpenBotWork` | 下一层为工作层 | MEILEI2_GUI_TOOL3 / MEILEI2_SHOW_MIN_TOOL | `MeiLei2_OpenBotWork` | — |
| `meilei2:MeiLei2_OpenCalculator` | 打开计算器 | MEILEI2_COMMON_TOOL | `MeiLei2_OpenCalculator` | — |
| `meilei2:MeiLei2_OpenCustom_dirs` | 打开 custom_dirs.dat | MEILEI2_VERSION_TOOLS | `MeiLei2_OpenCustom_dirs` | — |
| `meilei2:MeiLei2_OpenFiles` | 批量打开部件 | MEILEI2_PHOTO_TOOL | `MeiLei2_OpenFiles` | — |
| `meilei2:MeiLei2_OpenMoldUgOnPath` | 打开梅雷安装目录 | MEILEI2_VERSION_TOOLS | `MeiLei2_OpenMoldUgOnPath` | — |
| `meilei2:MeiLei2_OpenPrtThePath` | 打开当前部件所在文件夹 | MEILEI2_PHOTO_TOOL | `MeiLei2_OpenPrtThePath` | — |
| `meilei2:MeiLei2_OpenUpObjWork` | 上一个有对象层 | MEILEI2_GUI_TOOL3 / MEILEI2_SHOW_MIN_TOOL | `MeiLei2_OpenUpObjWork` | — |
| `meilei2:MeiLei2_OpenUpWork` | 上一层为工作层 | MEILEI2_GUI_TOOL3 / MEILEI2_SHOW_MIN_TOOL | `MeiLei2_OpenUpWork` | — |
| `meilei2:MeiLei2_OrdinateDim` | 坐标标注 | MEILEI2_DIM_TOOLS | `MeiLei2_OrdinateDim` | — |
| `meilei2:MeiLei2_ParallelMoveCopy` | 平行移动/复制 | MEILEI2_TRANSFORM_TOOL | `MeiLei2_ParallelMoveCopy` | — |
| `meilei2:MeiLei2_PartLibrary` | 简单零件库 | MEILEI2_PARTS_LIBRARY_TOOL | `MeiLei2_PartLibrary` | — |
| `meilei2:MeiLei2_PartUnitConversion` | 部件单位转换 | MEILEI2_PHOTO_TOOL | `MeiLei2_PartUnitConversion` | — |
| `meilei2:MeiLei2_PathToCurve` | 刀路转曲线 | MEILEI2_CAM_TOOLS | `MeiLei2_PathToCurve` | — |
| `meilei2:MeiLei2_PluginsInformation` | 关于 | MEILEI2_VERSION_TOOLS | `MeiLei2_PluginsInformation` | — |
| `meilei2:MeiLei2_PointCoordinates` | 点坐标 | MEILEI2_GUI_TOOL4 / MEILEI2_ANALYSIS_TOOL | `MeiLei2_PointCoordinates` | — |
| `meilei2:MeiLei2_PointGateBulge` | 波点\火山口 | MEILEI2_MOLD_FEATURE_TOOL | `MeiLei2_PointGateBulge` | — |
| `meilei2:MeiLei2_PointPointDistance` | 对象距离 | MEILEI2_GUI_TOOL4 / MEILEI2_ANALYSIS_TOOL | `MeiLei2_PointPointDistance` | — |
| `meilei2:MeiLei2_PointToPointMoveCopy` | 点到点移动/复制 | MEILEI2_TRANSFORM_TOOL | `MeiLei2_PointToPointMoveCopy` | — |
| `meilei2:MeiLei2_Positive_entity` | 摆正实体 | MEILEI2_TRANSFORM_TOOL | `MeiLei2_Positive_entity` | — |
| `meilei2:MeiLei2_PreferencesSelection` | 选择首选项 | MEILEI2_SELECTION_TOOL | `MeiLei2_PreferencesSelection` | — |
| `meilei2:MeiLei2_ProjectionOuterContour` | 投影最外轮廓线 | MEILEI2_CURVE_TOOL | `MeiLei2_ProjectionOuterContour` | — |
| `meilei2:MeiLei2_QRCode` | 创建二维码 | MEILEI2_COMMON_TOOL | `MeiLei2_QRCode` | — |
| `meilei2:MeiLei2_ReadAtt` | 读Excel数据到对象属性 | MEILEI2_BOM_TOOL | `MeiLei2_ReadAtt` | — |
| `meilei2:MeiLei2_Register` | 注册 | MEILEI2_VERSION_TOOLS | `MeiLei2_Register` | — |
| `meilei2:MeiLei2_RemoveAllParams` | 去除参数 | MEILEI2_BATCH_TOOL | `MeiLei2_RemoveAllParams` | — |
| `meilei2:MeiLei2_RemoveAllSel` | 清空选择 | MEILEI2_SELECTION_TOOL | `MeiLei2_RemoveAllSel` | F11 |
| `meilei2:MeiLei2_RepairBreakFace` | 修复破面 | MEILEI2_GUI_TOOL4 / MEILEI2_ANALYSIS_TOOL | `MeiLei2_RepairBreakFace` | — |
| `meilei2:MeiLei2_ResizeFace` | 批量调整圆柱面 | MEILEI2_BATCH_TOOL | `MeiLei2_ResizeFace` | — |
| `meilei2:MeiLei2_ReverseHide` | 反向隐藏显示 | MEILEI2_GUI_TOOL3 / MEILEI2_SHOW_MIN_TOOL | `MeiLei2_ReverseHide` | — |
| `meilei2:MeiLei2_ReverseLayer` | 反向关闭层 | MEILEI2_GUI_TOOL3 / MEILEI2_SHOW_MIN_TOOL | `MeiLei2_ReverseLayer` | — |
| `meilei2:MeiLei2_RotatingMoveCopy` | 以点旋转移动/复制 | MEILEI2_TRANSFORM_TOOL | `MeiLei2_RotatingMoveCopy` | — |
| `meilei2:MeiLei2_RunnerBody` | 流道 | MEILEI2_INJECTION_SYSTEM_TOOL | `MeiLei2_RunnerBody` | — |
| `meilei2:MeiLei2_RunnerCenterline` | 流道中心线 | MEILEI2_CURVE_TOOL | `MeiLei2_RunnerCenterline` | — |
| `meilei2:MeiLei2_SaveBackup` | 保存并备份工作部件 | MEILEI2_PHOTO_TOOL | `MeiLei2_SaveBackup` | — |
| `meilei2:MeiLei2_ScaleDrawing` | 缩放图框 | MEILEI2_DWG_TOOLS | `MeiLei2_ScaleDrawing` | — |
| `meilei2:MeiLei2_Screw` | 螺丝 | MEILEI2_MB_TOOL | `MeiLei2_Screw` | — |
| `meilei2:MeiLei2_SelFaces` | 批量选择面 | MEILEI2_SELECTION_TOOL | `MeiLei2_SelFaces` | — |
| `meilei2:MeiLei2_SelFindFaces` | 选择查找面 | MEILEI2_SELECTION_TOOL | `MeiLei2_SelFindFaces` | — |
| `meilei2:MeiLei2_SelFliter_Body` | 选择实体 | MEILEI2_SELECTION_TOOL | `MeiLei2_SelFliter_Body` | — |
| `meilei2:MeiLei2_SelFliter_CSYS` | 选择csys坐标 | MEILEI2_SELECTION_TOOL | `MeiLei2_SelFliter_CSYS` | — |
| `meilei2:MeiLei2_SelFliter_Color` | 按指定颜色过滤 | MEILEI2_SELECTION_TOOL | `MeiLei2_SelFliter_Color` | — |
| `meilei2:MeiLei2_SelFliter_Comp` | 选择组件 | MEILEI2_SELECTION_TOOL | `MeiLei2_SelFliter_Comp` | — |
| `meilei2:MeiLei2_SelFliter_Curve` | 选择曲线 | MEILEI2_SELECTION_TOOL | `MeiLei2_SelFliter_Curve` | — |
| `meilei2:MeiLei2_SelFliter_Datum` | 选择基准 | MEILEI2_SELECTION_TOOL | `MeiLei2_SelFliter_Datum` | — |
| `meilei2:MeiLei2_SelFliter_Edge` | 选择边 | MEILEI2_SELECTION_TOOL | `MeiLei2_SelFliter_Edge` | — |
| `meilei2:MeiLei2_SelFliter_Face` | 选择面 | MEILEI2_SELECTION_TOOL | `MeiLei2_SelFliter_Face` | — |
| `meilei2:MeiLei2_SelFliter_Group` | 选择组 | MEILEI2_SELECTION_TOOL | `MeiLei2_SelFliter_Group` | — |
| `meilei2:MeiLei2_SelFliter_None` | 无选择 | MEILEI2_SELECTION_TOOL | `MeiLei2_SelFliter_None` | — |
| `meilei2:MeiLei2_SelFliter_Sheet` | 选择片体 | MEILEI2_SELECTION_TOOL | `MeiLei2_SelFliter_Sheet` | — |
| `meilei2:MeiLei2_SelFliter_Type` | 选择指定类型 | MEILEI2_SELECTION_TOOL | `MeiLei2_SelFliter_Type` | — |
| `meilei2:MeiLei2_SelHideObj` | 隐藏选择的对象 | MEILEI2_GUI_TOOL3 / MEILEI2_SHOW_MIN_TOOL | `MeiLei2_SelHideObj` | — |
| `meilei2:MeiLei2_SelRefSet` | 选择引用集成员对象 | MEILEI2_SELECTION_TOOL | `MeiLei2_SelRefSet` | — |
| `meilei2:MeiLei2_SelShowObj` | 隐藏选取外对象 | MEILEI2_GUI_TOOL3 / MEILEI2_SHOW_MIN_TOOL | `MeiLei2_SelShowObj` | — |
| `meilei2:MeiLei2_SetBenchmark` | 创建坐标原点 | MEILEI2_DIM_TOOLS | `MeiLei2_SetBenchmark` | — |
| `meilei2:MeiLei2_SetCenterMarks` | 批量设置中心线标记 | MEILEI2_EDIT_DIM_TOOLS | `MeiLei2_SetCenterMarks` | — |
| `meilei2:MeiLei2_SetCenterline3ds` | 批量设置3D中心线 | MEILEI2_EDIT_DIM_TOOLS | `MeiLei2_SetCenterline3ds` | — |
| `meilei2:MeiLei2_SetConfiguration` | 初始化配置 | MEILEI2_SET_TOOLS | `MeiLei2_SetConfiguration` | — |
| `meilei2:MeiLei2_SetHiddenline` | 批量设置隐藏线 | MEILEI2_DWG_TOOLS | `MeiLei2_SetHiddenline` | — |
| `meilei2:MeiLei2_SetLastCommand` | 设置快捷键 | MEILEI2_SET_TOOLS | `MeiLei2_SetLastFunction` | — |
| `meilei2:MeiLei2_SetObjectAtt` | 设置对象属性 | MEILEI2_BOM_TOOL | `MeiLei2_SetObjectAtt` | — |
| `meilei2:MeiLei2_SetObjectInDrawDisplayStatus` | 设置对象在图纸视图中显示状态 | MEILEI2_DWG_TOOLS | `MeiLei2_SetObjectInDrawDisplayStatus` | — |
| `meilei2:MeiLei2_SetRefSet` | 设置引用集 | MEILEI2_ASSEM_TOOL | `MeiLei2_SetRefSet` | — |
| `meilei2:MeiLei2_SetView` | 批量设置视图 | MEILEI2_DWG_TOOLS | `MeiLei2_SetView` | — |
| `meilei2:MeiLei2_SetViewDir` | 设置对象出图方向 | MEILEI2_DWG_TOOLS | `MeiLei2_SetViewDir` | — |
| `meilei2:MeiLei2_SetWorkCsys` | 坐标系 | MEILEI2_GUI_TOOL1 / MEILEI2_SHOW_TOOL | `MeiLei2_SetWorkCsys` | — |
| `meilei2:MeiLei2_ShowAllObj` | 显示所有的对象 | MEILEI2_GUI_TOOL3 / MEILEI2_SHOW_MIN_TOOL | `MeiLei2_ShowAllObj` | — |
| `meilei2:MeiLei2_ShuangSeQiu` | 双色球 | MEILEI2_VERSION_TOOLS | `MeiLei2_ShuangSeQiu` | — |
| `meilei2:MeiLei2_SmartChamfer` | 智能倒角 | MEILEI2_BATCH_TOOL | `MeiLei2_SmartChamfer` | — |
| `meilei2:MeiLei2_SplicingParts` | 排料 | MEILEI2_MOLD_FEATURE_TOOL | `MeiLei2_SplicingParts` | — |
| `meilei2:MeiLei2_Spring` | 弹簧 | MEILEI2_MB_TOOL | `MeiLei2_Spring` | — |
| `meilei2:MeiLei2_StretchFaces` | 拉伸面 | MEILEI2_ELECTRODE_TOOLS | `MeiLei2_StretchFaces` | — |
| `meilei2:MeiLei2_SwitchWindows` | 切换窗口 | MEILEI2_PHOTO_TOOL | `MeiLei2_SwitchWindows` | — |
| `meilei2:MeiLei2_SwitchingRadialSymbol` | 切换径向符号 | MEILEI2_EDIT_DIM_TOOLS | `MeiLei2_SwitchingRadialSymbol` | — |
| `meilei2:MeiLei2_SymbolProjectionAngle` | 插入投影视角图案 | MEILEI2_DWG_TOOLS | `MeiLei2_SymbolProjectionAngle` | — |
| `meilei2:MeiLei2_TemplateTextDynamicUpdate` | 制作图框注释动态更新 | MEILEI2_DWG_TOOLS | `MeiLei2_TemplateTextDynamicUpdate` | — |
| `meilei2:MeiLei2_Text` | 文本注释 | MEILEI2_COMMON_TOOL | `MeiLei2_Text` | — |
| `meilei2:MeiLei2_TextA` | 刻字 | MEILEI2_COMMON_TOOL | `MeiLei2_TextA` | — |
| `meilei2:MeiLei2_TextACenterLine` | 刻字中心线 | MEILEI2_CURVE_TOOL | `MeiLei2_TextACenterLine` | — |
| `meilei2:MeiLei2_TextFaceAttr` | 标记刻字面 | MEILEI2_COMMON_TOOL | `MeiLei2_TextFaceAttr` | — |
| `meilei2:MeiLei2_TimingSavePart` | 设置定时保存部件 | MEILEI2_SET_TOOLS | `MeiLei2_TimingSavePart` | — |
| `meilei2:MeiLei2_ToDxfDwg` | 批量导出dxf/dwg | MEILEI2_DWG_TOOLS | `MeiLei2_ToDxfDwg` | — |
| `meilei2:MeiLei2_ToolPositionVerification` | 刀具位置验证 | MEILEI2_CAM_TOOLS | `MeiLei2_ToolPositionVerification` | — |
| `meilei2:MeiLei2_ToolScreenShot` | 截图 | MEILEI2_PHOTO_TOOL | `MeiLei2_ToolScreenShot` | — |
| `meilei2:MeiLei2_TransformBody` | 变化实体 | MEILEI2_TRANSFORM_TOOL | `MeiLei2_TransformBody` | — |
| `meilei2:MeiLei2_Translucency` | 透明 | MEILEI2_SHOW_TOOL | `MeiLei2_Translucency` | — |
| `meilei2:MeiLei2_TrimBody` | 修剪实体 | MEILEI2_ELECTRODE_TOOLS | `MeiLei2_TrimBody` | — |
| `meilei2:MeiLei2_TwoPointCyl` | 两点圆柱 | MEILEI2_COMMON_TOOL | `MeiLei2_TwoPointCyl` | — |
| `meilei2:MeiLei2_TwoPointPlane` | 两点平面 | MEILEI2_COMMON_TOOL | `MeiLei2_TwoPointPlane` | — |
| `meilei2:MeiLei2_UShapedSlotCutting` | U形定位槽切割 | MEILEI2_BATCH_TOOL | `MeiLei2_UShapedSlotCutting` | — |
| `meilei2:MeiLei2_UnitConversion` | 单位转换 | MEILEI2_COMMON_TOOL | `MeiLei2_UnitConversion` | — |
| `meilei2:MeiLei2_VersionUpgrade` | 版本升级 | MEILEI2_VERSION_TOOLS | `MeiLei2_VersionUpgrade` | — |
| `meilei2:MeiLei2_View3` | 批量三视图 | MEILEI2_DWG_TOOLS | `MeiLei2_View3` | — |
| `meilei2:MeiLei2_View3Template` | 批量三视图模板 | MEILEI2_DWG_TOOLS | `MeiLei2_View3Template` | — |
| `meilei2:MeiLei2_ViewSaveAs` | 保存工作视图 | MEILEI2_DWG_TOOLS | `MeiLei2_ViewSaveAs` | — |
| `meilei2:MeiLei2_WaterContactCheck` | 水路干涉检查 | MEILEI2_GUI_TOOL4 / MEILEI2_ANALYSIS_TOOL | `MeiLei2_WaterContactCheck` | — |
| `meilei2:MeiLei2_gui` | 搞个球 | MEILEI_TWO_UG_MENU | `MeiLei2_gui` | — |
| `meilei2:MeiLei2_gui_1` | 搞个球 | MEILEI2_SET_TOOLS | `MeiLei2_gui` | — |
| `meilei2:NX_ADM_MOVE_FACE_FEATURE_1` | 移动面 | MEILEI2_ELECTRODE_TOOLS | `NX_ADM_MOVE_FACE_FEATURE_1` | — |
| `meilei2:NX_ADM_OFFSET_REGION_FEATURE_1` | 偏置区域 | MEILEI2_ELECTRODE_TOOLS | `NX_ADM_OFFSET_REGION_FEATURE_1` | — |
| `meilei2:NX_ADM_PULL_FACE_FEATURE_1` | 拉出面 | MEILEI2_ELECTRODE_TOOLS | `NX_ADM_PULL_FACE_FEATURE_1` | — |
| `meilei2:NX_MODELING_DELETE_FACE_FEATURE_1` | 删除面 | MEILEI2_ELECTRODE_TOOLS | `NX_MODELING_DELETE_FACE_FEATURE_1` | — |
| `meilei2:NX_MODELING_OFFSET_FEATURE_1` | 偏置面 | MEILEI2_ELECTRODE_TOOLS | `NX_MODELING_OFFSET_FEATURE_1` | — |
| `meilei2:NX_MODELING_REPLACE_FACE_FEATURE_1` | 替换面 | MEILEI2_ELECTRODE_TOOLS | `NX_MODELING_REPLACE_FACE_FEATURE_1` | — |

### 动作类型：模块文件（2 条）

| 复合键 | 中文名 | 菜单 | ACTIONS | 快捷键 |
|---|---|---|---|---|
| `meilei2:MeiLei2_CD_1` | 工具 - 菜单 | MEILEI_TWO_UG_MENU | `MeiLei2_CD_1.utd` | F2 |
| `meilei2:MeiLei2_CD_2` | 标准件 - 菜单 | MEILEI_TWO_UG_MENU | `MeiLei2_CD_2.utd` | F3 |

## 四、标准调用流程（Agent 必须按此执行）

1. `list_plugins()` 确认该外挂已注册、`version_ok_for_nx12=true`。
2. `search('<中文名>', plugin='meilei2')` 定位候选，拿到复合键。
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

