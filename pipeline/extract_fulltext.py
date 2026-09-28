"""從 PDF原始檔 抽出第 56～65 屆作品的章節文字，給研究包使用。

只保留「研究目的、設備器材、研究方法、結果、討論、結論」；封面、目錄、文獻探討、參考資料、心得不收。
輸出：
  data/fulltext/<sid>.json        完整章節（本機保存）
  site/data/fulltext/<sid>.json   網站用（每件上限 MAX_CHARS 字）
  data/fulltext_report.csv        每件的抽取結果，方便檢查

用法：python3 pipeline/extract_fulltext.py [--limit N]
"""
import csv, json, math, os, re, sys, collections
from multiprocessing import Pool

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'PDF原始檔')
OUT_FULL = os.path.join(ROOT, 'data', 'fulltext')
OUT_SITE = os.path.join(ROOT, 'site', 'data', 'fulltext')
MAX_CHARS = 12000
# 第 55 屆部分 PDF 字型編碼錯誤時常見的錯字；出現 5 次以上就套用 font_fix.json 對照表
GARBLED = re.compile('[ˣǵ烉炻ˤᶳᶲㆹ冯⃱屛]')
# 另一種錯法：中文被換成阿拉伯、印度等文字的字母（例：ࣽ৖໒ۈаٰǴ）
WEIRD = re.compile('[\u0400-\u04ff\u0590-\u1cff\u01c0-\u024f]')


_cf = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'char_freq.json')
CHAR_FREQ = json.load(open(_cf, encoding='utf-8')) if os.path.exists(_cf) else {}
COMMON = set(CHAR_FREQ)
_FREQ_TOTAL = sum(CHAR_FREQ.values()) or 1
_RARE = math.log(0.5 / _FREQ_TOTAL)
LOGF = {ch: math.log(n / _FREQ_TOTAL) for ch, n in CHAR_FREQ.items()}


def big5_glyph(code, off):
    """部分 PDF（多在第 52 屆）抽出的是字型裡的字形序號，依 Big5 順序排列。
    中文區：Big5 序號 = 字碼 − off；符號區再多位移 63（字型跳過 Big5 未使用的 A3C0–A3FE）。
    例：off=436 時「中」（Big5 A4A4，序號 537）抽成 U+03CD。"""
    g = code - off - 63
    if g < 0:
        a = code - off + 193            # 有些字型連英數字也是字形序號（例：「300」抽成 ˆ˃˃）
        return chr(a) if 32 <= a < 127 else None
    idx = g if g < 408 else code - off
    row, col = divmod(idx, 157)
    if row > 0x58:
        return None
    lead, trail = 0xA1 + row, (0x40 + col if col < 63 else 0xA1 + col - 63)
    try:
        return bytes([lead, trail]).decode('cp950')
    except UnicodeDecodeError:
        return None


def decode_glyphs(page):
    """一頁文字若大多是字形序號，找出能還原最多常用中文字的位移後換回中文；否則原樣傳回"""
    body = [ch for ch in page if ord(ch) > 0x7f and not ch.isspace()]
    if len(body) < 20 or sum(0x100 <= ord(ch) < 0x2000 for ch in body) / len(body) < 0.2 or not COMMON:
        return page, False
    freq = collections.Counter(body).most_common(40)          # 最常出現的字（多半是「的」「，」）最能判斷位移
    total = sum(n for _, n in freq)
    # 以「還原後的字在一般摘要中的出現頻率」評分：真正的位移會還原出「的」「，」這類極常見的字
    score = lambda off: sum(n * LOGF.get(big5_glyph(ord(ch), off) or '', _RARE) for ch, n in freq)
    best_off = max(range(0, 3000), key=score)
    hit = sum(n for ch, n in freq if (big5_glyph(ord(ch), best_off) or '') in COMMON)
    if hit / total < 0.6:
        return page, False
    return ''.join((big5_glyph(ord(ch), best_off) or ch) if ord(ch) > 0x7f else ch for ch in page), True


def fix_pages(pages):
    """字形序號逐頁判斷（同一份 PDF 可能混用字型）；第一種錯字則看整份 PDF 未還原的頁面一起判斷"""
    out, plain = [], []
    for p in pages:
        p, done = decode_glyphs(p)
        out.append(p)
        if not done:
            plain.append(len(out) - 1)
    if is_garbled('\n'.join(out[i] for i in plain)):
        for i in plain:
            out[i] = out[i].translate(FONT_FIX)
    return '\n'.join(out)


def is_garbled(text):
    return len(GARBLED.findall(text)) >= 5 or len(WEIRD.findall(text)) >= 30
_ff = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'font_fix.json')
FONT_FIX = str.maketrans(json.load(open(_ff, encoding='utf-8'))) if os.path.exists(_ff) else {}

