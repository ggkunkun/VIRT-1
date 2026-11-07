# 全面工程能力语料装配报告（virtu_engine_agent_v1）

- 生成时间：2026-11-04T15:02:53+0800 / seed=20261104
- 行数：2246（复核入库 2246，去重丢弃 0）
- 训练文件 sha256：`8735ded829c1476bf90673af91249623e322938cbf23de5c2a55dbe4232ca512`
- 分词器：real_bpe:tokenizers:D:\Virtu模型\checkpoints\_base_qwen3_8b\tokenizer.json
- 契约头 token 占比：**17.6%**（阈值 35%；历史 virtu_fix_v1 是 47.1%）
- 多轮含工具返回值比例：**94.3%**（阈值 35%）
- 评测集污染命中：0（要求 0；闸已加载评测条 500 条，checked=True；隔离目录：D:\Virtu模型\data\benchmark\virtu_eval_v1、D:\Virtu模型\data\benchmark\virtu_eval_phys_v1、D:\Virtu模型\data\benchmark\virtu_fix_v1）
- 桌面真帧校验：检查 9 张，判废 0 张

## 各族条数

- `tool_route`：1200 条
- `tool_refusal`：110 条
- `repair_loop`：900 条
- `observe_act_verify`：18 条
- `six_software_facts`：18 条

## 六个软件覆盖

- autocad：153 条
- cimco：160 条
- cross：365 条
- desktop：6 条
- nx：5 条
- solidworks：1258 条
- sscnc：145 条
- vericut：154 条

## 坐标空间实测（桌面闭环的前提）

```json
{
  "aligned": true,
  "click_space": [
    1920,
    1080
  ],
  "dpi": 120,
  "frame_over_click_ratio": 1.0,
  "frame_space": [
    1920,
    1080
  ],
  "virtual_origin": [
    0,
    0
  ],
  "virtual_space": [
    3,
    21
  ]
}
```

## 已知限制（不许当成已解决）

1. tool_route 的 observation 是确定性解析回读（_stub_evidence），不是 SOLIDWORKS 实测体积；上线前必须由 scripts/model_drives_solidworks.py 那类监考环换成真回读
2. 只有 SOLIDWORKS 有类型库接地的能力卡；其余五个软件的可执行 API 声明故意不进训
3. observe_act_verify 的轨迹来自自建 Tk 探针窗口与桌面巡检，尚未覆盖真实 CAD 对话框

## 样例（每族一条，截断显示）

### tool_route

```
[{"role": "system", "content": "你是 Virtu 工业软件智能体，驱动 SOLIDWORKS/AutoCAD/NX/CIMCO/VERICUT/斯沃六套软件。只能调用给定工具；参数自己按标准算，不许照抄示例值。没有工具返回值就不许声称完成，汇报必须逐字引用返回值里的字段。单位 mm、角度度、密度 g/cm3、应力 MPa。"}, {"role": "user", "content": "HUB_2626.nc 要在斯沃里跑，先算 6 把刀的刀偏和刀尖象限"}, {"role": "assistant", "content": "", "tool_calls": [{"id": "call_00000", "type": "function", "function": {"name": "cadcam_sscnc_control", "arguments": "{\"action\": \"calculate_offsets\", \"tools\": [{\"quadrant\": 3, \"r\": 0.8, \"tool_num\": 1, \"type\": \"drill\", \"x\": 20.0, \"z\": -30.0}, {\"quadrant\": 3, \"r\": 0.8, \"tool_num\": 2, \"type\": \"outer_rough\", \"x\": 24.0, \"z\": -60.0}, {\"quadrant\": 3, \"r\": 0.8, \"tool_num\": 3, \"type\": \"drill\", \"x\": 28.0, \"z\": -90.0}, {\"quadrant\": 3, \"r\": 0.8, \"tool_num\": 4, \"type\": \"outer_rough\", \"x\": 32.0, \"z\": -120.0}, {\"quadrant\": 3, \"r\": 0.8, \"tool_num\": 5, \"type\…
```

### tool_refusal

