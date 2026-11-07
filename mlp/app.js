import * as L from './logic.js';

const $ = (s) => document.querySelector(s);
const view = $('#view');
let M = null;
const S = { intent: null, pass: null, hist: null, lots: null, lot: null, myBid: null, auction: null, deal: null, chain: [] };
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const som = (n) => `${L.fmt(n)} so'm`;

function steps(k) {
  [1, 2, 3, 4].forEach((i) => { const e = $('#s' + i); e.className = 'step' + (i === k ? ' on' : i < k ? ' done' : ''); });
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

const EXAMPLES = [
  "Farg'onaga 20 tonna AI-92 benzin kerak, 20 kun ichida, tonnasi 17 mln so'mdan oshmasin",
  'Нужно 50 тонн цемента в Ташкент за 20 дней, не дороже 1 000 000 сум за тонну',
  "Samarqandga 30 tonna bug'doy kerak, 15 kun ichida",
];

// ---------- Step 1 ----------
function renderNeed() {
  steps(1);
  view.innerHTML = `
  <div class="grid g4" style="margin-bottom:16px">
    ${[
      ['Narxga ishonch yo\'q: 1–2 taklif bilan narx ko\'tariladi', 'Narx pasporti: real tarix, shubhali sakrashlar belgilanadi'],
      ['Mavjud bo\'lmagan tovar sotiladi, jo\'natma bo\'lmaydi', 'Faqat ombor guvohnomasi bilan tasdiqlangan lotlar'],
      ['Soxta xaridorlar narxni sun\'iy oshiradi', 'Muhrlangan takliflar + 2-narx qoidasi + shill-filtr'],
      ['Pul qaytmaydi, call-markazga tushib bo\'lmaydi', 'Escrow: yetkazilmasa — avtomatik qaytarish'],
    ].map(([p, s]) => `<div class="prob"><div class="p">${p}</div><div class="s">→ ${s}</div></div>`).join('')}
  </div>
  <div class="card">
    <h2>Nima kerak? Oddiy tilda yozing</h2>
    <p class="sub">O'zbek yoki rus tilida. Birja terminalini bilish shart emas — agent sizning nomingizdan ishlaydi, lekin faqat siz belgilagan chegaralar ichida.</p>
    <textarea id="need" placeholder="Masalan: Farg'onaga 20 tonna AI-92 kerak, 20 kun ichida, tonnasi 17 mln so'mdan oshmasin"></textarea>
    <div class="chips">${EXAMPLES.map((e, i) => `<button class="chip" data-ex="${i}">${esc(e)}</button>`).join('')}</div>
    <button id="parse">Tushunish →</button>
    <div id="confirm"></div>
  </div>`;
  view.querySelectorAll('[data-ex]').forEach((b) => b.onclick = () => { $('#need').value = EXAMPLES[b.dataset.ex]; $('#parse').click(); });
  $('#parse').onclick = () => {
    const txt = $('#need').value.trim();
    if (!txt) return;
    renderConfirm(L.parseIntent(txt));
  };
}

function renderConfirm(i) {
  const miss = (k) => (i.missing.includes(k) ? ' miss' : '');
  $('#confirm').innerHTML = `
  <hr style="border:0;border-top:1px solid var(--line);margin:18px 0">
  <h3>Agent topshirig'i (mandat) — tasdiqlang</h3>
  <p class="sub">${i.complete ? 'Hammasi tushunildi. Tekshirib, tasdiqlang.' : '<b style="color:var(--warn)">Ba\'zi ma\'lumotlar topilmadi — agent taxmin qilmaydi.</b> Sariq maydonlarni to\'ldiring.'}</p>
  <div class="grid g4">
    <label class="field${miss('productId')}">Tovar<select id="f-p"><option value="">—</option>${L.PRODUCTS.map((p) => `<option value="${p.id}" ${p.id === i.productId ? 'selected' : ''}>${p.name}</option>`).join('')}</select></label>
    <label class="field${miss('qty')}">Hajm (tonna)<input id="f-q" type="number" min="1" value="${i.qty ?? ''}"></label>
    <label class="field${miss('regionId')}">Manzil<select id="f-r"><option value="">—</option>${L.REGIONS.map((r) => `<option value="${r.id}" ${r.id === i.regionId ? 'selected' : ''}>${r.name}</option>`).join('')}</select></label>
    <label class="field${miss('days')}">Muddat (kun)<input id="f-d" type="number" min="1" value="${i.days ?? ''}"></label>
  </div>
  <div class="grid g2" style="margin-top:12px">
    <label class="field${miss('maxPrice')}">Maksimal narx, so'm / tonna (agent bundan oshirolmaydi)<input id="f-m" type="number" min="1" value="${i.maxPrice ?? ''}"></label>
    <div class="note" style="align-self:end">🔒 Chegaralar kodda qulflanadi: agent hajmni, tovar navini yoki narx chegarasini o'zi o'zgartira olmaydi.</div>
  </div>
  <div class="row" style="margin-top:14px"><button id="go">Mandatni tasdiqlash va lotlarni topish →</button></div>`;
  $('#go').onclick = () => {
    const v = L.validateIntent({
      productId: $('#f-p').value || null, qty: parseInt($('#f-q').value, 10), regionId: $('#f-r').value || null,
      days: parseInt($('#f-d').value, 10), maxPrice: parseInt($('#f-m').value, 10),
    });
    if (!v.complete) return renderConfirm(v);
    S.intent = v; renderLots();
  };
}

// ---------- Step 2 ----------
function spark(pass) {
  const W = 1000, H = 220, pad = 34, D = pass.daily;
  const xs = (k) => pad + (k / (D.length - 1)) * (W - pad * 2);
  const ps = D.map((h) => h.p).concat([pass.p10, pass.p90]), lo = Math.min(...ps) * 0.98, hi = Math.max(...ps) * 1.02;
  const ys = (p) => H - pad - ((p - lo) / (hi - lo)) * (H - pad * 2);
  const path = D.map((h, k) => `${k ? 'L' : 'M'}${xs(k).toFixed(1)},${ys(h.p).toFixed(1)}`).join('');
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Kunlik median narx">
    <rect x="${pad}" y="${ys(pass.p90)}" width="${W - pad * 2}" height="${ys(pass.p10) - ys(pass.p90)}" fill="#e8f3ee"/>
    <line x1="${pad}" x2="${W - pad}" y1="${ys(pass.median)}" y2="${ys(pass.median)}" stroke="#0b6e4f" stroke-dasharray="5 5"/>
    <path d="${path}" fill="none" stroke="#0f1b2d" stroke-width="2.5"/>
    <text x="${pad}" y="16" font-size="15" fill="#5b6778">Kunlik median narx, so'm/t · oxirgi ${D.length} savdo kuni · yashil: P10–P90 oralig'i</text>
    <text x="${pad}" y="${H - 8}" font-size="14" fill="#5b6778">${D[0].d}</text><text x="${W - pad}" y="${H - 8}" font-size="14" fill="#5b6778" text-anchor="end">${D.at(-1).d}</text>
  </svg>`;
}

function renderLots() {
  steps(2);
  const i = S.intent, p = L.product(i.productId);
  S.pass = L.passport(M[i.productId]); S.lots = L.lotsFor(i, M[i.productId]);
  const ok = S.lots.filter((l) => l.eligible);
  const adv = L.agentBid(i, S.pass);
  S.myBid = adv.bid;
  view.innerHTML = `
  <div class="card">
    <h2>Narx pasporti · ${p.name}</h2>
    <p class="sub">Tashkilotchilar bergan UZEX bitimlar reyestridan hisoblangan: ${L.fmt(S.pass.n)} ta bitim, ${S.pass.from} — ${S.pass.to}, ichki spot, bekor qilinganlar chiqarilgan. AI raqam o'ylab topmaydi.</p>
    <div class="grid g4">
      <div><div class="muted">Median</div><div class="big">${som(S.pass.median)}</div></div>
      <div><div class="muted">Odatiy oraliq (P10–P90)</div><div class="big" style="font-size:17px">${L.fmt(S.pass.p10)} – ${L.fmt(S.pass.p90)}</div></div>
      <div><div class="muted">Oxirgi kun mediani</div><div class="big">${som(S.pass.last)}</div></div>
      <div><div class="muted">Sizning chegarangiz</div><div class="big">${som(i.maxPrice)}</div></div>
    </div>
    ${spark(S.pass)}
    <div class="note w">⚠️ <b>Odatiy oraliqdan ancha yuqori bitimlar</b> (P90 dan 12%+ yuqori) — tekshiruv uchun belgilandi. Raqamlarni reyestrda tekshirish mumkin:
      <table style="margin-top:6px"><thead><tr><th>Bitim №</th><th>Sana</th><th>Boshlang'ich</th><th>Yakuniy narx/t</th><th>Ustama</th></tr></thead><tbody>
      ${S.pass.outliers.map((o) => `<tr><td class="mono">${o.id}</td><td>${o.d}</td><td>${L.fmt(o.start)}</td><td><b>${L.fmt(o.p)}</b></td><td style="color:var(--bad)">+${Math.round(o.markup * 100)}%</td></tr>`).join('')}
      </tbody></table></div>
    ${adv.warn ? `<div class="note r" style="margin-top:10px">Sizning chegarangiz odatiy oraliqdan <b>${Math.round((i.maxPrice / S.pass.p90 - 1) * 100)}%</b> yuqori. Agent tavsiyasi: <b>${som(adv.suggested)}</b>.
      <div class="row" style="margin-top:8px"><button class="sec" id="keep">O'z chegaramni qoldiraman</button><button id="accept">Tavsiyani qabul qilaman</button></div></div>` : ''}
  </div>
  <div class="card">
    <h2>Lotlar: ${ok.length} ta mos, ${S.lots.length - ok.length} ta chiqarildi</h2>
    <p class="sub">Qoidalar hamma uchun bir xil. Sotuvchi, STIR, shartnoma muddati va yetkazish tarixi — reyestrdan. Lot hajmi va ombor guvohnomasi — simulyatsiya.</p>
    <div class="grid">${S.lots.map((l) => `
      <div class="lot ${l.eligible ? '' : 'no'}">
        <div>
          <div><b>${l.id}</b> · ${esc(l.seller)} ${l.stock.verified ? '<span class="badge b-ok">✓ Zaxira tasdiqlangan</span>' : '<span class="badge b-no">✗ Zaxira tasdiqlanmagan</span>'}</div>
          <div class="muted">STIR ${l.inn} · ${esc(l.region)} · ${l.qty} t (simulyatsiya) · shartnoma: to'lovdan keyin ${l.deliveryDays} kunda yetkazish</div>
          <div class="muted">Yetkazish tarixi (reyestr): <b style="color:${l.record.onTime >= L.MIN_ON_TIME ? 'var(--good)' : 'var(--bad)'}">${(l.record.onTime * 100).toFixed(1)}% o'z vaqtida</b> · ${l.record.n} ta to'langan bitim · ${l.record.late} kechikkan · ${l.record.partial} qisman · ${l.record.undelivered} to'langan, yetkazilmagan</div>
          <div class="muted">${esc(l.stock.note)}</div>
          ${l.reasons.map((r) => `<div class="why muted">✗ ${esc(r)}</div>`).join('')}
        </div>
        <div style="text-align:right"><div class="muted">Boshlang'ich narx</div><div class="big" style="font-size:18px">${som(l.start)}</div>
          ${l.eligible ? `<button data-lot="${l.id}" style="margin-top:8px">Auksionga kirish →</button>` : ''}</div>
      </div>`).join('')}
    </div>
  </div>`;
  if (adv.warn) {
    $('#keep').onclick = (e) => { S.myBid = i.maxPrice; e.target.closest('.note').innerHTML = `Agent sizning chegarangiz bilan qatnashadi: <b>${som(S.myBid)}</b>.`; };
    $('#accept').onclick = (e) => { S.myBid = adv.suggested; e.target.closest('.note').innerHTML = `✓ Agent taklifi: <b>${som(S.myBid)}</b> (sizning chegarangizdan past).`; };
  }
  view.querySelectorAll('[data-lot]').forEach((b) => b.onclick = () => { S.lot = S.lots.find((l) => l.id === b.dataset.lot); renderAuction(); });
}

// ---------- Step 3 ----------
async function renderAuction() {
  steps(3);
  const lot = S.lot;
  const me = { name: 'Sizning agentingiz', amount: Math.max(S.myBid, lot.start), accountAgeDays: 900, linkedToSeller: false, cancelRate: 0, me: true };
  const bids = [me, ...L.otherBidders(lot, S.pass, me.amount)];
  const commits = await Promise.all(bids.map(async (b, k) => ({ ...b, salt: Math.random().toString(36).slice(2, 10), k })));
  for (const c of commits) c.commit = await L.sha256(`${c.name}|${c.amount}|${c.salt}`);
  view.innerHTML = `
  <div class="card">
    <div class="row" style="justify-content:space-between;flex-wrap:nowrap;align-items:flex-start">
      <div style="flex:1"><h2>Muhrlangan auksion · ${lot.id}</h2>
      <p class="sub">${S.intent.qty} t · ${esc(lot.seller)} · boshlang'ich ${som(lot.start)}. Har bir agent <b>bitta yashirin</b> taklif beradi. Hech kim boshqalarning taklifini ko'rmaydi — shuning uchun "narxni ko'tarib qo'yish" ishlamaydi.</p></div>
      <div style="text-align:right;min-width:120px"><div class="muted">Yopilishigacha</div><div class="timer" id="timer">0:08</div></div>
    </div>
    <table><thead><tr><th>Ishtirokchi</th><th>Muhr (SHA-256 majburiyat)</th><th>Taklif</th><th>Tekshiruv</th></tr></thead><tbody id="tb"></tbody></table>
    <div id="result"></div>
  </div>
  <div class="card"><h3>Qoidalar (oldindan e'lon qilingan)</h3>
    <div class="muted">1) Har bir agent bitta muhrlangan taklif beradi; muhr = SHA-256(ishtirokchi | summa | tuz). Ochilganda muhr qayta hisoblanadi.<br>
    2) Sotuvchi bilan bog'liq yoki yangi + ko'p bekor qiluvchi akkauntlar chiqariladi (sababi ko'rsatiladi).<br>
    3) Eng yuqori haqiqiy taklif yutadi va <b>ikkinchi eng yuqori haqiqiy narxni</b> to'laydi (Vickrey). Shuning uchun haqiqiy chegarani aytish — eng to'g'ri strategiya; blef foyda bermaydi.<br>
    4) Agent foydalanuvchi chegarasidan oshib taklif bera olmaydi — bu kodda tekshiriladi.</div></div>`;
  const tb = $('#tb');
  commits.forEach((c, k) => setTimeout(() => {
    tb.insertAdjacentHTML('beforeend', `<tr id="r${k}"><td>${esc(c.name)}</td><td class="mono">${c.commit.slice(0, 20)}…</td><td>🔒 yashirin</td><td class="r muted">kutilmoqda</td></tr>`);
  }, 350 * k));
  let left = 8;
  const iv = setInterval(async () => {
    left--; $('#timer').textContent = `0:0${Math.max(left, 0)}`;
    if (left > 0) return;
    clearInterval(iv);
    $('#timer').textContent = 'Yopildi';
    const r = L.runAuction(lot, commits);
    S.auction = r;
    for (const c of commits) {
      const ok = (await L.sha256(`${c.name}|${c.amount}|${c.salt}`)) === c.commit;
      const b = r.all.find((x) => x.name === c.name);
      const row = $('#r' + c.k);
      row.className = b.shill ? 'shill' : r.winner?.name === c.name ? 'win' : '';
      row.children[2].textContent = som(c.amount);
      row.children[3].innerHTML = b.shill ? `<span class="badge b-no">Chiqarildi</span><div style="font-size:12px">${b.reasons.map(esc).join('; ')}</div>`
        : `<span class="badge b-ok">${ok ? 'Muhr mos ✓' : 'Muhr mos emas'}</span>${r.winner?.name === c.name ? ' <span class="badge b-ok">G\'olib</span>' : ''}`;
    }
    const won = r.winner?.me;
    const saved = (r.payIfShill - r.pay) * S.intent.qty;
    $('#result').innerHTML = won ? `
      <div class="note g" style="margin-top:14px"><b>Siz yutdingiz.</b> Sizning taklifingiz: ${som(r.winner.amount)}/t. Siz to'laysiz: <b>${som(r.pay)}/t</b> — ikkinchi eng yuqori haqiqiy taklif.
      <br>Soxta ishtirokchi hisobga olinganda narx ${som(r.payIfShill)}/t bo'lardi. Filtr sizga <b>${som(saved)}</b> tejadi (${S.intent.qty} t uchun).</div>
      <div class="row" style="margin-top:12px"><button id="deal">Bitimni tasdiqlash va escrowga o'tish →</button></div>`
      : `<div class="note r" style="margin-top:14px"><b>Siz yutmadingiz.</b> G'olib taklifi sizning chegarangizdan yuqori edi. Agent chegaradan oshmadi — bu qoida. <button class="sec" id="back">Orqaga</button></div>`;
    if (won) $('#deal').onclick = startDeal; else $('#back').onclick = renderLots;
  }, 1000);
}

