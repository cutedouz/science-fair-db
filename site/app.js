'use strict';
/* 科展資料庫：純前端搜尋。資料在 data/，由 pipeline/build_site_data.py 產生。 */

const $ = (s) => document.querySelector(s);
const PAGE = 30;
const DOMAINS = ['數學', '物理', '化學', '生物', '地球科學', '環境科學', '生活與應用科學', '自然', '工程', '資訊', '農業與食品', '行為與社會科學', '其它'];
const STAGES = ['國小', '國中', '高中職', '未標示'];
const AWARDS = [
  ['top', '前三名・一至三等獎'],
  ['merit', '佳作・四等獎'],
  ['special', '特別獎'],
  ['none', '未得獎'],
  ['unknown', '未標示'],
];
const TOP = new Set(['第一名', '第二名', '第三名', '一等獎', '二等獎', '三等獎', '特別獎第一名', '特別獎第二名', '特別獎第三名']);
const MERIT = new Set(['佳作', '四等獎', '第四名', '大會獎佳作', '成就證書', '特別獎']);
const SRC = ['全國中小學科展', '臺灣國際科展'];

let docs = [];               // 作品（含評語）
let byId = new Map();
let abstracts = null;        // Map(id → 摘要)，背景載入
let absReady = null;         // Promise
let similar = null;
let info = {};

const state = {
  q: '', src: new Set(), stage: new Set(), domain: new Set(), award: new Set(),
  yFrom: null, yTo: null, city: '', review: false, scope: false, sort: 'rel', shown: PAGE, open: null,
};
let results = [];
let terms = [];

/* ---------- 文字處理 ---------- */
function norm(s) {
  return (s || '').toLowerCase().replace(/台/g, '臺')
    .replace(/[！-～]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0xfee0));
}
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
function highlight(text, maxLen) {
  let t = text || '';
  if (maxLen && t.length > maxLen) t = t.slice(0, maxLen) + '…';
  if (!terms.length) return esc(t);
  const n = norm(t);
  const ranges = [];
  for (const term of terms) {
    let i = n.indexOf(term);
    while (i !== -1) { ranges.push([i, i + term.length]); i = n.indexOf(term, i + term.length); }
  }
  if (!ranges.length) return esc(t);
  ranges.sort((a, b) => a[0] - b[0]);
  let out = '', pos = 0;
  for (const [a, b] of ranges) {
    if (a < pos) continue;
    out += esc(t.slice(pos, a)) + '<mark>' + esc(t.slice(a, b)) + '</mark>';
    pos = b;
  }
  return out + esc(t.slice(pos));
}
function snippet(d) {
  const a = abstracts && abstracts.get(d.i);
  if (!a) return '';
  if (terms.length) {
    const n = norm(a);
    for (const term of terms) {
      const i = n.indexOf(term);
      if (i > 40) return highlight('…' + a.slice(i - 30), 140);
      if (i !== -1) break;
    }
  }
  return highlight(a, 140);
}
function awardClass(d) {
  if (d.r && TOP.has(d.r)) return 'top';
  if (d.r && MERIT.has(d.r)) return 'merit';
  if (d.r === '未得獎') return 'none';
  return null;
}
function awardText(d) {
  const parts = [];
  if (d.r) parts.push(d.r);
  if (d.sp) parts.push(...d.sp);
  return parts.join('・');
}
const stageOf = (d) => d.g || '未標示';

