# -*- coding: utf-8 -*-
import re, sys
p = sys.argv[1]
d = open(p, 'rb').read()
strs = [m.group().decode() for m in re.finditer(rb'[\x20-\x7e]{4,}', d)]
kw = re.compile(r'(?i)(sscnc|control|\.ini|\.xml|param|swansoft|software|\\\\)')
seen = set()
for s in strs:
    if kw.search(s) and 'Afx' not in s and 'MFCTool' not in s and s not in seen:
        seen.add(s)
        print(repr(s[:140]))
# utf16 strings
for m in re.finditer(rb'(?:[\x20-\x7e]\x00){4,}', d):
    s = m.group().decode('utf-16-le')
    if kw.search(s) and s not in seen:
        seen.add(s)
        print('U', repr(s[:140]))
