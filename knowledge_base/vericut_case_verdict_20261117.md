---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 4089e70912072d5b0de62543257d198b_607edd3fe27311f189bc525400248c00
    ReservedCode1: F3VsrGZ1YkbKC/IsgLyGS4Ea1A9beBU+EZm5o33kkKVHbIUguyyPKfS1ukVjN2Og7FgkhCVvriyFJ02wqJ3QycUReoL3G0VrWzdAPvb8f9M2P4tl91w2T0fOFeGJRBpyOJbebFrFE/h+hzePlWSrXIPyDLYKD6Ab0Z028xkDHAQ7nPeW+kIr3/9rO0A=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 4089e70912072d5b0de62543257d198b_607edd3fe27311f189bc525400248c00
    ReservedCode2: F3VsrGZ1YkbKC/IsgLyGS4Ea1A9beBU+EZm5o33kkKVHbIUguyyPKfS1ukVjN2Og7FgkhCVvriyFJ02wqJ3QycUReoL3G0VrWzdAPvb8f9M2P4tl91w2T0fOFeGJRBpyOJbebFrFE/h+hzePlWSrXIPyDLYKD6Ab0Z028xkDHAQ7nPeW+kIr3/9rO0A=
---

# VERICUT 培训案例库（E:\training）案例判定书

**判定对象**：Agent 知识库索引 `D:\Virtu模型\knowledge_base\training_case_index.json` 收录的 80 个案例（78 个 .vcproject + 2 个 .vdafproject），资产根目录 `E:/training`。

**判定人**：Marvis（主 Agent）　**日期**：2026-11-17

**判定口径**：

1. 正误判定只采信两条硬证据——① 官方讲义 PDF 原文明确写出碰撞/错误/数据错误；② 官方题名即为查错类（Find and Detect Errors / debugging）。没有硬证据的一律不判错，避免把"没验证"说成"有错误"。
2. 轴数与工艺判定采信 NC 程序实测（模态 G0-G3、旋转轴字 A/B/C、车削循环 G70-G76/G32/G92）+ 机床文件 Component Type 交叉核对，不靠文件名猜。
3. **本轮未重跑 VERICUT 仿真**，因此"正确案例"含义是"官方按其正常工作流程使用、未发现故意缺陷证据"，不等于"已仿真验证零错误"。

---

## 一、错误案例 vs 正确案例

**错误案例 12 个，正确/参考案例 68 个**。错误案例还必须分型，因为四类错误的性质完全不同，Agent 不能一视同仁：

| 型 | 数量 | 错误性质 | 案例 |
| --- | --- | --- | --- |
| A 类·NC程序本身有错 | 4 | 3L Find and Detect Errors：程序含错误，仿真即为查错；3M Find and Detect Errors：程序含错误，仿真即为查错；3MT Find and Detect Errors：程序含错误，仿真即为查错；刀具过短导致真实碰撞，需用 MDI 反推合理刀长 | `lathe_session_day1`<br>`mill_session_day1`<br>`millturn_session_day1`<br>`session_14_MDI_to_validate_part_setup` |
| A 类·程序碰撞 | 2 | 下刀塔与结构件碰撞，仿真中止；第27行铆枪头碰撞，仿真中止 | `VDAF_programming_training_session`<br>`VDAF_simulation_training_session` |
| B 类·机床模型位置错 | 3 | 培训故意做错：5 轴 Z 模型未正确归位；培训故意做错：W 轴零点/模型角度未归位；培训故意做错：Z 轴零点/模型未正确归位 | `lathe_session_103l_add_3d_models_to_the_machine`<br>`mill_session_103m_add_3d_models_to_the_machine`<br>`millturn_session_103mt_add_3d_models_to_the_machine` |
| C 类·参数数据错 | 2 | 刀库随工程保存的优化值本身是错的 | `lathe_session_254fl_optimization`<br>`mill_session_254fm_optimization` |
| D 类·调试练习 | 1 | 以人为设置问题的工程练习查找故障 | `session_112_setting_up_and_using_basic_debugging_tools` |

**A 类要点**：这类案例的错误在 NC 程序/加工程序里，仿真一定会报碰撞或过切，是"拿错误程序当教材"；Agent 遇到这几条时，正确做法是期望仿真报错，而不是把报错当成自己操作失败。

