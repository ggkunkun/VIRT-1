# M07 DNC 通信与机床连接（Transmission / DNC Setup） — 标准化操作手册

> 对应模块：Transmission 选项卡 + DNC Setup 对话框
> 事实源：`docs.cimco.com/en/docs/edit/2026/dnc-setup/*` 与 `.../program-tabs/transmission/*`（C 语料）
> 诚实性基线：`CAPABILITY_BOUNDARIES.md`（DNC 能力官方正面支撑；本机实装数据见 `EVIDENCE.md`）

---

## 1. 模块定位与适用边界

**能做什么**：CIMCO Edit 通过**串口（serial）**或 **FTP** 连接在 CNC 机床与 PC 间发送/接收 NC 程序；两种协议均在 DNC Setup 对话框配置。DNC Setup 对话框**独立于 Editor Setup，不能从 Editor Setup 访问**，可从 Transmission 菜单或 Transmission 选项卡下的 Setup 菜单打开。来源：`https://docs.cimco.com/en/docs/edit/2026/program-tabs/transmission/`、`.../dnc-setup/`。

**不能做什么**：
- **许可边界**：`CIMCO Edit 2026 must be licensed for DNC operations to use this option`（DNC 选项需授权）。来源：`.../program-tabs/transmission/`。
- AI Agent 不能收发程序：`Connect to AI Agents` 明确 agent 不能向 CNC 收发程序，Transmission/DNC-Max/NC-Base 选项卡命令对 agent 不可用（来源：`.../editor-helpeditor-help/connect-ai-agents/`）。
- 本机许可状态未核实，按"未验证"处理：DNC 模块功能取决于授权，不宣称开箱可用。
- 不宣称"版本管理/程序管理"能力（**B-02**：属 NCBase/MDCMax 产品域）。

---

## 2. 官方菜单路径与快捷键（逐条附来源）

### 2.1 Transmission 菜单（来源：`https://docs.cimco.com/en/docs/edit/2026/program-tabs/transmission/transmission/`）

| 命令 | 功能 | 来源页 |
|---|---|---|
| Send | 发送当前 NC 程序到 Machine 下拉所选机床；弹 Transmit status；**FTP 不可用** | `.../transmission/transmission/` |
| Send Selected Lines | 发送选中行块；弹 Transmit status；**FTP 不可用** | 同上 |
| Send File | 定位文件发送；串口弹 Transmit status；FTP 在 Use split window 开启时弹 FTP Transfer | 同上 |
| Receive File | 从机床接收程序，保存而不打开；弹 Receive status；FTP 弹 FTP Transfer | 同上 |
| Receive | 接收并在新窗口打开；**FTP 不可用** | 同上 |
| Receive Into Current Window | 接收并插入当前窗口；**FTP 不可用** | 同上 |
| DNC Setup | 打开 DNC Setup 对话框 | 同上 |

### 2.2 Machine 与 Setup 菜单（来源：`.../transmission/machine/`、`.../transmission/setup/`）

| 命令 | 功能 | 来源页 |
|---|---|---|
| Machine Type | 选择要发送/接收的机床 | `.../transmission/machine/` |
| Status | 显示 Transmit dialog（若已隐藏）；**FTP 机床禁用** | `.../transmission/machine/` |
| DNC Setup | 打开 DNC Setup 对话框 | `.../transmission/setup/` |

### 2.3 DNC Setup 对话框（来源：`.../dnc-setup/`）

| 项 | 功能 | 来源页 |
|---|---|---|
| Machines | 机床配置列表；下方 Configuration 针对选中机床 | `.../dnc-setup/` |
| Protocol | 串口选 Standard Serial Protocol；FTP 选 FTP Client Protocol | `.../dnc-setup/` |
| Port information | 连接设置速记：串口 `COM1, 9600, 7E2` = 端口 COM1 / 波特率 9600 / 数据位 7 / 偶校验 E / 停止位 2；FTP `cimco@192.168.254.231` = 用户名 cimco / CNC IP 192.168.254.231 | `.../dnc-setup/` |
| Machine Type | 决定默认加载/保存目录、传输中如何检测换刀；在 Editor Setup > File Types 配置 | `.../dnc-setup/` |
| Setup / Rename / Add New / Delete / OK | 配置/重命名/新增（模板 FTP Client、Generic Serial Connected CNC、Okuma Template）/删除/应用 | `.../dnc-setup/` |

