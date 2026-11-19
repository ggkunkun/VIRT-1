"""Fetch the full CIMCO Edit 2026 official documentation corpus from docs.cimco.com.

Source of truth for the entire capability-building deliverable.
Low-concurrency + retry to avoid upstream throttling.
Re-runnable: python fetch_official.py
"""
import urllib.request, ssl, re, json, html, time, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup

HERE = r"D:\Virtu模型\cimco_edit_2026_expertise\00_sources"
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36'}


def get(url, tries=4):
    for i in range(tries):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40, context=CTX)
            return r.read().decode('utf-8', 'ignore')
        except Exception as exc:
            if i == tries - 1:
                sys.stderr.write(f"FAIL {url} {exc!r}\n")
                return None
            time.sleep(1.5 * (i + 1))


def extract(html_text):
    soup = BeautifulSoup(html_text, 'html.parser')
    for bad in soup(['script', 'style', 'nav', 'aside', 'header', 'footer', 'noscript']):
        bad.decompose()
    title_el = soup.find('h1') or soup.find('title')
    title = title_el.get_text(' ', strip=True) if title_el else ''
    # CIMCO docs put the article body in the longest div whose class contains 'content'
    cands = [d for d in soup.find_all('div', class_=re.compile(r'content|markdown', re.I))]
    body_el = max(cands, key=lambda d: len(d.get_text(' ', strip=True))) if cands else None
    if body_el is None:
        body_el = soup.body or soup
    text = re.sub(r'[ \t]+', ' ', body_el.get_text('\n', strip=True))
    text = re.sub(r'\n\s*\n+', '\n', text).strip()
    return title, text


def fetch_one(url):
    h = get(url)
    if not h:
        return url, None, None
    try:
        title, text = extract(h)
    except Exception as exc:
        return url, f"EXTRACT_ERR:{exc}", None
    return url, title, text


def main():
    urls = json.load(open(HERE + r"\official_urls.json", encoding='utf-8'))
    corpus = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(fetch_one, u): u for u in urls}
        for f in as_completed(futs):
            u, title, text = f.result()
            if text and len(text) > 80:
                corpus[u] = {'title': title, 'text': text}
    json.dump(corpus, open(HERE + r"\official_corpus.json", 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    from collections import Counter
    c = Counter()
    for u in corpus:
        m = re.search(r'/edit/2026/([^/]+)/', u)
        c[m.group(1) if m else '?'] += 1
    print(f"FETCHED {len(corpus)}/{len(urls)}  TOTAL_CHARS {sum(len(v['text']) for v in corpus.values())}")
    for k, v in c.most_common():
        print(f"  {k}: {v}")


if __name__ == '__main__':
    main()
