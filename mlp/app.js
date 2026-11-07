import * as L from './logic.js';

const $ = (s) => document.querySelector(s);
const root = $('#root');
let M = null;
const S = { intent: null, pass: null, lots: null, lot: null, myBid: null, auction: null, deal: null, chain: [] };
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const mln = (n) => (n >= 1e6 ? `${(n / 1e6).toFixed(2).replace('.', ',')} mln` : L.fmt(n));
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

function countUp(el, to, ms = 1100, f = mln) {
  const t0 = performance.now();
  const tick = (t) => { const k = Math.min(1, (t - t0) / ms), e = 1 - Math.pow(1 - k, 3); el.textContent = f(Math.round(to * e)); if (k < 1) requestAnimationFrame(tick); };
  requestAnimationFrame(tick);
}
const runCounters = () => document.querySelectorAll('[data-count]').forEach((el) => countUp(el, +el.dataset.count));

function fly(emoji, x = innerWidth / 2, y = innerHeight / 2) {
  for (let k = 0; k < 7; k++) {
    const e = document.createElement('div');
    e.className = 'fly'; e.textContent = emoji;
    e.style.left = `${x - 20 + (k - 3) * 34}px`; e.style.top = `${y}px`; e.style.animationDelay = `${k * 70}ms`;
    document.body.appendChild(e); setTimeout(() => e.remove(), 1800);
  }
}

// ---------------- Landing ----------------
function landing() {
  const tick = [];
  for (const p of L.PRODUCTS) {
    const m = M[p.id];
    tick.push(`<span>${p.name} <b>${mln(m.median)}</b> so'm/t</span>`);
    const o = m.outliers[0];
    if (o) tick.push(`<span>№${o.id} <span class="up">▲ +${Math.round(o.markup * 100)}%</span></span>`);
  }
  root.innerHTML = `
  <div class="land">
    <div class="nav in"><div class="logo"><div class="mark">A</div>Aniq</div><span class="pill g"><span class="dot"></span>UZEX 2035</span></div>
    <div class="hero">
      <span class="pill in" style="--d:1">Birja terminali kerak emas</span>
      <h1 class="in" style="--d:2">Ayting.<br><span class="grad">Qolganini Aniq qiladi.</span></h1>
      <p class="in" style="--d:3">Agent savdolashadi. Har bir qadam isbotlanadi.</p>
      <button class="btn in" style="--d:4" id="start">Boshlash →</button>
      <div class="feat">
        ${[['📈', 'Shubhali narx', 'Narx pasporti'], ['📦', 'Yo\'q tovar', 'Tasdiqlangan zaxira'], ['🎭', 'Soxta taklif', 'Muhrlangan auksion'], ['💸', 'Qotgan pul', 'Avto-qaytarish']]
          .map(([i, x, y], k) => `<div class="f in" style="--d:${5 + k}"><span class="ic" style="--d:${k}">${i}</span><div class="x">${x}</div><div class="y">${y}</div></div>`).join('')}
      </div>
    </div>
    <div class="tick"><div>${tick.join('')}${tick.join('')}</div></div>
  </div>`;
  $('#start').onclick = () => need();
}

