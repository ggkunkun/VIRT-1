# -*- coding: utf-8 -*-
"""SolidWorks 版本锚定：全项目唯一事实来源。

为什么必须显式锁 Rev 29（2021）
--------------------------------
本机 2026-11-19 实测：注册表里同时存在两套版本链，但只有一套是真装的。

    HKCR\\SldWorks.Application
        -> CLSID {0A5BC87B-FDBF-4A0B-BC8A-DE1271220E81}
        -> D:\\SOLIDWORKS (2)\\sldworks.exe          [29.5.0.0070  SP5.0]  真实存在

    HKCR\\SldWorks.Application.34
        -> CLSID {666AAEE2-7A21-40FC-B768-2078840A88C3}
        -> D:\\Program Files\\SOLIDWORKS Corp2026\\SOLIDWORKS\\sldworks.exe
                                                      [目录不存在，卸载残留]

无版本 ProgID ``SldWorks.Application`` 由 Windows 解析到**最后一次安装**的版本
（本机是 9/24 装的 2021，不是 9/11 装的 2026）。也就是说：当前能跑通纯属安装
顺序的巧合。一旦重装/修复 2026，ProgID 会静默翻到 Rev 34，而
``gencache.EnsureModule(TLB_GUID, 0, 29, 0)`` 仍按 2021 的 typelib 生成早期绑定，
前后绑定版本错位，报错会极难定位。

因此本模块提供两件事：
1. ``SW_PROGID`` —— 带版本的 ProgID，任何 Dispatch/GetActiveObject 都用它；
2. ``assert_revision`` —— 附着手校验跑的是 29.x，不匹配立刻抛错，禁止静默降级。

参考实测记录见 ``AGENT_CHAIN_RUNTIME.md``（2021 体积偏差 0.15%）。
"""

from __future__ import annotations

# SOLIDWORKS 2021 SP5.0 = Revision 29
SW_REV_MAJOR = 29
SW_REV_PREFIX = "29."

# 带修订号的 ProgID：不受"最后安装版本"影响
SW_PROGID = "SldWorks.Application.29"

# 该版本的可执行文件（本机实测路径）
SW_EXE = r"D:\SOLIDWORKS (2)\SLDWORKS.exe"

# sldworks.tlb 的类型库 GUID（Embedded 在 SLDWORKS.exe 同目录）
TLB_GUID = "{83A33D31-27C5-11CE-BFD4-00400513BB57}"


class SWRevisionMismatch(RuntimeError):
    """连到了非预期的 SolidWorks 版本。"""


def revision_of(sw) -> str:
    """读取运行中实例的 RevisionNumber，形如 ``29.5.0.0070``；读不到返回空串。

    冷启动瞬间 COM 已激活但属性可能尚未就绪，故做 3 次短重试；
    仍读不到才返回空串，由 assert_revision 决定是否中止。
    """
    import time

    for _ in range(3):
        try:
            v = getattr(sw, "RevisionNumber")
            rev = str(v() if callable(v) else v).strip()
            if rev:
                return rev
        except Exception:
            pass
        time.sleep(0.3)
    return ""


def assert_revision(sw, where: str = "") -> str:
    """确认当前实例是 Rev 29（2021）。

    - 读不到版本 -> 抛错（未知版本不允许继续，避免在 2026 上静默跑错 API）
    - 版本前缀不符 -> 抛错，并在消息里带上实际版本，便于定位是多实例还是注册漂移

    返回实际版本文本，供调用方写进证据链。
    """
    rev = revision_of(sw)
    tag = ("%s: " % where) if where else ""
    if not rev:
        raise SWRevisionMismatch(
            tag + "无法读取 RevisionNumber，拒绝在未知版本上继续"
        )
    if not rev.startswith(SW_REV_PREFIX):
        raise SWRevisionMismatch(
            tag + "期望 Rev %s.x，实际 %s（多半连到了其它版本实例）"
            % (SW_REV_MAJOR, rev)
        )
    return rev