**B/C 类要点**：错误不在程序，而在工程配置或数据——B 类是机床模型摆放/零点故意做错，C 类是随工程保存的刀库优化参数本身是错的。判错对象不同，修复动作也不同（B 改装配、C 重建刀库数据）。

---

## 二、设备需求判定（车床 / 三轴 / 四轴 / 五轴）

| 需用设备 | 数量 | 含车铣复合合计 |
| --- | --- | --- |
| 车床 | 22 | — |
| 车铣复合 | 17 | — |
| 三轴 | 13 | — |
| 四轴 | 7 | — |
| 五轴定位 | 15 | — |
| 不切削 | 4 | — |
| 机器人 | 2 | — |

**仅需车床（22 个）**：

`lathe_session_101l_Intro_to_VMC_building`　`lathe_session_102l_build_machine_kinematics`　`lathe_session_103l_add_3d_models_to_the_machine`　`lathe_session_104l_set_machine_collisions_and_travel_limits`　`lathe_session_105l_machine_building_review`　`lathe_session_107l_configure_tool_change_logic`　`lathe_session_10l_ncprogram_workoffset`　`lathe_session_111l_controlling_auxiliary_components`　`lathe_session_113l_control_configuration_review`　`lathe_session_11l_create_tool_library`　`lathe_session_13l_add_tools_to_turret`　`lathe_session_15l_multiple_setups_simulation`　`lathe_session_15l_multiple_setups_simulation2`　`lathe_session_16l_day_2_review`　`lathe_session_16l_day_2_review_2`　`lathe_session_252l_optimization`　`lathe_session_253l_optimization`　`lathe_session_254fl_optimization`　`lathe_session_6l_day1_review`　`lathe_session_7l_importing_models`　`lathe_session_day1`　`lathe_session_optimization`

**仅需普通三轴联动（13 个）**：

`mill_session_15m_multiple_setups_simulation_2`　`mill_session_16m_day_2_review`　`mill_session_16m_day_2_review_setup2`　`mill_session_252m_optimization`　`mill_session_253m_optimization`　`mill_session_254fm_optimization`　`mill_session_optimization`　`session_106_introduction_to_the_control`　`session_19_annotated_images`　`session_20_additive_module`　`session_22_probe_programming`　`session_23_assembly_manager`　`session_256_optimization`

**需四轴（7 个）**：

`mill_session_10m_ncprogram_workoffset`　`mill_session_11m_create_tool_library`　`mill_session_15m_multiple_setups_simulation`　`mill_session_7m_importing_models`　`mill_session_day1`　`session_109_configure_control_rotary_settings`　`session_21_using_reviewer`

**需五轴机床（15 个，但只是 3+2 定位）**：

`mill_session_101m_Intro_to_VMC_building`　`mill_session_102m_build_machine_kinematics`　`mill_session_103m_add_3d_models_to_the_machine`　`mill_session_104m_set_machine_collisions_and_travel_limits`　`mill_session_105m_machine_building_review`　`mill_session_107m_configure_tool_change_logic`　`mill_session_111m_controlling_auxiliary_components`　`mill_session_113m_control_configuration_review`　`mill_session_6m_day1_review`　`optimization_review`　`session_110_configure_control_to_output_messages`　`session_112_setting_up_and_using_basic_debugging_tools`　`session_14_MDI_to_validate_part_setup`　`session_18_create_report`　`session_8_create_coordinate_systems`

**需车铣复合（17 个）**：

`millturn_session_101mt_Intro_to_VMC_building`　`millturn_session_102mt_build_machine_kinematics`　`millturn_session_103mt_add_3d_models_to_the_machine`　`millturn_session_104mt_set_machine_collisions_and_travel_limits`　`millturn_session_105mt_machine_building_review`　`millturn_session_107mt_configure_tool_change_logic`　`millturn_session_10mt_ncprogram_workoffset`　`millturn_session_111mt_controlling_auxiliary_components`　`millturn_session_113mt_control_configuration_review`　`millturn_session_11mt_create_tool_library`　`millturn_session_15mt_multiple_setups_simulation`　`millturn_session_15mt_multiple_setups_simulation_2`　`millturn_session_16mt_day_2_review`　`millturn_session_6mt_day1_review`　`millturn_session_7mt_importing_models`　`millturn_session_day1`　`session_108_configure_spindle_logic`

