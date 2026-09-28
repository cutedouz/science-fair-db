import re, json, html, time, requests
from concurrent.futures import ThreadPoolExecutor
S = requests.Session(); S.headers['User-Agent'] = 'Mozilla/5.0'
BASE = 'https://www.ntsec.edu.tw/science/'
CATS = {'22097': 442, '21278': 404, '19961': 404}

def get(url):
    for i in range(5):
        try:
            r = requests.get(url, timeout=30, headers={'User-Agent': 'Mozilla/5.0'}); r.raise_for_status(); r.encoding = 'utf-8'; return r.text
        except Exception as e:
            time.sleep(2 * (i + 1))
    raise RuntimeError(url)

def clean(x):
    x = re.sub(r'<br\s*/?>', '\n', x); x = re.sub(r'<[^>]+>', '', x)
    return html.unescape(x).replace('　', ' ').strip()

def list_page(args):
    cat, p = args
    s = get(f'{BASE}list.aspx?a=21&cat={cat}&p={p}')
    return [(cat, sid) for sid in re.findall(r'detail\.aspx\?a=21&(?:amp;)?cat=%s&(?:amp;)?sid=(\d+)' % cat, s)]

def detail(args):
    cat, sid = args
    s = get(f'{BASE}detail.aspx?a=21&cat={cat}&sid={sid}')
    d = {'sid': int(sid)}
    m = re.search(r'sciencefair-title">.*?<p[^>]*>(.*?)</p>', s, re.S); d['作品名稱'] = clean(m.group(1)) if m else ''
    for t, v in re.findall(r'<p class="title[^"]*">(.*?)</p>\s*<p[^>]*>(.*?)</p>', s, re.S):
        d[clean(t)] = clean(v)
    m = re.search(r'summary-movtivation[^>]*>.*?</h1>\s*<div class="article-content[^"]*">(.*?)</div>', s, re.S)
    d['摘要或動機'] = clean(m.group(1)) if m else ''
    files = re.findall(r'href="(https://www\.ntsec\.edu\.tw/article/FileAtt\.ashx\?id=\d+)"', s)
    d['檔案連結'] = files
    return d

if __name__ == '__main__':
    jobs = [(c, p) for c, n in CATS.items() for p in range(1, (n + 9) // 10 + 1)]
    with ThreadPoolExecutor(4) as ex:
        items = [x for r in ex.map(list_page, jobs) for x in r]
    items = list(dict.fromkeys(items))
    print('items', len(items), flush=True)
    with ThreadPoolExecutor(4) as ex:
        rows = list(ex.map(detail, items))
    json.dump(rows, open('data.json', 'w', encoding='utf-8'), ensure_ascii=False)
    print('done', len(rows))
