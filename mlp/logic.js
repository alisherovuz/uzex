// Aniq — deterministic core. AI never does arithmetic, eligibility or state changes: this file does.
// All market data here is SYNTHETIC demo data.

export function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export const PRODUCTS = [
  { id: 'ai92', name: 'Avtomobil benzini', keys: ['ai-92', 'ai92', 'аи-92', 'аи92', 'benzin', 'бензин'] },
  { id: 'diesel', name: 'Dizel yoqilg\'isi', keys: ['dizel', 'дизел', 'солярк', 'diesel'] },
  { id: 'propan', name: 'Suyultirilgan gaz', keys: ['propan', 'пропан', 'suyultirilgan gaz', 'сжиженный газ', ' gaz', ' газ'] },
  { id: 'cement', name: 'Portlandsement', keys: ['sement', 'цемент', 'm400', 'м400'] },
  { id: 'rebar', name: 'Armatura', keys: ['armatura', 'арматур', 'metall', 'металл'] },
  { id: 'wheat', name: 'Bug\'doy (oziq-ovqat)', keys: ['bug\'doy', 'bugdoy', 'пшениц', 'wheat'] },
  { id: 'sugar', name: 'Oq shakar', keys: ['shakar', 'сахар'] },
];

export const REGIONS = [
  { id: 'tashkent', name: 'Toshkent', keys: ['toshkent', 'ташкент', 'tashkent'] },
  { id: 'fergana', name: 'Farg\'ona', keys: ['farg\'ona', 'fargona', 'фергана', 'фергану'] },
  { id: 'samarkand', name: 'Samarqand', keys: ['samarqand', 'самарканд'] },
  { id: 'namangan', name: 'Namangan', keys: ['namangan', 'наманган'] },
  { id: 'andijan', name: 'Andijon', keys: ['andijon', 'андижан'] },
  { id: 'bukhara', name: 'Buxoro', keys: ['buxoro', 'бухар'] },
];

const norm = (s) => (' ' + s + ' ').toLowerCase().replace(/[ʻʼ‘’`´]/g, "'");

// Language layer (demo: rule-based, Uzbek + Russian). An LLM can replace this function;
// its output must still pass validateIntent() before anything happens.
export function parseIntent(text) {
  const t = norm(text);
  const product = PRODUCTS.find((p) => p.keys.some((k) => t.includes(k))) || null;
  const region = REGIONS.find((r) => r.keys.some((k) => t.includes(k))) || null;

  let qty = null;
  const q = t.match(/(\d+(?:[.,]\d+)?)\s*(?:tonna|tonn|тонн|тн|t\b|т\b)/);
  if (q) qty = Math.round(parseFloat(q[1].replace(',', '.')));

  let days = null;
  const d = t.match(/(\d+)\s*(?:kun|день|дня|дней|сут)/);
  if (d) days = parseInt(d[1], 10);
  else if (/hafta|недел/.test(t)) days = 7;
  else if (/ertaga|завтра/.test(t)) days = 1;

  let maxPrice = null;
  const m = t.match(/(\d[\d\s]*(?:[.,]\d+)?)\s*(mln|million|млн)?\.?\s*(?:so'm|som|сум|sum)/);
  if (m) {
    const raw = m[1].trim();
    if (m[2]) maxPrice = Math.round(parseFloat(raw.replace(/\s/g, '').replace(',', '.')) * 1_000_000);
    else maxPrice = parseInt(raw.replace(/[\s.,]/g, ''), 10);
  }
  return validateIntent({ productId: product?.id ?? null, qty, regionId: region?.id ?? null, days, maxPrice });
}

export function validateIntent(i) {
  const missing = [];
  if (!PRODUCTS.some((p) => p.id === i.productId)) missing.push('productId');
  if (!Number.isInteger(i.qty) || i.qty <= 0 || i.qty > 100_000) missing.push('qty');
  if (!REGIONS.some((r) => r.id === i.regionId)) missing.push('regionId');
  if (!Number.isInteger(i.days) || i.days <= 0 || i.days > 365) missing.push('days');
  if (!Number.isInteger(i.maxPrice) || i.maxPrice <= 0) missing.push('maxPrice');
  return { ...i, missing, complete: missing.length === 0 };
}

export const product = (id) => PRODUCTS.find((p) => p.id === id);
export const region = (id) => REGIONS.find((r) => r.id === id);

// Market facts come from the organizers' UZEX dataset (market.json, built by scripts/build_market.py):
// 120-day price range per tonne, daily medians, outlier deals with real deal numbers, seller delivery records.
export function passport(m) {
  return { median: m.median, p10: m.p10, p90: m.p90, last: m.daily.at(-1).p, n: m.n, from: m.from_, to: m.to, daily: m.daily, outliers: m.outliers, avgMarkup: m.avgMarkup };
}

export const MIN_ON_TIME = 0.88;
const r1k = (x) => Math.round(x / 1000) * 1000;

// Lots: sellers, delivery terms and delivery records are from the dataset; lot sizes and
// warehouse-receipt verification are simulated. Every exclusion carries a reason.
export function lotsFor(intent, m) {
  const top = m.sellers.slice(0, 5);
  const start = (s) => r1k(s.basis > m.median * 0.8 && s.basis < m.median * 1.15 ? s.basis : m.median * 0.97);
  const lots = top.map((s, k) => ({
    id: `LOT-${4460 + k * 7}`, seller: s.name, inn: s.inn, region: s.region,
    qty: k === 2 ? Math.max(1, Math.floor(intent.qty / 2)) : intent.qty * (2 + k),
    start: start(s), deliveryDays: s.term ?? 10,
    record: { n: s.n, onTime: s.onTime, partial: s.partial, undelivered: s.undelivered, late: s.late },
    stock: { verified: true, note: `E-ombor guvohnomasi №EW-${20900 + k * 31} (simulyatsiya)` },
  }));
  const cheapest = lots.reduce((a, b) => (b.start < a.start ? b : a));
  cheapest.stock = { verified: false, note: 'Ombor guvohnomasi taqdim etilmagan (simulyatsiya)' };
  return lots.map((l) => {
    const reasons = [];
    if (!l.stock.verified) reasons.push('Zaxira tasdiqlanmagan — tovar mavjudligi isbotlanmagan');
    if (l.record.onTime < MIN_ON_TIME) reasons.push(`Yetkazish tarixi past: ${(l.record.onTime * 100).toFixed(1)}% o'z vaqtida (talab ≥ ${MIN_ON_TIME * 100}%)`);
    if (l.qty < intent.qty) reasons.push(`Hajm yetarli emas: ${l.qty} t < ${intent.qty} t`);
    if (l.deliveryDays > intent.days) reasons.push(`Shartnoma bo'yicha yetkazish ${l.deliveryDays} kun > sizning muddatingiz ${intent.days} kun`);
    if (l.start > intent.maxPrice) reasons.push('Boshlang\'ich narx sizning chegarangizdan yuqori');
    return { ...l, eligible: reasons.length === 0, reasons };
  });
}

