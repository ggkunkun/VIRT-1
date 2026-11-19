# 工程图与PMI

> 版本适用范围：**NX12.0-CN（NX 12.0 / 12.0.2.9 介质，简体中文）**
> 功能点数量：597　|　数据基准：`training/catalog/nx12_cn_full_catalog.json`
> 结构：模块 → 子模块 → 功能点 → 操作步骤 → 参数说明 → 注意事项（六级）
> 证据等级：E1=介质.btn/官方翻译直提；E2=仅菜单定义+官方中文；E3=无官方中文，需GUI复核；E4=官方翻译表补全，菜单/参数需GUI复核

## 1. 子模块：Simcenter 环境

本子模块 96 个功能点。

### 1.1 功能点：形状(H)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_ANALYSIS_SHAPE`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 7 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_te.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「形状(H)」定位。
2. 按对话框提示操作：列出“形状分析”命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出“形状分析”命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.2 功能点：格式(R)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_ARRANGE`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 9 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_te.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「格式(R)」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.3 功能点：2D 中心线  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_CRE_2D_CENTERLINE`
- **菜单路径**：插入(S) › 中心线(E) › 2D 中心线...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **来源提示**：`simcenter_layout_te.men`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 3 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/simcenter_layout_te_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 中心线(E)**。
2. 在展开项中选择 **2D 中心线...**（命令 ID：`UG_DRAFT_CRE_2D_CENTERLINE`）。
3. 按对话框提示操作：创建 2D 中心线。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建 2D 中心线。
    - 检索同义词：create a draft axis

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.4 功能点：区域填充  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_CRE_AREAFILL`
- **菜单路径**：插入(S) › 注释(A) › 区域填充(F)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **来源提示**：`simcenter_layout_te.men`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 3 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/simcenter_layout_te_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 注释(A)**。
2. 在展开项中选择 **区域填充(F)...**（命令 ID：`UG_DRAFT_CRE_AREAFILL`）。
3. 按对话框提示操作：在指定边界内创建图样或填实。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在指定边界内创建图样或填实。
    - 检索同义词：filled area

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.5 功能点：螺栓圆中心线  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_CRE_BOLT_CIRCLE_CENTERLINE`
- **菜单路径**：插入(S) › 中心线(E) › 螺栓圆(B)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **来源提示**：`simcenter_layout_te.men`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 3 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/simcenter_layout_te_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 中心线(E)**。
2. 在展开项中选择 **螺栓圆(B)...**（命令 ID：`UG_DRAFT_CRE_BOLT_CIRCLE_CENTERLINE`）。
3. 按对话框提示操作：创建完整或部分螺栓圆中心线。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建完整或部分螺栓圆中心线。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.6 功能点：中心标记  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_CRE_CENTERMARK`
- **菜单路径**：插入(S) › 中心线(E) › 中心标记(M)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **来源提示**：`simcenter_layout_te.men`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 3 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/simcenter_layout_te_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 中心线(E)**。
2. 在展开项中选择 **中心标记(M)...**（命令 ID：`UG_DRAFT_CRE_CENTERMARK`）。
3. 按对话框提示操作：创建中心标记。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建中心标记。
    - 检索同义词：create a rotating axis

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.7 功能点：圆形中心线  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_CRE_CIRCULAR_CENTERLINE`
- **菜单路径**：插入(S) › 中心线(E) › 圆形(C)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **来源提示**：`simcenter_layout_te.men`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 3 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/simcenter_layout_te_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 中心线(E)**。
2. 在展开项中选择 **圆形(C)...**（命令 ID：`UG_DRAFT_CRE_CIRCULAR_CENTERLINE`）。
3. 按对话框提示操作：创建完整或不完整的圆形中心线。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建完整或不完整的圆形中心线。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.8 功能点：特征控制框  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_CRE_GDT_SYMBOLS`
- **菜单路径**：插入(S) › 注释(A) › 特征控制框(E)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **来源提示**：`simcenter_layout_te.men`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 3 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/simcenter_layout_te_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 注释(A)**。
2. 在展开项中选择 **特征控制框(E)...**（命令 ID：`UG_DRAFT_CRE_GDT_SYMBOLS`）。
3. 按对话框提示操作：创建单行、多行或复合的特征控制框。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建单行、多行或复合的特征控制框。
    - 检索同义词：fcf, insert a geometric tolerance into a drawing, set tolerance values for geometric tolerances, designate symbols for geometric tolerances, change the tolerance class

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.9 功能点：符号标注  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_CRE_ID_SYMBOLS`
- **菜单路径**：插入(S) › 注释(A) › 符号标注(B)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **来源提示**：`simcenter_layout_te.men`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 3 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/simcenter_layout_te_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 注释(A)**。
2. 在展开项中选择 **符号标注(B)...**（命令 ID：`UG_DRAFT_CRE_ID_SYMBOLS`）。
3. 按对话框提示操作：创建符号注释。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建符号注释。
    - 检索同义词：add a balloon note, annotation, identification symbol, ID symbol

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.10 功能点：相交符号  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_CRE_INTERSECTION`
- **菜单路径**：插入(S) › 注释(A) › 相交符号(C)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **来源提示**：`simcenter_layout_te.men`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 3 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/simcenter_layout_te_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 注释(A)**。
2. 在展开项中选择 **相交符号(C)...**（命令 ID：`UG_DRAFT_CRE_INTERSECTION`）。
3. 按对话框提示操作：创建相交符号，该符号代表拐角上的证示线。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建相交符号，该符号代表拐角上的证示线。
    - 检索同义词：balloon, annotation

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.11 功能点：注释  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_CRE_NOTES_LABELS`
- **菜单路径**：插入(S) › 注释(A) › 注释(N)...；插入(S) › 注释(N)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **来源提示**：`simcenter_layout_te.men`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 4 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/simcenter_layout_te_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 注释(A)**。
2. 在展开项中选择 **注释(N)...**（命令 ID：`UG_DRAFT_CRE_NOTES_LABELS`）。
3. 按对话框提示操作：创建注释。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建注释。
    - 检索同义词：callout, text, drawing note, change the tolerance class

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.12 功能点：偏置中心点符号  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_CRE_OFFSET_CENTER_POINT`
- **菜单路径**：插入(S) › 中心线(E) › 偏置中心点符号(O)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **来源提示**：`simcenter_layout_te.men`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 3 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/simcenter_layout_te_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 中心线(E)**。
2. 在展开项中选择 **偏置中心点符号(O)...**（命令 ID：`UG_DRAFT_CRE_OFFSET_CENTER_POINT`）。
3. 按对话框提示操作：创建偏置中心点符号，该符号表示某一圆弧的中心，该中心的位置偏离其真正中心。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建偏置中心点符号，该符号表示某一圆弧的中心，该中心的位置偏离其真正中心。
    - 检索同义词：balloon, annotation

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.13 功能点：定制符号  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_CRE_SYMBOLS`
- **菜单路径**：插入(S) › 符号(Y) › 定制(C)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **来源提示**：`simcenter_layout_te.men`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 3 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/simcenter_layout_te_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 符号(Y)**。
2. 在展开项中选择 **定制(C)...**（命令 ID：`UG_DRAFT_CRE_SYMBOLS`）。
3. 按对话框提示操作：根据符号库创建定制符号的实例。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：根据符号库创建定制符号的实例。
    - 检索同义词：insert a custom symbol

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.14 功能点：对称中心线  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_CRE_SYMMETRICAL_CENTERLINE`
- **菜单路径**：插入(S) › 中心线(E) › 对称(S)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **来源提示**：`simcenter_layout_te.men`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 3 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/simcenter_layout_te_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 中心线(E)**。
2. 在展开项中选择 **对称(S)...**（命令 ID：`UG_DRAFT_CRE_SYMMETRICAL_CENTERLINE`）。
3. 按对话框提示操作：创建对称中心线。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建对称中心线。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.15 功能点：目标点符号  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_CRE_TARGET_POINT`
- **菜单路径**：插入(S) › 注释(A) › 目标点符号(T)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **来源提示**：`simcenter_layout_te.men`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 3 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/simcenter_layout_te_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 注释(A)**。
2. 在展开项中选择 **目标点符号(T)...**（命令 ID：`UG_DRAFT_CRE_TARGET_POINT`）。
3. 按对话框提示操作：创建可用于进行尺寸标注的目标点符号。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建可用于进行尺寸标注的目标点符号。
    - 检索同义词：balloon, annotation

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.16 功能点：焊接符号  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_CRE_WELD_SYMBOL`
- **菜单路径**：插入(S) › 注释(A) › 焊接符号(W)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **来源提示**：`simcenter_layout_te.men`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 3 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/simcenter_layout_te_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 注释(A)**。
2. 在展开项中选择 **焊接符号(W)...**（命令 ID：`UG_DRAFT_CRE_WELD_SYMBOL`）。
3. 按对话框提示操作：创建关联焊接符号。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建关联焊接符号。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.17 功能点：剖面线  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_CRE_XHATCH`
- **菜单路径**：插入(S) › 注释(A) › 剖面线(O)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **来源提示**：`simcenter_layout_te.men`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 3 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/simcenter_layout_te_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 注释(A)**。
2. 在展开项中选择 **剖面线(O)...**（命令 ID：`UG_DRAFT_CRE_XHATCH`）。
3. 按对话框提示操作：在指定边界内创建图样。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在指定边界内创建图样。
    - 检索同义词：draft cross section

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.18 功能点：基准特征符号  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_DATUM_SYMBOL`
- **菜单路径**：插入(S) › 注释(A) › 基准特征符号(R)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **来源提示**：`simcenter_layout_te.men`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 3 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/simcenter_layout_te_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 注释(A)**。
2. 在展开项中选择 **基准特征符号(R)...**（命令 ID：`UG_DRAFT_DATUM_SYMBOL`）。
3. 按对话框提示操作：创建基准特征符号。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建基准特征符号。
    - 检索同义词：insert a model datum plane

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.19 功能点：基准目标  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_DATUM_TARGET_SYMBOL`
- **菜单路径**：插入(S) › 注释(A) › 基准目标(D)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **来源提示**：`simcenter_layout_te.men`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 3 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/simcenter_layout_te_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 注释(A)**。
2. 在展开项中选择 **基准目标(D)...**（命令 ID：`UG_DRAFT_DATUM_TARGET_SYMBOL`）。
3. 按对话框提示操作：创建基准目标。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建基准目标。
    - 检索同义词：insert datum targets

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.20 功能点：角度尺寸  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_DIMENSION_ANGULAR`
- **菜单路径**：插入(S) › 尺寸(M) › 角度(A)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **来源提示**：`simcenter_layout_te.men`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 3 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/simcenter_layout_te_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 尺寸(M)**。
2. 在展开项中选择 **角度(A)...**（命令 ID：`UG_DRAFT_DIMENSION_ANGULAR`）。
3. 按对话框提示操作：在两条不平行线之间创建角度尺寸。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在两条不平行线之间创建角度尺寸。
    - 检索同义词：degrees, angle, radians

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.21 功能点：倒斜角尺寸  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_DIMENSION_CHAMFER`
- **菜单路径**：插入(S) › 尺寸(M) › 倒斜角(C)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **来源提示**：`simcenter_layout_te.men`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 3 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/simcenter_layout_te_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 尺寸(M)**。
2. 在展开项中选择 **倒斜角(C)...**（命令 ID：`UG_DRAFT_DIMENSION_CHAMFER`）。
3. 按对话框提示操作：在倒斜角曲线上创建倒斜角尺寸。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在倒斜角曲线上创建倒斜角尺寸。
    - 检索同义词：bevel

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.22 功能点：弧长尺寸  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_DIMENSION_CURVE_LENGTH`
- **菜单路径**：插入(S) › 尺寸(M) › 弧长(G)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **来源提示**：`simcenter_layout_te.men`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 3 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/simcenter_layout_te_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 尺寸(M)**。
2. 在展开项中选择 **弧长(G)...**（命令 ID：`UG_DRAFT_DIMENSION_CURVE_LENGTH`）。
3. 按对话框提示操作：创建弧长尺寸来测量圆弧的周长。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建弧长尺寸来测量圆弧的周长。
    - 检索同义词：total length, curve length, circumference

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.23 功能点：线性尺寸  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_DIMENSION_LINEAR`
- **菜单路径**：插入(S) › 尺寸(M) › 线性(L)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **来源提示**：`simcenter_layout_te.men`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 3 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/simcenter_layout_te_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 尺寸(M)**。
2. 在展开项中选择 **线性(L)...**（命令 ID：`UG_DRAFT_DIMENSION_LINEAR`）。
3. 按对话框提示操作：在两个对象或点位置之间创建线性尺寸。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在两个对象或点位置之间创建线性尺寸。
    - 检索同义词：dimension along X, dimension along Y, height, profile, landscape, minimum distance dimension, length dimension, opposite, distance from point, orthogonal, horizontal dimension, vertical dimension, parallel dimension, perpendicular dimension, cylindrical dimension, diameter, radius, horizontal chain dimensions, vertical chain dimensions, horizontal baseline dimensions, vertical baseline dimensions, insert dimensions from a common reference, hole callout

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.24 功能点：径向尺寸  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_DIMENSION_RADIAL`
- **菜单路径**：插入(S) › 尺寸(M) › 径向(R)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **来源提示**：`simcenter_layout_te.men`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 3 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/simcenter_layout_te_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 尺寸(M)**。
2. 在展开项中选择 **径向(R)...**（命令 ID：`UG_DRAFT_DIMENSION_RADIAL`）。
3. 按对话框提示操作：创建圆形对象的半径或直径尺寸。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建圆形对象的半径或直径尺寸。
    - 检索同义词：hole dimension, radius to center dimension, folded radius dimension, hole callout

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.25 功能点：快速尺寸  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_DIMENSION_RAPID`
- **菜单路径**：插入(S) › 尺寸(M) › 快速(P)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **来源提示**：`simcenter_layout_te.men`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 3 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/simcenter_layout_te_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 尺寸(M)**。
2. 在展开项中选择 **快速(P)...**（命令 ID：`UG_DRAFT_DIMENSION_RAPID`）。
3. 按对话框提示操作：根据选定对象和光标的位置自动判断尺寸类型，以创建尺寸。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：根据选定对象和光标的位置自动判断尺寸类型，以创建尺寸。
    - 检索同义词：guess, imply, derive, reference dimension, driven dimension with tolerance, inferred dimensions

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.26 功能点：厚度尺寸  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_DIMENSION_THICKNESS`
- **菜单路径**：插入(S) › 尺寸(M) › 厚度(T)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **来源提示**：`simcenter_layout_te.men`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 3 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/simcenter_layout_te_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 尺寸(M)**。
2. 在展开项中选择 **厚度(T)...**（命令 ID：`UG_DRAFT_DIMENSION_THICKNESS`）。
3. 按对话框提示操作：创建厚度尺寸来测量两条曲线之间的距离。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建厚度尺寸来测量两条曲线之间的距离。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.27 功能点：编辑图纸页  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_DRW_MODIFY`
- **菜单路径**：编辑(E) › 图纸页(H)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **来源提示**：`simcenter_layout_te.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 2 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/simcenter_layout_te_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E)**。
2. 在展开项中选择 **图纸页(H)...**（命令 ID：`UG_DRAFT_DRW_MODIFY`）。
3. 按对话框提示操作：编辑活动图纸页的名称、大小、比例、度量单位和投影角。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：编辑活动图纸页的名称、大小、比例、度量单位和投影角。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.28 功能点：打开图纸页  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_DRW_OPEN`
- **菜单路径**：格式(R) › 打开图纸页(T)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **来源提示**：`ug_gateway_simcenter.men`
- **出现菜单**：`DRAFTING/application/ug_drafting.men` 等 2 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_gateway_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **格式(R)**。
2. 在展开项中选择 **打开图纸页(T)...**（命令 ID：`UG_DRAFT_DRW_OPEN`）。
3. 按对话框提示操作：打开现有的图纸页。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：打开现有的图纸页。
    - 检索同义词：workplane, work plane, construction plane, work coordinate system

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.29 功能点：编辑(E)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_EDIT`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_te.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「编辑(E)」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.30 功能点：注释(O)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_EDIT_ANNOTATION`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 2 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_te.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「注释(O)」定位。
2. 按对话框提示操作：列出“编辑注释”命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出“编辑注释”命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.31 功能点：显示和隐藏(H)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_EDIT_SHOWHIDE`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 9 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_te.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「显示和隐藏(H)」定位。
2. 按对话框提示操作：列出“显示和隐藏”命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出“显示和隐藏”命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.32 功能点：符号(S)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_EDIT_SYMBOL`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 2 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_te.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「符号(S)」定位。
2. 按对话框提示操作：列出“编辑符号”命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出“编辑符号”命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.33 功能点：帮助(H)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_HELP`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 13 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_te.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「帮助(H)」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.34 功能点：关于 NX  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_HELP_ABOUT_UG`
- **菜单路径**：帮助(H) › 关于 NX(A)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **来源提示**：`definitions_simcenter.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/definitions_simcenter_btn_simpl_chinese.txt` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **帮助(H)**。
2. 在展开项中选择 **关于 NX(A)**（命令 ID：`UG_HELP_ABOUT_UG`）。
3. 按对话框提示操作：显示有关 NX 的常规信息和法律信息。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：显示有关 NX 的常规信息和法律信息。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.35 功能点：事件状态与跟踪  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_HELP_CALL_STATUS`
- **菜单路径**：帮助(H) › 在线技术支持(O) › 事件状态与跟踪(S)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **来源提示**：`ug_styler_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_styler_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **帮助(H) › 在线技术支持(O)**。
2. 在展开项中选择 **事件状态与跟踪(S)**（命令 ID：`UG_HELP_CALL_STATUS`）。
3. 按对话框提示操作：检查技术支持数据库，获取所报告问题的最新状态。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：检查技术支持数据库，获取所报告问题的最新状态。
    - 检索同义词：IR

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.36 功能点：捕捉事件报告数据  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_HELP_CAPTURE_IR_DATA`
- **菜单路径**：帮助(H) › 捕捉事件报告数据(I)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **来源提示**：`definitions_simcenter.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/definitions_simcenter_btn_simpl_chinese.txt` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **帮助(H)**。
2. 在展开项中选择 **捕捉事件报告数据(I)**（命令 ID：`UG_HELP_CAPTURE_IR_DATA`）。
3. 按对话框提示操作：将使用 NX 时遇到的事件描述保存到文本文件。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将使用 NX 时遇到的事件描述保存到文本文件。
    - 检索同义词：IR

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.37 功能点：认证  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_HELP_CERT_PATCHES`
- **菜单路径**：帮助(H) › 在线技术支持(O) › 认证(C)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **来源提示**：`ug_styler_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_styler_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **帮助(H) › 在线技术支持(O)**。
2. 在展开项中选择 **认证(C)**（命令 ID：`UG_HELP_CERT_PATCHES`）。
3. 按对话框提示操作：列出受支持的操作系统版本和关联的供应商软件产品、补丁、图形及相关硬件产品。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出受支持的操作系统版本和关联的供应商软件产品、补丁、图形及相关硬件产品。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.38 功能点：命令查找器  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_HELP_COMMAND_FINDER`
- **菜单路径**：帮助(H) › 命令查找器(F)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **来源提示**：`ug_styler_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 12 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_styler_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **帮助(H)**。
2. 在展开项中选择 **命令查找器(F)...**（命令 ID：`UG_HELP_COMMAND_FINDER`）。
3. 按对话框提示操作：通过使用关键词或词组搜索匹配项，找到一系列命令。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：通过使用关键词或词组搜索匹配项，找到一系列命令。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.39 功能点：定制和编程论坛  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_HELP_CUSTOMIZATION_FORUM`
- **菜单路径**：帮助(H) › PLM 社区论坛 › 定制和编程论坛(C)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **来源提示**：`ug_styler_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_styler_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **帮助(H) › PLM 社区论坛**。
2. 在展开项中选择 **定制和编程论坛(C)**（命令 ID：`UG_HELP_CUSTOMIZATION_FORUM`）。
3. 按对话框提示操作：访问 NX 定制和编程的在线用户社区论坛。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：访问 NX 定制和编程的在线用户社区论坛。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.40 功能点：设计论坛  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_HELP_DESIGN_FORUM`
- **菜单路径**：帮助(H) › PLM 社区论坛 › 设计论坛(D)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **来源提示**：`ug_styler_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_styler_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **帮助(H) › PLM 社区论坛**。
2. 在展开项中选择 **设计论坛(D)**（命令 ID：`UG_HELP_DESIGN_FORUM`）。
3. 按对话框提示操作：访问 NX 设计的在线用户社区论坛。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：访问 NX 设计的在线用户社区论坛。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.41 功能点：下载 NX 的完整发行版  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_HELP_DOWNLOAD_UG`
- **菜单路径**：帮助(H) › 在线技术支持(O) › 下载 NX 的完整发行版(D)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **来源提示**：`definitions_simcenter.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/definitions_simcenter_btn_simpl_chinese.txt` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **帮助(H) › 在线技术支持(O)**。
2. 在展开项中选择 **下载 NX 的完整发行版(D)**（命令 ID：`UG_HELP_DOWNLOAD_UG`）。
3. 按对话框提示操作：下载选定版本 NX 的完整发行版。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：下载选定版本 NX 的完整发行版。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.42 功能点：电子会议  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_HELP_ELEC_CONF`
- **菜单路径**：帮助(H) › 在线技术支持(O) › 电子会议(E)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **来源提示**：`ug_styler_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_styler_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **帮助(H) › 在线技术支持(O)**。
2. 在展开项中选择 **电子会议(E)**（命令 ID：`UG_HELP_ELEC_CONF`）。
3. 按对话框提示操作：提供电子论坛，以交流有关 Siemens PLM Software 产品线的信息。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：提供电子论坛，以交流有关 Siemens PLM Software 产品线的信息。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.43 功能点：生成应急许可证  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_HELP_EMERGNCY_LICENSE`
- **菜单路径**：帮助(H) › 在线技术支持(O) › 生成应急许可证(M)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **来源提示**：`ug_styler_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_styler_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **帮助(H) › 在线技术支持(O)**。
2. 在展开项中选择 **生成应急许可证(M)**（命令 ID：`UG_HELP_EMERGNCY_LICENSE`）。
3. 按对话框提示操作：申请应急许可证文件，其有效期为 7 天。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：申请应急许可证文件，其有效期为 7 天。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.44 功能点：生成 IR/PR 的支持日志  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_HELP_GENERATE_LOG`
- **菜单路径**：帮助(H) › 生成 IR/PR 的支持日志(G)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **来源提示**：`ug_styler_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_styler_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **帮助(H)**。
2. 在展开项中选择 **生成 IR/PR 的支持日志(G)**（命令 ID：`UG_HELP_GENERATE_LOG`）。
3. 按对话框提示操作：为 IR/PR 设置日志记录选项或收集支持日志。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：为 IR/PR 设置日志记录选项或收集支持日志。
    - 检索同义词：syslog, GTAC

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.45 功能点：GTAC 文件服务器  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_HELP_GTAC_SERVER`
- **菜单路径**：帮助(H) › 在线技术支持(O) › GTAC 文件服务器
- **定义来源**：`UGII/menus/definitions_main.btn`
- **来源提示**：`ug_styler_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_styler_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **帮助(H) › 在线技术支持(O)**。
2. 在展开项中选择 **GTAC 文件服务器**（命令 ID：`UG_HELP_GTAC_SERVER`）。
3. 按对话框提示操作：上传或下载数据（例如部件文件和图像）到技术支持文件服务器。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：上传或下载数据（例如部件文件和图像）到技术支持文件服务器。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.46 功能点：GTAC 支持网页  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_HELP_GTAC_SUP_PAGE`
- **菜单路径**：帮助(H) › 在线技术支持(O) › GTAC 支持网页(W)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **来源提示**：`ug_styler_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_styler_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **帮助(H) › 在线技术支持(O)**。
2. 在展开项中选择 **GTAC 支持网页(W)**（命令 ID：`UG_HELP_GTAC_SUP_PAGE`）。
3. 按对话框提示操作：访问 Web 服务器，获取 Siemens PLM Software 产品的技术支持。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：访问 Web 服务器，获取 Siemens PLM Software 产品的技术支持。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.47 功能点：帮助  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_HELP_HTML_DOC`
- **菜单路径**：帮助(H) › NX 帮助(H)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **来源提示**：`definitions_simcenter.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/definitions_simcenter_btn_simpl_chinese.txt` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **帮助(H)**。
2. 在展开项中选择 **NX 帮助(H)...**（命令 ID：`UG_HELP_HTML_DOC`）。
3. 按对话框提示操作：显示 NX 帮助库的目录，其中包含指向每个应用模块或软件区域的链接。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：显示 NX 帮助库的目录，其中包含指向每个应用模块或软件区域的链接。
    - 检索同义词：documentation

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.48 功能点：加工论坛  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_HELP_MANUFACTURING_FORUM`
- **菜单路径**：帮助(H) › PLM 社区论坛 › 加工论坛(M)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **来源提示**：`ug_styler_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_styler_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **帮助(H) › PLM 社区论坛**。
2. 在展开项中选择 **加工论坛(M)**（命令 ID：`UG_HELP_MANUFACTURING_FORUM`）。
3. 按对话框提示操作：访问 NX 加工的在线用户社区论坛。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：访问 NX 加工的在线用户社区论坛。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.49 功能点：获取 WebKey 帐户  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_HELP_OBTAIN_WEBKEY`
- **菜单路径**：帮助(H) › 在线技术支持(O) › 获取 WebKey 帐户
- **定义来源**：`UGII/menus/definitions_main.btn`
- **来源提示**：`ug_styler_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_styler_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **帮助(H) › 在线技术支持(O)**。
2. 在展开项中选择 **获取 WebKey 帐户**（命令 ID：`UG_HELP_OBTAIN_WEBKEY`）。
3. 按对话框提示操作：申请一个 WebKey 帐户，通过该帐户可访问 http://support.ugs.com 上提供的 Web 工具和服务。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：申请一个 WebKey 帐户，通过该帐户可访问 http://support.ugs.com 上提供的 Web 工具和服务。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.50 功能点：上下文帮助  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_HELP_ON_CONTEXT`
- **菜单路径**：帮助(H) › 上下文帮助(C)...
- **快捷键**：`F1`
- **定义来源**：`UGII/menus/definitions_main.btn`
- **来源提示**：`ug_styler_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 12 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_styler_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **帮助(H)**。
2. 在展开项中选择 **上下文帮助(C)...**（命令 ID：`UG_HELP_ON_CONTEXT`）。
3. 可直接使用快捷键 **F1** 调用（该快捷键来自介质 `.btn` 定义）。
4. 按对话框提示操作：显示上下文相关帮助。
5. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：显示上下文相关帮助。
    - 检索同义词：documentation, F1

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.51 功能点：PLM 社区论坛  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_HELP_PLM_COMMUNITY_FORUMS`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_te.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「PLM 社区论坛」定位。
2. 按对话框提示操作：可访问 PLM 社区论坛。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：可访问 PLM 社区论坛。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.52 功能点：发行说明  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_HELP_REL_NOTES`
- **菜单路径**：帮助(H) › 发行说明(R)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **来源提示**：`ug_styler_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_styler_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **帮助(H)**。
2. 在展开项中选择 **发行说明(R)...**（命令 ID：`UG_HELP_REL_NOTES`）。
3. 按对话框提示操作：显示最新版的发行说明。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：显示最新版的发行说明。
    - 检索同义词：caveats

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.53 功能点：通过技术支持记录事件  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_HELP_REQUEST_GTAC_SUP`
- **菜单路径**：帮助(H) › 在线技术支持(O) › 通过技术支持记录事件(L)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **来源提示**：`ug_styler_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_styler_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **帮助(H) › 在线技术支持(O)**。
2. 在展开项中选择 **通过技术支持记录事件(L)**（命令 ID：`UG_HELP_REQUEST_GTAC_SUP`）。
3. 按对话框提示操作：通过全球技术支持中心 (GTAC) 打开事件报告 (IR)。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：通过全球技术支持中心 (GTAC) 打开事件报告 (IR)。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.54 功能点：许可证调用  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_HELP_RETRIEVE_LICENSE`
- **菜单路径**：帮助(H) › 在线技术支持(O) › 许可证调用(R)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **来源提示**：`ug_styler_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_styler_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **帮助(H) › 在线技术支持(O)**。
2. 在展开项中选择 **许可证调用(R)**（命令 ID：`UG_HELP_RETRIEVE_LICENSE`）。
3. 按对话框提示操作：获取许可证文件的电子副本，或获取产品密码，这是运行许可软件所必需或要求的。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：获取许可证文件的电子副本，或获取产品密码，这是运行许可软件所必需或要求的。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.55 功能点：仿真论坛  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_HELP_SIMULATION_FORUM`
- **菜单路径**：帮助(H) › PLM 社区论坛 › 仿真论坛(S)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **来源提示**：`definitions_simcenter.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/definitions_simcenter_btn_simpl_chinese.txt` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **帮助(H) › PLM 社区论坛**。
2. 在展开项中选择 **仿真论坛(S)**（命令 ID：`UG_HELP_SIMULATION_FORUM`）。
3. 按对话框提示操作：访问 NX 仿真的在线用户社区论坛。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：访问 NX 仿真的在线用户社区论坛。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.56 功能点：日志文件  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_HELP_SYSTEM_LOG`
- **菜单路径**：帮助(H) › 日志文件(L)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **来源提示**：`ug_styler_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 13 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_styler_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **帮助(H)**。
2. 在展开项中选择 **日志文件(L)**（命令 ID：`UG_HELP_SYSTEM_LOG`）。
3. 按对话框提示操作：列出系统日志文件。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出系统日志文件。
    - 检索同义词：syslog, GTAC

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.57 功能点：在线技术支持(O)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_HELP_TEC_SUPPORT`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_te.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「在线技术支持(O)」定位。
2. 按对话框提示操作：列出“在线技术支持”命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出“在线技术支持”命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.58 功能点：PLM Solutions 症状/解决方案数据库  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_HELP_UGANSWER_DB`
- **菜单路径**：帮助(H) › 在线技术支持(O) › PLM Solutions 症状/解决方案数据库
- **定义来源**：`UGII/menus/definitions_main.btn`
- **来源提示**：`ug_styler_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_styler_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **帮助(H) › 在线技术支持(O)**。
2. 在展开项中选择 **PLM Solutions 症状/解决方案数据库**（命令 ID：`UG_HELP_UGANSWER_DB`）。
3. 按对话框提示操作：查询全球技术支持中心 (GTAC) 的症状/解决方案数据库。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：查询全球技术支持中心 (GTAC) 的症状/解决方案数据库。
    - 检索同义词：800 number, assistance

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.59 功能点：上传文件到技术支持  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_HELP_UPLOAD_FILE`
- **菜单路径**：帮助(H) › 在线技术支持(O) › 上传文件到技术支持(U)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **来源提示**：`ug_styler_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_styler_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **帮助(H) › 在线技术支持(O)**。
2. 在展开项中选择 **上传文件到技术支持(U)**（命令 ID：`UG_HELP_UPLOAD_FILE`）。
3. 按对话框提示操作：将事件报告 (IR) 的相关数据上传到技术支持文件服务器。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将事件报告 (IR) 的相关数据上传到技术支持文件服务器。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.60 功能点：基于 Web 的文档  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_HELP_WEB_BASED_DOC`
- **菜单路径**：帮助(H) › 在线技术支持(O) › 基于 Web 的文档
- **定义来源**：`UGII/menus/definitions_main.btn`
- **来源提示**：`ug_styler_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_styler_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **帮助(H) › 在线技术支持(O)**。
2. 在展开项中选择 **基于 Web 的文档**（命令 ID：`UG_HELP_WEB_BASED_DOC`）。
3. 按对话框提示操作：访问联机支持和产品文档。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：访问联机支持和产品文档。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.61 功能点：新增功能指南  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_HELP_WHATS_NEW`
- **菜单路径**：帮助(H) › 新增功能指南(W)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **来源提示**：`ug_styler_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_styler_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **帮助(H)**。
2. 在展开项中选择 **新增功能指南(W)...**（命令 ID：`UG_HELP_WHATS_NEW`）。
3. 按对话框提示操作：显示当前版本的新增功能指南。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：显示当前版本的新增功能指南。
    - 检索同义词：help

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.62 功能点：信息(I)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_INFO`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 9 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_te.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「信息(I)」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.63 功能点：分析(L)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_INFO_ANALYSIS`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 9 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_te.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「分析(L)」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.64 功能点：曲线(C)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_INFO_ANALYSIS_CURVE`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 7 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_te.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「曲线(C)」定位。
2. 按对话框提示操作：列出“曲线分析”命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出“曲线分析”命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.65 功能点：表达式(X)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_INFO_EXPRESSION`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 4 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_te.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「表达式(X)」定位。
2. 按对话框提示操作：列出“表达式信息”命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出“表达式信息”命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.66 功能点：部件(R)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_INFO_PART`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 2 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_te.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「部件(R)」定位。
2. 按对话框提示操作：列出“部件信息”命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出“部件信息”命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.67 功能点：插入(S)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_INSERT`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 8 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_te.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「插入(S)」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.68 功能点：部件间更新(I)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_INTERPART_UPDATES`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 3 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_te.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「部件间更新(I)」定位。
2. 按对话框提示操作：列出“部件间更新”命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出“部件间更新”命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.69 功能点：操作记录(J)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_JOURNAL`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_te.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「操作记录(J)」定位。
2. 按对话框提示操作：列出“操作记录”命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出“操作记录”命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.70 功能点：插入(I)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_JOURNAL_INSERT`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_te.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「插入(I)」定位。
2. 按对话框提示操作：列出“操作记录 - 插入”命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出“操作记录 - 插入”命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.71 功能点：宏(R)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_MACRO`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_te.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「宏(R)」定位。
2. 按对话框提示操作：列出“宏”命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出“宏”命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.72 功能点：定制菜单栏(C)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_MENUBAR_REPORT`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 3 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_te.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「定制菜单栏(C)」定位。
2. 按对话框提示操作：列出“定制菜单栏”命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出“定制菜单栏”命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.73 功能点：电影(E)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_MOVIE_CREATION`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 9 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_te.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「电影(E)」定位。
2. 按对话框提示操作：列出“电影”命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出“电影”命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.74 功能点：尺寸(D)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_PMI_CRE_DIMENSIONS`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`UGII/menus/ug_main.men`
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `UGII/menus/ug_main.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「尺寸(D)」定位。
2. 按对话框提示操作：列出“PMI 尺寸”命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出“PMI 尺寸”命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.75 功能点：安全标记(K)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_PMI_EMARKING`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`UGII/menus/ug_main.men`
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `UGII/menus/ug_main.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「安全标记(K)」定位。
2. 按对话框提示操作：列出“PMI 安全标记”命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出“PMI 安全标记”命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.76 功能点：专用(Z)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_PMI_SPECIALIZED`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`UGII/menus/ug_main.men`
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `UGII/menus/ug_main.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「专用(Z)」定位。
2. 按对话框提示操作：列出“专用 PMI”命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出“专用 PMI”命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.77 功能点：补充几何信息(G)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_PMI_SUPPLEMENTAL_GEOMETRY`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`UGII/menus/ug_main.men`
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `UGII/menus/ug_main.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「补充几何信息(G)」定位。
2. 按对话框提示操作：列出“补充 PMI 几何体”命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出“补充 PMI 几何体”命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.78 功能点：符号(Y)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_PMI_SYMBOLS`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`UGII/menus/ug_main.men`
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `UGII/menus/ug_main.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「符号(Y)」定位。
2. 按对话框提示操作：列出“PMI 符号”命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出“PMI 符号”命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.79 功能点：选择(L)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_SELECTION`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_te.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「选择(L)」定位。
2. 按对话框提示操作：列出“选择”命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出“选择”命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.80 功能点：表(B)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_TABLE`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_title_block.men` 等 2 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_title_block.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「表(B)」定位。
2. 按对话框提示操作：列出“编辑表”命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出“编辑表”命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.81 功能点：标注(C)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_TABLE_CALLOUT`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`UGII/menus/ug_main.men`
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `UGII/menus/ug_main.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「标注(C)」定位。
2. 按对话框提示操作：列出“标注分组”命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出“标注分组”命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.82 功能点：导入(P)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_TABLE_IMPORT`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_title_block.men` 等 2 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_title_block.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「导入(P)」定位。
2. 按对话框提示操作：列出“表 - 导入”命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出“表 - 导入”命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.83 功能点：插入(I)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_TABLE_INSERT`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_title_block.men` 等 2 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_title_block.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「插入(I)」定位。
2. 按对话框提示操作：列出“表 - 插入”命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出“表 - 插入”命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.84 功能点：列(C)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_TABLE_INSERT_COLS`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_title_block.men` 等 2 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_title_block.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「列(C)」定位。
2. 按对话框提示操作：列出“表 - 插入列”命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出“表 - 插入列”命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.85 功能点：行(R)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_TABLE_INSERT_ROWS`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_title_block.men` 等 2 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_title_block.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「行(R)」定位。
2. 按对话框提示操作：列出“表 - 插入行”命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出“表 - 插入行”命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.86 功能点：选择(S)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_TABLE_SELECT`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_title_block.men` 等 2 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_title_block.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「选择(S)」定位。
2. 按对话框提示操作：列出“表 - 选择”命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出“表 - 选择”命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.87 功能点：工具(T)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_TOOLBOX`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 12 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_te.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「工具(T)」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.88 功能点：部件中单位信息  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TOOLBOX_UNITS_IN_PART_INFORMATION`
- **菜单路径**：信息(I) › 部件中单位信息(P)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **来源提示**：`definitions_simcenter.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 5 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/definitions_simcenter_btn_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **信息(I)**。
2. 在展开项中选择 **部件中单位信息(P)**（命令 ID：`UG_TOOLBOX_UNITS_IN_PART_INFORMATION`）。
3. 按对话框提示操作：列出部件中存在的单位。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出部件中存在的单位。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.89 功能点：重复命令(R)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_TOOLS_REPEAT_MENU`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 12 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_te.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「重复命令(R)」定位。
2. 按对话框提示操作：列出上次使用的命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出上次使用的命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.90 功能点：更新(U)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_UPDATES`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 4 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_te.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「更新(U)」定位。
2. 按对话框提示操作：列出“更新”命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出“更新”命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.91 功能点：视图(V)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_VIEW`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 13 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_te.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「视图(V)」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.92 功能点：操作(O)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_VIEW_EDIT`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_te.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「操作(O)」定位。
2. 按对话框提示操作：列出“视图操作”命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出“视图操作”命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.93 功能点：停靠功能区  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_VIEW_RIBBON_DOCK`
- **菜单路径**：视图(V) › 停靠功能区(B)
- **来源提示**：`ug_styler_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 12 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_styler_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **视图(V)**。
2. 在展开项中选择 **停靠功能区(B)**（命令 ID：`UG_VIEW_RIBBON_DOCK`）。
3. 按对话框提示操作：此命令在功能区取消停靠时可用。也可通过在功能区的空白区调用快捷菜单来停靠/取消停靠功能区。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：此命令在功能区取消停靠时可用。也可通过在功能区的空白区调用快捷菜单来停靠/取消停靠功能区。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.94 功能点：最小化功能区  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_VIEW_RIBBON_MINIMIZED`
- **菜单路径**：视图(V) › 最小化功能区(Z)
- **来源提示**：`ug_styler_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 13 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_styler_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **视图(V)**。
2. 在展开项中选择 **最小化功能区(Z)**（命令 ID：`UG_VIEW_RIBBON_MINIMIZED`）。
3. 按对话框提示操作：最小化功能区以仅显示选项卡名称。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：最小化功能区以仅显示选项卡名称。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.95 功能点：截面(S)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_VIEW_SECTION`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_te.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「截面(S)」定位。
2. 按对话框提示操作：列出“视图剖切”命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出“视图剖切”命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 1.96 功能点：窗口(O)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_WINDOW`
- **来源提示**：`ug_main_simcenter.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 8 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_main_simcenter_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_te.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「窗口(O)」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 2. 子模块：制图/PMI

本子模块 86 个功能点。

### 2.1 功能点：CN_DIM_INHERIT_STYLE_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_DIM_INHERIT_STYLE_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_DIM_INHERIT_STYLE_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.2 功能点：CN_DIM_QUERY_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_DIM_QUERY_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_DIM_QUERY_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.3 功能点：CN_DIM_RESET_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_DIM_RESET_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_DIM_RESET_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.4 功能点：CN_DIM_TOL_FIT_QUERY_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_DIM_TOL_FIT_QUERY_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_DIM_TOL_FIT_QUERY_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.5 功能点：CN_DRAFT_ARROW_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_DRAFT_ARROW_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_DRAFT_ARROW_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.6 功能点：CN_DRAFT_CALLOUT_SORT_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_DRAFT_CALLOUT_SORT_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_DRAFT_CALLOUT_SORT_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.7 功能点：CN_DRAFT_CHECK_TABLE_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_DRAFT_CHECK_TABLE_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_DRAFT_CHECK_TABLE_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.8 功能点：CN_DRAFT_COORDINATE_TABLE  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_DRAFT_COORDINATE_TABLE`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_DRAFT_COORDINATE_TABLE」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.9 功能点：CN_DRAFT_CURVE_SECTION_VIEW_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_DRAFT_CURVE_SECTION_VIEW_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_DRAFT_CURVE_SECTION_VIEW_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.10 功能点：CN_DRAFT_DART_SECTION_VIEW_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_DRAFT_DART_SECTION_VIEW_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_DRAFT_DART_SECTION_VIEW_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.11 功能点：CN_DRAFT_DIM_NOTE_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_DRAFT_DIM_NOTE_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_DRAFT_DIM_NOTE_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.12 功能点：CN_DRAFT_DIM_SORT_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_DRAFT_DIM_SORT_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_DRAFT_DIM_SORT_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.13 功能点：CN_DRAFT_EDIT_PLIST_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_DRAFT_EDIT_PLIST_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_DRAFT_EDIT_PLIST_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.14 功能点：CN_DRAFT_EXPORT_PLIST_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_DRAFT_EXPORT_PLIST_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_DRAFT_EXPORT_PLIST_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.15 功能点：CN_DRAFT_GEAR_PARAMETERS_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_DRAFT_GEAR_PARAMETERS_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_DRAFT_GEAR_PARAMETERS_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.16 功能点：CN_DRAFT_GRID_LINE_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_DRAFT_GRID_LINE_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_DRAFT_GRID_LINE_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.17 功能点：CN_DRAFT_HOLE_SYMBOL_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_DRAFT_HOLE_SYMBOL_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_DRAFT_HOLE_SYMBOL_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.18 功能点：CN_DRAFT_MERGE_SHEET_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_DRAFT_MERGE_SHEET_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_DRAFT_MERGE_SHEET_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.19 功能点：CN_DRAFT_MUST_SYMBOL_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_DRAFT_MUST_SYMBOL_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_DRAFT_MUST_SYMBOL_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.20 功能点：CN_DRAFT_ORDDIM_ALIGNING_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_DRAFT_ORDDIM_ALIGNING_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_DRAFT_ORDDIM_ALIGNING_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.21 功能点：CN_DRAFT_PARTIAL_VIEW_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_DRAFT_PARTIAL_VIEW_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_DRAFT_PARTIAL_VIEW_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.22 功能点：CN_DRAFT_POINT_ANN_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_DRAFT_POINT_ANN_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_DRAFT_POINT_ANN_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.23 功能点：CN_DRAFT_POINT_ANN_UPDATE_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_DRAFT_POINT_ANN_UPDATE_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_DRAFT_POINT_ANN_UPDATE_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.24 功能点：CN_DRAFT_RPOJECT_CURVES_TO_VIEW_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_DRAFT_RPOJECT_CURVES_TO_VIEW_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_DRAFT_RPOJECT_CURVES_TO_VIEW_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.25 功能点：CN_DRAFT_SPRING_DRAFTING  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_DRAFT_SPRING_DRAFTING`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_DRAFT_SPRING_DRAFTING」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.26 功能点：CN_DRAFT_SYM_DIM_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_DRAFT_SYM_DIM_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_DRAFT_SYM_DIM_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.27 功能点：CN_DRAFT_TECH_NOTE_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_DRAFT_TECH_NOTE_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_DRAFT_TECH_NOTE_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.28 功能点：CN_DRAF_TEMPLATE_REPLACE_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_DRAF_TEMPLATE_REPLACE_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_DRAF_TEMPLATE_REPLACE_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.29 功能点：CN_MATCH_STYLE_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_MATCH_STYLE_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_MATCH_STYLE_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.30 功能点：GEAR_DRAFTING  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`GEAR_DRAFTING`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「GEAR_DRAFTING」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.31 功能点：MS_DRF_COORDINATE_NOTE_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MS_DRF_COORDINATE_NOTE_BTN`
- **出现菜单**：`MS_NXTOOLS/Application/ms_drafting_menu.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `MS_NXTOOLS/Application/ms_drafting_menu.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MS_DRF_COORDINATE_NOTE_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.32 功能点：MS_DRF_GRID_LINE_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MS_DRF_GRID_LINE_BTN`
- **出现菜单**：`MS_NXTOOLS/Application/ms_drafting_menu.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `MS_NXTOOLS/Application/ms_drafting_menu.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MS_DRF_GRID_LINE_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.33 功能点：MS_DRF_HOLE_NOTE_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MS_DRF_HOLE_NOTE_BTN`
- **出现菜单**：`MS_NXTOOLS/Application/ms_drafting_menu.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `MS_NXTOOLS/Application/ms_drafting_menu.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MS_DRF_HOLE_NOTE_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.34 功能点：MS_DRF_MULTIPLE_TEMPLATES_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MS_DRF_MULTIPLE_TEMPLATES_BTN`
- **出现菜单**：`MS_NXTOOLS/Application/ms_drafting_menu.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `MS_NXTOOLS/Application/ms_drafting_menu.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MS_DRF_MULTIPLE_TEMPLATES_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.35 功能点：3D 中心线  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_CRE_3D_CENTERLINE`
- **菜单路径**：插入(S) › 中心线(E) › 3D 中心线...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 中心线(E)**。
2. 在展开项中选择 **3D 中心线...**（命令 ID：`UG_DRAFT_CRE_3D_CENTERLINE`）。
3. 按对话框提示操作：基于面或曲线输入创建中心线，其中产生的中心线是真实 3D 中心线。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：基于面或曲线输入创建中心线，其中产生的中心线是真实 3D 中心线。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.36 功能点：自动中心线  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_CRE_AUTO_CENTERLINE`
- **菜单路径**：插入(S) › 中心线(E) › 自动(A)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 中心线(E)**。
2. 在展开项中选择 **自动(A)...**（命令 ID：`UG_DRAFT_CRE_AUTO_CENTERLINE`）。
3. 按对话框提示操作：自动创建中心标记、圆形中心线和圆柱形中心线。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：自动创建中心标记、圆形中心线和圆柱形中心线。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.37 功能点：逻辑管线布置图例  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_CRE_ROUTING_LGCL_LEGEND`
- **菜单路径**：工具(T) › 管线布置(G) › 逻辑图例(L)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 管线布置(G)**。
2. 在展开项中选择 **逻辑图例(L)...**（命令 ID：`UG_DRAFT_CRE_ROUTING_LGCL_LEGEND`）。
3. 按对话框提示操作：创建一个表格注释，这将列出图纸页中的所有组件。每个组件均映射至一个符号线型和说明。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建一个表格注释，这将列出图纸页中的所有组件。每个组件均映射至一个符号线型和说明。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.38 功能点：表格注释  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_CRE_TABULAR_NOTE`
- **菜单路径**：插入(S) › 表(B) › 表格注释(T)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 表(B)**。
2. 在展开项中选择 **表格注释(T)...**（命令 ID：`UG_DRAFT_CRE_TABULAR_NOTE`）。
3. 按对话框提示操作：创建信息表。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建信息表。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.39 功能点：用户定义符号  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_CRE_USER_DEF_SYMBOLS`
- **菜单路径**：插入(S) › 符号(Y) › 用户定义(D)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 符号(Y)**。
2. 在展开项中选择 **用户定义(D)...**（命令 ID：`UG_DRAFT_CRE_USER_DEF_SYMBOLS`）。
3. 按对话框提示操作：创建用户定义的符号实例（由 NX 提供或使用“文件 -> 实用工具 -> 符号线型”创建）。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建用户定义的符号实例（由 NX 提供或使用“文件 -> 实用工具 -> 符号线型”创建）。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.40 功能点：定义定制符号  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_DEFINE_SYMBOL`
- **菜单路径**：插入(S) › 符号(Y) › 定义定制符号(E)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 符号(Y)**。
2. 在展开项中选择 **定义定制符号(E)...**（命令 ID：`UG_DRAFT_DEFINE_SYMBOL`）。
3. 按对话框提示操作：定义定制符号。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：定义定制符号。
    - 检索同义词：store a symbol, user-defined weld symbol

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.41 功能点：坐标尺寸  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_DIMENSION_ORDINATE`
- **菜单路径**：插入(S) › 尺寸(M) › 坐标(O)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 尺寸(M)**。
2. 在展开项中选择 **坐标(O)...**（命令 ID：`UG_DRAFT_DIMENSION_ORDINATE`）。
3. 按对话框提示操作：创建坐标尺寸，测量从公共点沿一条坐标基线到某一对象上位置的距离。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建坐标尺寸，测量从公共点沿一条坐标基线到某一对象上位置的距离。
    - 检索同义词：create ordinate dimensions

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.42 功能点：向区域添加符号  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_DRAWING_FORMAT_ADDOBJTOREGION`
- **菜单路径**：工具(T) › 图纸格式(W) › 向区域添加符号(S)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 图纸格式(W)**。
2. 在展开项中选择 **向区域添加符号(S)...**（命令 ID：`UG_DRAFT_DRAWING_FORMAT_ADDOBJTOREGION`）。
3. 按对话框提示操作：向模板区域添加重用库中的定制符号。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：向模板区域添加重用库中的定制符号。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.43 功能点：边界和区域  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_DRAWING_FORMAT_BORDER_ZONES`
- **菜单路径**：工具(T) › 图纸格式(W) › 边界和区域(B)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 图纸格式(W)**。
2. 在展开项中选择 **边界和区域(B)...**（命令 ID：`UG_DRAFT_DRAWING_FORMAT_BORDER_ZONES`）。
3. 按对话框提示操作：创建图纸页边界和区域。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建图纸页边界和区域。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.44 功能点：标记为模板  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_DRAWING_FORMAT_MARKASTEMPLATE`
- **菜单路径**：工具(T) › 图纸格式(W) › 标记为模板(M)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 图纸格式(W)**。
2. 在展开项中选择 **标记为模板(M)...**（命令 ID：`UG_DRAFT_DRAWING_FORMAT_MARKASTEMPLATE`）。
3. 按对话框提示操作：将当前部件标记为图纸模板部件并捕捉输入以更新 PAX 文件。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将当前部件标记为图纸模板部件并捕捉输入以更新 PAX 文件。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.45 功能点：模板区域  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_DRAWING_FORMAT_REGION`
- **菜单路径**：工具(T) › 图纸格式(W) › 模板区域(T)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 图纸格式(W)**。
2. 在展开项中选择 **模板区域(T)...**（命令 ID：`UG_DRAFT_DRAWING_FORMAT_REGION`）。
3. 按对话框提示操作：创建模板区域，用于控制注释、定制符号、表格或视图的创建。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建模板区域，用于控制注释、定制符号、表格或视图的创建。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.46 功能点：自动化规则  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_DRAWING_FORMAT_RULE`
- **菜单路径**：工具(T) › 图纸格式(W) › 自动化规则(A)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 图纸格式(W)**。
2. 在展开项中选择 **自动化规则(A)...**（命令 ID：`UG_DRAFT_DRAWING_FORMAT_RULE`）。
3. 按对话框提示操作：定义规则以在模板实例化后创建制图对象。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：定义规则以在模板实例化后创建制图对象。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.47 功能点：定义标题块  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_DRAWING_FORMAT_TITLEBLOCK`
- **菜单路径**：工具(T) › 图纸格式(W) › 定义标题块(D)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 图纸格式(W)**。
2. 在展开项中选择 **定义标题块(D)...**（命令 ID：`UG_DRAFT_DRAWING_FORMAT_TITLEBLOCK`）。
3. 按对话框提示操作：定义一个标题块模板。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：定义一个标题块模板。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.48 功能点：填充标题块  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_DRAWING_FORMAT_TITLE_BLOCK_POPULATE`
- **菜单路径**：工具(T) › 图纸格式(W) › 填充标题块(P)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 图纸格式(W)**。
2. 在展开项中选择 **填充标题块(P)...**（命令 ID：`UG_DRAFT_DRAWING_FORMAT_TITLE_BLOCK_POPULATE`）。
3. 按对话框提示操作：修改当前图纸部件中所有标题块的单元格值。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：修改当前图纸部件中所有标题块的单元格值。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.49 功能点：对齐视图  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_DRW_ALIGN`
- **菜单路径**：编辑(E) › 视图(W) › 对齐(A)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 视图(W)**。
2. 在展开项中选择 **对齐(A)...**（命令 ID：`UG_DRAFT_DRW_ALIGN`）。
3. 按对话框提示操作：使图纸页上的视图对齐。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：使图纸页上的视图对齐。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.50 功能点：自动符号标注  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_DRW_AUTOBALLOON_VIEW`
- **菜单路径**：编辑(E) › 视图(W) › 自动符号标注(O)
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 视图(W)**。
2. 在展开项中选择 **自动符号标注(O)**（命令 ID：`UG_DRAFT_DRW_AUTOBALLOON_VIEW`）。
3. 按对话框提示操作：为零件明细表创建关联的圆形符号。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：为零件明细表创建关联的圆形符号。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.51 功能点：局部剖视图  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_DRW_BREAKOUT`
- **菜单路径**：插入(S) › 视图(W) › 局部剖(O)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 视图(W)**。
2. 在展开项中选择 **局部剖(O)...**（命令 ID：`UG_DRAFT_DRW_BREAKOUT`）。
3. 按对话框提示操作：通过在任何父图纸视图中移除一个部件区域来创建一个局部剖视图。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：通过在任何父图纸视图中移除一个部件区域来创建一个局部剖视图。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.52 功能点：断开视图  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_DRW_BROKEN_VIEW`
- **菜单路径**：插入(S) › 视图(W) › 断开视图(K)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 视图(W)**。
2. 在展开项中选择 **断开视图(K)...**（命令 ID：`UG_DRAFT_DRW_BROKEN_VIEW`）。
3. 按对话框提示操作：创建用于将一个视图分为多个边界的断裂线。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建用于将一个视图分为多个边界的断裂线。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.53 功能点：视图边界  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_DRW_DEFINE_BOUNDARY`
- **菜单路径**：编辑(E) › 视图(W) › 边界(B)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 视图(W)**。
2. 在展开项中选择 **边界(B)...**（命令 ID：`UG_DRAFT_DRW_DEFINE_BOUNDARY`）。
3. 按对话框提示操作：编辑图纸页上某一视图的视图边界。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：编辑图纸页上某一视图的视图边界。
    - 检索同义词：border, setting the size of a drawing view

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.54 功能点：局部放大图  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_DRW_DETAIL_VIEW`
- **菜单路径**：插入(S) › 视图(W) › 局部放大图(D)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 视图(W)**。
2. 在展开项中选择 **局部放大图(D)...**（命令 ID：`UG_DRAFT_DRW_DETAIL_VIEW`）。
3. 按对话框提示操作：创建一个包含图纸视图放大部分的视图。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建一个包含图纸视图放大部分的视图。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.55 功能点：图纸视图  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_DRW_DRAWING_VIEW`
- **菜单路径**：插入(S) › 视图(W) › 图纸(W)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 视图(W)**。
2. 在展开项中选择 **图纸(W)...**（命令 ID：`UG_DRAFT_DRW_DRAWING_VIEW`）。
3. 按对话框提示操作：在图纸页上创建一个空视图（以创建草图和视图相关的对象）。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在图纸页上创建一个空视图（以创建草图和视图相关的对象）。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.56 功能点：基本视图  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_DRW_IMPORT_VIEW`
- **菜单路径**：插入(S) › 视图(W) › 基本(B)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 视图(W)**。
2. 在展开项中选择 **基本(B)...**（命令 ID：`UG_DRAFT_DRW_IMPORT_VIEW`）。
3. 按对话框提示操作：在图纸页上创建基于模型的视图。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在图纸页上创建基于模型的视图。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.57 功能点：移动/复制视图  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_DRW_MOVE`
- **菜单路径**：编辑(E) › 视图(W) › 移动/复制(Y)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 视图(W)**。
2. 在展开项中选择 **移动/复制(Y)...**（命令 ID：`UG_DRAFT_DRW_MOVE`）。
3. 按对话框提示操作：将视图移动或复制到另一个图纸页上。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将视图移动或复制到另一个图纸页上。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.58 功能点：移至新视图  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_DRW_MOVE_TO_DRAWING_VIEW`
- **菜单路径**：编辑(E) › 视图(W) › 移至新视图(N)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 视图(W)**。
2. 在展开项中选择 **移至新视图(N)...**（命令 ID：`UG_DRAFT_DRW_MOVE_TO_DRAWING_VIEW`）。
3. 按对话框提示操作：根据图纸页上的对象创建新的图纸视图。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：根据图纸页上的对象创建新的图纸视图。
    - 可用性提示：This command is available only with the NX Layout license.
    - 检索同义词：move, drawing view

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.59 功能点：断开（原）(E)...  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_DRW_OLD_BROKEN_VIEW`
- **菜单路径**：插入(S) › 视图(W) › 断开（原）(E)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 视图(W)**。
2. 在展开项中选择 **断开（原）(E)...**（命令 ID：`UG_DRAFT_DRW_OLD_BROKEN_VIEW`）。
3. 按对话框提示操作：将图纸视图分解成多个边界并进行压缩，从而隐藏不感兴趣的部件部分，以此来减小图纸视图的大小。这是原有的“断开视图”命令。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将图纸视图分解成多个边界并进行压缩，从而隐藏不感兴趣的部件部分，以此来减小图纸视图的大小。这是原有的“断开视图”命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.60 功能点：半轴测剖视图  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_DRW_PICTORIAL_HALF_SECTION_VIEW`
- **菜单路径**：插入(S) › 视图(W) › 半轴测剖(I)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 视图(W)**。
2. 在展开项中选择 **半轴测剖(I)...**（命令 ID：`UG_DRAFT_DRW_PICTORIAL_HALF_SECTION_VIEW`）。
3. 按对话框提示操作：从任何父图纸视图创建一个基于轴测（3D）视图的半剖视图。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：从任何父图纸视图创建一个基于轴测（3D）视图的半剖视图。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.61 功能点：轴测剖视图  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_DRW_PICTORIAL_SECTION_VIEW`
- **菜单路径**：插入(S) › 视图(W) › 轴测剖(P)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 视图(W)**。
2. 在展开项中选择 **轴测剖(P)...**（命令 ID：`UG_DRAFT_DRW_PICTORIAL_SECTION_VIEW`）。
3. 按对话框提示操作：从任何父图纸视图创建一个基于轴测（3D）视图的剖视图。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：从任何父图纸视图创建一个基于轴测（3D）视图的剖视图。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.62 功能点：投影视图  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_DRW_PROJECT_VIEW`
- **菜单路径**：插入(S) › 视图(W) › 投影(J)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 视图(W)**。
2. 在展开项中选择 **投影(J)...**（命令 ID：`UG_DRAFT_DRW_PROJECT_VIEW`）。
3. 按对话框提示操作：从任何父图纸视图创建投影正交或辅助视图。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：从任何父图纸视图创建投影正交或辅助视图。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.63 功能点：视图中的次要几何元素  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_DRW_SECONDARY_GEOMETRY_IN_VIEW`
- **菜单路径**：编辑(E) › 视图(W) › 视图中的次要几何元素(G)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 视图(W)**。
2. 在展开项中选择 **视图中的次要几何元素(G)...**（命令 ID：`UG_DRAFT_DRW_SECONDARY_GEOMETRY_IN_VIEW`）。
3. 按对话框提示操作：重新定义或更新选定视图的次要几何元素规格。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：重新定义或更新选定视图的次要几何元素规格。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.64 功能点：剖切线  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_DRW_SECTION_LINE`
- **菜单路径**：插入(S) › 视图(W) › 剖切线(L)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 视图(W)**。
2. 在展开项中选择 **剖切线(L)...**（命令 ID：`UG_DRAFT_DRW_SECTION_LINE`）。
3. 按对话框提示操作：创建基于草图的、独立的剖切线，以用于创建派生自 PMI 切割平面符号的剖视图或剖切线。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建基于草图的、独立的剖切线，以用于创建派生自 PMI 切割平面符号的剖视图或剖切线。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.65 功能点：剖视图  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_DRW_SECTION_VIEW`
- **菜单路径**：插入(S) › 视图(W) › 剖视图(S)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 视图(W)**。
2. 在展开项中选择 **剖视图(S)...**（命令 ID：`UG_DRAFT_DRW_SECTION_VIEW`）。
3. 按对话框提示操作：从任何父图纸视图创建剖视图。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：从任何父图纸视图创建剖视图。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.66 功能点：定向剖视图  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_DRW_SIMPLE_3D_SECTION_VIEW`
- **菜单路径**：插入(S) › 视图(W) › 定向剖(T)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 视图(W)**。
2. 在展开项中选择 **定向剖(T)...**（命令 ID：`UG_DRAFT_DRW_SIMPLE_3D_SECTION_VIEW`）。
3. 按对话框提示操作：通过指定切割方位和位置来创建剖视图。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：通过指定切割方位和位置来创建剖视图。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.67 功能点：标准视图  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_DRW_STANDARD_VIEWS`
- **菜单路径**：插入(S) › 视图(W) › 标准(A)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 视图(W)**。
2. 在展开项中选择 **标准(A)...**（命令 ID：`UG_DRAFT_DRW_STANDARD_VIEWS`）。
3. 按对话框提示操作：在图纸页上创建具有标准方位的多个视图。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在图纸页上创建具有标准方位的多个视图。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.68 功能点：展开的点和角度剖视图  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_DRW_UNFOLDED_ANGLE_SECTION_VIEW`
- **菜单路径**：插入(S) › 视图(W) › 展开的点和角度剖(N)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 视图(W)**。
2. 在展开项中选择 **展开的点和角度剖(N)...**（命令 ID：`UG_DRAFT_DRW_UNFOLDED_ANGLE_SECTION_VIEW`）。
3. 按对话框提示操作：通过指定截面线段的位置和角度创建剖视图。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：通过指定截面线段的位置和角度创建剖视图。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.69 功能点：更新视图  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_DRW_UPDATE_VIEW`
- **菜单路径**：编辑(E) › 视图(W) › 更新(U)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 视图(W)**。
2. 在展开项中选择 **更新(U)...**（命令 ID：`UG_DRAFT_DRW_UPDATE_VIEW`）。
3. 按对话框提示操作：在选定视图中更新视图内容。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在选定视图中更新视图内容。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.70 功能点：视图对齐  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_DRW_VIEW_ALIGNMENT`
- **菜单路径**：编辑(E) › 视图(W) › 对齐(I)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 视图(W)**。
2. 在展开项中选择 **对齐(I)...**（命令 ID：`UG_DRAFT_DRW_VIEW_ALIGNMENT`）。
3. 按对话框提示操作：在视图之间创建永久对齐。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在视图之间创建永久对齐。
    - 检索同义词：associative alignment, view placement, view origin, align view, align a view, moving views

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.71 功能点：视图创建向导  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_DRW_VIEW_CREATION_WIZARD`
- **菜单路径**：插入(S) › 视图(W) › 视图创建向导(Z)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 视图(W)**。
2. 在展开项中选择 **视图创建向导(Z)...**（命令 ID：`UG_DRAFT_DRW_VIEW_CREATION_WIZARD`）。
3. 按对话框提示操作：对图纸页添加一个或多个视图。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：对图纸页添加一个或多个视图。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.72 功能点：视图中剖切  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_EDIT_SECTION_COMPONENTS`
- **菜单路径**：编辑(E) › 视图(W) › 视图中剖切(C)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 视图(W)**。
2. 在展开项中选择 **视图中剖切(C)...**（命令 ID：`UG_DRAFT_EDIT_SECTION_COMPONENTS`）。
3. 按对话框提示操作：设置图纸页中视图内装配组件或实体的剖切属性（剖切或非剖切）。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：设置图纸页中视图内装配组件或实体的剖切属性（剖切或非剖切）。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.73 功能点：视图相关编辑  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_EDIT_VIEW_DEPENDENT`
- **菜单路径**：编辑(E) › 视图(W) › 视图相关编辑(E)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 视图(W)**。
2. 在展开项中选择 **视图相关编辑(E)...**（命令 ID：`UG_DRAFT_EDIT_VIEW_DEPENDENT`）。
3. 按对话框提示操作：编辑视图中对象的显示，同时不影响其他视图中同一对象的显示。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：编辑视图中对象的显示，同时不影响其他视图中同一对象的显示。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.74 功能点：视图设置  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_EDIT_VIEW_STYLE`
- **菜单路径**：编辑(E) › 视图(W) › 设置(S)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 视图(W)**。
2. 在展开项中选择 **设置(S)...**（命令 ID：`UG_DRAFT_EDIT_VIEW_STYLE`）。
3. 按对话框提示操作：编辑图纸页视图的设置。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：编辑图纸页视图的设置。
    - 检索同义词：view properties, view appearance, show edge, hide edge, hidden line

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.75 功能点：特征参数  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_MODEL_FEATURE`
- **菜单路径**：插入(S) › 尺寸(M) › 特征参数(A)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 尺寸(M)**。
2. 在展开项中选择 **特征参数(A)...**（命令 ID：`UG_DRAFT_MODEL_FEATURE`）。
3. 按对话框提示操作：将孔和螺纹参数（以标注的形式）或草图尺寸继承到图纸页。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将孔和螺纹参数（以标注的形式）或草图尺寸继承到图纸页。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 特征类命令注意参数关联性；修改后需重算并检查特征导航器是否报错。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.76 功能点：形位公差参数  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_MODEL_GDT`
- **菜单路径**：插入(S) › 尺寸(M) › 形位公差参数(G)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 尺寸(M)**。
2. 在展开项中选择 **形位公差参数(G)...**（命令 ID：`UG_DRAFT_MODEL_GDT`）。
3. 按对话框提示操作：将几何体公差显示实例继承到图纸页。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将几何体公差显示实例继承到图纸页。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.77 功能点：优化显示  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_REFINE_DISPLAY`
- **菜单路径**：编辑(E) › 视图(W) › 优化显示(F)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 视图(W)**。
2. 在展开项中选择 **优化显示(F)...**（命令 ID：`UG_DRAFT_REFINE_DISPLAY`）。
3. 按对话框提示操作：优化轻量级图纸视图中某个区域的显示。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：优化轻量级图纸视图中某个区域的显示。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.78 功能点：设置(S)...  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_SECTION_LINE_SETTINGS`
- **菜单路径**：编辑(E) › 视图(W) › 设置(S)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 视图(W)**。
2. 在展开项中选择 **设置(S)...**（命令 ID：`UG_DRAFT_SECTION_LINE_SETTINGS`）。
3. 按对话框提示操作：设置定义新截面线显示的设置。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：设置定义新截面线显示的设置。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.79 功能点：打散视图  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_SMASH_VIEW`
- **菜单路径**：编辑(E) › 视图(W) › 打散视图(W)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 视图(W)**。
2. 在展开项中选择 **打散视图(W)...**（命令 ID：`UG_DRAFT_SMASH_VIEW`）。
3. 按对话框提示操作：将图纸视图在图纸页上分解为其构成片段。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将图纸视图在图纸页上分解为其构成片段。
    - 可用性提示：This command is available only with the NX Layout license.
    - 检索同义词：smash, view

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.80 功能点：从目录定义符号  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_SYMBOL_CATALOG`
- **菜单路径**：插入(S) › 符号(Y) › 从目录定义(G)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 符号(Y)**。
2. 在展开项中选择 **从目录定义(G)...**（命令 ID：`UG_DRAFT_SYMBOL_CATALOG`）。
3. 按对话框提示操作：按目录模板定义定制符号。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：按目录模板定义定制符号。
    - 检索同义词：custom symbol, define from catalog, fastener

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.81 功能点：删除迁移数据  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_TOOLBOX_DELETE_MIGRATION_DATA`
- **菜单路径**：工具(T) › 图纸迁移(W) › 删除迁移数据(D)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 图纸迁移(W)**。
2. 在展开项中选择 **删除迁移数据(D)...**（命令 ID：`UG_DRAFT_TOOLBOX_DELETE_MIGRATION_DATA`）。
3. 按对话框提示操作：删除部件中有关迁移的信息（进一步的后处理迁移分析在此之后不能执行，且无法解决对此部件的部件间引用）。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：删除部件中有关迁移的信息（进一步的后处理迁移分析在此之后不能执行，且无法解决对此部件的部件间引用）。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.82 功能点：图纸叠加开/关  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_TOOLBOX_DWG_OVERLAY`
- **菜单路径**：工具(T) › 图纸迁移(W) › 图纸叠加开/关(O)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 图纸迁移(W)**。
2. 在展开项中选择 **图纸叠加开/关(O)...**（命令 ID：`UG_DRAFT_TOOLBOX_DWG_OVERLAY`）。
3. 按对话框提示操作：显示图纸叠加。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：显示图纸叠加。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.83 功能点：更新验证  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_VIEW_UPDATE_VALIDATION`
- **菜单路径**：编辑(E) › 视图(W) › 更新验证(P)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 视图(W)**。
2. 在展开项中选择 **更新验证(P)...**（命令 ID：`UG_DRAFT_VIEW_UPDATE_VALIDATION`）。
3. 按对话框提示操作：验证无效小平面体的轻量级图纸视图。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：验证无效小平面体的轻量级图纸视图。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.84 功能点：表格标签  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_RT_DRFT_TAB_LABEL`
- **菜单路径**：插入(S) › 表(B) › 表格标签(A)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 表(B)**。
2. 在展开项中选择 **表格标签(A)...**（命令 ID：`UG_RT_DRFT_TAB_LABEL`）。
3. 按对话框提示操作：创建表样式标签。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建表样式标签。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.85 功能点：折弯表  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_CREATE_BEND_TABLE`
- **菜单路径**：插入(S) › 表(B) › 折弯表(D)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 表(B)**。
2. 在展开项中选择 **折弯表(D)...**（命令 ID：`UG_TABLE_CREATE_BEND_TABLE`）。
3. 按对话框提示操作：从展平图样视图创建折弯表。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：从展平图样视图创建折弯表。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 2.86 功能点：孔表  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_CREATE_HOLE_TABLE`
- **菜单路径**：插入(S) › 表(B) › 孔表(H)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 表(B)**。
2. 在展开项中选择 **孔表(H)...**（命令 ID：`UG_TABLE_CREATE_HOLE_TABLE`）。
3. 按对话框提示操作：创建一个包含所选孔的大小和位置的表。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建一个包含所选孔的大小和位置的表。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 3. 子模块：drafting

本子模块 45 个功能点。

### 3.1 功能点：MEILEI2_GUI_TOOL1  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MEILEI2_GUI_TOOL1`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MEILEI2_GUI_TOOL1」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.2 功能点：MEILEI2_GUI_TOOL2  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MEILEI2_GUI_TOOL2`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MEILEI2_GUI_TOOL2」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.3 功能点：MEILEI2_GUI_TOOL3  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MEILEI2_GUI_TOOL3`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MEILEI2_GUI_TOOL3」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.4 功能点：MEILEI2_GUI_TOOL4  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MEILEI2_GUI_TOOL4`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MEILEI2_GUI_TOOL4」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.5 功能点：MeiLei2_ArcLength  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_ArcLength`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_ArcLength」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.6 功能点：MeiLei2_BodyMoveLayer  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_BodyMoveLayer`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_BodyMoveLayer」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.7 功能点：MeiLei2_CentroidAnalysis  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_CentroidAnalysis`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_CentroidAnalysis」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.8 功能点：MeiLei2_CheckBreakFaceLocation  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_CheckBreakFaceLocation`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_CheckBreakFaceLocation」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.9 功能点：MeiLei2_CheckInterference  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_CheckInterference`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_CheckInterference」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.10 功能点：MeiLei2_ClearHighlight  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_ClearHighlight`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_ClearHighlight」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.11 功能点：MeiLei2_CloseAllLayer  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_CloseAllLayer`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_CloseAllLayer」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.12 功能点：MeiLei2_CloseSelObjlayer  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_CloseSelObjlayer`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_CloseSelObjlayer」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.13 功能点：MeiLei2_Color  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_Color`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_Color」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.14 功能点：MeiLei2_ContactFace  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_ContactFace`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_ContactFace」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.15 功能点：MeiLei2_DynamicCircle  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_DynamicCircle`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_DynamicCircle」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.16 功能点：MeiLei2_FindHaveBreakFaceBody  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_FindHaveBreakFaceBody`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_FindHaveBreakFaceBody」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.17 功能点：MeiLei2_Geometric_Analysis  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_Geometric_Analysis`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_Geometric_Analysis」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.18 功能点：MeiLei2_HideAllObj  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_HideAllObj`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_HideAllObj」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.19 功能点：MeiLei2_HoleInformation  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_HoleInformation`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_HoleInformation」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.20 功能点：MeiLei2_HoleMeasurement  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_HoleMeasurement`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_HoleMeasurement」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.21 功能点：MeiLei2_LayerGroup  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_LayerGroup`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_LayerGroup」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.22 功能点：MeiLei2_MeasureBodySize  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_MeasureBodySize`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_MeasureBodySize」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.23 功能点：MeiLei2_MeasuringEntity  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_MeasuringEntity`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_MeasuringEntity」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.24 功能点：MeiLei2_Object257Layer  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_Object257Layer`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_Object257Layer」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.25 功能点：MeiLei2_ObjectColor  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_ObjectColor`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_ObjectColor」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.26 功能点：MeiLei2_ObjectCommonlyOperation  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_ObjectCommonlyOperation`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_ObjectCommonlyOperation」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.27 功能点：MeiLei2_ObjectInformation  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_ObjectInformation`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_ObjectInformation」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.28 功能点：MeiLei2_ObjectMoveLayer  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_ObjectMoveLayer`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_ObjectMoveLayer」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.29 功能点：MeiLei2_OenSelObjlayer  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_OenSelObjlayer`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_OenSelObjlayer」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.30 功能点：MeiLei2_OpenAllLayer  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_OpenAllLayer`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_OpenAllLayer」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.31 功能点：MeiLei2_OpenAllLayerOrShow  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_OpenAllLayerOrShow`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_OpenAllLayerOrShow」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.32 功能点：MeiLei2_OpenBotObjWork  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_OpenBotObjWork`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_OpenBotObjWork」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.33 功能点：MeiLei2_OpenBotWork  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_OpenBotWork`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_OpenBotWork」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.34 功能点：MeiLei2_OpenUpObjWork  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_OpenUpObjWork`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_OpenUpObjWork」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.35 功能点：MeiLei2_OpenUpWork  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_OpenUpWork`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_OpenUpWork」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.36 功能点：MeiLei2_PointCoordinates  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_PointCoordinates`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_PointCoordinates」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.37 功能点：MeiLei2_PointPointDistance  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_PointPointDistance`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_PointPointDistance」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.38 功能点：MeiLei2_RepairBreakFace  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_RepairBreakFace`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_RepairBreakFace」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.39 功能点：MeiLei2_ReverseHide  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_ReverseHide`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_ReverseHide」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.40 功能点：MeiLei2_ReverseLayer  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_ReverseLayer`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_ReverseLayer」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.41 功能点：MeiLei2_SelHideObj  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_SelHideObj`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_SelHideObj」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.42 功能点：MeiLei2_SelShowObj  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_SelShowObj`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_SelShowObj」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.43 功能点：MeiLei2_SetWorkCsys  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_SetWorkCsys`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_SetWorkCsys」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.44 功能点：MeiLei2_ShowAllObj  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_ShowAllObj`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_ShowAllObj」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 3.45 功能点：MeiLei2_WaterContactCheck  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MeiLei2_WaterContactCheck`
- **出现菜单**：`YANGJEE/MeiLei2_tool/configuration/gui/drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `YANGJEE/MeiLei2_tool/configuration/gui/drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MeiLei2_WaterContactCheck」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 4. 子模块：表(B)

