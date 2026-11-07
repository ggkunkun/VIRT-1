# -*- coding: utf-8 -*-
"""
Virtu CAD/CAM 工业训练数据集修复与高质量扩充脚本 (完整一体化版)
"""

import os
import json
import hashlib

DATA_DIR = r"E:\数据"

SYS_PROMPT = (
    "你是由 Virtu 工业模型驱动的非标自动化全流程设计智能体（CAD/CAM/Automation AI Agent）。"
    "你具备深厚的机械设计与工业自动化工程知识，能够揣测用户意图，将非标自动化设备拆解为子机构与零部件，"
    "自主调用专业工具完成标准件选型、参数化建模、工程图标注、装配配合、宏批量输出等全流程工业设计任务。"
)

def make_sft_item(user_content, assistant_content):
    return {
        "messages": [
            {"role": "system", "content": SYS_PROMPT},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": assistant_content}
        ]
    }

# ==========================================
# 1. 扩充 工装夹具设计规则 (07_FIXTURES_AND_TOOLING)
# ==========================================
fixture_items = [
    make_sft_item(
        "在大型薄壁铝合金机匣或异形箱体数控加工夹具中，工件由于刚性较差，切削力和夹紧力极易引起薄壁局部下陷与震颤，导致壁厚超差和表面波纹。请阐述「浮动自位辅助支撑」（液压锁定式或弹簧自锁式）的工作原理、布置原则，以及在设计时如何避免辅助支撑破坏「六点定位原则」造成过定位？",
        """在大型薄壁铝合金件或异形薄壁箱体的数控切削夹具设计中，**浮动自位辅助支撑（Floating Self-aligning Auxiliary Support）**是抑制加工颤振、补偿刚性不足的关键机构。

### 1. 浮动自位辅助支撑工作原理
浮动支撑通常包含三段动作：
1. **轻力接触阶段**：工件在主定位元件（如一面两销）上完全定位并施加轻微预夹紧后，辅助支撑头在弱弹簧推力（通常仅 5~15 N）或微弱气压作用下浮动伸出，无应力贴合工件背部的自由曲面或薄壁悬空区域；
2. **刚性锁紧阶段**：支撑头贴紧工件后，通过液压油压（例如 7~10 MPa 液压锁紧轴套）或机械双斜楔机构从径向将其抱紧锁死，使活动顶杆变为刚性支承柱；
3. **承载切削阶段**：在切削力向下施加时，支撑柱直接将切削抗力传递至夹具体底座，切削力不直接引起薄壁弯曲变形。

### 2. 避免破坏「六点定位原则」的关键设计要点
- **绝对从属顺序（时序隔离）**：主定位基准（3个定位块）限制工件的 Z 轴平动及 X/Y 旋转等主自由度。辅助支撑的接触力必须远小于主定位面的重力与预紧力，不能将工件从基准定位元件上顶起或抬高；
- **锁死后不产生位移**：锁紧套必须设计为径向抱紧或对称斜向锁紧，轴向窜动量必须控制在 <= 2 μm，防止锁紧动作本身顶移工件；
- **机构刚度校核**：液压锁紧轴套在额定油压下的抗后退摩擦承载力通常需达到 F_hold >= 3000 N，确保在立铣刀主切削分力冲击下无轴向微退缩。

### 3. 布置原则
- 辅助支撑应布置在大切削负荷点下方、远离主定位支承的悬臂外缘，以及固有振型波峰节点处；
- 每个薄壁悬空跨度大于 120 mm 的区域至少设置 1 处自位支撑，有效提高工件动刚度 3~5 倍。"""
    ),
    make_sft_item(
        "在数控机床夹具设计中，气动转角下压气缸（如 SMC MKB 系列或 FESTO CLR 系列）被广泛用于快速压紧工件。请分析转角下压气缸的运动轨迹（转角行程与直线夹紧行程），并说明在设计配套压板长度和夹紧力计算时，为什么必须严格校核活塞杆所受的附加偏心翻转力矩？",
        """气动转角下压气缸是实现夹具自动化快速装卸的标准化核心执行元件。

### 1. 运动轨迹与行程分解
转角下压气缸的完整下行过程分为两个连续阶段：
1. **转角行程（Rotary Stroke，通常为 90°）**：活塞内部导向槽驱动活塞杆先作复合螺旋下沉旋转，压板从避让工件的待机角度旋转至工件正上方。此阶段严禁接触工件，若在旋转段提前接触工件，内部导向销与螺旋槽将承受极端侧向剪切而损坏；
2. **直线压紧行程（Clamping Stroke，通常 10~20 mm）**：转角完成后，活塞杆仅沿轴线垂直向下运动，压板压头接触工件施加垂直正压力完成夹紧。

### 2. 附加偏心翻转力矩校核与压板长度限制
- **偏心力臂 L 带来的力矩**：压板压头中心至气缸活塞杆轴线的距离为偏心力臂 L。在夹紧力 F_clamp 作用下，活塞杆导向套承受侧向倾覆力矩：
  M = F_clamp * L
- **导套磨损与卡死风险**：气缸内部青铜或自润滑导套间隙极其精密（通常 0.02~0.04 mm）。当 L 过长或惯性过大时，M 超出允许弯矩 M_max，将导致活塞杆拉毛划伤、漏气甚至卡死。
- **压板设计准则**：
  1. 压板力臂应尽量缩短，通常 L <= 1.5 * D_bore（D_bore 为气缸缸径）；
  2. 当因结构干涉必须采用长力臂压板（L > 100 mm）时，必须在压板外缘设置独立的外导向支承柱，分担倾覆力矩，保护气缸杆只受纯拉力。"""
    ),
    make_sft_item(
        "在精密多工位组合机床与五轴数控回转工作台中，端齿盘（Hirth Coupling / 鼠牙盘）是核心定位元件。请说明端齿盘实现高重复定位精度（可达 ±1 角秒）的自定心接触原理与分度啮合机制，并计算额定夹紧扭矩下的齿面接触应力校核方法。",
        """端齿盘（Hirth Coupling / 鼠牙盘）是工业机床实现超高重复定位精度与高抗扭刚度的精密机械联轴定位机构。

### 1. 自定心与多齿均载原理
- **直齿/梯形齿辐射啮合**：端齿盘由上下两片（或三片，含升降松开齿盘）具有相同齿数 Z（如 72 齿对应 5° 分度，144 齿对应 2.5° 分度）的环形齿盘组成。每个齿沿径向辐射分布，齿形角通常为 β = 60°；
- **全齿同时接触定心**：液压缸通过碟簧或油压将动齿盘与定齿盘强力压合。由于斜齿面左右两侧同时对中挤压，齿盘在 X, Y, Z 平动与倾斜方向上形成强制几何中心约束，无间隙自定心；
- **误差均化效应**：不同于销钉单点定位，端齿盘在啮合时是全部 Z 个齿面同时接触受力。单齿微小的加工公差被整周齿面均化，因此重复定位精度高达 ±1 角秒，刚性极高。

### 2. 齿面接触应力校核
在轴向液压拉紧力 F_a 与外加扭矩 T 复合作用下，齿面受力分析：
1. **齿面法向力 F_n**：考虑齿面倾角 β = 60°，轴向预紧力在全齿面产生的法向压力合力为：
   F_n = F_a / sin(β/2) = F_a / sin(30°) = 2 * F_a
2. **有效接触面积 A_eff**：
   A_eff = Z * l_tooth * h_tooth * η
   其中 l_tooth 为齿面接触径向长度，h_tooth 为啮合工作齿高，η 为实际接触系数（精磨配合通常取 η = 0.70~0.85）。
3. **接触应力校核**：
   σ_c = F_n / A_eff <= [σ_c]
   通常端齿盘采用渗碳淬火合金钢 20CrMnTi 或 42CrMo 氮化处理，表面硬度达 58~62 HRC，许用接触应力 [σ_c] = 800~1000 MPa，确保承受高转矩切削时不产生微观塑性变形。"""
    ),
    make_sft_item(
        "在白车身机器人焊接夹具中，大型气动翻转臂在由气缸驱动展开时容易发生惯性冲击，闭合夹紧时则要求高定位精度。请阐述翻转夹紧机构中重力平衡配重设计、气缸铰接点与死点位置的运动学规划原则，以及如何设置安全防坠落防夹伤机构？",
        """在汽车白车身自动化焊接工装夹具中，翻转臂机构必须同时保证快速节拍、零冲击与人机安全。

### 1. 翻转臂重力平衡与动力学规划
- **偏心重力力矩补偿**：翻转臂从水平夹紧位翻转到垂直打开位（开度通常 75°~90°）过程中，重心到回转轴的力臂产生变载荷力矩 M_g(θ) = m * g * r_cg * cos(θ)。应在回转轴后端配置铸铁平衡配重块或氮气气弹簧支承，使得整个翻转行程中综合力矩波动小于初始力矩的 20%，降低气缸缸径需求；
- **两端液压缓冲与气缸气缓冲**：在接近打开与闭合终点 15° 区域内，利用气缸内置行程末端可调气缓冲，并在夹具框架上加装外置液压减震器（如 ACE / ENIDINE 品牌），吸收大惯量翻转动能，避免基准撞击变形。

### 2. 连杆过死点与气缸推力储备
- **闭合位过死点自锁**：连杆机构在到达工件完全夹紧位置时，驱动铰链中心微量越过受力连线 1°~2°，形成机械死点。当车间气源意外断气（0 MPa）时，焊接热应力与工件反力不能推开夹臂，确保夹紧可靠；
- **推力储备系数**：夹紧气缸推力储备系数规定取 K >= 2.0~2.5，克服机构销轴摩擦阻力与气压波动。

### 3. 安全防坠落机构（Safety Catch）
- 依据汽车厂安全规范，翻转角度 > 45° 且运动质量 > 25 kg 的翻转臂，必须在回转主轴处集成气动常闭式棘轮防坠锁（Pneumatic Rod Lock / Drop Stop）；
- 仅当控制系统发送“翻转使能信号且安全光栅未被触发”时，先导电磁阀通气打开锁芯；一旦急停或断电断气，弹簧驱动机械销瞬间锁入棘轮齿，防止夹臂重力坠落砸伤人员或损坏治具。"""
    )
]