---

## 3. 参数配置规则

### 3.1 标准串口协议 — Port（来源：`.../dnc-setup/standard-serial-protocol/port/`）

| 参数名 | 取值 | 默认值 | 含义 | 来源页 |
|---|---|---|---|---|
| Port | 本地串口列表 | — | 选择与该机床配置用的串口 | `.../standard-serial-protocol/port/` |
| Baud rate | 下拉 | — | 传输速度 bit/s | 同上 |
| Stop bits | — | — | 每字符后停止位数；取决于 CNC 控制器，参照手册 | 同上 |
| Data bits | 通常 7 | 7-bit ASCII | 每字符位数，NC 数据传输默认 7 位 ASCII | 同上 |
| Parity | None/Even/Odd/Mark/Space | — | 校验方式：Even=偶数个1，Odd=奇数个1，Mark 恒1/线路低，Space 恒0/线路高（后两者仅测试用） | 同上 |
| Flow control | None/Software/Hardware/Hardware and Software | — | 握手：Software 用 XOn/XOff；Hardware 用 RTS/CTS | 同上 |
| Enable DTR / Enable RTS | 开/关 | — | 置 DTR / RTS 为高 | 同上 |
| Check parity / Insert on parity error | 开/关 + 字符 | — | 报告校验错误并插入指定字符 | 同上 |
| XOn / XOff character | 字符或 `\36` 形式 | 空=标准 | 非标准 XOn/XOff 字符（如 `$`=ASCII36 或 `\36`） | 同上 |

### 3.2 标准串口协议 — Transmit / Receive（来源：`.../standard-serial-protocol/transmit/`、`.../receive/`）

| 参数名 | 取值 | 默认值 | 含义 | 来源页 |
|---|---|---|---|---|
| CR/LF | 下拉/手输 | — | 回车换行符；ASCII13/10 写作 `\13`、`\10` | `.../transmit/` |
| Start trigger / End trigger | 字符串 | 空=从头/到文件尾 | 起始触发（从含该串首行开始传）/结束触发（含该串行**不发送**） | 同上 |
| Send at start/end of feed | 字符串 | — | 传输开始/结束发送的字符或串 | 同上 |
| Omit lines containing / Remove characters | — | — | 排除含特定字符的行 / 删除特定字符 | 同上 |
| Handshake timeout (s) | 秒 | — | 收到 XOff/CTS Low 后等待终止连接的时长 | 同上 |
| Delay before each line (ms) | 毫秒 | — | 每行发送前等待时间 | 同上 |
| Wait for XOn / Wait for 'Start' button | 开/关 | — | 等 XOn 后再发（仅 Software 握手）/ 等点 Start 再传 | 同上 |
| Remove ASCII 0's / white spaces / Replace tabs | 开/关 | — | 去 ASCII0 / 去空格(32)与制表(9) / 制表转空格 | 同上 |
| Receive：CR/LF | Auto/手输 | Auto | Auto 自动探测 CR/LF；非标准组合手输 `\13`、`\10` | `.../receive/` |
| Receive：Omit lines with string / Remove characters / Omit empty lines | — | — | 接收时排除/删字符/去空行 | 同上 |
| Start/End trigger（接收） | 字符串 | — | 开始/停止保存数据的触发串（首/末收到的字符序列） | 同上 |
| Receive timeout (s) | 秒 | — | 最后字符收到后判定接收完成的延时；无 End trigger 时须设 | 同上 |
| Send XOn / Send at start of reception | 开/关+串 | — | 就绪时发 XOn / 接收开始时发指定串 | 同上 |

### 3.3 FTP 客户端协议（来源：`.../dnc-setup/ftp-client-protocol/port/`、`.../send-receive/`）

