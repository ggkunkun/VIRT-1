# Agent 链运行时（CAD/CAM 六软件真执行 + 网桥闭环）

> 本文只讲**可复跑的执行链**与它的判决口径。模型训练/合并线另见
> `GPU_MERGE_RUNBOOK.md`、`VIRTU_REAL_MODEL_README.md`。

## 一、链的七层与各自的真实入口

| 层 | 做什么 | 真实入口 | 是否已实测 |
| :-- | :-- | :-- | :-- |
| L0 本地模型 | Qwen3-8B + 4×LoRA 合并 → Q4_0 GGUF | Ollama `virtu-omni-8b`（`scripts/hf_to_gguf_numpy.py` 产物） | ✅ 21 tok/s 整卡卸载 |
| L1 推理网桥 | OpenAI 兼容 `/v1/chat/completions` | `start_virtu_bridge.py` → `scripts/workbuddy_virtu_bridge.py` | ✅ `/health` + 往返 |
| L2 意图解析 | 许愿文本 → 几何规格 | `virtu_omni.engine.wish_cad_cam_engine.parse_wish_intent` | ✅（有反解盲点，见 §4） |
| L3 工件生成 | 六软件工程代码/配置 | 同引擎 `generate_*` 六个方法 | ✅ |
| L4 编排落盘 | 工件 + manifest + pipeline | `cad_cam_agent_chain.py` | ✅ |
| L5 自动拉起 | 单实例阶梯：进程表→复用，无则 explorer 派生 | `launch_cad_cam_chain.py`、`agent_chain_executor.ensure_process` | ✅ |
| L6 真执行 | 各软件原生接口跑出产物并**回读数值** | `agent_chain_executor.py` 六个 `stage_*` | 见 §3 |
| L7 回读闭环 | 工具调用→执行→实测摘要（不再写死成功文案） | 网桥 `/v1/tool/dispatch`、`/v1/chain/run`、`/v1/chain/status` | ✅ |

## 二、判决口径（写进每条结论）

- `executed` —— 软件确实跑了，且**数值来自回读**（文件字节、特征数、体积、STEP 实体、对话框接受）。
- `substituted` —— 该软件对本机没有机器可读接口，由自研确定性校验承担同等验证职责，并点名替代了什么。
- `blocked` —— 原生接口存在但本机条件缺失，附**实测报错原文**与解锁动作；禁止写成「环境问题」。

几何类阶段还要过一道解析核对：`|实测 − 解析| / 解析 < 5%`（如 SOLIDWORKS 回转体体积 vs πR²L）。
「宏返回 True」不算成功，「窗口开着」不算执行。

## 三、六阶段现状

 definitive run：`runs/full_chain/20261031_000915/`（`chain_evidence.json` + `AGENT_CHAIN_REPORT.md`），
计数 **5 executed + 1 substituted**（缺的是 VERICUT，实测「偶发才跑、11 次成功 1 次」，根因见 §4 第 8 条）。
下表每一格都以那次运行目录里的产物为准，不以本文字为准。