# ==========================================
# 2. 扩充 机构动画与高级造型 (08_ANIMATION_AND_CURRICULUM)
# ==========================================
animation_items = [
    make_sft_item(
        "在 SolidWorks 高级曲面造型中，针对流线型外壳、异形过渡支架等零件，为什么草图交界处采用「相切（G1）」往往会出现明显的光影折痕，而必须使用「曲率连续（G2）」？请说明在 SolidWorks 边界曲面与放样曲面中控制 G2 连续性的具体操作方法与斑马线（Zebra Stripes）检测判据。",
        """在三维 CAD 高级曲面建模中，曲面连接的连续性等级决定了外观工业设计的流线质感与空气动力学/模具成型平滑度。

### 1. G0 / G1 / G2 连续性的数学与光学差异
- **G0（位置连续）**：两曲面边缘共享相同空间点坐标，但切向量方向突变。视觉上形成清晰折痕棱线，法向量不连续；
- **G1（相切连续）**：两曲面在公共交界线上切线方向一致（法向量相同），但曲率半径发生跳变。光照渲染时，高光反射线在交界处发生尖锐折折断，称为“光影折痕”；
- **G2（曲率连续）**：两曲面在公共边界处不仅切向量一致，且截面曲率半径 R 与曲率中心连续过渡（二次导数连续）。高光反射线与斑马线平滑平顺过渡，完全没有视觉接缝。

### 2. SolidWorks 边界曲面中的 G2 控制操作
1. **优先使用【边界曲面】替代传统【放样曲面】**：边界曲面在方向 1 和方向 2 的所有边缘均提供独立的高阶连续性约束选项；
2. **设置边界相切条件**：在边界曲面属性管理器中，将与相邻曲面接触的边界曲线约束从默认的【无】或【相切面 (G1)】下拉切换为【曲率面 (G2)】；
3. **调整切线影响度滑块**：将【切线影响度（%）】滑块从默认 0% 提升至 50%~100%，让曲率连续的影响过渡均匀渗透进曲面内部，避免边缘局部突变；
4. **控制引导线质量**：引导线草图与相邻边界线之间必须添加【与曲率连续】几何关系约束，草图基准曲线阶数建议为 5 阶（拥有 6 个控制点）的样条曲线。

### 3. 斑马线（Zebra Stripes）检测判据
开启【评估】->【斑马线】工具：
- 若黑白条纹在公共交界处断开错位：仅为 G0 连续；
- 若黑白条纹在交界处虽连接但出现尖锐拐角：为 G1 连续；
- 若黑白条纹在交界处以平滑的圆弧平顺过渡延伸：达到严格的 G2 连续。"""
    ),
    make_sft_item(
        "在非标自动化设备设计中，自顶向下（Top-Down）的「骨架模型驱动（Skeleton-Driven Modeling）」是如何运作的？请详述在 SolidWorks 装配体中如何建立总布置骨架零件，如何通过外部参考将运动行程、电机安装位、导轨跨距传递给子装配体与零部件，以及在出图前如何解除或锁定外部参考以防文件报错？",
        """自顶向下（Top-Down）骨架模型驱动是高端非标自动化设备设计中防止干涉、快速响应客户节拍与行程修改的现代数字化工程方法。

### 1. 骨架模型（Skeleton Part）的建立机制
1. **总布置布局草图（Layout Sketch）**：在设备根装配体下新建一个虚拟零部件（如 Skeleton_Master.SLDPRT），将其固定在装配体原点；
2. **参数化主尺寸驱动**：在骨架零件的 3D 草图或多平面草图中，使用带明确工程语义的全局变量（如 Stroke_X=600, Puck_Pitch=120, Turntable_OD=900, Machine_Height=1650）绘制机构运动包络线、主传动轴中心线、各工位分度角度线；
3. **空间定位基准面（Datum Planes）**：根据工站划分，在骨架零件中建立各工序子机构的挂载基准面。

### 2. 外部参考传递给子装配体
- **派生草图与几何体引用**：在子机构（如 X 轴运动滑台）建模时，使用【在装配体中编辑零部件】，通过【转换实体引用】直接拾取骨架零件的导轨中心线与行程极值草图；
- **联动修改能力**：当生产工艺要求工位数由 8 工位变更为 12 工位，或行程从 600mm 增加到 800mm 时，工程师只需修改骨架零件中的全局变量，整机数十个子机构、标准件及自制件特征树自动全部重建更新，避免逐个零件修改的漏改与错位。

### 3. 锁定与断开外部参考（防止工程损坏）
- **开发阶段**：保持外部参考处于活动状态（状态符号 ->）；
- **生产归档阶段**：
  1. 在装配体特征树右键点击顶级装配体，选择【外部参考引用】；
  2. 点击【锁定全部（Lock All）】（显示符号 ->*）：此时模型几何参数冻结，不再因上层文件路径改变而意外重建变异，但保留未来解锁修改的接口；
  3. 最终生产出图移交给制造车间或客户前，若要求独立文档，可点击【断开全部（Break All）】（显示符号 ->x），切断关联并保留当前尺寸几何特征，彻底避免丢失外部参考时的模型变红报错。"""
    ),
    make_sft_item(
        "在包装机械或灌装流水线中，变节距输送螺杆（Variable Pitch Timing Screw / Augers）负责将等间距来料的药瓶平滑加速至不同间距。请说明在三维 CAD（SolidWorks 或 NX）中绘制变节距螺旋槽扫掠切除的数学建模过程与截面轮廓干涉避让设计。",
        """变节距输送螺杆是非标自动化高速连续包装线中的核心定制导向零件，其作用是将工件在旋转推进过程中实现平滑加速或减速分流。

### 1. 变节距螺旋线数学描述
传统固定节距螺杆节距为常数 P0。变节距螺杆的轴向位移 Z(θ) 是回转角 θ 的二次或高次多项式函数，实现平滑加速度约束：
Z(θ) = v0 * (θ / 2π) + 0.5 * a0 * (θ / 2π)^2
对应瞬时节距 P(θ) 从入料端初始节距 P_in 平稳加速至出料端 P_out。

### 2. SolidWorks 参数化建模三步法
1. **生成回转基体**：旋转拉伸出螺杆主体圆柱，外径由瓶子高度支承位置确定（通常外径 ⌀80~⌀120 mm，长度 600~1000 mm）；
2. **绘制空间变节距螺旋线（Helix/Spiral）**：
   - 插入【曲线】->【螺旋线/涡状线】，定义方式选择【高度和节距】；
   - 在参数栏选择【变节距】，在展开的数据表格中依次填入各关键段的高度 H 与节距 P 节点，设置过渡段为平滑样条曲线；
3. **扫掠切除（Swept Cut）轮廓与方向控制**：
   - 在螺杆端部建立与瓶子外形吻合的接触轮廓截面（需外放 0.5~1.0 mm 制造与运行间隙）；
   - 关键设置：在扫掠切除选项中，【方向/扭转控制】必须选择【保持法向不变】或选择圆柱表面作为【方向向量】，严格杜绝扫描过程中瓶槽倾斜失真；
   - 螺杆两端必须设置不小于 1.5 圈的恒定等节距导入段与导出段，确保来料顺畅进入与平稳送出。"""
    ),
    make_sft_item(
        "在 SolidWorks Composer 中为客户制作非标设备交互式数字培训手册时，如何实现视口协同（Collaborative Views）、零件爆炸图拆解时序控制，并一键发布为轻量化 HTML / 可交互 3D PDF？",
        """SolidWorks Composer 用于直接利用 CAD 工程数模制作生产装配工艺指导书（SOP）和交互式技术培训文档。

### 1. 视口协同与关键帧动画时序控制
- **协同视图（Views）架构**：在 Composer 中，每个视图保存模型在该时刻的相机位姿、爆炸位移、零部件隐藏/显示状态、剖切面以及批注标签（Callouts）。
- **线性爆炸拆解时序**：
  1. 使用【平移】或【分解管理器（Explode Studio）】，沿各轴向约束拉出零部件；
  2. 在时间轴（Timeline）中拖动关键帧（Keyframes），设置零件平移时长（如 1.5 秒），依次排列“外罩拆卸 -> 气管快插拔除 -> 核心电机法兰螺丝拆卸 -> 模组滑块整体抽出”的时序流水；
  3. 为每个拆解动作添加【关联轨迹线（Trajectory Lines）】，指引工人安装运动方向。

### 2. 交互式热点与零件清单（BOM Table）联动
- 在 Composer 中导入 CAD 装配体的元数据，生成矢量表格；
- 点击零件清单中的某项物料编号（Item No.），3D 场景中对应零件自动高亮泛光显示，反之在 3D 模型中点击零件，BOM 列表中自动滚动物料并弹出零件名称、订货号与装配扭矩规格。

### 3. 一键发布轻量化格式
- **交互式 HTML 格式**：选择【发布为 HTML】，导出包含 WebGL / Composer Player 嵌入式内核的单网页，车间平板电脑在浏览器中无需安装 CAD 软件即可 360° 旋转、测量距离、步进播放拆装动画；
- **高分辨率矢量图纸与 3D PDF**：使用【技术插图（Technical Illustration）】模块输出带轮廓阴影与轮廓加粗的 SVG / EPS 工业说明书插图，或直接发布为包含 3D 动态实体的 Adobe 交互式 PDF。"""
    )
]

