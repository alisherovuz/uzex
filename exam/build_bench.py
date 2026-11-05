"""Benchmark set: ~200 templated questions (Uzbek + Russian) whose answers are computed by pandas from the RAW CSVs.
No model is involved in the answer key. Usage: python exam/build_bench.py data/uzex_spot_data.zip exam/bench.json"""
import glob, json, os, random, sys, tempfile, zipfile
import pandas as pd

random.seed(2026)
src, out = sys.argv[1], sys.argv[2]
if src.endswith(".zip"):
    tmp = tempfile.mkdtemp(); zipfile.ZipFile(src).extractall(tmp)
    src = os.path.dirname(glob.glob(os.path.join(tmp, "**", "contracts.csv"), recursive=True)[0])
rd = lambda f: pd.read_csv(os.path.join(src, f), dtype=str, keep_default_na=False, na_values=[""])
D = pd.concat([rd(os.path.basename(f)) for f in sorted(glob.glob(os.path.join(src, "deals_*.csv")))], ignore_index=True)
C = rd("contracts.csv"); P = rd("participants.csv"); R = rd("usd_rates.csv"); B = rd("brokers.csv")
num = lambda s: pd.to_numeric(s.str.replace(" ", "", regex=False), errors="coerce")
dt = lambda s: pd.to_datetime(s, format="%d.%m.%Y", errors="coerce")
D["qty"], D["lot"], D["amt"] = num(D["Количество"]), num(D["Лот"]), num(D["Сумма сделки"])
D["date"], D["pay"], D["dlv"] = dt(D["Дата сделки"]), dt(D["Дата оплаты"]), dt(D["Дата поставки"])
D["year"], D["ym"] = D.date.dt.year, D.date.dt.strftime("%Y-%m")
D["cancel"] = D["Состояние сделки"].str.startswith("Аннулирован"); ok = ~D.cancel
cs = C.set_index("Номер контракта")
D["cur"] = D["Номер контракта"].map(cs["Валюта"]); D["dterm"] = D["Номер контракта"].map(cs["Срок поставки"]).astype(int)
rate = R.assign(d=dt(R["Дата"]), r=num(R["Курс"])).set_index("d")["r"]
D["uzs"] = D.amt.where(D.cur == "Узбекский сум", D.amt * D.date.map(rate))
D["vol"] = D.qty * D.lot
D["unit"] = D["Единица измерения"]
D["vol_t"] = D.vol.where(D.unit != "килограмм", D.vol / 1000)
D["mass"] = D.unit.isin(["тонна", "килограмм"])
name = D["Наименование товара"].str.lower()

PROD = {  # regex on raw names -> (uz, ru)
    r"сахар": ("shakar", "сахар"), r"цемент": ("sement", "цемент"), r"пшениц": ("bug'doy", "пшеница"),
    r"карбамид|мочевин": ("karbamid", "карбамид"), r"селитр": ("ammiakli selitra", "аммиачная селитра"),
    r"дизел": ("dizel yoqilg'isi", "дизельное топливо"), r"^полиэтилен": ("polietilen", "полиэтилен"),
    r"хлопок.?сырец": ("paxta (xom ashyo)", "хлопок-сырец"), r"катод": ("mis katod", "медный катод"),
    r"битум": ("bitum", "битум"), r"^арматур": ("armatura", "арматура"), r"полипропилен": ("polipropilen", "полипропилен"),
    r"кирпич": ("g'isht", "кирпич"), r"^рис|рис ": ("guruch", "рис"), r"мука": ("un", "мука"),
    r"сжиженн|газ сжиж": ("suyultirilgan gaz", "сжиженный газ"), r"мазут": ("mazut", "мазут"),
}
pmask = {k: name.str.contains(k, regex=True) for k in PROD}
REG_RU = {"Andijon viloyati": "Андижанской области", "Buxoro viloyati": "Бухарской области", "Jizzax viloyati": "Джизакской области",
          "Qashqadaryo viloyati": "Кашкадарьинской области", "Navoiy viloyati": "Навоийской области", "Namangan viloyati": "Наманганской области",
          "Samarqand viloyati": "Самаркандской области", "Surxondaryo viloyati": "Сурхандарьинской области", "Sirdaryo viloyati": "Сырдарьинской области",
          "Toshkent viloyati": "Ташкентской области", "Toshkent shahri": "городе Ташкенте", "Farg‘ona viloyati": "Ферганской области",
          "Xorazm viloyati": "Хорезмской области", "Qoraqalpog‘iston Respublikasi": "Республике Каракалпакстан"}