NUM = '壹貳參参肆伍陸柒捌玖拾'
# 三種章節編號寫法：壹貳參、一二三、沒有編號（整行就是章節名稱）
HEADS = [
    re.compile(r'^\s*([壹貳參参肆伍陸柒捌玖拾]{1,3})\s*[、﹑.．]\s*(.{1,30}?)\s*$', re.M),
    re.compile(r'^\s*([一二三四五六七八九十]{1,3})\s*[、﹑.．]\s*(.{1,30}?)\s*$', re.M),
    re.compile(r'^\s*()((?:研究|實驗)?(?:動機|目的|設備|器材|過程|方法|結果|討論|結論)[^\n]{0,12}?)\s*$', re.M),
]
KEEP = [('目的', '研究目的'), ('問題', '研究目的'), ('設備', '研究設備及器材'), ('器材', '研究設備及器材'), ('儀器', '研究設備及器材'),
        ('材料', '研究設備及器材'), ('方法', '研究過程或方法'), ('過程', '研究過程或方法'), ('架構', '研究過程或方法'),
        ('結果', '研究結果'), ('討論', '討論'), ('結論', '結論'), ('應用', '結論')]
DROP = ('參考', '文獻', '附錄', '心得', '感謝', '致謝', '展望', '動機', '前言', '摘要', '緒論', '理論', '探討')


CRASHERS = {'第64屆_國小組_生活與應用科學(一)科_未列獎項_082809'}   # 會讓 PyMuPDF 當掉的檔案


def extract_text(path):
    try:
        if os.environ.get('FT_BACKEND') == 'pypdf' or any(c in path for c in CRASHERS):
            raise ImportError
        import pymupdf
        with pymupdf.open(path) as doc:
            return fix_pages([page.get_text() for page in doc])
    except ImportError:
        import pypdf
        return fix_pages([p.extract_text() or '' for p in pypdf.PdfReader(path).pages])


def classify(title):
    t = re.sub(r'\s+', '', title)
    # 「研究結果與討論」這類合併章節，以第一個符合的類別為準；先檢查要保留的
    for k, name in KEEP:
        if k in t:
            return name
    if any(k in t for k in DROP):
        return None
    return None


def clean(s):
    s = re.sub(r'^\s*(第\s*\d+\s*頁|[-–—]?\s*\d{1,3}\s*[-–—]?)\s*$', '', s, flags=re.M)   # 頁碼
    s = re.sub(r'(\d)\s*\n?\s*o\s*\n?\s*C\b', r'\1°C', s)   # 上標被拆開的 °C
    s = re.sub(r'[ \t　]+', ' ', s)
    # 中文之間的換行多半是排版斷行，直接接起來；保留段落空行
    s = re.sub(r'(?<=[一-鿿，、；：（）「」])\n(?=[一-鿿，、；：（）「」])', '', s)
    s = re.sub(r'\n{3,}', '\n\n', s)
    return s.strip()


ORDER = {c: i for i, c in enumerate('壹貳參肆伍陸柒捌玖拾')} | {'参': 2} | {c: i for i, c in enumerate('一二三四五六七八九十')}


def numval(num):
    return ORDER.get(num[-1], -1) + (10 if len(num) > 1 else 0) if num else -1


def sections_from(text, heads):
    # 章節編號回頭重來（例如附了縣市賽版本或後續研究）就視為另一份文件，在這裡截止
    last = -1
    for i, h in enumerate(heads):
        v = numval(h[2])
        if v != -1 and v <= last:
            heads = heads[:i]
            break
        last = max(last, v)
    secs = []
    for i, (st, e, num, title) in enumerate(heads):
        end = heads[i + 1][0] if i + 1 < len(heads) else len(text)
        name = classify(title)
        if name:
            h = (f'{num}、' if num else '') + re.sub(r'\s+', '', title).rstrip('：:')
            secs.append({'h': h, 'k': name, 'text': clean(text[e:end])})
    secs = [x for x in secs if len(x['text']) > 20]
    # 目錄沒有頁碼時，同名章節會出現兩次；保留內容較長的那一次
    keep = {}
    for x in secs:
        if x['h'] not in keep or len(x['text']) > len(keep[x['h']]['text']):
            keep[x['h']] = x
    return [x for x in secs if keep[x['h']] is x]


def split_sections(text):
    """試過每種編號寫法與每個可能的正文起點（跳過目錄），選抽出內容最多、且涵蓋最多種章節的結果。"""
    best, best_score = [], 0
    for pat in HEADS:
        heads = []
        for m in pat.finditer(text):
            title = m.group(2)
            if re.search(r'(\.{3,}|…{2,}|\s\d{1,3})$', title):   # 目錄行：後面接頁碼
                continue
            heads.append((m.start(), m.end(), m.group(1), title))
        if not heads:
            continue
        starts = [i for i, h in enumerate(heads) if classify(h[3])] or [0]
        for i in starts[:12]:
            secs = sections_from(text, heads[i:])
            kinds = {x['k'] for x in secs}
            score = len(kinds) * 10000 + min(sum(len(x['text']) for x in secs), 60000)
            if score > best_score and len(kinds) >= 2:
                best, best_score = secs, score
        if best:
            break          # 有編號的寫法優先，找到就不用退到下一種
    return best