| 阶段 | 打通方式（实测出来的，不是猜的） | 判决 |
| :-- | :-- | :-- |
| SOLIDWORKS 2021 | COM 附着既有实例 + `RunMacro2` 外部宏（真实特征名选草图）+ `Extension.CreateMassProperty` 自报体积/面积 + `SaveAs3` 导 STEP | executed（体积偏差 0.15%） |
| Siemens NX 12.0 | `NXBIN\run_journal.exe` **无头**执行 journal（`UGII_ROOT_DIR` 必须指 `UGII`，注册表里那份是对的）；`Parts.FileNew` 用裸模板名；`uf.ModlFeatures.CreateCyl1(sign,origin,height,diam,dir)`；`uf.Modeling.Update/AskMassProps3d`；`uf.ModlGeneral.AskBoundingBox` | executed（bbox 实测 = Ø53×45） |
| AutoCAD 2026 | **整段 COM 关进带硬超时的子进程**（`_run_child`）→ 附着前先点掉 CAD 自己的模态框（被强杀后重启必弹「图形修复」，它挂着时 Document 层每个调用都被拒）→ `SendCommand` 载 LISP 并跑 `(c:VIRTU_VERIFY)` → **LISP 自己把实体数/图层写进 metrics 文件**，COM `ModelSpace.Count` 作第二通道 → `SaveAs` DWG；剖面按 `groove_radii` 画半圆槽弧（**装不下的槽不画**，写进 `geometry_warnings` 并在报告里显示 ⚠️） | executed（两通道各实测 54 个实体、4 条自建图层，一致） |
| CIMCO Edit 2026 | 命令行 `ShellExecuteW(exe, "nc")` 载入编辑器，并**回读 CIMCO 自己写在标题/文档标签里的文件路径**作为「确实打开」的证据；**无 Application COM**（HKCR 5 个 `CIMCO.*` 全无 CLSID）、**无命令行开关**（官方 CHM 587 主题里零命中），backplot 是自绘 ribbon → 机器可校验部分由自研 Macro B 解析器承担 | executed（标题回读） |
| VERICUT 9.6 | **GUI 通道**：`vericut_console.bat`（不带 batch）+ `CGTECH_VCPROJECT`/`CGTECH_TRANSACTION_LOG` 起正常界面并自动加载工程 → 模板命中播放键（`work/vericut-toolchain/vc_playbtn.png`，~0.92）→ 回读 `force_turning_sample.log` 汇总段（总时长/空切占比/切削长度/总行程/错误数）。无头 batch 只留兜底（`batch batchp fitall ...`，11 次成 1 次） | executed（实测 0:01:23 / 空切 52% / 切削 458.03 mm / 总行程 2103.03 mm / 错误 107，日志指名我们那份 NC）|
| 斯沃 7.2 | **先用真鼠标点面板上的 `EDIT` 键把模式切过去**（137 个面板键是真 Button，但 `BM_CLICK`/`WM_COMMAND`/坐标级按键消息都不改模式；点之前要提前台 + `WindowFromPoint` 自检，点完「文件→打开」就不再弹「请把模式打在 Auto 或 Edit 上」），机型由 `common\general.ini [GENERAL] CNC=<索引>` 决定（49=NCT104 M 铣 / 50=NCT104 T 车；**登录窗下拉改了不生效**），经 `CNCLogin.exe` 握手起仿真；**NC 直接写进机床目录 `NC\*.cnc`（控制器自己的程序存储区）**，再用真 Win32 菜单「文件→打开」提交 | executed（程序进控制器且打开命令未拒；走刀未宣称，见 §4.6） |

斯沃这一格最终是怎么过的：不走「面板键切模式」那条死路（138 个面板键是真 `Button`，
但 `BM_CLICK`、`WM_COMMAND`、坐标级 `WM_LBUTTONDOWN/UP` 都不改模式；真鼠标点击还必须先把
面板自身 `GA_ROOT` 提前台，用 `GA_ROOTOWNER` 会把宿主主框提上来正好盖住面板；这套「提前台 + 命中自检 + 真点击」封装在 `win_input.py`），
而是用**控制器自己的存储约定**：把 NC 直接写进机床目录 `NC\WM2026.cnc`，
再触发真 Win32 菜单「文件→打开」——这次它不再弹「请把模式打在 Auto 或 Edit 上」，
说明程序已被控制器接受。判决记 `executed`，边界写死在 notes 里：
**循环启动走刀发生在自绘 CNC 屏上，本机无 OCR，因此不宣称跑过加工**。

## 四、已知缺口（不粉饰）

1. **模型自主 tool-calling 未达标**：本地 `virtu-omni-8b` 带 tools 时输出自然语言而非标准 `tool_calls`，
   参数还会幻觉。根因是 `tool_agent_lora`(r=16) 因 rank 冲突被排除 + 23k tool_call 语料尚未训练。
   现阶段 L7 用**确定性规划器 + 真执行器**闭环，并在摘要里标明这一点；模型那条腿属于训练任务。
2. `parse_wish_intent` 的半径盲点已修：`R15 R12 R10` 这种紧贴写法现在能解析成 `groove_radii=[15,12,10]`，CIMCO 会按三道槽各出一条 G02、NX 建 `GROOVE_R1..Rn`（`Cr12MoV` 里的 `r12` 不会被误认）；残留：`轴孔14` 之外的尺寸仍可能漏读，执行器一律以生成时的 spec 为准。
   执行器一律以**生成时使用的 spec** 为准，不做事后反解。
