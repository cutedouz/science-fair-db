"""補跑沒有結果的 PDF（每份獨立程序、限時），並重建 data/fulltext_report.csv。"""
import csv, json, os, subprocess, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_fulltext import ROOT, OUT_FULL, OUT_SITE, MAX_CHARS, trim
from extract_fulltext import find_jobs
jobs = [(sid, path) for sid, path, _ in find_jobs()]
status_path = os.path.join(ROOT, 'data', 'fulltext_status.json')
status = json.load(open(status_path)) if os.path.exists(status_path) else {}
for sid, path in jobs:
    if os.path.exists(os.path.join(OUT_FULL, f'{sid}.json')) or str(sid) in status:
        continue
    try:
        out = subprocess.run([sys.executable, '-W', 'ignore', os.path.join(ROOT, 'pipeline', 'extract_one.py'), str(sid), path],
                             capture_output=True, text=True, timeout=60)
        res = json.loads(out.stdout.strip().splitlines()[-1]) if out.returncode == 0 and out.stdout.strip() else {'secs': None, 'status': f'程式錯誤（代碼 {out.returncode}）'}
    except subprocess.TimeoutExpired:
        res = {'secs': None, 'status': '處理逾時'}
    if res['secs']:
        secs = res['secs']
        json.dump(secs, open(os.path.join(OUT_FULL, f'{sid}.json'), 'w', encoding='utf-8'), ensure_ascii=False)
        short, _ = trim(secs, MAX_CHARS)
        json.dump([{'h': s['h'], 't': s['text']} for s in short], open(os.path.join(OUT_SITE, f'{sid}.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, separators=(',', ':'))
    else:
        status[str(sid)] = res['status']
    print(sid, res['status'], flush=True)
json.dump(status, open(status_path, 'w'), ensure_ascii=False)
rows, stat = [], collections.Counter()
for sid, path in jobs:
    p = os.path.join(OUT_SITE, f'{sid}.json')
    if os.path.exists(p):
        secs = json.load(open(p, encoding='utf-8'))
        rows.append([sid, 'ok', len(secs), sum(len(s['t']) for s in secs), '／'.join(s['h'] for s in secs), os.path.basename(path)])
        stat['ok'] += 1
    else:
        rows.append([sid, status.get(str(sid), '未處理'), 0, 0, '', os.path.basename(path)])
        stat[status.get(str(sid), '未處理')] += 1
with open(os.path.join(ROOT, 'data', 'fulltext_report.csv'), 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f); w.writerow(['sid', '結果', '章節數', '網站字數', '章節', '檔名']); w.writerows(sorted(rows))
print('FINISHED', dict(stat))
