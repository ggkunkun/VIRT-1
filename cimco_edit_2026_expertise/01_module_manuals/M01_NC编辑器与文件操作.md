# M01 NC 编辑器与文件操作 — 标准化操作手册

> 对应模块：Editor 选项卡（Program Tabs > Editor）
> 事实源：`docs.cimco.com/en/docs/edit/2026/program-tabs/editor/*`（A 语料）
> 诚实性基线：`CAPABILITY_BOUNDARIES.md`（本模块不触及 add-on/版本管理边界，仅 B-05：本模块为 NC 编辑器，非几何建模工具）

---

## 1. 模块定位与适用边界

**能做什么**：Editor 选项卡提供 NC 程序的文本编辑基础能力，包括文件新建/打开/保存/打印、多格式关联、文本选择与编辑（复制/剪切/粘贴/撤销/重做）、范围标记删除、从外部文件追加/插入文本、查找与替换（含正则、多文件、结果列表、批量替换）、书签管理、窗口布局与深色主题、全局配置入口。来源：`.../program-tabs/editor/`。

**不能做什么**：
- 不是几何建模工具，无 2D/3D 建模、绘图功能（**B-05**：2D/3D 建模路由 AutoCAD/NX/SOLIDWORKS）。
- "Save as associated file" 会保存到 CIMCO NC-Base，属产品管理域，本手册不展开 NC-Base 的**版本管理**能力（**B-02**：`version control` 语料 0 命中）。
- 本模块不涉及仿真、通信、后处理的参数，分别见 M03/M04/M07/M06。

---

## 2. 官方菜单路径与快捷键（逐条附来源）

### 2.1 File 菜单
路径：Editor 选项卡 > File。来源：`https://docs.cimco.com/en/docs/edit/2026/program-tabs/editor/file/`。

| 命令 | 快捷键 | 功能 | 来源页 |
|---|---|---|---|
| New | Ctrl+N | 创建空程序/文件 | `.../editor/file/` |
| Open | Ctrl+O | 打开文件 | `.../editor/file/` |
| Advanced Open | Ctrl+Alt+O | 按文件名/内容/创建修改日期检索定位文件（Open 图标下拉） | `.../editor/file/` |
| Recent | — | 最近使用文件列表（Open 图标下拉） | `.../editor/file/` |
| Close | Ctrl+F4 | 关闭当前窗口，修改则提示保存 | `.../editor/file/` |
| Close All | — | 关闭所有窗口（Open/Close 图标下拉） | `.../editor/file/` |
| Save | Ctrl+S | 保存当前 CNC 程序 | `.../editor/file/` |
| Save All | — | 按当前名保存所有打开程序（Save 图标下拉） | `.../editor/file/` |
| Save As | — | 以新名保存 | `.../editor/file/` |
| Save as associated file | — | 保存到 CIMCO NC-Base，需选 Machine/Program Name/文件名 | `.../editor/file/` |
| Print | Ctrl+P | 打印（先选中区域可只打印部分） | `.../editor/file/` |
| Printer Setup | — | 打印配置（Print 图标下拉） | `.../editor/file/` |
| Global setup | — | 进入 Editor Setup 全局配置 | `.../editor/file/` |

### 2.2 Edit 菜单
路径：Editor 选项卡 > Edit。来源：`.../program-tabs/editor/edit/`。

| 命令 | 快捷键 | 功能 |
|---|---|---|
| Copy | Ctrl+C | 复制选中文本到剪贴板 |
| Cut | Ctrl+X | 删除选中文本并存入剪贴板 |
| Paste | Ctrl+V | 在光标处插入剪贴板内容 |
| Select All | Ctrl+A | 选中文件全部行 |
| Undo | Ctrl+Z | 撤销上次操作 |
| Redo | Ctrl+Y | 重做上次撤销（可重做自打开以来所有撤销） |
| Mark/Delete range | Ctrl+M | 指定行/块号范围进行更新、选择或删除；可从换刀/进给/主轴值到下一个之间特殊选择（亦可从 NC Functions > Insert/Remove 访问） |
| Append File | — | 将文件追加到当前 CNC 程序末尾 |
| Insert File | — | 在光标位置将文件插入当前窗口 |

### 2.3 Find 菜单
路径：Editor 选项卡 > Find。来源：`.../program-tabs/editor/find/`。

| 命令 | 快捷键 | 功能 |
|---|---|---|
| Find | Ctrl+F | 打开查找对话框（Find what 输入；支持 Match whole string / Ignore case / Use regular expression / Search all / Find NC Command） |
| Find Previous | Shift+F3 | 查找上一处 |
| Find Next | F3 | 查找下一处 |
| Replace | Ctrl+H | 替换对话框（Find what / Replace with / Multiline / Replace in selection only / Result to new window / Replace All from File） |
| Go to Line/Block Number | Ctrl+J | 光标移到指定行/块号 |
| Next Tool Change / Previous Tool Change | — | 移到下一/上一换刀处 |

