# -*- coding: utf-8 -*-
"""校验所有文档中反引号引用的本地文件/图片路径是否真实存在。"""
import re, os, glob

DOCS = r"D:\Virtu模型\ssnc_teaching\docs"
BASE = r"D:\Virtu模型\ssnc_teaching"

exts = ('.md', '.json', '.png', '.ini', '.cnc', '.htm', '.gif', '.jpg', '.jpeg', '.GIF', '.JPG', '.PNG')

def resolve(ref, docpath):
    r = ref.strip().replace('/', os.sep).replace('\\', os.sep)
    r = r.lstrip(os.sep)
    cands = [
        os.path.join(BASE, r),
        os.path.join(os.path.dirname(docpath), r),
        os.path.join(os.path.dirname(docpath), '..', r),
    ]
    for c in cands:
        c = os.path.normpath(c)
        if os.path.exists(c):
            return True, c
    return False, None

missing = []
total = 0
for d in glob.glob(os.path.join(DOCS, '*.md')):
    text = open(d, encoding='utf-8').read()
    refs = re.findall(r'`([^`\n]{2,160})`', text)
    for ref in refs:
        if ref.endswith(exts) or ref.count('/') >= 1:
            # 跳过明显是通配符/概念性描述
            if '*' in ref or '<' in ref or ' ' in ref and not ref.endswith(exts):
                continue
            total += 1
            ok, p = resolve(ref, d)
            if not ok:
                missing.append((os.path.basename(d), ref))

print("checked refs:", total)
print("missing:", len(missing))
for f, r in missing[:60]:
    print("  MISSING [%s] %s" % (f, r))
