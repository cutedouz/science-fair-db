"""第 55 屆部分 PDF 的字型編碼錯誤（例：「溶解」抽成「愞解」、「，」抽成「炻」）。
比對 PDF 內的摘要與科教館網站上的正確摘要，學出「錯字 → 正確字」對照表，存成 pipeline/font_fix.json。
"""
import json, os, re, sys, collections, difflib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_fulltext import ROOT, find_jobs, extract_text, GARBLED

works = {w['id']: w for w in json.load(open(os.path.join(ROOT, 'data', 'works.json'), encoding='utf-8'))}
pairs = collections.defaultdict(collections.Counter)
used = 0
for sid, path, ed in find_jobs():
    if ed != 55:
        continue
    text = re.sub(r'\s+', '', extract_text(path))
    if len(GARBLED.findall(text)) < 5:
        continue
    good = re.sub(r'\s+', '', works[sid]['abstract'])
    if len(good) < 80:
        continue
    # 在 PDF 前段找出和網站摘要最像的一段（字數大致相同，因為錯字是一對一替換）
    head = text[:12000]
    best, best_r = None, 0
    for start in range(0, max(1, len(head) - len(good)), 40):
        win = head[start:start + len(good) + 60]
        r = difflib.SequenceMatcher(None, win, good, autojunk=False).quick_ratio()
        if r > best_r:
            best, best_r = win, r
    if not best or best_r < 0.5:
        continue
    used += 1
    for op, a1, a2, b1, b2 in difflib.SequenceMatcher(None, best, good, autojunk=False).get_opcodes():
        if op == 'replace' and a2 - a1 == b2 - b1 <= 3:
            for x, y in zip(best[a1:a2], good[b1:b2]):
                if x != y:
                    pairs[x][y] += 1
# 正常文章裡常見的字不可能是錯字（例如「為」「會」）；只收在其他屆摘要中罕見的字
normal = collections.Counter(ch for w in works.values() if w['edition_no'] != 55 for ch in w['abstract'])
table = {}
for x, c in pairs.items():
    y, n = c.most_common(1)[0]
    if x.isascii() or normal[x] >= 30:
        continue
    if n >= 2 and n / sum(c.values()) >= 0.75:
        table[x] = y
json.dump(table, open(os.path.join(ROOT, 'pipeline', 'font_fix.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0, sort_keys=True)
print('用來學習的作品', used, '件；學到', len(table), '個字的對照')
print(' '.join(f'{k}→{v}' for k, v in sorted(table.items(), key=lambda kv: -sum(pairs[kv[0]].values()))[:60]))
