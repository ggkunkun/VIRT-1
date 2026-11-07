# Virtu 13.63B 装配体全流程落地（2026-11-07）

- 工作区：`D:\Virtu模型`｜样本：`assets/wheel_mold_P0.step`（与桌面 `微型机轮模总成(P0) 6R15-6R12-6R10.step` 同 sha256 `712e8ac6…`）
- 口径：以下数值全部来自 `runs/model_drive_20261107_134057/provenance.json` 的 **measured** 记录，证据文件已 `seal_leg` 封缄（`raw_sha256 cf45406a…`，12 行）

## 一句话结论

模型侧「理解」由结构化 BOM + 几何配合推断承担，执行侧由 SolidWorks COM 真装配承担：**13.63B 模型在第 1 轮自主发出 2 个工具调用，4 件全部按 BOM 位姿落位，3 个真实配合落盘并在重开后仍在，GB 工程图 5 视图重开后仍是 5 视图，9/9 门禁全绿。**

## 一、根因：之前为什么「拼不上」

| # | 事实（实测） | 证据 |
|---|---|---|
| 1 | 模型读原始 STEP 不是能力问题：结构化 BOM 注入后 0/7 → 7/7 命中 | `STEP_BOM_SOLUTION_REPORT.md` |
| 2 | SW 2021 的 STEP/IGES **翻译器经 API 全部失败**：`OpenDoc6` 返回 `2097152 (0x200000)`（零件）/ `1024,2`（装配），换 AP203/AP214/AP242/IGES 结果相同 | `runs/asm_run_05/convert_result.json`、本轮探针 |
| 3 | 可用通道是 `IPartDoc.InsertImportedFeature`（3D Interconnect），逐件导入为原生 SLDPRT；整包导入 SW 只得到空装配 | `InsertImportedFeature` → 体积与 OCP 完全一致 |
| 4 | 配合「加了但重开消失」的真因是 **SW 同名文档冲突**：每次运行都写 `wheel_mold_mated.SLDASM`，旧文档未关导致重开被拒；改为每次运行唯一命名后配合稳定落盘 | run_05 成功 / run_06/07 失败 / run_08 全绿 |
| 5 | `IModelDoc2.SelectByID2` 在 2021 不存在，实际在 `IModelDocExtension`（DISPID 68）；孔内圆柱面按坐标选不中 → 必须多点候选 + 选中后核对曲面类型/半径，漂移即 `EditUndo2` 撤销 | `bridges/assembly_worker.py::_sel_surface/add_mate` |

## 二、链路

```
STEP ──StepBOM──> 零件树 + 4x4 位姿(含旋转)
      └─OCP(XCAF/build123d)──> 每件本地 STEP + 实测体积(mm³) + 面数
STEP ──face_inventory/infer_mates──> 共面(距离/重合) + 同轴(r=3, 轴向重叠) 候选 + 选点
      └─assembly_worker(build)──> InsertImportedFeature→SLDPRT → NewAssembly
            → AddComponent5(按 bbox 中心补偿) → 选面校验 → AddMate5
            → 漂移即撤销 → 无接触件 FixComponent → 保存 → 关/重开核对
      └─assembly_worker(drawing)──> gb_a3 第一角三视图 + 等轴测 → .SLDDRW → 重开核对
      └─assembly_pipeline──> 9 项门禁 + verification.json/report.md
      └─scripts/seal_assembly_run.py──> provenance.json + sealed/raw.jsonl
```

新增/修改文件：

- `bridges/step_bom.py`：位姿补 3×3 旋转（`_frame_of` / `_placement_between`，含父坐标系求逆）；修复实体切片丢右括号
- `bridges/step_parts_occ.py`：OCP 拆件、按实体导出、本地化位姿求逆、体积/面数/包围盒对账
- `bridges/step_mates.py`：共面/同轴配合推断 + 圆柱面多点选点
- `bridges/assembly_worker.py`：SolidWorks COM 子进程（import/build/drawing），可被父进程超时中止
- `bridges/assembly_pipeline.py`：编排与门禁
- `scripts/model_drives_assembly.py`：模型经 Ollama 工具调用环驱动
- `scripts/seal_assembly_run.py`：按测量宪法封缄
- 反证测试：`tests/test_assembly_gates.py`、`tests/test_step_mates_falsifiable.py`、`tests/test_step_bom_pose.py`（合计 17 passed）

## 三、实测证据（run_id `10ca2ad9cfbb970d`，drift 空）

