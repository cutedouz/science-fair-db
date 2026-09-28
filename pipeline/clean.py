"""把 data/raw 的原始爬蟲資料整理成網站用的 data/works.json。

用法：python3 pipeline/clean.py
"""
import csv, json, re, os, collections
from stage import stage_from_school, infer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'data', 'raw')
OUT = os.path.join(ROOT, 'data')

# ---------- 讀原始資料 ----------
rows = {}
for line in open(os.path.join(RAW, 'scan.jsonl'), encoding='utf-8'):
    r = json.loads(line)
    if r.get('作品名稱'):
        rows[r['sid']] = r
# sid 2850 在官網缺類別，實為 2004 年國際科展
if 2850 in rows and not rows[2850].get('科展類別'):
    rows[2850]['科展類別'] = '臺灣國際科展作品'

groups = {int(k): v[0] for k, v in json.load(open(os.path.join(RAW, 'groups.json'), encoding='utf-8')).items()}
fn_path = os.path.join(RAW, 'filenames.json')
filenames = {int(k): v for k, v in json.load(open(fn_path)).items()} if os.path.exists(fn_path) else {}

subjects = {}
for r in csv.DictReader(open(os.path.join(ROOT, 'pipeline', 'subjects.csv'), encoding='utf-8')):
    subjects[(r['來源'], r['原始科別'])] = [d for d in r['標準領域'].split('、') if d]

# ---------- 小工具 ----------
def txt(v):
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', (v or '').replace('\\r', '')).strip()

def split_people(v):
    return [x.strip() for x in re.split(r'[;；、,，]', txt(v)) if x.strip()]

def split_keywords(v):
    v = txt(v)
    if not v:
        return []
    if re.search(r'[、,，;；/]', v):
        parts = re.split(r'[、,，;；/]', v)
    elif re.search(r'[一-鿿]', v):
        parts = v.split()          # 中文關鍵字以空白分隔
    else:
        parts = [v]                # 英文片語保留空白
    return list(dict.fromkeys(p.strip(' .。') for p in parts if p.strip(' .。')))

RANKS = ['特別獎第一名', '特別獎第二名', '特別獎第三名', '第一名', '第二名', '第三名', '第四名', '大會獎佳作', '佳作',
         '一等獎', '二等獎', '三等獎', '四等獎', '成就證書', '特別獎', '未得獎作品', '無']
# 官方資料的錯字與同義寫法
SPECIAL_FIX = {'團體合作獎': '團隊合作獎', '團隊會作獎': '團隊合作獎'}
def parse_award(v):
    v = txt(v)
    rank, special, rep = None, [], []
    parts = []
    for chunk in re.split(r'[;；、]', v):
        if '代表' in chunk or re.search(r'展覽會|博覽會', chunk):
            rep.append(re.sub(r'\s+', '', chunk)); continue
        parts += chunk.split()
    for part in parts:
        part = part.strip()
        if not part:
            continue
        hit = next((k for k in RANKS if part == k), None)
        if hit:
            if hit in ('未得獎作品', '無'):
                rank = rank or '未得獎'
            elif not rank or rank == '未得獎':
                rank = hit
        else:
            part = part.replace('(鄉土)教材獎', '最佳鄉土教材獎').replace('最佳最佳', '最佳')
            special.append(SPECIAL_FIX.get(part, part))
    return rank, list(dict.fromkeys(special)), rep

def year_of(ed):
    m = re.search(r'民國\s*(\d+)', ed)
    if m:
        return int(m.group(1)) + 1911
    m = re.search(r'(\d{4})', ed)
    return int(m.group(1)) if m else None

def edition_no(ed):
    m = re.search(r'第\s*(\d+)\s*屆', ed)
    return int(m.group(1)) if m else None

# 2010 年縣市改制前的名稱 → 現制
CITY_FIX = {'台北縣': '新北市', '臺北縣': '新北市', '桃園縣': '桃園市', '台中縣': '臺中市', '臺中縣': '臺中市',
            '台南縣': '臺南市', '臺南縣': '臺南市', '高雄縣': '高雄市'}
