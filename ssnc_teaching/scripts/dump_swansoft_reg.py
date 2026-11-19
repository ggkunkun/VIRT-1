# -*- coding: utf-8 -*-
import winreg, sys

def dump(root, path, depth=0):
    try:
        k = winreg.OpenKey(root, path)
    except OSError:
        return
    print('  ' * depth + '=== ' + path)
    i = 0
    while True:
        try:
            n, v, t = winreg.EnumValue(k, i)
            print('  ' * depth + '  V %s = %r' % (n, v))
            i += 1
        except OSError:
            break
    j = 0
    while True:
        try:
            sn = winreg.EnumKey(k, j)
            dump(root, path + '\\' + sn, depth + 1)
            j += 1
        except OSError:
            break
    winreg.CloseKey(k)

for hive, hn in [(winreg.HKEY_CURRENT_USER, 'HKCU'), (winreg.HKEY_LOCAL_MACHINE, 'HKLM')]:
    dump(hive, r'Software\Swansoft')
    dump(hive, r'Software\WOW6432Node\Swansoft')
    print('done', hn)
    break  # HKCU first only? no - do both
print('ALL DONE')
for hive, hn in [(winreg.HKEY_LOCAL_MACHINE,)]:
    dump(hive, r'Software\WOW6432Node\Swansoft')
    dump(hive, r'Software\Swansoft')
print('HKLM DONE')
