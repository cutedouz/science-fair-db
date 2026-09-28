"""從 data/works.json 產生網站用的資料檔（site/data/）。

- meta.json：作品清單（不含摘要），網站一開就載入
- abstracts-N.json：摘要，分檔在背景載入
- similar.json：每件作品最相近的 8 件（字元雙字組 TF-IDF 餘弦相似度）
網站不存作者姓名：works.json 本來就沒有作者欄位。

用法：python3 pipeline/build_site_data.py
"""
import json, math, os, re, collections, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'site', 'data')
os.makedirs(OUT, exist_ok=True)
works = json.load(open(os.path.join(ROOT, 'data', 'works.json'), encoding='utf-8'))

# ---------- 作品清單 ----------
meta = []
for w in works:
    m = {
        'i': w['id'], 's': 0 if w['src'] == '全國' else 1, 't': w['title'], 'y': w['year'], 'e': w['edition'],
        'g': w.get('stage'), 'gs': w.get('stage_src'), 'gd': w.get('stage_detail'),
        'd': w['domains'], 'sj': w['subject'], 'r': w['rank'], 'sp': w['special'], 'rp': w['rep'],
        'sc': w['school'], 'c': w['city'], 'tc': w['teachers'], 'k': w['keywords'], 'cd': w['code'],
        'p': w['pdf'],
    }
    if w['type'] == '評語':
        m['v'] = 1
    if w.get('related'):
        m['rl'] = w['related']
    if os.path.exists(os.path.join(OUT, 'fulltext', f"{w['id']}.json")):
        m['f'] = 1          # 有研究內容節錄（pipeline/extract_fulltext.py 產生）
    meta.append({k: v for k, v in m.items() if v not in (None, [], '')})

def dump(name, obj):
    path = os.path.join(OUT, name)
    json.dump(obj, open(path, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    return os.path.getsize(path)

sizes = {'meta.json': dump('meta.json', meta)}

# ---------- 摘要（分檔，每檔 < 6MB） ----------
chunks, cur, cur_size = [], {}, 0
for w in works:
    a = w['abstract']
    if not a:
        continue
    cur[w['id']] = a
    cur_size += len(a.encode('utf-8')) + 12
    if cur_size > 6_000_000:
        chunks.append(cur); cur, cur_size = {}, 0
if cur:
    chunks.append(cur)
for n, ch in enumerate(chunks):
    sizes[f'abstracts-{n}.json'] = dump(f'abstracts-{n}.json', ch)

# ---------- 相似作品（很花時間；已存在就沿用，加 --similar 才重算） ----------
import sys
if os.path.exists(os.path.join(OUT, 'similar.json')) and '--similar' not in sys.argv:
    similar = json.load(open(os.path.join(OUT, 'similar.json'), encoding='utf-8'))
else:
    similar = None
def tokens(w):
    text = ' '.join([w['title']] * 3 + [' '.join(w['keywords'])] * 2 + [w['abstract']]).lower()
    toks = []
    for run in re.findall(r'[一-鿿]+', text):
        toks += [run[i:i + 2] for i in range(len(run) - 1)]
    toks += [t for t in re.findall(r'[a-z][a-z0-9\-]{2,}', text)]
    return toks

def compute_similar(docs):
    tf = [collections.Counter(tokens(w)) for w in docs]
    df = collections.Counter(t for c in tf for t in c)
    N = len(docs)
    vecs = []
    for c in tf:
        v = {t: (1 + math.log(n)) * math.log(N / df[t]) for t, n in c.items() if df[t] > 1 and df[t] < N * 0.2}
        top = sorted(v.items(), key=lambda x: -x[1])[:60]
        norm = math.sqrt(sum(x * x for _, x in top)) or 1
        vecs.append({t: x / norm for t, x in top})
    inv = collections.defaultdict(list)
    for i, v in enumerate(vecs):
        for t, x in v.items():
            inv[t].append((i, x))
    norm_title = lambda t: re.sub(r'[\W_]', '', t).lower()
    similar = {}
    for i, v in enumerate(vecs):
        acc = collections.defaultdict(float)
        for t, x in v.items():
            for j, y in inv[t]:
                if j != i:
                    acc[j] += x * y
        same = norm_title(docs[i]['title'])
        best = [(j, s) for j, s in sorted(acc.items(), key=lambda x: -x[1]) if norm_title(docs[j]['title']) != same][:8]
        similar[docs[i]['id']] = [docs[j]['id'] for j, s in best if s > 0.08]
    return similar

if similar is None:
    similar = compute_similar(docs := [w for w in works if w['type'] == '作品'])
sizes['similar.json'] = dump('similar.json', similar)

docs = [w for w in works if w['type'] == '作品']
info = {'built': datetime.date.today().isoformat(), 'count': len(docs), 'reviews': len(works) - len(docs),
        'abstract_files': len(chunks)}
sizes['info.json'] = dump('info.json', info)
for k, v in sizes.items():
    print(f'{k:20s} {v / 1e6:.1f} MB')
print(info)
