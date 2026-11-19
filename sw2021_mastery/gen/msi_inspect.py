# -*- coding: utf-8 -*-
"""读取 solidworks.msi 中 SldToolboxUpdater 相关的 CustomAction 与属性。"""
import win32com.client

DB = r'E:\迅雷下载\SW2021_SP5_64bit\swwi\data\solidworks.msi'
m = win32com.client.Dispatch('WindowsInstaller.Installer')
db = m.OpenDatabase(DB, 0)

BT = '`'  # MSI SQL 标识符限定符

def dump(sql, cols):
    v = db.OpenView(sql)
    v.Execute()
    while True:
        r = v.Fetch()
        if r is None:
            break
        vals = [r.StringData(i) for i in range(1, cols + 1)]
        print(' | '.join(str(x)[:260] for x in vals))

print('=== Property 表 (源相关) ===')
dump('select {0}Property{0},{0}Value{0} from {0}Property{0}'.format(BT), 2) if False else None
v = db.OpenView("select `Property`,`Value` from `Property`")
v.Execute()
while True:
    r = v.Fetch()
    if r is None:
        break
    p, val = r.StringData(1), r.StringData(2)
    if any(k in p.upper() for k in ('SOURCE', 'TOOLBOX', 'SLDIM', 'MEDIA', 'ZIPS')):
        print(p, '=', val)

print()
print('=== CustomAction SldToolboxUpdater ===')
v = db.OpenView("select `Action`,`Type`,`Source`,`Target` from `CustomAction`")
v.Execute()
while True:
    r = v.Fetch()
    if r is None:
        break
    if 'ToolboxUpdater' in r.StringData(1):
        print(r.StringData(1), '| type', r.IntegerData(2), '| src', r.StringData(3), '| tgt', r.StringData(4))