# ==========================================
# 3. 扩充 标准件选型与电机匹配 (05_STANDARDS_AND_COMPONENTS_LIBRARY)
# ==========================================
standard_items = [
    make_sft_item(
        "在伺服驱动非标自动化滑台设计中，工作滑块总质量 m = 60 kg，水平安装滚珠丝杠（外径 d = 25 mm，导程 Ph = 20 mm，总长 L = 1200 mm，材料钢），工作台最大加速度 a = 10 m/s^2，伺服电机额定转速 3000 r/min。请计算折算到电机轴的负载转动惯量 J_L，根据工业伺服刚性匹配准则计算惯量比，并判定是否需要配置行星减速机？",
        """在伺服运动控制系统中，负载惯量与电机转子惯量的合理匹配是保证系统定位精度、响应频宽及伺服不发生高频振荡的前提。

### 1. 机构各部件转动惯量计算
#### (1) 滚珠丝杠自身转动惯量 J_S
丝杠材质为钢（密度 ρ = 7.85 * 10^-3 g/mm^3），其等效圆柱体转动惯量公式为：
J_S = (π * ρ * L * d^4) / 32
代入数据：d = 25 mm = 2.5 cm, L = 1200 mm = 120 cm：
J_S = (3.1416 * 7.85 * 10^-3 * 120 * 2.5^4) / 32 ≈ 3.61 kg·cm^2 = 3.61 * 10^-4 kg·m^2

#### (2) 滑台与工件直线运动质量折算到电机轴的转动惯量 J_M
直线运动质量 m = 60 kg，导程 P_h = 20 mm = 0.02 m：
J_M = m * (P_h / (2π))^2 = 60 * (0.02 / (2 * 3.1416))^2 ≈ 6.08 * 10^-4 kg·m^2

#### (3) 联轴器转动惯量估计
选用常用膜片联轴器，转动惯量约为 J_C ≈ 0.40 * 10^-4 kg·m^2。

#### (4) 折算到电机轴的总负载转动惯量 J_L
J_L = J_S + J_M + J_C = (3.61 + 6.08 + 0.40) * 10^-4 = 10.09 * 10^-4 kg·m^2 = 1.009 * 10^-3 kg·m^2

### 2. 惯量匹配校核与减速机配置决策
- **初选伺服电机规格**：选用 750W 中惯量伺服电机（如安川 SGM7J-08A），转子转动惯量 J_motor ≈ 1.5 * 10^-4 kg·m^2。
- **直连惯量比计算**：
  Ratio = J_L / J_motor = (10.09 * 10^-4) / (1.5 * 10^-4) ≈ 6.73 : 1
- **工程判定结论**：
  - 在一般非标设备中，推荐惯量比 <= 5:1，在高动态高速点位机构中推荐 <= 3:1；当前 6.73:1 处于偏高区间，极易在加减速拐点出现整定时间过长或伺服啸叫；
  - **优化方案**：配置一套速比 i = 3 的精密行星减速机（背隙 <= 3 arcmin）。加入减速机后，折算到电机轴的负载惯量降为 J_L' = J_L / (i^2) ≈ 1.12 * 10^-4 kg·m^2，此时惯量比降至 0.75:1，系统动态响应与定位刚性达到极致最佳状态。"""
    ),
    make_sft_item(
        "在同步带传动选型中（如 HTD 3M、HTD 5M 系列），如何根据传递功率、带速、中心距以及小带轮齿数确定同步带的基准带宽？当小带轮包角齿数 z_m < 6 时，应采取何种修正措施？",
        """同步带传动兼具齿轮传动的准确性与皮带传动的平稳性，是工业自动化水平搬送的主力元件。

### 1. 同步带基准带宽选型计算
1. **设计计算功率 P_c**：
   P_c = P * K_A
   其中 P 为驱动电机额定功率，K_A 为工况载荷修正系数（每天运行 16 小时、中等冲击的设备通常取 K_A = 1.4~1.6）。
2. **基准额定功率 P_0 与带宽系数 K_b**：
   查阅同步带选型手册（如 MISUMI 规范），在给定小带轮齿数 z_1 与小带轮转速 n_1 条件下，查得基准宽度（如 HTD 5M 宽 15mm）的基准传递功率 P_0。
3. **实际所需带宽比率计算**：
   P_c <= P_0 * K_z * K_b
   其中 K_z 为啮合齿数修正系数，K_b 为带宽修正系数。根据计算求得的 K_b，在标准宽度系列（如 9, 15, 25, 30 mm）中向上圆整选定带宽。

### 2. 小带轮啮合包角齿数 z_m < 6 的修正措施
- **啮合齿数计算公式**：
  z_m = (θ_1 / 360°) * z_1
- **当 z_m < 6 时的危害**：由于带齿承受剪切力的总接触齿数不足，载荷集中在 3~4 个齿上，极易产生带齿根部剪切断裂或爬齿跳齿。
- **应对措施**：
  1. **啮合齿数折减系数**：手册规定当 z_m = 5 时取 K_z = 0.8；z_m = 4 时取 K_z = 0.6，必须按此系数强制增大皮带带宽；
  2. **增大中心距或增大带轮直径**：加大小带轮齿数（HTD 5M 建议小轮齿数 z_1 >= 20）；
  3. **加装张紧轮**：在同步带松边内侧加装张紧轮，加大对小带轮的包角，确保 z_m >= 6。"""
    ),
    make_sft_item(
        "在工业机器视觉外观检测系统中，被检工件尺寸为 120 mm × 80 mm，工艺要求最小缺陷识别精度为 0.05 mm（每个可分辨特征至少覆盖 2 个像元）。工作安装空间限制镜头前端至工件的工作距离 WD = 300 mm。请计算工业相机的最小像素分辨率、推荐的 CMOS 靶面尺寸，并计算匹配的工业远心/定焦镜头焦距 f。",
        """机器视觉系统的硬件选型必须基于光学采样定理与光学放大倍率进行闭环计算。

### 1. 相机像素分辨率计算
- **视场范围（Field of View, FOV）**：考虑边缘预留 15% 冗余安全裕量，实际视场确定为：
  FOV_X = 120 * 1.15 = 138 mm,  FOV_Y = 80 * 1.15 = 92 mm
- **像元精度要求**：根据 Nyquist 采样定理，识别 0.05 mm 缺陷至少需 2 个像素点覆盖，因此系统单像素物理分辨率应达到：
  δ = 0.05 mm / 2 = 0.025 mm/pixel
- **相机所需理论像素数**：
  Pixel_X = FOV_X / δ = 138 / 0.025 = 5520 pixels
  Pixel_Y = FOV_Y / δ = 92 / 0.025 = 3680 pixels
  总像素数 ≈ 2031 万像素。选用 2000 万像素（20MP）面阵相机（1 英寸 CMOS 靶面，像元尺寸 2.4 μm × 2.4 μm，分辨率 5472 × 3648）。

### 2. 镜头光学焦距 f 计算
- **传感器靶面尺寸**：1 英寸靶面宽 V_X = 5472 * 0.0024 mm ≈ 13.13 mm；
- **光学放大倍率 β**：
  β = Sensor_X / FOV_X = 13.13 / 138 ≈ 0.0951
- **根据工作距离 WD 计算焦距 f**：
  f = (WD * β) / (1 + β) = (300 * 0.0951) / (1 + 0.0951) ≈ 26.05 mm
- **镜头选型结论**：
  在标准工业定焦镜头系列中，推荐选择 f = 25 mm 或 35 mm 低畸变工业百万像素定焦镜头。对于精密微小测量，若需消除透视形变，可配置双侧远心镜头。"""
    ),
    make_sft_item(
        "在气动管路系统设计中，如何根据气缸的工作气耗与快速动作响应时间，计算电磁换向阀所需的有效流通截面积 S（mm^2）与流量系数 C_v？若选型过小或过大分别会带来什么工程隐患？",
        """气动换向阀的通流能力匹配直接决定气缸的动作节拍、终点冲击与供气系统能耗。

### 1. 气动电磁阀有效流通截面积 S 计算
1. **气缸最大瞬间压缩空气消耗流量 Q_max**：
   Q_max = (π * D^2 / 4) * v_max * ((p_1 + 0.1013) / 0.1013) * 10^-3  [L/min (ANR)]
   其中 D 为气缸内径 (mm)，v_max 为活塞最大工作速度 (mm/s)，p_1 为供气表压 (MPa)。
2. **所需有效截面积 S 计算公式（ISO 6358 准则）**：
   在亚音速临界压降状态下（充气压降取 Δp = 0.05~0.1 MPa）：
   S = Q_max / (228 * sqrt(Δp * (p_2 + 0.1)))  [mm^2]
3. **S 与流量系数 C_v 的换算**：
   C_v = S / 18.0

### 2. 选型不匹配的工业隐患
- **电磁阀流通能力过小（S 偏小）**：气缸充放气产生严重节流憋压，活塞运动迟缓，无法达到预定生产节拍；中途易产生爬行顿挫。
- **电磁阀流通能力过大（S 偏大）**：瞬间进气充填过快，活塞以极大动能撞击端盖端面，产生强烈机械震动和噪音；体积和功耗成倍增加，浪费压缩空气。"""
    ),
    make_sft_item(
        "在精密点胶机吸嘴贴片头机构中，贴片压力要求严格稳定在 1.0 N ± 0.1 N。为什么普通减压阀无法满足微力控制要求？请说明精密电气比例阀（如 SMC ITV0010 系列）的工作原理与闭环压力控制策略。",
        """在半导体与 3C 精密贴片贴合工艺中，芯片裸片或光学透镜极其脆弱，微力（0.5~2.0 N）控制是防止压伤晶圆的核心要求。

### 1. 普通调压阀在微压工况下的失效原因
- **调压死区与溢流死区过大**：普通调压阀依靠机械弹簧压缩量驱动膜片平衡，调压灵敏度通常在 0.01~0.02 MPa（10~20 kPa）。对于 ⌀10mm 的微型气缸，10 kPa 波动直接产生 F = P * A ≈ 0.785 N 的推力误差，误差占比高达 78.5%；
- **回程迟滞性大**：活塞摩擦阻力导致机械调压阀存在不可忽略的回程滞后。

### 2. 精密电气比例阀（SMC ITV 系列）工作原理
电气比例阀通过电信号（0~10 V 或 4~20 mA）连续无级调节输出气压：
1. **双先导电磁阀调制**：内部包含一个超高速进气电磁阀和一个排气电磁阀；
2. **集成半导体压力传感器**：实时直接监测二次侧出口微气压；
3. **高速微处理器闭环回路**：
   - 当输入控制电压增大时，进气电磁阀快速通电开启，辅助气压充入主先导室，主排气口关闭，二次侧压力升高；
   - 内部压力传感器检测到当前压力并将反馈信号与目标指令比对，当达到目标压力时，进气与排气阀同时关闭锁定气压；
   - 响应时间达到毫秒级（<= 100 ms），输出压力线性度 <= ±1%，重复精度高达 <= ±0.5%，保证贴片头 1.0 N 微力下压时零超调、零机械冲击。"""
    )
]