本子模块 33 个功能点。

### 4.1 功能点：编辑表指引线  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_EDIT_TABLE_LEADER`
- **菜单路径**：编辑(E) › 表(B) › 指引线(L)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B)**。
2. 在展开项中选择 **指引线(L)...**（命令 ID：`UG_DRAFT_EDIT_TABLE_LEADER`）。
3. 按对话框提示操作：编辑零件明细表、表格注释或表格标签的指引线。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：编辑零件明细表、表格注释或表格标签的指引线。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 4.2 功能点：附加/拆离行  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_ATTACH_DETACH_ROWS`
- **菜单路径**：编辑(E) › 表(B) › 附加/拆离行(A)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B)**。
2. 在展开项中选择 **附加/拆离行(A)**（命令 ID：`UG_TABLE_ATTACH_DETACH_ROWS`）。
3. 按对话框提示操作：将选定的行附加至父行或整个零件明细表，或从父行或整个零件明细表拆离选定的行。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将选定的行附加至父行或整个零件明细表，或从父行或整个零件明细表拆离选定的行。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 4.3 功能点：自动符号标注  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_AUTOBALLOON`
- **菜单路径**：插入(S) › 表(B) › 自动符号标注(B)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 表(B)**。
2. 在展开项中选择 **自动符号标注(B)**（命令 ID：`UG_TABLE_AUTOBALLOON`）。
3. 按对话框提示操作：为选定的零件明细表创建关联的圆形符号。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：为选定的零件明细表创建关联的圆形符号。
    - 检索同义词：ID symbol, autoballoon

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 4.4 功能点：粗体  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_BOLD`
- **菜单路径**：编辑(E) › 表(B) › 粗体(B)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_title_block.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B)**。
2. 在展开项中选择 **粗体(B)**（命令 ID：`UG_TABLE_BOLD`）。
3. 按对话框提示操作：将选定单元格中的文本改为使用粗体字。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将选定单元格中的文本改为使用粗体字。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 4.5 功能点：单元格设置  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_CELL_STYLE`
- **菜单路径**：编辑(E) › 表(B) › 单元格设置(C)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_title_block.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B)**。
2. 在展开项中选择 **单元格设置(C)...**（命令 ID：`UG_TABLE_CELL_STYLE`）。
3. 按对话框提示操作：编辑选定单元格的设置。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：编辑选定单元格的设置。
    - 检索同义词：appearance, look

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 4.6 功能点：零件明细表  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_CREATE_PARTS_LIST`
- **菜单路径**：插入(S) › 表(B) › 零件明细表(P)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 表(B)**。
2. 在展开项中选择 **零件明细表(P)...**（命令 ID：`UG_TABLE_CREATE_PARTS_LIST`）。
3. 按对话框提示操作：创建装配的物料清单。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建装配的物料清单。
    - 检索同义词：BOM balloon region in a table

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 4.7 功能点：编辑表  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_EDIT`
- **菜单路径**：编辑(E) › 表(B) › 编辑(E)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_title_block.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B)**。
2. 在展开项中选择 **编辑(E)...**（命令 ID：`UG_TABLE_EDIT`）。
3. 按对话框提示操作：编辑选定的表区域。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：编辑选定的表区域。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 4.8 功能点：编辑单元格  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_EDIT_CELL`
- **菜单路径**：编辑(E) › 表(B) › 编辑单元格(C)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_title_block.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B)**。
2. 在展开项中选择 **编辑单元格(C)...**（命令 ID：`UG_TABLE_EDIT_CELL`）。
3. 按对话框提示操作：编辑选定单元格中的文本。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：编辑选定单元格中的文本。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 4.9 功能点：编辑文本  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_EDIT_TEXT`
- **菜单路径**：编辑(E) › 表(B) › 编辑文本(T)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_title_block.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B)**。
2. 在展开项中选择 **编辑文本(T)...**（命令 ID：`UG_TABLE_EDIT_TEXT`）。
3. 按对话框提示操作：使用注释编辑器编辑选定单元格中的文本。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：使用注释编辑器编辑选定单元格中的文本。
    - 检索同义词：access part or assembly material parameters in drawing

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 4.10 功能点：使用电子表格编辑表  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_EDIT_USING_SPREADSHEET`
- **菜单路径**：编辑(E) › 表(B) › 使用电子表格编辑(N)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B)**。
2. 在展开项中选择 **使用电子表格编辑(N)**（命令 ID：`UG_TABLE_EDIT_USING_SPREADSHEET`）。
3. 按对话框提示操作：使用电子表编辑选定的表。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：使用电子表编辑选定的表。
    - 检索同义词：Excel, Xess, edit using spreadsheet

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 4.11 功能点：不用电子表格编辑表  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_EDIT_WITHOUT_SPREADSHEET`
- **菜单路径**：编辑(E) › 表(B) › 不用电子表格编辑(W)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B)**。
2. 在展开项中选择 **不用电子表格编辑(W)**（命令 ID：`UG_TABLE_EDIT_WITHOUT_SPREADSHEET`）。
3. 按对话框提示操作：当编辑选定的表格时，使电子表格不可用。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：当编辑选定的表格时，使电子表格不可用。
    - 检索同义词：edit without spreadsheet

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 4.12 功能点：评估规则和更新  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_EVALUATE_RULES_AND_UPDATE`
- **菜单路径**：编辑(E) › 表(B) › 评估规则和更新(L)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_title_block.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B)**。
2. 在展开项中选择 **评估规则和更新(L)**（命令 ID：`UG_TABLE_EVALUATE_RULES_AND_UPDATE`）。
3. 按对话框提示操作：评估规则并更新选定的表格注释。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：评估规则并更新选定的表格注释。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 4.13 功能点：导出  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_EXPORT`
- **菜单路径**：编辑(E) › 表(B) › 导出(X)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_title_block.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B)**。
2. 在展开项中选择 **导出(X)...**（命令 ID：`UG_TABLE_EXPORT`）。
3. 按对话框提示操作：将表或零件明细表导出至外部文件或浏览器。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将表或零件明细表导出至外部文件或浏览器。
    - 检索同义词：save a table as text

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 4.14 功能点：属性  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_FORMBOARD_EDIT_OBJECT_ATTRIBUTE`
- **菜单路径**：编辑(E) › 表(B) › 属性(A)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B)**。
2. 在展开项中选择 **属性(A)...**（命令 ID：`UG_TABLE_FORMBOARD_EDIT_OBJECT_ATTRIBUTE`）。
3. 按对话框提示操作：将某一对象属性指派到选定的表格注释单元格。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将某一对象属性指派到选定的表格注释单元格。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 4.15 功能点：对象参考属性  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_FORMBOARD_OBJECT_ATTRIBUTE_SELECTION`
- **菜单路径**：编辑(E) › 表(B) › 对象参考属性(J)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B)**。
2. 在展开项中选择 **对象参考属性(J)**（命令 ID：`UG_TABLE_FORMBOARD_OBJECT_ATTRIBUTE_SELECTION`）。
3. 按对话框提示操作：将某一对象的属性与选定的表格注释相关联。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将某一对象的属性与选定的表格注释相关联。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 4.16 功能点：选择引脚列表组件  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_FORMBOARD_PIN_LIST_SELECTION`
- **菜单路径**：编辑(E) › 表(B) › 选择引脚列表组件(P)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B)**。
2. 在展开项中选择 **选择引脚列表组件(P)**（命令 ID：`UG_TABLE_FORMBOARD_PIN_LIST_SELECTION`）。
3. 按对话框提示操作：选择用于引脚列表的组件。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：选择用于引脚列表的组件。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 4.17 功能点：转至单元格 URL  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_GOTO_CELL_URL`
- **菜单路径**：编辑(E) › 表(B) › 转至单元格 URL(G)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_title_block.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B)**。
2. 在展开项中选择 **转至单元格 URL(G)**（命令 ID：`UG_TABLE_GOTO_CELL_URL`）。
3. 按对话框提示操作：在系统定义的 Web 浏览器中打开选定单元格中指定的 URL。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在系统定义的 Web 浏览器中打开选定单元格中指定的 URL。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 4.18 功能点：斜体  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_ITALIC`
- **菜单路径**：编辑(E) › 表(B) › 斜体(I)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_title_block.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B)**。
2. 在展开项中选择 **斜体(I)**（命令 ID：`UG_TABLE_ITALIC`）。
3. 按对话框提示操作：将选定单元格中的文本改为使用斜体字。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将选定单元格中的文本改为使用斜体字。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 4.19 功能点：锁定/解锁行  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_LOCK_UNLOCK_ROWS`
- **菜单路径**：编辑(E) › 表(B) › 锁定/解锁行(K)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B)**。
2. 在展开项中选择 **锁定/解锁行(K)**（命令 ID：`UG_TABLE_LOCK_UNLOCK_ROWS`）。
3. 按对话框提示操作：锁定选定行，并在删除后采用“已锁定删除的行”设置。“解锁”会除去对选定行的锁定。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：锁定选定行，并在删除后采用“已锁定删除的行”设置。“解锁”会除去对选定行的锁定。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 4.20 功能点：合并单元格  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_MERGE_CELLS`
- **菜单路径**：编辑(E) › 表(B) › 合并单元格(M)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_title_block.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B)**。
2. 在展开项中选择 **合并单元格(M)**（命令 ID：`UG_TABLE_MERGE_CELLS`）。
3. 按对话框提示操作：合并选定的单元格。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：合并选定的单元格。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 4.21 功能点：调整大小  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_RESIZE_ROWS_COLS`
- **菜单路径**：编辑(E) › 表(B) › 调整大小(Z)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_title_block.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B)**。
2. 在展开项中选择 **调整大小(Z)**（命令 ID：`UG_TABLE_RESIZE_ROWS_COLS`）。
3. 按对话框提示操作：调整选定行的高度或选定列的宽度。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：调整选定行的高度或选定列的宽度。
    - 检索同义词：resize rows and columns

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 4.22 功能点：恢复自动文本  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_RESTORE_AUTO_TEXT`
- **菜单路径**：编辑(E) › 表(B) › 自动文本(O)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B)**。
2. 在展开项中选择 **自动文本(O)**（命令 ID：`UG_TABLE_RESTORE_AUTO_TEXT`）。
3. 按对话框提示操作：将各列的默认文本恢复为零件明细表中每个选定单元格的文本。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将各列的默认文本恢复为零件明细表中每个选定单元格的文本。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 4.23 功能点：另存为模板  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_SAVE_AS_TEMPLATE`
- **菜单路径**：编辑(E) › 表(B) › 另存为模板(V)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B)**。
2. 在展开项中选择 **另存为模板(V)...**（命令 ID：`UG_TABLE_SAVE_AS_TEMPLATE`）。
3. 按对话框提示操作：将选定的表或零件明细表作为定制的表模板文件保存到表资源板中。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将选定的表或零件明细表作为定制的表模板文件保存到表资源板中。
    - 检索同义词：save a table

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 4.24 功能点：排序  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_SORT_ROWS`
- **菜单路径**：编辑(E) › 表(B) › 排序(R)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B)**。
2. 在展开项中选择 **排序(R)...**（命令 ID：`UG_TABLE_SORT_ROWS`）。
3. 按对话框提示操作：按列值对选定的表或零件明细表进行排序。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：按列值对选定的表或零件明细表进行排序。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 4.25 功能点：表设置  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_STYLE`
- **菜单路径**：编辑(E) › 表(B) › 设置(S)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_title_block.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B)**。
2. 在展开项中选择 **设置(S)...**（命令 ID：`UG_TABLE_STYLE`）。
3. 按对话框提示操作：编辑选定表或零件明细表的设置。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：编辑选定表或零件明细表的设置。
    - 检索同义词：appearance, look

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 4.26 功能点：取消合并单元格  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_UNMERGE_CELLS`
- **菜单路径**：编辑(E) › 表(B) › 取消合并单元格(U)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_title_block.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B)**。
2. 在展开项中选择 **取消合并单元格(U)**（命令 ID：`UG_TABLE_UNMERGE_CELLS`）。
3. 按对话框提示操作：取消合并选定的已合并单元格。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：取消合并选定的已合并单元格。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 4.27 功能点：更新折弯表  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_UPDATE_BEND_TABLE`
- **菜单路径**：编辑(E) › 表(B) › 更新折弯表(D)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B)**。
2. 在展开项中选择 **更新折弯表(D)**（命令 ID：`UG_TABLE_UPDATE_BEND_TABLE`）。
3. 按对话框提示操作：手动更新选定的折弯表。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：手动更新选定的折弯表。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 4.28 功能点：更新下料长度表  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_UPDATE_FORMBOARD_CUT_SHEET`
- **菜单路径**：编辑(E) › 表(B) › 更新下料长度表(H)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B)**。
2. 在展开项中选择 **更新下料长度表(H)**（命令 ID：`UG_TABLE_UPDATE_FORMBOARD_CUT_SHEET`）。
3. 按对话框提示操作：手动更新选定的下料长度表。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：手动更新选定的下料长度表。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 4.29 功能点：更新引脚列表  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_UPDATE_FORMBOARD_PIN_LIST`
- **菜单路径**：编辑(E) › 表(B) › 更新引脚列表(D)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B)**。
2. 在展开项中选择 **更新引脚列表(D)**（命令 ID：`UG_TABLE_UPDATE_FORMBOARD_PIN_LIST`）。
3. 按对话框提示操作：手动更新选定的引脚列表。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：手动更新选定的引脚列表。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 4.30 功能点：更新孔表  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_UPDATE_HOLE_TABLE`
- **菜单路径**：编辑(E) › 表(B) › 更新孔表(H)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B)**。
2. 在展开项中选择 **更新孔表(H)**（命令 ID：`UG_TABLE_UPDATE_HOLE_TABLE`）。
3. 按对话框提示操作：手动更新选定的孔表。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：手动更新选定的孔表。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 4.31 功能点：更新零件明细表  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_UPDATE_PARTS_LIST`
- **菜单路径**：编辑(E) › 表(B) › 更新零件明细表(D)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B)**。
2. 在展开项中选择 **更新零件明细表(D)**（命令 ID：`UG_TABLE_UPDATE_PARTS_LIST`）。
3. 按对话框提示操作：手动更新选定的零件明细表。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：手动更新选定的零件明细表。
    - 检索同义词：bill of material, BOM

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 4.32 功能点：更新表  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_UPDATE_PMI_TABLE`
- **菜单路径**：编辑(E) › 表(B) › 更新表(T)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B)**。
2. 在展开项中选择 **更新表(T)**（命令 ID：`UG_TABLE_UPDATE_PMI_TABLE`）。
3. 按对话框提示操作：手动更新选定的表。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：手动更新选定的表。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 4.33 功能点：更新表格注释  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_UPDATE_TABULAR_NOTE`
- **菜单路径**：编辑(E) › 表(B) › 更新表格注释(B)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_title_block.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B)**。
2. 在展开项中选择 **更新表格注释(B)**（命令 ID：`UG_TABLE_UPDATE_TABULAR_NOTE`）。
3. 按对话框提示操作：手动更新选定的表格注释。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：手动更新选定的表格注释。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 5. 子模块：船舶结构

