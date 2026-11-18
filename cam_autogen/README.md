# `cam_autogen` — Agent 工业级自动化加工程序生成系统

## 1. 模块化独立部署架构

四个核心功能模块之间**零交叉依赖**，仅共享纯数据结构契约 [`contracts.py`](contracts.py) 与基础组件 [`common/__init__.py`](common/__init__.py)（由 [`test_cam_architecture.py`](../tests/cam_autogen/test_cam_architecture.py) 通过 AST 扫描强制校验）：

| 模块 | 包路径 | 独立启动命令 | 默认端口 | 核心 REST 接口 |
| :--- | :--- | :--- | :---: | :--- |
| M1 加工工艺类型识别 | `cam_autogen.process_recognition` | `python -m cam_autogen.process_recognition --port 8101` | 8101 | `GET /health`, `GET /v1/info`, `POST /v1/recognize`, `POST /v1/evaluate` |
| M2 最优加工方案求解 | `cam_autogen.optimization` | `python -m cam_autogen.optimization --port 8102` | 8102 | `GET /health`, `GET /v1/info`, `POST /v1/optimize` |
| M3 加工程序自动生成 | `cam_autogen.program_generation` | `python -m cam_autogen.program_generation --port 8103` | 8103 | `GET /health`, `GET /v1/info`, `POST /v1/generate` |
| M4 机床参数自动配置 | `cam_autogen.machine_config` | `python -m cam_autogen.machine_config --port 8104` | 8104 | `GET /health`, `GET /v1/info`, `GET /v1/machines`, `POST /v1/machines`, `POST /v1/configure` |
| 双重校验与可视化 | `cam_autogen.verification` | `python -m cam_autogen.verification --port 8105` | 8105 | `GET /health`, `GET /v1/info`, `POST /v1/verify` |
| 端到端全自动编排 | `cam_autogen.pipeline` | `python -m cam_autogen.pipeline --serve --port 8100` | 8100 | `GET /health`, `GET /v1/info`, `POST /v1/run` |

支撑组件：`cam_autogen.stock_positioning`（3-2-1 六点定位、虎钳/卡盘/尾座装夹禁区与可选联网工艺标准查询）。

## 2. 端到端 CLI 运行示例

```bash
# 使用内置阶梯轴示例一键生成 FANUC 程序 + 机床配置 + 可视化报告 + 溯源日志
.venv\Scripts\python.exe -m cam_autogen.pipeline --example shaft --dialect FANUC --out runs/cam_autogen/demo_shaft

# 使用西门子或华中数控系统生成车铣复合件或铣削件
.venv\Scripts\python.exe -m cam_autogen.pipeline --example keyed_shaft --dialect SIEMENS --out runs/cam_autogen/demo_keyed
.venv\Scripts\python.exe -m cam_autogen.pipeline --example block --dialect HUAZHONG --out runs/cam_autogen/demo_block
```

## 3. 输出交付物

每次端到端执行自动落盘：
- `<part_id>.nc`（或 SIEMENS `<part_id>.mpf`）：零修改可直接导入目标机床的 ISO 数控程序
- `<part_id>.machine_setup.json`：匹配机床规格、G54 工件偏置、刀库刀位表、专用后处理规则与行程校核
- `<part_id>.process_plan.json`：多目标求解后的逐工序切削参数、物理指标与约束满足度
- `<part_id>.stock_setup.json`：毛坯装夹方式、夹持深度、悬伸比与 3D 夹具禁区
- `<part_id>.verification.html` / `.json`：内嵌 SVG 刀轨图与分级告警的独立可视化校验报告
- `pipeline.log.jsonl`：全链路每阶段输入/输出摘要、状态与耗时审计日志（可用 `common.summarize_trace()` 回溯与分析性能瓶颈）
