import json, requests, time
from concurrent.futures import ThreadPoolExecutor
R = {}
for l in open('scan.jsonl'): r = json.loads(l); R[r['sid']] = r
jobs = [(r['sid'], r['檔案連結'][0]) for r in R.values() if r.get('檔案連結')]
def head(j):
    sid, url = j
    for i in range(4):
        try:
            h = requests.head(url, timeout=30, allow_redirects=True, headers={'User-Agent': 'Mozilla/5.0'})
            return sid, h.headers.get('content-disposition', '').split('filename=')[-1]
        except Exception: time.sleep(3 * (i + 1))
    return sid, None
with ThreadPoolExecutor(4) as ex: out = dict(ex.map(head, jobs))
json.dump(out, open('filenames.json', 'w'))
print('FINISHED', len(out), sum(v is None for v in out.values()))