# ==========================================
# 4. 扩充 机械设计手册强度与疲劳计算 (03_MECHANICAL_HANDBOOK_RAG_AND_QA)
# ==========================================
handbook_items = [
    make_sft_item(
        "某自动化主驱动传动轴，轴径 d = 45 mm，材料为 45号钢（调质处理，抗拉强度 σ_b = 650 MPa，屈服强度 σ_s = 360 MPa，弯曲疲劳极限 σ_-1 = 275 MPa，扭剪疲劳极限 τ_-1 = 155 MPa）。工作时轴承受稳定不变的转矩 T = 420 N·m，同时承受交变对称弯曲力矩 M = 550 N·m。请依据《机械设计手册 第六版 第3卷 第14篇 轴》：\n1. 计算轴截面处的弯曲正应力 σ 与扭转剪应力 τ；\n2. 采用第三强度理论（Tresca）或第四强度理论（von Mises）计算当量弯矩 M_e 与当量应力 σ_e；\n3. 校核该轴的疲劳强度安全系数 S，判定其是否满足安全储备要求（规定许用安全系数 [S] = 1.5~2.0）。",
        """依据《机械设计手册 第六版 第3卷 第14篇 轴的设计》：

### 1. 截面工作应力计算
轴径 d = 45 mm，轴的抗弯截面模量 W 与抗扭截面模量 W_t 为：
W = (π * d^3) / 32 ≈ 8946 mm^3
W_t = (π * d^3) / 16 = 2 * W ≈ 17892 mm^3

- **弯曲正应力 σ_b（对称循环交变应力）**：
  σ_b = M / W = (550 * 10^3 N·mm) / 8946 mm^3 ≈ 61.48 MPa
- **扭转剪应力 τ（静应力/脉动循环应力）**：
  τ = T / W_t = (420 * 10^3 N·mm) / 17892 mm^3 ≈ 23.47 MPa

### 2. 当量弯矩 M_e 与当量应力 σ_e 计算
根据手册规定，扭转应力性质按脉动循环考虑，折算系数 α ≈ 0.887：
- **当量弯矩 M_e**：
  M_e = sqrt(M^2 + (α * T)^2) = sqrt(550^2 + (0.887 * 420)^2) ≈ 664.3 N·m
- **当量应力 σ_e**：
  σ_e = M_e / W = (664.3 * 10^3) / 8946 ≈ 74.26 MPa

### 3. 疲劳强度安全系数校核
考虑轴肩过渡圆角处的有效应力集中系数 k_σ = 1.65、表面状态系数 β_σ = 0.88、尺寸系数 ε_σ = 0.82：
- 弯曲安全系数 S_σ ≈ 2.08
- 扭转安全系数 S_τ ≈ 9.20
- **截面综合疲劳安全系数 S**：
  S = (S_σ * S_τ) / sqrt(S_σ^2 + S_τ^2) ≈ 2.03

**判定结论**：S = 2.03 > [S] = 1.5~2.0，该轴在给定交变工况下满足疲劳寿命设计储备，轴肩圆角处不会产生疲劳裂纹萌生。"""
    ),
    make_sft_item(
        "在机械法兰螺栓连接中，采用 4 颗 8.8 级 M12 高强度螺栓（材料屈服强度 σ_s = 640 MPa，公称应力截面积 A_s = 84.3 mm^2）沿分度圆周均匀紧固。总工作轴向拉力 F_total = 24 kN。依据《机械设计手册 第六版 第2卷 第5篇 紧固件与螺栓连接》，请计算每颗螺栓的最佳预紧力 F_0、拧紧力矩 T_torque（取摩擦系数 μ = 0.15），并校核螺栓在预紧与工作复合载荷下的拉伸安全系数。",
        """依据《机械设计手册 第六版 第2卷 联接与紧固》高强度螺栓连接规范：

### 1. 螺栓工作载荷分配
每颗螺栓承受的外加工作轴向拉力 F 为：
F = F_total / 4 = 24 kN / 4 = 6.0 kN = 6000 N

### 2. 预紧力 F_0 与最大总拉力 F_b 计算
推荐安装预紧力取 F_0 = 1.5 * F = 9000 N。
取相对刚度系数 C_b / (C_b + C_m) ≈ 0.25：
F_b = F_0 + 0.25 * F = 9000 + 1500 = 10500 N = 10.5 kN

### 3. 拧紧力矩 T_torque 计算
螺栓规格 M12，力矩系数 k ≈ 0.20：
T_torque = k * F_0 * d = 0.20 * 9000 N * 0.012 m = 21.6 N·m

### 4. 螺栓拉伸应力与安全系数校核
考虑拧紧时螺纹升角摩擦剪应力，采用等效应力系数 1.3 倍校核：
σ_equiv = (1.3 * F_b) / A_s = (1.3 * 10500) / 84.3 ≈ 161.9 MPa
- **材料安全系数 S**：
  S = σ_s / σ_equiv = 640 / 161.9 ≈ 3.95
- **结论**：S = 3.95 >> [S] = 1.5~1.8，螺栓强度冗余充足，绝无塑性屈服与断裂风险，法兰紧固稳定。"""
    ),
    make_sft_item(
        "在自动化压装机构中，设计一个圆柱螺旋压缩弹簧。已知最大工作载荷 F_2 = 650 N，最小预载荷 F_1 = 200 N，工作行程 h = 25 mm。选用碳素弹簧钢丝 65Mn（许用切应力 [τ] = 450 MPa，切变模量 G = 79 GPa）。初选外径 D_2 = 40 mm，簧丝直径 d = 5 mm。请校核弹簧的刚度、有效圈数 n、曲度系数 K（Wahl系数），并校核弹簧切应力 τ_2 是否满足强度要求。",
        """依据《机械设计手册 第六版 第2卷 第7篇 弹簧》：

### 1. 弹簧几何参数与曲度系数 K
- 中径 D = D_2 - d = 35 mm，旋绕比 C = D / d = 7.0
- 曲度系数 K = ((4C - 1) / (4C - 4)) + (0.615 / C) ≈ 1.213

### 2. 弹簧刚度与有效圈数 n 计算
- 弹簧刚度 P' = (F_2 - F_1) / h = (650 - 200) / 25 = 18.0 N/mm
- 有效圈数 n = (G * d^4) / (8 * D^3 * P') ≈ 8.0 圈。取两端并紧磨平各 1 圈，总圈数 n_1 = 10.0 圈。

### 3. 最大工作载荷下切应力 τ_2 校核
τ_2 = K * (8 * F_2 * D) / (π * d^3) ≈ 682.6 MPa
强度评估：计算得到 τ_2 = 682.6 MPa > [τ] = 450 MPa，初选的 d = 5 mm 应力超标！

### 4. 优化设计整改
将簧丝直径增大至 d = 6.0 mm（外径 D_2 = 42 mm, D = 36 mm, C = 6.0，K ≈ 1.253）：
τ_2' = 1.253 * (8 * 650 * 36) / (π * 6^3) ≈ 423.8 MPa < [τ] = 450 MPa
重新计算有效圈数 n' ≈ 14.5 圈。此时弹簧切应力完全满足强度安全准则。"""
    ),
    make_sft_item(
        "在电机输出轴与联轴器配合中，轴径 d = 50 mm，传递额定扭矩 T = 600 N·m，选用 GB/T 1096 圆头普通平键（A型）。按标准选配平键尺寸：键宽 b = 14 mm，键高 h = 9 mm，键长 L = 60 mm。联轴器材质为 HT200（铸铁，许用挤压应力 [σ_p] = 50~60 MPa），载荷平稳轻微振动。请校核平键连接的挤压强度，若强度不足应如何改进？",
        """依据《机械设计手册 第六版 第2卷 第6篇 键与花键联接》：

### 1. 平键几何尺寸与接触参数
- 轴径 d = 50 mm，平键规格 14 * 9 * 60 mm（A型圆头平键）
- 键工作长度 l = L - b = 60 - 14 = 46 mm
- 轮毂槽接触高度 k = h - t = 9 - 5.5 = 3.5 mm

### 2. 挤压应力 σ_p 计算
圆周力 F_t = 2T / d = (2 * 600 * 10^3) / 50 = 24000 N
实际挤压应力 σ_p = F_t / (k * l) = 24000 / (3.5 * 46) ≈ 149.07 MPa

### 3. 强度校核结论与工程整改
- 轮毂材质为 HT200 铸铁，许用挤压应力 [σ_p] = 50~60 MPa。现 σ_p = 149.07 MPa >> 60 MPa，轮毂键槽将被压溃！
- **工程整改方案**：
  1. 采用双平键布置：沿轴圆周相隔 180° 对称布置两根相同的平键；
  2. 最佳工业方案：将平键连接改为机械胀紧套（免键涨套，如 Z2型涨紧联结套），依靠内外锥面过盈抱紧，完全消除应力集中与冲击间隙。"""
    )
]