| 参数名 | 取值 | 默认值 | 含义 | 来源页 |
|---|---|---|---|---|
| Server address | IP | 例 127.0.0.1 | FTP 服务器 IP | `.../ftp-client-protocol/port/` |
| Username / Password | 字符串 | — | 客户端连接凭据 | 同上 |
| PC default path | 路径 | `C:\` | PC 端默认路径（空则 C:\） | 同上 |
| FTP server default path | `/[DIR]` | — | FTP 服务器端默认路径（绝对，从根算） | 同上 |
| Use split window | 开/关 | — | 收发用拆分窗口（FTP 接收时总用拆分窗口） | `.../ftp-client-protocol/send-receive/` |
| Receive to default PC directory | 开/关 | — | 总是接收到默认本地目录 | 同上 |
| Allowed split window actions | Send/Receive/Local deletion/renaming/dir change/dir creation/Remote 对应项 | — | 控制在拆分窗口中允许的操作 | 同上 |

### 3.4 本机实装清单 — TPL/TYP 传输模板（实测）

- EVIDENCE.md INS-03 记 **Templates 326**（含 Attachments/Gfx 等全部文件）。
- 本机 2026-11-18 精确枚举：**`.TPL` 47 个 + `.TYP` 44 个 = 91 个模板文件**（口径为按扩展名精确匹配）。
- 代表 TPL（实测）：`AGIECLASSIC.TPL`、`AGIECUT.TPL`、`ANDON.TPL`、`BRIDGEPORT.TPL`、`BROTHERQD2.TPL`、`BROTHERQD3.TPL`、`FANUC-FAPT.TPL`、`FANUC-FILEMATE.TPL`、`FANUC-HANDYFILE.TPL`、`FTPSERVER.TPL`、`GENERICS.TPL`、`HEIDENHAIN.TPL`、`HURCOCONV.TPL`、`LSV2-D11.TPL`、`LSV2-D4.TPL`、`LSV2-HH.TPL`。
- 另有 `.epl`（如 FtpClient.epl、Okuma.epl）、`.TPH`、`.TPM`、`MultiChannelSystemTemplates.json` 等配置/模板文件。
- **具体模板与机床控制的映射需现场确认**；官方语料未逐个说明各 TPL 用途。

---

## 4. 标准操作步骤

### 4.1 配置一个串口机床并发送程序
1. Transmission 菜单或 Setup > DNC Setup；检查点：DNC Setup 对话框打开（独立于 Editor Setup）（`.../transmission/`）。
2. Add New，命名并选模板（Generic Serial Connected CNC / Okuma Template / FTP Client）；检查点：新机床出现（`.../dnc-setup/`）。
3. Port 页设 Port/Baud rate/Stop bits/Data bits/Parity/Flow control；检查点：与机床 RS-232 参数一致，Port information 显示如 `COM1, 9600, 7E2`（`.../standard-serial-protocol/port/`）。
4. Transmit 页设 CR/LF、Start/End trigger、握手超时、延迟；检查点：与机床 DNC 协议匹配（`.../standard-serial-protocol/transmit/`）。
5. Transmission > Machine 选机床，Send / Send File；检查点：Transmit status 显示 EIA RS-232-C 信号、进度 0–100%、Terminal 窗口文本（`.../transmission/transmission/`、`.../transmission/untitled-104/`）。

### 4.2 接收程序
1. Receive 页设 CR/LF（建议 Auto）、Start/End trigger、Receive timeout；检查点：无 End trigger 时已设超时（`.../standard-serial-protocol/receive/`）。
2. Transmission > Receive File（保存不打开）/ Receive（新窗口）/ Receive Into Current Window；检查点：Receive status 显示进度与终端文本（`.../transmission/transmission/`）。
3. 若 General 勾 Specify name when receiving，接收时指定文件名；检查点：文件按指定名保存（`.../editor-setup/general/`）。

### 4.3 FTP 传输
1. DNC Setup 选 FTP Client Protocol；Port 页设 Server address/Username/Password/PC default path/FTP server default path；检查点：路径为 FTP 绝对格式 `/[DIR]`（`.../ftp-client-protocol/port/`）。
2. Send/Receive 页设 Use split window 与 Allowed actions；检查点：需要的本地/远程操作已勾选（`.../ftp-client-protocol/send-receive/`）。
3. Transmission > Send File / Receive File；检查点：FTP Transfer（Split Window）左侧本地 PC、右侧远程 CNC，可 Refresh/Send to remote/Receive from remote（`.../transmission/split-window/`）。

---

## 5. 输出标准与判定准则

| 输出 | 判定准则 | 依据 |
|---|---|---|
| 传输许可 | DNC 操作需授权；本机许可未核实按未验证处理 | `.../transmission/` |
| 串口参数 | Port information 速记与机床一致（如 COM1,9600,7E2） | `.../dnc-setup/` |
| 握手 | Software=XOn/XOff，Hardware=RTS/CTS，可组合 | `.../standard-serial-protocol/port/` |
| 字符输入 | 可用字符本身或 ASCII 值（`\36`=ASCII36），如 `$*`=\$\* 或 `\36\42` | `.../transmit/`、`.../receive/` |
| FTP 路径 | FTP server default path 为从根算的绝对路径 `/[DIR]` | `.../ftp-client-protocol/port/` |
| 状态反馈 | Transmit/Receive status 显示 RS-232 信号、进度、终端文本 | `.../transmission/untitled-104/` |
| TPL 映射 | 具体模板用途官方语料未明确，需现场确认 | 本机实测 |

---

## 6. 行业最佳实践 / 常见误区

1. **误区：DNC Setup 从 Editor Setup 进。** 官方明确二者独立，DNC Setup 只能从 Transmission 菜单或 Transmission 选项卡的 Setup 菜单打开（`.../transmission/`）。
2. **误区：所有收发命令 FTP 都能用。** Send、Send Selected Lines、Receive、Receive Into Current Window 明确"not available for FTP"（`.../transmission/transmission/`）。
3. **最佳实践：接收超时兜底。** 无 End trigger 时必须设 Receive timeout，否则需手动停止接收（`.../receive/`）。
4. **最佳实践：End trigger 行不发送。** 发送时含结束触发的行不会被传送（`.../transmit/`）。
5. **误区：AI agent 可代收发程序。** Connect to AI Agents 明确禁止（`.../editor-helpeditor-help/connect-ai-agents/`）。
6. **最佳实践：拆分窗口权限最小化。** FTP 的本地/远程删除、重命名、建目录均需在 Send/Receive 单独勾选才可用（`.../ftp-client-protocol/send-receive/`）。

---

## 7. 证据溯源表

| 序号 | SOURCE_URL | 用途 |
|---|---|---|
| S1 | `https://docs.cimco.com/en/docs/edit/2026/program-tabs/transmission/` | Transmission 概述、DNC Setup 独立性、许可要求 |
| S2 | `https://docs.cimco.com/en/docs/edit/2026/program-tabs/transmission/transmission/` | Send/Receive 全部命令 |
| S3 | `https://docs.cimco.com/en/docs/edit/2026/program-tabs/transmission/machine/` | Machine/Status |
| S4 | `https://docs.cimco.com/en/docs/edit/2026/program-tabs/transmission/setup/` | DNC Setup 入口 |
| S5 | `https://docs.cimco.com/en/docs/edit/2026/program-tabs/transmission/split-window/` | FTP Transfer Dialog |
| S6 | `https://docs.cimco.com/en/docs/edit/2026/program-tabs/transmission/untitled-104/` | Transmit/Receive Status 对话框 |
| S7 | `https://docs.cimco.com/en/docs/edit/2026/dnc-setup/` | DNC Setup 对话框与 Port information 速记 |
| S8 | `https://docs.cimco.com/en/docs/edit/2026/dnc-setup/standard-serial-protocol/port/` | 串口参数与握手 |
| S9 | `https://docs.cimco.com/en/docs/edit/2026/dnc-setup/standard-serial-protocol/transmit/` | 发送参数 |
| S10 | `https://docs.cimco.com/en/docs/edit/2026/dnc-setup/standard-serial-protocol/receive/` | 接收参数 |
| S11 | `https://docs.cimco.com/en/docs/edit/2026/dnc-setup/standard-serial-protocol/directories/` | 默认发送/接收目录与扩展名 |
| S12 | `https://docs.cimco.com/en/docs/edit/2026/dnc-setup/ftp-client-protocol/port/` | FTP 端口参数 |
| S13 | `https://docs.cimco.com/en/docs/edit/2026/dnc-setup/ftp-client-protocol/send-receive/` | FTP 收发与拆分窗口动作 |
| S14 | `https://docs.cimco.com/en/docs/edit/2026/editor-helpeditor-help/connect-ai-agents/` | AI agent 收发禁令 |
| S15 | 本地 `EVIDENCE.md` + 本机 `E:\...\CIMCOEdit\Templates\` 枚举 | TPL/TYP 实装清单 |

> 未在语料中明确的模板用途一律标注"官方语料未明确，需现场确认"。