本子模块 25 个功能点。

### 5.1 功能点：船舶设计(B)  `[NX12.0-CN] [E4-TRANSLATION]`

- **命令 ID**：`NX_SHIP_STRUCTURE`
- **来源提示**：`nx_drafting_shipstructure.men`
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/nx_drafting_shipstructure_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令为 **E4-TRANSLATION**：中文名/功能说明来自官方简体中文翻译表（`nx_drafting_shipstructure.men`），但 `.men/.btn` 菜单源未随当前介质提供；[待实测] 在对应应用模块中通过 `帮助(H) › 命令查找器(F)` 搜索「船舶设计(B)」定位实际菜单路径。
2. 按对话框提示操作：列出船舶设计命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出船舶设计命令。

**注意事项**：

    - 该命令来自官方简体中文翻译表（E4），中文名/功能说明可信；但菜单路径、快捷键、参数对话框未随介质提供，必须在 NX 12.0 中文界面 GUI 复核后使用。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 5.2 功能点：尺寸(I)...  `[NX12.0-CN] [E4-TRANSLATION]`

- **命令 ID**：`UG_DRAFT_DIMENSION_SHIP`
- **来源提示**：`nx_drafting_shipstructure.men`
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/nx_drafting_shipstructure_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令为 **E4-TRANSLATION**：中文名/功能说明来自官方简体中文翻译表（`nx_drafting_shipstructure.men`），但 `.men/.btn` 菜单源未随当前介质提供；[待实测] 在对应应用模块中通过 `帮助(H) › 命令查找器(F)` 搜索「尺寸(I)...」定位实际菜单路径。
2. 按对话框提示操作：创建从船舶概念模型中的某一指定位置到某一对象或点的基线尺寸。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建从船舶概念模型中的某一指定位置到某一对象或点的基线尺寸。
    - 可用性提示：此命令仅在提供船舶制图许可证时可用。

**注意事项**：

    - 该命令来自官方简体中文翻译表（E4），中文名/功能说明可信；但菜单路径、快捷键、参数对话框未随介质提供，必须在 NX 12.0 中文界面 GUI 复核后使用。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 5.3 功能点：船舶设计（原有）(N)  `[NX12.0-CN] [E4-TRANSLATION]`

- **命令 ID**：`UG_SHIPBUILDING_DRAFTING`
- **来源提示**：`ug_drafting_shipbuilding.men`
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_drafting_shipbuilding_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令为 **E4-TRANSLATION**：中文名/功能说明来自官方简体中文翻译表（`ug_drafting_shipbuilding.men`），但 `.men/.btn` 菜单源未随当前介质提供；[待实测] 在对应应用模块中通过 `帮助(H) › 命令查找器(F)` 搜索「船舶设计（原有）(N)」定位实际菜单路径。
2. 按对话框提示操作：列出制图船舶设计（原有）命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出制图船舶设计（原有）命令。

**注意事项**：

    - 该命令来自官方简体中文翻译表（E4），中文名/功能说明可信；但菜单路径、快捷键、参数对话框未随介质提供，必须在 NX 12.0 中文界面 GUI 复核后使用。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 5.4 功能点：标注船舶图纸(A)...  `[NX12.0-CN] [E4-TRANSLATION]`

- **命令 ID**：`UG_SHIP_ANNOTATE_DRAWING`
- **来源提示**：`nx_drafting_shipstructure.men`
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/nx_drafting_shipstructure_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令为 **E4-TRANSLATION**：中文名/功能说明来自官方简体中文翻译表（`nx_drafting_shipstructure.men`），但 `.men/.btn` 菜单源未随当前介质提供；[待实测] 在对应应用模块中通过 `帮助(H) › 命令查找器(F)` 搜索「标注船舶图纸(A)...」定位实际菜单路径。
2. 按对话框提示操作：标注船舶图纸。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：标注船舶图纸。

**注意事项**：

    - 该命令来自官方简体中文翻译表（E4），中文名/功能说明可信；但菜单路径、快捷键、参数对话框未随介质提供，必须在 NX 12.0 中文界面 GUI 复核后使用。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 5.5 功能点：注释船舶对象(N)...  `[NX12.0-CN] [E4-TRANSLATION]`

- **命令 ID**：`UG_SHIP_ANNOTATE_OBJECT`
- **来源提示**：`nx_drafting_shipstructure.men`
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/nx_drafting_shipstructure_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令为 **E4-TRANSLATION**：中文名/功能说明来自官方简体中文翻译表（`nx_drafting_shipstructure.men`），但 `.men/.btn` 菜单源未随当前介质提供；[待实测] 在对应应用模块中通过 `帮助(H) › 命令查找器(F)` 搜索「注释船舶对象(N)...」定位实际菜单路径。
2. 按对话框提示操作：注释船舶对象。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：注释船舶对象。

**注意事项**：

    - 该命令来自官方简体中文翻译表（E4），中文名/功能说明可信；但菜单路径、快捷键、参数对话框未随介质提供，必须在 NX 12.0 中文界面 GUI 复核后使用。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 5.6 功能点：注释(A)...  `[NX12.0-CN] [E4-TRANSLATION]`

- **命令 ID**：`UG_SHIP_ANNOTATION`
- **来源提示**：`ug_drafting_shipbuilding.men`
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_drafting_shipbuilding_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令为 **E4-TRANSLATION**：中文名/功能说明来自官方简体中文翻译表（`ug_drafting_shipbuilding.men`），但 `.men/.btn` 菜单源未随当前介质提供；[待实测] 在对应应用模块中通过 `帮助(H) › 命令查找器(F)` 搜索「注释(A)...」定位实际菜单路径。
2. 按对话框提示操作：创建和编辑特定于船舶设计的装配图纸注释和符号。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建和编辑特定于船舶设计的装配图纸注释和符号。

**注意事项**：

    - 该命令来自官方简体中文翻译表（E4），中文名/功能说明可信；但菜单路径、快捷键、参数对话框未随介质提供，必须在 NX 12.0 中文界面 GUI 复核后使用。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 5.7 功能点：区域中心线(L)...  `[NX12.0-CN] [E4-TRANSLATION]`

- **命令 ID**：`UG_SHIP_AREACENTERLINE`
- **来源提示**：`ug_drafting_shipbuilding.men`
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_drafting_shipbuilding_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令为 **E4-TRANSLATION**：中文名/功能说明来自官方简体中文翻译表（`ug_drafting_shipbuilding.men`），但 `.men/.btn` 菜单源未随当前介质提供；[待实测] 在对应应用模块中通过 `帮助(H) › 命令查找器(F)` 搜索「区域中心线(L)...」定位实际菜单路径。
2. 按对话框提示操作：创建船舶设计特定组件中心线，这种中心线由以边限定的某个区域内的两条或两条以上交叉线组成。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建船舶设计特定组件中心线，这种中心线由以边限定的某个区域内的两条或两条以上交叉线组成。

**注意事项**：

    - 该命令来自官方简体中文翻译表（E4），中文名/功能说明可信；但菜单路径、快捷键、参数对话框未随介质提供，必须在 NX 12.0 中文界面 GUI 复核后使用。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 5.8 功能点：基本设计外板展开图(X)...  `[NX12.0-CN] [E4-TRANSLATION]`

- **命令 ID**：`UG_SHIP_BASIC_EXPANSION_DRAWING`
- **来源提示**：`nx_drafting_shipstructure.men`
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/nx_drafting_shipstructure_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令为 **E4-TRANSLATION**：中文名/功能说明来自官方简体中文翻译表（`nx_drafting_shipstructure.men`），但 `.men/.btn` 菜单源未随当前介质提供；[待实测] 在对应应用模块中通过 `帮助(H) › 命令查找器(F)` 搜索「基本设计外板展开图(X)...」定位实际菜单路径。
2. 按对话框提示操作：创建选定船舶部件的外板展开图。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建选定船舶部件的外板展开图。

**注意事项**：

    - 该命令来自官方简体中文翻译表（E4），中文名/功能说明可信；但菜单路径、快捷键、参数对话框未随介质提供，必须在 NX 12.0 中文界面 GUI 复核后使用。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 5.9 功能点：基本设计剖面图(S)...  `[NX12.0-CN] [E4-TRANSLATION]`

- **命令 ID**：`UG_SHIP_BASIC_SECTION_DRAWING`
- **来源提示**：`nx_drafting_shipstructure.men`
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/nx_drafting_shipstructure_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令为 **E4-TRANSLATION**：中文名/功能说明来自官方简体中文翻译表（`nx_drafting_shipstructure.men`），但 `.men/.btn` 菜单源未随当前介质提供；[待实测] 在对应应用模块中通过 `帮助(H) › 命令查找器(F)` 搜索「基本设计剖面图(S)...」定位实际菜单路径。
2. 按对话框提示操作：在一个或多个平面上创建选定船舶部件的图纸。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在一个或多个平面上创建选定船舶部件的图纸。

**注意事项**：

    - 该命令来自官方简体中文翻译表（E4），中文名/功能说明可信；但菜单路径、快捷键、参数对话框未随介质提供，必须在 NX 12.0 中文界面 GUI 复核后使用。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 5.10 功能点：详细设计外板展开图(O)...  `[NX12.0-CN] [E4-TRANSLATION]`

- **命令 ID**：`UG_SHIP_DETAIL_EXPANSION_DRAWING`
- **来源提示**：`nx_drafting_shipstructure.men`
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/nx_drafting_shipstructure_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令为 **E4-TRANSLATION**：中文名/功能说明来自官方简体中文翻译表（`nx_drafting_shipstructure.men`），但 `.men/.btn` 菜单源未随当前介质提供；[待实测] 在对应应用模块中通过 `帮助(H) › 命令查找器(F)` 搜索「详细设计外板展开图(O)...」定位实际菜单路径。
2. 按对话框提示操作：创建选定船舶部件的外板展开图。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建选定船舶部件的外板展开图。

**注意事项**：

    - 该命令来自官方简体中文翻译表（E4），中文名/功能说明可信；但菜单路径、快捷键、参数对话框未随介质提供，必须在 NX 12.0 中文界面 GUI 复核后使用。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 5.11 功能点：详细设计剖面图(T)...  `[NX12.0-CN] [E4-TRANSLATION]`

- **命令 ID**：`UG_SHIP_DETAIL_SECTION_DRAWING`
- **来源提示**：`nx_drafting_shipstructure.men`
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/nx_drafting_shipstructure_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令为 **E4-TRANSLATION**：中文名/功能说明来自官方简体中文翻译表（`nx_drafting_shipstructure.men`），但 `.men/.btn` 菜单源未随当前介质提供；[待实测] 在对应应用模块中通过 `帮助(H) › 命令查找器(F)` 搜索「详细设计剖面图(T)...」定位实际菜单路径。
2. 按对话框提示操作：在一个或多个平面上创建选定船舶部件的图纸。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在一个或多个平面上创建选定船舶部件的图纸。