CITIES = ['臺北市', '新北市', '桃園市', '臺中市', '臺南市', '高雄市', '基隆市', '新竹市', '嘉義市', '新竹縣', '苗栗縣',
          '彰化縣', '南投縣', '雲林縣', '嘉義縣', '屏東縣', '宜蘭縣', '花蓮縣', '臺東縣', '澎湖縣', '金門縣', '連江縣']
# 校名沒寫縣市時，用鄉鎮或知名校名判斷
TOWNS = [('臺灣師範大學', '臺北市'), ('臺北教育大學', '臺北市'), ('高雄師範大學', '高雄市'), ('鳳山', '高雄市'), ('鳳新', '高雄市'),
         ('岡山', '高雄市'), ('旗美', '高雄市'), ('羅東', '宜蘭縣'), ('蘭陽', '宜蘭縣'), ('武陵', '桃園市'), ('中壢', '桃園市'),
         ('潮州', '屏東縣'), ('板橋', '新北市'), ('新莊', '新北市'), ('三重', '新北市'), ('民雄', '嘉義縣'), ('員林', '彰化縣'),
         ('秀水', '彰化縣'), ('科學工業園區', '新竹市'), ('中科實驗', '臺中市'), ('東華大學', '花蓮縣'), ('竹北', '新竹縣'),
         ('斗六', '雲林縣'), ('虎尾', '雲林縣'), ('北港', '雲林縣'), ('玉里', '花蓮縣'), ('馬公', '澎湖縣'), ('金門', '金門縣'),
         ('澎湖', '澎湖縣'), ('馬祖', '連江縣'), ('豐原', '臺中市'), ('大甲', '臺中市'), ('竹南', '苗栗縣'), ('埔里', '南投縣')]
SHORT = [(c[:2], c) for c in ['臺北市', '新北市', '桃園市', '臺中市', '臺南市', '高雄市', '基隆市', '新竹市', '嘉義市',
         '苗栗縣', '彰化縣', '南投縣', '雲林縣', '屏東縣', '宜蘭縣', '花蓮縣', '臺東縣']]
def city_of(school):
    s = txt(school).replace('台', '臺')
    for old, new in CITY_FIX.items():
        if old.replace('台', '臺') in s:
            return new
    hits = [(s.find(c), c) for c in CITIES if c in s]
    if hits:
        return min(hits)[1]
    for town, c in TOWNS:
        if town in s:
            return c
    hits = [(s.find(k), c) for k, c in SHORT if k in s]
    return min(hits)[1] if hits else None

GROUP_STAGE = {'國小組': '國小', '國中組': '國中', '高級中等學校組': '高中職'}
CODE_STAGE = {'03': '國中', '04': '高中', '05': '高中職', '08': '國小', '09': '高職'}
def code_of(sid):
    m = re.search(r'(?:nphssf|NPHSF)\d{4}-(\d{6})', filenames.get(sid) or '')
    return m.group(1) if m else None

def norm_title(t):
    return re.sub(r'[\W_]', '', t).lower()

# ---------- 主流程 ----------
works = []
for sid, r in sorted(rows.items()):
    src = '全國' if '全國' in (r.get('科展類別') or '') else '國際'
    title = txt(r['作品名稱'])
    ed = re.sub(r'\s+', '', txt(r.get('屆次')))
    subj = txt(r.get('科別'))
    rank, special, rep = parse_award(r.get('得獎情形'))
    w = {
        'id': sid,
        'src': src,
        'type': '評語' if src == '全國' and '評語' in title else '作品',
        'title': title,
        'edition': ed,
        'edition_no': edition_no(ed),
        'year': year_of(ed),
        'subject': subj,
        'domains': subjects.get((src, subj), []),
        'award_raw': txt(r.get('得獎情形')),
        'rank': rank,
        'special': special,
        'rep': rep,
        'school': txt(r.get('學校名稱')),
        'city': city_of(r.get('學校名稱')),
        'teachers': split_people(r.get('指導老師')),
        'keywords': split_keywords(r.get('關鍵字')),
        'abstract': txt(r.get('摘要或動機')),
        'pdf': (r.get('檔案連結') or [None])[0],
        'code': code_of(sid),
        'url': f'https://www.ntsec.edu.tw/science/detail.aspx?a={"21" if src == "全國" else "90"}&sid={sid}',
    }
    works.append(w)

