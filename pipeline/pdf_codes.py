"""從 PDF原始檔 的檔名取出官方作品編號與組別，存成 data/raw/pdf_codes.json（sid → 編號、組別）。
clean.py 會用它補上資料庫缺少的作品編號，學習階段因此改用官方資料。
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sort_new_pdfs import ROOT, RAW, load_index, match_pdf
works, by_code, by_title, overrides = load_index()
out, bad = {}, []
for d, _, fs in os.walk(RAW):
    for f in fs:
        if f.startswith('._') or not f.lower().endswith('.pdf'):
            continue
        ed, grp, code, w = match_pdf(f, works, by_code, by_title, overrides)
        if w:
            out[str(w['id'])] = {'code': code, 'group': grp, 'file': f}
        else:
            bad.append(f)
json.dump(out, open(os.path.join(ROOT, 'data', 'raw', 'pdf_codes.json'), 'w', encoding='utf-8'), ensure_ascii=False)
print('取得作品編號', len(out), '件；對不上', len(bad))
for b in bad[:10]:
    print('  ', b)