# ==========================================
# 5. 扩充 CAD/CAM 工业代码生成 (02_SFT_CAD_CAM_CODE)
# ==========================================
cad_cam_items = [
    make_sft_item(
        "请编写一个生产级的 SolidWorks VBA 宏，能够递归遍历当前打开的整机装配体树，提取每个零部件的【图号（PartNo）】、【零件名称（Description）】、【材质（Material）】、【数量（Quantity）】与【质量（Mass in kg）】，过滤被压缩或轻化的零件，并将结果格式化输出为结构化 CSV 清单。",
        """下面是生产级 SolidWorks VBA 宏源码，支持自动遍历多层级子装配树并提取 BOM 物理属性：

```vb
' =========================================================================
' SolidWorks Macro: 递归遍历装配体树并导出结构化 BOM 物理属性清单
' 支持过滤轻化/压缩件，自动提取图号、图名、材质及称重质量
' =========================================================================
Option Explicit

Dim swApp As SldWorks.SldWorks
Dim swModel As SldWorks.ModelDoc2
Dim swAssy As SldWorks.AssemblyDoc
Dim dictParts As Object
Dim dictInfo As Object

Sub main()
    Set swApp = Application.SldWorks
    Set swModel = swApp.ActiveDoc
    
    If swModel Is Nothing Then
        MsgBox "请先打开一个 SolidWorks 装配体文件！", vbCritical, "Virtu CAM"
        Exit Sub
    End If
    
    If swModel.GetType <> swDocASSEMBLY Then
        MsgBox "当前活动文档不是装配体，请在 .SLDASM 环境中运行！", vbExclamation, "Virtu CAM"
        Exit Sub
    End If
    
    Set swAssy = swModel
    Set dictParts = CreateObject("Scripting.Dictionary")
    Set dictInfo = CreateObject("Scripting.Dictionary")
    
    Dim swRootComp As SldWorks.Component2
    Dim swConf As SldWorks.Configuration
    Set swConf = swAssy.GetActiveConfiguration
    Set swRootComp = swConf.GetRootComponent3(True)
    
    TraverseComponent swRootComp, 1
    
    Dim outPath As String
    outPath = Left(swModel.GetPathName, InStrRev(swModel.GetPathName, ".")) & "csv"
    If outPath = "csv" Then outPath = "C:\\Temp\\Virtu_Assembly_BOM.csv"
    
    Dim fso As Object, fOut As Object
    Set fso = CreateObject("Scripting.FileSystemObject")
    Set fOut = fso.CreateTextFile(outPath, True, True)
    
    fOut.WriteLine "物料图号,零件名称,材料材质,装配数量,单件质量(kg),总质量(kg)"
    
    Dim key As Variant
    For Each key In dictParts.Keys
        Dim count As Long
        count = dictParts(key)
        Dim info As String
        info = dictInfo(key)
        
        Dim fields() As String
        fields = Split(info, "|")
        Dim mass As Double
        mass = CDbl(fields(2))
        Dim totalMass As Double
        totalMass = Round(mass * count, 3)
        
        fOut.WriteLine fields(0) & "," & fields(1) & "," & fields(3) & "," & count & "," & mass & "," & totalMass
    Next key
    
    fOut.Close
    MsgBox "装配体 BOM 属性清单已成功导出至：" & vbCrLf & outPath, vbInformation, "Virtu 工业智能体"
End Sub

Sub TraverseComponent(swComp As SldWorks.Component2, depth As Long)
    Dim vChildren As Variant
    vChildren = swComp.GetChildren
    If IsEmpty(vChildren) Then Exit Sub
    
    Dim i As Long
    For i = 0 To UBound(vChildren)
        Dim swChild As SldWorks.Component2
        Set swChild = vChildren(i)
        
        If swChild.GetSuppression <> swComponentSuppressed Then
            Dim childModel As SldWorks.ModelDoc2
            Set childModel = swChild.GetModelDoc2
            
            If Not childModel Is Nothing Then
                If childModel.GetType = swDocPART Then
                    Dim custPropMgr As SldWorks.CustomPropertyManager
                    Set custPropMgr = childModel.Extension.CustomPropertyManager("")
                    Dim valOut As String, resolvedVal As String
                    
                    custPropMgr.Get4 "图号", False, valOut, resolvedVal
                    Dim partNo As String
                    partNo = IIf(resolvedVal <> "", resolvedVal, swChild.Name2)
                    
                    custPropMgr.Get4 "名称", False, valOut, resolvedVal
                    Dim partDesc As String
                    partDesc = IIf(resolvedVal <> "", resolvedVal, childModel.GetTitle)
                    
                    Dim mat As String
                    mat = childModel.MaterialIdName
                    If mat = "" Then mat = "未指定材质"
                    
                    Dim swMassProp As SldWorks.MassProperty
                    Set swMassProp = childModel.Extension.CreateMassProperty
                    Dim unitMass As Double
                    If Not swMassProp Is Nothing Then
                        unitMass = Round(swMassProp.Mass, 3)
                    Else
                        unitMass = 0
                    End If
                    
                    If dictParts.Exists(partNo) Then
                        dictParts(partNo) = dictParts(partNo) + 1
                    Else
                        dictParts.Add partNo, 1
                        dictInfo.Add partNo, partNo & "|" & partDesc & "|" & unitMass & "|" & mat
                    End If
                ElseIf childModel.GetType = swDocASSEMBLY Then
                    TraverseComponent swChild, depth + 1
                End If
            End If
        End If
    Next i
End Sub
```"""
    ),
    make_sft_item(
        "请编写一段基于 Siemens NX Open Python API 的脚本，能够自动批量遍历指定目录下的所有 .prt 图纸文件，打开并提取图纸标题栏中的【PART_NO】、【REVISION】与【TITLE】属性，一键导出高清 PDF 并自动重命名为规范的「图号_版本_图名.pdf」。",
        """下面是基于 Siemens NX Open Python API 开发的生产级批量图纸导出与属性自动重命名脚本：

```python
# -*- coding: utf-8 -*-
# NX Open Python Script: 批量工程图转 PDF 并按标题栏属性规范重命名
# 执行环境: Siemens NX 12.0 / NX 1980+ (run_journal.exe 运行)
import os
import NXOpen
import NXOpen.UF

def export_drawings_to_pdf(input_dir, output_dir):
    the_session = NXOpen.Session.GetSession()
    the_uf_session = NXOpen.UF.UFSession.GetUFSession()
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    prt_files = [f for f in os.listdir(input_dir) if f.lower().endswith(".prt")]
    print(f"[*] 找到 {len(prt_files)} 个 NX PRT 图纸文件，准备开始批量批处理...")
    
    for file_name in prt_files:
        part_path = os.path.join(input_dir, file_name)
        try:
            base_part, open_status = the_session.Parts.OpenBase(part_path)
            part = base_part
            
            part_no = "UNKNOWN_NO"
            part_rev = "A"
            part_title = "UNTITLED"
            
            try: part_no = part.GetStringAttribute("PART_NO")
            except:
                try: part_no = part.GetStringAttribute("DB_PART_NO")
                except: part_no = os.path.splitext(file_name)[0]
                
            try: part_rev = part.GetStringAttribute("REVISION")
            except:
                try: part_rev = part.GetStringAttribute("DB_PART_REV")
                except: part_rev = "0"
                
            try: part_title = part.GetStringAttribute("TITLE")
            except:
                try: part_title = part.GetStringAttribute("DB_PART_NAME")
                except: part_title = part.Leaf
                
            safe_title = "".join(c for c in part_title if c not in r'\\/:*?"<>|').strip()
            pdf_filename = f"{part_no}_Rev{part_rev}_{safe_title}.pdf"
            pdf_path = os.path.join(output_dir, pdf_filename)
            
            sheets = part.DrawingSheets.ToArray()
            if len(sheets) == 0:
                part.Close(NXOpen.BasePart.CloseWholeTree.TrueValue, None)
                continue
                
            pdf_builder = the_session.PrintManager.CreatePdfBuilder()
            pdf_builder.Action = NXOpen.PrintManager.Action.Export
            pdf_builder.OutputText = NXOpen.PrintManager.OutputTextOption.Polylines
            pdf_builder.Colors = NXOpen.PrintManager.Color.BlackAndWhite
            pdf_builder.StandardWidth = NXOpen.PrintManager.StandardWidth.Thin
            pdf_builder.Scale = 1.0
            pdf_builder.OutputFile = pdf_path
            
            the_uf_session.Plot.AskDefaultParameters()
            pdf_builder.Commit()
            pdf_builder.Destroy()
            print(f"[+] 导出成功: {pdf_filename}")
            
            part.Close(NXOpen.BasePart.CloseWholeTree.TrueValue, None)
        except Exception as e:
            print(f"[-] 处理 {file_name} 失败: {str(e)}")

if __name__ == "__main__":
    SRC = r"D:\\Project_Drawings"
    DST = r"D:\\Project_Drawings\\Export_PDF"
    export_drawings_to_pdf(SRC, DST)
```"""
    ),
    make_sft_item(
        "请编写一段用于 AutoCAD 2026 的 AutoLISP (.lsp) 脚本，要求能够自动扫描当前 DWG 图纸中的所有属性块图框（Title Block），提取图框属性中的「图号」、「图名」、「材料」与「制图比例」，在命令行整齐打印，并在当前图纸指定坐标处自动生成一张 AutoCAD 生产图纸目录表格（AcDbTable）。",
        """下面是用于 AutoCAD 的生产级 AutoLISP 属性提取与目录生成脚本源码：

```lisp
;;; =========================================================================
;;; AutoLISP: 自动提取标题栏属性块并在 DWG 中生成图纸目录表格
;;; 支持 AutoCAD 2020 ~ 2026 简体中文版
;;; =========================================================================
(vl-load-com)

(defun c:VirtuGenDrawingIndex ( / doc ms ss i ent blkObj attList pNo pName pMat pScale pt tbl row)
  (setq doc (vla-get-ActiveDocument (vlax-get-acad-object)))
  (setq ms (vla-get-ModelSpace doc))
  
  (princ "\n[Virtu CAD] 正在搜索图纸中的标题栏属性块...")
  (setq ss (ssget "X" '((0 . "INSERT") (66 . 1))))
  
  (if (not ss)
    (alert "未在当前图纸中检测到包含属性块的标题栏！")
    (progn
      (setq titleDataList '())
      (setq i 0)
      
      (while (< i (sslength ss))
        (setq ent (ssname ss i))
        (setq blkObj (vlax-ename->vla-object ent))
        (setq attList (vlax-invoke blkObj 'GetAttributes))
        (setq pNo "" pName "" pMat "" pScale "")
        
        (foreach att attList
          (setq tag (strcase (vla-get-TagString att)))
          (setq val (vla-get-TextString att))
          (cond
            ((or (= tag "图号") (= tag "DWG_NO") (= tag "PART_NO")) (setq pNo val))
            ((or (= tag "图名") (= tag "DWG_NAME") (= tag "TITLE")) (setq pName val))
            ((or (= tag "材料") (= tag "MATERIAL")) (setq pMat val))
            ((or (= tag "比例") (= tag "SCALE")) (setq pScale val))
          )
        )
        (if (/= pNo "")
          (setq titleDataList (cons (list pNo pName pMat pScale) titleDataList))
        )
        (setq i (1+ i))
      )
      
      (princ (strcat "\n[+] 成功解析到 " (itoa (length titleDataList)) " 个图框标题栏。"))
      (setq pt (getpoint "\n请在图纸空白处点击放置图纸目录表格位置: "))
      (if (and pt titleDataList)
        (progn
          (setq pt (vlax-3d-point pt))
          (setq tbl (vla-AddTable ms pt (+ (length titleDataList) 2) 5 8.0 45.0))
          (vla-SetText tbl 0 0 "机械工程图纸加工目录表")
          
          (vla-SetText tbl 1 0 "序号")
          (vla-SetText tbl 1 1 "图样代号 (图号)")
          (vla-SetText tbl 1 2 "图样名称 (零件名)")
          (vla-SetText tbl 1 3 "材料规格")
          (vla-SetText tbl 1 4 "比例")
          
          (setq row 2)
          (setq idx 1)
          (foreach item titleDataList
            (vla-SetText tbl row 0 (itoa idx))
            (vla-SetText tbl row 1 (nth 0 item))
            (vla-SetText tbl row 2 (nth 1 item))
            (vla-SetText tbl row 3 (nth 2 item))
            (vla-SetText tbl row 4 (nth 3 item))
            (setq row (1+ row))
            (setq idx (1+ idx))
          )
          (vla-Update tbl)
          (princ "\n[OK] 图纸目录表格已成功生成！")
        )
      )
    )
  )
  (princ)
)
(princ "\n[Virtu CAD] 脚本加载成功！输入 VirtuGenDrawingIndex 命令即可执行。")
```"""
    ),
    make_sft_item(
        "请编写一段用于 FANUC 0i-TF 数控车床的 Macro B 用户宏程序，实现对非圆曲线——椭圆轮廓（半长轴 A = 40 mm，半短轴 B = 25 mm）的外圆半精车与精车加工。要求使用 #100~#125 变量实现参数化步距控制，支持指定精车余量与刀尖圆弧半径补偿（G42）。",
        """下面是基于 FANUC 0i-TF 系统编写的非圆二次曲线（椭圆）精车加工 Macro B 宏程序：

```gcode
%
O2026 (FANUC 0i-TF ELLIPSE MACRO TURNING)
(EQUATION: Z^2/A^2 + X^2/B^2 = 1 -> X = 2 * B * SQRT[1 - Z^2/A^2])

#100 = 40.0   (半长轴 A，Z向范围 0 到 -40.0)
#101 = 25.0   (半短轴 B，X向单边半径值)
#102 = 0.2    (Z 向插补步距 dZ，单位 mm)
#103 = 0.5    (外圆粗车精加工单边预留余量)
#104 = 800    (主轴切削转速 r/min)
#105 = 0.08   (精车进给速度 F, mm/rev)

G21 G40 G97 G99
T0101         (选用 35度外圆精车刀，刀尖 R0.4)
M03 S#104     (主轴正转)
M08           (开启切削液)

G00 X[2 * [#101 + #103] + 10.0] Z5.0
Z0.0
G00 X0.0

G01 G42 X0.0 Z0.0 F#105
#110 = 0.0    (当前自变量 Z 坐标深度，起始为 0)

WHILE [#110 GE [-#100]] DO 1
    #112 = 1.0 - [#110 * #110] / [#100 * #100]
    IF [#112 LT 0.0] THEN #112 = 0.0
    
    #111 = #101 * SQRT[#112]
    #113 = 2.0 * #111   (转换为机床 X 直径坐标)
    G01 X#113 Z#110 F#105
    #110 = #110 - #102
END 1

G01 W-2.0 F#105
G01 X[2 * #101 + 6.0] F0.2
G40 G00 X120.0 Z100.0 M09
M05
M30
%
```"""
    ),
    make_sft_item(
        "在五轴联动加工中心数控后置处理中，刀具中心点控制（TCPM / RTCP，在西门子系统中对应 TRAORI，在发那科对应 G43.4）至关重要。请说明五轴编程为什么必须启用刀尖跟随功能？并在 Siemens NX 后置处理 TCL 脚本中编写逻辑，实现在程序头自动判断刀轴模式并输出 TRAORI 与动态工作平面指令（CYCLE800）。",
        """五轴联动数控加工中，**刀具中心点控制（TCPM / RTCP / TRAORI）**是保证五轴工件表面质量与多轴刀具轨迹精度的最核心数控技术。

### 1. 为什么五轴加工必须启用 TCPM / TRAORI？
- **消除机床运动学几何偏置误差**：在五轴机床中，旋转轴转动会产生刀具摆动杠杆误差。启用西门子 `TRAORI` 后，CAM 输出的是工件坐标系下的刀尖坐标与矢量，数控系统实时自动补偿回转偏置；
- **自适应矢量插补**：进给速度 F 恒定在刀具切削触点而非机床回转中心，避免刀尖过切与欠切。

### 2. NX Post Builder (TCL) 自动输出 TRAORI 逻辑
在 NX 后置处理器的 `PB_CMD_before_motion` 中添加以下 TCL 控制逻辑：

```tcl
# =========================================================================
# NX Post Custom TCL: 智能检测五轴联动与定轴加工并输出 TRAORI / CYCLE800
# =========================================================================

proc PB_CMD_virtu_5axis_controller {} {
    global mom_tool_axis_type
    
    if {[info exists mom_tool_axis_type]} {
        if {$mom_tool_axis_type == "Variable" || $mom_tool_axis_type == "Interpolated"} {
            MOM_output_literal "; >>>>> 启用五轴联动实时刀尖控制 (TRAORI) <<<<<"
            MOM_output_literal "TRAORI(1)"
            MOM_output_literal "G54 G90 G64"
            MOM_output_literal "ORIWKS"
            MOM_output_literal "ORIVECT"
        } else {
            MOM_output_literal "; >>>>> 启用 3+2 定轴定向加工动态坐标系 (CYCLE800) <<<<<"
            MOM_output_literal "CYCLE800(1,\"TABLE\",200000,57,0,0,0,0,0,0,0,0,0,1)"
        }
    }
}

proc PB_CMD_virtu_end_of_5axis {} {
    global mom_tool_axis_type
    if {[info exists mom_tool_axis_type]} {
        if {$mom_tool_axis_type == "Variable"} {
            MOM_output_literal "TRAFOOF"
            MOM_output_literal "CYCLE800()"
            MOM_output_literal "; >>>>> TRAORI 已安全关闭 <<<<<"
        }
    }
}
```"""
    )
]