**注意事项**：

    - 该命令来自官方简体中文翻译表（E4），中文名/功能说明可信；但菜单路径、快捷键、参数对话框未随介质提供，必须在 NX 12.0 中文界面 GUI 复核后使用。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 5.12 功能点：制图线(D)...  `[NX12.0-CN] [E4-TRANSLATION]`

- **命令 ID**：`UG_SHIP_DRAFTINGLINE`
- **来源提示**：`ug_drafting_shipbuilding.men`
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_drafting_shipbuilding_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令为 **E4-TRANSLATION**：中文名/功能说明来自官方简体中文翻译表（`ug_drafting_shipbuilding.men`），但 `.men/.btn` 菜单源未随当前介质提供；[待实测] 在对应应用模块中通过 `帮助(H) › 命令查找器(F)` 搜索「制图线(D)...」定位实际菜单路径。
2. 按对话框提示操作：用所需的线型、宽度和颜色绘制特定于船舶设计的组件类（由属性标识）。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：用所需的线型、宽度和颜色绘制特定于船舶设计的组件类（由属性标识）。

**注意事项**：

    - 该命令来自官方简体中文翻译表（E4），中文名/功能说明可信；但菜单路径、快捷键、参数对话框未随介质提供，必须在 NX 12.0 中文界面 GUI 复核后使用。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 5.13 功能点：编辑船舶剖面图(D)...  `[NX12.0-CN] [E4-TRANSLATION]`

- **命令 ID**：`UG_SHIP_DRAFT_SECTION_EDITOR`
- **来源提示**：`nx_drafting_shipstructure.men`
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/nx_drafting_shipstructure_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令为 **E4-TRANSLATION**：中文名/功能说明来自官方简体中文翻译表（`nx_drafting_shipstructure.men`），但 `.men/.btn` 菜单源未随当前介质提供；[待实测] 在对应应用模块中通过 `帮助(H) › 命令查找器(F)` 搜索「编辑船舶剖面图(D)...」定位实际菜单路径。
2. 按对话框提示操作：编辑显示部件中的船舶剖面图。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：编辑显示部件中的船舶剖面图。

**注意事项**：

    - 该命令来自官方简体中文翻译表（E4），中文名/功能说明可信；但菜单路径、快捷键、参数对话框未随介质提供，必须在 NX 12.0 中文界面 GUI 复核后使用。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 5.14 功能点：疏散平面图符号(E)...  `[NX12.0-CN] [E4-TRANSLATION]`

- **命令 ID**：`UG_SHIP_EVACUATION_PLAN_SYMBOL`
- **来源提示**：`nx_drafting_shipstructure.men`
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/nx_drafting_shipstructure_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令为 **E4-TRANSLATION**：中文名/功能说明来自官方简体中文翻译表（`nx_drafting_shipstructure.men`），但 `.men/.btn` 菜单源未随当前介质提供；[待实测] 在对应应用模块中通过 `帮助(H) › 命令查找器(F)` 搜索「疏散平面图符号(E)...」定位实际菜单路径。
2. 按对话框提示操作：在图纸视图中创建疏散平面图符号。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在图纸视图中创建疏散平面图符号。

**注意事项**：

    - 该命令来自官方简体中文翻译表（E4），中文名/功能说明可信；但菜单路径、快捷键、参数对话框未随介质提供，必须在 NX 12.0 中文界面 GUI 复核后使用。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 5.15 功能点：肋骨线（原）(F)...  `[NX12.0-CN] [E4-TRANSLATION]`

- **命令 ID**：`UG_SHIP_FRAMEBAR`
- **来源提示**：`ug_drafting_shipbuilding.men`
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_drafting_shipbuilding_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令为 **E4-TRANSLATION**：中文名/功能说明来自官方简体中文翻译表（`ug_drafting_shipbuilding.men`），但 `.men/.btn` 菜单源未随当前介质提供；[待实测] 在对应应用模块中通过 `帮助(H) › 命令查找器(F)` 搜索「肋骨线（原）(F)...」定位实际菜单路径。
2. 按对话框提示操作：这是原来的“肋骨线”命令。将水平或竖直肋骨线添加到船舶设计装配图纸视图。肋骨线表示一个线性标尺，它提供关于船舶的信息，例如基线、舱壁和栅格。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：这是原来的“肋骨线”命令。将水平或竖直肋骨线添加到船舶设计装配图纸视图。肋骨线表示一个线性标尺，它提供关于船舶的信息，例如基线、舱壁和栅格。

**注意事项**：

    - 该命令来自官方简体中文翻译表（E4），中文名/功能说明可信；但菜单路径、快捷键、参数对话框未随介质提供，必须在 NX 12.0 中文界面 GUI 复核后使用。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 5.16 功能点：肋骨线(F)...  `[NX12.0-CN] [E4-TRANSLATION]`

- **命令 ID**：`UG_SHIP_FRAME_BAR`
- **来源提示**：`nx_drafting_shipstructure.men`
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/nx_drafting_shipstructure_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令为 **E4-TRANSLATION**：中文名/功能说明来自官方简体中文翻译表（`nx_drafting_shipstructure.men`），但 `.men/.btn` 菜单源未随当前介质提供；[待实测] 在对应应用模块中通过 `帮助(H) › 命令查找器(F)` 搜索「肋骨线(F)...」定位实际菜单路径。
2. 按对话框提示操作：将水平或竖直肋骨线添加到船舶设计装配图纸视图。肋骨线表示一个线性标尺，它提供关于船舶的信息，例如基线、舱壁和栅格。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将水平或竖直肋骨线添加到船舶设计装配图纸视图。肋骨线表示一个线性标尺，它提供关于船舶的信息，例如基线、舱壁和栅格。

**注意事项**：

    - 该命令来自官方简体中文翻译表（E4），中文名/功能说明可信；但菜单路径、快捷键、参数对话框未随介质提供，必须在 NX 12.0 中文界面 GUI 复核后使用。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 5.17 功能点：图纸自动化(W)...  `[NX12.0-CN] [E4-TRANSLATION]`

- **命令 ID**：`UG_SHIP_GENERAL_ARRANGEMENT_DRAWING_AUTOMATION`
- **来源提示**：`nx_drafting_shipstructure.men`
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/nx_drafting_shipstructure_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令为 **E4-TRANSLATION**：中文名/功能说明来自官方简体中文翻译表（`nx_drafting_shipstructure.men`），但 `.men/.btn` 菜单源未随当前介质提供；[待实测] 在对应应用模块中通过 `帮助(H) › 命令查找器(F)` 搜索「图纸自动化(W)...」定位实际菜单路径。
2. 按对话框提示操作：创建船舶整体布置视图列表。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建船舶整体布置视图列表。

**注意事项**：

    - 该命令来自官方简体中文翻译表（E4），中文名/功能说明可信；但菜单路径、快捷键、参数对话框未随介质提供，必须在 NX 12.0 中文界面 GUI 复核后使用。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 5.18 功能点：整体布置视图(G)...  `[NX12.0-CN] [E4-TRANSLATION]`

- **命令 ID**：`UG_SHIP_GENERAL_ARRANGEMENT_VIEW`
- **来源提示**：`nx_drafting_shipstructure.men`
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/nx_drafting_shipstructure_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令为 **E4-TRANSLATION**：中文名/功能说明来自官方简体中文翻译表（`nx_drafting_shipstructure.men`），但 `.men/.btn` 菜单源未随当前介质提供；[待实测] 在对应应用模块中通过 `帮助(H) › 命令查找器(F)` 搜索「整体布置视图(G)...」定位实际菜单路径。
2. 按对话框提示操作：创建船舶整体布置视图。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建船舶整体布置视图。

**注意事项**：

    - 该命令来自官方简体中文翻译表（E4），中文名/功能说明可信；但菜单路径、快捷键、参数对话框未随介质提供，必须在 NX 12.0 中文界面 GUI 复核后使用。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 5.19 功能点：型材草图(K)  `[NX12.0-CN] [E4-TRANSLATION]`

- **命令 ID**：`UG_SHIP_INVERSE_BENDING_LINE_AUTO_DRAWING`
- **来源提示**：`nx_drafting_shipstructure.men`
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/nx_drafting_shipstructure_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令为 **E4-TRANSLATION**：中文名/功能说明来自官方简体中文翻译表（`nx_drafting_shipstructure.men`），但 `.men/.btn` 菜单源未随当前介质提供；[待实测] 在对应应用模块中通过 `帮助(H) › 命令查找器(F)` 搜索「型材草图(K)」定位实际菜单路径。
2. 按对话框提示操作：创建型材的草图文件。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建型材的草图文件。

**注意事项**：

    - 该命令来自官方简体中文翻译表（E4），中文名/功能说明可信；但菜单路径、快捷键、参数对话框未随介质提供，必须在 NX 12.0 中文界面 GUI 复核后使用。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 5.20 功能点：协调计划标签(C)...  `[NX12.0-CN] [E4-TRANSLATION]`

- **命令 ID**：`UG_SHIP_LABEL_COORDINATION`
- **来源提示**：`ug_drafting_shipbuilding.men`
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_drafting_shipbuilding_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令为 **E4-TRANSLATION**：中文名/功能说明来自官方简体中文翻译表（`ug_drafting_shipbuilding.men`），但 `.men/.btn` 菜单源未随当前介质提供；[待实测] 在对应应用模块中通过 `帮助(H) › 命令查找器(F)` 搜索「协调计划标签(C)...」定位实际菜单路径。
2. 按对话框提示操作：创建船舶设计协调计划组件标签。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建船舶设计协调计划组件标签。

**注意事项**：

    - 该命令来自官方简体中文翻译表（E4），中文名/功能说明可信；但菜单路径、快捷键、参数对话框未随介质提供，必须在 NX 12.0 中文界面 GUI 复核后使用。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 5.21 功能点：设备计划标签(E)...  `[NX12.0-CN] [E4-TRANSLATION]`

- **命令 ID**：`UG_SHIP_LABEL_EQUIPMENT`
- **来源提示**：`ug_drafting_shipbuilding.men`
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_drafting_shipbuilding_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令为 **E4-TRANSLATION**：中文名/功能说明来自官方简体中文翻译表（`ug_drafting_shipbuilding.men`），但 `.men/.btn` 菜单源未随当前介质提供；[待实测] 在对应应用模块中通过 `帮助(H) › 命令查找器(F)` 搜索「设备计划标签(E)...」定位实际菜单路径。
2. 按对话框提示操作：创建船舶设计设备计划组件标签。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建船舶设计设备计划组件标签。

**注意事项**：

    - 该命令来自官方简体中文翻译表（E4），中文名/功能说明可信；但菜单路径、快捷键、参数对话框未随介质提供，必须在 NX 12.0 中文界面 GUI 复核后使用。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 5.22 功能点：标记隔绝区域(M)...  `[NX12.0-CN] [E4-TRANSLATION]`

- **命令 ID**：`UG_SHIP_MARK_INSULATION_AREA`
- **来源提示**：`nx_drafting_shipstructure.men`
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/nx_drafting_shipstructure_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令为 **E4-TRANSLATION**：中文名/功能说明来自官方简体中文翻译表（`nx_drafting_shipstructure.men`），但 `.men/.btn` 菜单源未随当前介质提供；[待实测] 在对应应用模块中通过 `帮助(H) › 命令查找器(F)` 搜索「标记隔绝区域(M)...」定位实际菜单路径。
2. 按对话框提示操作：在图纸视图中标记防火、隔热或隔音区域。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在图纸视图中标记防火、隔热或隔音区域。

**注意事项**：

    - 该命令来自官方简体中文翻译表（E4），中文名/功能说明可信；但菜单路径、快捷键、参数对话框未随介质提供，必须在 NX 12.0 中文界面 GUI 复核后使用。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 5.23 功能点：胎架图纸(P)...  `[NX12.0-CN] [E4-TRANSLATION]`

- **命令 ID**：`UG_SHIP_PINJIG_DRAWING`
- **来源提示**：`nx_drafting_shipstructure.men`
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/nx_drafting_shipstructure_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令为 **E4-TRANSLATION**：中文名/功能说明来自官方简体中文翻译表（`nx_drafting_shipstructure.men`），但 `.men/.btn` 菜单源未随当前介质提供；[待实测] 在对应应用模块中通过 `帮助(H) › 命令查找器(F)` 搜索「胎架图纸(P)...」定位实际菜单路径。
2. 按对话框提示操作：创建胎架的图纸。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建胎架的图纸。

**注意事项**：

    - 该命令来自官方简体中文翻译表（E4），中文名/功能说明可信；但菜单路径、快捷键、参数对话框未随介质提供，必须在 NX 12.0 中文界面 GUI 复核后使用。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 5.24 功能点：符号(S)...  `[NX12.0-CN] [E4-TRANSLATION]`

- **命令 ID**：`UG_SHIP_SYMBOL`
- **来源提示**：`ug_drafting_shipbuilding.men`
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_drafting_shipbuilding_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令为 **E4-TRANSLATION**：中文名/功能说明来自官方简体中文翻译表（`ug_drafting_shipbuilding.men`），但 `.men/.btn` 菜单源未随当前介质提供；[待实测] 在对应应用模块中通过 `帮助(H) › 命令查找器(F)` 搜索「符号(S)...」定位实际菜单路径。
2. 按对话框提示操作：在制图线上创建特定于船舶设计的符号（例如型材端切和厚度方向），以提供关于图纸上单元的附加信息。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在制图线上创建特定于船舶设计的符号（例如型材端切和厚度方向），以提供关于图纸上单元的附加信息。

**注意事项**：

    - 该命令来自官方简体中文翻译表（E4），中文名/功能说明可信；但菜单路径、快捷键、参数对话框未随介质提供，必须在 NX 12.0 中文界面 GUI 复核后使用。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 5.25 功能点：焊缝(W)...  `[NX12.0-CN] [E4-TRANSLATION]`

- **命令 ID**：`UG_SHIP_WELDSEAM`
- **来源提示**：`ug_drafting_shipbuilding.men`
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_drafting_shipbuilding_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令为 **E4-TRANSLATION**：中文名/功能说明来自官方简体中文翻译表（`ug_drafting_shipbuilding.men`），但 `.men/.btn` 菜单源未随当前介质提供；[待实测] 在对应应用模块中通过 `帮助(H) › 命令查找器(F)` 搜索「焊缝(W)...」定位实际菜单路径。
2. 按对话框提示操作：创建一个特定于船舶设计的焊接符号来指定焊接参数，例如：类型、轮廓形状、大小、长度和/或间距以及精加工方法。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建一个特定于船舶设计的焊接符号来指定焊接参数，例如：类型、轮廓形状、大小、长度和/或间距以及精加工方法。

**注意事项**：

    - 该命令来自官方简体中文翻译表（E4），中文名/功能说明可信；但菜单路径、快捷键、参数对话框未随介质提供，必须在 NX 12.0 中文界面 GUI 复核后使用。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 6. 子模块：nx_china_package_drafting

本子模块 19 个功能点。

### 6.1 功能点：CN_ATTRIBUTE_TOOL_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_ATTRIBUTE_TOOL_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_ATTRIBUTE_TOOL_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 6.2 功能点：CN_ATTR_TOOL_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_ATTR_TOOL_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_ATTR_TOOL_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 6.3 功能点：CN_CHECKER_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_CHECKER_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_CHECKER_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 6.4 功能点：CN_CK_ASSEM_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_CK_ASSEM_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_CK_ASSEM_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 6.5 功能点：CN_CK_DRAFT_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_CK_DRAFT_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_CK_DRAFT_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 6.6 功能点：CN_CK_MODLE_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_CK_MODLE_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_CK_MODLE_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 6.7 功能点：CN_COMPONENT_RENAME_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_COMPONENT_RENAME_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_COMPONENT_RENAME_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 6.8 功能点：CN_DCS_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_DCS_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_DCS_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 6.9 功能点：CN_DRAFTING_ANN_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_DRAFTING_ANN_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_DRAFTING_ANN_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 6.10 功能点：CN_DRAFTING_DIM_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_DRAFTING_DIM_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_DRAFTING_DIM_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 6.11 功能点：CN_DRAFTING_DIM_STYLE_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_DRAFTING_DIM_STYLE_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_DRAFTING_DIM_STYLE_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 6.12 功能点：CN_DRAFTING_TOOL_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_DRAFTING_TOOL_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_DRAFTING_TOOL_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 6.13 功能点：CN_DRAFTING_VIEW_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_DRAFTING_VIEW_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_DRAFTING_VIEW_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 6.14 功能点：CN_DRAFT_GEAR_TOOL_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_DRAFT_GEAR_TOOL_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_DRAFT_GEAR_TOOL_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 6.15 功能点：CN_DRAFT_SPRING_TOOL_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_DRAFT_SPRING_TOOL_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_DRAFT_SPRING_TOOL_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 6.16 功能点：CN_OTHER_TOOL_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_OTHER_TOOL_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_OTHER_TOOL_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 6.17 功能点：CN_STANDARDIZATION_TOOL_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_STANDARDIZATION_TOOL_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_STANDARDIZATION_TOOL_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 6.18 功能点：CN_STD_LAYER_CAT_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_STD_LAYER_CAT_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_STD_LAYER_CAT_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 6.19 功能点：CN_STD_LAYER_STA_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`CN_STD_LAYER_STA_BTN`
- **出现菜单**：`LOCALIZATION/prc/application/nx_china_package_drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `LOCALIZATION/prc/application/nx_china_package_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「CN_STD_LAYER_STA_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 7. 子模块：编辑(E)

本子模块 19 个功能点。

### 7.1 功能点：抑制制图对象  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_EDIT_COND_OBJ`
- **菜单路径**：编辑(E) › 抑制制图对象(F)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E)**。
2. 在展开项中选择 **抑制制图对象(F)...**（命令 ID：`UG_DRAFT_EDIT_COND_OBJ`）。
3. 按对话框提示操作：使用控制表达式控制制图对象的可见性。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：使用控制表达式控制制图对象的可见性。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 7.2 功能点：编辑制图对象组件  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_EDIT_DEL_COMP`
- **菜单路径**：编辑(E) › 组件(M)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E)**。
2. 在展开项中选择 **组件(M)...**（命令 ID：`UG_DRAFT_EDIT_DEL_COMP`）。
3. 按对话框提示操作：删除或移动制图对象上的组件（缝隙或折线），或者删除制图对象的一部分（尺寸标注线或箭头）。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：删除或移动制图对象上的组件（缝隙或折线），或者删除制图对象的一部分（尺寸标注线或箭头）。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 7.3 功能点：编辑图像  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_EDIT_IMAGE`
- **菜单路径**：编辑(E) › 图像(I)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E)**。
2. 在展开项中选择 **图像(I)...**（命令 ID：`UG_DRAFT_EDIT_IMAGE`）。
3. 按对话框提示操作：修改图纸页上光栅图像的位置、方位、大小或宽高比。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：修改图纸页上光栅图像的位置、方位、大小或宽高比。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 7.4 功能点：复制  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_EDIT_COPY`
- **菜单路径**：编辑(E) › 复制(C)
- **快捷键**：`Ctrl+C`
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 5 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E)**。
2. 在展开项中选择 **复制(C)**（命令 ID：`UG_EDIT_COPY`）。
3. 可直接使用快捷键 **Ctrl+C** 调用（该快捷键来自介质 `.btn` 定义）。
4. 按对话框提示操作：将选定的对象复制到剪贴板上。
5. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将选定的对象复制到剪贴板上。
    - 检索同义词：duplicate, switch views to another sheet

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 7.5 功能点：复制显示  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_EDIT_COPY_DISPLAY`
- **菜单路径**：编辑(E) › 复制显示(S)
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 4 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E)**。
2. 在展开项中选择 **复制显示(S)**（命令 ID：`UG_EDIT_COPY_DISPLAY`）。
3. 按对话框提示操作：将图形窗口的图像复制到剪贴板上。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将图形窗口的图像复制到剪贴板上。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 7.6 功能点：剪切  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_EDIT_CUT`
- **菜单路径**：编辑(E) › 剪切(T)
- **快捷键**：`Ctrl+X`
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 4 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E)**。
2. 在展开项中选择 **剪切(T)**（命令 ID：`UG_EDIT_CUT`）。
3. 可直接使用快捷键 **Ctrl+X** 调用（该快捷键来自介质 `.btn` 定义）。
4. 按对话框提示操作：剪切选定的对象并将其放在剪贴板上。
5. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：剪切选定的对象并将其放在剪贴板上。
    - 检索同义词：tear

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 7.7 功能点：删除  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_EDIT_DELETE`
- **菜单路径**：编辑(E) › 删除(D)...
- **快捷键**：`Ctrl+D`
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 6 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E)**。
2. 在展开项中选择 **删除(D)...**（命令 ID：`UG_EDIT_DELETE`）。
3. 可直接使用快捷键 **Ctrl+D** 调用（该快捷键来自介质 `.btn` 定义）。
4. 按对话框提示操作：删除对象。
5. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：删除对象。
    - 检索同义词：remove, eliminate, delete item, delete many, delete all, delete a view, remove rows, delete sheets, erasing a note, delete a table

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 7.8 功能点：移动对象  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_EDIT_MOVE_OBJECT`
- **菜单路径**：编辑(E) › 移动对象(O)...
- **快捷键**：`Ctrl+T`
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 4 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E)**。
2. 在展开项中选择 **移动对象(O)...**（命令 ID：`UG_EDIT_MOVE_OBJECT`）。
3. 可直接使用快捷键 **Ctrl+T** 调用（该快捷键来自介质 `.btn` 定义）。
4. 按对话框提示操作：移动或旋转选定的对象。
5. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：移动或旋转选定的对象。
    - 检索同义词：copy, transform, translate, position, rotate a table 90 degrees, move a table

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 7.9 功能点：编辑对象显示  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_EDIT_OBJECT_DISPLAY`
- **菜单路径**：编辑(E) › 对象显示(J)...
- **快捷键**：`Ctrl+J`
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 9 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E)**。
2. 在展开项中选择 **对象显示(J)...**（命令 ID：`UG_EDIT_OBJECT_DISPLAY`）。
3. 可直接使用快捷键 **Ctrl+J** 调用（该快捷键来自介质 `.btn` 定义）。
4. 按对话框提示操作：修改对象的图层、颜色、线型、宽度、栅格数量、透明度、着色和分析显示状态。
5. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：修改对象的图层、颜色、线型、宽度、栅格数量、透明度、着色和分析显示状态。
    - 检索同义词：appearance, custom line color, line style, edit object display

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 7.10 功能点：粘贴  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_EDIT_PASTE`
- **菜单路径**：编辑(E) › 粘贴(P)
- **快捷键**：`Ctrl+V`
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 9 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E)**。
2. 在展开项中选择 **粘贴(P)**（命令 ID：`UG_EDIT_PASTE`）。
3. 可直接使用快捷键 **Ctrl+V** 调用（该快捷键来自介质 `.btn` 定义）。
4. 按对话框提示操作：从剪贴板粘贴对象。
5. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：从剪贴板粘贴对象。
    - 检索同义词：switch views to another sheet

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 7.11 功能点：属性  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_EDIT_PROPERTIES`
- **菜单路径**：编辑(E) › 属性(I)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 6 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E)**。
2. 在展开项中选择 **属性(I)...**（命令 ID：`UG_EDIT_PROPERTIES`）。
3. 按对话框提示操作：指派、复制、编辑、显示和删除对象名称和属性。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：指派、复制、编辑、显示和删除对象名称和属性。
    - 检索同义词：property, name, attribute

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 7.12 功能点：重做  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_EDIT_REDO`
- **菜单路径**：编辑(E) › 重做(R)
- **快捷键**：`Ctrl+Y`
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 8 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E)**。
2. 在展开项中选择 **重做(R)**（命令 ID：`UG_EDIT_REDO`）。
3. 可直接使用快捷键 **Ctrl+Y** 调用（该快捷键来自介质 `.btn` 定义）。
4. 按对话框提示操作：重新执行上一个撤消的操作。
5. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：重新执行上一个撤消的操作。
    - 检索同义词：revert, restore, undo

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 7.13 功能点：编辑草图  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_EDIT_SKETCH`
- **菜单路径**：编辑(E) › 草图(K)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E)**。
2. 在展开项中选择 **草图(K)...**（命令 ID：`UG_EDIT_SKETCH`）。
3. 按对话框提示操作：激活选定草图从而使其可编辑。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：激活选定草图从而使其可编辑。
    - 检索同义词：edit string, edit profile, open sketch, edit sketch, wireframe

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 7.14 功能点：编辑设置  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_EDIT_STYLE`
- **菜单路径**：编辑(E) › 设置(S)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 4 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E)**。
2. 在展开项中选择 **设置(S)...**（命令 ID：`UG_EDIT_STYLE`）。
3. 按对话框提示操作：编辑选定制图对象的设置。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：编辑选定制图对象的设置。
    - 检索同义词：notes, fonts, text, appearance, look, properties, shaded views in drawings, modifying view and edge display, word wrap table text, define repeat regions, specifying the view scale, true length

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 7.15 功能点：变换  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_EDIT_TRANSFORM`
- **菜单路径**：编辑(E) › 变换(M)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E)**。
2. 在展开项中选择 **变换(M)...**（命令 ID：`UG_EDIT_TRANSFORM`）。
3. 按对话框提示操作：缩放、镜像、拟合对象，或者创建对象的阵列或对象的副本。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：缩放、镜像、拟合对象，或者创建对象的阵列或对象的副本。
    - 检索同义词：move, copy, shear, 3-point fit, 4-point fit

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 7.16 功能点：撤消  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_EDIT_UNDO`
- **菜单路径**：编辑(E) › 撤消
- **快捷键**：`Ctrl+Z`
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 9 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E)**。
2. 在展开项中选择 **撤消**（命令 ID：`UG_EDIT_UNDO`）。
3. 可直接使用快捷键 **Ctrl+Z** 调用（该快捷键来自介质 `.btn` 定义）。
4. 按对话框提示操作：撤消上次操作。
5. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：撤消上次操作。
    - 检索同义词：revert, restore, redo

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 7.17 功能点：编辑剖视图  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_CUT_VIEW_EDIT`
- **菜单路径**：编辑(E) › 剖视图(W)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E)**。
2. 在展开项中选择 **剖视图(W)...**（命令 ID：`UG_PMI_CUT_VIEW_EDIT`）。
3. 按对话框提示操作：编辑工作视图中的 3D 剖切。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：编辑工作视图中的 3D 剖切。
    - 检索同义词：cut, slice

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 7.18 功能点：编辑剖视图  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_LIGHTWEIGHT_SECTION_VIEW_EDIT`
- **菜单路径**：编辑(E) › 剖视图(W)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E)**。
2. 在展开项中选择 **剖视图(W)...**（命令 ID：`UG_PMI_LIGHTWEIGHT_SECTION_VIEW_EDIT`）。
3. 按对话框提示操作：编辑 3D 剖视图。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：编辑 3D 剖视图。
    - 检索同义词：cut, slice

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 7.19 功能点：更多  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_SC_MORE`
- **菜单路径**：编辑(E) › 更多；编辑(E) › 选择(L) › 更多
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 7 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E)**。
2. 在展开项中选择 **更多**（命令 ID：`UG_SC_MORE`）。
3. 按对话框提示操作：提供选择意图规则的附加选项。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：提供选择意图规则的附加选项。
    - 可用性提示：EXCLUDE_FROM_COMMAND_FINDER
    - 检索同义词：link, WAVE

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 8. 子模块：PMI

本子模块 16 个功能点。

### 8.1 功能点：继承 PMI 跟踪  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_INHERIT_PMI_TRACKING`
- **菜单路径**：格式(R) › PMI › 继承 PMI 跟踪...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **格式(R) › PMI**。
2. 在展开项中选择 **继承 PMI 跟踪...**（命令 ID：`UG_INHERIT_PMI_TRACKING`）。
3. 按对话框提示操作：编辑继承到图纸的 PMI 的跟踪状态。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：编辑继承到图纸的 PMI 的跟踪状态。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 8.2 功能点：符号注释  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_BALLOON_NOTE`
- **菜单路径**：PMI › 符号标注(B)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI**。
2. 在展开项中选择 **符号标注(B)...**（命令 ID：`UG_PMI_BALLOON_NOTE`）。
3. 按对话框提示操作：创建符号注释。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建符号注释。
    - 检索同义词：pmi

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 8.3 功能点：特征控制框  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_CRE_GDT_SYMBOLS`
- **菜单路径**：PMI › 特征控制框(F)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI**。
2. 在展开项中选择 **特征控制框(F)...**（命令 ID：`UG_PMI_CRE_GDT_SYMBOLS`）。
3. 按对话框提示操作：创建单行、多行或复合的特征控制框。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建单行、多行或复合的特征控制框。
    - 检索同义词：geometric tolerance, pmi

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 8.4 功能点：注释  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_CRE_NOTES_LABELS`
- **菜单路径**：PMI › 注释(N)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI**。
2. 在展开项中选择 **注释(N)...**（命令 ID：`UG_PMI_CRE_NOTES_LABELS`）。
3. 按对话框提示操作：创建注释。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建注释。
    - 检索同义词：text, label, notation, pmi

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 8.5 功能点：焊接符号  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_CRE_WELD_SYMBOL`
- **菜单路径**：PMI › 焊接符号(W)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI**。
2. 在展开项中选择 **焊接符号(W)...**（命令 ID：`UG_PMI_CRE_WELD_SYMBOL`）。
3. 按对话框提示操作：创建关联焊接符号。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建关联焊接符号。
    - 检索同义词：pmi

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 8.6 功能点：剖视图（原）  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_CUT_VIEW_CREATE`
- **菜单路径**：PMI › 剖视图（原有）(V)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI**。
2. 在展开项中选择 **剖视图（原有）(V)...**（命令 ID：`UG_PMI_CUT_VIEW_CREATE`）。
3. 按对话框提示操作：在模型中创建剖切并在 3D 剖视图中显示结果。这是原剖视图命令。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在模型中创建剖切并在 3D 剖视图中显示结果。这是原剖视图命令。
    - 可用性提示：EXCLUDE_FROM_COMMAND_FINDER

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 8.7 功能点：基准特征符号  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_DATUM`
- **菜单路径**：PMI › 基准特征符号(A)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI**。
2. 在展开项中选择 **基准特征符号(A)...**（命令 ID：`UG_PMI_DATUM`）。
3. 按对话框提示操作：创建基准特征符号。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建基准特征符号。
    - 检索同义词：datum tag, pmi

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 8.8 功能点：基准目标  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_DATUM_TARGET`
- **菜单路径**：PMI › 基准目标(T)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI**。
2. 在展开项中选择 **基准目标(T)...**（命令 ID：`UG_PMI_DATUM_TARGET`）。
3. 按对话框提示操作：创建基准目标。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建基准目标。
    - 检索同义词：locator, datum tag, pmi

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 8.9 功能点：PMI 剖视图  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_LIGHTWEIGHT_SECTION_VIEW_CREATE`
- **菜单路径**：PMI › 剖视图(C)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI**。
2. 在展开项中选择 **剖视图(C)...**（命令 ID：`UG_PMI_LIGHTWEIGHT_SECTION_VIEW_CREATE`）。
3. 按对话框提示操作：创建模型的剖视图并在 3D 剖视图中显示结果。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建模型的剖视图并在 3D 剖视图中显示结果。
    - 检索同义词：slice, pmi, lightweight

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 8.10 功能点：查找与几何体关联的 PMI  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_QUERY`
- **菜单路径**：信息(I) › PMI › 查找与几何体关联的 PMI...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **信息(I) › PMI**。
2. 在展开项中选择 **查找与几何体关联的 PMI...**（命令 ID：`UG_PMI_QUERY`）。
3. 按对话框提示操作：查找与选定几何体关联的所有 PMI 对象。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：查找与选定几何体关联的所有 PMI 对象。
    - 检索同义词：search, locate, query

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 8.11 功能点：PMI 报告  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_REPORT`
- **菜单路径**：信息(I) › PMI › 报告(R)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **信息(I) › PMI**。
2. 在展开项中选择 **报告(R)...**（命令 ID：`UG_PMI_REPORT`）。
3. 按对话框提示操作：产生一个电子表格报告，其中报告工作部件中选定的 PMI。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：产生一个电子表格报告，其中报告工作部件中选定的 PMI。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 8.12 功能点：重置所有 PMI 设置  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_RESET_SIZE`
- **菜单路径**：PMI › 重置所有 PMI 设置
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI**。
2. 在展开项中选择 **重置所有 PMI 设置**（命令 ID：`UG_PMI_RESET_SIZE`）。
3. 按对话框提示操作：将工作部件中所有 PMI 的大小重置为当前的部件首选项。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将工作部件中所有 PMI 的大小重置为当前的部件首选项。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 8.13 功能点：调整 PMI 大小  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_RESIZE`
- **菜单路径**：PMI › 调整大小(R)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI**。
2. 在展开项中选择 **调整大小(R)**（命令 ID：`UG_PMI_RESIZE`）。
3. 按对话框提示操作：在活动视图中调整 PMI 符号大小。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在活动视图中调整 PMI 符号大小。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 8.14 功能点：PMI 搜索  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_SEARCH`
- **菜单路径**：信息(I) › PMI › 搜索(S)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **信息(I) › PMI**。
2. 在展开项中选择 **搜索(S)...**（命令 ID：`UG_PMI_SEARCH`）。
3. 按对话框提示操作：基于各类搜索准则搜索 PMI 对象。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：基于各类搜索准则搜索 PMI 对象。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 8.15 功能点：抑制 PMI 对象  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_SUPPRESS_OBJECT`
- **菜单路径**：PMI › 抑制 PMI 对象(U)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI**。
2. 在展开项中选择 **抑制 PMI 对象(U)**（命令 ID：`UG_PMI_SUPPRESS_OBJECT`）。
3. 按对话框提示操作：通过表达式或手动抑制选定的 PMI。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：通过表达式或手动抑制选定的 PMI。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 8.16 功能点：表  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_TABLE_CREATE`
- **菜单路径**：PMI › 表(T)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI**。
2. 在展开项中选择 **表(T)...**（命令 ID：`UG_PMI_TABLE_CREATE`）。
3. 按对话框提示操作：创建信息表。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建信息表。
    - 检索同义词：Tabular Note, Tabulation, Row, Column

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 9. 子模块：专用(Z)

本子模块 13 个功能点。

### 9.1 功能点：坐标注释  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_COORDINATE_SYMBOL`
- **菜单路径**：PMI › 专用(Z) › 坐标注释(O)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI › 专用(Z)**。
2. 在展开项中选择 **坐标注释(O)...**（命令 ID：`UG_PMI_COORDINATE_SYMBOL`）。
3. 按对话框提示操作：将坐标注释与模型中的点相关联。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将坐标注释与模型中的点相关联。
    - 检索同义词：pmi

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 9.2 功能点：企业标识  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_ENTERPRISE_IDENTIFIER`
- **菜单路径**：PMI › 专用(Z) › 企业标识(E)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI › 专用(Z)**。
2. 在展开项中选择 **企业标识(E)...**（命令 ID：`UG_PMI_ENTERPRISE_IDENTIFIER`）。
3. 按对话框提示操作：将公司信息与模型相关联。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将公司信息与模型相关联。
    - 检索同义词：pmi

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 9.3 功能点：一般注释  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_GENERAL_NOTE`
- **菜单路径**：PMI › 专用(Z) › 一般注释(G)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI › 专用(Z)**。
2. 在展开项中选择 **一般注释(G)...**（命令 ID：`UG_PMI_GENERAL_NOTE`）。
3. 按对话框提示操作：将一般注释与模型相关联。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将一般注释与模型相关联。
    - 检索同义词：pmi

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 9.4 功能点：整数注释  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_INTEGER`
- **菜单路径**：PMI › 专用(Z) › 整数注释(I)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI › 专用(Z)**。
2. 在展开项中选择 **整数注释(I)...**（命令 ID：`UG_PMI_INTEGER`）。
3. 按对话框提示操作：将整型值注释与模型相关联。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将整型值注释与模型相关联。
    - 检索同义词：pmi

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 9.5 功能点：定位器指示符  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_LOCATOR`
- **菜单路径**：PMI › 专用(Z) › 定位器指示符(L)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI › 专用(Z)**。
2. 在展开项中选择 **定位器指示符(L)...**（命令 ID：`UG_PMI_LOCATOR`）。
3. 按对话框提示操作：创建定位器指示符，它在部件上标记特征（例如孔）以使组件相互精确定位。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建定位器指示符，它在部件上标记特征（例如孔）以使组件相互精确定位。
    - 检索同义词：pmi

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 9.6 功能点：材料规格  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_MATERIAL_SPECIFICATION`
- **菜单路径**：PMI › 专用(Z) › 材料规格(M)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI › 专用(Z)**。
2. 在展开项中选择 **材料规格(M)...**（命令 ID：`UG_PMI_MATERIAL_SPECIFICATION`）。
3. 按对话框提示操作：将材料参数与模型相关联。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将材料参数与模型相关联。
    - 检索同义词：pmi

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 9.7 功能点：数字注释  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_NUMBER`
- **菜单路径**：PMI › 专用(Z) › 数字注释(B)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI › 专用(Z)**。
2. 在展开项中选择 **数字注释(B)...**（命令 ID：`UG_PMI_NUMBER`）。
3. 按对话框提示操作：将数值注释与模型相关联。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将数值注释与模型相关联。
    - 检索同义词：pmi

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 9.8 功能点：部件标识  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_PART_ID`
- **菜单路径**：PMI › 专用(Z) › 部件标识(P)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI › 专用(Z)**。
2. 在展开项中选择 **部件标识(P)...**（命令 ID：`UG_PMI_PART_ID`）。
3. 按对话框提示操作：将部件信息与模型相关联。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将部件信息与模型相关联。
    - 检索同义词：pmi

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 9.9 功能点：工艺说明  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_PROCESS_SPEC`
- **菜单路径**：PMI › 专用(Z) › 工艺说明(R)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI › 专用(Z)**。
2. 在展开项中选择 **工艺说明(R)...**（命令 ID：`UG_PMI_PROCESS_SPEC`）。
3. 按对话框提示操作：将工艺说明与模型相关联。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将工艺说明与模型相关联。
    - 检索同义词：pmi

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 9.10 功能点：特定注释  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_SPECIFIC_NOTE`
- **菜单路径**：PMI › 专用(Z) › 特定注释(S)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI › 专用(Z)**。
2. 在展开项中选择 **特定注释(S)...**（命令 ID：`UG_PMI_SPECIFIC_NOTE`）。
3. 按对话框提示操作：将注释与模型中特定的几何体相关联。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将注释与模型中特定的几何体相关联。
    - 检索同义词：pmi

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 9.11 功能点：字符串注释  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_STRING`
- **菜单路径**：PMI › 专用(Z) › 字符串注释(T)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI › 专用(Z)**。
2. 在展开项中选择 **字符串注释(T)...**（命令 ID：`UG_PMI_STRING`）。
3. 按对话框提示操作：将文本注释与模型相关联。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将文本注释与模型相关联。
    - 检索同义词：pmi

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 9.12 功能点：URL 注释  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_URL_NOTE`
- **菜单路径**：PMI › 专用(Z) › URL 注释...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI › 专用(Z)**。
2. 在展开项中选择 **URL 注释...**（命令 ID：`UG_PMI_URL_NOTE`）。
3. 按对话框提示操作：将 URL 链接注释与模型相关联。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将 URL 链接注释与模型相关联。
    - 检索同义词：pmi

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 9.13 功能点：用户定义 PMI  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_USER_DEFINED`
- **菜单路径**：PMI › 专用(Z) › 用户定义(D)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI › 专用(Z)**。
2. 在展开项中选择 **用户定义(D)...**（命令 ID：`UG_PMI_USER_DEFINED`）。
3. 按对话框提示操作：创建用户定义 PMI 注释。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建用户定义 PMI 注释。
    - 检索同义词：user-defined

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 10. 子模块：制图布局