/* ---------- 篩選與搜尋 ---------- */
function passes(d, skip) {
  if (!!d.v !== state.review) return false;
  if (state.yFrom && d.y < state.yFrom) return false;
  if (state.yTo && d.y > state.yTo) return false;
  if (state.city && d.c !== state.city) return false;
  const g = {};
  g.src = !state.src.size || state.src.has(String(d.s));
  g.stage = !state.stage.size || state.stage.has(stageOf(d));
  g.domain = !state.domain.size || (d.d || []).some((x) => state.domain.has(x));
  g.award = !state.award.size || [...state.award].some((a) =>
    a === 'special' ? d.sp && d.sp.length : a === 'unknown' ? !d.r && !(d.sp && d.sp.length) : awardClass(d) === a);
  for (const k in g) if (k !== skip && !g[k]) return false;
  return true;
}
function score(d) {
  if (!terms.length) return 1;
  let s = 0, core = false;
  const a = !state.scope && abstracts ? d._na || (d._na = norm(abstracts.get(d.i) || '')) : '';
  for (const t of terms) {
    let hit = 0;
    if (d._nt.includes(t)) { hit += 6; core = true; }
    if (d._nk.includes(t)) { hit += 4; core = true; }
    if (!state.scope && d._no.includes(t)) hit += 2;
    if (a) {
      let c = 0, i = a.indexOf(t);
      while (i !== -1 && c < 3) { c++; i = a.indexOf(t, i + t.length); }
      hit += c;
    }
    if (!hit) return 0;
    s += hit;
  }
  if (terms.length > 1 && d._nt.includes(terms.join(''))) s += 4;
  d._core = core;
  return s;
}
function run(keepPage) {
  terms = norm(state.q).split(/\s+/).filter(Boolean);
  const cand = [];
  for (const d of docs) {
    const sc = score(d);
    if (sc) { d._s = sc; cand.push(d); }
  }
  results = cand.filter((d) => passes(d));
  const bySort = {
    rel: (a, b) => b._s - a._s || b.y - a.y || b.i - a.i,
    new: (a, b) => b.y - a.y || b.i - a.i,
    old: (a, b) => a.y - b.y || a.i - b.i,
  };
  results.sort(bySort[terms.length ? state.sort : state.sort === 'rel' ? 'new' : state.sort]);
  if (!keepPage) state.shown = PAGE;
  renderFacets(cand);
  renderList();
  saveUrl();
}

/* ---------- 畫面 ---------- */
function chip(group, value, label, n) {
  const on = state[group].has(value);
  return `<button class="chip" type="button" data-g="${group}" data-v="${esc(value)}" aria-pressed="${on}" data-empty="${!n}">${esc(label)}<span class="n">${n.toLocaleString()}</span></button>`;
}
function renderFacets(cand) {
  const cnt = { src: {}, stage: {}, domain: {}, award: {} };
  for (const d of cand) {
    if (passes(d, 'src')) cnt.src[d.s] = (cnt.src[d.s] || 0) + 1;
    if (passes(d, 'stage')) cnt.stage[stageOf(d)] = (cnt.stage[stageOf(d)] || 0) + 1;
    if (passes(d, 'domain')) for (const x of d.d || []) cnt.domain[x] = (cnt.domain[x] || 0) + 1;
    if (passes(d, 'award')) {
      const ac = awardClass(d);
      if (ac) cnt.award[ac] = (cnt.award[ac] || 0) + 1;
      if (d.sp && d.sp.length) cnt.award.special = (cnt.award.special || 0) + 1;
      if (!d.r && !(d.sp && d.sp.length)) cnt.award.unknown = (cnt.award.unknown || 0) + 1;
    }
  }
  $('#f-src').innerHTML = SRC.map((l, i) => chip('src', String(i), l, cnt.src[i] || 0)).join('');
  $('#f-stage').innerHTML = STAGES.map((s) => chip('stage', s, s, cnt.stage[s] || 0)).join('');
  $('#f-domain').innerHTML = DOMAINS.filter((x) => cnt.domain[x] || state.domain.has(x)).map((x) => chip('domain', x, x, cnt.domain[x] || 0)).join('');
  $('#f-award').innerHTML = AWARDS.map(([k, l]) => chip('award', k, l, cnt.award[k] || 0)).join('');
  const nf = state.src.size + state.stage.size + state.domain.size + state.award.size + (state.city ? 1 : 0) +
    (state.yFrom ? 1 : 0) + (state.yTo ? 1 : 0) + (state.review ? 1 : 0);
  $('#filter-count').textContent = nf;
  $('#filter-count').hidden = !nf;
}
function metaLine(d) {
  const bits = [`<span class="tag src-${d.s}">${d.s ? '國際' : '全國'}</span>`];
  bits.push(`<span class="mono">${d.y || ''}</span>`);
  if (d.s === 0 && d.e) bits.push(esc(d.e.split('--')[0]));
  if (d.g) bits.push(`<span class="tag${d.gs === '推測' ? ' guess' : ''}">${esc(d.g)}</span>`);
  if (d.sj) bits.push(esc(d.sj));
  const aw = awardText(d);
  if (aw && d.r !== '未得獎') bits.push(`<span class="tag award">${esc(aw)}</span>`);
  if (d.sc) bits.push(highlight(d.sc));
  return bits.join('<span class="sep">·</span>');
}
function renderList() {
  $('#total').textContent = results.length.toLocaleString();
  const pack = getPack();
  const html = results.slice(0, state.shown).map((d) => `
    <li class="item">
      <div class="item-main" data-open="${d.i}" role="button" tabindex="0">
        <h3 class="item-title">${highlight(d.t)}</h3>
        <div class="meta">${metaLine(d)}${terms.length && !d._core ? '<span class="sep">·</span><span class="tag where">僅摘要或學校提到</span>' : ''}</div>
        ${d.v ? '' : `<p class="snippet">${snippet(d)}</p>`}
      </div>
      ${d.v ? '' : `<button class="pick" type="button" data-pick="${d.i}" aria-pressed="${pack.has(d.i)}" aria-label="加入研究包" title="加入研究包">${pack.has(d.i) ? '✓' : '+'}</button>`}
    </li>`).join('');
  $('#list').innerHTML = html || `<li class="empty">找不到符合的作品。試試較短的關鍵字，或清除部分篩選條件。</li>`;
  $('#more').hidden = results.length <= state.shown;
  $('#more').textContent = `顯示更多（還有 ${(results.length - state.shown).toLocaleString()} 件）`;
}