def work(job):
    sid, path = job
    try:
        text = extract_text(path)
    except Exception as err:
        return sid, None, f'讀取失敗：{err}'
    if len(re.findall(r'[一-鿿]', text)) < 300:
        return sid, None, '幾乎沒有文字（可能是掃描檔）'
    secs = split_sections(text)
    if not secs:
        return sid, None, '找不到章節標題'
    return sid, secs, 'ok'


def trim(secs, limit):
    total = sum(len(s['text']) for s in secs)
    if total <= limit:
        return secs, False
    # 依比例截短每一節，讓每節都保留開頭
    out = []
    for s in secs:
        n = max(300, int(len(s['text']) * limit / total))
        out.append({**s, 'text': s['text'][:n] + ('…（節錄）' if len(s['text']) > n else '')})
    return out, True


def find_jobs():
    """PDF原始檔 裡每份 PDF 對應到的作品：先用「屆次＋作品編號」，資料庫缺編號時改用作品名稱。"""
    import unicodedata
    nfc = lambda s: unicodedata.normalize('NFC', s)
    nt = lambda t: re.sub(r'[\W_]', '', t)
    works = json.load(open(os.path.join(ROOT, 'data', 'works.json'), encoding='utf-8'))
    by_code = {(w['edition_no'], w['code']): w for w in works if w['code']}
    by_title = {(w['edition_no'], nt(w['title'])): w for w in works if w['src'] == '全國' and w['type'] == '作品'}
    ov = json.load(open(os.path.join(ROOT, 'pipeline', 'pdf_overrides.json'), encoding='utf-8'))
    overrides = {nfc(k): v for k, v in ov.items() if not k.startswith('_')}
    by_id = {w['id']: w for w in works}
    jobs = {}
    for d, _, fs in os.walk(SRC):
        for f in fs:
            m = re.match(r'第(\d+)屆_.*?_(\d{6})_(.+)\.pdf$', nfc(f))
            if not m or f.startswith('._'):
                continue
            ed = int(m.group(1))
            w = by_id.get(overrides.get(nfc(f))) or by_code.get((ed, m.group(2))) or by_title.get((ed, nt(m.group(3))))
            if w:
                jobs[w['id']] = (w['id'], os.path.join(d, f), ed)
    return sorted(jobs.values())


if __name__ == '__main__':
    jobs = find_jobs()
    if '--editions' in sys.argv:
        eds = {int(x) for x in sys.argv[sys.argv.index('--editions') + 1].split(',')}
        jobs = [j for j in jobs if j[2] in eds]
    jobs = [(sid, path) for sid, path, _ in jobs]
    print('處理', len(jobs), '份', flush=True)
    if '--limit' in sys.argv:
        jobs = jobs[:int(sys.argv[sys.argv.index('--limit') + 1])]
    os.makedirs(OUT_FULL, exist_ok=True)
    os.makedirs(OUT_SITE, exist_ok=True)
    stat = collections.Counter()
    kinds = collections.Counter()
    rows = []
    with Pool(4) as pool:
        for n, (sid, secs, status) in enumerate(pool.imap_unordered(work, jobs, chunksize=4), 1):
            stat[status.split('：')[0]] += 1
            chars = 0
            if secs:
                json.dump(secs, open(os.path.join(OUT_FULL, f'{sid}.json'), 'w', encoding='utf-8'), ensure_ascii=False)
                short, cut = trim(secs, MAX_CHARS)
                json.dump([{'h': s['h'], 't': s['text']} for s in short],
                          open(os.path.join(OUT_SITE, f'{sid}.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
                chars = sum(len(s['text']) for s in short)
                kinds.update({s['k'] for s in secs})
                stat['截短'] += cut
            rows.append([sid, status, len(secs or []), chars, '／'.join(s['h'] for s in secs or [])])
            if n % 200 == 0:
                print('progress', n, '/', len(jobs), flush=True)
    with open(os.path.join(ROOT, 'data', 'fulltext_report.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['sid', '結果', '章節數', '網站字數', '章節'])
        w.writerows(sorted(rows))
    ok = [r for r in rows if r[1] == 'ok']
    print('FINISHED', dict(stat))
    print('章節類別出現次數', dict(kinds))
    if ok:
        print('網站字數 平均', sum(r[3] for r in ok) // len(ok))