# ==========================================
# 6. 扩充 具备多轮迭代与异常恢复的 Agent 轨迹 (01_SFT_AGENT_TOOLCALLS)
# ==========================================
agent_robust_sample_a = {
    "messages": [
        {"role": "system", "content": SYS_PROMPT},
        {"role": "user", "content": "帮我设计一套【精密伺服滚珠丝杠十字滑台机构】（所属领域：通用3C非标自动化设备 (General 3C Industrial Automation)），要求完成从工况推断、BOM结构分解、标准件选型、自制底座参数化建模、装配配合与空间干涉检测。如果发生空间干涉，必须自主诊断干涉部位并迭代回滚修改特征树尺寸，确保 0 干涉后再输出工程图和宏清单。"},
        {"role": "assistant", "content": "收到精密伺服滚珠丝杠十字滑台的设计需求。我正在分析其高精点位传动工况，推断行程、负载与定位精度预算：",
         "tool_calls": [{"id": "call_intent_stage_01", "type": "function", "function": {"name": "cad.infer_equipment_intent", "arguments": json.dumps({"equipment_name": "精密伺服滚珠丝杠十字滑台机构", "domain": "通用3C非标自动化设备 (General 3C Industrial Automation)", "target_payload_kg": 25.0, "travel_stroke_mm": 350.0, "repeatability_mm": 0.005}, ensure_ascii=False)}}]},
        {"role": "tool", "tool_call_id": "call_intent_stage_01", "content": json.dumps({"status": "success", "equipment_id": "EQ_STAGE_77A", "kinematic_plan": {"cycle_budget_sec": 1.5, "target_repeatability_mm": 0.005, "base_structure": "双轴正交高刚性铸铁十字座"}}, ensure_ascii=False)},
        {"role": "assistant", "content": "工况推断完毕。现在执行自顶向下装配体结构树分解，规划底座、X轴滑台、Y轴滑台、伺服电机及丝杠轴承座等构件：",
         "tool_calls": [{"id": "call_decomp_stage_01", "type": "function", "function": {"name": "cad.decompose_automation_assembly", "arguments": json.dumps({"equipment_id": "EQ_STAGE_77A", "assembly_name": "Cross_Slide_Table.SLDASM", "submodules": ["X_Axis_Drive_Unit", "Y_Axis_Cross_Base", "Servo_Motor_Mount"]}, ensure_ascii=False)}}]},
        {"role": "tool", "tool_call_id": "call_decomp_stage_01", "content": json.dumps({"status": "success", "assembly_name": "Cross_Slide_Table.SLDASM", "total_submodules": 3, "custom_parts_registered": 4, "cots_components_needed": 6}, ensure_ascii=False)},
        {"role": "assistant", "content": "结构树规划完成。从标准件库中检索调取 COTS 标准件：研磨级滚珠丝杠、固定端支承座与伺服电机法兰：",
         "tool_calls": [{"id": "call_std_stage_01", "type": "function", "function": {"name": "cad.query_standard_parts_library", "arguments": json.dumps({"query_categories": ["滚珠丝杠", "丝杠支承座", "伺服电机"]}, ensure_ascii=False)}}]},
        {"role": "tool", "tool_call_id": "call_std_stage_01", "content": json.dumps({"status": "success", "ball_screw": "MISUMI/BSGW15-10-450", "fixed_support_unit": "A研发设计库/丝杆固定侧 LEB01-15", "motor": "Panasonic_400W_Servo_MHMF042"}, ensure_ascii=False)},
        {"role": "assistant", "content": "标准件调取完毕。现在对核心基准自制件【Cross_Base.SLDPRT】进行初次参数化特征树建模：",
         "tool_calls": [{"id": "call_model_stage_01", "type": "function", "function": {"name": "cad.model_parametric_feature_tree", "arguments": json.dumps({"part_name": "Cross_Base.SLDPRT", "material": "HT300", "features": [{"type": "Base_Extrude", "dims": [500, 400, 45]}, {"type": "Guide_Mounting_Slot", "depth": 6.0, "width": 20.0}, {"type": "Screw_Pocket_Cut", "pocket_depth": 18.0, "pocket_width": 42.0}]}, ensure_ascii=False)}}]},
        {"role": "tool", "tool_call_id": "call_model_stage_01", "content": json.dumps({"status": "success", "part_file": "Cross_Base.SLDPRT", "rebuild_errors": 0, "feature_count": 3}, ensure_ascii=False)},
        {"role": "assistant", "content": "基座建模完成。现在将丝杠、支承座与底座进行装配配合约束，并执行三维空间干涉碰撞检测：",
         "tool_calls": [{"id": "call_asm_stage_01", "type": "function", "function": {"name": "cad.assemble_components_with_mates", "arguments": json.dumps({"assembly_name": "Cross_Slide_Table.SLDASM", "components_to_mate": ["Cross_Base.SLDPRT", "LEB01-15.SLDPRT", "BSGW15.SLDPRT"]}, ensure_ascii=False)}}]},
        {"role": "tool", "tool_call_id": "call_asm_stage_01", "content": json.dumps({"status": "warning", "assembly_name": "Cross_Slide_Table.SLDASM", "collision_check": {"interference_count": 1, "interference_volume_mm3": 142.6, "collided_parts": ["Cross_Base.SLDPRT", "LEB01-15.SLDPRT"], "description": "支承座固定沉头螺栓头部与底座安装避让台阶产生空间干涉 2.2 mm"}}, ensure_ascii=False)},
        {"role": "assistant", "content": "检测到 1 处空间干涉！干涉原因为支承座固定沉头螺栓头部与底座安装避让台阶产生 2.2 mm 干涉。我正在启动自适应异常恢复机制：回溯重新调用参数化特征树工具，将【Cross_Base.SLDPRT】中的避让沉槽深度由 18.0mm 加深至 24.0mm，避让槽宽由 42.0mm 拓展至 50.0mm，预留 3.8mm 安全装配间隙：",
         "tool_calls": [{"id": "call_model_stage_retry", "type": "function", "function": {"name": "cad.model_parametric_feature_tree", "arguments": json.dumps({"part_name": "Cross_Base.SLDPRT", "action": "modify_feature", "feature_target": "Screw_Pocket_Cut", "modified_dims": {"pocket_depth": 24.0, "pocket_width": 50.0}}, ensure_ascii=False)}}]},
        {"role": "tool", "tool_call_id": "call_model_stage_retry", "content": json.dumps({"status": "success", "part_file": "Cross_Base.SLDPRT", "rebuild_errors": 0, "feature_modified": "Screw_Pocket_Cut", "clearance_verified": True}, ensure_ascii=False)},
        {"role": "assistant", "content": "特征树避让修改完成。现在重新执行装配配合，并二次触发空间干涉检查以确保隐患彻底排除：",
         "tool_calls": [{"id": "call_asm_stage_recheck", "type": "function", "function": {"name": "cad.assemble_components_with_mates", "arguments": json.dumps({"assembly_name": "Cross_Slide_Table.SLDASM", "recheck_interference": True}, ensure_ascii=False)}}]},
        {"role": "tool", "tool_call_id": "call_asm_stage_recheck", "content": json.dumps({"status": "success", "assembly_name": "Cross_Slide_Table.SLDASM", "collision_check": {"interference_count": 0, "interference_volume_mm3": 0.0, "status": "CLEAN"}}, ensure_ascii=False)},
        {"role": "assistant", "content": "二次干涉检查完全通过（0 干涉）。现在生成修改后的【Cross_Base.SLDPRT】加工工程图，标定导轨安装台面平面度 0.008mm 与配合公差：",
         "tool_calls": [{"id": "call_draw_stage_01", "type": "function", "function": {"name": "cad.generate_engineering_drawing_annotation", "arguments": json.dumps({"part_file": "Cross_Base.SLDPRT", "gdt_tolerances": ["平面度 0.008 A", "垂直度 0.01 B"]}, ensure_ascii=False)}}]},
        {"role": "tool", "tool_call_id": "call_draw_stage_01", "content": json.dumps({"status": "success", "drawing_file": "Cross_Base.SLDDRW", "views_generated": 4, "dimension_callouts": 38, "gdt_frames": 2}, ensure_ascii=False)},
        {"role": "assistant", "content": "工程图输出完成。最后调用 SolidWorks 自动化宏执行 DWG/PDF 生产输出与整机总重统计：",
         "tool_calls": [{"id": "call_macro_stage_01", "type": "function", "function": {"name": "cad.execute_solidworks_macro", "arguments": json.dumps({"assembly_name": "Cross_Slide_Table.SLDASM", "actions": ["export_dwg", "export_pdf", "calculate_bom_weight"]}, ensure_ascii=False)}}]},
        {"role": "tool", "tool_call_id": "call_macro_stage_01", "content": json.dumps({"status": "success", "dwg_files": ["Cross_Base.dwg"], "total_assembly_mass_kg": 42.8}, ensure_ascii=False)},
        {"role": "assistant", "content": "### 【精密伺服滚珠丝杠十字滑台机构】设计与鲁棒迭代闭环完成！\n\n#### 1. 工程工况与结构分解\n- **设备定位**：通用3C高精度双轴正交十字滑台，额定负载 25kg，行程 350mm，重复定位精度 ±0.005mm；\n- **标准件选型**：MISUMI BSGW15-10 研磨级丝杠 + LEB01-15 预紧支承座 + 松下 400W 伺服电机。\n\n#### 2. 自适应异常检测与特征回溯迭代\n- **干涉诊断**：在初次装配中，干涉检测模块捕获到 1 处 142.6 mm³ 空间碰撞（支承座螺栓头与底座干涉 2.2mm）；\n- **闭环修复**：自动回滚并修改特征树 `Screw_Pocket_Cut`，将避让槽深度拓深至 24.0mm，二次装配干涉数归零（0 干涉）。\n\n#### 3. 制造工程输出\n- **工程图**：生成 `Cross_Base.SLDDRW`，标定导轨贴合面平面度 0.008mm；\n- **生产数据**：批量生成国标图层 DWG/PDF，整机核算总质量 42.8 kg。"}
    ]
}