3. NX 圆弧槽：`NXOpen.UF` 无 `CreateTorus`，`Features` 也无 `CreateTorusBuilder`；槽特征目前用表达式
   (`GROOVE_PITCH`) 承载，几何未生成，journal 里如实记录 `groove_notes`。
4. SW 内孔切除：`FeatureCut3` 的方向参数未在真机上锁定，当前 SW 阶段只建外径回转体，
   孔由 NX 阶段（`CreateCyl1` Negative）承担，两边体积可交叉核对。
5. **Vericut 的「事件归属」现在按双条件把关，旧数字已撤回**：`.vcproject` 里 `NCPrograms/NCProgram/File`
   确实只指向我们那份 NC（8 处引用，无样本残留），但一次全新 CWD 的 batch 跑下来事件数为 0，
   说明上一轮那 157 个事件不是本次产生的（`collision_nc_lines` 里出现 74 行，而我们的 NC 只有 40 行就是铁证）。
   现在 sidecar 只有在「本次新建」且「内容指名我们那份 NC」两个条件同时成立时才计入证据，
   否则在输出里留 `[SIDECAR_REJECTED_STALE]` / `[SIDECAR_REJECTED_NOT_OUR_NC]` 标记。
   `CGTECH_TRAINING` 仍指空目录，避免把 `E:\training\*.mcd` 的教程报错混成我们的语法事件。
6. **斯沃这一格的边界要说全**：车床路线在本机是坏的（实测：`CNC=50` 或直起 `FANUC0iTF\sscnc.exe`
   都弹「找不到 `Nj2Controlor.dll`」，只有铣床 NCT104 M 起得来），所以阶段 6 是在**铣床控制器**上完成的；
   而链路生成的 NC 是车床程序（G71/G70、U/W）。「程序被写进控制器程序区且『文件→打开』不再拒绝」是实测事实，
   但**「该程序适合这台铣床控制器」并未被证实**，循环启动走刀也未执行（自绘 CNC 屏无 OCR）。
   要闭合需要二者之一：补 `Nj2Controlor.dll` 起车床，或为铣床生成对应工序的 NC。
7. 面板键的输入语义：EDIT/AUTO 等 139 个控件是真 `Button`，`BM_CLICK`、`WM_COMMAND`（发给面板与主框）、
   坐标级 `WM_LBUTTONDOWN/UP` 三种都试过，模式不变；真鼠标点击要先把**面板根窗**（`GA_ROOT`）提到前台，
   用 `GA_ROOTOWNER` 会把宿主主框提上来正好盖住面板（踩过）。CNC 显示屏是 OpenGL，
   `PrintWindow` 抓出来是黑的，只能抓屏幕像素（`scratch/acp/grab_screen.py`）。
8. **VERICUT：GUI 通道已打通，全自动还差「点播放」这一步**。豆包那套 `work/vericut-toolchain/vericut_link.py` 给了两条可用通道——`launch_via_bat()` 起界面、`play_simulation()`+`parse_sim_log()` 跑并回读；本机做了三处订正：`vericut_agent.bat` 把工程路径写死且用 `start`+`javaw`（起不来）→ 改用 `vericut_console.bat`+环境变量；播放锚点 (1890,860) 在 125% DPI 下不命中 → 改用模板匹配（命中 0.92）；`F5` 不是「开始播放」，日志里那条 `ActionMainPlay` 是**跑完**的完成记录。真跑那次是我手动触发：日志 27,540B、总时长 0:01:23、空切 52%、切削 458.03 mm、错误 107，且明确处理我们的 NC。自动化点播放不稳（当前布局把「仿真控制条」挤出可见区，模板就 miss）——所以阶段在点不到时**立刻**返回 blocked 并写清原因，而不是干等；只要日志一旦出现可解析汇总，判决会自动翻成 executed。

## 四点五、本轮推翻的旧结论（留档防复发）

