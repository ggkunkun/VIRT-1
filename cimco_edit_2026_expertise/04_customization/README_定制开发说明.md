# 阶段4 高级配置与定制能力交付说明

> 2026-11-18。所有成果经 `verify_deliverables.py` 实测验证（6/6 PASS，见 `verification_report.json`）。
> 边界遵循 `../00_sources/CAPABILITY_BOUNDARIES.md`（尤其 B-04 后处理定位、B-03 华中数控）。

## 一、交付清单

### 后处理定制 3 例（均基于官方 Posts/*.js 派生，非从零臆造）
| 文件 | 基线 | 定制点 | 验证 |
|---|---|---|---|
| `post_processors/PP_CASE1_Fanuc_NOK_Increment.js` | 官方 `fanuc.js` | 序列号起始 10→1000、步长 5→10；适配不支持 G81 K 参数的控制器（长手持钻孔） | 函数集与基线一致、元数据已定制、括号平衡 |
| `post_processors/PP_CASE2_Huazhong_ISO_Generic.js` | 官方 `fanuc.js` | 螺旋线性化开启、容差 0.01→0.02；适配华中数控无螺旋插补场景 | 同上；标题明确标注 B-03 非原生 |
| `post_processors/PP_CASE3_Heidenhain_Metric_Finish.js` | 官方 `heidenhain.js` | 公差 0.02→0.005mm（精加工） | 函数集与基线一致（Heidenhain 用 reset/onInit 生命周期，非 onOpen/onClose） |

- `_base_*.js` 是从本机安装目录复制的官方基线（可比对差异）。
- `_derive_report.json` 记录每处修改，全部 applied（无 NOT_APPLIED）。
- **部署方法**：将定制 .js 复制到 `CIMCO Edit→Editor Setup→Plugins/Post Processors` 对应目录，或在 CNC-Calc/后处理选择时指向该文件路径。
- **边界**：CIMCO Edit 的后处理用于 CNC-Calc 生成的刀路与反向后处理（B-04），不是通用 CAM 后处理；上线前须在目标机床做空运行验证。

### 宏脚本自动化工具 2 个（均可直接运行）
| 文件 | 功能 | 实测 |
|---|---|---|
| `macros/macro1_batch_validate.py` | 批量 NC 校验+质量报告（CSV/JSON），基于已实测的 cimco_bridge | 2 样本：合规件 PASS、故障件（未闭合循环+缺M30）FAIL，符合预期 |
| `macros/macro2_renumber_format.py` | 批量重编号+规范化，规则对齐官方 .MAC [RENUM]（SKIP=%,O） | 输出 N100/N110/N120 正确，%与O行跳过 |

- 运行报告样例：`macros/_verify_batch_report.json`、`macros/_verify_renum_report.json`。
- **部署**：两脚本仅依赖 `D:\Virtu模型\bridges\cimco_bridge.py` 与 Python 标准库，放到同机即可运行。
- **边界**：本地静态校验/格式化，非 CIMCO 内核 GUI 宏（B-06）。

## 二、验证结果（verify_deliverables.py）

```
[PP] 3 个后处理：missing=[] funcs_lost=[] 元数据已定制 → PASS
[DERIVE] not_applied=[] → PASS
[MACRO1] good.nc=PASS bad.nc=FAIL → PASS（负面样本被正确拦截）
[MACRO2] N100/N110/N120 → PASS
SUMMARY: 6/6 PASS all_pass=True
```

## 三、诚实说明
1. 后处理"可直接在工业现场部署"= 结构合法、与官方基线同源、参数修改可追溯；**不宣称已在真实机床验证过加工结果**（这需要现场空运行）。
2. 华中数控后处理按 B-03 明确为"ISO 通用模板近似、非官方原生支持"，必须现场验证。
3. 宏脚本是工程等价实现（Python），不是 CIMCO 内建 VBA/JS 宏录制文件；覆盖了对应的自动化场景。