本子模块 13 个功能点。

### 10.1 功能点：符号(Y)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_CRE_ALL_SYMBOLS`
- **来源提示**：`nx_layout_app.men`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 3 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/nx_layout_app_men_simpl_chinese.txt` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_app.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「符号(Y)」定位。
2. 按对话框提示操作：列出制图符号命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出制图符号命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 10.2 功能点：注释(A)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_CRE_ANNOTATION`
- **来源提示**：`nx_layout_app.men`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 3 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/nx_layout_app_men_simpl_chinese.txt` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_app.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「注释(A)」定位。
2. 按对话框提示操作：列出图纸注释命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出图纸注释命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 10.3 功能点：中心线(E)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_CRE_CENTERLINES`
- **来源提示**：`nx_layout_app.men`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 3 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/nx_layout_app_men_simpl_chinese.txt` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_app.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「中心线(E)」定位。
2. 按对话框提示操作：列出制图中心线命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出制图中心线命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 10.4 功能点：尺寸(M)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_CRE_DIMENSIONS`
- **来源提示**：`nx_layout_app.men`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 3 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/nx_layout_app_men_simpl_chinese.txt` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_app.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「尺寸(M)」定位。
2. 按对话框提示操作：列出图纸尺寸命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出图纸尺寸命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 10.5 功能点：视图(W)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_CRE_VIEW`
- **来源提示**：`nx_layout_app.men`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 2 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/nx_layout_app_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_app.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「视图(W)」定位。
2. 按对话框提示操作：列出图纸视图命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出图纸视图命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 10.6 功能点：视图(W)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_EDIT_VIEW`
- **来源提示**：`nx_layout_app.men`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 2 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/nx_layout_app_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_app.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「视图(W)」定位。
2. 按对话框提示操作：列出图纸编辑视图命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出图纸编辑视图命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 10.7 功能点：退出  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_FILE_QUIT`
- **菜单路径**：文件(F) › 退出(X)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **来源提示**：`nx_layout_te.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 5 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/nx_layout_te_men_simpl_chinese.txt` 等 4 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **文件(F)**。
2. 在展开项中选择 **退出(X)**（命令 ID：`UG_FILE_QUIT`）。
3. 按对话框提示操作：结束会话并显示有关未保存已修改文件的警告。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：结束会话并显示有关未保存已修改文件的警告。
    - 检索同义词：quit, bye, finish, stop

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 10.8 功能点：2D 组件顺序  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_NXLAYOUT_2D_COMPONENT_NAVIGATOR_ORDER`
- **来源提示**：`nx_layout_app.men`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men`
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/nx_layout_app_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_app.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「2D 组件顺序」定位。
2. 按对话框提示操作：列出 2D 组件布局顺序命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出 2D 组件布局顺序命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 10.9 功能点：显示几何体颜色(C)  `[NX12.0-CN] [E4-TRANSLATION]`

- **命令 ID**：`UG_NXLAYOUT_DISPLAY_GEOMETRY_COLOR`
- **来源提示**：`nx_layout_app.men`
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/nx_layout_app_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令为 **E4-TRANSLATION**：中文名/功能说明来自官方简体中文翻译表（`nx_layout_app.men`），但 `.men/.btn` 菜单源未随当前介质提供；[待实测] 在对应应用模块中通过 `帮助(H) › 命令查找器(F)` 搜索「显示几何体颜色(C)」定位实际菜单路径。
2. 按对话框提示操作：在对象显示属性中指定的颜色与草图颜色之间切换布局几何体的显示。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在对象显示属性中指定的颜色与草图颜色之间切换布局几何体的显示。

**注意事项**：

    - 该命令来自官方简体中文翻译表（E4），中文名/功能说明可信；但菜单路径、快捷键、参数对话框未随介质提供，必须在 NX 12.0 中文界面 GUI 复核后使用。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 10.10 功能点：2D 组件(N)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_NXLAYOUT_EDIT_2D_COMPONENTS`
- **来源提示**：`nx_layout_app.men`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 3 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/nx_layout_app_men_simpl_chinese.txt` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_app.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「2D 组件(N)」定位。
2. 按对话框提示操作：列出 2D 组件编辑命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出 2D 组件编辑命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 10.11 功能点：2D 组件(N)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_NXLAYOUT_INSERT_2D_COMPONENTS`
- **来源提示**：`nx_layout_app.men`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 3 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/nx_layout_app_men_simpl_chinese.txt` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_app.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「2D 组件(N)」定位。
2. 按对话框提示操作：列出 2D 组件插入命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出 2D 组件插入命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 10.12 功能点：新建布局  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_NXLAYOUT_INSERT_LAYOUT`
- **来源提示**：`nx_layout_app.men`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men`
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/nx_layout_app_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_app.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「新建布局」定位。
2. 按对话框提示操作：为 2D 设计创建新的布局。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：为 2D 设计创建新的布局。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 10.13 功能点：布局(T)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_NXLAYOUT_LAYOUT_COMMANDS`
- **来源提示**：`nx_layout_app.men`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 2 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/nx_layout_app_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_app.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「布局(T)」定位。
2. 按对话框提示操作：列出布局命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出布局命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 11. 子模块：操作(O)

本子模块 13 个功能点。

### 11.1 功能点：设置镜像平面...  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_INFO_ANALYSIS_MIRROR_DISP_PL`
- **菜单路径**：视图(V) › 操作(O) › 设置镜像平面(L)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **视图(V) › 操作(O)**。
2. 在展开项中选择 **设置镜像平面(L)...**（命令 ID：`UG_INFO_ANALYSIS_MIRROR_DISP_PL`）。
3. 按对话框提示操作：重新定义用于“镜像显示”选项的镜像平面。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：重新定义用于“镜像显示”选项的镜像平面。
    - 检索同义词：reflect, symmetric

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 11.2 功能点：根据选择调整视图  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_SEL_FIT_VIEW`
- **菜单路径**：视图(V) › 操作(O) › 根据选择调整视图(V)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **视图(V) › 操作(O)**。
2. 在展开项中选择 **根据选择调整视图(V)**（命令 ID：`UG_SEL_FIT_VIEW`）。
3. 按对话框提示操作：使工作视图适合当前选定的对象。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：使工作视图适合当前选定的对象。
    - 检索同义词：zoom, magnify

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 11.3 功能点：重新生成工作视图  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_VIEW_EDIT_REGEN_WORK`
- **菜单路径**：视图(V) › 操作(O) › 重新生成工作视图(G)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **视图(V) › 操作(O)**。
2. 在展开项中选择 **重新生成工作视图(G)**（命令 ID：`UG_VIEW_EDIT_REGEN_WORK`）。
3. 按对话框提示操作：重新生成工作视图以擦除临时显示的对象并更新已修改几何体的显示。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：重新生成工作视图以擦除临时显示的对象并更新已修改几何体的显示。
    - 检索同义词：repaint

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 11.4 功能点：适合窗口  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_VIEW_FIT`
- **菜单路径**：视图(V) › 操作(O) › 适合窗口(F)
- **快捷键**：`Ctrl+F`
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **视图(V) › 操作(O)**。
2. 在展开项中选择 **适合窗口(F)**（命令 ID：`UG_VIEW_FIT`）。
3. 可直接使用快捷键 **Ctrl+F** 调用（该快捷键来自介质 `.btn` 定义）。
4. 按对话框提示操作：调整工作视图的中心和比例以显示所有对象。
5. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：调整工作视图的中心和比例以显示所有对象。
    - 检索同义词：maximize, zoom, magnify, fit view

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 11.5 功能点：非比例缩放选项...  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_VIEW_NON_PZOOM_PL`
- **菜单路径**：视图(V) › 操作(O) › 非比例缩放选项(I)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **视图(V) › 操作(O)**。
2. 在展开项中选择 **非比例缩放选项(I)...**（命令 ID：`UG_VIEW_NON_PZOOM_PL`）。
3. 按对话框提示操作：重新定义非比例缩放的方法、锚点中心及灵敏度。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：重新定义非比例缩放的方法、锚点中心及灵敏度。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 11.6 功能点：定向  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_VIEW_ORIENT`
- **菜单路径**：视图(V) › 操作(O) › 定向(E)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **视图(V) › 操作(O)**。
2. 在展开项中选择 **定向(E)...**（命令 ID：`UG_VIEW_ORIENT`）。
3. 按对话框提示操作：将工作视图定向到指定的坐标系。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将工作视图定向到指定的坐标系。
    - 检索同义词：orientation, orient view

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 11.7 功能点：视图原点  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_VIEW_ORIGIN`
- **菜单路径**：视图(V) › 操作(O) › 原点(O)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **视图(V) › 操作(O)**。
2. 在展开项中选择 **原点(O)...**（命令 ID：`UG_VIEW_ORIGIN`）。
3. 按对话框提示操作：更改工作视图的中心。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：更改工作视图的中心。
    - 检索同义词：center of rotation, view origin

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 11.8 功能点：刷新  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_VIEW_REFRESH`
- **菜单路径**：视图(V) › 操作(O) › 刷新(H)
- **快捷键**：`F5`
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **视图(V) › 操作(O)**。
2. 在展开项中选择 **刷新(H)**（命令 ID：`UG_VIEW_REFRESH`）。
3. 可直接使用快捷键 **F5** 调用（该快捷键来自介质 `.btn` 定义）。
4. 按对话框提示操作：重画图形窗口中的所有视图，（例如）以擦除临时显示的对象。
5. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：重画图形窗口中的所有视图，（例如）以擦除临时显示的对象。
    - 检索同义词：reset, redisplay

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 11.9 功能点：恢复工作视图  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_VIEW_RESTORE_ORIGINAL`
- **菜单路径**：视图(V) › 操作(O) › 恢复(E)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **视图(V) › 操作(O)**。
2. 在展开项中选择 **恢复(E)**（命令 ID：`UG_VIEW_RESTORE_ORIGINAL`）。
3. 按对话框提示操作：将工作视图恢复为上次视图操作之前的方向和比例。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将工作视图恢复为上次视图操作之前的方向和比例。
    - 检索同义词：undo, reset

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 11.10 功能点：旋转视图  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_VIEW_ROTATE`
- **菜单路径**：视图(V) › 操作(O) › 旋转(R)...
- **快捷键**：`Ctrl+R`
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **视图(V) › 操作(O)**。
2. 在展开项中选择 **旋转(R)...**（命令 ID：`UG_VIEW_ROTATE`）。
3. 可直接使用快捷键 **Ctrl+R** 调用（该快捷键来自介质 `.btn` 定义）。
4. 按对话框提示操作：使用鼠标围绕特定的轴旋转视图，或将其旋转至特定的视图方向。
5. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：使用鼠标围绕特定的轴旋转视图，或将其旋转至特定的视图方向。
    - 检索同义词：spin, dynamic rotation, rotate view

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 11.11 功能点：设置视图至 WCS  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_VIEW_SET_TO_WCS`
- **菜单路径**：视图(V) › 操作(O) › 设置视图至 WCS
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 8 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **视图(V) › 操作(O)**。
2. 在展开项中选择 **设置视图至 WCS**（命令 ID：`UG_VIEW_SET_TO_WCS`）。
3. 按对话框提示操作：将工作视图定向到 WCS 的 XC-YC 平面。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将工作视图定向到 WCS 的 XC-YC 平面。
    - 检索同义词：view workplane

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 11.12 功能点：取消缩放  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_VIEW_UNZOOM`
- **菜单路径**：视图(V) › 操作(O) › 取消缩放(U)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **视图(V) › 操作(O)**。
2. 在展开项中选择 **取消缩放(U)**（命令 ID：`UG_VIEW_UNZOOM`）。
3. 按对话框提示操作：通过反转上次缩放操作来缩放视图。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：通过反转上次缩放操作来缩放视图。
    - 检索同义词：undo

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 11.13 功能点：缩放  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_VIEW_ZOOM`
- **菜单路径**：视图(V) › 操作(O) › 缩放(Z)...
- **快捷键**：`Ctrl+Shift+Z`
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **视图(V) › 操作(O)**。
2. 在展开项中选择 **缩放(Z)...**（命令 ID：`UG_VIEW_ZOOM`）。
3. 可直接使用快捷键 **Ctrl+Shift+Z** 调用（该快捷键来自介质 `.btn` 定义）。
4. 按对话框提示操作：放大或缩小工作视图。
5. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：放大或缩小工作视图。
    - 检索同义词：increase, decrease, scale, magnify, zoom view

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 12. 子模块：几何公差(M)

本子模块 11 个功能点。

### 12.1 功能点：转换非关联公差  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_GDT_CONVERT_NONASSOCIATE_TOLERANCES`
- **菜单路径**：几何公差(M) › 转换非关联公差(C)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **几何公差(M)**。
2. 在展开项中选择 **转换非关联公差(C)...**（命令 ID：`UG_PMI_GDT_CONVERT_NONASSOCIATE_TOLERANCES`）。
3. 按对话框提示操作：将在制图中创建的形位公差符号转换为公差特征，并将它们与模型特征关联。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将在制图中创建的形位公差符号转换为公差特征，并将它们与模型特征关联。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 12.2 功能点：基准参考框编辑器  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_GDT_DATUM_REFERENCE_FRAME_EDITOR`
- **菜单路径**：几何公差(M) › 基准参考框编辑器(D)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **几何公差(M)**。
2. 在展开项中选择 **基准参考框编辑器(D)...**（命令 ID：`UG_PMI_GDT_DATUM_REFERENCE_FRAME_EDITOR`）。
3. 按对话框提示操作：创建和编辑可重用的基准参考框。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建和编辑可重用的基准参考框。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 12.3 功能点：删除公差特征  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_GDT_DELETE_TOLERANCE_FEATURE`
- **菜单路径**：几何公差(M) › 删除公差特征(E)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **几何公差(M)**。
2. 在展开项中选择 **删除公差特征(E)...**（命令 ID：`UG_PMI_GDT_DELETE_TOLERANCE_FEATURE`）。
3. 按对话框提示操作：从数据库中删除公差特征，并从图形窗口中删除该公差特征的所有显示实例。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：从数据库中删除公差特征，并从图形窗口中删除该公差特征的所有显示实例。

**注意事项**：

    - 特征类命令注意参数关联性；修改后需重算并检查特征导航器是否报错。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 12.4 功能点：显示实例编辑器  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_GDT_DISPLAY_INSTANCE_EDITOR`
- **菜单路径**：几何公差(M) › 显示实例编辑器(I)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **几何公差(M)**。
2. 在展开项中选择 **显示实例编辑器(I)...**（命令 ID：`UG_PMI_GDT_DISPLAY_INSTANCE_EDITOR`）。
3. 按对话框提示操作：创建和编辑公差显示实例。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建和编辑公差显示实例。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 12.5 功能点：公差特征关联对象  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_GDT_GEOMETRIC_TOLERANCING_ASSOCIATED`
- **菜单路径**：几何公差(M) › 关联对象(A)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **几何公差(M)**。
2. 在展开项中选择 **关联对象(A)...**（命令 ID：`UG_PMI_GDT_GEOMETRIC_TOLERANCING_ASSOCIATED`）。
3. 按对话框提示操作：基于公差特征、公差索引、基准、基准参考框、几何索引和链接特征，查找关联的 PMI 形位公差对象。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：基于公差特征、公差索引、基准、基准参考框、几何索引和链接特征，查找关联的 PMI 形位公差对象。
    - 检索同义词：gdt associated objects, gd&t associated objects

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 12.6 功能点：列出所有公差特征  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_GDT_GEOMETRIC_TOLERANCING_LIST_ALL`
- **菜单路径**：几何公差(M) › 全部列出(L)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **几何公差(M)**。
2. 在展开项中选择 **全部列出(L)...**（命令 ID：`UG_PMI_GDT_GEOMETRIC_TOLERANCING_LIST_ALL`）。
3. 按对话框提示操作：列出关于公差特征的所有信息。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出关于公差特征的所有信息。
    - 检索同义词：gdt list all, gd&t list all

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 12.7 功能点：公差特征搜索  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_GDT_GEOMETRIC_TOLERANCING_SEARCH`
- **菜单路径**：几何公差(M) › 搜索(S)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **几何公差(M)**。
2. 在展开项中选择 **搜索(S)...**（命令 ID：`UG_PMI_GDT_GEOMETRIC_TOLERANCING_SEARCH`）。
3. 按对话框提示操作：基于指定准则搜索公差特征。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：基于指定准则搜索公差特征。
    - 检索同义词：find, locate, gdt search, gd&t search

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 12.8 功能点：主模型公差  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_GDT_MASTER_MODEL_TOLERANCING`
- **菜单路径**：几何公差(M) › 主模型公差(M)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **几何公差(M)**。
2. 在展开项中选择 **主模型公差(M)...**（命令 ID：`UG_PMI_GDT_MASTER_MODEL_TOLERANCING`）。
3. 按对话框提示操作：将公差特征数据从装配组件向上拖动至父装配部件。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将公差特征数据从装配组件向上拖动至父装配部件。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 12.9 功能点：几何公差  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_GDT_TOLERANCE_FEATURE_EDITOR`
- **菜单路径**：几何公差(M) › 公差特征编辑器(T)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **几何公差(M)**。
2. 在展开项中选择 **公差特征编辑器(T)...**（命令 ID：`UG_PMI_GDT_TOLERANCE_FEATURE_EDITOR`）。
3. 按对话框提示操作：在模型中创建、编辑和定位公差特征。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在模型中创建、编辑和定位公差特征。
    - 检索同义词：tolerance feature editor

**注意事项**：

    - 特征类命令注意参数关联性；修改后需重算并检查特征导航器是否报错。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 12.10 功能点：公差特征更新报告  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_GDT_UPDATE_REPORT`
- **菜单路径**：几何公差(M) › 更新报告(U)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **几何公差(M)**。
2. 在展开项中选择 **更新报告(U)...**（命令 ID：`UG_PMI_GDT_UPDATE_REPORT`）。
3. 按对话框提示操作：列出与几何模型或公差规格本身不同步的公差特征。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出与几何模型或公差规格本身不同步的公差特征。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 12.11 功能点：验证公差规格  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_GDT_VALIDATE_TOLERANCE_SPECIFICATION`
- **菜单路径**：几何公差(M) › 验证公差规格(V)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **几何公差(M)**。
2. 在展开项中选择 **验证公差规格(V)**（命令 ID：`UG_PMI_GDT_VALIDATE_TOLERANCE_SPECIFICATION`）。
3. 按对话框提示操作：验证有关指定标准以及有关特征所关联的几何体和基准的公差特征语义和语法。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：验证有关指定标准以及有关特征所关联的几何体和基准的公差特征语义和语法。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 13. 子模块：工具(T)

本子模块 11 个功能点。

### 13.1 功能点：制图标准  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFTING_STANDARD`
- **菜单路径**：工具(T) › 制图标准(D)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T)**。
2. 在展开项中选择 **制图标准(D)...**（命令 ID：`UG_DRAFTING_STANDARD`）。
3. 按对话框提示操作：将由选定的用户默认制图标准定义的设置加载到会话中。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将由选定的用户默认制图标准定义的设置加载到会话中。
    - 检索同义词：load drafting standard

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 13.2 功能点：版本升级  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFTING_VERSION_UP`
- **菜单路径**：工具(T) › 版本更新(V)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T)**。
2. 在展开项中选择 **版本更新(V)...**（命令 ID：`UG_DRAFTING_VERSION_UP`）。
3. 按对话框提示操作：将部件中 PMI、制图对象和图纸视图的创建版本更新为当前 NX 版本。更新对象的版本可能会影响其显示和行为。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将部件中 PMI、制图对象和图纸视图的创建版本更新为当前 NX 版本。更新对象的版本可能会影响其显示和行为。
    - 检索同义词：change version, update version

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 13.3 功能点：转换为 PMI  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_DRAW_TO_PMI`
- **菜单路径**：工具(T) › 转换为 PMI(C)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T)**。
2. 在展开项中选择 **转换为 PMI(C)...**（命令 ID：`UG_DRAFT_DRAW_TO_PMI`）。
3. 按对话框提示操作：将图纸数据转换为相应的 PMI 对象。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将图纸数据转换为相应的 PMI 对象。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 13.4 功能点：复制到 3D  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_EDIT_VIEW_COPY3D`
- **菜单路径**：工具(T) › 复制到 3D...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T)**。
2. 在展开项中选择 **复制到 3D...**（命令 ID：`UG_DRAFT_EDIT_VIEW_COPY3D`）。
3. 按对话框提示操作：将曲线复制到 3D 建模空间。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将曲线复制到 3D 建模空间。
    - 可用性提示：This command is available only with the NX Layout license.
    - 检索同义词：export to solids, IDEAS

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 13.5 功能点：表达式  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_INSERT_DLEXPRESSION`
- **菜单路径**：工具(T) › 表达式(X)...
- **快捷键**：`Ctrl+E`
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 5 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T)**。
2. 在展开项中选择 **表达式(X)...**（命令 ID：`UG_INSERT_DLEXPRESSION`）。
3. 可直接使用快捷键 **Ctrl+E** 调用（该快捷键来自介质 `.btn` 定义）。
4. 按对话框提示操作：提供用于创建和修改表达式的选项。
5. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：提供用于创建和修改表达式的选项。
    - 检索同义词：parameters, function, formula, variable, part equations, relations, add param, delete param

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 13.6 功能点：从 3D 创建  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_NXLAYOUT_CREATE_2D_COMPONENT_FROM_3D`
- **菜单路径**：工具(T) › 从 3D 创建(C)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T)**。
2. 在展开项中选择 **从 3D 创建(C)...**（命令 ID：`UG_NXLAYOUT_CREATE_2D_COMPONENT_FROM_3D`）。
3. 按对话框提示操作：从模型/装配剖切或投影边创建一个或多个 2D 组件。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：从模型/装配剖切或投影边创建一个或多个 2D 组件。
    - 可用性提示：This command is available only with the NX Layout license.
    - 检索同义词：Create layout, 2D component

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 13.7 功能点：根据布局创建装配  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_NXLAYOUT_CREATE_ASSEMBY_FROM_LAYOUT2D`
- **菜单路径**：工具(T) › 根据布局创建装配(L)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T)**。
2. 在展开项中选择 **根据布局创建装配(L)...**（命令 ID：`UG_NXLAYOUT_CREATE_ASSEMBY_FROM_LAYOUT2D`）。
3. 按对话框提示操作：根据布局的内容创建装配。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：根据布局的内容创建装配。
    - 可用性提示：This command is available only with the NX Layout license.
    - 检索同义词：2D Layout, create assembly

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 13.8 功能点：电子表格  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TOOLBOX_SPREADSHEET`
- **菜单路径**：工具(T) › 电子表格(H)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T)**。
2. 在展开项中选择 **电子表格(H)...**（命令 ID：`UG_TOOLBOX_SPREADSHEET`）。
3. 按对话框提示操作：将模型数据从 NX 转移到电子表格。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将模型数据从 NX 转移到电子表格。
    - 检索同义词：Excel, Xess

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 13.9 功能点：单位转换器  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TOOLBOX_UNITS_CONVERTER`
- **菜单路径**：工具(T) › 单位转换器(O)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 7 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T)**。
2. 在展开项中选择 **单位转换器(O)...**（命令 ID：`UG_TOOLBOX_UNITS_CONVERTER`）。
3. 按对话框提示操作：计算单位转换。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：计算单位转换。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 13.10 功能点：单位管理器  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TOOLBOX_UNITS_MANAGER`
- **菜单路径**：工具(T) › 单位管理器(U)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 7 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T)**。
2. 在展开项中选择 **单位管理器(U)...**（命令 ID：`UG_TOOLBOX_UNITS_MANAGER`）。
3. 按对话框提示操作：创建新单位和单位制。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建新单位和单位制。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 13.11 功能点：可视编辑器（即将失效）  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TOOLBOX_VISUAL_EDITOR`
- **菜单路径**：工具(T) › 可视编辑器（即将失效）(V)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T)**。
2. 在展开项中选择 **可视编辑器（即将失效）(V)...**（命令 ID：`UG_TOOLBOX_VISUAL_EDITOR`）。
3. 按对话框提示操作：为模型的静态图形表示提供其相应的尺寸和表达式。首选使用产品模板工作室命令。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：为模型的静态图形表示提供其相应的尺寸和表达式。首选使用产品模板工作室命令。
    - 检索同义词：visual parameter editor

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 14. 子模块：选择(L)

本子模块 10 个功能点。

### 14.1 功能点：全部（选定的除外）  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_SEL_ALL_BUT_SELECTED`
- **菜单路径**：编辑(E) › 选择(L) › 全部（选定的除外）
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 选择(L)**。
2. 在展开项中选择 **全部（选定的除外）**（命令 ID：`UG_SEL_ALL_BUT_SELECTED`）。
3. 按对话框提示操作：取消选择所有当前选定的对象并选择所有其他可选对象。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：取消选择所有当前选定的对象并选择所有其他可选对象。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 14.2 功能点：圆  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_SEL_AREA_CIRCLE`
- **菜单路径**：编辑(E) › 选择(L) › 圆
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_title_block.men` 等 9 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 选择(L)**。
2. 在展开项中选择 **圆**（命令 ID：`UG_SEL_AREA_CIRCLE`）。
3. 按对话框提示操作：使用画圆动作进行多选。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：使用画圆动作进行多选。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 14.3 功能点：套索  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_SEL_AREA_LASSO`
- **菜单路径**：编辑(E) › 选择(L) › 套索
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 选择(L)**。
2. 在展开项中选择 **套索**（命令 ID：`UG_SEL_AREA_LASSO`）。
3. 按对话框提示操作：使用套索动作进行多选。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：使用套索动作进行多选。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 14.4 功能点：矩形  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_SEL_AREA_RECTANGLE`
- **菜单路径**：编辑(E) › 选择(L) › 矩形
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 选择(L)**。
2. 在展开项中选择 **矩形**（命令 ID：`UG_SEL_AREA_RECTANGLE`）。
3. 按对话框提示操作：使用矩形动作进行多选。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：使用矩形动作进行多选。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 14.5 功能点：颜色过滤器  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_SEL_COLOR_FILTER`
- **菜单路径**：编辑(E) › 选择(L) › 颜色过滤器
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 9 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 选择(L)**。
2. 在展开项中选择 **颜色过滤器**（命令 ID：`UG_SEL_COLOR_FILTER`）。
3. 按对话框提示操作：将选择范围过滤至指定颜色的对象。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将选择范围过滤至指定颜色的对象。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 14.6 功能点：全不选  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_SEL_DESELECT_ALL`
- **菜单路径**：编辑(E) › 选择(L) › 全不选(D)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 选择(L)**。
2. 在展开项中选择 **全不选(D)**（命令 ID：`UG_SEL_DESELECT_ALL`）。
3. 按对话框提示操作：取消选择所有当前选定的对象。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：取消选择所有当前选定的对象。
    - 检索同义词：clear

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 14.7 功能点：重置过滤器  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_SEL_RESET`
- **菜单路径**：编辑(E) › 选择(L) › 重置过滤器
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 选择(L)**。
2. 在展开项中选择 **重置过滤器**（命令 ID：`UG_SEL_RESET`）。
3. 按对话框提示操作：将所有过滤器选项（类型、颜色、图层过滤器）重置为它们的原始状态。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将所有过滤器选项（类型、颜色、图层过滤器）重置为它们的原始状态。
    - 检索同义词：behind

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 14.8 功能点：恢复  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_SEL_RESTORE_GLOBAL`
- **菜单路径**：编辑(E) › 选择(L) › 恢复(R)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 9 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 选择(L)**。
2. 在展开项中选择 **恢复(R)**（命令 ID：`UG_SEL_RESTORE_GLOBAL`）。
3. 按对话框提示操作：当从某一操作返回时，恢复全局选定的对象。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：当从某一操作返回时，恢复全局选定的对象。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 14.9 功能点：全选  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_SEL_SELECT_ALL`
- **菜单路径**：编辑(E) › 选择(L) › 全选(S)
- **快捷键**：`Ctrl+A`
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 选择(L)**。
2. 在展开项中选择 **全选(S)**（命令 ID：`UG_SEL_SELECT_ALL`）。
3. 可直接使用快捷键 **Ctrl+A** 调用（该快捷键来自介质 `.btn` 定义）。
4. 按对话框提示操作：基于选择过滤器选择所有可见对象。
5. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：基于选择过滤器选择所有可见对象。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 14.10 功能点：向上一级  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_SEL_UP_ONE_LEVEL`
- **菜单路径**：编辑(E) › 选择(L) › 向上一级(U)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 6 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 选择(L)**。
2. 在展开项中选择 **向上一级(U)**（命令 ID：`UG_SEL_UP_ONE_LEVEL`）。
3. 按对话框提示操作：如果为某个操作启用了组件或组，则选择层次结构中上一级的对象。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：如果为某个操作启用了组件或组，则选择层次结构中上一级的对象。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 15. 子模块：重复命令(R)