```
[{"role": "system", "content": "你是 Virtu 工业软件智能体，驱动 SOLIDWORKS/AutoCAD/NX/CIMCO/VERICUT/斯沃六套软件。只能调用给定工具；参数自己按标准算，不许照抄示例值。没有工具返回值就不许声称完成，汇报必须逐字引用返回值里的字段。单位 mm、角度度、密度 g/cm3、应力 MPa。"}, {"role": "user", "content": "给我出个工程图"}, {"role": "assistant", "content": "缺图号、比例、主要外形尺寸与要标注的配合项，我不出图。"}]
```

### repair_loop

```
[{"role": "system", "content": "你是 Virtu 工业软件智能体，驱动 SOLIDWORKS/AutoCAD/NX/CIMCO/VERICUT/斯沃六套软件。只能调用给定工具；参数自己按标准算，不许照抄示例值。没有工具返回值就不许声称完成，汇报必须逐字引用返回值里的字段。单位 mm、角度度、密度 g/cm3、应力 MPa。"}, {"role": "user", "content": "做一件法兰：外径 139.1、轮毂 92.0、总高 27.0、12 个螺栓孔，孔径 9.9，倒角 2.9"}, {"role": "assistant", "content": "", "tool_calls": [{"id": "r00000", "type": "function", "function": {"name": "cadcam_solidworks_model", "arguments": "{\"action\": \"model_flange\", \"dimensions\": {\"D_bolt\": 9.9, \"D_bore\": 103.7, \"D_hub\": 92.0, \"D_outer\": 139.1, \"H_total\": 27.0, \"PCD\": 124.7, \"chamfer\": 2.9, \"n_bolts\": 12, \"t_base\": 10.8}, \"part_name\": \"Flange_d_b_r00000\"}"}}]}, {"role": "tool", "tool_call_id": "r00000", "content": "{\"attempted_dimensions\": {\"D_bolt\": 9.9, \"D_bore\": 103.7, \"D_hub\": 92.0, \"D_outer\": 139.1, \"H_total\": 27.0, \"PCD\": 124.7, \"chamfer\": 2.9, \"n_bolts\": 12, \"…
```

### observe_act_verify

```
[{"role": "system", "content": "你在本机桌面上通过截图与键鼠操作工业软件。坐标一律用截图画面的像素系。发键鼠之前必须先确认目标窗口存在且在前台；抓屏失败或被安全闸拦下时如实说没做成，不许描述你没看到的画面。每一次动作之后都要再一次抓屏或接口回读才算结论。"}, {"role": "user", "content": "先看一眼整屏当前状态"}, {"role": "assistant", "content": "", "tool_calls": [{"id": "g00001", "type": "function", "function": {"name": "cadcam_desktop_gui", "arguments": "{\"action\": \"capture\"}"}}]}, {"role": "tool", "tool_call_id": "g00001", "content": "{\"frame_sha256\": \"63830b2a0c4641f64afc296c0f54cc3f2ff9a5b49711b2f6984bee25ff8b3e3d\", \"frame_size\": [1920, 1080], \"height\": 1080, \"output_path\": \"data/desktop_traces/2026-11-04\\\\frames\\\\step_000001.png\", \"status\": \"captured\", \"target\": \"desktop\", \"width\": 1920}"}, {"role": "assistant", "content": "目标 None 的窗口不存在，实际拿到的是整屏（target=desktop，1920x1080）。所以只能说「截到了屏幕」，不能说「截到了 None 的窗口」。"}]
```

### six_software_facts

```
[{"role": "system", "content": "你是 Virtu 工业软件智能体，驱动 SOLIDWORKS/AutoCAD/NX/CIMCO/VERICUT/斯沃六套软件。只能调用给定工具；参数自己按标准算，不许照抄示例值。没有工具返回值就不许声称完成，汇报必须逐字引用返回值里的字段。单位 mm、角度度、密度 g/cm3、应力 MPa。"}, {"role": "user", "content": "SOLIDWORKS 2021 该走哪条自动化通道？"}, {"role": "assistant", "content": "通道：COM Automation(SldWorks.Application) + VBA/RunMacro2。判据：完成后必须靠COM 回读（特征树/体积/尺寸逐项读回）回读，不看返回值当成功。"}]
```
