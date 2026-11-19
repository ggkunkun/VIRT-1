# -*- coding: utf-8 -*-
"""严格校验：按全树 basename 索引判断文档引用的文件是否真实存在；排除标注性引用。"""
import re, os, glob
from collections import defaultdict

ROOT = r"D:\Virtu模型\ssnc_teaching"
DOCS = os.path.join(ROOT, "docs")

# 全树建立 basename -> [相对路径] 索引
name_index = defaultdict(list)
for dp, dns, fns in os.walk(ROOT):
    for fn in fns:
        name_index[fn].append(os.path.relpath(os.path.join(dp, fn), ROOT))

FILE_EXT = re.compile(r'\.(md|json|png|ini|cnc|htm|html|gif|jpg|jpeg)$', re.I)

not_found = []
checked = 0
for d in glob.glob(os.path.join(DOCS, '*.md')):
    text = open(d, encoding='utf-8').read()
    # 只匹配以文件扩展名结尾的引用（排除目录名 Code/ pic/ 和标注）
    for ref in re.findall(r'`([^`\n]+?)`', text):
        ref = ref.strip()
        if not FILE_EXT.search(ref):
            continue
        # 取路径最后一段作为 basename
        base = ref.replace('\\', '/').split('/')[-1]
        if not base or '*' in base or '<' in base:
            continue
        checked += 1
        if base not in name_index:
            not_found.append((os.path.basename(d), ref, base))

print("refs with file-extension checked:", checked)
print("NOT FOUND by basename:", len(not_found))
for f, ref, b in not_found[:80]:
    print("  [%s] %s   (basename=%s)" % (f, ref, b))