REG_UZ_LOC = {k: k.replace("viloyati", "viloyatida").replace("shahri", "shahrida").replace("Respublikasi", "Respublikasida") for k in REG_RU}
REG_ALIAS = {k: [k.split()[0].replace("‘", "'").lower()[:5], k.split()[0][:5].lower(), REG_RU[k].split()[0][:6].lower()] for k in REG_RU}
MON_UZ = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentyabr", "oktyabr", "noyabr", "dekabr"]
MON_RU = ["январе", "феврале", "марте", "апреле", "мае", "июне", "июле", "августе", "сентябре", "октябре", "ноябре", "декабре"]
YEARS = [2022, 2023, 2024, 2025, 2026]
Q = []
def add(qid, lang, q, tol=0.005, **exp): Q.append({"id": qid, "lang": lang, "q": q, "tol": tol, **exp})
pick = lambda xs: random.choice(list(xs))
L = lambda i: "uz" if i % 2 == 0 else "ru"

# T1 deal counts per product/year (total or non-cancelled both accepted)
for i in range(20):
    k = pick(PROD); y = pick(YEARS); s = D[pmask[k] & (D.year == y)]
    if not len(s): continue
    uz, ru = PROD[k]
    q = f"{y}-yilda {uz} bo'yicha nechta bitim tuzilgan?" if L(i) == "uz" else f"Сколько сделок по товару «{ru}» заключено в {y} году?"
    add(f"cnt_{i}", L(i), q, nums_any=[len(s), int((~s.cancel).sum())])
# T2 tonnes sold (mass units, kg->t), non-cancelled
for i in range(20):
    k = pick([k for k in PROD if (D[pmask[k]].mass.mean() > .99)]); y = pick(YEARS)
    s = D[pmask[k] & (D.year == y) & ok]
    if not len(s): continue
    uz, ru = PROD[k]; v = s.vol_t.sum()
    q = f"{y}-yilda qancha tonna {uz} sotilgan (bekor qilinganlarsiz)?" if L(i) == "uz" else f"Сколько тонн товара «{ru}» продано в {y} году (без аннулированных)?"
    add(f"ton_{i}", L(i), q, nums_any=[round(v, 1), round(v)], tol=0.004)
# T3 turnover in UZS per product/year
for i in range(20):
    k = pick(PROD); y = pick(YEARS); s = D[pmask[k] & (D.year == y) & ok]
    if not len(s): continue
    uz, ru = PROD[k]
    q = f"{y}-yilda {uz} savdosi so'mda qancha bo'lgan (bekor qilinganlarsiz)?" if L(i) == "uz" else f"Каков оборот по товару «{ru}» в {y} году в сумах (без аннулированных)?"
    add(f"uzs_{i}", L(i), q, nums_any=[round(s.uzs.sum())], tol=0.004)
# T4 weighted price per tonne for a month
for i in range(15):
    k = pick([k for k in PROD if (D[pmask[k]].mass.mean() > .99)]); y = pick([2024, 2025, 2026]); m = random.randint(1, 10)
    s = D[pmask[k] & (D.ym == f"{y}-{m:02d}") & ok]
    if len(s) < 5: continue
    uz, ru = PROD[k]; p = s.uzs.sum() / s.vol_t.sum()
    q = (f"{y}-yil {MON_UZ[m-1]} oyida {uz}ning 1 tonnasi o'rtacha (tortilgan) necha so'm turgan?" if L(i) == "uz"
         else f"Какова средневзвешенная цена тонны товара «{ru}» в {MON_RU[m-1]} {y} года?")
    add(f"price_{i}", L(i), q, nums_any=[round(p)], tol=0.004)
# T5 top seller by turnover for product/year
for i in range(15):
    k = pick(PROD); y = pick(YEARS); s = D[pmask[k] & (D.year == y) & ok]
    if not len(s): continue
    inn = s.groupby("ИНН продавца").uzs.sum().idxmax(); uz, ru = PROD[k]
    q = f"{y}-yilda {uz} bo'yicha savdo hajmi eng katta sotuvchi kim?" if L(i) == "uz" else f"Какой продавец лидировал по обороту товара «{ru}» в {y} году?"
    add(f"topsel_{i}", L(i), q, texts_any=[inn])
# T6 cancellation share by region/year
for i in range(15):
    r = pick(REG_RU); y = pick(YEARS); s = D[(D["Регион"] == r) & (D.year == y)]
    if not len(s): continue
    sh = 100 * s.cancel.mean()
    q = f"{y}-yilda {REG_UZ_LOC[r]} bekor qilingan bitimlar ulushi necha foiz?" if L(i) == "uz" else f"Какая доля сделок была аннулирована в {REG_RU[r]} в {y} году (в %)?"
    add(f"canc_{i}", L(i), q, nums_any=[round(sh, 2), round(sh, 1)], tol=0.01)
# T7 broker activity in a year (either side)
for i in range(15):
    b = pick(B["Код брокера"]); y = pick(YEARS)
    s = D[(D.year == y) & ((D["Брокер продавца"] == b) | (D["Брокер покупателя"] == b))]
    q = f"{y}-yilda {b} brokeri nechta bitimda qatnashgan?" if L(i) == "uz" else f"В скольких сделках участвовал брокер {b} в {y} году?"
    if len(s): add(f"brk_{i}", L(i), q, nums_any=[len(s), int((~s.cancel).sum())])
    else: add(f"brk_{i}", L(i), q, texts_any=["0", "yo'q", "не участв", "ни одной", "нет сделок", "qatnashmagan"])