/* ---------- 詳細頁 ---------- */
function openDrawer(html) {
  $('#drawer').innerHTML = html;
  $('#drawer').hidden = false;
  $('#scrim').hidden = false;
  $('#drawer').scrollTop = 0;
  document.body.style.overflow = 'hidden';
}
function closeDrawer() {
  $('#drawer').hidden = true;
  $('#scrim').hidden = true;
  document.body.style.overflow = '';
  state.open = null;
  saveUrl();
}
function row(label, value) { return value ? `<dt>${label}</dt><dd>${value}</dd>` : ''; }
function simItem(id) {
  const d = byId.get(id);
  if (!d) return '';
  return `<li><button type="button" data-open="${d.i}"><span class="t">${esc(d.t)}</span><span class="m">${d.s ? '國際' : '全國'} · ${d.y} · ${esc(d.g || '')} · ${esc(d.sj || '')}${awardText(d) && d.r !== '未得獎' ? ' · ' + esc(awardText(d)) : ''}</span></button></li>`;
}
async function showWork(id) {
  const d = byId.get(id);
  if (!d) return;
  state.open = id;
  saveUrl();
  const url = `https://www.ntsec.edu.tw/science/detail.aspx?a=${d.s ? 90 : 21}&sid=${d.i}`;
  const stageNote = { '作品編號': '取自官方作品編號', '官網組別': '取自官網組別', '官網科別': '取自官網科別', '推測': '本站依學校名稱推測' }[d.gs] || '';
  const inPack = getPack().has(d.i);
  const render = () => {
    const abs = abstracts ? abstracts.get(d.i) : null;
    const sims = similar ? (similar[d.i] || []) : null;
    openDrawer(`
      <div class="drawer-bar">
        <span class="code-label">${d.cd ? '作品編號 ' + d.cd : 'SID ' + d.i}</span>
        <button class="close" type="button" data-close aria-label="關閉">✕</button>
      </div>
      <h2 id="d-title">${esc(d.t)}</h2>
      <div class="meta">${metaLine(d)}</div>
      <div class="actions">
        ${d.v ? '' : `<button class="btn primary" type="button" data-pick="${d.i}" aria-pressed="${inPack}">${inPack ? '已在研究包 ✓' : '加入研究包'}</button>`}
        ${d.p ? `<a class="btn" href="${esc(d.p)}" target="_blank" rel="noopener">下載 PDF</a>` : ''}
        <a class="btn" href="${url}" target="_blank" rel="noopener">科教館原始頁面 ↗</a>
      </div>
      <dl class="facts">
        ${row('來源', `${SRC[d.s]}${d.s === 0 ? '・' + esc(d.e) : '・' + d.y + ' 年'}`)}
        ${row('學習階段', d.g ? `${esc(d.gd || d.g)} <span class="note">${stageNote}</span>` : '<span class="note">未標示</span>')}
        ${row('科別', `${esc(d.sj || '（未填）')}${d.d && d.d.length ? ` <span class="note">領域：${esc(d.d.join('、'))}</span>` : ''}`)}
        ${row('得獎', esc(awardText(d)) || '<span class="note">未標示</span>')}
        ${row('出國代表', d.rp ? esc(d.rp.join('；')) : '')}
        ${row('學校', esc(d.sc) + (d.c ? ` <span class="note">${esc(d.c)}</span>` : ''))}
        ${row('指導老師', esc((d.tc || []).join('、')))}
        ${row('關鍵字', d.k ? `<div class="kw">${d.k.map((k) => `<button type="button" data-kw="${esc(k)}">${esc(k)}</button>`).join('')}</div>` : '')}
      </dl>
      <p class="author-note">作者資訊請見<a href="${url}" target="_blank" rel="noopener">科教館原始頁面</a>。本站不收錄作者姓名。</p>
      <div class="section-h">摘要或動機</div>
      <div class="abstract">${abs ? esc(abs) : abstracts ? '<span class="note">這件作品沒有摘要。</span>' : '<span class="note">摘要載入中…</span>'}</div>
      ${d.f ? `<div class="section-h">研究內容節錄</div><div id="ft-box"><button class="btn" type="button" data-ft="${d.i}">顯示研究目的、方法、結果與結論</button><p class="note">節錄自 PDF 全文，圖表、照片與公式無法呈現，請以 PDF 為準。</p></div>` : ''}
      ${d.rl ? `<div class="section-h">同一作品也參加了${d.s ? '全國科展' : '國際科展'}</div><ul class="sim">${d.rl.map(simItem).join('')}</ul>` : ''}
      ${d.v ? '' : `<div class="section-h">相似作品</div>${sims === null ? '<p class="note">計算中…</p>' : sims.length ? `<ul class="sim">${sims.map(simItem).join('')}</ul>` : '<p class="note">沒有足夠相似的作品。</p>'}`}
    `);
  };
  render();
  if (!abstracts || !similar) {
    await Promise.all([absReady, loadSimilar()]);
    if (state.open === id) render();
  }
}
const ftCache = new Map();
function loadFulltext(id) {
  if (!ftCache.has(id)) ftCache.set(id, fetch(`data/fulltext/${id}.json`).then((r) => (r.ok ? r.json() : null)).catch(() => null));
  return ftCache.get(id);
}
let simPromise = null;
function loadSimilar() {
  return simPromise || (simPromise = fetch('data/similar.json').then((r) => r.json()).then((j) => { similar = j; }).catch(() => { similar = {}; }));
}