// ---------------- Shell ----------------
function shell(step, name, title, body, back) {
  root.innerHTML = `
  <div class="app">
    <div class="top"><button class="back" id="back" aria-label="Orqaga">←</button>
      <div class="prog">${[1, 2, 3, 4].map((i) => `<i class="${i < step ? 'done' : i === step ? 'on' : ''}"></i>`).join('')}</div>
      <span class="pill">${step}/4</span></div>
    <div class="stepname in">${name}</div>
    <h2 class="h in" style="--d:1">${title}</h2>
    ${body}
    <div class="foot">Narx va sotuvchilar — tashkilotchilar reyestri · Lot, agentlar, escrow — simulyatsiya</div>
  </div>`;
  $('#back').onclick = back;
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ---------------- 1 · Need ----------------
const EXAMPLES = [
  "Farg'onaga 20 tonna AI-92 benzin kerak, 20 kun ichida, tonnasi 17 mln so'mdan oshmasin",
  'Нужно 50 тонн цемента в Ташкент за 20 дней, не дороже 1 000 000 сум за тонну',
  "Samarqandga 30 tonna bug'doy kerak, 15 kun ichida",
];
function need() {
  shell(1, 'Ehtiyoj', 'Nima kerak?', `
    <div class="ask in" style="--d:2"><textarea id="need" placeholder="Oddiy tilda yozing…">${esc(S.intent?.text ?? '')}</textarea><button class="send" id="parse" aria-label="Yuborish">→</button></div>
    <div class="ex">${EXAMPLES.map((e, i) => `<button class="in" style="--d:${3 + i}" data-ex="${i}">${esc(e)}</button>`).join('')}</div>
    <div id="mand"></div>`, landing);
  const go = () => { const t = $('#need').value.trim(); if (t) mandate({ ...L.parseIntent(t), text: t }); };
  $('#parse').onclick = go;
  $('#need').onkeydown = (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); go(); } };
  root.querySelectorAll('[data-ex]').forEach((b) => b.onclick = () => { $('#need').value = EXAMPLES[b.dataset.ex]; go(); });
  if (S.intent) mandate(S.intent);
}

function mandate(i) {
  const miss = (k) => (i.missing.includes(k) ? ' miss' : '');
  $('#mand').innerHTML = `
  <div class="card in">
    <div class="row" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
      <b style="font-size:18px">Agent mandati</b>${i.complete ? '<span class="pill g">✓ Tushunildi</span>' : '<span class="pill a">To\'ldiring</span>'}</div>
    <div class="mand">
      <div class="mf wide${miss('productId')}"><label>Tovar</label><select id="f-p"><option value="">—</option>${L.PRODUCTS.map((p) => `<option value="${p.id}" ${p.id === i.productId ? 'selected' : ''}>${p.name}</option>`).join('')}</select></div>
      <div class="mf${miss('qty')}"><label>Tonna</label><input id="f-q" type="number" inputmode="numeric" value="${i.qty ?? ''}"></div>
      <div class="mf${miss('days')}"><label>Kun</label><input id="f-d" type="number" inputmode="numeric" value="${i.days ?? ''}"></div>
      <div class="mf${miss('regionId')}"><label>Manzil</label><select id="f-r"><option value="">—</option>${L.REGIONS.map((r) => `<option value="${r.id}" ${r.id === i.regionId ? 'selected' : ''}>${r.name}</option>`).join('')}</select></div>
      <div class="mf${miss('maxPrice')}"><label>Maks. so'm / t</label><input id="f-m" type="number" inputmode="numeric" value="${i.maxPrice ?? ''}"></div>
    </div>
    <div class="lock">🔒 Agent bu chegaradan chiqolmaydi</div>
    <button class="btn" id="go" style="width:100%;margin-top:8px">Lotlarni topish →</button>
  </div>`;
  $('#mand').scrollIntoView({ behavior: 'smooth', block: 'start' });
  $('#go').onclick = () => {
    const v = L.validateIntent({ productId: $('#f-p').value || null, qty: parseInt($('#f-q').value, 10), regionId: $('#f-r').value || null, days: parseInt($('#f-d').value, 10), maxPrice: parseInt($('#f-m').value, 10) });
    if (!v.complete) return mandate({ ...v, text: i.text });
    S.intent = { ...v, text: i.text }; market();
  };
}