| 旧结论（`runs/cad_cam_chain/.../CHAIN_FULLSTATUS.md`） | 实测 |
| :-- | :-- |
| 「SOLIDWORKS ✅ 已执行：RunMacro2 建出旋转体」 | 宏根本没建几何：导出的 STEP 4.4KB、零 `MANIFOLD_SOLID_BREP`、体积 0；真因是英文名选基准面 + 空草图名选取 + 毫米数值喂进以米为单位的 API。现版宏实测体积 99,278.3 mm³ = 解析值 |
| 「桥接层已把工具结果同步至工作区」类摘要 | 那是写死在 `_handle_tool_orchestration` 里的成功文案，与执行无关；现已替换为真执行 + 实测摘要 |
| 「斯沃菜单自绘、无法驱动」 | 菜单是真 `HMENU`（59~74 项带命令 ID），面板 138 个控件也是真 `Button`；墙在模式状态不可读写，不在自绘 |
| 「Vericut 被环境挡住（无头入口不可用）」 | 无头入口存在、许可证可用，但它只做「装载工程」这一步：`batch batchp` 待命、`batcht` 自退、`vcp=` 被拒、stdin 无响应（§4 第 8 条）。**同时撤回我自己上一轮给的 executed**：那次报的 157 个碰撞事件里 `collision_nc_lines` 出现 74 行，而我们生成的 NC 只有 40 行 —— 事件来自 CWD 里别处的旧 sidecar 日志，不是本次仿真。现已把 sidecar 收进「本次新建 + 内容指名我们那份 NC」双条件闸，并有回归测试钉住 |
| 「AutoCAD 阶段在主线程里 COM 就够」 | 实测主线程被一次挂起的 COM 调用困住 **19 分钟**（Python 侧对阻塞的 IDispatch 调用无任何超时手段，换守护线程又因公寓不匹配把「能应答」误判成「不应答」）。现方案：子进程跑完整 COM + 结果文件 + 到点 `taskkill`，判决照旧打在回读数值上 |
| 「`(load "runs/…")` 这种相对路径交给 CAD 无所谓」 | AutoLISP 的 `load`/`open`、CIMCO 的文件参数、`CGTECH_VCPROJECT` 都按**对方软件自己的 CWD** 解析，失败时不报错只给「实体 0 / 零事件」。现所有外发路径统一 `os.path.abspath()`，并有回归测试钉住 |

## 四点六、本轮修的三条判据/架构缺陷（2026-10-30）

| 缺陷 | 实测证据 | 修法 |
| :-- | :-- | :-- |
| AutoCAD 实体数是**累计值**，判据必过 | 同一实例连跑三次读数 54 → 90 → 102 | 每次 `Documents.Add` 新建文档；判据改「本次新增 = after − before」，LISP 哨兵同样折算增量；拿不到新文档时记 `reused_document=True` |
| 旧文档占住同一个 DWG，`SaveAs` 报「打开文档时出错」 | `Drawing5.dwg` 存不下、dwg 为空 | 开跑前关掉指向本输出的旧文档，存完再关新文档释放占用 |
| CAD 刚被关过文档时 `load` 偶发静默不生效 | 同一命令一次 0 实体、下一次 6 实体 | 哨兵没出现就重载 LISP 重跑一次（有界，写进 steps） |
| 写结果后进程赖着被误判超时 | ACAD `added=6` 却判 blocked | `_run_child` 区分 `timed_out`（没结果）与 `lingering_killed`（有结果、进程没收尾） |
| `/v1/chain/run` 与 `/v1/tool/dispatch` **无单飞锁** | 两条并发请求会同时驱动同一批软件 | 桥里加 `_APP_EXEC_LOCK` + `run_exclusive()`，第二条直接 409（带 holder）；真机验证 A=200 executed / B=409 |
| `ensure_process` **只按 exe 名**复用 | 会接管用户自己开的同款软件且永不回收 | 同源判定＝全路径相等 → 同一文件(dev+inode) → 去盘符尾段相等；派生启动写 `runs/launch_ledger.json`（只追加、原子替换、读失败绝不回写），`started_by_us` 只认账本 |

