import re
def stage_from_school(s):
    s = (s or '').replace('臺','台')
    if re.search(r'附設國[民]?中|\(國中部\)|國中部|附設國民中學', s): return '國中'
    if re.search(r'國民小學|國小|實驗小學|實小|小學', s): return '國小'
    if re.search(r'國民中學|國中', s): return '國中'
    if re.search(r'高級工業|高工|高級商業|高商|高級農|高農|高級職業|高職|家商|家事|海事|工商|工家|農工|商工|高級海', s): return '高職'
    if re.search(r'高級中學|高中|高級中等|完全中學|中學|實驗學校|女中', s): return '高中'
    if re.search(r'大學|學院', s): return '大學'
    return None

AMBIG = re.compile(r'財團法人|中小學|附屬|實驗|國際|美國學校|台商|臺商|私立.*(高級中學|中學)|完全中學|學院')
def infer(rows, window=4):
    """rows: works of ONE edition. Returns {sid: (stage, confidence)}"""
    rows = sorted(rows, key=lambda r: r['sid'])
    base = [stage_from_school(r.get('學校名稱')) for r in rows]
    amb = [bool(AMBIG.search(r.get('學校名稱') or '')) or b is None for r, b in zip(rows, base)]
    out = {}
    for i, r in enumerate(rows):
        if not amb[i]:
            out[r['sid']] = (base[i], '學校名稱'); continue
        near = [base[j] for j in range(max(0, i-window), min(len(rows), i+window+1)) if j != i and not amb[j] and base[j]]
        if near:
            from collections import Counter
            out[r['sid']] = (Counter(near).most_common(1)[0][0], '推測')
        else:
            out[r['sid']] = (base[i], '推測')
    return out
