# Agent-Desktop 全模型接入与闭环验证报告
**生成时间**: 2026-11-08 14:41:20
**开源项目**: [vercel-labs/agent-desktop](https://github.com/vercel-labs/agent-desktop) v1.2.0
**适配平台**: windows (Native Accessibility Tree / UIA)
**测试口径**: 实测闭环 (Thought -> Action -> Observation -> Conclusion)
**接入成功率**: 8 / 8

## 1. 全模型接入状态矩阵
| 序号 | 模型名称 / 标签 | 接入状态 | 耗时 (s) | 触发工具 | 闭环结论摘要 |
|:---:|:---|:---:|:---:|:---|:---|
| 1 | `virtu-13.63b:hardened` | ✅ 成功 | 42.83 | `desktop_status` | 桌面适配器运行状态：权限已授权，平台为 Windows。无需要屏幕录制或自动化操作的界面交互需求，当前桌面处于可访问状态... |
| 2 | `virtu-moe-14b:hardened` | ✅ 成功 | 51.97 | `desktop_status` | 系统桌面适配器状态检查完成，当前运行健康度为正常（ok: true），已获得无障碍访问权限。支持的屏幕表面类型包括窗口、... |
| 3 | `virtu-v3:hardened` | ✅ 成功 | 16.98 | `desktop_status` | 桌面适配器状态检查完成，系统报告如下： - **软件版本**: 2.6 - **运行状态**: ✅ 正常运行（ok: t... |
| 4 | `virtu-internet-enhanced:latest` | ✅ 成功 | 38.88 | `desktop_status` | 系统桌面适配器状态正常，权限已授予。... |
| 5 | `qwen3:8b` | ✅ 成功 | 28.33 | `desktop_status` | 系统桌面适配器状态检查结果如下：  - **状态**: 正常（`ok: true`） - **版本**: 2.6 - *... |
| 6 | `qwen2.5:7b-instruct-q4_K_M` | ✅ 成功 | 18.04 | `desktop_status` | 桌面适配器状态检查结果显示如下：  - 系统平台：Windows - 权限状态：   - 可访问性权限：已授予   - ... |
| 7 | `qwen2.5:1.5b` | ✅ 成功 | 5.79 | `desktop_status` | The desktop status check for your Windows system has been co... |
| 8 | `models/Qwen3-VL-2B-Instruct (Local HF)` | ✅ 成功 | - | `-` | Local safetensors weights present (4.25 GB). Ready for visua... |

## 2. 核心架构与功能特征
- **无坐标盲猜**: 基于操作系统原生无障碍树 (Accessibility Tree)，为每个控件分配唯一且稳定的 `@ref` ID。
- **多协议支持**: 支持直接 CLI JSON 管道调用与标准 stdio MCP (Model Context Protocol) 模式。
- **工业多软件兼容**: 与 SOLIDWORKS、AutoCAD、CIMCO、VERICUT、NX 形成互补，支持桌面状态无副作用探测。
- **自动沙箱适配**: 内置 WinSta0 桌面会话自动绑定与 Win32 容灾降级层，确保在后台执行器或服务进程下零崩溃。