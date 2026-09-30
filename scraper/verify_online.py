"""上科教館官網逐筆重新抓取，和 data/raw/scan.jsonl 比對，並掃描新的 sid。
輸出：
  data/raw/scan_verify.jsonl     本次抓到的官網資料
  data/verify_report.json        差異清單（欄位、舊值、新值）與新作品
"""
import json, os, sys, datetime
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scrape
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
old = {}
for line in open(os.path.join(ROOT, 'data', 'raw', 'scan.jsonl'), encoding='utf-8'):
    r = json.loads(line)
    if r.get('作品名稱'):
        old[r['sid']] = r
hi = max(old)
sids = sorted(old) + list(range(hi + 1, hi + 2001))          # 已知作品＋其後 2,000 個 sid
out_path = os.path.join(ROOT, 'data', 'raw', 'scan_verify.jsonl')
done = {}
if os.path.exists(out_path):
    for line in open(out_path, encoding='utf-8'):
        r = json.loads(line); done[r['sid']] = r
f = open(out_path, 'a', encoding='utf-8')

def job(sid):
    try:
        d = scrape.detail(('22097', str(sid)))
    except Exception as e:
        d = {'sid': sid, 'error': str(e)}
    return d

todo = [s for s in sids if s not in done]
with ThreadPoolExecutor(6) as ex:
    for n, d in enumerate(ex.map(job, todo), 1):
        done[d['sid']] = d
        f.write(json.dumps(d, ensure_ascii=False) + '\n'); f.flush()
        if n % 1000 == 0:
            print('progress', n, '/', len(todo), flush=True)
FIELDS = ['作品名稱', '科展類別', '屆次', '科別', '得獎情形', '學校名稱', '指導老師', '作者', '關鍵字', '摘要或動機', '檔案連結']
norm = lambda v: ' '.join(v).strip() if isinstance(v, list) else (v or '').strip()
diffs, gone, errors = [], [], []
for sid, o in old.items():
    n = done.get(sid, {})
    if 'error' in n:
        errors.append(sid); continue
    if not n.get('作品名稱'):
        gone.append(sid); continue
    for k in FIELDS:
        if norm(o.get(k)) != norm(n.get(k)):
            diffs.append({'sid': sid, '欄位': k, '舊': norm(o.get(k))[:200], '新': norm(n.get(k))[:200]})
new = [d for s, d in done.items() if s > hi and d.get('作品名稱')]
report = {'核對日期': datetime.date.today().isoformat(), '已知作品': len(old), '差異筆數': len(diffs),
          '有差異的作品': len({d['sid'] for d in diffs}), '官網已不存在': gone, '抓取失敗': errors,
          '新作品': [{'sid': d['sid'], '作品名稱': d['作品名稱'], '科展類別': d.get('科展類別'), '屆次': d.get('屆次')} for d in new],
          '差異': diffs}
json.dump(report, open(os.path.join(ROOT, 'data', 'verify_report.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('FINISHED 已知', len(old), '差異', len(diffs), '筆（', report['有差異的作品'], '件）；官網已不存在', len(gone), '；失敗', len(errors), '；新作品', len(new))