> Find All 结果列表：显示命中数与文件数，Filter search results 字段为 F6，`< Previous`/`Next >` 为 Shift+F8/F8，双击或 Go to 跳转（来源同上）。

### 2.4 Bookmarks 与 Window
路径：Editor 选项卡 > Bookmarks / Window。来源：`.../editor/bookmarks/`、`.../editor/window/`。

| 命令 | 快捷键 | 功能 |
|---|---|---|
| Go to Previous / Next | Shift+F5 / F5 | 跳到上/下一书签 |
| Add Bookmark (Remove Bookmark) | F2 | 在选中行创建/移除书签（可命名） |
| View Bookmarks | — | 打开书签对话框，列出所有打开文档的书签 |
| Dark Theme | — | 启用深色主题 |
| Cascade / Arrange icons / Tile Horizontally / Tile Vertically | — | 层叠 / 排列图标 / 水平平铺 / 垂直平铺 |

---

## 3. 参数配置规则

### 3.1 Find / Replace 对话框参数（来源：`.../editor/find/`）

| 参数名 | 取值 | 默认值 | 含义 | 来源页 |
|---|---|---|---|---|
| Find what | 文本/正则 | 空（有选中文本时自动填入） | 要查找的字符串 | `.../editor/find/` |
| Match whole string | 开/关 | 关 | 仅精确匹配整串 | `.../editor/find/` |
| Ignore case | 开/关 | 关 | 忽略大小写 | `.../editor/find/` |
| Use regular expression | 开/关 | 关 | 将 Find what 解释为正则，如 `\(\((.*?)\)\)` 匹配 `((` 与 `))` 之间文本 | `.../editor/find/` |
| Search all | 开/关 | 关 | 搜索所有打开文件 | `.../editor/find/` |
| Find NC Command | Tool Change/Feedrate/Spindle Speed | — | 查找 NC 指令，识别方式在 Editor Setup > File Types 配置 | `.../editor/find/` |
| Replace in selection only | 开/关 | 关 | 仅对选中行替换 | `.../editor/find/` |
| Multiline | 开/关 | 关 | 允许 Find what/Replace with 多行 | `.../editor/find/` |
| Delimiter | 字符 | — | Replace All from File 时外部分隔符（如 `T1;T10` 用分号） | `.../editor/find/` |

### 3.2 文件类型与保存参数（来源：`.../editor/filetype/`、`.../editor-setup/file-types/load-save/`）

| 参数名 | 取值 | 默认值 | 含义 | 来源页 |
|---|---|---|---|---|
| File Type | 下拉档案 | 当前档案 | 决定着色、语法、重编方式、换刀识别、Backplot 设置、保存目录 | `.../editor/filetype/` |
| Default extension | 字符串 | — | 新文件保存时追加的扩展名 | `.../editor-setup/file-types/load-save/` |
| Register default extension | 开/关 | — | 在 Windows 注册扩展名关联 | 同上 |
| Save with linefeed type | Auto/DOS/Unix/Mac | Auto | 保存时行尾类型（DOS=CR LF；Unix=LF；Mac=CR） | 同上 |
| Auto save interval | 下拉 | — | 自动保存间隔（覆盖原文件） | 同上 |
| Message when loading UNICODE / Prompt to save as UNICODE | 开/关 | — | UNICODE 文件加载提示/保存提示 | 同上 |

---

## 4. 标准操作步骤

### 4.1 打开并规范化一个 NC 程序
1. 启动 editor，确认 File Type 菜单显示为对应机床档案；检查点：颜色/语法与预期一致（`.../editor/filetype/`）。
2. Ctrl+O 或 Advanced Open（Ctrl+Alt+O）定位文件；检查点：Advanced Open 可按内容/日期筛选（`.../editor/file/`）。
3. 必要时通过 Edit > Append File / Insert File 合并外部程序；检查点：插入位置在光标处、追加在末尾（`.../editor/edit/`）。
4. 编辑后 Ctrl+S 保存；检查点：状态栏无未保存标记，备份 .bak 按 General 配置生成（`.../editor/file/`、`.../editor-setup/general/`）。

### 4.2 批量替换并留存结果
1. Ctrl+H 打开替换对话框；检查点：确认 Ignore case/Match whole string/Multiline 状态（`.../editor/find/`）。
2. 若替换规则来自外部文件，勾选 Replace All from File 并设 Delimiter；检查点：每行一对 find/replace（`.../editor/find/`）。
3. 勾选 Result to new window 生成替换后副本；检查点：原文件保持不变，新窗口为替换结果（`.../editor/find/`）。
4. 用 Find All 列出全部命中并 F6 过滤核查；检查点：命中数与文件数显示正确（`.../editor/find/`）。