// ---------- Step 4 ----------
const LABEL = { agreed: 'Kelishildi', escrow: 'Pul escrowda', shipped: 'Jo\'natildi', delivered: 'Yetkazildi', released: 'Pul sotuvchiga', refunded: 'Pul qaytarildi' };
const now = () => new Date().toLocaleString('uz-UZ', { hour12: false });

async function log(data) { S.chain = await L.appendEvent(S.chain, { t: now(), ...data }); }

async function startDeal() {
  steps(4);
  const r = S.auction, i = S.intent;
  const goods = r.pay * i.qty, fee = Math.round(goods * 0.001);
  S.deal = { state: 'agreed', goods, fee, total: goods + fee, deadline: S.lot.deliveryDays };
  S.chain = [];
  await log({ e: 'agreed', lot: S.lot.id, seller: S.lot.seller, qty: i.qty, price: r.pay, total: S.deal.total });
  renderDeal();
}

async function act(event) {
  try {
    const next = L.transition(S.deal.state, event);
    S.deal.state = next;
    const msg = { pay: 'Xaridor to\'lovi escrow hisobiga tushdi', ship: 'Sotuvchi jo\'natdi (yuk xati №TTN-55102)', confirm: 'Xaridor yetkazilganini tasdiqladi', release: 'Pul sotuvchiga o\'tkazildi', deadline: `Yetkazish muddati (${S.deal.deadline} kun) o'tdi — avtomatik qaytarish` }[event];
    await log({ e: next, note: msg, ...(next === 'refunded' ? { refund: S.deal.total } : {}) });
  } catch (err) { alertBox(err.message); }
  renderDeal();
}
function alertBox(m) { const n = $('#err'); if (n) n.textContent = m; }

