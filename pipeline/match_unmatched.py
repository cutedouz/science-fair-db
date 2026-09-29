"""把 data/pdf_unmatched.json 裡對不上的 PDF，以近似名稱規則找出對應作品，寫進 pipeline/pdf_overrides.json。
規則（只考慮同屆、還沒有 PDF 的作品）：名稱正規化後相同；或名稱互相包含且只有一件；或前 5 字相同且最像；
或相似度 ≥ 0.5 且比第二名高 0.2 以上。檔名寫「作品名稱待核對」者不處理。
"""
import json, os, re, difflib, unicodedata, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sort_new_pdfs import ROOT, load_index, match_pdf
nfc = lambda s: unicodedata.normalize('NFC', s)
nk = lambda t: re.sub(r'[\W_]', '', unicodedata.normalize('NFKC', t)).lower()
works, by_code, by_title, overrides = load_index()
has = {int(k) for k in json.load(open(os.path.join(ROOT, 'data', 'raw', 'pdf_codes.json')))}
unmatched = json.load(open(os.path.join(ROOT, 'data', 'pdf_unmatched.json'), encoding='utf-8'))
ov_path = os.path.join(ROOT, 'pipeline', 'pdf_overrides.json')
ov = json.load(open(ov_path, encoding='utf-8'))
taken, added, rest = set(has), [], []
for f in unmatched:
    m = re.match(r'第(\d+)屆_.*?_(\d{2,6})_(.+)\.pdf$', nfc(f))
    if not m:
        rest.append(f); continue
    ed, title = int(m.group(1)), m.group(3)
    while re.match(r'\d{2,4}_', title):
        title = title.split('_', 1)[1]
    title = re.sub(r'[（(][^）)]*組[）)]$', '', title)
    t = nk(title)
    pool = [w for w in works.values() if w['edition_no'] == ed and w['src'] == '全國' and w['type'] == '作品' and w['id'] not in taken]
    sc = sorted(((difflib.SequenceMatcher(None, t, nk(w['title'])).ratio(), w) for w in pool), key=lambda x: -x[0]) + [(0, None)] * 2
    (r1, w1), (r2, _) = sc[0], sc[1]
    exact = [w for w in pool if nk(w['title']) == t]
    sub = [w for w in pool if len(t) >= 4 and (t in nk(w['title']) or nk(w['title']) in t)]
    pre = [w for w in pool if len(t) >= 2 and (nk(w['title']).startswith(t[:5]) or t.startswith(nk(w['title'])[:5]))]
    if '待核對' in title or not w1:
        w = None
    elif exact:
        w = exact[0]
    elif len(sub) == 1:
        w = sub[0]
    elif len(pre) == 1 and pre[0] is w1 and r1 - r2 >= 0.1:
        w = w1
    elif r1 >= 0.5 and r1 - r2 >= 0.2:
        w = w1
    else:
        w = None
    if w:
        ov[nfc(f)] = w['id']; taken.add(w['id']); added.append((title, w['title']))
    else:
        rest.append(f)
json.dump(ov, open(ov_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('新增對照', len(added), '份；仍對不上', len(rest), '份')
import random
random.seed(0)
for a, b in random.sample(added, min(12, len(added))):
    print('  抽查', a[:24], '→', b[:28])