async function showFulltext(id) {
  const box = $('#ft-box');
  box.innerHTML = '<p class="note">載入中…</p>';
  const secs = await loadFulltext(id);
  if (state.open !== id || !$('#ft-box')) return;
  $('#ft-box').innerHTML = secs && secs.length
    ? secs.map((x) => `<details class="ft"><summary>${esc(x.h)}</summary><div class="abstract">${esc(x.t)}</div></details>`).join('') +
      '<p class="note">節錄自 PDF 全文，圖表、照片與公式無法呈現，請以 PDF 為準。</p>'
    : '<p class="note">這件作品目前沒有節錄內容。</p>';
  const first = $('#ft-box details');
  if (first) first.open = true;
}

/* ---------- 查證研究方向 ---------- */
function verifyLines(text) {
  return text.split('\n').map((line) => {
    const m = line.match(/查證關鍵字[:：]\s*(.+)/);
    const kws = norm(m ? m[1] : line).split(/[\s、,，;；/]+/).filter((k) => k.length >= 1);
    return [...new Set(kws)];
  }).filter((k) => k.length);
}
function verifyOne(kws) {
  const full = [], part = [];
  for (const d of docs) {
    if (d.v) continue;
    const a = abstracts ? d._na || (d._na = norm(abstracts.get(d.i) || '')) : '';
    let hit = 0, sc = 0;
    for (const k of kws) {
      const h = (d._nt.includes(k) ? 6 : 0) + (d._nk.includes(k) ? 4 : 0) + (a.includes(k) ? 1 : 0);
      if (h) { hit++; sc += h; }
    }
    if (hit === kws.length) full.push([d, sc]);
    else if (kws.length > 1 && hit >= Math.ceil(kws.length / 2)) part.push([d, sc + hit * 10]);
  }
  const by = (x, y) => y[1] - x[1] || y[0].y - x[0].y;
  return { full: full.sort(by), part: part.sort(by) };
}
function verifyHtml(kws) {
  const { full, part } = verifyOne(kws);
  const list = (arr, n) => `<ul class="sim">${arr.slice(0, n).map(([d]) => simItem(d.i)).join('')}</ul>`;
  const label = kws.map((k) => `<span class="tag">${esc(k)}</span>`).join(' ');
  let body;
  if (full.length) {
    body = `<p><b>已有 ${full.length} 件作品同時提到這些關鍵字</b>，動手前請先讀讀看，想想你的研究和它們有什麼不同。</p>${list(full, 6)}`;
  } else {
    body = `<p><b>沒有作品同時提到這些關鍵字。</b>這不代表一定沒人做過：別人可能用了不同的詞，請換成同義詞再查一次（例如「清潔劑」和「界面活性劑」）。</p>`;
  }
  if (part.length) body += `<p class="note">部分符合（只提到其中幾個關鍵字）：${part.length} 件</p>${list(part, 4)}`;
  return `<section class="verify-item"><div class="meta">${label}<button class="reset" type="button" data-vsearch="${esc(kws.join(' '))}">在搜尋結果中查看</button></div>${body}</section>`;
}
function showVerify(text) {
  let saved = '';
  try { saved = localStorage.getItem('verify') || ''; } catch { /* 無法讀取就留空 */ }
  state.open = null;
  openDrawer(`
    <div class="drawer-bar"><span class="code-label">查證研究方向</span><button class="close" type="button" data-close aria-label="關閉">✕</button></div>
    <h2 id="d-title">這個方向有人做過嗎？</h2>
    <p class="note">每一行輸入一個研究方向的關鍵字，或直接貼上 AI 回答中「查證關鍵字：」那幾行。網站會在全部 ${docs.filter((d) => !d.v).length.toLocaleString()} 件作品的標題、關鍵字與摘要中尋找。</p>
    <label for="verify-input" class="section-h">研究方向關鍵字</label>
    <textarea id="verify-input" class="fallback" rows="5" placeholder="查證關鍵字：螞蟻 界面活性劑 表面張力&#10;查證關鍵字：費洛蒙 溫度&#10;螞蟻 蚜蟲 蜜露">${esc(text ?? saved)}</textarea>
    <div class="actions"><button class="btn primary" type="button" id="verify-run">查證</button></div>
    <div id="verify-out"></div>
  `);
  if (text ?? saved) runVerify();
}
async function runVerify() {
  const text = $('#verify-input').value;
  try { localStorage.setItem('verify', text); } catch { /* 無法儲存時略過 */ }
  const lines = verifyLines(text);
  if (!lines.length) { $('#verify-out').innerHTML = '<p class="note">請先輸入關鍵字。</p>'; return; }
  $('#verify-out').innerHTML = '<p class="note">查證中…</p>';
  await absReady;
  $('#verify-out').innerHTML = lines.map(verifyHtml).join('') +
    '<p class="note">只比對標題、關鍵字與摘要，研究內容節錄不在查證範圍內。結果僅供參考，最後仍要自己讀過相關作品再判斷。</p>';
}

