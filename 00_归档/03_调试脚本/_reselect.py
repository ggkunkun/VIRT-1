import win32com.client as w, pythoncom
pythoncom.CoInitialize()
try: sw = w.GetActiveObject('SldWorks.Application')
except Exception: sw = w.Dispatch('SldWorks.Application')
p = sw.ActiveDoc
p.ClearSelection2(True)
sk = p.FeatureByName('草图2')
sk.Select2(False, 0)
print('SEL', sk.Name, '| selcount', p.SelectionManager.GetSelectedObjectCount2(-1) if hasattr(p.SelectionManager,'GetSelectedObjectCount2') else '?')
