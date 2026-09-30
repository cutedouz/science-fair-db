"""下載臺灣國際科展作品 PDF，並分成兩份：
  分年：PDF原始檔/國際科展/<年份>年/
  分科：筆記本分類/國際_<領域>[_<年份範圍>]/（每個資料夾 ≤ 300 份，超過依年份拆分）
檔名：國際_<年份>_<科別>_<得獎>_<sid>_<作品名稱>.pdf
"""
import json, os, re, time, shutil, collections, requests
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'PDF原始檔', '國際科展')
DST = os.path.join(ROOT, '筆記本分類')
LIMIT = 300
safe = lambda s: re.sub(r'[\\/:*?"<>|\n\r\t]+', '_', s or '').strip()[:80]
works = [w for w in json.load(open(os.path.join(ROOT, 'data', 'works.json'), encoding='utf-8')) if w['src'] == '國際' and w['pdf']]

def name_of(w):
    return safe(f"國際_{w['year']}_{w['subject'] or '科別未知'}_{w['rank'] or '未列獎項'}_{w['id']}_{w['title']}") + '.pdf'

def fetch(w):
    d = os.path.join(RAW, f"{w['year']}年"); os.makedirs(d, exist_ok=True)
    path = os.path.join(d, name_of(w))
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return w, path, 'ok'
    err = ''
    for i in range(3):
        try:
            r = requests.get(w['pdf'], timeout=180, headers={'User-Agent': 'Mozilla/5.0'})
            if r.content[:5] == b'%PDF-':
                open(path, 'wb').write(r.content)
                return w, path, 'ok'
            return w, None, '不是 PDF（連結可能已失效）'
        except Exception as e:
            err = str(e)[:60]; time.sleep(5 * (i + 1))
    return w, None, f'下載失敗：{err}'

with ThreadPoolExecutor(4) as ex:
    res = list(ex.map(fetch, works))
ok = [(w, p) for w, p, st in res if st == 'ok']
fail = [(w['id'], w['year'], w['title'][:30], st) for w, p, st in res if st != 'ok']
json.dump(fail, open(os.path.join(ROOT, 'data', 'fetch_intl_failed.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)

# 分科：依標準領域分組，超過上限依年份切段
groups = collections.defaultdict(list)
for w, p in ok:
    groups[f"國際_{'、'.join(w['domains']) or '其他'}"].append((w, p))
count = collections.Counter()
for base, items in groups.items():
    items.sort(key=lambda x: x[0]['year'])
    chunks, cur = [], []
    for y in sorted({w['year'] for w, _ in items}):
        batch = [x for x in items if x[0]['year'] == y]
        if cur and len(cur) + len(batch) > LIMIT:
            chunks.append(cur); cur = []
        cur += batch
    chunks.append(cur)
    for c in chunks:
        lo, hi = c[0][0]['year'], c[-1][0]['year']
        folder = base if len(chunks) == 1 else f"{base}_{lo}年" if lo == hi else f"{base}_{lo}-{hi}年"
        os.makedirs(os.path.join(DST, folder), exist_ok=True)
        for w, p in c:
            dest = os.path.join(DST, folder, os.path.basename(p))
            if not os.path.exists(dest):
                shutil.copyfile(p, dest)
            count[folder] += 1
print('國際科展有 PDF 連結', len(works), '件；下載成功', len(ok), '；失敗', len(fail))
for k, v in sorted(count.items()):
    print(f'  {k:30s} {v}')