/* ---------- 研究包 ---------- */
function getPack() {
  try { return new Set(JSON.parse(localStorage.getItem('pack') || '[]')); } catch { return packMem; }
}
let packMem = new Set();
function setPack(set) {
  packMem = set;
  try { localStorage.setItem('pack', JSON.stringify([...set])); } catch { /* 無法儲存時只保留在本頁 */ }
  $('#pack-count').textContent = set.size;
}
function togglePick(id) {
  const p = getPack();
  p.has(id) ? p.delete(id) : p.add(id);
  setPack(p);
  renderList();
  if (state.open === id) showWork(id);
}
async function packText(ids) {
  const fts = await Promise.all(ids.map((id) => (byId.get(id) && byId.get(id).f ? loadFulltext(id) : null)));
  const nft = fts.filter(Boolean).length;
  const today = new Date().toISOString().slice(0, 10);
  const topic = state.q.trim() || '自選主題';
  const lines = [
    `# 科展研究包：${topic}`,
    '',
    `產生日期：${today}　共 ${ids.length} 件作品，其中 ${nft} 件附研究內容節錄`,
    '資料來源：國立臺灣科學教育館（https://www.ntsec.edu.tw），依政府網站資料開放宣告使用。本檔由「科展資料庫」整理，非科教館官方資料。作者姓名請見各作品的科教館頁面。',
    '',
    '## 給 AI 的指示',
    '',
    `你是協助中小學生做科展研究的助理。以下是 ${ids.length} 件過去的科展作品資料，編號 W1 到 W${ids.length}。請：`,
    '1. 依研究問題把這些作品分組，說明每一組在探討什麼。',
    '2. 用表格比較各作品的研究方法、操作變因、使用器材與主要發現。每一格都要註明出自哪一件（例如 W3）。',
    '   表格只能填本檔明確寫到的內容。沒寫到的一律填「本檔未提及」，不要依常理補上可能用到的方法或器材；真的要補充時，另外標示〔推測〕。',
    '3. 找出這些作品還沒探討、值得延伸研究的方向，並說明理由。',
    '   「還沒探討」只代表本檔這幾件作品沒有做過，不代表所有科展都沒人做過。',
    '   每個方向的最後一行，請用這個格式寫出 2～4 個中文關鍵字，方便我到「科展資料庫」查證：查證關鍵字：關鍵字1 關鍵字2 關鍵字3',
    '   每個方向都要評估中小學生是否做得到（器材、時間、經費），並提醒安全與法規限制，例如危險化學藥品、入侵種或受保護物種的採集與飼養。',
    '4. 只根據本檔內容回答。有「研究內容節錄」的作品，以節錄為主要依據；只有摘要的作品，引用時註明「僅依摘要」。本檔沒有寫到的，請直接說「本檔未提及」，並告訴我該讀哪一件的 PDF 全文。',
    '   節錄是從 PDF 自動抽出的文字，圖表、照片和公式會缺漏或變亂；看不懂的數據請不要自行猜測，直接請我查看 PDF。',
    '5. 引用任何一件作品之前，先核對它的標題與研究對象，不要把不同作品的變因、器材或結果混在一起。',
    '6. 不要替我寫研究報告、實驗結果或結論。',
    '',
    '## 作品',
  ];
  ids.forEach((id, n) => {
    const d = byId.get(id);
    if (!d) return;
    lines.push('', `### W${n + 1}｜${d.t}`);
    lines.push(`- 來源：${SRC[d.s]}　${d.s === 0 ? d.e : d.y + ' 年'}`);
    lines.push(`- 學習階段／科別：${d.gd || d.g || '未標示'}／${d.sj || '未填'}`);
    if (awardText(d)) lines.push(`- 得獎：${awardText(d)}`);
    lines.push(`- 學校：${d.sc || '未填'}`);
    if (d.k) lines.push(`- 關鍵字：${d.k.join('、')}`);
    lines.push(`- 科教館頁面：https://www.ntsec.edu.tw/science/detail.aspx?a=${d.s ? 90 : 21}&sid=${d.i}`);
    if (d.p) lines.push(`- PDF 全文：${d.p}`);
    lines.push('', `摘要：${(abstracts && abstracts.get(d.i)) || '（無摘要）'}`);
    const ft = fts[n];
    if (ft && ft.length) {
      lines.push('', '研究內容節錄（自動取自 PDF，圖表與公式可能缺漏）：');
      for (const x of ft) lines.push('', `#### ${x.h}`, x.t);
    }
  });
  return lines.join('\n');
}
function showPack() {
  const ids = [...getPack()].filter((id) => byId.has(id));
  state.open = null;
  openDrawer(`
    <div class="drawer-bar"><span class="code-label">研究包 · ${ids.length} 件</span><button class="close" type="button" data-close aria-label="關閉">✕</button></div>
    <h2 id="d-title">研究包</h2>
    <p class="note">把勾選的作品整理成一份文字檔，上傳到 Gemini Notebook（或其他 AI 工具）後，就能請 AI 比較這些研究的方法與發現。檔案裡已附上寫好的指示。</p>
    <ol class="howto">
      <li>在搜尋結果按 <b>＋</b> 把作品加進來，建議 10～30 件。第 40 屆（2000 年）以後的全國科展作品大多附有研究方法、結果與結論的節錄（第 41 屆多為掃描檔，沒有節錄）。</li>
      <li>按「下載檔案」或「複製內容」。</li>
      <li>在 Gemini Notebook 新增來源，上傳檔案或貼上文字。</li>
      <li>想深入的作品，再把它的 PDF 全文加進同一本筆記。</li>
    </ol>
    <div class="actions">
      <button class="btn primary" type="button" id="pack-download" ${ids.length ? '' : 'disabled'}>下載檔案</button>
      <button class="btn" type="button" id="pack-copy" ${ids.length ? '' : 'disabled'}>複製內容</button>
      <button class="btn" type="button" id="pack-clear" ${ids.length ? '' : 'disabled'}>清空</button>
    </div>
    ${ids.filter((id) => byId.get(id).f).length > 30 ? '<p class="note">附研究內容節錄的作品超過 30 件，檔案會很長，AI 的比較也會變得粗略，建議縮小範圍。</p>' : ids.length > 100 ? '<p class="note">超過 100 件時，AI 的比較會變得粗略，建議縮小範圍。</p>' : ''}
    <div id="pack-fallback"></div>
    <ul class="pack-list">${ids.map((id) => {
      const d = byId.get(id);
      return `<li><span>${esc(d.t)}<br><span class="note">${d.s ? '國際' : '全國'} · ${d.y} · ${esc(d.sj || '')}${d.f ? ' · 附研究內容節錄' : ' · 僅摘要'}</span></span><button class="x" type="button" data-unpick="${id}" aria-label="移除">✕</button></li>`;
    }).join('') || '<li class="note">研究包是空的。</li>'}</ul>
  `);
}
async function packAction(kind) {
  await absReady;
  const ids = [...getPack()].filter((id) => byId.has(id));
  const text = await packText(ids);
  if (kind === 'copy') {
    try { await navigator.clipboard.writeText(text); toast('已複製研究包內容'); }
    catch { fallback(text); }
  } else {
    const name = `科展研究包_${(state.q.trim() || '自選').replace(/[\\/:*?"<>|\s]+/g, '_').slice(0, 30)}.md`;
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([text], { type: 'text/markdown;charset=utf-8' }));
    a.download = name;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
    toast('已下載 ' + name);
  }
}
function fallback(text) {
  $('#pack-fallback').innerHTML = '<p class="note">無法自動複製，請全選下方文字後手動複製。</p><textarea class="fallback" id="pack-text" readonly></textarea>';
  $('#pack-text').value = text;
  $('#pack-text').select();
}
let toastTimer;
function toast(msg) {
  $('#toast').textContent = msg;
  $('#toast').hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { $('#toast').hidden = true; }, 2200);
}