// Agent advice: never bid above the user's limit; warn if the limit is above the fair range.
export function agentBid(intent, pass) {
  const cap = intent.maxPrice;
  const warn = cap > pass.p90 * 1.03;
  return { bid: cap, warn, suggested: warn ? Math.round(pass.p90 / 1000) * 1000 : cap };
}

// Other participants (synthetic). One is a shill linked to the seller.
export function otherBidders(lot, pass, userBid) {
  const r = rng(lot.start % 7919);
  const base = Math.max(lot.start, pass.median * 0.97);
  const mk = (name, f, meta) => ({ name, amount: Math.max(lot.start, Math.round((base * f) / 1000) * 1000), ...meta });
  return [
    mk('Agent · Namangan Qurilish MChJ', 1.004 + r() * 0.006, { accountAgeDays: 1460, linkedToSeller: false, cancelRate: 0.02 }),
    mk('Agent · Andijon Agro Trans', 1.012 + r() * 0.008, { accountAgeDays: 820, linkedToSeller: false, cancelRate: 0.0 }),
    mk('Agent · Buxoro Avto Servis', 1.0 + r() * 0.004, { accountAgeDays: 2100, linkedToSeller: false, cancelRate: 0.05 }),
    { name: 'Agent · Yangi Biznes Plyus MChJ', amount: Math.max(lot.start, userBid - 15_000), accountAgeDays: 2, linkedToSeller: true, cancelRate: 0.6 },
  ];
}

export function shillReasons(b) {
  const r = [];
  if (b.linkedToSeller) r.push('Sotuvchi bilan bog\'liq (bir xil STIR/telefon)');
  if (b.accountAgeDays < 7) r.push(`Akkaunt ${b.accountAgeDays} kunlik`);
  if (b.cancelRate > 0.3) r.push(`Avvalgi bitimlarning ${Math.round(b.cancelRate * 100)}% bekor qilingan`);
  return r;
}
export const isShill = (b) => b.linkedToSeller || (b.accountAgeDays < 7 && b.cancelRate > 0.3);

// Sealed-bid, second-price (Vickrey). Highest valid bid wins; pays max(second valid bid, start price).
export function runAuction(lot, bids) {
  const all = bids.map((b) => ({ ...b, shill: isShill(b), reasons: shillReasons(b), belowStart: b.amount < lot.start }));
  const valid = all.filter((b) => !b.shill && !b.belowStart).sort((a, b) => b.amount - a.amount || a.name.localeCompare(b.name));
  if (!valid.length) return { all, valid, winner: null, pay: null, payIfShill: null };
  const winner = valid[0];
  const pay = Math.max(valid[1]?.amount ?? lot.start, lot.start);
  const others = all.filter((b) => b !== all.find((x) => x.name === winner.name) && !b.belowStart).map((b) => b.amount);
  const payIfShill = Math.max(Math.max(...others, lot.start), lot.start);
  return { all, valid, winner, pay, payIfShill: Math.min(payIfShill, winner.amount) };
}

// Deal state machine. Invalid transitions throw.
export const STATES = ['agreed', 'escrow', 'shipped', 'delivered', 'released', 'refunded'];
const T = {
  agreed: { pay: 'escrow' },
  escrow: { ship: 'shipped', deadline: 'refunded' },
  shipped: { confirm: 'delivered', deadline: 'refunded' },
  delivered: { release: 'released' },
};
export function transition(state, event) {
  const next = T[state]?.[event];
  if (!next) throw new Error(`Ruxsat etilmagan o'tish: ${state} → ${event}`);
  return next;
}

export async function sha256(s) {
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s));
  return [...new Uint8Array(buf)].map((x) => x.toString(16).padStart(2, '0')).join('');
}
export async function appendEvent(chain, data) {
  const prev = chain.at(-1)?.hash ?? '0'.repeat(64);
  const body = JSON.stringify(data);
  return [...chain, { data, prev, hash: await sha256(prev + body) }];
}
export async function verifyChain(chain) {
  let prev = '0'.repeat(64);
  for (const e of chain) {
    if (e.prev !== prev || e.hash !== (await sha256(prev + JSON.stringify(e.data)))) return false;
    prev = e.hash;
  }
  return true;
}

export const fmt = (n) => new Intl.NumberFormat('ru-RU').format(n).replace(/ /g, ' ');