agent_robust_sample_b = {
    "messages": [
        {"role": "system", "content": SYS_PROMPT},
        {"role": "user", "content": "设计一套【高速轻载芯片吸附移载机械手】（所属领域：通用3C非标自动化设备 (General 3C Industrial Automation)）。如果在调取标准件库时首选规格缺失，请自主按力学储备重新检索合适规格，并自适应调整端部法兰接口尺寸。"},
        {"role": "assistant", "content": "收到高速芯片吸附移载机械手的设计需求。首先推断其高速轻载运动节拍（CT < 0.8s）与动力学负荷：",
         "tool_calls": [{"id": "call_intent_pick_01", "type": "function", "function": {"name": "cad.infer_equipment_intent", "arguments": json.dumps({"equipment_name": "高速轻载芯片吸附移载机械手", "domain": "通用3C非标自动化设备 (General 3C Industrial Automation)", "target_payload_kg": 0.5, "cycle_time_sec": 0.8}, ensure_ascii=False)}}]},
        {"role": "tool", "tool_call_id": "call_intent_pick_01", "content": json.dumps({"status": "success", "equipment_id": "EQ_PICKER_09", "specs": {"vertical_stroke_mm": 60, "pick_force_N": 4.5}}, ensure_ascii=False)},
        {"role": "assistant", "content": "工况推断完成。执行自顶向下装配体结构规划：",
         "tool_calls": [{"id": "call_decomp_pick_01", "type": "function", "function": {"name": "cad.decompose_automation_assembly", "arguments": json.dumps({"equipment_id": "EQ_PICKER_09", "assembly_name": "Chip_Picker_Head.SLDASM"}, ensure_ascii=False)}}]},
        {"role": "tool", "tool_call_id": "call_decomp_pick_01", "content": json.dumps({"status": "success", "assembly_name": "Chip_Picker_Head.SLDASM", "components": ["Flange_Plate.SLDPRT", "Nozzle_Stem.SLDPRT"]}, ensure_ascii=False)},
        {"role": "assistant", "content": "向标准件库查询超轻量碳纤维无杆气缸：",
         "tool_calls": [{"id": "call_std_pick_01", "type": "function", "function": {"name": "cad.query_standard_parts_library", "arguments": json.dumps({"query_part": "Carbon_Fiber_Mini_Cylinder_D12"}, ensure_ascii=False)}}]},
        {"role": "tool", "tool_call_id": "call_std_pick_01", "content": json.dumps({"status": "not_found", "message": "标准库中未检索到碳纤维无杆气缸，推荐库存标准工业替代件：SMC MGPM12-60Z 紧凑型带导杆薄型双轴气缸"}, ensure_ascii=False)},
        {"role": "assistant", "content": "检测到首选定制件无库存。已获取推荐标准替代件【SMC MGPM12-60Z】（双导杆抗扭刚度强，额定推力 56 N 远超 4.5 N 需求，安全系数 K = 12.4）。现在根据 MGPM12-60Z 的安装孔距（PCD 30mm，4×M4 螺纹）对自制安装法兰【Flange_Plate.SLDPRT】进行自适应参数化特征树建模：",
         "tool_calls": [{"id": "call_model_pick_01", "type": "function", "function": {"name": "cad.model_parametric_feature_tree", "arguments": json.dumps({"part_name": "Flange_Plate.SLDPRT", "mounting_holes": {"type": "M4_Counterbore", "pcd": 30.0, "count": 4}}, ensure_ascii=False)}}]},
        {"role": "tool", "tool_call_id": "call_model_pick_01", "content": json.dumps({"status": "success", "part_file": "Flange_Plate.SLDPRT", "features_built": 4}, ensure_ascii=False)},
        {"role": "assistant", "content": "自适应法兰建模完成。执行装配体约束配合与干涉校验：",
         "tool_calls": [{"id": "call_asm_pick_01", "type": "function", "function": {"name": "cad.assemble_components_with_mates", "arguments": json.dumps({"assembly_name": "Chip_Picker_Head.SLDASM", "mates": ["Flange_Plate TO SMC_MGPM12-60Z"]}, ensure_ascii=False)}}]},
        {"role": "tool", "tool_call_id": "call_asm_pick_01", "content": json.dumps({"status": "success", "collision_check": {"interference_count": 0}}, ensure_ascii=False)},
        {"role": "assistant", "content": "配合校验通过，0干涉。生成吸附机构工程图标注并批处理输出宏：",
         "tool_calls": [{"id": "call_macro_pick_01", "type": "function", "function": {"name": "cad.execute_solidworks_macro", "arguments": json.dumps({"assembly_name": "Chip_Picker_Head.SLDASM", "actions": ["export_dwg", "export_pdf"]}, ensure_ascii=False)}}]},
        {"role": "tool", "tool_call_id": "call_macro_pick_01", "content": json.dumps({"status": "success", "dwg_files": ["Flange_Plate.dwg", "Chip_Picker_Head.dwg"]}, ensure_ascii=False)},
        {"role": "assistant", "content": "### 【高速轻载芯片吸附移载机械手】自适应选型与设计闭环完成！\n\n1. **标准件自适应替代**：碳纤维无杆气缸缺货时，智能体动态校核力学储备，选用高可靠现货标准件 SMC MGPM12-60Z 双轴气缸；\n2. **接口参数联动更新**：自制法兰安装孔距由原设计自动变更为 PCD 30mm 4×M4 沉孔，装配检测 0 干涉；\n3. **工程输出**：自动输出全套制造级 DWG 与 PDF 文件。"}
    ]
}

