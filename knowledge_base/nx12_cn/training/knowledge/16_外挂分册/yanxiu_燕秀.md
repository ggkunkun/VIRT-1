# 外挂分册：燕秀 UG 模具外挂（`yanxiu`）

> 版本：**NX12.0-CN**　|　厂商目录：`YANGJEE/yanxiu`
> 命令数：219（中文标签 219）
> 风险等级：**LOW**　|　证据：E1-MEDIA（GBK/UTF-8 嗅探解码，直接解析介质 .men；已按 NX12 版本目录过滤）
> **非 Siemens 官方功能**，输出时必须向用户明确标注为第三方外挂。

## 一、能力卡

- 菜单文件：1 个，已排除其它 NX 版本菜单 0 个
- 文件编码：{'gbk': 1}
- 菜单版本：{'120': 1}（NX12 应为 120）
- 动作形态：{'模块文件': 2, '其他': 217}
- 硬编码绝对路径：0 处
- 环境变量依赖：0 处
- 跨外挂重名命令 ID：0 个（必须用复合键 `yanxiu:<ID>`）

## 二、调用前的硬性检查

- ✅ 命令键必须用命名空间：`plugin_id:command_id`；裸 ID 会被判为歧义。

## 三、命令清单

### 动作类型：其他（217 条）

