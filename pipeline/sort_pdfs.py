"""把 PDF原始檔 依「標準領域_學習階段」複製到 筆記本分類/，每個資料夾 ≤ 300 份（Gemini Notebook 單本上限）。

用法：
  python3 pipeline/sort_pdfs.py          # 只產生預覽 筆記本分類_預覽.csv，不複製
  python3 pipeline/sort_pdfs.py --copy   # 依預覽實際複製（原始檔不動）
"""
import csv, json, os, re, shutil, sys, collections, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'PDF原始檔')
DST = os.path.join(ROOT, '筆記本分類')
LIMIT = 300

nfc = lambda s: unicodedata.normalize('NFC', s)
# macOS 檔名可能是 NFD，統一用 NFC 比對
on_disk = {}
for d, _, fs in os.walk(SRC):
    for f in fs:
        if f.lower().endswith('.pdf') and not f.startswith('._'):
            on_disk[nfc(f)] = os.path.join(d, f)
# Google 雲端硬碟會把檔名中的 / ' % 等符號改成 _，所以改用「屆次＋作品編號」比對
by_code = {}
for f, full in on_disk.items():
    m = re.match(r'第(\d+)屆_.*?_(\d{6})_', f)
    if m:
        by_code[(int(m.group(1)), m.group(2))] = (f, full)

works = json.load(open(os.path.join(ROOT, 'data', 'works.json'), encoding='utf-8'))
idx = {(w['edition_no'], w['code']): w for w in works if w['code']}

plan, missing = [], []
for r in csv.DictReader(open(os.path.join(ROOT, 'data', 'raw', 'official_56-65.csv'), encoding='utf-8-sig')):
    ed = int(re.search(r'\d+', r['屆次']).group())
    w = idx.get((ed, r['作品編號']))
    domain = '、'.join(w['domains']) if w and w['domains'] else '未分類'
    stage = (w or {}).get('stage') or '未知階段'
    fname, path = by_code.get((ed, r['作品編號']), (None, None))
    row = {'屆次': ed, '作品編號': r['作品編號'], '作品名稱': r['作品名稱'], 'sid': (w or {}).get('id'),
           '標準領域': domain, '學習階段': stage, '檔名': fname or r['儲存檔名'], '來源路徑': path}
    (plan if path else missing).append(row)

# 分組；超過上限的組依屆次對半切
groups = collections.defaultdict(list)
for row in plan:
    groups[(row['標準領域'], row['學習階段'])].append(row)
for (d, s), rows in groups.items():
    if len(rows) <= LIMIT:
        for row in rows:
            row['資料夾'] = f'{d}_{s}'
    else:
        eds = sorted({x['屆次'] for x in rows})
        cut = eds[len(eds) // 2]
        for row in rows:
            lo, hi = (eds[0], cut - 1) if row['屆次'] < cut else (cut, eds[-1])
            row['資料夾'] = f'{d}_{s}_第{lo}-{hi}屆'

count = collections.Counter(row['資料夾'] for row in plan)
with open(os.path.join(ROOT, '筆記本分類_預覽.csv'), 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['資料夾', '份數'])
    for k, v in sorted(count.items()):
        w.writerow([k, v])
    w.writerow([])
    w.writerow(['資料夾', '屆次', '作品編號', '作品名稱', '檔名'])
    for row in sorted(plan, key=lambda x: (x['資料夾'], x['屆次'], x['作品編號'])):
        w.writerow([row['資料夾'], row['屆次'], row['作品編號'], row['作品名稱'], row['檔名']])

print('官方清單', len(plan) + len(missing), '找到檔案', len(plan), '缺檔', len(missing))
for m in missing:
    print('  缺', m['屆次'], m['作品編號'], m['作品名稱'][:30])
print('資料夾數', len(count), '最大', max(count.values()))
extra = set(on_disk) - {nfc(r['檔名']) for r in plan}
print('磁碟上有、清單沒有的 PDF', len(extra), list(extra)[:5])

if '--copy' in sys.argv:
    for row in plan:
        dest_dir = os.path.join(DST, row['資料夾'])
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, row['檔名'])
        if not os.path.exists(dest):
            shutil.copy2(row['來源路徑'], dest)
    print('已複製到', DST)
