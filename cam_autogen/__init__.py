"""cam_autogen：Agent 工业级自动化加工程序生成系统。

四个独立模块 + 校验 + 编排：
  process_recognition  M1 工艺类型识别        :8101
  optimization         M2 多目标最优方案求解  :8102
  program_generation   M3 加工程序自动生成    :8103
  machine_config       M4 机床参数自动配置    :8104
  verification         双重校验 + 可视化报告  :8105
  stock_positioning    毛坯摆放/定位规则（含可选联网标准查询）
  pipeline             端到端编排（进程内或 HTTP）  :8100
"""
import os as _os

# 避免多核 OpenBLAS 在受限内存环境（Windows 16GB 多进程并发时）过度预留线程缓冲池
_os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
_os.environ.setdefault("OMP_NUM_THREADS", "1")

__version__ = "1.0.0"
