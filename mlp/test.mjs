import assert from 'node:assert/strict';
import * as L from './logic.js';
import { readFileSync } from 'node:fs';
const M = JSON.parse(readFileSync(new URL('./market.json', import.meta.url)));

let n = 0;
const t = async (name, fn) => { await fn(); n++; console.log('ok', name); };

await t('parse Uzbek full intent', () => {
  const i = L.parseIntent("Farg'onaga 20 tonna AI-92 benzin kerak, 20 kun ichida, tonnasi 17 mln so'mdan oshmasin");
  assert.deepEqual([i.productId, i.qty, i.regionId, i.days, i.maxPrice, i.complete], ['ai92', 20, 'fergana', 20, 17_000_000, true]);
});
await t('parse Russian full intent', () => {
  const i = L.parseIntent('Нужно 50 тонн цемента в Ташкент за 20 дней, не дороже 1 000 000 сум за тонну');
  assert.deepEqual([i.productId, i.qty, i.regionId, i.days, i.maxPrice, i.complete], ['cement', 50, 'tashkent', 20, 1_000_000, true]);
});
await t('missing price is reported, not invented', () => {
  const i = L.parseIntent("Samarqandga 30 tonna bug'doy kerak, 15 kun ichida");
  assert.equal(i.productId, 'wheat'); assert.equal(i.maxPrice, null); assert.deepEqual(i.missing, ['maxPrice']);
});
await t('garbage input is incomplete', () => {
  assert.equal(L.parseIntent('salom').complete, false);
});

const intent = L.parseIntent("Farg'onaga 20 tonna AI-92 benzin kerak, 20 kun ichida, tonnasi 17 mln so'mdan oshmasin");
const pass = L.passport(M.ai92);
const lots = L.lotsFor(intent, M.ai92);
console.table(lots.map((l) => ({ id: l.id, seller: l.seller.slice(0, 22), start: l.start, onTime: l.record.onTime, term: l.deliveryDays, ok: l.eligible, why: l.reasons.join(' | ').slice(0, 60) })));

await t('passport has a real range and outlier deals with deal numbers', () => {
  assert.ok(pass.p10 <= pass.median && pass.median <= pass.p90);
  assert.ok(pass.outliers.length > 0 && pass.outliers.every((o) => o.p > pass.p90 && /^\d+$/.test(o.id)));
});
await t('every product in the parser has market data', () => {
  for (const p of L.PRODUCTS) assert.ok(M[p.id]?.sellers.length >= 4, p.id);
});
await t('unverified-stock lot is excluded even though cheapest', () => {
  const cheapest = [...lots].sort((a, b) => a.start - b.start)[0];
  assert.equal(cheapest.eligible, false);
  assert.match(cheapest.reasons[0], /Zaxira tasdiqlanmagan/);
  assert.ok(lots.filter((l) => l.eligible).length >= 1);
  assert.ok(lots.every((l) => l.eligible || l.reasons.length > 0));
});
await t('auction: shill excluded, winner pays second valid price', () => {
  const lot = lots.find((l) => l.eligible);
  const me = { name: 'Siz', amount: intent.maxPrice, accountAgeDays: 900, linkedToSeller: false, cancelRate: 0 };
  const bids = [me, ...L.otherBidders(lot, pass, me.amount)];
  const r = L.runAuction(lot, bids);
  assert.equal(r.winner.name, 'Siz');
  assert.equal(r.all.filter((b) => b.shill).length, 1);
  const secondValid = r.valid[1].amount;
  assert.equal(r.pay, Math.max(secondValid, lot.start));
  assert.ok(r.payIfShill > r.pay, 'shill would have raised the price');
  assert.ok(r.pay <= me.amount);
});
await t('single valid bidder pays the start price', () => {
  const lot = { start: 1000 };
  const r = L.runAuction(lot, [{ name: 'A', amount: 5000, accountAgeDays: 100, linkedToSeller: false, cancelRate: 0 }]);
  assert.equal(r.pay, 1000);
});
await t('bids below start price are ignored', () => {
  const r = L.runAuction({ start: 1000 }, [{ name: 'A', amount: 900, accountAgeDays: 100, linkedToSeller: false, cancelRate: 0 }]);
  assert.equal(r.winner, null);
});
await t('state machine: happy path and refund path', () => {
  let s = 'agreed';
  for (const e of ['pay', 'ship', 'confirm', 'release']) s = L.transition(s, e);
  assert.equal(s, 'released');
  assert.equal(L.transition(L.transition('agreed', 'pay'), 'deadline'), 'refunded');
  assert.throws(() => L.transition('released', 'deadline'));
  assert.throws(() => L.transition('agreed', 'release'));
});
await t('hash chain verifies and detects tampering', async () => {
  let c = [];
  c = await L.appendEvent(c, { e: 'agreed', amount: 100 });
  c = await L.appendEvent(c, { e: 'escrow' });
  assert.equal(await L.verifyChain(c), true);
  c[0].data.amount = 99;
  assert.equal(await L.verifyChain(c), false);
});
console.log(`\n${n} tests passed`);