### 4.3 书签标记与窗口布局
1. 光标置于关键行按 F2 添加命名书签；检查点：行号高亮显示（须在 Editor Settings 启用 Show line numbers）（`.../editor/bookmarks/`）。
2. F5/Shift+F5 在各书签间跳转；检查点：View Bookmarks 列表显示文件、行号、书签名称与路径（`.../editor/bookmarks/`）。
3. 用 Window 下拉选择 Cascade/Tile 布局；检查点：书签仅对**已保存**的文档显示（`.../editor/bookmarks/`、`.../editor/window/`）。

---

## 5. 输出标准与判定准则

| 输出 | 判定准则 | 依据 |
|---|---|---|
| 保存文件 | 扩展名符合 File Type 的 Default extension；行尾类型符合 Load/Save 配置 | `.../editor-setup/file-types/load-save/` |
| 替换结果 | Result to new window 开启时原件不变；Show replaced count 可显示替换数量 | `.../editor/find/`、`.../general/editor/` |
| 书签可见性 | 行号显示开启 + 文档已保存 | `.../editor/bookmarks/` |
| 撤销完整性 | Redo 可恢复自文件打开以来的所有 Undo 操作 | `.../editor/edit/` |
| 大文件保护 | 行数 > 1024 的文件默认只读打开以防损坏（General 配置） | `.../editor-setup/general/` |

---

## 6. 行业最佳实践 / 常见误区

1. **误区：书签在未保存文档中也可见。** 官方明确：书签仅在文档已保存后显示于 Bookmarks 对话框（`.../editor/bookmarks/`）。
2. **误区：Undo 不可跨越多次操作恢复。** Redo 可重做自文件上次打开以来的所有 Undo 操作（`.../editor/edit/`）。
3. **最佳实践：替换前先 Result to new window。** 生成副本文档可保留原件用于比对，避免不可逆批量替换（`.../editor/find/`）。
4. **最佳实践：多文件检索用 Search all + Find All。** Find All 给出命中数与文件数并支持 F6 过滤、Shift+F8/F8 步进，适合跨程序核对（`.../editor/find/`）。
5. **误区：把 Editor 当建模工具。** NC 编辑器无几何建模能力（**B-05**）。
6. **最佳实践：用 Advanced Open 按内容检索。** 在文件名不确定时可按文件内容与创建/修改日期定位（`.../editor/file/`）。

---

## 7. 证据溯源表

| 序号 | SOURCE_URL | 用途 |
|---|---|---|
| S1 | `https://docs.cimco.com/en/docs/edit/2026/program-tabs/` | Ribbon 激活方式与快捷键显示约定 |
| S2 | `https://docs.cimco.com/en/docs/edit/2026/program-tabs/editor/` | Editor 子节清单 |
| S3 | `https://docs.cimco.com/en/docs/edit/2026/program-tabs/editor/file/` | File 菜单全部命令与快捷键 |
| S4 | `https://docs.cimco.com/en/docs/edit/2026/program-tabs/editor/edit/` | Edit 菜单与 Mark/Delete range |
| S5 | `https://docs.cimco.com/en/docs/edit/2026/program-tabs/editor/find/` | Find/Replace 全部参数与 F6/F8 快捷键 |
| S6 | `https://docs.cimco.com/en/docs/edit/2026/program-tabs/editor/bookmarks/` | 书签命令、F2/F5/Shift+F5 |
| S7 | `https://docs.cimco.com/en/docs/edit/2026/program-tabs/editor/window/` | 窗口布局四种模式 |
| S8 | `https://docs.cimco.com/en/docs/edit/2026/program-tabs/editor/filetype/` | File Type 决定项 |
| S9 | `https://docs.cimco.com/en/docs/edit/2026/program-tabs/editor/setup/` | Editor Setup 入口 |
| S10 | `https://docs.cimco.com/en/docs/edit/2026/program-tabs/editor/help/` | Help 下拉入口 |
| S11 | `https://docs.cimco.com/en/docs/edit/2026/editor-setup/file-types/load-save/` | 扩展名/行尾/自动保存参数 |
| S12 | `https://docs.cimco.com/en/docs/edit/2026/editor-setup/general/` | 备份/只读大文件保护 |
| S13 | 本地 `CAPABILITY_BOUNDARIES.md` | B-02、B-05 边界 |

> 未在语料中明确的菜单项一律标注"官方语料未明确，需现场确认"。
