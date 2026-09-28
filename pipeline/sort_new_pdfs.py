"""把新下載的 PDF 資料夾併入 PDF原始檔 與 筆記本分類（每個資料夾 ≤ 300 份）。

用法：python3 pipeline/sort_new_pdfs.py <下載資料夾> [--dry-run]
- 依「屆次＋作品編號」、作品名稱、pipeline/pdf_overrides.json 對應到資料庫作品
- 學習階段以檔名上的官方組別為準
- 資料夾放不下時：已依屆次拆分的，新開「第X-Y屆」資料夾；尚未拆分的，原資料夾加上屆次範圍後再新開一個
"""
import json, os, re, shutil, sys, collections, unicodedata
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'PDF原始檔', '科展資料庫', 'PDF')
DST = os.path.join(ROOT, '筆記本分類')
LIMIT = 300
GROUP_STAGE = {'國小組': '國小', '國中組': '國中', '高中組': '高中職', '高職組': '高中職', '高級中等學校組': '高中職'}
nfc = lambda s: unicodedata.normalize('NFC', s)
nt = lambda t: re.sub(r'[\W_]', '', t)


def match_pdf(fname, works, by_code, by_title, overrides):
    """回傳 (屆次, 組別, 作品編號, 作品) ；對不上時作品為 None"""
    m = re.match(r'第(\d+)屆_([^_]+)_.*?_(\d{6})_(.+)\.pdf$', nfc(fname))
    if not m:
        return None, None, None, None
    ed, grp, code, title = int(m.group(1)), m.group(2), m.group(3), m.group(4)
    w = works.get(overrides.get(nfc(fname))) or by_code.get((ed, code)) or by_title.get((ed, nt(title)))
    if not w and '待核對' not in title:
        # 近似名稱：同一屆中相似度 ≥ 0.85，且明顯高於第二像的作品
        import difflib
        cands = sorted(((difflib.SequenceMatcher(None, nt(title), k[1]).ratio(), v) for k, v in by_title.items() if k[0] == ed),
                       key=lambda x: -x[0])[:2]
        if cands and cands[0][0] >= 0.85 and (len(cands) < 2 or cands[0][0] - cands[1][0] >= 0.1):
            w = cands[0][1]
    return ed, grp, code, w


def load_index():
    works = {w['id']: w for w in json.load(open(os.path.join(ROOT, 'data', 'works.json'), encoding='utf-8'))}
    by_code = {(w['edition_no'], w['code']): w for w in works.values() if w['code']}
    by_title = {(w['edition_no'], nt(w['title'])): w for w in works.values() if w['src'] == '全國' and w['type'] == '作品'}
    ov = json.load(open(os.path.join(ROOT, 'pipeline', 'pdf_overrides.json'), encoding='utf-8'))
    overrides = {nfc(k): v for k, v in ov.items() if not k.startswith('_')}
    return works, by_code, by_title, overrides


def folder_editions(path):
    eds = set()
    for f in os.listdir(path):
        m = re.match(r'第(\d+)屆_', nfc(f))
        if m and not f.startswith('._'):
            eds.add(int(m.group(1)))
    return eds


def count(path):
    return len([f for f in os.listdir(path) if f.lower().endswith('.pdf') and not f.startswith('._')])


if __name__ == '__main__':
    src = os.path.join(ROOT, sys.argv[1])
    dry = '--dry-run' in sys.argv
    works, by_code, by_title, overrides = load_index()
    plan, bad, dup = [], [], []
    for d, _, fs in os.walk(src):
        for f in fs:
            if f.startswith('._') or not f.lower().endswith('.pdf'):
                continue
            ed, grp, code, w = match_pdf(f, works, by_code, by_title, overrides)
            if ed and os.path.exists(os.path.join(RAW, f'第{ed}屆', f)):
                dup.append(f); continue          # 已經分類過的檔案，略過
            if not w:
                bad.append(f); continue
            stage = GROUP_STAGE.get(grp) or w['stage']
            plan.append((os.path.join(d, f), ed, f"{'、'.join(w['domains']) or '未分類'}_{stage}"))
    if dup:
        print('已分類過、略過', len(dup), '份')
    if bad:
        print(f'對不上的檔案 {len(bad)} 份（留在原資料夾；可加進 pipeline/pdf_overrides.json 後重跑）')
        json.dump(sorted(bad), open(os.path.join(ROOT, 'data', 'pdf_unmatched.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
        if '--skip-unmatched' not in sys.argv:
            sys.exit(1)
    groups = collections.defaultdict(list)
    for p in plan:
        groups[p[2]].append(p)
    existing = [d for d in os.listdir(DST) if not d.startswith('._') and os.path.isdir(os.path.join(DST, d))]
    # 少於 5 份、又沒有現成資料夾的零星組別（多為跨領域的舊科別），併入「其他_學習階段」
    for base in [b for b, items in groups.items() if len(items) < 5]:
        if not any(d == base or d.startswith(base + '_第') for d in existing):
            other = '其他_' + base.rsplit('_', 1)[1]
            groups[other] = groups.get(other, []) + [(x[0], x[1], other) for x in groups.pop(base)]
    plan = [x for items in groups.values() for x in items]
    target, renames = {}, []
    for base, items in groups.items():
        new_eds = sorted({x[1] for x in items})
        lo, hi = new_eds[0], new_eds[-1]
        ranged = sorted((d for d in existing if re.fullmatch(re.escape(base) + r'_第(\d+)-(\d+)屆', d)),
                        key=lambda d: int(re.search(r'第(\d+)-', d).group(1)))
        if ranged:
            first = ranged[0]
            if count(os.path.join(DST, first)) + len(items) <= LIMIT:
                a, b = map(int, re.search(r'第(\d+)-(\d+)屆', first).groups())
                new_name = f'{base}_第{min(a, lo)}-{max(b, hi)}屆'
                if new_name != first:
                    renames.append((first, new_name))
                target[base] = new_name
            else:
                target[base] = f'{base}_第{lo}-{hi}屆'
        elif base in existing:
            if count(os.path.join(DST, base)) + len(items) <= LIMIT:
                target[base] = base
            else:
                eds = folder_editions(os.path.join(DST, base))
                renames.append((base, f'{base}_第{min(eds)}-{max(eds)}屆'))
                target[base] = f'{base}_第{lo}-{hi}屆'
        else:
            target[base] = base
    for a, b in renames:
        print('改名', a, '→', b)
    for base, items in sorted(groups.items()):
        print(f'{target[base]:32s} +{len(items)}')
    if dry:
        sys.exit(0)
    for a, b in renames:
        os.rename(os.path.join(DST, a), os.path.join(DST, b))
    for path, ed, base in plan:
        os.makedirs(os.path.join(RAW, f'第{ed}屆'), exist_ok=True)
        raw_path = os.path.join(RAW, f'第{ed}屆', os.path.basename(path))
        shutil.move(path, raw_path)
        os.makedirs(os.path.join(DST, target[base]), exist_ok=True)
        shutil.copyfile(raw_path, os.path.join(DST, target[base], os.path.basename(path)))
    over = {d: count(os.path.join(DST, d)) for d in os.listdir(DST) if not d.startswith('._')}
    print('FINISHED', len(plan), '份；資料夾', len(over), '個；最大', max(over.values()))