async function renderDeal() {
  const d = S.deal, i = S.intent, st = d.state;
  const flow = st === 'refunded' ? ['agreed', 'escrow', 'refunded'] : ['agreed', 'escrow', 'shipped', 'delivered', 'released'];
  const idx = flow.indexOf(st);
  const valid = await L.verifyChain(S.chain);
  const btn = {
    agreed: `<button id="b-pay">To'lash (escrowga)</button>`,
    escrow: `<button id="b-ship">Sotuvchi jo'natdi</button> <button class="bad" id="b-dl">Sotuvchi yetkazmadi — muddat o'tdi</button>`,
    shipped: `<button class="good" id="b-cf">Yetkazildi, tasdiqlayman</button> <button class="bad" id="b-dl">Yetib kelmadi — muddat o'tdi</button>`,
    delivered: `<button class="good" id="b-rel">Pulni sotuvchiga chiqarish</button>`,
  }[st] || '';
  view.innerHTML = `
  <div class="card">
    <h2>Bitim · ${S.lot.id} · ${L.product(i.productId).name}</h2>
    <p class="sub">${i.qty} t × ${som(S.auction.pay)} · sotuvchi: ${esc(S.lot.seller)} · manzil: ${L.region(i.regionId).name}</p>
    <div class="grid g4">
      <div><div class="muted">Tovar</div><div class="big" style="font-size:18px">${som(d.goods)}</div></div>
      <div><div class="muted">Birja yig'imi (demo stavka 0,1%)</div><div class="big" style="font-size:18px">${som(d.fee)}</div></div>
      <div><div class="muted">Jami</div><div class="big" style="font-size:18px">${som(d.total)}</div></div>
      <div><div class="muted">Holat</div><div class="big" style="font-size:18px;color:${st === 'refunded' ? 'var(--bad)' : st === 'released' ? 'var(--good)' : 'var(--ink)'}">${LABEL[st]}</div></div>
    </div>
    <div class="tl">${flow.map((s, k) => `<div class="${k < idx ? 'ok' : k === idx ? (s === 'refunded' ? 'x' : st === 'released' ? 'ok' : 'cur') : ''}">${LABEL[s]}</div>`).join('')}</div>
    ${st === 'refunded' ? `<div class="note r"><b>${som(d.total)} xaridorga avtomatik qaytarildi.</b> Call-markazga qo'ng'iroq, ariza yoki kutish kerak emas. Sotuvchining ishonch reytingi pasaytirildi; holat inson ko'rib chiqishi uchun ochildi.</div>` : ''}
    ${st === 'released' ? `<div class="note g"><b>Bitim yakunlandi.</b> Pul faqat yetkazish tasdiqlangandan keyin sotuvchiga o'tdi.</div>` : ''}
    <div class="row" style="margin-top:12px">${btn}</div><div id="err" class="muted" style="color:var(--bad)"></div>
  </div>
  <div class="card">
    <h3>Bitim isboti (hash-zanjir)</h3>
    <p class="sub">Har bir voqea oldingisining hashi bilan bog'langan. Bitta raqam o'zgartirilsa — zanjir buziladi. Shikoyat yoki nazorat uchun tayyor dalil.</p>
    <ol class="log">${S.chain.map((c) => `<li><b>${LABEL[c.data.e] || c.data.e}</b> · ${esc(c.data.t)}${c.data.note ? ' · ' + esc(c.data.note) : ''} <span class="mono muted">#${c.hash.slice(0, 12)}</span></li>`).join('')}</ol>
    <div class="row"><span class="badge ${valid ? 'b-ok' : 'b-no'}">${valid ? '✓ Zanjir butun — yozuvlar o\'zgartirilmagan' : '✗ Zanjir buzilgan — yozuv o\'zgartirilgan!'}</span>
    <button class="sec" id="tamper">Sinab ko'ring: narxni yashirincha o'zgartirish</button>
    <button class="sec" id="restart">Yangi ehtiyoj</button></div>
  </div>`;
  const on = (id, ev) => { const b = $(id); if (b) b.onclick = () => act(ev); };
  on('#b-pay', 'pay'); on('#b-ship', 'ship'); on('#b-cf', 'confirm'); on('#b-rel', 'release'); on('#b-dl', 'deadline');
  $('#tamper').onclick = () => { S.chain[0].data.price = S.chain[0].data.price + 500_000; renderDeal(); };
  $('#restart').onclick = () => { Object.assign(S, { intent: null, deal: null, chain: [] }); renderNeed(); };
}

fetch('market.json').then((r) => r.json()).then((d) => { M = d; renderNeed(); }).catch(() => { view.innerHTML = '<div class="card">Bozor ma\'lumotini yuklab bo\'lmadi.</div>'; });
