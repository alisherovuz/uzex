import sys, json, re, pandas as pd, numpy as np
src, out = sys.argv[1], sys.argv[2]
END = pd.Timestamp('2026-10-30')
deals = pd.concat([pd.read_csv(f'{src}/deals_{y}.csv', dtype=str) for y in (2025, 2026)])
con = pd.read_csv(f'{src}/contracts.csv', dtype=str)
par = pd.read_csv(f'{src}/participants.csv', dtype=str).drop_duplicates('ИНН').set_index('ИНН')['Наименование']
num = lambda s: pd.to_numeric(s.str.replace(' ', '', regex=False), errors='coerce')
d = deals[(deals['Тип контракта'] == 'Внутренний') & (deals['Форма контракта'] == 'Спот')].copy()
d = d[d['Единица измерения'].isin(['тонна', 'килограмм'])]
k = np.where(d['Единица измерения'] == 'килограмм', 1000, 1)
d['vol_t'] = num(d['Количество']) * num(d['Лот']) / k
d['sum'] = num(d['Сумма сделки']); d['start_t'] = num(d['Стартовая цена']) * k
d['price_t'] = d['sum'] / d['vol_t']
d['date'] = pd.to_datetime(d['Дата сделки'], format='%d.%m.%Y')
d['paid'] = pd.to_datetime(d['Дата оплаты'], format='%d.%m.%Y', errors='coerce')
d['deliv'] = pd.to_datetime(d['Дата поставки'], format='%d.%m.%Y', errors='coerce')
c = con.set_index('Номер контракта')
d['term'] = pd.to_numeric(d['Номер контракта'].map(c['Срок поставки']), errors='coerce')
d['basis_t'] = pd.to_numeric(d['Номер контракта'].map(c['Базисная цена']), errors='coerce') * k
d['due'] = d['paid'] + pd.to_timedelta(d['term'], unit='D')
P = {
 'ai92': r'бензин', 'diesel': r'дизельн', 'propan': r'сжижен', 'cement': r'цемент',
 'rebar': r'арматур', 'wheat': r'пшениц', 'sugar': r'сахар',
}
res = {}
for pid, rx in P.items():
    x = d[d['Наименование товара'].str.contains(rx, case=False, regex=True, na=False)].dropna(subset=['price_t'])
    x = x[x['price_t'] > 0]
    ok = x[x['Состояние сделки'] != 'Аннулирован(Не оплачен)']
    w = ok[ok['date'] > END - pd.Timedelta(days=120)]
    daily = w.groupby('date').agg(price=('price_t', 'median'), n=('price_t', 'size'), vol=('vol_t', 'sum')).reset_index().tail(60)
    p10, p50, p90 = np.percentile(w['price_t'], [10, 50, 90])
    w = w.assign(markup=w['price_t'] / w['start_t'] - 1)
    out_deals = w[(w['price_t'] > p90 * 1.12)].sort_values('price_t', ascending=False).head(5)
    # seller delivery record: paid deals whose delivery deadline has passed
    due = x[x['paid'].notna() & (x['due'] < END)]
    g = []
    for inn, s in due.groupby('ИНН продавца'):
        if len(s) < 5: continue
        full = s['Состояние сделки'].eq('Исполнен')
        on_time = full & (s['deliv'] <= s['due'])
        partial = s['Состояние сделки'].eq('Исполнен(Частично)')
        undeliv = s['Состояние сделки'].eq('Оплачен')
        latest = x[x['ИНН продавца'] == inn].sort_values('date').iloc[-1]
        g.append(dict(inn=inn, name=str(par.get(inn, inn)), n=int(len(s)), onTime=round(on_time.mean(), 3),
                      partial=int(partial.sum()), undelivered=int(undeliv.sum()), late=int((full & ~on_time).sum()),
                      region=latest['Регион'], basis=int(round(latest['basis_t'] if pd.notna(latest['basis_t']) else latest['start_t'])),
                      term=int(latest['term']) if pd.notna(latest['term']) else None, product=latest['Наименование товара'][:80]))
    g = sorted(g, key=lambda r: -r['n'])
    res[pid] = dict(
        n=int(len(w)), from_=str(w['date'].min().date()), to=str(w['date'].max().date()),
        p10=int(p10), median=int(p50), p90=int(p90), avgMarkup=round(float(w['markup'].median()), 4),
        daily=[dict(d=str(r.date.date()), p=int(r.price), n=int(r.n)) for r in daily.itertuples()],
        outliers=[dict(id=r['Номер сделки'], d=str(r['date'].date()), p=int(r['price_t']), start=int(r['start_t']), markup=round(float(r['markup']), 3)) for _, r in out_deals.iterrows()],
        sellers=g[:40])
    print(pid, len(w), int(p50), 'sellers', len(g), 'outliers', len(out_deals), 'onTime range', min([s['onTime'] for s in g] or [0]), max([s['onTime'] for s in g] or [0]))
json.dump(res, open(out, 'w'), ensure_ascii=False)
