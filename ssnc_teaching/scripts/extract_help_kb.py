# -*- coding: utf-8 -*-
"""把官方CHM反编译出的251个.htm主题批量转为结构化Markdown知识库，抽取文本+本地截图引用。"""
import os, re, html, glob, json

SRC = r"D:\Virtu模型\ssnc_teaching\source\chm_cn"
KB   = r"D:\Virtu模型\ssnc_teaching\source\help_kb_md"
os.makedirs(KB, exist_ok=True)

def decode(raw):
    for enc in ["utf-8", "gb18030", "gbk"]:
        try: return raw.decode(enc)
        except Exception: pass
    return raw.decode("utf-8", "ignore")

def html_to_md(s, base):
    # 记录图片引用
    imgs = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', s, re.I)
    s = re.sub(r'<script.*?</script>', '', s, flags=re.S|re.I)
    s = re.sub(r'<style.*?</style>', '', s, flags=re.S|re.I)
    # br/p/div -> newline
    s = re.sub(r'<br\s*/?>', '\n', s, flags=re.I)
    s = re.sub(r'</(p|div|tr|h[1-6]|li)>', '\n', s, flags=re.I)
    s = re.sub(r'<[^>]+>', '', s)
    s = html.unescape(s)
    s = s.replace('\xa0', ' ')
    lines = [re.sub(r'[ \t]+', ' ', ln).strip() for ln in s.split('\n')]
    lines = [ln for ln in lines if ln]
    out = '\n'.join(lines)
    imgs_rel = []
    for im in imgs:
        im = im.replace('\\', '/')
        rel = os.path.relpath(os.path.normpath(os.path.join(base, im)), KB).replace('\\','/')
        imgs_rel.append(rel)
    return out, imgs_rel

files = glob.glob(os.path.join(SRC, "**", "*.htm"), recursive=True) + \
        glob.glob(os.path.join(SRC, "**", "*.html"), recursive=True)
files = sorted(set(files))
index = []
for p in files:
    raw = open(p, 'rb').read()
    s = decode(raw)
    base = os.path.dirname(p)
    text, imgs = html_to_md(s, base)
    rel = os.path.relpath(p, SRC).replace('\\','/')
    # 先处理 .html 再 .htm，避免同名文件互相覆盖（如 802d_ref_frame.html/.htm）
    outname = rel.replace('/', '__').replace('.html', '.html.md').replace('.htm', '.md')
    outpath = os.path.join(KB, outname)
    title = ''
    m = re.search(r'<title>(.*?)</title>', s, re.S|re.I)
    if m: title = html.unescape(re.sub(r'<[^>]+>','',m.group(1))).strip()
    header = "# %s\n\n> 官方帮助主题源文件: `source/chm_cn/%s`\n" % (title or outname, rel)
    if imgs:
        header += "\n> 关联官方截图(%d):\n" % len(imgs)
        for im in imgs[:60]:
            header += "> - `source/chm_cn/%s`\n" % im.replace('../','')
    body = header + "\n---\n\n" + text + "\n"
    open(outpath, 'w', encoding='utf-8').write(body)
    index.append({"src": rel, "md": outname, "title": title, "chars": len(text), "imgs": len(imgs)})

json.dump(index, open(os.path.join(KB, "_index.json"),'w',encoding='utf-8'), ensure_ascii=False, indent=1)
print("converted", len(index), "topics; total chars", sum(i['chars'] for i in index))
print("topics with imgs", sum(1 for i in index if i['imgs']>0))
# 打印较长的主题（内容量大的优先）
for i in sorted(index, key=lambda x:-x['chars'])[:25]:
    print("%6d ch %3d img  %s  %s" % (i['chars'], i['imgs'], i['title'][:30], i['src'][:60]))