本子模块 10 个功能点。

### 15.1 功能点：重复上一命令  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TOOLS_REPEAT_LAST_COMMAND_0`
- **菜单路径**：工具(T) › 重复命令(R) › 重复上一命令
- **快捷键**：`F4`
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 18 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 重复命令(R)**。
2. 在展开项中选择 **重复上一命令**（命令 ID：`UG_TOOLS_REPEAT_LAST_COMMAND_0`）。
3. 可直接使用快捷键 **F4** 调用（该快捷键来自介质 `.btn` 定义）。
4. 按对话框提示操作：重复上一个使用的命令。
5. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：重复上一个使用的命令。
    - 检索同义词：previous, latest, most recent, action, do again, repeat command

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 15.2 功能点：重复上一命令  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TOOLS_REPEAT_LAST_COMMAND_1`
- **菜单路径**：工具(T) › 重复命令(R) › 重复上一命令
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 18 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 重复命令(R)**。
2. 在展开项中选择 **重复上一命令**（命令 ID：`UG_TOOLS_REPEAT_LAST_COMMAND_1`）。
3. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 15.3 功能点：重复上一命令  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TOOLS_REPEAT_LAST_COMMAND_2`
- **菜单路径**：工具(T) › 重复命令(R) › 重复上一命令
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 18 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 重复命令(R)**。
2. 在展开项中选择 **重复上一命令**（命令 ID：`UG_TOOLS_REPEAT_LAST_COMMAND_2`）。
3. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 15.4 功能点：重复上一命令  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TOOLS_REPEAT_LAST_COMMAND_3`
- **菜单路径**：工具(T) › 重复命令(R) › 重复上一命令
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 18 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 重复命令(R)**。
2. 在展开项中选择 **重复上一命令**（命令 ID：`UG_TOOLS_REPEAT_LAST_COMMAND_3`）。
3. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 15.5 功能点：重复上一命令  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TOOLS_REPEAT_LAST_COMMAND_4`
- **菜单路径**：工具(T) › 重复命令(R) › 重复上一命令
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 18 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 重复命令(R)**。
2. 在展开项中选择 **重复上一命令**（命令 ID：`UG_TOOLS_REPEAT_LAST_COMMAND_4`）。
3. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 15.6 功能点：重复上一命令  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TOOLS_REPEAT_LAST_COMMAND_5`
- **菜单路径**：工具(T) › 重复命令(R) › 重复上一命令
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 18 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 重复命令(R)**。
2. 在展开项中选择 **重复上一命令**（命令 ID：`UG_TOOLS_REPEAT_LAST_COMMAND_5`）。
3. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 15.7 功能点：重复上一命令  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TOOLS_REPEAT_LAST_COMMAND_6`
- **菜单路径**：工具(T) › 重复命令(R) › 重复上一命令
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 18 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 重复命令(R)**。
2. 在展开项中选择 **重复上一命令**（命令 ID：`UG_TOOLS_REPEAT_LAST_COMMAND_6`）。
3. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 15.8 功能点：重复上一命令  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TOOLS_REPEAT_LAST_COMMAND_7`
- **菜单路径**：工具(T) › 重复命令(R) › 重复上一命令
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 18 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 重复命令(R)**。
2. 在展开项中选择 **重复上一命令**（命令 ID：`UG_TOOLS_REPEAT_LAST_COMMAND_7`）。
3. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 15.9 功能点：重复上一命令  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TOOLS_REPEAT_LAST_COMMAND_8`
- **菜单路径**：工具(T) › 重复命令(R) › 重复上一命令
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 18 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 重复命令(R)**。
2. 在展开项中选择 **重复上一命令**（命令 ID：`UG_TOOLS_REPEAT_LAST_COMMAND_8`）。
3. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 15.10 功能点：重复上一命令  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TOOLS_REPEAT_LAST_COMMAND_9`
- **菜单路径**：工具(T) › 重复命令(R) › 重复上一命令
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 18 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 重复命令(R)**。
2. 在展开项中选择 **重复上一命令**（命令 ID：`UG_TOOLS_REPEAT_LAST_COMMAND_9`）。
3. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 16. 子模块：窗口布局(L)

本子模块 9 个功能点。

### 16.1 功能点：1 个选项卡式组  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_WINDOW_TILE_1`
- **菜单路径**：窗口布局(L) › 1 个选项卡式组
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 8 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **窗口布局(L)**。
2. 在展开项中选择 **1 个选项卡式组**（命令 ID：`UG_WINDOW_TILE_1`）。
3. 按对话框提示操作：使用 1 个选项卡式组的布局排列窗口。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：使用 1 个选项卡式组的布局排列窗口。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 16.2 功能点：2 个选项卡式组  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_WINDOW_TILE_1_1_HORIZ`
- **菜单路径**：窗口布局(L) › 2 个选项卡式组(T)
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 8 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **窗口布局(L)**。
2. 在展开项中选择 **2 个选项卡式组(T)**（命令 ID：`UG_WINDOW_TILE_1_1_HORIZ`）。
3. 按对话框提示操作：使用 2 个选项卡式组的布局排列窗口（水平）。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：使用 2 个选项卡式组的布局排列窗口（水平）。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 16.3 功能点：2 个选项卡式组  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_WINDOW_TILE_1_1_VERT`
- **菜单路径**：窗口布局(L) › 2 个选项卡式组
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 8 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **窗口布局(L)**。
2. 在展开项中选择 **2 个选项卡式组**（命令 ID：`UG_WINDOW_TILE_1_1_VERT`）。
3. 按对话框提示操作：使用 2 个选项卡式组的布局排列窗口（竖直）。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：使用 2 个选项卡式组的布局排列窗口（竖直）。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 16.4 功能点：3 个选项卡式组  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_WINDOW_TILE_1_2_HORIZ`
- **菜单路径**：窗口布局(L) › 3 个选项卡式组(A)
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 8 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **窗口布局(L)**。
2. 在展开项中选择 **3 个选项卡式组(A)**（命令 ID：`UG_WINDOW_TILE_1_2_HORIZ`）。
3. 按对话框提示操作：使用 3 个选项卡式组的布局排列窗口（水平，选项 1）。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：使用 3 个选项卡式组的布局排列窗口（水平，选项 1）。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 16.5 功能点：3 个选项卡式组  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_WINDOW_TILE_1_2_VERT`
- **菜单路径**：窗口布局(L) › 3 个选项卡式组
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 8 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **窗口布局(L)**。
2. 在展开项中选择 **3 个选项卡式组**（命令 ID：`UG_WINDOW_TILE_1_2_VERT`）。
3. 按对话框提示操作：使用 3 个选项卡式组的布局排列窗口（竖直，选项 1）。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：使用 3 个选项卡式组的布局排列窗口（竖直，选项 1）。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 16.6 功能点：3 个选项卡式组  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_WINDOW_TILE_2_1_HORIZ`
- **菜单路径**：窗口布局(L) › 3 个选项卡式组(B)
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 8 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **窗口布局(L)**。
2. 在展开项中选择 **3 个选项卡式组(B)**（命令 ID：`UG_WINDOW_TILE_2_1_HORIZ`）。
3. 按对话框提示操作：使用 3 个选项卡式组的布局排列窗口（水平，选项 2）。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：使用 3 个选项卡式组的布局排列窗口（水平，选项 2）。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 16.7 功能点：3 个选项卡式组  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_WINDOW_TILE_2_1_VERT`
- **菜单路径**：窗口布局(L) › 3 个选项卡式组(G)
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 8 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **窗口布局(L)**。
2. 在展开项中选择 **3 个选项卡式组(G)**（命令 ID：`UG_WINDOW_TILE_2_1_VERT`）。
3. 按对话框提示操作：使用 3 个选项卡式组的布局排列窗口。（竖直，选项 2）。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：使用 3 个选项卡式组的布局排列窗口。（竖直，选项 2）

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 16.8 功能点：4 个选项卡式组  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_WINDOW_TILE_2_2_HORIZ`
- **菜单路径**：窗口布局(L) › 4 个选项卡式组
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 8 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **窗口布局(L)**。
2. 在展开项中选择 **4 个选项卡式组**（命令 ID：`UG_WINDOW_TILE_2_2_HORIZ`）。
3. 按对话框提示操作：使用 4 个选项卡式组的布局排列窗口 (2x2)。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：使用 4 个选项卡式组的布局排列窗口 (2x2)。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 16.9 功能点：6 个选项卡式组  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_WINDOW_TILE_3_3_HORIZ`
- **菜单路径**：窗口布局(L) › 6 个选项卡式组
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 8 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **窗口布局(L)**。
2. 在展开项中选择 **6 个选项卡式组**（命令 ID：`UG_WINDOW_TILE_3_3_HORIZ`）。
3. 按对话框提示操作：使用 6 个选项卡式组的布局排列窗口 (2x3)。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：使用 6 个选项卡式组的布局排列窗口 (2x3)。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 17. 子模块：尺寸(D)

本子模块 8 个功能点。

### 17.1 功能点：角度尺寸  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_DIMENSION_ANGULAR`
- **菜单路径**：PMI › 尺寸(D) › 角度(A)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI › 尺寸(D)**。
2. 在展开项中选择 **角度(A)...**（命令 ID：`UG_PMI_DIMENSION_ANGULAR`）。
3. 按对话框提示操作：在两条不平行线之间创建角度尺寸。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在两条不平行线之间创建角度尺寸。
    - 检索同义词：degrees, angle, radians, pmi

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 17.2 功能点：倒斜角尺寸  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_DIMENSION_CHAMFER`
- **菜单路径**：PMI › 尺寸(D) › 倒斜角(C)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI › 尺寸(D)**。
2. 在展开项中选择 **倒斜角(C)...**（命令 ID：`UG_PMI_DIMENSION_CHAMFER`）。
3. 按对话框提示操作：在倒斜角曲线上创建倒斜角尺寸。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在倒斜角曲线上创建倒斜角尺寸。
    - 检索同义词：bevel, pmi

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 17.3 功能点：弧长尺寸  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_DIMENSION_CURVE_LENGTH`
- **菜单路径**：PMI › 尺寸(D) › 弧长(G)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI › 尺寸(D)**。
2. 在展开项中选择 **弧长(G)...**（命令 ID：`UG_PMI_DIMENSION_CURVE_LENGTH`）。
3. 按对话框提示操作：创建弧长尺寸来测量圆弧的周长。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建弧长尺寸来测量圆弧的周长。
    - 检索同义词：total length, curve length, circumference, pmi

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 17.4 功能点：线性尺寸  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_DIMENSION_LINEAR`
- **菜单路径**：PMI › 尺寸(D) › 线性(L)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI › 尺寸(D)**。
2. 在展开项中选择 **线性(L)...**（命令 ID：`UG_PMI_DIMENSION_LINEAR`）。
3. 按对话框提示操作：在两点之间创建线性尺寸。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在两点之间创建线性尺寸。
    - 检索同义词：dimension along X, dimension along Y, height, profile, landscape, minimum distance dimension, length dimension, opposite, distance from point, orthogonal, horizontal dimension, vertical dimension, parallel dimension, perpendicular dimension, cylindrical dimension, diameter, radius, horizontal chain dimensions, vertical chain dimensions, horizontal baseline dimensions, vertical baseline dimensions, insert dimensions from a common reference, hole callout, pmi

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 17.5 功能点：坐标尺寸  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_DIMENSION_ORDINATE`
- **菜单路径**：PMI › 尺寸(D) › 坐标(O)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI › 尺寸(D)**。
2. 在展开项中选择 **坐标(O)...**（命令 ID：`UG_PMI_DIMENSION_ORDINATE`）。
3. 按对话框提示操作：创建坐标尺寸，测量从公共点沿一条坐标基线到某一对象上位置的距离。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建坐标尺寸，测量从公共点沿一条坐标基线到某一对象上位置的距离。
    - 检索同义词：pmi

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 17.6 功能点：径向尺寸  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_DIMENSION_RADIAL`
- **菜单路径**：PMI › 尺寸(D) › 径向(R)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI › 尺寸(D)**。
2. 在展开项中选择 **径向(R)...**（命令 ID：`UG_PMI_DIMENSION_RADIAL`）。
3. 按对话框提示操作：创建圆形对象的半径或直径尺寸。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建圆形对象的半径或直径尺寸。
    - 检索同义词：hole dimension, radius to center dimension, folded radius dimension, hole callout, pmi

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 17.7 功能点：快速尺寸  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_DIMENSION_RAPID`
- **菜单路径**：PMI › 尺寸(D) › 快速(P)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI › 尺寸(D)**。
2. 在展开项中选择 **快速(P)...**（命令 ID：`UG_PMI_DIMENSION_RAPID`）。
3. 按对话框提示操作：根据选定对象和光标的位置自动判断尺寸类型，以创建尺寸。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：根据选定对象和光标的位置自动判断尺寸类型，以创建尺寸。
    - 检索同义词：guess, imply, derive, reference dimension, driven dimension with tolerance, inferred dimension, pmi

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 17.8 功能点：厚度尺寸  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_DIMENSION_THICKNESS`
- **菜单路径**：PMI › 尺寸(D) › 厚度(T)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI › 尺寸(D)**。
2. 在展开项中选择 **厚度(T)...**（命令 ID：`UG_PMI_DIMENSION_THICKNESS`）。
3. 按对话框提示操作：创建厚度尺寸来测量两条曲线之间的距离。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建厚度尺寸来测量两条曲线之间的距离。
    - 检索同义词：pmi

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 18. 子模块：选择(S)

本子模块 8 个功能点。

### 18.1 功能点：导航至标注  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_NAV_TO_CALLOUTS`
- **菜单路径**：编辑(E) › 表(B) › 选择(S) › 导航至标注(N)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B) › 选择(S)**。
2. 在展开项中选择 **导航至标注(N)**（命令 ID：`UG_TABLE_NAV_TO_CALLOUTS`）。
3. 按对话框提示操作：查找并高亮显示表示零件明细表中选定项的符号注释。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：查找并高亮显示表示零件明细表中选定项的符号注释。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 18.2 功能点：导航至孔表行  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_NAV_TO_HOLE_TABLE_ROW`
- **菜单路径**：编辑(E) › 表(B) › 选择(S) › 导航至孔表行(H)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B) › 选择(S)**。
2. 在展开项中选择 **导航至孔表行(H)**（命令 ID：`UG_TABLE_NAV_TO_HOLE_TABLE_ROW`）。
3. 按对话框提示操作：查找并高亮显示表示选定孔标签的孔表行。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：查找并高亮显示表示选定孔标签的孔表行。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 18.3 功能点：导航至零件明细表行  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_NAV_TO_PARTS_LIST_ROW`
- **菜单路径**：编辑(E) › 表(B) › 选择(S) › 导航至零件明细表行(P)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B) › 选择(S)**。
2. 在展开项中选择 **导航至零件明细表行(P)**（命令 ID：`UG_TABLE_NAV_TO_PARTS_LIST_ROW`）。
3. 按对话框提示操作：查找并高亮显示表示选定符号注释的零件明细表行。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：查找并高亮显示表示选定符号注释的零件明细表行。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 18.4 功能点：选择单元格  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_SELECT_CELLS`
- **菜单路径**：编辑(E) › 表(B) › 选择(S) › 单元格(C)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_title_block.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B) › 选择(S)**。
2. 在展开项中选择 **单元格(C)**（命令 ID：`UG_TABLE_SELECT_CELLS`）。
3. 按对话框提示操作：选择选定行、列或表区域的单元格。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：选择选定行、列或表区域的单元格。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 18.5 功能点：选择列  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_SELECT_COLS`
- **菜单路径**：编辑(E) › 表(B) › 选择(S) › 列(L)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_title_block.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B) › 选择(S)**。
2. 在展开项中选择 **列(L)**（命令 ID：`UG_TABLE_SELECT_COLS`）。
3. 按对话框提示操作：选择选定的单元格或表区域的列。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：选择选定的单元格或表区域的列。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 18.6 功能点：选择组件/对象  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_SELECT_MEMBERS`
- **菜单路径**：编辑(E) › 表(B) › 选择(S) › 组件/对象(M)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_title_block.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B) › 选择(S)**。
2. 在展开项中选择 **组件/对象(M)**（命令 ID：`UG_TABLE_SELECT_MEMBERS`）。
3. 按对话框提示操作：选择要包含在零件明细表中的组件或对象。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：选择要包含在零件明细表中的组件或对象。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 18.7 功能点：选择行  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_SELECT_ROWS`
- **菜单路径**：编辑(E) › 表(B) › 选择(S) › 行(R)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_title_block.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B) › 选择(S)**。
2. 在展开项中选择 **行(R)**（命令 ID：`UG_TABLE_SELECT_ROWS`）。
3. 按对话框提示操作：选择当前选定的单元格或表区域的行。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：选择当前选定的单元格或表区域的行。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 18.8 功能点：选择表区域  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_SELECT_SECTION`
- **菜单路径**：编辑(E) › 表(B) › 选择(S) › 表区域(T)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_title_block.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B) › 选择(S)**。
2. 在展开项中选择 **表区域(T)**（命令 ID：`UG_TABLE_SELECT_SECTION`）。
3. 按对话框提示操作：选择选定单元格、行或列的表区域。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：选择选定单元格、行或列的表区域。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 19. 子模块：ug_drafting

本子模块 7 个功能点。

### 19.1 功能点：管线布置(G)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFTING_ROUTING`
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/ug_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「管线布置(G)」定位。
2. 按对话框提示操作：列出制图管线布置命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出制图管线布置命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 19.2 功能点：曲线/点(C)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_CURVE_AND_POINTS`
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/ug_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「曲线/点(C)」定位。
2. 按对话框提示操作：列出曲线和点命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出曲线和点命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 19.3 功能点：图纸格式(W)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_DRAWING_FORMAT`
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/ug_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「图纸格式(W)」定位。
2. 按对话框提示操作：列出图纸格式命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出图纸格式命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 19.4 功能点：图纸迁移(W)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_MIGRATION_TOOLS`
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/ug_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「图纸迁移(W)」定位。
2. 按对话框提示操作：列出“图纸迁移”命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出“图纸迁移”命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 19.5 功能点：图纸比较(R)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_INFO_ANALYSIS_DRAWING_COMPARE`
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/ug_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「图纸比较(R)」定位。
2. 按对话框提示操作：列出图纸比较命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出图纸比较命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 19.6 功能点：2D 组件顺序  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_NXLAYOUT_NAVIGATOR_ORDER`
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/ug_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「2D 组件顺序」定位。
2. 按对话框提示操作：列出 2D 组件布局顺序命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出 2D 组件布局顺序命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 19.7 功能点：UG_PMI_TRACKING  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`UG_PMI_TRACKING`
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/ug_drafting.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「UG_PMI_TRACKING」定位。
2. 按对话框提示操作：列出 PMI 命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出 PMI 命令。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 20. 子模块：宏(R)

本子模块 7 个功能点。

### 20.1 功能点：插入宏用户暂停  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_MACRO_PAUSE`
- **菜单路径**：工具(T) › 宏(R) › 用户暂停(A)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 宏(R)**。
2. 在展开项中选择 **用户暂停(A)**（命令 ID：`UG_MACRO_PAUSE`）。
3. 按对话框提示操作：在录制会话过程中，将暂停插入宏。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在录制会话过程中，将暂停插入宏。
    - 检索同义词：wait, break, freeze, hesitate, macro user pause

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 20.2 功能点：回放宏  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_MACRO_PLAYBACK`
- **菜单路径**：工具(T) › 宏(R) › 回放(P)...
- **快捷键**：`Ctrl+Shift+P`
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 宏(R)**。
2. 在展开项中选择 **回放(P)...**（命令 ID：`UG_MACRO_PLAYBACK`）。
3. 可直接使用快捷键 **Ctrl+Shift+P** 调用（该快捷键来自介质 `.btn` 定义）。
4. 按对话框提示操作：回放现有的宏文件。
5. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：回放现有的宏文件。
    - 检索同义词：recording, program file, macro playback

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 20.3 功能点：录制宏  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_MACRO_RECORD`
- **菜单路径**：工具(T) › 宏(R) › 开始录制(R)...
- **快捷键**：`Ctrl+Shift+R`
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 宏(R)**。
2. 在展开项中选择 **开始录制(R)...**（命令 ID：`UG_MACRO_RECORD`）。
3. 可直接使用快捷键 **Ctrl+Shift+R** 调用（该快捷键来自介质 `.btn` 定义）。
4. 按对话框提示操作：将互动式会话录制为宏文件。
5. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将互动式会话录制为宏文件。
    - 检索同义词：track, program file, macro record, record macro

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 20.4 功能点：开始宏计时器  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_MACRO_START_TIMER`
- **菜单路径**：工具(T) › 宏(R) › 开始计时器(T)
- **快捷键**：`Alt+F5`
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 宏(R)**。
2. 在展开项中选择 **开始计时器(T)**（命令 ID：`UG_MACRO_START_TIMER`）。
3. 可直接使用快捷键 **Alt+F5** 调用（该快捷键来自介质 `.btn` 定义）。
4. 按对话框提示操作：当录制或回放宏时，跟踪完成指定事件所需的时长。
5. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：当录制或回放宏时，跟踪完成指定事件所需的时长。
    - 检索同义词：start timer

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 20.5 功能点：宏步进回放  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_MACRO_STEP`
- **菜单路径**：工具(T) › 宏(R) › 步进(S)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 宏(R)**。
2. 在展开项中选择 **步进(S)...**（命令 ID：`UG_MACRO_STEP`）。
3. 按对话框提示操作：在回放宏时，仔细地逐行检查宏的交互作用。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在回放宏时，仔细地逐行检查宏的交互作用。
    - 检索同义词：program, single step, macro step playback

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 20.6 功能点：宏用户输入  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_MACRO_USER_ENTRY`
- **菜单路径**：工具(T) › 宏(R) › 用户输入(U)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 宏(R)**。
2. 在展开项中选择 **用户输入(U)**（命令 ID：`UG_MACRO_USER_ENTRY`）。
3. 按对话框提示操作：在录制会话过程中，将用户输入点插入宏。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在录制会话过程中，将用户输入点插入宏。
    - 检索同义词：macro user entry

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 20.7 功能点：宏用户输入带指导说明  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_MACRO_USER_ENTRY_INS`
- **菜单路径**：工具(T) › 宏(R) › 用户输入带指导说明(I)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 宏(R)**。
2. 在展开项中选择 **用户输入带指导说明(I)**（命令 ID：`UG_MACRO_USER_ENTRY_INS`）。
3. 按对话框提示操作：在录制会话过程中，将用户输入点插入宏，并包含简要的用户指导。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在录制会话过程中，将用户输入点插入宏，并包含简要的用户指导。
    - 检索同义词：macro user entry

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 21. 子模块：布局(T)

本子模块 7 个功能点。

### 21.1 功能点：定义锚点  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_NXLAYOUT_2D_COMPONENT_DEFINE_ANCHOR_POINT`
- **菜单路径**：工具(T) › 布局(T) › 定义锚点(P)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 4 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 布局(T)**。
2. 在展开项中选择 **定义锚点(P)...**（命令 ID：`UG_NXLAYOUT_2D_COMPONENT_DEFINE_ANCHOR_POINT`）。
3. 按对话框提示操作：定义 2D 组件的锚点位置。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：定义 2D 组件的锚点位置。
    - 可用性提示：This command is available only with the NX Layout license.
    - 检索同义词：sketch object, symbol

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 21.2 功能点：隔离编辑(E)  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_NXLAYOUT_2D_COMPONENT_EDIT`
- **菜单路径**：工具(T) › 布局(T) › 隔离编辑(E)
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 布局(T)**。
2. 在展开项中选择 **隔离编辑(E)**（命令 ID：`UG_NXLAYOUT_2D_COMPONENT_EDIT`）。
3. 按对话框提示操作：隔离编辑 2D 组件定义。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：隔离编辑 2D 组件定义。
    - 可用性提示：This command is available only with the NX Layout license.
    - 检索同义词：2D Layout, Edit

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 21.3 功能点：将布局转换为图纸页  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_NXLAYOUT_CONVERT_LAYOUT_TO_SHEET`
- **菜单路径**：工具(T) › 布局(T) › 转换为图纸页(S)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 布局(T)**。
2. 在展开项中选择 **转换为图纸页(S)...**（命令 ID：`UG_NXLAYOUT_CONVERT_LAYOUT_TO_SHEET`）。
3. 按对话框提示操作：将某个布局转化为一个图纸页。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将某个布局转化为一个图纸页。
    - 可用性提示：This command is available only in the Layout application.
    - 检索同义词：Conceptual design, 2D design

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 21.4 功能点：将图纸页转换为布局  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_NXLAYOUT_CONVERT_SHEET_TO_LAYOUT`
- **菜单路径**：工具(T) › 布局(T) › 转换为布局(L)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 布局(T)**。
2. 在展开项中选择 **转换为布局(L)...**（命令 ID：`UG_NXLAYOUT_CONVERT_SHEET_TO_LAYOUT`）。
3. 按对话框提示操作：将某个图纸页转换为一个布局。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将某个图纸页转换为一个布局。
    - 可用性提示：This command is available only with the NX Layout license.
    - 检索同义词：Conceptual design, 2D design

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 21.5 功能点：2D 组件设置  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_NXLAYOUT_EDIT_2D_COMPONENT_SETTING`
- **菜单路径**：工具(T) › 布局(T) › 设置(S)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 布局(T)**。
2. 在展开项中选择 **设置(S)...**（命令 ID：`UG_NXLAYOUT_EDIT_2D_COMPONENT_SETTING`）。
3. 按对话框提示操作：编辑选定 2D 组件的设置。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：编辑选定 2D 组件的设置。
    - 检索同义词：2d components

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 21.6 功能点：退出 2D 组件编辑  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_NXLAYOUT_EXIT_2D_COMPONENT_EDIT`
- **菜单路径**：工具(T) › 布局(T) › 退出 2D 组件编辑(X)
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 4 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 布局(T)**。
2. 在展开项中选择 **退出 2D 组件编辑(X)**（命令 ID：`UG_NXLAYOUT_EXIT_2D_COMPONENT_EDIT`）。
3. 按对话框提示操作：退出 2D 组件编辑，不保存对 2D 组件定义的更改。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：退出 2D 组件编辑，不保存对 2D 组件定义的更改。
    - 可用性提示：This command is available when editing a 2D component.

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 21.7 功能点：完成 2D 组件编辑  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_NXLAYOUT_FINISH_2D_COMPONENT_EDIT`
- **菜单路径**：工具(T) › 布局(T) › 完成 2D 组件编辑(F)
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 4 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 布局(T)**。
2. 在展开项中选择 **完成 2D 组件编辑(F)**（命令 ID：`UG_NXLAYOUT_FINISH_2D_COMPONENT_EDIT`）。
3. 按对话框提示操作：保存对 2D 组件定义的更改。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：保存对 2D 组件定义的更改。
    - 可用性提示：This command is available when editing a 2D component.

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 22. 子模块：显示和隐藏(H)

本子模块 7 个功能点。

### 22.1 功能点：隐藏  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_EDIT_BLANK_SELECTED`
- **菜单路径**：编辑(E) › 显示和隐藏(H) › 隐藏(H)...
- **快捷键**：`Ctrl+B`
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 9 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 显示和隐藏(H)**。
2. 在展开项中选择 **隐藏(H)...**（命令 ID：`UG_EDIT_BLANK_SELECTED`）。
3. 可直接使用快捷键 **Ctrl+B** 调用（该快捷键来自介质 `.btn` 定义）。
4. 按对话框提示操作：使选定的对象在显示区中不可见。
5. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：使选定的对象在显示区中不可见。
    - 检索同义词：blank, erase, invisible, visibility

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 22.2 功能点：显示和隐藏  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_EDIT_MD_SHOWHIDE_ALL`
- **菜单路径**：编辑(E) › 显示和隐藏(H) › 显示和隐藏(O)...
- **快捷键**：`Ctrl+W`
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 9 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 显示和隐藏(H)**。
2. 在展开项中选择 **显示和隐藏(O)...**（命令 ID：`UG_EDIT_MD_SHOWHIDE_ALL`）。
3. 可直接使用快捷键 **Ctrl+W** 调用（该快捷键来自介质 `.btn` 定义）。
4. 按对话框提示操作：按类型显示或隐藏对象。
5. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：按类型显示或隐藏对象。
    - 检索同义词：blank, unblank, erase, visible, visibility, display filters, show dim

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 22.3 功能点：立即隐藏  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_EDIT_ONE_PICK_HIDE`
- **菜单路径**：编辑(E) › 显示和隐藏(H) › 立即隐藏(M)...
- **快捷键**：`Ctrl+Shift+I`
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 9 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 显示和隐藏(H)**。
2. 在展开项中选择 **立即隐藏(M)...**（命令 ID：`UG_EDIT_ONE_PICK_HIDE`）。
3. 可直接使用快捷键 **Ctrl+Shift+I** 调用（该快捷键来自介质 `.btn` 定义）。
4. 按对话框提示操作：一旦选定对象后，就隐藏它们。
5. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：一旦选定对象后，就隐藏它们。
    - 检索同义词：blank, erase, invisible, visibility

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 22.4 功能点：全部显示  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_EDIT_UNBLANK_ALL_OF_PART`
- **菜单路径**：编辑(E) › 显示和隐藏(H) › 全部显示(A)
- **快捷键**：`Ctrl+Shift+U`
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 9 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 显示和隐藏(H)**。
2. 在展开项中选择 **全部显示(A)**（命令 ID：`UG_EDIT_UNBLANK_ALL_OF_PART`）。
3. 可直接使用快捷键 **Ctrl+Shift+U** 调用（该快捷键来自介质 `.btn` 定义）。
4. 按对话框提示操作：显示可选图层上的所有对象。
5. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：显示可选图层上的所有对象。
    - 检索同义词：unblank all, visible, visibility, display all, un hide all

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 22.5 功能点：按名称显示  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_EDIT_UNBLANK_BY_NAME`
- **菜单路径**：编辑(E) › 显示和隐藏(H) › 按名称显示(N)...
- **快捷键**：`Ctrl+Shift+B`
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 9 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 显示和隐藏(H)**。
2. 在展开项中选择 **按名称显示(N)...**（命令 ID：`UG_EDIT_UNBLANK_BY_NAME`）。
3. 可直接使用快捷键 **Ctrl+Shift+B** 调用（该快捷键来自介质 `.btn` 定义）。
4. 按对话框提示操作：显示具有指定名称的所有对象。
5. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：显示具有指定名称的所有对象。
    - 检索同义词：unblank by name, visible, visibility

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 22.6 功能点：显示所有此类型对象  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_EDIT_UNBLANK_BY_TYPE`
- **菜单路径**：编辑(E) › 显示和隐藏(H) › 显示所有此类型对象(T)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 9 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 显示和隐藏(H)**。
2. 在展开项中选择 **显示所有此类型对象(T)...**（命令 ID：`UG_EDIT_UNBLANK_BY_TYPE`）。
3. 按对话框提示操作：显示指定类型的所有对象。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：显示指定类型的所有对象。
    - 检索同义词：unblank all of type, visible, visibility, display filters

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 22.7 功能点：显示  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_EDIT_UNBLANK_SELECTED`
- **菜单路径**：编辑(E) › 显示和隐藏(H) › 显示(S)...
- **快捷键**：`Ctrl+Shift+K`
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 9 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 显示和隐藏(H)**。
2. 在展开项中选择 **显示(S)...**（命令 ID：`UG_EDIT_UNBLANK_SELECTED`）。
3. 可直接使用快捷键 **Ctrl+Shift+K** 调用（该快捷键来自介质 `.btn` 定义）。
4. 按对话框提示操作：使选定的对象在显示区中可见。
5. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：使选定的对象在显示区中可见。
    - 检索同义词：unblank, visible, visibility, un hide

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 23. 子模块：表达式(X)

本子模块 7 个功能点。