# T8 buyer by INN: number of deals and cancelled count
buyers = D["ИНН покупателя"].value_counts(); buyers = buyers[buyers >= 15].index.tolist()
for i in range(15):
    inn = pick(buyers); s = D[D["ИНН покупателя"] == inn]
    q = f"STIR {inn} xaridor sifatida nechta bitim tuzgan?" if L(i) == "uz" else f"Сколько сделок заключил покупатель с ИНН {inn}?"
    add(f"buy_{i}", L(i), q, nums_any=[len(s), int((~s.cancel).sum())])
# T9 export USD per year
for i in range(10):
    y = pick(YEARS); k = pick([r"катод", r"пряж"]); s = D[name.str.contains(k) & (D["Тип контракта"] == "Экспортный") & (D.year == y) & ok]
    if not len(s): continue
    uz, ru = {"катод": ("mis katod", "медный катод"), "пряж": ("paxta ipi (pryaja)", "хлопчатобумажная пряжа")}[k]
    q = f"{y}-yilda {uz} eksporti necha dollar bo'lgan?" if L(i) == "uz" else f"На какую сумму в долларах экспортирован товар «{ru}» в {y} году?"
    add(f"exp_{i}", L(i), q, nums_any=[round(s.amt.sum(), 2), round(s.amt.sum())], tol=0.004)
# T10 region with most deals for product/year
for i in range(15):
    k = pick(PROD); y = pick(YEARS); s = D[pmask[k] & (D.year == y)]
    if not len(s): continue
    r = s["Регион"].value_counts().idxmax(); uz, ru = PROD[k]
    q = f"{y}-yilda {uz} eng ko'p qaysi hududdan sotilgan (bitimlar soni bo'yicha)?" if L(i) == "uz" else f"Из какого региона больше всего сделок по товару «{ru}» в {y} году?"
    add(f"reg_{i}", L(i), q, texts_any=REG_ALIAS[r])
# T11 late deliveries for product/year
for i in range(10):
    k = pick(PROD); y = pick([2023, 2024, 2025]); s = D[pmask[k] & (D.year == y) & D.dlv.notna() & D.pay.notna()]
    n = int(((s.dlv - s.pay).dt.days > s.dterm).sum()); uz, ru = PROD[k]
    q = f"{y}-yilda {uz} bo'yicha nechta bitim kechikib yetkazilgan?" if L(i) == "uz" else f"Сколько сделок по товару «{ru}» в {y} году были поставлены с опозданием?"
    add(f"late_{i}", L(i), q, nums_any=[n] if n else [], texts_any=None if n else ["0", "yo'q", "не было", "ни одной"])
# T12 traps
inns = set(P["ИНН"])
fake = [str(random.randint(900000000, 999999999)) for _ in range(40)]; fake = [f for f in fake if f not in inns][:6]
traps = [(f"STIR {f} kompaniyasi nechta bitim tuzgan?", f"Сколько сделок у компании с ИНН {f}?") for f in fake[:6]]
traps += [("2019-yilda nechta bitim tuzilgan?", "Сколько сделок было в 2019 году?"),
          ("2027-yil yanvarida shakar narxi qancha bo'ladi?", "Сколько будет стоить сахар в январе 2027 года?"),
          ("Birjada qancha kofe sotilgan?", "Сколько кофе продано на бирже?"), ("Birjada qancha xom neft sotilgan?", "Сколько сырой нефти продано на бирже?"),
          ("BK150 brokeri qancha bitim qilgan?", "Сколько сделок у брокера BK150?"), ("Bitcoin narxi qancha?", "Какой сейчас курс биткоина?"),
          ("2026-yil noyabrda nechta bitim bo'ldi?", "Сколько сделок было в ноябре 2026 года?"), ("Titan qancha sotilgan?", "Сколько продано титана?"),
          ("UZEX direktori kim?", "Кто директор UZEX?"), ("Ertaga sement narxi oshadimi?", "Вырастет ли завтра цена цемента?")]
for i, (u, r_) in enumerate(traps[:20]):
    add(f"trap_{i}", L(i), u if L(i) == "uz" else r_, not_found=True)

for q in Q:
    for k in ("nums_any",):
        if k in q and q[k] is not None: q[k] = [float(x) for x in q[k]]
    if q.get("texts_any") is None: q.pop("texts_any", None)
    if q.get("nums_any") == []: q.pop("nums_any")
json.dump(Q, open(out, "w"), ensure_ascii=False, indent=1)
from collections import Counter
print(len(Q), "questions;", Counter(q["id"].split("_")[0] for q in Q), Counter(q["lang"] for q in Q))