# 學習階段：檔名作品編號 > 官網組別列表 > 科別內含組別 > 推測
by_ed = collections.defaultdict(list)
for w in works:
    if w['type'] == '作品':
        by_ed[(w['src'], w['edition'])].append({'sid': w['id'], '學校名稱': w['school']})
guess = {}
for rs in by_ed.values():
    guess.update(infer(rs))
for w in works:
    if w['type'] != '作品':
        w['stage'], w['stage_src'] = None, None
        continue
    code = w['code']
    m = re.match(r'(國小|國中|高中|高職)組', w['subject'])
    if code and code[:2] in CODE_STAGE:
        w['stage'], w['stage_src'] = CODE_STAGE[code[:2]], '作品編號'
    elif w['id'] in groups:
        w['stage'], w['stage_src'] = GROUP_STAGE[groups[w['id']]], '官網組別'
    elif m:
        w['stage'], w['stage_src'] = m.group(1), '官網科別'
    else:
        st, how = guess.get(w['id'], (None, None))
        w['stage'], w['stage_src'] = st, ('推測' if st else None)
    # 高中、高職在 2016 年後合併為「高級中等學校組」，統一成「高中職」方便篩選
    if w['stage'] in ('高中', '高職'):
        w['stage_detail'] = w['stage']
        w['stage'] = '高中職'

# 第 56～65 屆：以科展官網（twsf.ntsec.gov.tw）的官方作品資料表為準，補上得獎資訊
off_path = os.path.join(RAW, 'official_56-65.csv')
if os.path.exists(off_path):
    idx = {(w['edition_no'], w['code']): w for w in works if w['code']}
    for r in csv.DictReader(open(off_path, encoding='utf-8-sig')):
        w = idx.get((int(re.search(r'\d+', r['屆次']).group()), r['作品編號']))
        if not w:
            continue
        award = r['名次'].replace('最佳(鄉土)教材獎', '最佳鄉土教材獎').replace('(鄉土)教材獎', '最佳鄉土教材獎').replace('奬', '獎')
        if award == '未列獎項':
            w['rank'], w['special'] = w['rank'] or '未得獎', w['special']
        else:
            rank, special, _ = parse_award(award)
            w['rank'] = rank or w['rank']
            w['special'] = list(dict.fromkeys(w['special'] + special))
        w['award_src'] = '官方作品資料表'

# 全國 ↔ 國際 同名作品互相連結
by_title = collections.defaultdict(list)
for w in works:
    if w['type'] == '作品':
        by_title[norm_title(w['title'])].append(w)
for ws in by_title.values():
    srcs = {w['src'] for w in ws}
    if len(srcs) > 1:
        for w in ws:
            w['related'] = [x['id'] for x in ws if x['src'] != w['src']]

json.dump(works, open(os.path.join(OUT, 'works.json'), 'w', encoding='utf-8'), ensure_ascii=False)

# ---------- 報告 ----------
W = [w for w in works if w['type'] == '作品']
print('作品', len(W), '評語', len(works) - len(W))
print('學習階段來源', collections.Counter((w['src'], w['stage_src']) for w in W))
print('學習階段', collections.Counter((w['src'], w['stage']) for w in W))
print('無標準領域', collections.Counter(w['subject'] for w in W if not w['domains']))
print('名次', collections.Counter(w['rank'] for w in W).most_common())
print('特別獎', collections.Counter(s for w in W for s in w['special']).most_common())
print('縣市缺', sum(not w['city'] for w in W if w['src'] == '全國'), '/', sum(w['src'] == '全國' for w in W))
print('互相連結', sum('related' in w for w in W))