// ---------------- 2 · Market ----------------
function chart(pass) {
  const W = 700, H = 200, D = pass.daily;
  const ps = D.map((h) => h.p).concat([pass.p10, pass.p90]), lo = Math.min(...ps) * 0.97, hi = Math.max(...ps) * 1.03;
  const x = (k) => (k / (D.length - 1)) * W, y = (p) => H - ((p - lo) / (hi - lo)) * H;
  const line = D.map((h, k) => `${k ? 'L' : 'M'}${x(k).toFixed(1)},${y(h.p).toFixed(1)}`).join('');
  return `<svg class="chart" viewBox="0 0 ${W} ${H + 24}" width="100%" preserveAspectRatio="none" style="display:block;margin-top:14px">
    <defs><linearGradient id="gl" x1="0" x2="1"><stop offset="0" stop-color="#33e6a0"/><stop offset="1" stop-color="#5aa9ff"/></linearGradient>
    <linearGradient id="ga" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#33e6a0" stop-opacity=".25"/><stop offset="1" stop-color="#33e6a0" stop-opacity="0"/></linearGradient></defs>
    <rect x="0" y="${y(pass.p90)}" width="${W}" height="${y(pass.p10) - y(pass.p90)}" fill="rgba(255,255,255,.035)" rx="6"/>
    <path class="area" d="${line}L${W},${H}L0,${H}Z" fill="url(#ga)"/>
    <path class="line" d="${line}" fill="none" stroke="url(#gl)" stroke-width="3" stroke-linejoin="round"/>
    <line x1="0" x2="${W}" y1="${y(pass.median)}" y2="${y(pass.median)}" stroke="rgba(255,255,255,.3)" stroke-dasharray="5 6"/>
    <text x="0" y="${H + 20}" font-size="12" fill="#8b97aa">${D[0].d}</text><text x="${W}" y="${H + 20}" font-size="12" fill="#8b97aa" text-anchor="end">${D.at(-1).d}</text>
  </svg>`;
}
const ring = (v, ok) => {
  const c = 2 * Math.PI * 23, col = ok ? '#33e6a0' : '#ff5d6c';
  return `<div class="ring"><svg width="56" height="56"><circle cx="28" cy="28" r="23" stroke="rgba(255,255,255,.08)" stroke-width="5" fill="none"/><circle cx="28" cy="28" r="23" stroke="${col}" stroke-width="5" fill="none" stroke-linecap="round" stroke-dasharray="${c}" stroke-dashoffset="${c * (1 - v)}" style="transition:stroke-dashoffset 1.2s"/></svg><b style="color:${col}">${Math.round(v * 100)}%</b></div>`;
};