/* ---------- 網址狀態 ---------- */
function saveUrl() {
  const p = new URLSearchParams();
  if (state.q) p.set('q', state.q);
  for (const [k, g] of [['src', 'src'], ['st', 'stage'], ['dm', 'domain'], ['aw', 'award']]) if (state[g].size) p.set(k, [...state[g]].join(','));
  if (state.yFrom) p.set('yf', state.yFrom);
  if (state.yTo) p.set('yt', state.yTo);
  if (state.city) p.set('c', state.city);
  if (state.review) p.set('rv', '1');
  if (state.scope) p.set('sc', '1');
  if (state.sort !== 'rel') p.set('sort', state.sort);
  if (state.open) p.set('w', state.open);
  const qs = p.toString();
  try { history.replaceState(null, '', qs ? '?' + qs : location.pathname); } catch { /* 預覽環境不支援 */ }
}
function loadUrl() {
  let p;
  try { p = new URLSearchParams(location.search); } catch { return; }
  state.q = p.get('q') || '';
  for (const [k, g] of [['src', 'src'], ['st', 'stage'], ['dm', 'domain'], ['aw', 'award']]) if (p.get(k)) state[g] = new Set(p.get(k).split(','));
  state.yFrom = +p.get('yf') || null;
  state.yTo = +p.get('yt') || null;
  state.city = p.get('c') || '';
  state.review = p.get('rv') === '1';
  state.scope = p.get('sc') === '1';
  state.sort = p.get('sort') || 'rel';
  state.open = +p.get('w') || null;
}

