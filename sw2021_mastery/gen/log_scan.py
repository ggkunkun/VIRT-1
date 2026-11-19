# -*- coding: utf-8 -*-
import re, sys
t = open(r'D:\Virtu模型\sw2021_mastery\work\repair_localcache.log', 'rb').read().decode('utf-16-le', errors='replace')
lines = t.splitlines()

# 1) All 'Action ended' with nonzero return value
pat = re.compile(r'Action ended .*(?:return value|返回值)\s*:?\s*(\d+)')
for i, l in enumerate(lines):
    m = pat.search(l)
    if m and m.group(1) != '0':
        print('NONZERO END @', i, l[:200])

print('====')
# 2) Find InstallExecute result
for i, l in enumerate(lines):
    if 'InstallExecute' in l and ('ended' in l or '返回值' in l or 'Action start' in l):
        print('IE @', i, l[:220])

print('====')
# 3) lines mentioning 1729 / 2318 / error codes 2xxx/3xxx non-noise
seen = set()
for i, l in enumerate(lines):
    m = re.search(r'Note: 1: (\d{4})', l)
    if m and m.group(1) not in {'2203','2262','2205','2711','2726','1717','1406','2718','2318','2898'}:
        key = m.group(1)
        if key not in seen:
            seen.add(key)
            print('NOTE @', i, l[:250])