### 23.1 功能点：列出所有表达式  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_EXPRESSION_LIST_ALL`
- **菜单路径**：信息(I) › 表达式(X) › 全部列出(A)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 4 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **信息(I) › 表达式(X)**。
2. 在展开项中选择 **全部列出(A)**（命令 ID：`UG_EXPRESSION_LIST_ALL`）。
3. 按对话框提示操作：列出部件中的所有表达式。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出部件中的所有表达式。
    - 检索同义词：parameter, function, formula, variable, part equations, info expressions, list expressions, expression information

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 23.2 功能点：按引用列出所有表达式  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_EXPRESSION_LIST_ALL_BY_REF`
- **菜单路径**：信息(I) › 表达式(X) › 按引用全部列出(R)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 4 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **信息(I) › 表达式(X)**。
2. 在展开项中选择 **按引用全部列出(R)**（命令 ID：`UG_EXPRESSION_LIST_ALL_BY_REF`）。
3. 按对话框提示操作：列出部件中的所有表达式，包括特征名和引用等信息。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出部件中的所有表达式，包括特征名和引用等信息。
    - 检索同义词：parameter, function, formula, variable, equation, info expressions, list expressions, expression information, reference information, list all by reference

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 23.3 功能点：列出所有测量表达式  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_EXPRESSION_LIST_ALL_GEOMETRIC`
- **菜单路径**：信息(I) › 表达式(X) › 列出所有测量(M)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 4 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **信息(I) › 表达式(X)**。
2. 在展开项中选择 **列出所有测量(M)**（命令 ID：`UG_EXPRESSION_LIST_ALL_GEOMETRIC`）。
3. 按对话框提示操作：列出部件中的所有测量表达式。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出部件中的所有测量表达式。
    - 检索同义词：parameter, function, formula, variable, equation, info expressions, list expressions, expression information, list all geometric expressions

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 23.4 功能点：列出装配中的所有表达式  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_EXPRESSION_LIST_ALL_IN_ASSY`
- **菜单路径**：信息(I) › 表达式(X) › 列出装配中的所有表达式(Y)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 4 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **信息(I) › 表达式(X)**。
2. 在展开项中选择 **列出装配中的所有表达式(Y)**（命令 ID：`UG_EXPRESSION_LIST_ALL_IN_ASSY`）。
3. 按对话框提示操作：列出显示装配中每个部件的所有表达式。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出显示装配中每个部件的所有表达式。
    - 检索同义词：parameter, function, formula, variable, assembly equations, info expressions, list expressions, expression information, list all in assembly

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 23.5 功能点：列出会话中的所有表达式  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_EXPRESSION_LIST_ALL_IN_SESS`
- **菜单路径**：信息(I) › 表达式(X) › 列出会话中的全部(N)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 4 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **信息(I) › 表达式(X)**。
2. 在展开项中选择 **列出会话中的全部(N)**（命令 ID：`UG_EXPRESSION_LIST_ALL_IN_SESS`）。
3. 按对话框提示操作：列出会话中加载的每个部件中的所有表达式。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出会话中加载的每个部件中的所有表达式。
    - 检索同义词：parameter, function, formula, variable, equation, info expressions, list expressions, expression information, list all in session

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 23.6 功能点：按草图列出表达式  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_EXPRESSION_LIST_BY_SKETCH`
- **菜单路径**：信息(I) › 表达式(X) › 按草图列出表达式(S)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 4 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **信息(I) › 表达式(X)**。
2. 在展开项中选择 **按草图列出表达式(S)...**（命令 ID：`UG_EXPRESSION_LIST_BY_SKETCH`）。
3. 按对话框提示操作：列出草图中的所有表达式。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出草图中的所有表达式。
    - 检索同义词：parameter, function, formula, variable, equation, info expressions, list expressions, expression information, sketch expressions, list by sketch

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 23.7 功能点：按装配约束列出表达式  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_LIST_MATING_CONSTRAINTS`
- **菜单路径**：信息(I) › 表达式(X) › 列出装配约束(C)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 4 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **信息(I) › 表达式(X)**。
2. 在展开项中选择 **列出装配约束(C)**（命令 ID：`UG_LIST_MATING_CONSTRAINTS`）。
3. 按对话框提示操作：列出部件的所有装配约束（如果它是装配）。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出部件的所有装配约束（如果它是装配）。
    - 检索同义词：parameter, function, formula, variable, equation, list assembly constraints

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 24. 子模块：分析(L)

本子模块 6 个功能点。

### 24.1 功能点：屏幕距离  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_INFO_DYNAMIC_DISTANCE`
- **菜单路径**：分析(L) › 屏幕距离
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 4 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **分析(L)**。
2. 在展开项中选择 **屏幕距离**（命令 ID：`UG_INFO_DYNAMIC_DISTANCE`）。
3. 按对话框提示操作：通过显示临时标尺来测量屏幕上两个对象之间的大致 2D 距离。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：通过显示临时标尺来测量屏幕上两个对象之间的大致 2D 距离。
    - 检索同义词：length, measurement

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 24.2 功能点：测量角度（即将失效）  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_INFO_GEOMETRIC_ANGLE`
- **菜单路径**：分析(L) › 测量角度（即将失效）(A)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 9 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **分析(L)**。
2. 在展开项中选择 **测量角度（即将失效）(A)...**（命令 ID：`UG_INFO_GEOMETRIC_ANGLE`）。
3. 按对话框提示操作：计算两个对象之间或由三点定义的两直线之间的夹角。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：计算两个对象之间或由三点定义的两直线之间的夹角。
    - 检索同义词：degrees, measurement, radians

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 24.3 功能点：测量长度（即将失效）  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_INFO_GEOMETRIC_ARC_LENGTH`
- **菜单路径**：分析(L) › 测量长度（即将失效）(L)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 9 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **分析(L)**。
2. 在展开项中选择 **测量长度（即将失效）(L)...**（命令 ID：`UG_INFO_GEOMETRIC_ARC_LENGTH`）。
3. 按对话框提示操作：测量曲线的长度。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：测量曲线的长度。
    - 检索同义词：measurement, arclength

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 24.4 功能点：测量距离（即将失效）  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_INFO_GEOMETRIC_DISTANCE`
- **菜单路径**：分析(L) › 测量距离（即将失效）(D)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 9 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **分析(L)**。
2. 在展开项中选择 **测量距离（即将失效）(D)...**（命令 ID：`UG_INFO_GEOMETRIC_DISTANCE`）。
3. 按对话框提示操作：计算两个对象之间距离，曲线长度，或者圆弧、圆边或圆柱面的半径。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：计算两个对象之间距离，曲线长度，或者圆弧、圆边或圆柱面的半径。
    - 检索同义词：measurement, angle, diameter, area

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 24.5 功能点：测量  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_INFO_GEOMETRIC_MEASUREMENT`
- **菜单路径**：分析(L) › 测量(S)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 9 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **分析(L)**。
2. 在展开项中选择 **测量(S)...**（命令 ID：`UG_INFO_GEOMETRIC_MEASUREMENT`）。
3. 按对话框提示操作：计算对象或对象集的不同测量值。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：计算对象或对象集的不同测量值。
    - 检索同义词：inquire, inquiry

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 24.6 功能点：截面惯性分析  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_INFO_SECTION_INERTIA`
- **菜单路径**：分析(L) › 截面惯性(N)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/ug_drafting.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **分析(L)**。
2. 在展开项中选择 **截面惯性(N)...**（命令 ID：`UG_INFO_SECTION_INERTIA`）。
3. 按对话框提示操作：计算截面的主惯性矩、圆周、面积和重心。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：计算截面的主惯性矩、圆周、面积和重心。
    - 检索同义词：physical, inertial, properties

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 25. 子模块：视图(V)

本子模块 6 个功能点。

### 25.1 功能点：替换视图  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_VIEW_REPLACE_VIEW`
- **菜单路径**：视图(V) › 替换视图(L)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **视图(V)**。
2. 在展开项中选择 **替换视图(L)...**（命令 ID：`UG_DRAFT_VIEW_REPLACE_VIEW`）。
3. 按对话框提示操作：用另一个建模视图替换显示的建模视图。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：用另一个建模视图替换显示的建模视图。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 25.2 功能点：导航至父视图  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_LAYOUT_FIT_TO_PARENT_VIEW`
- **菜单路径**：视图(V) › 导航至父视图
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 7 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **视图(V)**。
2. 在展开项中选择 **导航至父视图**（命令 ID：`UG_LAYOUT_FIT_TO_PARENT_VIEW`）。
3. 按对话框提示操作：显示选定视图的父视图。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：显示选定视图的父视图。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 25.3 功能点：隐藏/显示当前对话框  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_VIEW_CURRENT_DIALOG`
- **菜单路径**：视图(V) › 当前对话框(C)
- **快捷键**：`F3`
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **视图(V)**。
2. 在展开项中选择 **当前对话框(C)**（命令 ID：`UG_VIEW_CURRENT_DIALOG`）。
3. 可直接使用快捷键 **F3** 调用（该快捷键来自介质 `.btn` 定义）。
4. 按对话框提示操作：隐藏或显示当前对话框。
5. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：隐藏或显示当前对话框。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 25.4 功能点：导航至局部放大图  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_VIEW_FIT_TO_DETAIL_VIEW`
- **菜单路径**：视图(V) › 导航至局部放大图
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 7 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **视图(V)**。
2. 在展开项中选择 **导航至局部放大图**（命令 ID：`UG_VIEW_FIT_TO_DETAIL_VIEW`）。
3. 按对话框提示操作：显示选定局部放大图边界的局部放大图。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：显示选定局部放大图边界的局部放大图。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 25.5 功能点：导航至剖视图  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_VIEW_FIT_TO_SECTION_VIEW`
- **菜单路径**：视图(V) › 导航至剖视图
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 7 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **视图(V)**。
2. 在展开项中选择 **导航至剖视图**（命令 ID：`UG_VIEW_FIT_TO_SECTION_VIEW`）。
3. 按对话框提示操作：显示选定剖切线的剖视图。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：显示选定剖切线的剖视图。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 25.6 功能点：显示 HD3D 工具 UI  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_VIEW_VISUAL_PLM_UI`
- **菜单路径**：视图(V) › HD3D 工具 UI
- **快捷键**：`Ctrl+3`
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 9 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **视图(V)**。
2. 在展开项中选择 **HD3D 工具 UI**（命令 ID：`UG_VIEW_VISUAL_PLM_UI`）。
3. 可直接使用快捷键 **Ctrl+3** 调用（该快捷键来自介质 `.btn` 定义）。
4. 按对话框提示操作：在场景中隐藏或显示 HD3D 工具元素。
5. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在场景中隐藏或显示 HD3D 工具元素。
    - 可用性提示：This command is available when an HD3D Tool is active.
    - 检索同义词：show ribbon,hide ribbon

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 26. 子模块：2D 组件(N)

本子模块 5 个功能点。

### 26.1 功能点：定义 2D 组件  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_NXLAYOUT_2D_COMPONENT_DEFINE`
- **菜单路径**：插入(S) › 2D 组件(N) › 定义(D)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 2D 组件(N)**。
2. 在展开项中选择 **定义(D)...**（命令 ID：`UG_NXLAYOUT_2D_COMPONENT_DEFINE`）。
3. 按对话框提示操作：通过选择内容和在重用库中存储其定义来定义 2D 组件实例。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：通过选择内容和在重用库中存储其定义来定义 2D 组件实例。
    - 可用性提示：This command is available only with the NX Layout license.
    - 检索同义词：sketch object, symbol

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 26.2 功能点：将 2D 组件设为唯一  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_NXLAYOUT_2D_COMPONENT_MAKE_UNIQUE`
- **菜单路径**：编辑(E) › 2D 组件(N) › 设为唯一(M)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 2D 组件(N)**。
2. 在展开项中选择 **设为唯一(M)...**（命令 ID：`UG_NXLAYOUT_2D_COMPONENT_MAKE_UNIQUE`）。
3. 按对话框提示操作：为选定的 2D 组件实例新建 2D 组件定义。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：为选定的 2D 组件实例新建 2D 组件定义。
    - 可用性提示：This command is available only with the NX Layout license.
    - 检索同义词：sketch object, symbol, library

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 26.3 功能点：新建 2D 组件  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_NXLAYOUT_2D_COMPONENT_NEW`
- **菜单路径**：插入(S) › 2D 组件(N) › 新建(N)
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S) › 2D 组件(N)**。
2. 在展开项中选择 **新建(N)**（命令 ID：`UG_NXLAYOUT_2D_COMPONENT_NEW`）。
3. 按对话框提示操作：创建空的 2D 组件实例，并在重用库中存储其定义。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建空的 2D 组件实例，并在重用库中存储其定义。
    - 可用性提示：This command is available only with the NX Layout license.
    - 检索同义词：sketch object, symbol

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 26.4 功能点：替换 2D 组件  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_NXLAYOUT_2D_COMPONENT_REPLACE`
- **菜单路径**：编辑(E) › 2D 组件(N) › 替换(R)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 2D 组件(N)**。
2. 在展开项中选择 **替换(R)...**（命令 ID：`UG_NXLAYOUT_2D_COMPONENT_REPLACE`）。
3. 按对话框提示操作：将选定的 2D 组件实例替换为其他 2D 组件定义。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将选定的 2D 组件实例替换为其他 2D 组件定义。
    - 可用性提示：This command is available only with the NX Layout license.
    - 检索同义词：sketch object, symbol, library

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 26.5 功能点：打散 2D 组件  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_NXLAYOUT_2D_COMPONENT_SMASH`
- **菜单路径**：编辑(E) › 2D 组件(N) › 打散(S)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 2D 组件(N)**。
2. 在展开项中选择 **打散(S)...**（命令 ID：`UG_NXLAYOUT_2D_COMPONENT_SMASH`）。
3. 按对话框提示操作：将 2D 组件的实例分解为几个构成片段。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将 2D 组件的实例分解为几个构成片段。
    - 可用性提示：This command is available only with the NX Layout license.
    - 检索同义词：sketch object, symbol

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 27. 子模块：测量(S)

本子模块 5 个功能点。

### 27.1 功能点：简单角度（即将失效）  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_INFO_SIMPLE_GEOMETRIC_ANGLE`
- **菜单路径**：测量(S) › 简单角度（即将失效）(A)...
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 9 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **测量(S)**。
2. 在展开项中选择 **简单角度（即将失效）(A)...**（命令 ID：`UG_INFO_SIMPLE_GEOMETRIC_ANGLE`）。
3. 按对话框提示操作：计算两个对象的夹角。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：计算两个对象的夹角。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 27.2 功能点：简单直径  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_INFO_SIMPLE_GEOMETRIC_DIAMETER`
- **菜单路径**：测量(S) › 简单直径(D)...
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 9 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **测量(S)**。
2. 在展开项中选择 **简单直径(D)...**（命令 ID：`UG_INFO_SIMPLE_GEOMETRIC_DIAMETER`）。
3. 按对话框提示操作：测量圆弧、圆边或圆柱面的直径。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：测量圆弧、圆边或圆柱面的直径。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 27.3 功能点：简单距离（即将失效）  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_INFO_SIMPLE_GEOMETRIC_DISTANCE`
- **菜单路径**：测量(S) › 简单距离（即将失效）(S)...
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 9 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **测量(S)**。
2. 在展开项中选择 **简单距离（即将失效）(S)...**（命令 ID：`UG_INFO_SIMPLE_GEOMETRIC_DISTANCE`）。
3. 按对话框提示操作：计算两个对象的间距。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：计算两个对象的间距。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 27.4 功能点：简单长度（即将失效）  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_INFO_SIMPLE_GEOMETRIC_LENGTH`
- **菜单路径**：测量(S) › 简单长度（即将失效）(L)...
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 9 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **测量(S)**。
2. 在展开项中选择 **简单长度（即将失效）(L)...**（命令 ID：`UG_INFO_SIMPLE_GEOMETRIC_LENGTH`）。
3. 按对话框提示操作：测量一条或多条曲线的长度。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：测量一条或多条曲线的长度。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 27.5 功能点：简单半径  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_INFO_SIMPLE_GEOMETRIC_RADIUS`
- **菜单路径**：测量(S) › 简单半径(R)...
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 9 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **测量(S)**。
2. 在展开项中选择 **简单半径(R)...**（命令 ID：`UG_INFO_SIMPLE_GEOMETRIC_RADIUS`）。
3. 按对话框提示操作：测量圆弧、圆边或圆柱面的半径。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：测量圆弧、圆边或圆柱面的半径。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 28. 子模块：符号(S)

本子模块 5 个功能点。

### 28.1 功能点：编辑定制符号  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_EDIT_CUSTOM_SYMBOL`
- **菜单路径**：编辑(E) › 符号(S) › 编辑定制符号(E)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 符号(S)**。
2. 在展开项中选择 **编辑定制符号(E)...**（命令 ID：`UG_DRAFT_EDIT_CUSTOM_SYMBOL`）。
3. 按对话框提示操作：编辑定制符号定义。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：编辑定制符号定义。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 28.2 功能点：退出定制符号编辑  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_EXIT_CUSTOM_SYMBOL_EDIT`
- **菜单路径**：编辑(E) › 符号(S) › 退出定制符号编辑(X)
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 符号(S)**。
2. 在展开项中选择 **退出定制符号编辑(X)**（命令 ID：`UG_DRAFT_EXIT_CUSTOM_SYMBOL_EDIT`）。
3. 按对话框提示操作：退出定制符号编辑而不保存对定制符号定义的更改。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：退出定制符号编辑而不保存对定制符号定义的更改。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 28.3 功能点：完成定制符号编辑  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_FINISH_CUSTOM_SYMBOL_EDIT`
- **菜单路径**：编辑(E) › 符号(S) › 完成定制符号编辑(F)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 符号(S)**。
2. 在展开项中选择 **完成定制符号编辑(F)...**（命令 ID：`UG_DRAFT_FINISH_CUSTOM_SYMBOL_EDIT`）。
3. 按对话框提示操作：保存对定制符号定义的更改。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：保存对定制符号定义的更改。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 28.4 功能点：替换定制符号  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_REPLACE_CUSTOM_SYMBOL`
- **菜单路径**：编辑(E) › 符号(S) › 替换定制符号(R)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 符号(S)**。
2. 在展开项中选择 **替换定制符号(R)**（命令 ID：`UG_PMI_REPLACE_CUSTOM_SYMBOL`）。
3. 按对话框提示操作：将选定的定制符号实例替换为其他主符号。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将选定的定制符号实例替换为其他主符号。
    - 检索同义词：Reassociate

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 28.5 功能点：打散定制符号  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_SMASH_CUSTOM_SYMBOL`
- **菜单路径**：编辑(E) › 符号(S) › 打散定制符号(S)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 符号(S)**。
2. 在展开项中选择 **打散定制符号(S)...**（命令 ID：`UG_PMI_SMASH_CUSTOM_SYMBOL`）。
3. 按对话框提示操作：将定制符号的实例分解为几个构成片段。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将定制符号的实例分解为几个构成片段。
    - 检索同义词：smash instance

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 29. 子模块：首选项

本子模块 5 个功能点。

### 29.1 功能点：制图首选项  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_PREFERENCES_DRAFTING`
- **菜单路径**：首选项(P) › 制图(D)...；所有首选项(A) › 制图(D)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 4 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **首选项(P)**。
2. 在展开项中选择 **制图(D)...**（命令 ID：`UG_DRAFT_PREFERENCES_DRAFTING`）。
3. 按对话框提示操作：设置“制图”应用模块的默认工作流、图纸和注释设置以及其他特性。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：设置“制图”应用模块的默认工作流、图纸和注释设置以及其他特性。
    - 检索同义词：annotation preferences, view preferences, drawing preferences, table preferences, view label preferences, drafting automation preferences, drafting settings, drafting options, notes, text, appearance, look, true length

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 29.2 功能点：布局首选项  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_NXLAYOUT_PREFERENCES`
- **菜单路径**：首选项(P) › 布局(L)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 4 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **首选项(P)**。
2. 在展开项中选择 **布局(L)...**（命令 ID：`UG_NXLAYOUT_PREFERENCES`）。
3. 按对话框提示操作：设置默认工作流程、2D 组件和布局设置，以及布局应用模块的其他特性。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：设置默认工作流程、2D 组件和布局设置，以及布局应用模块的其他特性。
    - 检索同义词：layout preferences, 2D component preferences, create from 3D preferences, create assembly preferences

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 29.3 功能点：公差标准  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_GDT_TOLERANCE_STANDARD`
- **菜单路径**：首选项(P) › PMI › 公差标准(S)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **首选项(P) › PMI**。
2. 在展开项中选择 **公差标准(S)...**（命令 ID：`UG_PMI_GDT_TOLERANCE_STANDARD`）。
3. 按对话框提示操作：设置公差标准，以管理各种几何公差标注和符号的格式设置。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：设置公差标准，以管理各种几何公差标注和符号的格式设置。
    - 检索同义词：ASME, ISO, GM addendum

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 29.4 功能点：PMI 首选项  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_PREFERENCES`
- **菜单路径**：首选项(P) › PMI › PMI 首选项
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **首选项(P) › PMI**。
2. 在展开项中选择 **PMI 首选项**（命令 ID：`UG_PMI_PREFERENCES`）。
3. 按对话框提示操作：为 PMI 工作流程设置首选项并显示特性。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：为 PMI 工作流程设置首选项并显示特性。
    - 检索同义词：PMI preferences, options

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 29.5 功能点：几何公差首选项  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_PREFERENCES_GEOMETRIC_TOLERANCING`
- **菜单路径**：首选项(P) › PMI › 几何公差(T)...
- **快捷键**：`Ctrl+M`
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **首选项(P) › PMI**。
2. 在展开项中选择 **几何公差(T)...**（命令 ID：`UG_PMI_PREFERENCES_GEOMETRIC_TOLERANCING`）。
3. 可直接使用快捷键 **Ctrl+M** 调用（该快捷键来自介质 `.btn` 定义）。
4. 按对话框提示操作：设置几何公差的默认注释平面和其他首选项。
5. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：设置几何公差的默认注释平面和其他首选项。
    - 可用性提示：EXCLUDE_FROM_COMMAND_FINDER
    - 检索同义词：modeller, feature modeling, solid modeling, 3D design, part modeling

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 30. 子模块：信息(I)

本子模块 4 个功能点。

### 30.1 功能点：样条信息  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_INFO_ANALYSIS_SPLINE`
- **菜单路径**：信息(I) › 样条(S)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 4 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **信息(I)**。
2. 在展开项中选择 **样条(S)...**（命令 ID：`UG_INFO_ANALYSIS_SPLINE`）。
3. 按对话框提示操作：列出样条的信息，如次数和极点数、段数和结点数。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出样条的信息，如次数和极点数、段数和结点数。
    - 检索同义词：shaped curve, b-curve, b-spline, info spline, spline information

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 30.2 功能点：点信息  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_INFO_GEOMETRIC_POINT`
- **菜单路径**：信息(I) › 点(P)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 9 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **信息(I)**。
2. 在展开项中选择 **点(P)...**（命令 ID：`UG_INFO_GEOMETRIC_POINT`）。
3. 按对话框提示操作：获取显式或隐式点的绝对和工作坐标。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：获取显式或隐式点的绝对和工作坐标。
    - 检索同义词：position, location, info point, point information

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 30.3 功能点：对象信息  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_INFO_OBJECT`
- **菜单路径**：信息(I) › 对象(O)...
- **快捷键**：`Ctrl+I`
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **信息(I)**。
2. 在展开项中选择 **对象(O)...**（命令 ID：`UG_INFO_OBJECT`）。
3. 可直接使用快捷键 **Ctrl+I** 调用（该快捷键来自介质 `.btn` 定义）。
4. 按对话框提示操作：列出关于几何对象的信息。
5. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出关于几何对象的信息。
    - 检索同义词：properties, info object

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 30.4 功能点：单位信息  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TOOLBOX_UNITS_INFORMATION`
- **菜单路径**：信息(I) › 单位信息(N)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 5 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **信息(I)**。
2. 在展开项中选择 **单位信息(N)**（命令 ID：`UG_TOOLBOX_UNITS_INFORMATION`）。
3. 按对话框提示操作：列出关于每次测量的默认单位的信息。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出关于每次测量的默认单位的信息。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 31. 子模块：操作记录(J)

本子模块 4 个功能点。

### 31.1 功能点：编辑操作记录  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_JOURNAL_EDIT`
- **菜单路径**：工具(T) › 操作记录(J) › 编辑(E)...
- **快捷键**：`Alt+F11`
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 操作记录(J)**。
2. 在展开项中选择 **编辑(E)...**（命令 ID：`UG_JOURNAL_EDIT`）。
3. 可直接使用快捷键 **Alt+F11** 调用（该快捷键来自介质 `.btn` 定义）。
4. 按对话框提示操作：编辑任何现有的操作记录文件。
5. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：编辑任何现有的操作记录文件。
    - 检索同义词：journamation, journal editor

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 31.2 功能点：播放操作记录  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_JOURNAL_PLAY`
- **菜单路径**：工具(T) › 操作记录(J) › 播放(P)...
- **快捷键**：`Alt+F8`
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 操作记录(J)**。
2. 在展开项中选择 **播放(P)...**（命令 ID：`UG_JOURNAL_PLAY`）。
3. 可直接使用快捷键 **Alt+F8** 调用（该快捷键来自介质 `.btn` 定义）。
4. 按对话框提示操作：回放现有的操作记录文件。
5. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：回放现有的操作记录文件。
    - 检索同义词：journamation, recording, program file, play journal file, journal manager

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 31.3 功能点：录制操作记录  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_JOURNAL_RECORD`
- **菜单路径**：工具(T) › 操作记录(J) › 录制(R)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 操作记录(J)**。
2. 在展开项中选择 **录制(R)...**（命令 ID：`UG_JOURNAL_RECORD`）。
3. 按对话框提示操作：将互动式会话录制为操作记录文件。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将互动式会话录制为操作记录文件。
    - 检索同义词：journamation, track, program file, journal record

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 31.4 功能点：停止操作记录录制  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_JOURNAL_STOP`
- **菜单路径**：工具(T) › 操作记录(J) › 停止录制(S)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 操作记录(J)**。
2. 在展开项中选择 **停止录制(S)**（命令 ID：`UG_JOURNAL_STOP`）。
3. 按对话框提示操作：停止录制操作记录会话。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：停止录制操作记录会话。
    - 检索同义词：journamation, halt, end, stop recording

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 32. 子模块：曲线(C)

本子模块 4 个功能点。

### 32.1 功能点：曲线连续性分析  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_INFO_ANALYSIS_CURVE_CONTINUITY`
- **菜单路径**：分析(L) › 曲线(C) › 连续性(Y)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 7 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **分析(L) › 曲线(C)**。
2. 在展开项中选择 **连续性(Y)...**（命令 ID：`UG_INFO_ANALYSIS_CURVE_CONTINUITY`）。
3. 按对话框提示操作：检查曲线偏差，如面、曲线、边或基准平面法线的位置、相切、曲率和流变化。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：检查曲线偏差，如面、曲线、边或基准平面法线的位置、相切、曲率和流变化。
    - 检索同义词：Tangent, curvature, flow, acceleration, edge, G0, G1, G2, G3

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 32.2 功能点：曲线分析...  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_INFO_ANALYSIS_CURVE_CURVATURE`
- **菜单路径**：分析(L) › 曲线(C) › 曲线分析(U)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 7 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **分析(L) › 曲线(C)**。
2. 在展开项中选择 **曲线分析(U)...**（命令 ID：`UG_INFO_ANALYSIS_CURVE_CURVATURE`）。
3. 按对话框提示操作：通过动态显示曲线或边上的曲率梳图、曲率峰值点或曲率拐点，分析边或曲线的形状。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：通过动态显示曲线或边上的曲率梳图、曲率峰值点或曲率拐点，分析边或曲线的形状。
    - 检索同义词：curvature needles, comb options

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 32.3 功能点：曲线曲率图选项...  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_INFO_ANALYSIS_CURVE_GRAFO`
- **菜单路径**：分析(L) › 曲线(C) › 图选项(A)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 4 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **分析(L) › 曲线(C)**。
2. 在展开项中选择 **图选项(A)...**（命令 ID：`UG_INFO_ANALYSIS_CURVE_GRAFO`）。
3. 按对话框提示操作：设置曲线曲率图显示选项。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：设置曲线曲率图显示选项。
    - 检索同义词：chart, diagram, curve analysis - graph options

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 32.4 功能点：曲线分析信息选项...  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_INFO_ANALYSIS_CURVE_LISTO`
- **菜单路径**：分析(L) › 曲线(C) › 分析信息选项(T)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 4 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **分析(L) › 曲线(C)**。
2. 在展开项中选择 **分析信息选项(T)...**（命令 ID：`UG_INFO_ANALYSIS_CURVE_LISTO`）。
3. 按对话框提示操作：为选定的曲线分析对象列出分析数据。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：为选定的曲线分析对象列出分析数据。
    - 检索同义词：curve analysis - output listing options

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 33. 子模块：补充几何信息(G)

本子模块 4 个功能点。

### 33.1 功能点：PMI 中心线  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_CRE_3DCENTERLINE`
- **菜单路径**：PMI › 补充几何信息(G) › 中心线(C)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI › 补充几何信息(G)**。
2. 在展开项中选择 **中心线(C)...**（命令 ID：`UG_PMI_CRE_3DCENTERLINE`）。
3. 按对话框提示操作：创建中心线。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建中心线。
    - 检索同义词：pmi

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 33.2 功能点：PMI 螺栓圆中心线  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_CRE_BOLTCIRCLECENTERLINE`
- **菜单路径**：PMI › 补充几何信息(G) › 螺栓圆中心线(B)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI › 补充几何信息(G)**。
2. 在展开项中选择 **螺栓圆中心线(B)...**（命令 ID：`UG_PMI_CRE_BOLTCIRCLECENTERLINE`）。
3. 按对话框提示操作：创建完整或部分螺栓圆中心线。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建完整或部分螺栓圆中心线。
    - 检索同义词：pmi

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 33.3 功能点：PMI 中心标记  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_CRE_CENTERMARK`
- **菜单路径**：PMI › 补充几何信息(G) › 中心标记(K)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI › 补充几何信息(G)**。
2. 在展开项中选择 **中心标记(K)...**（命令 ID：`UG_PMI_CRE_CENTERMARK`）。
3. 按对话框提示操作：创建中心标记。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建中心标记。
    - 检索同义词：pmi

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 33.4 功能点：PMI 区域  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_REGIONS`
- **菜单路径**：PMI › 补充几何信息(G) › 区域(R)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI › 补充几何信息(G)**。
2. 在展开项中选择 **区域(R)...**（命令 ID：`UG_PMI_REGIONS`）。
3. 按对话框提示操作：创建区域（矩形、圆形等等）以用于表示部件上的限制区域。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建区域（矩形、圆形等等）以用于表示部件上的限制区域。
    - 检索同义词：pmi regions

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 34. 子模块：nx_pts_view_popup

本子模块 3 个功能点。

### 34.1 功能点：重复命令(R)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_TOOLS_REPEAT_VIEW_MENU`
- **来源提示**：`nx_pts_view_popup.men`
- **出现菜单**：`DRAFTING/application/nx_title_block_view_popup.men` 等 6 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/nx_pts_view_popup_men_simpl_chinese.txt` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_title_block_view_popup.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「重复命令(R)」定位。
2. 按对话框提示操作：列出上次使用的命令。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出上次使用的命令。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 34.2 功能点：适合窗口  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_VIEW_POPUP_FIT`
- **快捷键**：`F6`
- **定义来源**：`UGII/menus/definitions_main.btn`
- **来源提示**：`nx_pts_view_popup.men`
- **出现菜单**：`DRAFTING/application/nx_title_block_view_popup.men` 等 6 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/nx_pts_view_popup_men_simpl_chinese.txt` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `UGII/menus/definitions_main.btn`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「适合窗口」定位。
2. 可直接使用快捷键 **F6** 调用（该快捷键来自介质 `.btn` 定义）。
3. 按对话框提示操作：调整光标所在视图的中心和比例以显示所有对象。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：调整光标所在视图的中心和比例以显示所有对象。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 34.3 功能点：刷新  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_VIEW_POPUP_REFRESH`
- **快捷键**：`F5`
- **定义来源**：`UGII/menus/definitions_main.btn`
- **来源提示**：`nx_pts_view_popup.men`
- **出现菜单**：`DRAFTING/application/nx_title_block_view_popup.men` 等 6 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/nx_pts_view_popup_men_simpl_chinese.txt` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `UGII/menus/definitions_main.btn`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「刷新」定位。
2. 可直接使用快捷键 **F5** 调用（该快捷键来自介质 `.btn` 定义）。
3. 按对话框提示操作：重画图形窗口中的所有视图，（例如）以擦除临时显示的对象。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：重画图形窗口中的所有视图，（例如）以擦除临时显示的对象。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 35. 子模块：几何公差(T)

本子模块 3 个功能点。

### 35.1 功能点：公差特征关联对象  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_GDT_INFO_ASSOCIATED`
- **菜单路径**：几何公差(T) › 关联对象(A)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **几何公差(T)**。
2. 在展开项中选择 **关联对象(A)...**（命令 ID：`UG_PMI_GDT_INFO_ASSOCIATED`）。
3. 按对话框提示操作：查找指定的关联，例如与公差特征关联的基准参考。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：查找指定的关联，例如与公差特征关联的基准参考。
    - 检索同义词：gdt associated objects, gd&t associated objects

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 35.2 功能点：列出所有公差特征  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_GDT_INFO_LIST_ALL`
- **菜单路径**：几何公差(T) › 全部列出(L)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **几何公差(T)**。
2. 在展开项中选择 **全部列出(L)...**（命令 ID：`UG_PMI_GDT_INFO_LIST_ALL`）。
3. 按对话框提示操作：列出有关部件中公差特征的所有信息。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出有关部件中公差特征的所有信息。
    - 检索同义词：gdt list all, gd&t list all

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 35.3 功能点：公差特征搜索  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_GDT_INFO_SEARCH`
- **菜单路径**：几何公差(T) › 搜索(S)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **几何公差(T)**。
2. 在展开项中选择 **搜索(S)...**（命令 ID：`UG_PMI_GDT_INFO_SEARCH`）。
3. 按对话框提示操作：基于各类搜索准则搜索公差特征。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：基于各类搜索准则搜索公差特征。
    - 检索同义词：find, locate, gdt search, gd&t search

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 36. 子模块：安全标记(K)

本子模块 3 个功能点。