/* ---------- 事件 ---------- */
let qTimer;
$('#q').addEventListener('input', (e) => {
  state.q = e.target.value;
  $('#q-clear').hidden = !state.q;
  clearTimeout(qTimer);
  qTimer = setTimeout(() => run(), 180);
});
$('#q-clear').addEventListener('click', () => { state.q = ''; $('#q').value = ''; $('#q-clear').hidden = true; run(); $('#q').focus(); });
$('#sort').addEventListener('change', (e) => { state.sort = e.target.value; run(); });
$('#y-from').addEventListener('change', (e) => { state.yFrom = +e.target.value || null; run(); });
$('#y-to').addEventListener('change', (e) => { state.yTo = +e.target.value || null; run(); });
$('#f-city').addEventListener('change', (e) => { state.city = e.target.value; run(); });
$('#f-review').addEventListener('change', (e) => { state.review = e.target.checked; run(); });
$('#f-scope').addEventListener('change', (e) => { state.scope = e.target.checked; run(); });
$('#reset').addEventListener('click', () => {
  Object.assign(state, { src: new Set(), stage: new Set(), domain: new Set(), award: new Set(), yFrom: null, yTo: null, city: '', review: false });
  syncControls(); run();
});
$('#more').addEventListener('click', () => { state.shown += PAGE * 2; renderList(); });
$('#open-filters').addEventListener('click', () => $('#filters').classList.add('open'));
$('#close-filters').addEventListener('click', () => $('#filters').classList.remove('open'));
$('#open-pack').addEventListener('click', showPack);
$('#open-verify').addEventListener('click', () => showVerify());
$('#scrim').addEventListener('click', closeDrawer);
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !$('#drawer').hidden) closeDrawer(); });
document.addEventListener('click', (e) => {
  const t = e.target.closest('[data-g],[data-open],[data-pick],[data-unpick],[data-close],[data-kw],[data-ft],[data-vsearch],#verify-run,#pack-copy,#pack-download,#pack-clear');
  if (!t) return;
  if (t.dataset.g) {
    const set = state[t.dataset.g];
    set.has(t.dataset.v) ? set.delete(t.dataset.v) : set.add(t.dataset.v);
    run();
  } else if (t.dataset.pick) {
    togglePick(+t.dataset.pick);
  } else if (t.dataset.unpick) {
    const p = getPack(); p.delete(+t.dataset.unpick); setPack(p); renderList(); showPack();
  } else if (t.dataset.open) {
    showWork(+t.dataset.open);
  } else if (t.hasAttribute('data-close')) {
    closeDrawer();
  } else if (t.dataset.kw) {
    state.q = t.dataset.kw; $('#q').value = state.q; $('#q-clear').hidden = false; closeDrawer(); run();
    window.scrollTo(0, 0);
  } else if (t.dataset.vsearch) {
    state.q = t.dataset.vsearch; $('#q').value = state.q; $('#q-clear').hidden = false; closeDrawer(); run();
    window.scrollTo(0, 0);
  } else if (t.id === 'verify-run') {
    runVerify();
  } else if (t.dataset.ft) {
    showFulltext(+t.dataset.ft);
  } else if (t.id === 'pack-copy') packAction('copy');
  else if (t.id === 'pack-download') packAction('download');
  else if (t.id === 'pack-clear') { setPack(new Set()); renderList(); showPack(); }
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && e.target.dataset && e.target.dataset.open) showWork(+e.target.dataset.open);
});
function syncControls() {
  $('#q').value = state.q;
  $('#q-clear').hidden = !state.q;
  $('#sort').value = state.sort;
  $('#y-from').value = state.yFrom || '';
  $('#y-to').value = state.yTo || '';
  $('#f-city').value = state.city;
  $('#f-review').checked = state.review;
  $('#f-scope').checked = state.scope;
}