function market() {
  const i = S.intent, p = L.product(i.productId);
  S.pass = L.passport(M[i.productId]); S.lots = L.lotsFor(i, M[i.productId]);
  const adv = L.agentBid(i, S.pass); S.myBid = adv.bid;
  const ok = S.lots.filter((l) => l.eligible).sort((a, b) => a.start - b.start), no = S.lots.filter((l) => !l.eligible);
  const short = (r) => r.replace(/ —.*/, '').replace(/:.*/, '');
  shell(2, p.name, 'Narx pasporti', `
    <div class="card in" style="--d:2">
      <div class="stats">
        <div class="stat"><div class="k">Median</div><div class="v" data-count="${S.pass.median}">0</div><div class="u">so'm / t</div></div>
        <div class="stat"><div class="k">Odatiy oraliq</div><div class="v" style="font-size:clamp(15px,2.6vw,19px)">${mln(S.pass.p10)} – ${mln(S.pass.p90)}</div><div class="u">P10–P90</div></div>
        <div class="stat"><div class="k">Sizning chegara</div><div class="v" data-count="${i.maxPrice}" style="color:${adv.warn ? 'var(--a)' : 'var(--g)'}">0</div><div class="u">so'm / t</div></div>
      </div>
      ${chart(S.pass)}
      <div class="muted" style="margin-top:6px">${L.fmt(S.pass.n)} ta real bitim · ${S.pass.from} — ${S.pass.to}</div>
    </div>
    ${S.pass.outliers.length ? `<details class="in" style="--d:3;margin-bottom:14px"><summary><span class="pill r">⚠ ${S.pass.outliers.length}</span> ta shubhali qimmat bitim <span class="muted" style="margin-left:auto">ko'rish</span></summary>
      <div class="ol">${S.pass.outliers.map((o) => `<span class="id">№${o.id}</span><span>${o.d}</span><b style="color:var(--r)">+${Math.round(o.markup * 100)}%</b>`).join('')}</div></details>` : ''}
    ${adv.warn ? `<div class="warnbox in" style="--d:3"><span style="font-size:26px">🤖</span><div style="flex:1"><b>Chegarangiz bozordan yuqori.</b><div class="muted">Tavsiya: ${mln(adv.suggested)}</div></div><button class="btn sm" id="accept">Qabul</button></div>` : ''}
    <div class="stepname in" style="--d:4">Lotlar · ${ok.length} ta mos</div>
    ${ok.map((l, k) => `
      <div class="lot ok in" style="--d:${5 + k}" data-lot="${l.id}">${ring(l.record.onTime, true)}
        <div class="main"><div class="nm">${esc(l.seller)}</div><div class="chips"><span class="pill g">✓ Zaxira</span><span class="pill">${l.deliveryDays} kun</span><span class="pill">${esc(l.region.replace(' viloyati', ''))}</span></div></div>
        <div class="pr">${mln(l.start)}<div class="muted">boshlang'ich</div></div></div>`).join('')}
    <div class="stepname in" style="--d:7;color:var(--mut)">Chiqarildi · ${no.length}</div>
    ${no.map((l, k) => `
      <div class="lot no in" style="--d:${8 + k}">${ring(l.record.onTime, l.record.onTime >= L.MIN_ON_TIME)}
        <div class="main"><div class="nm">${esc(l.seller)}</div><div class="chips">${l.reasons.map((r) => `<span class="pill r">✗ ${esc(short(r))}</span>`).join('')}</div></div>
        <div class="pr">${mln(l.start)}</div></div>`).join('')}
    <div class="muted" style="text-align:center">Doira — sotuvchi o'z vaqtida yetkazgan bitimlar ulushi (reyestr)</div>`, need);
  runCounters();
  if (adv.warn) $('#accept').onclick = (e) => { S.myBid = adv.suggested; e.target.closest('.warnbox').innerHTML = `<span style="font-size:26px">✓</span><b>Agent ${mln(S.myBid)} bilan qatnashadi</b>`; };
  root.querySelectorAll('[data-lot]').forEach((b) => b.onclick = () => { S.lot = S.lots.find((l) => l.id === b.dataset.lot); auction(); });
}

// ---------------- 3 · Auction ----------------
async function auction() {
  const lot = S.lot, SEC = 6, C = 2 * Math.PI * 66;
  const me = { name: 'Sizning agentingiz', amount: Math.max(S.myBid, lot.start), accountAgeDays: 900, linkedToSeller: false, cancelRate: 0, me: true };
  const bids = [me, ...L.otherBidders(lot, S.pass, me.amount)].map((b) => ({ ...b, salt: Math.random().toString(36).slice(2, 10) }));
  for (const b of bids) b.commit = await L.sha256(`${b.name}|${b.amount}|${b.salt}`);
  const short = (n) => n.replace('Agent · ', '').replace(' MChJ', '');
  shell(3, `${lot.id} · ${S.intent.qty} t`, 'Muhrlangan auksion', `
    <div class="arena">
      <div class="clock in" style="--d:2"><svg width="150" height="150"><circle cx="75" cy="75" r="66" stroke="rgba(255,255,255,.08)" stroke-width="8" fill="none"/>
        <circle class="p" id="cp" cx="75" cy="75" r="66" stroke="url(#cg)" stroke-width="8" fill="none" stroke-linecap="round" stroke-dasharray="${C}" stroke-dashoffset="0"/>
        <defs><linearGradient id="cg"><stop offset="0" stop-color="#33e6a0"/><stop offset="1" stop-color="#5aa9ff"/></linearGradient></defs></svg><div class="t" id="ct">${SEC}</div></div>
      <div class="muted in" style="--d:3;margin-bottom:14px" id="phase">🔒 Takliflar muhrlangan — hech kim ko'rmaydi</div>
      <div class="bids">${bids.map((b, k) => `
        <div class="bid in ${b.me ? 'me' : ''}" style="--d:${4 + k}" id="b${k}"><div class="fl">
          <div class="fa"><div class="who">${b.me ? '🧑‍💼 ' : '🤖 '}${esc(short(b.name))}</div><div style="font-size:30px">🔒</div><div class="hash">${b.commit.slice(0, 24)}…</div></div>
          <div class="ba"><div class="who">${esc(short(b.name))}</div><div class="amt">${mln(b.amount)}</div><div class="tag"></div></div>
        </div></div>`).join('')}</div>
      <div id="res" style="width:100%"></div>
      <div class="card in" style="--d:9;margin-top:16px;width:100%"><div class="how">
        <div>🔒 Har kim bitta yashirin taklif beradi</div><div>🎭 Sotuvchiga bog'liq akkaunt chiqariladi</div><div>🏆 Eng yuqori yutadi — ikkinchi narxni to'laydi</div></div></div>
    </div>`, market);
  for (let s = SEC; s > 0; s--) {
    $('#ct').textContent = s; $('#cp').style.strokeDashoffset = C * (1 - (s - 1) / SEC);
    await wait(1000); if (!$('#ct')) return;
  }
  $('#ct').textContent = '✓'; $('#phase').textContent = '🔓 Muhrlar ochilmoqda…';
  const r = L.runAuction(lot, bids); S.auction = r;
  for (let k = 0; k < bids.length; k++) {
    const b = r.all[k], el = $('#b' + k);
    el.classList.add('open'); if (b.shill) el.classList.add('shill'); if (r.winner?.name === b.name) el.classList.add('win');
    el.querySelector('.tag').innerHTML = b.shill ? '<span class="pill r">🎭 Soxta</span>' : r.winner?.name === b.name ? '<span class="pill g">🏆 G\'olib</span>' : '<span class="pill">✓ Muhr mos</span>';
    await wait(450);
  }
  $('#phase').textContent = '🎭 Soxta ishtirokchi sotuvchiga bog\'liq — chiqarildi';
  const won = r.winner?.me, saved = (r.payIfShill - r.pay) * S.intent.qty;
  $('#res').innerHTML = won ? `<div class="result"><div class="muted">Siz yutdingiz · to'laysiz</div><div class="big" id="pay">0</div><div class="muted">so'm / t · taklifingiz ${mln(r.winner.amount)}</div>
      <div style="margin:12px 0"><span class="pill g">🛡 Filtr tejadi: ${mln(saved)} so'm</span></div><button class="btn" id="deal" style="width:100%">Bitimni tasdiqlash →</button></div>`
    : `<div class="result" style="box-shadow:inset 0 0 0 1px var(--r);background:rgba(255,93,108,.08)"><div class="big">Yutmadingiz</div><div class="muted">Agent chegaradan oshmadi</div><button class="btn ghost" id="again" style="margin-top:12px">Boshqa lot</button></div>`;
  if (won) { countUp($('#pay'), r.pay); fly('✨', innerWidth / 2, innerHeight * 0.7); $('#deal').onclick = startDeal; } else $('#again').onclick = market;
  $('#res').scrollIntoView({ behavior: 'smooth', block: 'center' });
}

// ---------------- 4 · Deal ----------------
const LABEL = { agreed: 'Kelishildi', escrow: 'Pul escrowda', shipped: 'Yo\'lda', delivered: 'Yetkazildi', released: 'Yakunlandi', refunded: 'Pul qaytdi' };
const ICON = { agreed: '🤝', escrow: '🔐', shipped: '🚚', delivered: '📦', released: '✅', refunded: '↩️' };
const now = () => new Date().toLocaleTimeString('uz-UZ', { hour12: false });
const log = async (d) => { S.chain = await L.appendEvent(S.chain, { t: now(), ...d }); };

async function startDeal() {
  const r = S.auction, goods = r.pay * S.intent.qty, fee = Math.round(goods * 0.001);
  S.deal = { state: 'agreed', total: goods + fee, fee };
  S.chain = []; S.broken = false;
  await log({ e: 'agreed', lot: S.lot.id, seller: S.lot.seller, qty: S.intent.qty, price: r.pay, total: S.deal.total });
  deal();
}
async function act(ev, btn) {
  const next = L.transition(S.deal.state, ev);
  S.deal.state = next;
  await log({ e: next, ...(next === 'refunded' ? { refund: S.deal.total } : {}) });
  const rc = btn?.getBoundingClientRect();
  if (next === 'refunded') fly('💸', rc ? rc.left + rc.width / 2 : undefined, rc ? rc.top : undefined);
  if (next === 'released') fly('✅', rc ? rc.left + rc.width / 2 : undefined, rc ? rc.top : undefined);
  deal();
}

async function deal() {
  const d = S.deal, st = d.state;
  const flow = st === 'refunded' ? ['agreed', 'escrow', 'refunded'] : ['agreed', 'escrow', 'shipped', 'delivered', 'released'];
  const idx = flow.indexOf(st), valid = await L.verifyChain(S.chain);
  const acts = {
    agreed: `<button class="btn" data-a="pay">🔐 To'lash</button>`,
    escrow: `<button class="btn" data-a="ship">🚚 Jo'natildi</button><button class="btn red" data-a="deadline">⏰ Yetkazilmadi</button>`,
    shipped: `<button class="btn" data-a="confirm">📦 Qabul qildim</button><button class="btn red" data-a="deadline">⏰ Kelmadi</button>`,
    delivered: `<button class="btn" data-a="release">✅ Pulni chiqarish</button>`,
  }[st] || `<button class="btn ghost" id="restart">↻ Yangi ehtiyoj</button>`;
  const sub = { agreed: 'To\'lov escrowga tushadi', escrow: 'Sotuvchi yetkazmaguncha pul sizniki', shipped: 'Qabul qilsangiz — pul chiqadi', delivered: 'Bir bosishda yakunlanadi', released: 'Pul faqat yetkazilgandan keyin o\'tdi', refunded: 'Avtomatik. Qo\'ng\'iroq yo\'q, ariza yo\'q.' }[st];
  shell(4, `${S.lot.id} · ${esc(S.lot.seller)}`, 'Bitim', `
    <div class="card in" style="--d:2;text-align:center">
      <div class="orb s-${st}">${ICON[st]}</div>
      <div class="state">${LABEL[st]}</div>
      <div class="amount"><b id="amt" style="color:var(--ink)">${mln(d.total)}</b> so'm · ${sub}</div>
      <div class="tl">${flow.map((s, k) => `${k ? `<div class="bar ${k <= idx ? (s === 'refunded' ? 'x' : 'ok') : ''}"></div>` : ''}<div class="n ${k < idx || (k === idx && st === 'released') ? 'ok' : k === idx ? (st === 'refunded' ? 'x' : 'cur') : ''}">${k < idx || st === 'released' ? '✓' : k === idx && st === 'refunded' ? '↩' : k + 1}</div>`).join('')}</div>
      <div class="tll">${flow.map((s) => `<span>${LABEL[s]}</span>`).join('')}</div>
      <div class="acts">${acts}</div>
    </div>
    <div class="card in" style="--d:3">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px"><b>Bitim isboti</b>
        <span class="pill ${valid ? 'g' : 'r'}">${valid ? '✓ Butun' : '✗ O\'zgartirilgan!'}</span></div>
      <div class="chain ${valid ? '' : 'broken'}">${S.chain.map((c) => `<div class="blk"><b>${ICON[c.data.e]} ${LABEL[c.data.e]}</b><code>${c.data.t} · #${c.hash.slice(0, 10)}</code></div>`).join('')}</div>
      <button class="btn ghost sm" id="tamper" style="margin-top:6px">🕵️ Narxni yashirin o'zgartirib ko'ring</button>
    </div>`, market);
  root.querySelectorAll('[data-a]').forEach((b) => b.onclick = () => act(b.dataset.a, b));
  const rs = $('#restart'); if (rs) rs.onclick = () => { Object.assign(S, { intent: null, deal: null, chain: [] }); need(); };
  $('#tamper').onclick = () => { S.chain[0].data.price += 500_000; deal(); };
  if (st === 'refunded') countUp($('#amt'), d.total, 900);
}

root.innerHTML = '<div style="min-height:100vh;display:grid;place-items:center"><div class="mark" style="animation:pulse 1s infinite">A</div></div>';
fetch('market.json').then((r) => r.json()).then((d) => { M = d; landing(); })
  .catch(() => { root.innerHTML = '<div class="app"><h2 class="h">Ma\'lumot yuklanmadi</h2></div>'; });
