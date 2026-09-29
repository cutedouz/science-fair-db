"""從科教館網站補抓「資料庫有、但 PDF原始檔 沒有」的全國科展 PDF，存到 未分類PDF檔/科教館補抓/。
檔名比照其他 PDF：第XX屆_組別_科別_名次_編號_作品名稱.pdf，並寫入 pipeline/pdf_overrides.json 直接指定 sid。
"""
import json, os, re, time, requests, unicodedata
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, '未分類PDF檔', '科教館補抓')
works = [w for w in json.load(open(os.path.join(ROOT, 'data', 'works.json'), encoding='utf-8')) if w['src'] == '全國' and w['type'] == '作品']
has = {int(k) for k in json.load(open(os.path.join(ROOT, 'data', 'raw', 'pdf_codes.json')))}
todo = [w for w in works if w['id'] not in has and w['pdf']]
GROUP = {'國小': '國小組', '國中': '國中組', '高中': '高中組', '高職': '高職組', '高中職': '高中組'}
safe = lambda s: re.sub(r'[\\/:*?"<>|\n\r\t]+', '_', s).strip()[:80]

def name_of(w):
    grp = GROUP.get(w.get('stage_detail') or w.get('stage'), '組別未知')
    award = w['rank'] or '未列獎項'
    return safe(f"第{w['edition_no']}屆_{grp}_{w['subject'] or '科別未知'}_{award}_{w['code'] or '000000'}_{w['title']}") + '.pdf'

def fetch(w):
    d = os.path.join(OUT, f"第{w['edition_no']}屆"); os.makedirs(d, exist_ok=True)
    path = os.path.join(d, name_of(w))
    for i in range(3):
        try:
            r = requests.get(w['pdf'], timeout=120, headers={'User-Agent': 'Mozilla/5.0'})
            if r.content[:5] == b'%PDF-':
                open(path, 'wb').write(r.content)
                return w['id'], os.path.basename(path), len(r.content), 'ok'
            return w['id'], None, 0, '不是 PDF（連結可能已失效）'
        except Exception as e:
            err = str(e); time.sleep(5 * (i + 1))
    return w['id'], None, 0, f'下載失敗：{err[:60]}'

with ThreadPoolExecutor(4) as ex:
    res = list(ex.map(fetch, todo))
ov_path = os.path.join(ROOT, 'pipeline', 'pdf_overrides.json')
ov = json.load(open(ov_path, encoding='utf-8'))
for sid, fname, size, st in res:
    if fname:
        ov[unicodedata.normalize('NFC', fname)] = sid
json.dump(ov, open(ov_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump([r for r in res if r[3] != 'ok'], open(os.path.join(ROOT, 'data', 'fetch_missing_failed.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
ok = [r for r in res if r[3] == 'ok']
print('要補抓', len(todo), '成功', len(ok), f'（{sum(r[2] for r in ok)/1e6:.0f} MB）', '失敗', len(res) - len(ok))
for r in res:
    if r[3] != 'ok':
        print('  ', r[0], r[3])