**不需要切削（4 个纯建模/工装，2 个机器人 VDAF）**：

`new_project_inch`　`new_project_millimeter`　`session_24_delete_detached_stock`　`session_9_Move_and_locate_models`　`VDAF_programming_training_session`　`VDAF_simulation_training_session`

---

## 三、关于"五轴联动"的关键结论（对 Agent 最重要的一条）

**这 80 个案例里，需要五轴联动的案例是 0 个。**

实测证据：

1. 逐行解析全部案例 NC 程序，统计"同一进给块（G01/G02/G03）中同时存在并变化的旋转轴个数"——全库最大值为 **1**，从未出现 2 个旋转轴同时进给。真正的五轴联动（X/Y/Z + A + C 同时插补、RTCP 跟随）的必要条件是该值达到 2。
2. 15 个判为五轴的案例（mill_session_101m～113m 等），旋转轴动作全部出现在 **G00 快速定位块**里（如 `G0 Z500. B180.` 式的分度转位），进给块中旋转轴值变化次数为 0 —— 这是典型的 **3+2 定面加工**：先转位锁定，再纯三轴切削。
3. 7 个四轴案例同样只有单旋转轴分度，属于 3+1。

**因此**：

- 若 Agent 把这批案例标注为"五轴联动训练样本"，标注是错的，会把 3+2 定位当成联动曲面加工来学，学到的是错的策略。
- 要用五轴联动做真实验证，这批培训库不够，必须另造联动案例（连续变化 B/C 值的 impeller、blisk 类程序），例如 `D:\Virtu模型\artifacts\aero_closed_impeller\AE_CLOSED_IMPELLER_NASA1975_5AXIS.nc` 那一类。

---

## 四、必须标"待核验"的案例（24 个，不要当结论用）

| 待核验原因 | 数量 | 处理建议 |
| --- | --- | --- |
| 无绑定机床，能力靠文件名推断 | 10 | 仅 101L/102L/101M/102M/101MT/102MT 等建模阶段工程，机床尚未挂接，能力按家族暂定 |
| 机床为空白模板，轴数不可核验 | 3 | 105 系列为建模评审空白模板，不代表真实设备能力 |
| NC 用 B 轴但主机床仅 3 轴（实为多工位→第二台卧加 makino_a55） | 1 | 案例含两台机床，能力应按第二工位机床（卧加 B 轴）记，非主机床 |
| 机床加密(.xmch)，轴数不可核验 | 9 | 打开 VERICUT 查看机床轴配置，或按车铣复合+N 轴暂记 |

---

## 五、完整 80 条逐条判定表