agent_robust_sample_c = {
    "messages": [
        {"role": "system", "content": SYS_PROMPT},
        {"role": "user", "content": "请对【精密主轴箱前支承套】进行工程图标注与尺寸公差设计。注意如果存在封闭尺寸链超差冲突，必须重构工艺基准并输出标准化制造工程图。"},
        {"role": "assistant", "content": "收到主轴箱前支承套工程设计任务。首先推断主轴支承套的配合公差等级与工艺定位基准：",
         "tool_calls": [{"id": "call_intent_spindle_01", "type": "function", "function": {"name": "cad.infer_equipment_intent", "arguments": json.dumps({"part_name": "Spindle_Bearing_Sleeve.SLDPRT", "precision_level": "P4/P2 High Precision"}, ensure_ascii=False)}}]},
        {"role": "tool", "tool_call_id": "call_intent_spindle_01", "content": json.dumps({"status": "success", "recommended_bearing": "7014C/P4 Angular Contact Bearings", "inner_fit": "⌀110 js6", "outer_fit": "⌀150 H6"}, ensure_ascii=False)},
        {"role": "assistant", "content": "公差基准推断完成。构建支承套参数化特征树：",
         "tool_calls": [{"id": "call_model_spindle_01", "type": "function", "function": {"name": "cad.model_parametric_feature_tree", "arguments": json.dumps({"part_name": "Spindle_Bearing_Sleeve.SLDPRT", "features": ["Revolve_Body", "Precision_Bore_Step", "Oil_Groove"]}, ensure_ascii=False)}}]},
        {"role": "tool", "tool_call_id": "call_model_spindle_01", "content": json.dumps({"status": "success", "part_file": "Spindle_Bearing_Sleeve.SLDPRT", "features_count": 3}, ensure_ascii=False)},
        {"role": "assistant", "content": "现在进行工程图标注。初次标注尝试包含端面台阶全封闭链：",
         "tool_calls": [{"id": "call_draw_spindle_01", "type": "function", "function": {"name": "cad.generate_engineering_drawing_annotation", "arguments": json.dumps({"part_file": "Spindle_Bearing_Sleeve.SLDPRT", "dimensions": ["L1=45.0±0.02", "L2=35.0±0.02", "Total_L=80.0±0.01"]}, ensure_ascii=False)}}]},
        {"role": "tool", "tool_call_id": "call_draw_spindle_01", "content": json.dumps({"status": "conflict_warning", "issue": "检测到尺寸链封闭环冲突：总长 80.0±0.01 与分段累计公差 ±0.04 产生过约束超差风险，违反 GB/T 4458.4 尺寸注法规范"}, ensure_ascii=False)},
        {"role": "assistant", "content": "检测到尺寸链封闭环冲突！依据机械制图规范，绝不允许出现封闭尺寸公差环。我正在重构标注基准：以主要装配端面（基准 A）为单一基准，将总长标注为参考尺寸 (80)，释放非配合台阶作为自由公差环，并增加端面圆跳动 0.005 A：",
         "tool_calls": [{"id": "call_draw_spindle_rebuild", "type": "function", "function": {"name": "cad.generate_engineering_drawing_annotation", "arguments": json.dumps({"part_file": "Spindle_Bearing_Sleeve.SLDPRT", "dimensions": ["L1=45.0±0.02", "Total_Ref=(80)"], "gdt_frames": ["端面圆跳动 0.005 A", "同轴度 0.008 A"]}, ensure_ascii=False)}}]},
        {"role": "tool", "tool_call_id": "call_draw_spindle_rebuild", "content": json.dumps({"status": "success", "drawing_file": "Spindle_Bearing_Sleeve.SLDDRW", "dimension_chain_valid": True, "standards_compliance": "GB/T 4458 & ISO 1101 Validated"}, ensure_ascii=False)},
        {"role": "assistant", "content": "重构工程图标注通过。执行 SolidWorks 宏命令批量导出生产图纸与加工工序单：",
         "tool_calls": [{"id": "call_macro_spindle_01", "type": "function", "function": {"name": "cad.execute_solidworks_macro", "arguments": json.dumps({"part_file": "Spindle_Bearing_Sleeve.SLDPRT", "actions": ["export_dwg", "export_pdf"]}, ensure_ascii=False)}}]},
        {"role": "tool", "tool_call_id": "call_macro_spindle_01", "content": json.dumps({"status": "success", "dwg_files": ["Spindle_Bearing_Sleeve.dwg"]}, ensure_ascii=False)},
        {"role": "assistant", "content": "### 【精密主轴箱前支承套】尺寸链消解与标注闭环完成！\n\n1. **设计意图对齐**：精确配置 P4 级角接触轴承内孔 ⌀110 js6 与外径配合；\n2. **尺寸链超差冲突消解**：识别出封闭尺寸链缺陷，自动解除全封闭过约束，将总长转化为参考尺寸并施加单一工艺基准 A，增加端面跳动 0.005 A；\n3. **工程产物就绪**：输出符合国家制图标准的工程图与 DWG。"}
    ]
}

def append_jsonl(file_path, items):
    with open(file_path, "a", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"[+] 成功向 {os.path.basename(file_path)} 写入 {len(items)} 条新样本")

def main():
    print("="*60)
    print("Virtu 数据集高质量扩充与修复处理中...")
    print("="*60)
    
    # 1. 扩充 工装夹具 (07)
    path_fixture = os.path.join(DATA_DIR, "07_FIXTURES_AND_TOOLING", "fixture_design_rules_sft.jsonl")
    append_jsonl(path_fixture, fixture_items)
    
    # 2. 扩充 动画与造型 (08)
    path_anim = os.path.join(DATA_DIR, "08_ANIMATION_AND_CURRICULUM", "animation_and_curriculum_sft.jsonl")
    append_jsonl(path_anim, animation_items)
    
    # 3. 扩充 标准件选型 (05)
    path_std = os.path.join(DATA_DIR, "05_STANDARDS_AND_COMPONENTS_LIBRARY", "standard_components_selection_sft.jsonl")
    append_jsonl(path_std, standard_items)
    
    # 4. 扩充 机械设计手册 QA (03)
    path_handbook = os.path.join(DATA_DIR, "03_MECHANICAL_HANDBOOK_RAG_AND_QA", "mechanical_calculation_qa_sft.jsonl")
    append_jsonl(path_handbook, handbook_items)
    
    # 5. 扩充 CAD/CAM 工业代码 (02)
    path_cadcam = os.path.join(DATA_DIR, "02_SFT_CAD_CAM_CODE", "virtu_cad_cam_code_sft.jsonl")
    append_jsonl(path_cadcam, cad_cam_items)
    
    # 6. 扩充 Agent 异常恢复鲁棒轨迹 (01)
    path_agent = os.path.join(DATA_DIR, "01_SFT_AGENT_TOOLCALLS", "virtu_agent_toolcall_train.jsonl")
    append_jsonl(path_agent, [agent_robust_sample_a, agent_robust_sample_b, agent_robust_sample_c])
    
    print("\n[OK] 各子模块扩充写入完成。")

if __name__ == "__main__":
    main()
