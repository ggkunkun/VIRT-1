# -*- coding: utf-8 -*-
"""重启 SolidWorks 并获取 COM 句柄"""
import time
import win32com.client as w
import pythoncom

pythoncom.CoInitialize()
sw = None
try:
    sw = w.GetActiveObject('SldWorks.Application')
    print('ATTACHED_EXISTING')
except Exception as e:
    print('NO_EXISTING', type(e).__name__)
    sw = w.Dispatch('SldWorks.Application')
    print('DISPATCHED_NEW')

try:
    sw.Visible = True
except Exception as e:
    print('VISIBLE_ERR', e)

for i in range(40):
    try:
        rev = sw.RevisionNumber
        if rev:
            print('REV', rev)
            break
    except Exception:
        pass
    time.sleep(2)

try:
    ad = sw.ActiveDoc
    print('ACTIVEDOC', ad.GetTitle if ad else None)
except Exception as e:
    print('ACTIVEDOC_ERR', type(e).__name__, e)
print('DONE')