| 指标 | 值 | 口径 | 证据 |
|---|---:|---|---|
| 零件体积 mm³（P0/P1/P2/P3） | 45765.768 / 59607.908 / 100307.497 / 35472.713 | measured，OCP 实测并与 SW 质量属性逐件对账 | `verification.json` |
| 装配体积 mm³ | 241154.0（零件和 241153.886，差 **0.114 mm³**） | measured | 同上 |
| 组件位姿 | 4/4 回读 == BOM（阈值 0.05 mm） | measured | 同上 |
| 接触配合 | 3：1×距离 0.3 mm（共面）+ 2×同心 r=3 mm（轴向重叠 19 mm） | measured，选面后核对曲面类型/半径，加后无漂移 | 同上 |
| 重开配合条目 | 6（3 个配合 × 两侧组件） | measured，`IComponent2.GetMates` | 同上 |
| 工程图视图 | 5（图框 + 三视图 + 等轴测）；重开 **5** | measured，`IDrawingDoc.GetViewCount` | 同上 |
| 门禁 | **9/9 PASS** | measured | `verification.json.gates` |
| 模型驱动 | `virtu-moe-14b:fast`（digest `729abf24…`，Q4_K_M）第 1 轮自主发出 2 个工具调用：`cadcam_step_reverse(bom)` + `cadcam_assembly_build(full_mated)`，driver=`model` | measured | `transcript.json` |

## 四、证据路径

- 运行目录：`runs/model_drive_20261107_134057/`
  - `verification.json` / `report.md`：门禁与实测
  - `transcript.json`：模型对话与工具调用（含 `served_model`、耗时）
  - `provenance.json` / `provenance.md` / `sealed/_seal.json`：封缄
  - `artifacts/`：`*.SLDASM`、`*.SLDDRW`、4 个 `*.SLDPRT`、7 个单件 STEP
- 对照运行：`runs/asm_run_08/`（同链路、harness 直接调用，9/9 全绿）

## 五、边界（不粉饰）

1. **P3（夹料模）在 STEP 中是爆炸图位姿**：与其余零件无任何接触候选（轴向重叠为负），因此没有伪造接触配合，采用 `FixComponent` 并明确标注。
2. 只加成了 3 个接触配合：P0-P1 的第二个 0.1 mm 共面配合、P0-P1 的同心配合因**孔内隐藏面按坐标选不中**而未添加（记录在 `contact_mates[].error`），没有用假配合凑数。
3. 工程图只有三视图+等轴测，**没有尺寸标注/BOM 明细表**；干涉检查未接入（未测，不写成 0 干涉）。
4. 模型驱动证据只证明「模型会自主发起正确工具调用并接受门禁」，**不评价其文字解释质量**；本轮内容字段为空（思考型模型只发了工具调用）。
5. SW 2021 的 STEP 翻译器损坏是**环境事实**，本链路绕开了它；换/修 SW 后才可回归传统 `OpenDoc6` 导入。
6. `BreakLink` 返回 False（未证实断开），配合落盘的正向证据是重开后 `GetMates` 仍在；机制解释保持为「唯一命名解决了重开冲突」，不宣称 BreakLink 生效。

## 六、复现

```bash
# 1) 纯理解（不碰 SW）
.venv/Scripts/python.exe -c "import sys,json;sys.path.insert(0,'.');from bridges.step_mates import face_inventory,infer_mates;print(json.dumps(infer_mates(face_inventory(r'assets/wheel_mold_P0.step')),ensure_ascii=False)[:2000])"

# 2) 全流程（SW 需已安装；首次会自行启动，约 40-60s）
.venv/Scripts/python.exe -u bridges/assembly_pipeline.py "assets/wheel_mold_P0.step" runs/asm_manual

# 3) 模型驱动 + 封缄
.venv/Scripts/python.exe scripts/model_drives_assembly.py --step "assets/wheel_mold_P0.step" --model virtu-moe-14b:fast
.venv/Scripts/python.exe scripts/seal_assembly_run.py --run runs/model_drive_<时间戳>

# 4) 反证测试
.venv/Scripts/python.exe -m pytest tests/test_assembly_gates.py tests/test_step_mates_falsifiable.py tests/test_step_bom_pose.py -q -p no:cacheprovider --basetemp=scratch/pt
```

> 注：SW 工程图/装配产物使用 ASCII 工作目录 `C:\temp_virtu_sw\virtu_<run_id>`（SW 2021 对中文路径与同名文档敏感），最终产物复制回 `runs/.../artifacts/`。