| 复合键 | 中文名 | 菜单 | ACTIONS | 快捷键 |
|---|---|---|---|---|
| `yanxiu:GetFilterMethod_FilterClear` | 取消全部过滤 | X15 | `GetFilterMethod_FilterClear` | — |
| `yanxiu:GetFilterMethod_FilterColor` | 按指定颜色过滤 | X15 | `GetFilterMethod_FilterColor` | — |
| `yanxiu:GetFilterMethod_FilterComponent` | 选择装配组件 | X15 | `GetFilterMethod_FilterComponent` | — |
| `yanxiu:GetFilterMethod_FilterCsys` | 选择Csys | X15 | `GetFilterMethod_FilterCsys` | — |
| `yanxiu:GetFilterMethod_FilterCurve` | 选择线 | X15 | `GetFilterMethod_FilterCurve` | — |
| `yanxiu:GetFilterMethod_FilterDatumn` | 选择基准 | X15 | `GetFilterMethod_FilterDatumn` | — |
| `yanxiu:GetFilterMethod_FilterEdge` | 选择边 | X15 | `GetFilterMethod_FilterEdge` | — |
| `yanxiu:GetFilterMethod_FilterFace` | 选择面 | X15 | `GetFilterMethod_FilterFace` | — |
| `yanxiu:GetFilterMethod_FilterGroup` | 选择组 | X15 | `GetFilterMethod_FilterGroup` | — |
| `yanxiu:GetFilterMethod_FilterSelect` | 选择指定类型 | X15 | `GetFilterMethod_FilterSelect` | — |
| `yanxiu:GetFilterMethod_FilterSheetBody` | 选择片体 | X15 | `GetFilterMethod_FilterSheetBody` | — |
| `yanxiu:GetFilterMethod_FilterSolidBody` | 选择实体 | X15 | `GetFilterMethod_FilterSolidBody` | — |
| `yanxiu:MinTools_4CornerMoveCopyMirr` | 4角镜像 | X13 | `MinTools_4CornerMoveCopyMirr` | — |
| `yanxiu:MinTools_BodyCenterToPoint` | 实体中心到原点移动/复制 | X13 | `MinTools_BodyCenterToPoint` | — |
| `yanxiu:YX_2DUG` | 自动出图UG模式(开发中) | X52 | `YX_Sheet` | — |
| `yanxiu:YX_2d1` | 自动投影零件图 | X52 | `YX_Sheet` | — |
| `yanxiu:YX_2d2` | 自动投影顶针图 | X52 | `YX_Sheet` | — |
| `yanxiu:YX_2d3` | 批量导出2D至CAD | X52 | `YX_Sheet` | — |
| `yanxiu:YX_2d4` | 自动标数 | X52 | `YX_Sheet` | — |
| `yanxiu:YX_AnalysisFaces` | 模仁上色 | X22 | `YX_AnalysisFaces` | — |
| `yanxiu:YX_AnalysisOfGeometric` | 几何分析 | X23 | `YX_AnalysisOfGeometric` | — |
| `yanxiu:YX_AvoidAirUI` | 分型面避空 | X22 | `YX_AvoidAirUI` | — |
| `yanxiu:YX_BackGoroundColor` | 修改背景颜色(循环) | X11 | `YX_BackGoroundColor` | — |
| `yanxiu:YX_BaseFrmSetting` | 设置 | YX | `YX_BaseFrmSetting` | — |
| `yanxiu:YX_BodyZoom` | 产品放缩水 | X22 | `YX_BodyZoom` | — |
| `yanxiu:YX_ClearHighlight` | 清除高亮 | X11 | `YX_ClearHighlight` | — |
| `yanxiu:YX_ColorAll_216_103` | 快速颜色103 | X16 | `YX_MinTools_ColorToolbar` | — |
| `yanxiu:YX_ColorAll_216_108` | 快速颜色108 | X16 | `YX_MinTools_ColorToolbar` | — |
| `yanxiu:YX_ColorAll_216_11` | 快速颜色11 | X16 | `YX_MinTools_ColorToolbar` | — |
| `yanxiu:YX_ColorAll_216_125` | 快速颜色125 | X16 | `YX_MinTools_ColorToolbar` | — |
| `yanxiu:YX_ColorAll_216_164` | 快速颜色164 | X16 | `YX_MinTools_ColorToolbar` | — |
| `yanxiu:YX_ColorAll_216_181` | 快速颜色181 | X16 | `YX_MinTools_ColorToolbar` | — |
| `yanxiu:YX_ColorAll_216_186` | 快速颜色186 | X16 | `YX_MinTools_ColorToolbar` | — |
| `yanxiu:YX_ColorAll_216_211` | 快速颜色211 | X16 | `YX_MinTools_ColorToolbar` | — |
| `yanxiu:YX_ColorAll_216_31` | 快速颜色31 | X16 | `YX_MinTools_ColorToolbar` | — |
| `yanxiu:YX_ColorAll_216_78` | 快速颜色78 | X16 | `YX_MinTools_ColorToolbar` | — |
| `yanxiu:YX_ComputingEquipmentUI` | 计算工具 | X23 | `YX_ComputingEquipmentUI` | — |
| `yanxiu:YX_Cool` | 动态水路 | X35 | `YX_Cool` | — |
| `yanxiu:YX_CorrectionBox` | 校验订料尺寸 | X51 | `YX_CorrectionBox` | — |
| `yanxiu:YX_CreateDatum` | 基准角 (支持装配) | X22 | `YX_CreateDatum` | — |
| `yanxiu:YX_CrossBodyCopy` | 跨体-复制 (支持装配) | X21 | `YX_CrossBodyCopy` | — |
| `yanxiu:YX_CrossBodyDelete` | 跨体-删除 (支持装配) | X21 | `YX_CrossBodyDelete` | — |
| `yanxiu:YX_CrossBodyMirror` | 跨体-镜像 (支持装配) | X21 | `YX_CrossBodyMirror` | — |
| `yanxiu:YX_CrossBodyMove` | 跨体-移动 (支持装配) | X21 | `YX_CrossBodyMove` | — |
| `yanxiu:YX_DeepHoleDrillUI` | 深孔钻自动报价 | X55 | `YX_DeepHoleDrillUI` | — |
| `yanxiu:YX_DeleteBlend` | 批量删除-R角 (支持装配) | X21 | `YX_DeleteBlend` | — |
| `yanxiu:YX_DeleteChamfer` | 批量删除-C角 (支持装配) | X21 | `YX_DeleteChamfer` | — |
| `yanxiu:YX_DeleteHole` | 批量删除-孔 (支持装配) | X21 | `YX_DeleteHole` | — |
| `yanxiu:YX_DeleteText` | 批量删除-字 (支持装配) | X21 | `YX_DeleteText` | — |
| `yanxiu:YX_DynamicCircleUI` | 动态圆 | X23 | `YX_DynamicCircleUI` | — |
| `yanxiu:YX_EditBodyAtt` | 编辑属性 | X51 | `YX_EditBodyAtt` | — |
| `yanxiu:YX_EjpPinDir` | 顶针定位 | X22 | `YX_EjpPinDir` | — |
| `yanxiu:YX_ExtractionLine` | 抽取线 | X22 | `YX_ExtractionLine` | — |
| `yanxiu:YX_FaceRounding` | 面体取整 | X12 | `YX_FaceRounding` | — |
| `yanxiu:YX_FrameAvoidance` | 避空角 (支持装配) | X22 | `YX_FrameAvoidance` | — |
| `yanxiu:YX_FrmAbout` | 关于 | YX | `YX_FrmAbout` | — |
| `yanxiu:YX_Help_UG1` | 帮助/新功能视频 | YX | `YX_Help_UG1` | — |
| `yanxiu:YX_HoleBK` | 孔避空 | X22 | `YX_HoleBK` | — |
| `yanxiu:YX_InclusionBody` | 包容体 | X12 | `YX_InclusionBody` | — |
| `yanxiu:YX_InsertDatum` | 顶块基准 | X22 | `YX_InsertDatum` | — |
| `yanxiu:YX_IntelligenceChamfer` | 智能倒角 (支持装配) | X21 | `YX_IntelligenceChamfer` | — |
| `yanxiu:YX_KOHole` | KO孔 | X22 | `YX_KOHole` | — |
| `yanxiu:YX_LAYER_TYPE1` | 前模仁 | X141 | `YX_MinTools_LayerToolbar` | — |
| `yanxiu:YX_LAYER_TYPE11` | 产品 | X141 | `YX_MinTools_LayerToolbar` | — |
| `yanxiu:YX_LAYER_TYPE12` | 全套模具 | X141 | `YX_MinTools_LayerToolbar` | — |
| `yanxiu:YX_LAYER_TYPE13` | 前模组 | X141 | `YX_MinTools_LayerToolbar` | — |
| `yanxiu:YX_LAYER_TYPE14` | 后模组 | X141 | `YX_MinTools_LayerToolbar` | — |
| `yanxiu:YX_LAYER_TYPE15` | 前模胚 | X141 | `YX_MinTools_LayerToolbar` | — |
| `yanxiu:YX_LAYER_TYPE16` | 后模胚 | X141 | `YX_MinTools_LayerToolbar` | — |
| `yanxiu:YX_LAYER_TYPE2` | 后模仁 | X141 | `YX_MinTools_LayerToolbar` | — |
| `yanxiu:YX_LAYER_TYPE3` | 前模镶件 | X141 | `YX_MinTools_LayerToolbar` | — |
| `yanxiu:YX_LAYER_TYPE4` | 后模镶件 | X141 | `YX_MinTools_LayerToolbar` | — |
| `yanxiu:YX_LAYER_TYPE5` | 滑块 | X141 | `YX_MinTools_LayerToolbar` | — |
| `yanxiu:YX_LAYER_TYPE6` | 斜顶 | X141 | `YX_MinTools_LayerToolbar` | — |
| `yanxiu:YX_LAYER_TYPE7` | 顶针 | X141 | `YX_MinTools_LayerToolbar` | — |
| `yanxiu:YX_LAYER_TYPE8` | 前模运水 | X141 | `YX_MinTools_LayerToolbar` | — |
| `yanxiu:YX_LAYER_TYPE9` | 后模运水 | X141 | `YX_MinTools_LayerToolbar` | — |
| `yanxiu:YX_LayerAll_256_10` | 10图层开关/快速移到层 | X141 | `YX_MinTools_LayerToolbar` | — |
| `yanxiu:YX_LayerAll_256_100` | 100图层开关/快速移到层 | X141 | `YX_MinTools_LayerToolbar` | — |
| `yanxiu:YX_LayerAll_256_110` | 110图层开关/快速移到层 | X141 | `YX_MinTools_LayerToolbar` | — |
| `yanxiu:YX_LayerAll_256_18` | 18图层开关/快速移到层 | X141 | `YX_MinTools_LayerToolbar` | — |
| `yanxiu:YX_LayerAll_256_20` | 20图层开关/快速移到层 | X141 | `YX_MinTools_LayerToolbar` | — |
| `yanxiu:YX_LayerAll_256_28` | 28图层开关/快速移到层 | X141 | `YX_MinTools_LayerToolbar` | — |
| `yanxiu:YX_LayerAll_256_30` | 30图层开关/快速移到层 | X141 | `YX_MinTools_LayerToolbar` | — |
| `yanxiu:YX_LayerAll_256_40` | 40图层开关/快速移到层 | X141 | `YX_MinTools_LayerToolbar` | — |
| `yanxiu:YX_LayerAll_256_70` | 70图层开关/快速移到层 | X141 | `YX_MinTools_LayerToolbar` | — |
| `yanxiu:YX_LiftAvoidEmpty` | 斜顶避空 | X22 | `YX_LiftAvoidEmpty` | — |
| `yanxiu:YX_MPPriceInitial` | 模胚全加工自动报价 | X55 | `YX_MPPriceInitial` | — |
| `yanxiu:YX_MinTools_AssemblyRename` | 装配重命名 | X53 | `YX_MinTools_AssemblyRename` | — |
| `yanxiu:YX_MinTools_AssemblySplit` | 装配拆分 | X53 | `YX_MinTools_AssemblySplit` | — |
| `yanxiu:YX_MinTools_AssemblyTree` | 装配初始化 | X53 | `YX_MinTools_AssemblyTree` | — |
| `yanxiu:YX_MinTools_BalanceCornePlaneUI` | 平衡块 | X32 | `YX_MinTools_BalanceCornePlaneUI` | — |
| `yanxiu:YX_MinTools_BarbUI` | 强制复位 | X34 | `YX_MinTools_BarbUI` | — |
| `yanxiu:YX_MinTools_BlockWorkBlankUI` | 模仁毛坯 | X22 | `YX_MinTools_BlockWorkBlankUI` | — |
| `yanxiu:YX_MinTools_BodyCancelTranslucency` | 一键取消透明 | X12 | `YX_MinTools_BodyCancelTranslucency` | — |
| `yanxiu:YX_MinTools_BodyCenLine` | 中心线 (支持装配) | X12 | `YX_MinTools_BodyCenLine` | — |
| `yanxiu:YX_MinTools_BodyFaceCombine` | 批量实体面连接 | X21 | `YX_MinTools_BodyFaceCombine` | — |
| `yanxiu:YX_MinTools_BodyLanyerAdditive` | 1个体归1个层 | X14 | `YX_MinTools_BodyLanyerAdditive` | — |
| `yanxiu:YX_MinTools_BodySplit` | 批量分割 | X21 | `YX_MinTools_BodySplit` | — |
| `yanxiu:YX_MinTools_BodySubtract` | 批量对象求差 | X21 | `YX_MinTools_BodySubtract` | — |
| `yanxiu:YX_MinTools_BodyText` | 刻字 (支持装配) | X12 | `YX_MinTools_BodyText` | — |
| `yanxiu:YX_MinTools_BodyTranslucency` | 透明 (支持装配) | X12 | `YX_MinTools_BodyTranslucency` | — |
| `yanxiu:YX_MinTools_BodyUnite` | 批量对象求和 | X21 | `YX_MinTools_BodyUnite` | — |
| `yanxiu:YX_MinTools_BodysBox` | 测量实体 (支持装配) | X12 | `YX_MinTools_BodysBox` | — |
| `yanxiu:YX_MinTools_BomDisplay` | BOM清单 | X51 | `YX_MinTools_BomDisplay` | — |
| `yanxiu:YX_MinTools_CoincideObj` | 重合对象 | X12 | `YX_MinTools_CoincideObj` | — |
| `yanxiu:YX_MinTools_ColorToolbar` | 配置颜色工具条 | X16 | `YX_MinTools_ColorToolbar` | — |
| `yanxiu:YX_MinTools_CoolCsysTubeUI` | 复杂水路 | X35 | `YX_MinTools_CoolCsysTubeUI` | — |
| `yanxiu:YX_MinTools_CoolCsysWellUI` | 水井 | X35 | `YX_MinTools_CoolCsysWellUI` | — |
| `yanxiu:YX_MinTools_CoolLibUI` | 水路零件 | X35 | `YX_MinTools_CoolLibUI` | — |
| `yanxiu:YX_MinTools_CoolPipeUI` | 模板水路 | X35 | `YX_MinTools_CoolPipeUI` | — |
| `yanxiu:YX_MinTools_CoolTubeUI` | 运水管 | X35 | `YX_MinTools_CoolTubeUI` | — |
| `yanxiu:YX_MinTools_CounterTravelSwitch` | 计数器/行程开关 | X32 | `YX_MinTools_CounterTravelSwitch` | — |
| `yanxiu:YX_MinTools_DateStamp` | 日期章 | X32 | `YX_MinTools_DateStamp` | — |
| `yanxiu:YX_MinTools_DeepHoleDrill` | 钻孔基准台 | X22 | `YX_MinTools_DeepHoleDrill` | — |
| `yanxiu:YX_MinTools_DirectionMove_move` | 平行移动/复制 | X13 | `YX_MinTools_DirectionMove_move` | — |
| `yanxiu:YX_MinTools_EjectionTrim` | 顶针修剪 | X34 | `YX_MinTools_EjectionTrim` | — |
| `yanxiu:YX_MinTools_EjectionUI` | 顶针 | X34 | `YX_MinTools_EjectionUI` | — |
| `yanxiu:YX_MinTools_EjpPlatePart` | 顶针板零件 | X32 | `YX_MinTools_EjpPlatePart` | — |
| `yanxiu:YX_MinTools_ExportX_T` | 快速导出(支持装配) | X11 | `YX_MinTools_ExportX_T` | — |
| `yanxiu:YX_MinTools_FaceBodyWcs` | 坐标系 | X12 | `YX_MinTools_FaceBodyWcs` | — |
| `yanxiu:YX_MinTools_FaceCylindrical` | 批量自动补圆孔 | X21 | `YX_MinTools_FaceCylindrical` | — |
| `yanxiu:YX_MinTools_FaceReplace` | 批量替换面 | X21 | `YX_MinTools_FaceReplace` | — |
| `yanxiu:YX_MinTools_FrmOpenFileForm` | 打开UG文件(批量导入) | X11 | `YX_MinTools_FrmOpenFileForm` | — |
| `yanxiu:YX_MinTools_GearBodyUI` | 齿轮 | X36 | `YX_MinTools_GearBodyUI` | — |
| `yanxiu:YX_MinTools_GearRackBodyUI` | 直齿条 | X36 | `YX_MinTools_GearRackBodyUI` | — |
| `yanxiu:YX_MinTools_GrooveFaceOffset` | 批量偏移面(避空) | X21 | `YX_MinTools_GrooveFaceOffset` | — |
| `yanxiu:YX_MinTools_LayerBrowse` | 浏览图层 | X14 | `YX_MinTools_LayerBrowse` | — |
| `yanxiu:YX_MinTools_LayerToolbar` | 配置图层工具条 | X141 | `YX_MinTools_LayerToolbar` | — |
| `yanxiu:YX_MinTools_LibManager` | 零件库管理配置 | X31 | `YX_MinTools_LibManager` | — |
| `yanxiu:YX_MinTools_LiftBaseUI` | 斜顶座 | X36 | `YX_MinTools_LiftBaseUI` | — |
| `yanxiu:YX_MinTools_LiftHeadUI` | 斜顶头 | X36 | `YX_MinTools_LiftHeadUI` | — |
| `yanxiu:YX_MinTools_LiftPlanteUI` | 斜顶导向块 | X36 | `YX_MinTools_LiftPlanteUI` | — |
| `yanxiu:YX_MinTools_LocKAxisMove_move` | 锁轴移动/复制 | X13 | `YX_MinTools_LocKAxisMove_move` | — |
| `yanxiu:YX_MinTools_LocatingBlockUI` | 精定位 | X32 | `YX_MinTools_LocatingBlockUI` | — |
| `yanxiu:YX_MinTools_LockPlaneUI` | 挤压块 | X32 | `YX_MinTools_LockPlaneUI` | — |
| `yanxiu:YX_MinTools_MBPlateGRFC` | 隔热板/防尘板 | X32 | `YX_MinTools_MBPlateGRFC` | — |
| `yanxiu:YX_MinTools_MatchpropColorUI` | 颜色刷子/随机颜色 | X12 | `YX_MinTools_MatchpropColorUI` | — |
| `yanxiu:YX_MinTools_ModifPartInformation` | 设置项目信息 | X51 | `YX_MinTools_ModifPartInformation` | — |
| `yanxiu:YX_MinTools_MoldBaseGP` | 模胚配件 | X32 | `YX_MinTools_MoldBaseGP` | — |
| `yanxiu:YX_MinTools_MouldBaseUser` | 非标模胚 | X32 | `YX_MinTools_MouldBaseUser` | — |
| `yanxiu:YX_MinTools_OilCylinderUI` | 油缸 | X36 | `YX_MinTools_OilCylinderUI` | — |
| `yanxiu:YX_MinTools_OneselfRotating_move` | 实体自转移动/复制 | X13 | `YX_MinTools_OneselfRotating_move` | — |
| `yanxiu:YX_MinTools_PointGateBulge` | 波点\火山口 | X22 | `YX_MinTools_PointGateBulge` | — |
| `yanxiu:YX_MinTools_PointGateUI` | 开模控制零件 | X33 | `YX_MinTools_PointGateUI` | — |
| `yanxiu:YX_MinTools_PointToPoint_move` | 点到点移动/复制 | X13 | `YX_MinTools_PointToPoint_move` | — |
| `yanxiu:YX_MinTools_PressingPlate` | 压板 | X32 | `YX_MinTools_PressingPlate` | — |
| `yanxiu:YX_MinTools_PullerPinUI` | 钩针 | X33 | `YX_MinTools_PullerPinUI` | — |
| `yanxiu:YX_MinTools_RemoveDispParms` | 杀参 | X12 | `YX_MinTools_RemoveDispParms` | — |
| `yanxiu:YX_MinTools_RepairFace` | 修复破面 | X12 | `YX_MinTools_RepairFace` | — |
| `yanxiu:YX_MinTools_Rotating_move` | 以点旋转移动/复制 | X13 | `YX_MinTools_Rotating_move` | — |
| `yanxiu:YX_MinTools_SaveBackup` | 保存并备份 | X11 | `YX_MinTools_SaveBackup` | — |
| `yanxiu:YX_MinTools_SaveBackupAll` | 本级装配含子零件-保存并备份 | X11 | `YX_MinTools_SaveBackupAll` | — |
| `yanxiu:YX_MinTools_Screenshot` | 固定大小截图 | X11 | `YX_MinTools_Screenshot` | — |
| `yanxiu:YX_MinTools_Screenshot2` | 截图 | X11 | `YX_MinTools_Screenshot2` | — |
| `yanxiu:YX_MinTools_ScrewEjectorPinIdentifyUI` | 自动识别螺丝顶针 | X51 | `YX_MinTools_ScrewEjectorPinIdentifyUI` | — |
| `yanxiu:YX_MinTools_SetObjColor` | 设置对象颜色 (支持装配) | X12 | `YX_MinTools_SetObjColor` | — |
| `yanxiu:YX_MinTools_SingleAxisMove_move` | 点到点单轴移动/复制 | X13 | `YX_MinTools_SingleAxisMove_move` | — |
| `yanxiu:YX_MinTools_SlideBaseUI` | 滑块座 | X36 | `YX_MinTools_SlideBaseUI` | — |
| `yanxiu:YX_MinTools_SlidePinUI` | 斜导柱 | X36 | `YX_MinTools_SlidePinUI` | — |
| `yanxiu:YX_MinTools_SlidePlateUI` | 滑块压条 | X36 | `YX_MinTools_SlidePlateUI` | — |
| `yanxiu:YX_MinTools_SlideWedgeUI` | 铲机 | X36 | `YX_MinTools_SlideWedgeUI` | — |
| `yanxiu:YX_MinTools_SliderGuideBlockUI` | 滑块导向 | X36 | `YX_MinTools_SliderGuideBlockUI` | — |
| `yanxiu:YX_MinTools_SliderLockBlockUI` | 滑块限位 | X36 | `YX_MinTools_SliderLockBlockUI` | — |
| `yanxiu:YX_MinTools_SnapToClosestCannedOrientation` | 用户坐标F8摆正 | X12 | `YX_MinTools_SnapToClosestCannedOrientation` | — |
| `yanxiu:YX_MinTools_SpeedSelectObj` | 快速选择对象 | X15 | `YX_MinTools_SpeedSelectObj` | — |
| `yanxiu:YX_MinTools_SplitPinStep` | 拆镶针/镶件挂台 | X22 | `YX_MinTools_SplitPinStep` | — |
| `yanxiu:YX_MinTools_SpringPart` | 弹簧/氮气弹簧/弹力胶 | X32 | `YX_MinTools_SpringPart` | — |
| `yanxiu:YX_MinTools_StartLibProgramMethod` | 启动共享库主程序 | X31 | `YX_MinTools_StartLibProgramMethod` | — |
| `yanxiu:YX_MinTools_StopPlateSupport` | 安全扣/模脚 | X32 | `YX_MinTools_StopPlateSupport` | — |
| `yanxiu:YX_MinTools_ViewShowUI` | 显示管理器 | X14 | `YX_MinTools_ViewShowUI` | — |
| `yanxiu:YX_MinTools_WearPlaneUI` | 耐磨块 | X36 | `YX_MinTools_WearPlaneUI` | — |
| `yanxiu:YX_MinTools_YX_Lib_PartsLibraryUI` | 零件库 | X31 | `YX_MinTools_YX_Lib_PartsLibraryUI` | — |
| `yanxiu:YX_MinTools_deleteDispObj` | 删除点\线\基准\草图\注释\图层类别\工程图等. | X12 | `YX_MinTools_deleteDispObj` | — |
| `yanxiu:YX_MoldBase` | 模胚 | X32 | `YX_MoldBase` | — |
| `yanxiu:YX_MoldPdf` | 燕秀标准件PDF目录 | YX | `YX_MoldPdf` | — |
| `yanxiu:YX_OilGroove` | 油槽 (支持装配) | X22 | `YX_OilGroove` | — |
| `yanxiu:YX_OpenMoldUgOnPath` | 打开燕秀UG模具安装目录 | X11 | `YX_OpenMoldUgOnPath` | — |
| `yanxiu:YX_PartingSurfaceUI` | 分型面工具 | X22 | `YX_PartingSurfaceUI` | — |
| `yanxiu:YX_PositioningTable` | 虎口 | X22 | `YX_PositioningTable` | — |
| `yanxiu:YX_PryGroove` | 撬模槽 (支持装配) | X22 | `YX_PryGroove` | — |
| `yanxiu:YX_ReferenceChamfering` | 参考倒角 | X21 | `YX_ReferenceChamfering` | — |
| `yanxiu:YX_ScreenNotesUI` | 屏幕注释 | X11 | `YX_ScreenNotesUI` | — |
| `yanxiu:YX_Screw` | 螺丝 | X32 | `YX_Screw` | — |
| `yanxiu:YX_Segmentation` | 实体分割 | X12 | `YX_Segmentation` | — |
| `yanxiu:YX_SelectedFaceWCS_Z` | 摆正实体 | X12 | `YX_SelectedFaceWCS_Z` | — |
| `yanxiu:YX_SelectedShowObj` | 隐藏选取外对象 | X14 | `YX_SelectedShowObj` | — |
| `yanxiu:YX_SetBodyAttUI` | 设置实体属性 | X51 | `YX_SetBodyAttUI` | — |
| `yanxiu:YX_ShortcutKeyForm` | 快捷键(空格执行) | YX | `YX_ShortcutKeyForm` | — |
| `yanxiu:YX_Slotting` | 开框 (支持装配) | X22 | `YX_Slotting` | — |
| `yanxiu:YX_SplicingParts` | 拼料 | X22 | `YX_SplicingParts` | — |
| `yanxiu:YX_Sprue` | 唧嘴定位环 | X33 | `YX_Sprue` | — |
| `yanxiu:YX_UG_EDIT_BLANK_SELECTED` | 隐藏对象 | X14 | `YX_UG_EDIT_BLANK_SELECTED` | — |
| `yanxiu:YX_UG_EDIT_UNBLANK_ALL_OF_PART` | 显示全部隐藏对象 | X14 | `YX_UG_EDIT_UNBLANK_ALL_OF_PART` | — |
| `yanxiu:YX_UpData` | 升级 | YX | `YX_UpData` | — |
| `yanxiu:YX_VersionConversion` | 降版本 | X11 | `YX_VersionConversion` | — |
| `yanxiu:YX_WireCuttingQuotationUI` | 线切割自动报价 | X55 | `YX_WireCuttingQuotationUI` | — |
| `yanxiu:YX_buyweb` | 燕秀商城--(购买配件) | YX | `YX_buyweb` | — |
| `yanxiu:YX_closeAllLayer` | 关闭所有图层 | X14 | `YX_closeAllLayer` | — |
| `yanxiu:YX_closeSelectedObjlayer` | 关闭选取图层 | X14 | `YX_closeSelectedObjlayer` | — |
| `yanxiu:YX_download` | 下载燕秀其他软件 | YX | `YX_download` | — |
| `yanxiu:YX_layerNotShow` | 反向关闭图层 | X14 | `YX_layerNotShow` | — |
| `yanxiu:YX_openAllLayer` | 打开所有图层 | X14 | `YX_openAllLayer` | — |
| `yanxiu:YX_openAllLayerOrShow` | 打开所有层并显示隐藏 | X14 | `YX_openAllLayerOrShow` | — |
| `yanxiu:YX_openBotObjWork` | 下一个有对象层 | X14 | `YX_openBotObjWork` | — |
| `yanxiu:YX_openBotWork` | 下一层 | X14 | `YX_openBotWork` | — |
| `yanxiu:YX_openSelectedObjlayer` | 关闭选取外图层 | X14 | `YX_openSelectedObjlayer` | — |
| `yanxiu:YX_openUpObjWork` | 上一个有对象层 | X14 | `YX_openUpObjWork` | — |
| `yanxiu:YX_openUpWork` | 上一层 | X14 | `YX_openUpWork` | — |
| `yanxiu:YX_openWorkPartPath` | 打开Prt文件夹 | X11 | `YX_openWorkPartPath` | — |
| `yanxiu:YanXiuCustomization_YX_DPBlockUI` | 定位销 | X32 | `YanXiuCustomization_YX_DPBlockUI` | — |
| `yanxiu:Yx_BulkCopy` | 批量复制/替换 | X21 | `Yx_BulkCopy` | — |
| `yanxiu:Yx_ExhaustDesign` | 排气 | X22 | `Yx_ExhaustDesign` | — |
| `yanxiu:Yx_Gate` | 进胶点 | X33 | `Yx_Gate` | — |
| `yanxiu:Yx_InterferenceCoolCheck_Sel` | 水路干涉检查 | X23 | `Yx_InterferenceCoolCheck_Sel` | — |
| `yanxiu:Yx_InterferencePieceCheck_Sel` | 零件干涉检查 | X23 | `Yx_InterferencePieceCheck_Sel` | — |
| `yanxiu:Yx_Runner` | 流道 | X33 | `Yx_Runner` | — |

### 动作类型：模块文件（2 条）

| 复合键 | 中文名 | 菜单 | ACTIONS | 快捷键 |
|---|---|---|---|---|
| `yanxiu:YX_formUtd1` | 标准件-菜单 | YX | `YX_UTD1.utd` | F3 |
| `yanxiu:YX_formUtd2` | 工具-菜单 | YX | `YX_UTD2.utd` | F4 |

## 四、标准调用流程（Agent 必须按此执行）

1. `list_plugins()` 确认该外挂已注册、`version_ok_for_nx12=true`。
2. `search('<中文名>', plugin='yanxiu')` 定位候选，拿到复合键。
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