### 36.1 功能点：公司专有信息  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_COMPANY_PROPRIETARY`
- **菜单路径**：PMI › 安全标记(K) › 公司专有信息(C)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI › 安全标记(K)**。
2. 在展开项中选择 **公司专有信息(C)...**（命令 ID：`UG_PMI_COMPANY_PROPRIETARY`）。
3. 按对话框提示操作：将部件标记为公司专有，以仅供内部使用或供外部使用。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将部件标记为公司专有，以仅供内部使用或供外部使用。
    - 检索同义词：pmi

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 36.2 功能点：导出控制  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_EXPORT_CONTROL`
- **菜单路径**：PMI › 安全标记(K) › 导出控制(E)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI › 安全标记(K)**。
2. 在展开项中选择 **导出控制(E)...**（命令 ID：`UG_PMI_EXPORT_CONTROL`）。
3. 按对话框提示操作：将导出控制指令添加到部件文件。 。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将导出控制指令添加到部件文件。 
    - 检索同义词：pmi

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 36.3 功能点：政府安全信息  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_GOVERNMENT_SECURITY`
- **菜单路径**：PMI › 安全标记(K) › 政府安全信息(G)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI › 安全标记(K)**。
2. 在展开项中选择 **政府安全信息(G)...**（命令 ID：`UG_PMI_GOVERNMENT_SECURITY`）。
3. 按对话框提示操作：将政府安全信息添加到部件文件。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将政府安全信息添加到部件文件。
    - 检索同义词：pmi

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 37. 子模块：定制菜单栏(C)

本子模块 3 个功能点。

### 37.1 功能点：快捷键  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_INFO_MB_ACCELERATORS`
- **菜单路径**：信息(I) › 定制菜单栏(C) › 快捷键(S)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **信息(I) › 定制菜单栏(C)**。
2. 在展开项中选择 **快捷键(S)**（命令 ID：`UG_INFO_MB_ACCELERATORS`）。
3. 按对话框提示操作：列出当前应用模块中定义的所有键盘快捷键以及它们相关联的命令。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出当前应用模块中定义的所有键盘快捷键以及它们相关联的命令。
    - 检索同义词：keyboard shortcuts, hot keys, hotkeys, accelerators

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 37.2 功能点：菜单栏定制项报告  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_INFO_MB_CUSTOM_ITEMS`
- **菜单路径**：信息(I) › 定制菜单栏(C) › 定制项报告(C)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **信息(I) › 定制菜单栏(C)**。
2. 在展开项中选择 **定制项报告(C)**（命令 ID：`UG_INFO_MB_CUSTOM_ITEMS`）。
3. 按对话框提示操作：列出有关菜单栏菜单和视图快捷菜单中定制项的信息。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出有关菜单栏菜单和视图快捷菜单中定制项的信息。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 37.3 功能点：菜单栏报告工具  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_INFO_MB_REPORT_TOOL`
- **菜单路径**：信息(I) › 定制菜单栏(C) › 报告工具(R)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **信息(I) › 定制菜单栏(C)**。
2. 在展开项中选择 **报告工具(R)...**（命令 ID：`UG_INFO_MB_REPORT_TOOL`）。
3. 按对话框提示操作：提供审核、验证和管理菜单栏定制的选项。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：提供审核、验证和管理菜单栏定制的选项。
    - 检索同义词：menubar report tool, menu bar report tool

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 38. 子模块：导入(P)

本子模块 3 个功能点。

### 38.1 功能点：导入属性  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_IMPORT_ATTS`
- **菜单路径**：编辑(E) › 表(B) › 导入(P) › 属性(A)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_title_block.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B) › 导入(P)**。
2. 在展开项中选择 **属性(A)...**（命令 ID：`UG_TABLE_IMPORT_ATTS`）。
3. 按对话框提示操作：将属性导入单元格。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将属性导入单元格。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 38.2 功能点：导入表达式  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_IMPORT_EXPS`
- **菜单路径**：编辑(E) › 表(B) › 导入(P) › 表达式(E)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_title_block.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B) › 导入(P)**。
2. 在展开项中选择 **表达式(E)...**（命令 ID：`UG_TABLE_IMPORT_EXPS`）。
3. 按对话框提示操作：将表达式导入单元格。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将表达式导入单元格。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 38.3 功能点：导入电子表格  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_IMPORT_SS`
- **菜单路径**：编辑(E) › 表(B) › 导入(P) › 电子表格(S)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_title_block.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B) › 导入(P)**。
2. 在展开项中选择 **电子表格(S)...**（命令 ID：`UG_TABLE_IMPORT_SS`）。
3. 按对话框提示操作：将电子表格的内容导入表。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将电子表格的内容导入表。
    - 检索同义词：Excel, Xess

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 39. 子模块：尺寸(E)

本子模块 3 个功能点。

### 39.1 功能点：编辑特征尺寸  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_EDIT_VALUE`
- **菜单路径**：编辑(E) › 尺寸(E) › 特征尺寸(F)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 尺寸(E)**。
2. 在展开项中选择 **特征尺寸(F)...**（命令 ID：`UG_DRAFT_EDIT_VALUE`）。
3. 按对话框提示操作：编辑选定的特征尺寸。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：编辑选定的特征尺寸。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 39.2 功能点：编辑尺寸  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_EDIT_DIMENSION`
- **菜单路径**：编辑(E) › 尺寸(E) › 编辑尺寸
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 3 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 尺寸(E)**。
2. 在展开项中选择 **编辑尺寸**（命令 ID：`UG_PMI_EDIT_DIMENSION`）。
3. 按对话框提示操作：编辑尺寸的首选项或附加文本。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：编辑尺寸的首选项或附加文本。
    - 检索同义词：add parameters to dimension text

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 39.3 功能点：编辑坐标尺寸  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_EDIT_ORDINATE`
- **菜单路径**：编辑(E) › 尺寸(E) › 坐标(R)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 尺寸(E)**。
2. 在展开项中选择 **坐标(R)...**（命令 ID：`UG_PMI_EDIT_ORDINATE`）。
3. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 40. 子模块：插入(I)

本子模块 3 个功能点。

### 40.1 功能点：附注  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_JOURNAL_INSERT_COMMENT`
- **菜单路径**：工具(T) › 操作记录(J) › 插入(I) › 附注(C)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 操作记录(J) › 插入(I)**。
2. 在展开项中选择 **附注(C)...**（命令 ID：`UG_JOURNAL_INSERT_COMMENT`）。
3. 按对话框提示操作：在录制会话过程中，将附注插入操作记录文件。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在录制会话过程中，将附注插入操作记录文件。
    - 检索同义词：journamation, insert journal comments

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 40.2 功能点：插入用户暂停  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_JOURNAL_INSERT_PAUSE`
- **菜单路径**：工具(T) › 操作记录(J) › 插入(I) › 用户暂停(P)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 操作记录(J) › 插入(I)**。
2. 在展开项中选择 **用户暂停(P)**（命令 ID：`UG_JOURNAL_INSERT_PAUSE`）。
3. 按对话框提示操作：在录制会话过程中，将暂停插入操作记录文件。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在录制会话过程中，将暂停插入操作记录文件。
    - 检索同义词：journamation, wait, break, freeze, hesitate, journal user pause

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 40.3 功能点：用户定义代码  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_JOURNAL_INSERT_USER_DEFINED`
- **菜单路径**：工具(T) › 操作记录(J) › 插入(I) › 用户定义代码(U)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 操作记录(J) › 插入(I)**。
2. 在展开项中选择 **用户定义代码(U)...**（命令 ID：`UG_JOURNAL_INSERT_USER_DEFINED`）。
3. 按对话框提示操作：在录制会话过程中，将用户定义代码插入操作记录文件。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在录制会话过程中，将用户定义代码插入操作记录文件。
    - 检索同义词：journamation, insert user defined journal code

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 41. 子模块：标注(C)

本子模块 3 个功能点。

### 41.1 功能点：水平分组  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_CALLOUT_GROUP_HORIZONTAL`
- **菜单路径**：编辑(E) › 表(B) › 标注(C) › 水平分组(H)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B) › 标注(C)**。
2. 在展开项中选择 **水平分组(H)...**（命令 ID：`UG_TABLE_CALLOUT_GROUP_HORIZONTAL`）。
3. 按对话框提示操作：对选定标注分组，并使用一条指引线将其置于水平布局。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：对选定标注分组，并使用一条指引线将其置于水平布局。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 41.2 功能点：竖直分组  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_CALLOUT_GROUP_VERTICAL`
- **菜单路径**：编辑(E) › 表(B) › 标注(C) › 竖直分组(V)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B) › 标注(C)**。
2. 在展开项中选择 **竖直分组(V)...**（命令 ID：`UG_TABLE_CALLOUT_GROUP_VERTICAL`）。
3. 按对话框提示操作：对选定标注分组，并使用一条指引线将其置于竖直布局。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：对选定标注分组，并使用一条指引线将其置于竖直布局。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 41.3 功能点：对标注取消分组  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_CALLOUT_UNGROUP`
- **菜单路径**：编辑(E) › 表(B) › 标注(C) › 取消分组(U)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B) › 标注(C)**。
2. 在展开项中选择 **取消分组(U)**（命令 ID：`UG_TABLE_CALLOUT_UNGROUP`）。
3. 按对话框提示操作：对标注取消分组并恢复各条指引线。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：对标注取消分组并恢复各条指引线。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 42. 子模块：电影(E)

本子模块 3 个功能点。

### 42.1 功能点：录制电影  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_MOVIE_RECORD`
- **菜单路径**：工具(T) › 电影(E) › 录制(R)...
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 9 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 电影(E)**。
2. 在展开项中选择 **录制(R)...**（命令 ID：`UG_MOVIE_RECORD`）。
3. 按对话框提示操作：将交互信息录制为电影文件。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将交互信息录制为电影文件。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 42.2 功能点：电影录制设置  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_MOVIE_SETTINGS`
- **菜单路径**：工具(T) › 电影(E) › 设置(T)...
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 9 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 电影(E)**。
2. 在展开项中选择 **设置(T)...**（命令 ID：`UG_MOVIE_SETTINGS`）。
3. 按对话框提示操作：修改电影录制的设置。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：修改电影录制的设置。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 42.3 功能点：停止电影录制  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_MOVIE_STOP`
- **菜单路径**：工具(T) › 电影(E) › 停止(S)
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 9 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 电影(E)**。
2. 在展开项中选择 **停止(S)**（命令 ID：`UG_MOVIE_STOP`）。
3. 按对话框提示操作：停止电影的录制。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：停止电影的录制。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 43. 子模块：行(R)

本子模块 3 个功能点。

### 43.1 功能点：插入标题行  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_INSERT_HEADER_ROW`
- **菜单路径**：编辑(E) › 表(B) › 插入(I) › 行(R) › 标题行(H)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_title_block.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B) › 插入(I) › 行(R)**。
2. 在展开项中选择 **标题行(H)**（命令 ID：`UG_TABLE_INSERT_HEADER_ROW`）。
3. 按对话框提示操作：在选定行的表区域的顶部或底部插入标题行。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在选定行的表区域的顶部或底部插入标题行。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 43.2 功能点：上方插入行  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_INSERT_ROWS_ABOVE`
- **菜单路径**：编辑(E) › 表(B) › 插入(I) › 行(R) › 上方(A)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_title_block.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B) › 插入(I) › 行(R)**。
2. 在展开项中选择 **上方(A)**（命令 ID：`UG_TABLE_INSERT_ROWS_ABOVE`）。
3. 按对话框提示操作：在选定的行上方插入一行。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在选定的行上方插入一行。
    - 检索同义词：insert rows

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 43.3 功能点：下方插入行  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_INSERT_ROWS_BELOW`
- **菜单路径**：编辑(E) › 表(B) › 插入(I) › 行(R) › 下方(B)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_title_block.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B) › 插入(I) › 行(R)**。
2. 在展开项中选择 **下方(B)**（命令 ID：`UG_TABLE_INSERT_ROWS_BELOW`）。
3. 按对话框提示操作：在选定的行下方插入一行。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在选定的行下方插入一行。
    - 检索同义词：insert rows

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 44. 子模块：2D 组件顺序

本子模块 2 个功能点。

### 44.1 功能点：编辑布局中的顺序  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_NXLAYOUT_EDIT_ORDERS_IN_LAYOUT`
- **菜单路径**：工具(T) › 布局(T) › 2D 组件顺序 › 编辑布局中的顺序(O)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 布局(T) › 2D 组件顺序**。
2. 在展开项中选择 **编辑布局中的顺序(O)...**（命令 ID：`UG_NXLAYOUT_EDIT_ORDERS_IN_LAYOUT`）。
3. 按对话框提示操作：创建并编辑 2D 组件顺序，定义 2D 组件在部件导航器的“草图”节点中的显示顺序。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建并编辑 2D 组件顺序，定义 2D 组件在部件导航器的“草图”节点中的显示顺序。
    - 可用性提示：This command is available only with the NX Layout license.
    - 检索同义词：Navigator

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 44.2 功能点：重排序 2D 组件  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_NXLAYOUT_REORDER_2D_COMPONENTS`
- **菜单路径**：工具(T) › 布局(T) › 2D 组件顺序 › 重排序 2D 组件...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 布局(T) › 2D 组件顺序**。
2. 在展开项中选择 **重排序 2D 组件...**（命令 ID：`UG_NXLAYOUT_REORDER_2D_COMPONENTS`）。
3. 按对话框提示操作：在布局结构中重排序 2D 组件。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在布局结构中重排序 2D 组件。
    - 可用性提示：This command is available only with the NX Layout license.
    - 检索同义词：Layout, Navigator

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 45. 子模块：列(C)

本子模块 2 个功能点。

### 45.1 功能点：左边插入列  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_INSERT_COLS_LEFT`
- **菜单路径**：编辑(E) › 表(B) › 插入(I) › 列(C) › 在左边(L)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_title_block.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B) › 插入(I) › 列(C)**。
2. 在展开项中选择 **在左边(L)**（命令 ID：`UG_TABLE_INSERT_COLS_LEFT`）。
3. 按对话框提示操作：在选定列的左边插入一列。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在选定列的左边插入一列。
    - 检索同义词：insert columns

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 45.2 功能点：右边插入列  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_TABLE_INSERT_COLS_RIGHT`
- **菜单路径**：编辑(E) › 表(B) › 插入(I) › 列(C) › 在右边(R)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_title_block.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 表(B) › 插入(I) › 列(C)**。
2. 在展开项中选择 **在右边(R)**（命令 ID：`UG_TABLE_INSERT_COLS_RIGHT`）。
3. 按对话框提示操作：在选定列的右边插入一列。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在选定列的右边插入一列。
    - 检索同义词：insert columns

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 46. 子模块：图纸比较(R)

本子模块 2 个功能点。

### 46.1 功能点：跟踪图纸更改  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_TRACK_DRAWING_CHANGES`
- **菜单路径**：分析(L) › 图纸比较(R) › 跟踪图纸更改(T)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **分析(L) › 图纸比较(R)**。
2. 在展开项中选择 **跟踪图纸更改(T)...**（命令 ID：`UG_DRAFT_TRACK_DRAWING_CHANGES`）。
3. 按对话框提示操作：将当前图纸的对象与另一文件进行比较，或与之前保存的数据快照进行比较。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将当前图纸的对象与另一文件进行比较，或与之前保存的数据快照进行比较。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 46.2 功能点：视觉叠加  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_VISUAL_OVERLAY`
- **菜单路径**：分析(L) › 图纸比较(R) › 视觉叠加(V)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **分析(L) › 图纸比较(R)**。
2. 在展开项中选择 **视觉叠加(V)...**（命令 ID：`UG_DRAFT_VISUAL_OVERLAY`）。
3. 按对话框提示操作：将另一部件文件中的数据或同一部件文件中之前创建的叠加数据叠加在活动图纸之上。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将另一部件文件中的数据或同一部件文件中之前创建的叠加数据叠加在活动图纸之上。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 47. 子模块：图纸自动化(O)

本子模块 2 个功能点。

### 47.1 功能点：注释视图  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAWING_AUTOMATION_ANNOTATE_VIEWS`
- **菜单路径**：工具(T) › 图纸自动化(O) › 注释视图(A)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 图纸自动化(O)**。
2. 在展开项中选择 **注释视图(A)...**（命令 ID：`UG_DRAWING_AUTOMATION_ANNOTATE_VIEWS`）。
3. 按对话框提示操作：在指定视图中基于一组预定义的规则创建注释。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在指定视图中基于一组预定义的规则创建注释。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 47.2 功能点：分布注释  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAWING_AUTOMATION_DISTRIBUTE_ANNOTATIONS`
- **菜单路径**：工具(T) › 图纸自动化(O) › 分布注释(D)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 图纸自动化(O)**。
2. 在展开项中选择 **分布注释(D)...**（命令 ID：`UG_DRAWING_AUTOMATION_DISTRIBUTE_ANNOTATIONS`）。
3. 按对话框提示操作：在指定视图中均匀地分布注释。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在指定视图中均匀地分布注释。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 48. 子模块：截面(S)

本子模块 2 个功能点。

### 48.1 功能点：编辑截面  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_VIEW_SECTIONING`
- **菜单路径**：视图(V) › 截面(S) › 编辑截面(C)...
- **快捷键**：`Ctrl+H`
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **视图(V) › 截面(S)**。
2. 在展开项中选择 **编辑截面(C)...**（命令 ID：`UG_VIEW_SECTIONING`）。
3. 可直接使用快捷键 **Ctrl+H** 调用（该快捷键来自介质 `.btn` 定义）。
4. 按对话框提示操作：编辑工作视图截面或者在没有截面的情况下新建截面。装配导航器列出所有现有截面。
5. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：编辑工作视图截面或者在没有截面的情况下新建截面。装配导航器列出所有现有截面。
    - 检索同义词：cut, slice, dynamic clip, clipping, view sectioning, section{3}

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 48.2 功能点：新建截面  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_VIEW_SECTION_CREATE`
- **菜单路径**：视图(V) › 截面(S) › 新建截面(T)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **视图(V) › 截面(S)**。
2. 在展开项中选择 **新建截面(T)...**（命令 ID：`UG_VIEW_SECTION_CREATE`）。
3. 按对话框提示操作：创建新的动态截面对象并在工作视图中激活它。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建新的动态截面对象并在工作视图中激活它。
    - 检索同义词：cut, slice, dynamic clip, clipping, view section, view sectioning, section{1}

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 49. 子模块：捕捉点(O)

本子模块 2 个功能点。

### 49.1 功能点：点对话框  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_INFER_DIALOG`
- **菜单路径**：捕捉点(O) › 点对话框
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 8 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **捕捉点(O)**。
2. 在展开项中选择 **点对话框**（命令 ID：`UG_INFER_DIALOG`）。
3. 按对话框提示操作：使用完整的“点”对话框来选择点。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：使用完整的“点”对话框来选择点。
    - 可用性提示：EXCLUDE_FROM_COMMAND_FINDER

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 49.2 功能点：清除捕捉点  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_INFER_RESET`
- **菜单路径**：捕捉点(O) › 清除捕捉点
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 8 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **捕捉点(O)**。
2. 在展开项中选择 **清除捕捉点**（命令 ID：`UG_INFER_RESET`）。
3. 按对话框提示操作：清除所有捕捉点设置。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：清除所有捕捉点设置。
    - 可用性提示：EXCLUDE_FROM_COMMAND_FINDER

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 50. 子模块：插入(S)

本子模块 2 个功能点。

### 50.1 功能点：图像  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_DRAFT_CRE_IMAGE`
- **菜单路径**：插入(S) › 图像(I)...
- **定义来源**：`DRAFTING/startup/definitions_drafting.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_app.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S)**。
2. 在展开项中选择 **图像(I)...**（命令 ID：`UG_DRAFT_CRE_IMAGE`）。
3. 按对话框提示操作：在图纸页上放置光栅图像（.jpg、.png 或 .tif）。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在图纸页上放置光栅图像（.jpg、.png 或 .tif）。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 50.2 功能点：新建图纸页  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_DRW_NEW`
- **菜单路径**：插入(S) › 图纸页(H)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **插入(S)**。
2. 在展开项中选择 **图纸页(H)...**（命令 ID：`UG_DRAFT_DRW_NEW`）。
3. 按对话框提示操作：新建图纸页。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：新建图纸页。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 51. 子模块：标题栏

本子模块 2 个功能点。

### 51.1 功能点：退出编辑表  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_TITLE_BLOCK_EXIT`
- **来源提示**：`nx_title_block.men`
- **出现菜单**：`DRAFTING/application/nx_title_block.men` 等 2 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/nx_title_block_men_simpl_chinese.txt` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_title_block.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「退出编辑表」定位。
2. 按对话框提示操作：退出“标题块”任务环境。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：退出“标题块”任务环境。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 51.2 功能点：完成编辑表  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_TITLE_BLOCK_FINISH`
- **来源提示**：`nx_title_block.men`
- **出现菜单**：`DRAFTING/application/nx_title_block.men` 等 2 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/nx_title_block_men_simpl_chinese.txt` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_title_block.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「完成编辑表」定位。
2. 按对话框提示操作：退出“编辑标题块表”任务环境并传播任何更改。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：退出“编辑标题块表”任务环境并传播任何更改。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 52. 子模块：注释(O)

本子模块 2 个功能点。

### 52.1 功能点：编辑注释原点  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_EDIT_MOVE_ORIGIN`
- **菜单路径**：编辑(E) › 注释(O) › 原点(G)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 注释(O)**。
2. 在展开项中选择 **原点(G)...**（命令 ID：`UG_PMI_EDIT_MOVE_ORIGIN`）。
3. 按对话框提示操作：编辑注释的位置。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：编辑注释的位置。
    - 检索同义词：origin tool

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 52.2 功能点：编辑注释  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_EDIT_OBJECT`
- **菜单路径**：编辑(E) › 注释(O) › 注释对象(O)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 注释(O)**。
2. 在展开项中选择 **注释对象(O)**（命令 ID：`UG_PMI_EDIT_OBJECT`）。
3. 按对话框提示操作：基于选定注释对象的类型编辑注释。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：基于选定注释对象的类型编辑注释。
    - 检索同义词：modifying crosshatch, modify crosshatch patterns, controlling the cutting line display, reference dimension, decimal places and trailing zeros, specify an existing text style as the current style, display dimension text symbols, add text to a dimension, add a new leader, add a jog to a leader

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 53. 子模块：窗口(O)

本子模块 2 个功能点。

### 53.1 功能点：重置布局  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_WINDOW_RESET_LAYOUT`
- **菜单路径**：窗口(O) › 重置布局(R)；窗口 › 重置布局(R)
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 8 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **窗口(O)**。
2. 在展开项中选择 **重置布局(R)**（命令 ID：`UG_WINDOW_RESET_LAYOUT`）。
3. 按对话框提示操作：将所有框架中的所有选项卡式窗口移至主框架的一个选项卡式组中。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将所有框架中的所有选项卡式窗口移至主框架的一个选项卡式组中。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 53.2 功能点：切换窗口  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_WINDOW_SWITCH`
- **菜单路径**：窗口(O) › 切换窗口...；窗口 › 切换窗口...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 6 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **窗口(O)**。
2. 在展开项中选择 **切换窗口...**（命令 ID：`UG_WINDOW_SWITCH`）。
3. 按对话框提示操作：列出之前显示的部件并将显示部件改为指定的一个部件。(Ctrl+Tab)。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出之前显示的部件并将显示部件改为指定的一个部件。(Ctrl+Tab)

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 54. 子模块：符号(Y)

本子模块 2 个功能点。

### 54.1 功能点：定制符号  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_CRE_SYMBOLS`
- **菜单路径**：PMI › 符号(Y) › 定制(C)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI › 符号(Y)**。
2. 在展开项中选择 **定制(C)...**（命令 ID：`UG_PMI_CRE_SYMBOLS`）。
3. 按对话框提示操作：根据符号库创建定制符号的实例。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：根据符号库创建定制符号的实例。
    - 检索同义词：insert, pmi

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 54.2 功能点：定义定制符号  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_PMI_DEFINE_SYMBOL`
- **菜单路径**：PMI › 符号(Y) › 定义定制符号(E)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`UGII/menus/ug_main.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **PMI › 符号(Y)**。
2. 在展开项中选择 **定义定制符号(E)...**（命令 ID：`UG_PMI_DEFINE_SYMBOL`）。
3. 按对话框提示操作：定义定制符号。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：定义定制符号。
    - 检索同义词：store a symbol, user-defined weld symbol, pmi

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 55. 子模块：通透显示样式

本子模块 2 个功能点。

### 55.1 功能点：通透显示原始颜色壳  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_VIEW_SEE_THRU_STYLE_ORIGINAL_COLOR_SHELL`
- **菜单路径**：通透显示样式 › 通透显示原始颜色壳
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 9 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **通透显示样式**。
2. 在展开项中选择 **通透显示原始颜色壳**（命令 ID：`UG_VIEW_SEE_THRU_STYLE_ORIGINAL_COLOR_SHELL`）。
3. 按对话框提示操作：将已取消着重的着色几何体显示为透明壳，同时保留原始颜色。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将已取消着重的着色几何体显示为透明壳，同时保留原始颜色。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 55.2 功能点：通透显示壳  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_VIEW_SEE_THRU_STYLE_SHELL`
- **菜单路径**：通透显示样式 › 通透显示壳
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 9 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **通透显示样式**。
2. 在展开项中选择 **通透显示壳**（命令 ID：`UG_VIEW_SEE_THRU_STYLE_SHELL`）。
3. 按对话框提示操作：使用一种颜色将已取消着重的着色几何体显示为透明壳。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：使用一种颜色将已取消着重的着色几何体显示为透明壳。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 56. 子模块：部件(R)

本子模块 2 个功能点。

### 56.1 功能点：部件历史记录  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_INFO_PART_HISTORY`
- **菜单路径**：信息(I) › 部件(R) › 部件历史记录(H)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **信息(I) › 部件(R)**。
2. 在展开项中选择 **部件历史记录(H)...**（命令 ID：`UG_INFO_PART_HISTORY`）。
3. 按对话框提示操作：列出部件的保存历史记录。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出部件的保存历史记录。
    - 检索同义词：revisions

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

### 56.2 功能点：部件修改  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_INFO_PART_MODIFICATIONS`
- **菜单路径**：信息(I) › 部件(R) › 修改(M)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 2 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **信息(I) › 部件(R)**。
2. 在展开项中选择 **修改(M)...**（命令 ID：`UG_INFO_PART_MODIFICATIONS`）。
3. 按对话框提示操作：列出相对于特定部件版本创建的或上一次修改的对象。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：列出相对于特定部件版本创建的或上一次修改的对象。
    - 检索同义词：edits, info part modifications

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 57. 子模块：WCS

本子模块 1 个功能点。

### 57.1 功能点：WCS 设为绝对  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_WCS_SET_TO_ABS`
- **菜单路径**：格式(R) › WCS › WCS 设为绝对(A)；视图(V) › 操作(O) › WCS 设为绝对(A)
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **格式(R) › WCS**。
2. 在展开项中选择 **WCS 设为绝对(A)**（命令 ID：`UG_WCS_SET_TO_ABS`）。
3. 按对话框提示操作：将 WCS 转为绝对坐标系的位置和方位。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：将 WCS 转为绝对坐标系的位置和方位。
    - 检索同义词：workplane, work plane, coordinate system

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 58. 子模块：ms_drafting_menu

本子模块 1 个功能点。

### 58.1 功能点：MS_DRAFTING_MENU_BTN  `[NX12.0-CN] [E3-UNTR]`

- **命令 ID**：`MS_DRAFTING_MENU_BTN`
- **出现菜单**：`MS_NXTOOLS/Application/ms_drafting_menu.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `MS_NXTOOLS/Application/ms_drafting_menu.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「MS_DRAFTING_MENU_BTN」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 59. 子模块：nx_geodesic_sketch

本子模块 1 个功能点。

### 59.1 功能点：任务(K)  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_FILE`
- **来源提示**：`nx_geodesic_sketch.men`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/nx_geodesic_sketch_men_simpl_chinese.txt` 等 13 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/application/nx_layout_te.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「任务(K)」定位。
2. [待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - [待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 60. 子模块：nx_layout_te

本子模块 1 个功能点。

### 60.1 功能点：UG_HELP_LEARNING  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_HELP_LEARNING`
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 10 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `UGII/menus/definitions_main.btn`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「UG_HELP_LEARNING」定位。
2. 按对话框提示操作：显示关于 Learning Advantage 及其成员资格选项的信息。Learning Advantage 提供在线自学课程库，供用户获取 Siemens PLM Software 解决方案的技能和知识。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：显示关于 Learning Advantage 及其成员资格选项的信息。Learning Advantage 提供在线自学课程库，供用户获取 Siemens PLM Software 解决方案的技能和知识。
    - 检索同义词：class, teaching, tutorials, cast, training

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 61. 子模块：nx_title_block_view_popup

本子模块 1 个功能点。

### 61.1 功能点：撤消  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_VIEW_POPUP_UNDO`
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_title_block_view_popup.men` 等 6 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `UGII/menus/definitions_main.btn`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「撤消」定位。
2. 按对话框提示操作：撤消上次操作。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：撤消上次操作。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 62. 子模块：ug_view_popup_simviewer

本子模块 1 个功能点。

### 62.1 功能点：更新显示  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_VIEW_POPUP_UPDATE`
- **定义来源**：`UGII/menus/definitions_main.btn`
- **来源提示**：`ug_view_popup_simviewer.men`
- **出现菜单**：`DRAFTING/application/nx_title_block_view_popup.men` 等 6 处
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_view_popup_simviewer_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `UGII/menus/definitions_main.btn`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「更新显示」定位。
2. 按对话框提示操作：执行旋转所需的显示更改（在光标所在的视图中）或比例更改（如隐藏线和轮廓线）。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：执行旋转所需的显示更改（在光标所在的视图中）或比例更改（如隐藏线和轮廓线）。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 63. 子模块：制造视图

本子模块 1 个功能点。

### 63.1 功能点：克隆模型视图  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`MFGVIEWMAKER_CLONE_MODEL_VIEWS_BUTTON`
- **来源提示**：`mfg_view_maker.men`
- **出现菜单**：`DRAFTING/mfg_view_maker/application/mfg_view_maker.men`
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/mfg_view_maker_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 本命令定义于 `DRAFTING/mfg_view_maker/application/mfg_view_maker.men`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「克隆模型视图」定位。
2. 按对话框提示操作：在指定目标下创建模型视图的副本。
3. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在指定目标下创建模型视图的副本。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 64. 子模块：帮助(H)

本子模块 1 个功能点。

### 64.1 功能点：制图教程  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_DRAFT_HELP_TUTORIALS`
- **菜单路径**：帮助(H) › 制图教程(D)...
- **出现菜单**：`DRAFTING/application/ug_drafting.men`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **帮助(H)**。
2. 在展开项中选择 **制图教程(D)...**（命令 ID：`UG_DRAFT_HELP_TUTORIALS`）。
3. 按对话框提示操作：显示自学制图工作流教程。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：显示自学制图工作流教程。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 65. 子模块：形状(H)

本子模块 1 个功能点。

### 65.1 功能点：高亮线  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_INFO_ANALYSIS_HIGHLIGHT_LINES`
- **菜单路径**：分析(L) › 形状(H) › 高亮线(H)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 7 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **分析(L) › 形状(H)**。
2. 在展开项中选择 **高亮线(H)...**（命令 ID：`UG_INFO_ANALYSIS_HIGHLIGHT_LINES`）。
3. 按对话框提示操作：在曲面上生成一组高亮线以辅助评估曲面质量。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：在曲面上生成一组高亮线以辅助评估曲面质量。
    - 检索同义词：reflection highlight lines, projection highlight lines, brighten

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 66. 子模块：文件(F)

本子模块 1 个功能点。

### 66.1 功能点：打印  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_FILE_PRINT`
- **菜单路径**：文件(F) › 打印(P)...；任务(K) › 打印(P)...
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 8 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **文件(F)**。
2. 在展开项中选择 **打印(P)...**（命令 ID：`UG_FILE_PRINT`）。
3. 按对话框提示操作：打印图形窗口中的图像。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：打印图形窗口中的图像。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 67. 子模块：曲线(V)

本子模块 1 个功能点。

### 67.1 功能点：编辑曲线参数  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_EDIT_CURVE_PARAMETERS`
- **菜单路径**：编辑(E) › 曲线(V) › 参数(P)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 5 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **编辑(E) › 曲线(V)**。
2. 在展开项中选择 **参数(P)...**（命令 ID：`UG_EDIT_CURVE_PARAMETERS`）。
3. 按对话框提示操作：编辑大多数类型曲线和点的参数。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：编辑大多数类型曲线和点的参数。

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 68. 子模块：管线布置

本子模块 1 个功能点。

### 68.1 功能点：管线布置物料清单  `[NX12.0-CN] [E2-MENU]`

- **命令 ID**：`UG_ROUTE_BOM`
- **菜单路径**：工具(T) › 管线布置(G) › 物料清单(B)...
- **来源提示**：`ug_route_common.men`
- **出现菜单**：`DRAFTING/application/ug_drafting.men`
- **官方翻译表**：`LOCALIZATION/translations/simpl_chinese/ug_route_common_men_simpl_chinese.txt`

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **工具(T) › 管线布置(G)**。
2. 在展开项中选择 **物料清单(B)...**（命令 ID：`UG_ROUTE_BOM`）。
3. 按对话框提示操作：创建管线布置物料清单。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：创建管线布置物料清单。

**注意事项**：

    - 该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。
    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

## 69. 子模块：高级质量属性(E)

本子模块 1 个功能点。

### 69.1 功能点：用曲线计算面积  `[NX12.0-CN] [E1-MEDIA]`

- **命令 ID**：`UG_INFO_AREA_USING_CURVES`
- **菜单路径**：分析(L) › 高级质量属性(E) › 用曲线计算面积(A)...；分析(L) › 用曲线计算面积(A)...
- **定义来源**：`UGII/menus/definitions_main.btn`
- **出现菜单**：`DRAFTING/application/nx_layout_te.men` 等 4 处

**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：

1. 在中文界面顶部菜单栏依次选择 **分析(L) › 高级质量属性(E)**。
2. 在展开项中选择 **用曲线计算面积(A)...**（命令 ID：`UG_INFO_AREA_USING_CURVES`）。
3. 按对话框提示操作：计算投影到 XC-YC 平面的封闭曲线串的几何属性。
4. 单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。

**参数说明**：

    - 官方功能说明（介质翻译表原文）：计算投影到 XC-YC 平面的封闭曲线串的几何属性。
    - 检索同义词：outline, boundary, periphery, perimeter, physical, inertial, area analysis

**注意事项**：

    - 本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。

