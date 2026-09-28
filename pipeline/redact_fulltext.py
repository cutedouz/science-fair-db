"""從 data/fulltext（完整版節錄）重新產生網站版 site/data/fulltext：
截短到每件上限字數、把作者姓名換成〔作者〕、移除學生程式碼裡的 API 金鑰或存取權杖。
網站不收錄作者姓名。在 extract_fulltext.py / finish_fulltext.py 之後執行；重複執行結果相同。

取代一律在解析後的文字上進行，不直接改 JSON 原始文字（否則可能破壞跳脫字元，產生無法解析的檔案）。
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_fulltext import ROOT, OUT_FULL, OUT_SITE, MAX_CHARS, trim

KEYLIKE = re.compile(r'(?:sk-|AIza|ghp_|gho_|xox[abp]-)[A-Za-z0-9_\-]{16,}'
                     r'|(?<![A-Za-z0-9_\-])(?=[A-Za-z0-9_\-]{40,})(?=\S*[a-z])(?=\S*[A-Z])(?=\S*\d)[A-Za-z0-9_\-]{40,}')

authors = {}
for line in open(os.path.join(ROOT, 'data', 'raw', 'scan.jsonl'), encoding='utf-8'):
    r = json.loads(line)
    if r.get('作者'):
        authors[r['sid']] = sorted({x.strip() for x in re.split(r'[;；、,，]', r['作者']) if len(x.strip()) >= 2}, key=len, reverse=True)

os.makedirs(OUT_SITE, exist_ok=True)
built = named = keys = 0
wanted = set()
for f in os.listdir(OUT_FULL):
    if not f.endswith('.json') or f.startswith('._'):
        continue
    sid = int(f[:-5])
    wanted.add(f)
    secs = json.load(open(os.path.join(OUT_FULL, f), encoding='utf-8'))
    short, _ = trim(secs, MAX_CHARS)
    out, hit_name = [], False
    for s in short:
        t = s['text']
        for n in authors.get(sid, []):
            if n in t:
                t = t.replace(n, '〔作者〕'); hit_name = True
        t, k = KEYLIKE.subn('〔已移除疑似金鑰〕', t)
        keys += k
        out.append({'h': s['h'].rstrip('!！ '), 't': t})
    named += hit_name
    json.dump(out, open(os.path.join(OUT_SITE, f), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    built += 1
# 完整版已不存在的舊網站檔一併移除
stale = [f for f in os.listdir(OUT_SITE) if f.endswith('.json') and not f.startswith('._') and f not in wanted]
for f in stale:
    os.remove(os.path.join(OUT_SITE, f))
# 最後檢查每個網站檔都能解析
for f in wanted:
    json.load(open(os.path.join(OUT_SITE, f), encoding='utf-8'))
print(f'網站版節錄 {built} 件；遮蔽作者姓名 {named} 件；移除疑似金鑰 {keys} 處；刪除過時檔 {len(stale)} 件；全部檔案皆可解析')