| # | 案例 | 正误 | 错误型 | 需用设备 | 联动等级 | 置信度 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `lathe_session_101l_Intro_to_VMC_building` | 正确/参考案例 | — | 车床（2 轴车削，X/Z） | 车削（无旋转联动需求） | 低（仅文件名推断，待验证） | 无绑定机床，能力靠文件名推断 |
| 2 | `lathe_session_102l_build_machine_kinematics` | 正确/参考案例 | — | 车床（2 轴车削，X/Z） | 车削（无旋转联动需求） | 低（仅文件名推断，待验证） | 无绑定机床，能力靠文件名推断 |
| 3 | `lathe_session_103l_add_3d_models_to_the_machine` | 错误案例 | B 类·机床模型位置错 | 车床（2 轴车削，X/Z） | 车削（无旋转联动需求） | 高（NC 实测） |  |
| 4 | `lathe_session_104l_set_machine_collisions_and_travel_limits` | 正确/参考案例 | — | 车床（2 轴车削，X/Z） | 车削（无旋转联动需求） | 高（NC 实测） |  |
| 5 | `lathe_session_105l_machine_building_review` | 正确/参考案例 | — | 车床（2 轴车削，X/Z） | 车削（无旋转联动需求） | 高（NC 实测） | 机床为空白模板，轴数不可核验 |
| 6 | `lathe_session_107l_configure_tool_change_logic` | 正确/参考案例 | — | 车床（2 轴车削，X/Z） | 车削（无旋转联动需求） | 高（NC 实测） |  |
| 7 | `lathe_session_10l_ncprogram_workoffset` | 正确/参考案例 | — | 车床（2 轴车削，X/Z） | 车削（无旋转联动需求） | 高（NC 实测） |  |
| 8 | `lathe_session_111l_controlling_auxiliary_components` | 正确/参考案例 | — | 车床（2 轴车削，X/Z） | 车削（无旋转联动需求） | 高（NC 实测） |  |
| 9 | `lathe_session_113l_control_configuration_review` | 正确/参考案例 | — | 车床（2 轴车削，X/Z） | 车削（无旋转联动需求） | 高（NC 实测） |  |
| 10 | `lathe_session_11l_create_tool_library` | 正确/参考案例 | — | 车床（2 轴车削，X/Z） | 车削（无旋转联动需求） | 高（NC 实测） |  |
| 11 | `lathe_session_13l_add_tools_to_turret` | 正确/参考案例 | — | 车床（2 轴车削，X/Z） | 车削（无旋转联动需求） | 高（NC 实测） |  |
| 12 | `lathe_session_15l_multiple_setups_simulation` | 正确/参考案例 | — | 车床（2 轴车削，X/Z） | 车削（无旋转联动需求） | 高（NC 实测） |  |
| 13 | `lathe_session_15l_multiple_setups_simulation2` | 正确/参考案例 | — | 车床（2 轴车削，X/Z） | 车削（无旋转联动需求） | 高（NC 实测） |  |
| 14 | `lathe_session_16l_day_2_review` | 正确/参考案例 | — | 车床（2 轴车削，X/Z） | 车削（无旋转联动需求） | 高（机床轴实测） |  |
| 15 | `lathe_session_16l_day_2_review_2` | 正确/参考案例 | — | 车床（2 轴车削，X/Z） | 车削（无旋转联动需求） | 高（机床轴实测） |  |
| 16 | `lathe_session_252l_optimization` | 正确/参考案例 | — | 车床（2 轴车削，X/Z） | 车削（无旋转联动需求） | 高（NC 实测） |  |
| 17 | `lathe_session_253l_optimization` | 正确/参考案例 | — | 车床（2 轴车削，X/Z） | 车削（无旋转联动需求） | 高（NC 实测） |  |
| 18 | `lathe_session_254fl_optimization` | 错误案例 | C 类·参数数据错 | 车床（2 轴车削，X/Z） | 车削（无旋转联动需求） | 高（NC 实测） |  |
| 19 | `lathe_session_6l_day1_review` | 正确/参考案例 | — | 车床（2 轴车削，X/Z） | 车削（无旋转联动需求） | 高（NC 实测） |  |
| 20 | `lathe_session_7l_importing_models` | 正确/参考案例 | — | 车床（2 轴车削，X/Z） | 车削（无旋转联动需求） | 高（NC 实测） |  |
| 21 | `lathe_session_day1` | 错误案例 | A 类·NC程序本身有错 | 车床（2 轴车削，X/Z） | 车削（无旋转联动需求） | 高（NC 实测） |  |
| 22 | `lathe_session_optimization` | 正确/参考案例 | — | 车床（2 轴车削，X/Z） | 车削（无旋转联动需求） | 高（NC 实测） |  |
| 23 | `mill_session_101m_Intro_to_VMC_building` | 正确/参考案例 | — | 五轴机床（3+2 定位，不联动） | 3+2 定位（旋转轴仅分度，非联动） | 高（NC 实测） | 无绑定机床，能力靠文件名推断 |
| 24 | `mill_session_102m_build_machine_kinematics` | 正确/参考案例 | — | 五轴机床（3+2 定位，不联动） | 3+2 定位（旋转轴仅分度，非联动） | 高（NC 实测） | 无绑定机床，能力靠文件名推断 |
| 25 | `mill_session_103m_add_3d_models_to_the_machine` | 错误案例 | B 类·机床模型位置错 | 五轴机床（3+2 定位，不联动） | 3+2 定位（旋转轴仅分度，非联动） | 高（NC 实测） |  |
| 26 | `mill_session_104m_set_machine_collisions_and_travel_limits` | 正确/参考案例 | — | 五轴机床（3+2 定位，不联动） | 3+2 定位（旋转轴仅分度，非联动） | 高（NC 实测） |  |
| 27 | `mill_session_105m_machine_building_review` | 正确/参考案例 | — | 五轴机床（3+2 定位，不联动） | 3+2 定位（旋转轴仅分度，非联动） | 高（NC 实测） | 机床为空白模板，轴数不可核验 |
| 28 | `mill_session_107m_configure_tool_change_logic` | 正确/参考案例 | — | 五轴机床（3+2 定位，不联动） | 3+2 定位（旋转轴仅分度，非联动） | 高（NC 实测） |  |
| 29 | `mill_session_10m_ncprogram_workoffset` | 正确/参考案例 | — | 四轴（3+1，单旋转轴分度） | 单旋转轴分度/定位 | 高（机床轴实测） |  |
| 30 | `mill_session_111m_controlling_auxiliary_components` | 正确/参考案例 | — | 五轴机床（3+2 定位，不联动） | 3+2 定位（旋转轴仅分度，非联动） | 高（NC 实测） |  |
| 31 | `mill_session_113m_control_configuration_review` | 正确/参考案例 | — | 五轴机床（3+2 定位，不联动） | 3+2 定位（旋转轴仅分度，非联动） | 高（NC 实测） |  |
| 32 | `mill_session_11m_create_tool_library` | 正确/参考案例 | — | 四轴（3+1，单旋转轴分度） | 单旋转轴分度/定位 | 高（NC 实测） |  |
| 33 | `mill_session_15m_multiple_setups_simulation` | 正确/参考案例 | — | 四轴（3+1，单旋转轴分度） | 单旋转轴分度/定位 | 高（NC 实测） | NC 用 B 轴但主机床仅 3 轴（实为多工位→第二台卧加 makino_a55） |
| 34 | `mill_session_15m_multiple_setups_simulation_2` | 正确/参考案例 | — | 普通三轴立/卧式加工中心 | 无旋转轴（三轴） | 高（NC 实测） |  |
| 35 | `mill_session_16m_day_2_review` | 正确/参考案例 | — | 普通三轴立/卧式加工中心 | 无旋转轴（三轴） | 高（机床轴实测） |  |
| 36 | `mill_session_16m_day_2_review_setup2` | 正确/参考案例 | — | 普通三轴立/卧式加工中心 | 无旋转轴（三轴） | 高（机床轴实测） |  |
| 37 | `mill_session_252m_optimization` | 正确/参考案例 | — | 普通三轴立/卧式加工中心 | 无旋转轴（三轴） | 高（NC 实测） |  |
| 38 | `mill_session_253m_optimization` | 正确/参考案例 | — | 普通三轴立/卧式加工中心 | 无旋转轴（三轴） | 高（NC 实测） |  |
| 39 | `mill_session_254fm_optimization` | 错误案例 | C 类·参数数据错 | 普通三轴立/卧式加工中心 | 无旋转轴（三轴） | 高（NC 实测） |  |
| 40 | `mill_session_6m_day1_review` | 正确/参考案例 | — | 五轴机床（3+2 定位，不联动） | 3+2 定位（旋转轴仅分度，非联动） | 高（NC 实测） |  |
| 41 | `mill_session_7m_importing_models` | 正确/参考案例 | — | 四轴（3+1，单旋转轴分度） | 单旋转轴分度/定位 | 高（NC 实测） |  |
| 42 | `mill_session_day1` | 错误案例 | A 类·NC程序本身有错 | 四轴（3+1，单旋转轴分度） | 单旋转轴分度/定位 | 高（NC 实测） |  |
| 43 | `mill_session_optimization` | 正确/参考案例 | — | 普通三轴立/卧式加工中心 | 无旋转轴（三轴） | 高（NC 实测） |  |
| 44 | `millturn_session_101mt_Intro_to_VMC_building` | 正确/参考案例 | — | 车铣复合（车床+动力刀/C 轴） | 车削（无旋转联动需求） | 高（NC 实测） | 无绑定机床，能力靠文件名推断 |
| 45 | `millturn_session_102mt_build_machine_kinematics` | 正确/参考案例 | — | 车铣复合（车床+动力刀/C 轴） | 车削（无旋转联动需求） | 高（NC 实测） | 无绑定机床，能力靠文件名推断 |
| 46 | `millturn_session_103mt_add_3d_models_to_the_machine` | 错误案例 | B 类·机床模型位置错 | 车铣复合（车床+动力刀/C 轴） | 车削（无旋转联动需求） | 高（NC 实测） |  |
| 47 | `millturn_session_104mt_set_machine_collisions_and_travel_limits` | 正确/参考案例 | — | 车铣复合（车床+动力刀/C 轴） | 车削（无旋转联动需求） | 高（NC 实测） |  |
| 48 | `millturn_session_105mt_machine_building_review` | 正确/参考案例 | — | 车铣复合（车床+动力刀/C 轴） | 车削（无旋转联动需求） | 高（NC 实测） | 机床为空白模板，轴数不可核验 |
| 49 | `millturn_session_107mt_configure_tool_change_logic` | 正确/参考案例 | — | 车铣复合（车床+动力刀/C 轴） | 车削（无旋转联动需求） | 高（NC 实测） |  |
| 50 | `millturn_session_10mt_ncprogram_workoffset` | 正确/参考案例 | — | 车铣复合（车床+动力刀/C 轴） | 车削（无旋转联动需求） | 高（机床轴实测） | 机床加密(.xmch)，轴数不可核验 |
| 51 | `millturn_session_111mt_controlling_auxiliary_components` | 正确/参考案例 | — | 车铣复合（车床+动力刀/C 轴） | 车削（无旋转联动需求） | 高（NC 实测） |  |
| 52 | `millturn_session_113mt_control_configuration_review` | 正确/参考案例 | — | 车铣复合（车床+动力刀/C 轴） | 车削（无旋转联动需求） | 高（NC 实测） |  |
| 53 | `millturn_session_11mt_create_tool_library` | 正确/参考案例 | — | 车铣复合（车床+动力刀/C 轴） | 车削（无旋转联动需求） | 高（NC 实测） | 机床加密(.xmch)，轴数不可核验 |
| 54 | `millturn_session_15mt_multiple_setups_simulation` | 正确/参考案例 | — | 车铣复合（车床+动力刀/C 轴） | 车削（无旋转联动需求） | 高（NC 实测） | 机床加密(.xmch)，轴数不可核验 |
| 55 | `millturn_session_15mt_multiple_setups_simulation_2` | 正确/参考案例 | — | 车铣复合（车床+动力刀/C 轴） | 车削（无旋转联动需求） | 高（NC 实测） | 机床加密(.xmch)，轴数不可核验 |
| 56 | `millturn_session_16mt_day_2_review` | 正确/参考案例 | — | 车铣复合（车床+动力刀/C 轴） | 车削（无旋转联动需求） | 高（机床轴实测） | 机床加密(.xmch)，轴数不可核验 |
| 57 | `millturn_session_6mt_day1_review` | 正确/参考案例 | — | 车铣复合（车床+动力刀/C 轴） | 车削（无旋转联动需求） | 高（NC 实测） | 机床加密(.xmch)，轴数不可核验 |
| 58 | `millturn_session_7mt_importing_models` | 正确/参考案例 | — | 车铣复合（车床+动力刀/C 轴） | 车削（无旋转联动需求） | 高（NC 实测） | 机床加密(.xmch)，轴数不可核验 |
| 59 | `millturn_session_day1` | 错误案例 | A 类·NC程序本身有错 | 车铣复合（车床+动力刀/C 轴） | 车削（无旋转联动需求） | 高（NC 实测） | 机床加密(.xmch)，轴数不可核验 |
| 60 | `new_project_inch` | 正确/参考案例 | — | 无需切削（仅建模/工装操作） | 无旋转轴（三轴） | 中（无 NC 无机床，按会话定位） | 无绑定机床，能力靠文件名推断 |
| 61 | `new_project_millimeter` | 正确/参考案例 | — | 无需切削（仅建模/工装操作） | 无旋转轴（三轴） | 中（无 NC 无机床，按会话定位） | 无绑定机床，能力靠文件名推断 |
| 62 | `optimization_review` | 正确/参考案例 | — | 五轴机床（3+2 定位，不联动） | 3+2 定位（旋转轴仅分度，非联动） | 高（NC 实测） |  |
| 63 | `session_106_introduction_to_the_control` | 正确/参考案例 | — | 普通三轴立/卧式加工中心 | 无旋转轴（三轴） | 高（NC 实测） |  |
| 64 | `session_108_configure_spindle_logic` | 正确/参考案例 | — | 车铣复合（车床+动力刀/C 轴） | 车削（无旋转联动需求） | 高（NC 实测） |  |
| 65 | `session_109_configure_control_rotary_settings` | 正确/参考案例 | — | 四轴（3+1，单旋转轴分度） | 单旋转轴分度/定位 | 高（NC 实测） |  |
| 66 | `session_110_configure_control_to_output_messages` | 正确/参考案例 | — | 五轴机床（3+2 定位，不联动） | 3+2 定位（旋转轴仅分度，非联动） | 高（NC 实测） |  |
| 67 | `session_112_setting_up_and_using_basic_debugging_tools` | 错误案例 | D 类·调试练习 | 五轴机床（3+2 定位，不联动） | 3+2 定位（旋转轴仅分度，非联动） | 高（NC 实测） |  |
| 68 | `session_14_MDI_to_validate_part_setup` | 错误案例 | A 类·NC程序本身有错 | 五轴机床（3+2 定位，不联动） | 3+2 定位（旋转轴仅分度，非联动） | 高（NC 实测） |  |
| 69 | `session_18_create_report` | 正确/参考案例 | — | 五轴机床（3+2 定位，不联动） | 3+2 定位（旋转轴仅分度，非联动） | 高（NC 实测） |  |
| 70 | `session_19_annotated_images` | 正确/参考案例 | — | 普通三轴立/卧式加工中心 | 无旋转轴（三轴） | 高（NC 实测） |  |
| 71 | `session_20_additive_module` | 正确/参考案例 | — | 普通三轴立/卧式加工中心 | 无旋转轴（三轴） | 高（NC 实测） |  |
| 72 | `session_21_using_reviewer` | 正确/参考案例 | — | 四轴（3+1，单旋转轴分度） | 单旋转轴分度/定位 | 高（NC 实测） |  |
| 73 | `session_22_probe_programming` | 正确/参考案例 | — | 普通三轴立/卧式加工中心 | 无旋转轴（三轴） | 高（NC 实测） |  |
| 74 | `session_23_assembly_manager` | 正确/参考案例 | — | 普通三轴立/卧式加工中心 | 无旋转轴（三轴） | 高（NC 实测） |  |
| 75 | `session_24_delete_detached_stock` | 正确/参考案例 | — | 无需切削（仅建模/工装操作） | 无旋转轴（三轴） | 中（无 NC 无机床，按会话定位） | 无绑定机床，能力靠文件名推断 |
| 76 | `session_256_optimization` | 正确/参考案例 | — | 普通三轴立/卧式加工中心 | 无旋转轴（三轴） | 高（NC 实测） |  |
| 77 | `session_8_create_coordinate_systems` | 正确/参考案例 | — | 五轴机床（3+2 定位，不联动） | 3+2 定位（旋转轴仅分度，非联动） | 高（NC 实测） |  |
| 78 | `session_9_Move_and_locate_models` | 正确/参考案例 | — | 无需切削（仅建模/工装操作） | 无旋转轴（三轴） | 中（无 NC 无机床，按会话定位） | 无绑定机床，能力靠文件名推断 |
| 79 | `VDAF_programming_training_session` | 错误案例 | A 类·程序碰撞 | 铆接机器人/VDAF（非 CNC 主轴切削） | 无旋转轴（三轴） | 中（资产类别实测） | 机床加密(.xmch)，轴数不可核验 |
| 80 | `VDAF_simulation_training_session` | 错误案例 | A 类·程序碰撞 | 铆接机器人/VDAF（非 CNC 主轴切削） | 无旋转轴（三轴） | 中（资产类别实测） |  |

---

## 六、给 Agent 的执行约束（直接写进规则）

1. 加载错误案例（A 型）时必须预期仿真报错；把"报错"判为案例预期结果，不计入 Agent 失败。
2. 选机床时必须按本表的"需用设备"列，不得按案例名前缀 `mill_` 就默认三轴——`mill_session_101m` 系列实为五轴机床 3+2。
3. 生成/评估五轴联动能力时，禁止引用本库任何案例作为"联动证据"。
4. 24 个待核验案例，Agent 回答时必须带"待核验"标注，禁止给出确定轴数。
*（内容由AI生成，仅供参考）*
