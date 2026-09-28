import json, os, sys, threading, scrape
from concurrent.futures import ThreadPoolExecutor
LO, HI = int(sys.argv[1]), int(sys.argv[2])
OUT = 'scan.jsonl'
done = set()
if os.path.exists(OUT):
    for l in open(OUT, encoding='utf-8'): done.add(json.loads(l)['sid'])
lock = threading.Lock(); f = open(OUT, 'a', encoding='utf-8'); n = [0]
def job(sid):
    try: d = scrape.detail(('22097', str(sid)))
    except Exception as e: d = {'sid': sid, 'error': str(e)}
    with lock:
        f.write(json.dumps(d, ensure_ascii=False) + '\n'); f.flush(); n[0] += 1
        if n[0] % 1000 == 0: print('progress', n[0], 'sid', sid, flush=True)
with ThreadPoolExecutor(6) as ex:
    list(ex.map(job, [s for s in range(LO, HI) if s not in done]))
print('FINISHED', n[0], flush=True)
