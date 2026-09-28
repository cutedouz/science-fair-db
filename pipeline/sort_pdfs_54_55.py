"""把第 54～55 屆 PDF 併入 PDF原始檔 與 筆記本分類（每個資料夾 ≤ 300 份）。
依屆次拆分的資料夾（第56-60屆）改名為第54-60屆，第 54～55 屆併入其中。
"""
import json, os, re, shutil, collections, unicodedata, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'drive-download-20260928T153950Z-1-001')
RAW = os.path.join(ROOT, 'PDF原始檔', '科展資料庫', 'PDF')
DST = os.path.join(ROOT, '筆記本分類')
nfc = lambda s: unicodedata.normalize('NFC', s)
nt = lambda t: re.sub(r'[\W_]', '', t)
works = json.load(open(os.path.join(ROOT, 'data', 'works.json'), encoding='utf-8'))
by_code = {(w['edition_no'], w['code']): w for w in works if w['code']}
by_title = {(w['edition_no'], nt(w['title'])): w for w in works if w['src'] == '全國' and w['type'] == '作品'}

plan = []
for d, _, fs in os.walk(SRC):
    for f in fs:
        if f.startswith('._') or not f.lower().endswith('.pdf'):
            continue
        m = re.match(r'第(\d+)屆_.*?_(\d{6})_(.+)\.pdf$', nfc(f))   # 得獎欄可能含底線，取第一個六位數編號
        if not m:
            sys.exit(f'檔名格式不符：{f}')
        ed, code, title = int(m.group(1)), m.group(2), m.group(3)
        w = by_code.get((ed, code)) or by_title.get((ed, nt(title)))
        if not w:
            sys.exit(f'對不上：{f}')
        plan.append((os.path.join(d, f), ed, w))

existing = {d for d in os.listdir(DST) if not d.startswith('._')}
renames = {}
for d in existing:
    if d.endswith('_第56-60屆'):
        renames[d] = d.replace('_第56-60屆', '_第54-60屆')
for old, new in renames.items():
    os.rename(os.path.join(DST, old), os.path.join(DST, new))
    print('改名', old, '→', new)
existing = {renames.get(d, d) for d in existing}

count = collections.Counter()
for path, ed, w in plan:
    base = f"{'、'.join(w['domains']) or '未分類'}_{w['stage']}"
    folder = f'{base}_第54-60屆' if f'{base}_第54-60屆' in existing else base
    os.makedirs(os.path.join(RAW, f'第{ed}屆'), exist_ok=True)
    raw_path = os.path.join(RAW, f'第{ed}屆', os.path.basename(path))
    shutil.move(path, raw_path)                                  # 同一顆硬碟，搬移是瞬間完成
    os.makedirs(os.path.join(DST, folder), exist_ok=True)
    shutil.copyfile(raw_path, os.path.join(DST, folder, os.path.basename(path)))
    count[folder] += 1
for k, v in sorted(count.items()):
    n = len([f for f in os.listdir(os.path.join(DST, k)) if not f.startswith('._')])
    print(f'{k:28s} +{v:3d} → 共 {n}')
print('FINISHED', len(plan))