/* ---------- 啟動 ---------- */
async function start() {
  $('#list').innerHTML = '<li class="empty">載入作品資料中…</li>';
  try {
    [docs, info] = await Promise.all([
      fetch('data/meta.json').then((r) => r.json()),
      fetch('data/info.json').then((r) => r.json()),
    ]);
  } catch (err) {
    $('#list').innerHTML = '<li class="empty">資料載入失敗，請重新整理頁面。</li>';
    return;
  }
  for (const d of docs) {
    d._nt = norm(d.t);
    d._nk = norm((d.k || []).join(' '));
    d._no = norm([d.sc, ...(d.tc || [])].join(' '));
    byId.set(d.i, d);
  }
  const years = [...new Set(docs.map((d) => d.y).filter(Boolean))].sort((a, b) => a - b);
  const opts = years.map((y) => `<option value="${y}">${y}</option>`).join('');
  $('#y-from').innerHTML = '<option value="">最早</option>' + opts;
  $('#y-to').innerHTML = '<option value="">最新</option>' + opts;
  const cities = [...new Set(docs.map((d) => d.c).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'zh-Hant'));
  $('#f-city').innerHTML += cities.map((c) => `<option>${esc(c)}</option>`).join('');
  $('#brand-count').textContent = `${(info.count || docs.length).toLocaleString()} 件作品・${years[0]}–${years[years.length - 1]}`;
  if (info.built) $('#built').textContent = ` 資料更新：${info.built}。`;
  setPack(getPack());
  loadUrl();
  syncControls();
  run();
  if (state.open) showWork(state.open);

  absReady = Promise.all(Array.from({ length: info.abstract_files || 1 }, (_, n) =>
    fetch(`data/abstracts-${n}.json`).then((r) => r.json()))).then((parts) => {
    abstracts = new Map();
    for (const part of parts) for (const k in part) abstracts.set(+k, part[k]);
    $('#abs-note').hidden = true;
    run(true);
  }).catch(() => { abstracts = new Map(); $('#abs-note').textContent = '摘要載入失敗，目前只搜尋標題與關鍵字'; });
}
start();