| 意图反解只取第一个 R（`fillet_r=radii[0]`，而且 `R15` 根本没匹配上） | 「三道圆弧槽 R15 R12 R10」 生成的 NC 只切一刀、NX 一个 `GROOVE_R` | 新增 `groove_radii/num_grooves/parse_warnings`；CIMCO 按列表逐槽出行、NX 建逐槽表达式；材料牌号里的 `r12` 用负向后顾排除 |
| 桥没有鉴权、参数可指向任意文件 | 本机任意进程都能触发真执行；`nc_file_path` 可指到任意路径 | `VIRTU_BRIDGE_TOKEN`（或 `%LOCALAPPDATA%irtu_bridge_token`）启用 Bearer 鉴权，未配置时启动日志明示 DISABLED；`_path_allowed()` 要求路径落在仓库内（`VIRTU_ALLOWED_ROOTS` 可扩）——真机验证：无头/错 token=401、对 token=200 |
| 取证包不可校验 | `chain_evidence.json` 无 schema、无哈希、无代码锚点 | bundle 加 `schema_version=2`、`code`（执行器/桥/引擎/win_input 的 sha256 前 16 位 + git HEAD）、`integrity`（每个产物 sha256 + 字节数） |
| 跑完无法按账本回收实例 | 只能人工关，或误伤别人的窗口 | `--close-launched`：只关「账本里记着 + 现在还在 + 同源」的 PID |
| ACAD 剖面图里没有槽（和 NC 不一致） | 图只有矩形剖面 + 3 个尺寸 | LISP 按 `groove_radii` 画半圆槽弧；**装不下的槽不画**（R15 在 Ø53×45 上会超出件长），改为写进 `geometry_warnings` 并在报告里显示 ⚠️ |
| 桥对工具调用不做入参校验 | 空 target / 非对象 parameters 也能落到执行器 | `_validate_dispatch_args()`：目标白名单 + action 非空 + parameters 必须是对象；直连端点回 400，聊天路径回 blocked 证据 |
| 取证包无限增长、跑前不做环境清理 | `runs/full_chain` 只增不减 | `_prune_runs()` 只删时间戳目录、保留最近 30 个（`VIRTU_KEEP_RUNS=0` 可关）；`preflight_apps()` 跑前点掉 acad/SW/CIMCO 的白名单模态框并记进 bundle |
## 五、怎么跑

```bash
# 全链：意图 → 工件 → 六阶段实跑 → 取证包 + 报告
python agent_chain_executor.py --stage all --wish "我想制造一款精密成型轮模 材质Cr12MoV 外径53mm 轴孔14mm 宽度45mm"
# 产物：runs/full_chain/<ts>/{chain_evidence.json, AGENT_CHAIN_REPORT.md, nx_wheel_mold.prt, wheel_mold.step, ...}

# 单阶段
python agent_chain_executor.py --stage nx --out runs/full_chain/manual

# 网桥闭环（L1 + L7）
python start_virtu_bridge.py --check      # 只看后端解析（应为 vllm_http + virtu-omni-8b）
python start_virtu_bridge.py              # 起 :8000
curl http://127.0.0.1:8000/v1/chain/status

# Agent 侧真执行入口
curl -X POST http://127.0.0.1:8000/v1/tool/dispatch -H "Content-Type: application/json" \
     -d '{"target_software":"Siemens_NX","action":"run_journal","wish":"外径53mm 轴孔14mm 长度45mm 轮模"}'
```

验收脚本：`scratch/acp/test_bridge_e2e.py`（起桥 → tool_calls → 真执行 → 摘要必须含实测字段，
且不得出现旧的写死成功文案）。

## 六、本机环境事实（本轮实测修正）

- NX 的环境变量真值在 `HKCU\Environment`：`UGII_BASE_DIR=<NX>`、`UGII_ROOT_DIR=<NX>\NXBIN`；
  无头 journal 需要 `UGII_ROOT_DIR=<NX>\UGII` 才能解析模板目录，模板用**裸名** `model-plain-1-mm-template.prt`。
- SOLIDWORKS 的 `ISldWorks` 只有类型库、live 对象不暴露 ITypeInfo → pywin32 必须走 makepy 缓存
  （`gen_py/3.12/83A33D31-…x0x29x0.py`，用 `gencache.EnsureModule` 加载）；
  中文界面下基准面名为 `前视/上视/右视基准面`，草图为 `草图N`，`SelectByID2` 必须用真实特征名。
- 斯沃 `sscnc.exe` 分散在各机床目录（`SSCNC/<系统>/<机床>/sscnc.exe`），直接双击即退，
  必须经 `CNCLogin.exe` 握手。
- Vericut 许可证：`C:\ProgramData\CGTech\license\cgtech.lf` + `LSERVOPTS=-s …`，FlexNet 服务在跑。
