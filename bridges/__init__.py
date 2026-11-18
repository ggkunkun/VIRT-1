# -*- coding: utf-8 -*-
"""bridges - 本地工业软件 / 桌面自动化桥接层。

本文件使 bridges 成为常规包（此前该目录无 __init__.py，属隐式命名空间目录，
在 setuptools packages.find 的 namespaces=false 模式下不会被安装，
pip install -e . 之后 `import bridges.xxx` 会 ModuleNotFoundError）。

设计约束：
- 不做任何 `from .xxx import ...` 的集中再导出，避免在导入 bridges 时
  触发子模块的第三方依赖（pywin32 / uiautomation / COM 等）。
- 子模块一律按显式路径导入：`from bridges.xxx import yyy`。
"""

__all__ = []
