"""把網站用節錄（site/data/fulltext）裡出現的作者姓名換成〔作者〕。網站不收錄作者姓名。
在 extract_fulltext.py / finish_fulltext.py 之後執行；重複執行也不會出錯。
"""
import json, os, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, 'site', 'data', 'fulltext')
authors = {}
for line in open(os.path.join(ROOT, 'data', 'raw', 'scan.jsonl'), encoding='utf-8'):
    r = json.loads(line)
    if r.get('作者'):
        authors[r['sid']] = sorted({x.strip() for x in re.split(r'[;；、,，]', r['作者']) if len(x.strip()) >= 2}, key=len, reverse=True)
# 學生程式碼裡偶爾會貼上 API 金鑰或存取權杖；網站不應再散布
KEYLIKE = re.compile(r'(?:sk-|AIza|ghp_|gho_|xox[abp]-)[A-Za-z0-9_\-]{16,}|(?<![A-Za-z0-9_\-])(?=[A-Za-z0-9_\-]{40,})(?=[^\s"]*[a-z])(?=[^\s"]*[A-Z])(?=[^\s"]*\d)[A-Za-z0-9_\-]{40,}')
keys = 0
changed = 0
for f in os.listdir(SITE):
    if f.endswith('.json') and not f.startswith('._'):
        path = os.path.join(SITE, f)
        raw = open(path, encoding='utf-8').read()
        new, n = KEYLIKE.subn('〔已移除疑似金鑰〕', raw)
        if n:
            open(path, 'w', encoding='utf-8').write(new)
            keys += n
            print('  移除疑似金鑰', f, n, '處')
for f in os.listdir(SITE):
    if not f.endswith('.json') or f.startswith('._'):
        continue
    names = authors.get(int(f[:-5]))
    if not names:
        continue
    path = os.path.join(SITE, f)
    raw = open(path, encoding='utf-8').read()
    new = raw
    for n in names:
        new = new.replace(n, '〔作者〕')
    if new != raw:
        open(path, 'w', encoding='utf-8').write(new)
        changed += 1
print('已遮蔽作者姓名的節錄', changed, '件；移除疑似金鑰', keys, '處')
