"""HARD exam: 40 tricky questions (Uzbek Latin/Cyrillic + Russian) with ground truth computed by plain pandas
directly from the RAW CSV export — an independent code path from the agent's DuckDB.

Expected-answer spec per question:
  nums_any  — at least one of these numbers must appear in the answer (rel. tolerance `tol`)
  nums_all  — every one of these numbers must appear
  texts_any — at least one alias must appear (case-insensitive)
  texts_all — list of alias-groups; each group needs one match
  not_found — the agent must say the data has no answer (status not_found/clarify)
Usage: python exam/build_hard.py data/uzex_spot_data.zip exam/hard.json
"""
import glob
import json
import os
import sys
import tempfile
import zipfile

import pandas as pd

src, out = sys.argv[1], sys.argv[2]
if src.endswith(".zip"):
    tmp = tempfile.mkdtemp()
    zipfile.ZipFile(src).extractall(tmp)
    src = os.path.dirname(glob.glob(os.path.join(tmp, "**", "contracts.csv"), recursive=True)[0])
rd = lambda f: pd.read_csv(os.path.join(src, f), dtype=str, keep_default_na=False, na_values=[""])
D = pd.concat([rd(os.path.basename(f)) for f in sorted(glob.glob(os.path.join(src, "deals_*.csv")))], ignore_index=True)
C = rd("contracts.csv"); P = rd("participants.csv"); R = rd("usd_rates.csv")
num = lambda s: pd.to_numeric(s.str.replace(" ", "", regex=False), errors="coerce")
dt = lambda s: pd.to_datetime(s, format="%d.%m.%Y", errors="coerce")

D["qty"], D["lot"], D["amt"], D["start"] = num(D["Количество"]), num(D["Лот"]), num(D["Сумма сделки"]), num(D["Стартовая цена"])
D["deliv"] = num(D["Поставлено"])
D["date"], D["pay"], D["dlv"] = dt(D["Дата сделки"]), dt(D["Дата оплаты"]), dt(D["Дата поставки"])
D["year"], D["ym"] = D["date"].dt.year, D["date"].dt.strftime("%Y-%m")
D["cancel"] = D["Состояние сделки"].str.startswith("Аннулирован")
cc = C.set_index("Номер контракта")
D["cur"] = D["Номер контракта"].map(cc["Валюта"])
D["pterm"] = D["Номер контракта"].map(cc["Срок оплаты"]).astype(int)
D["dterm"] = D["Номер контракта"].map(cc["Срок поставки"]).astype(int)
rate = R.assign(d=dt(R["Дата"]), r=num(R["Курс"])).set_index("d")["r"]
D["uzs"] = D["amt"].where(D["cur"] == "Узбекский сум", D["amt"] * D["date"].map(rate))
D["vol"] = D["qty"] * D["lot"]
D["unit"] = D["Единица измерения"]
D["vol_t"] = D["vol"].where(D["unit"] != "килограмм", D["vol"] / 1000)
D["unit_t"] = D["unit"].replace({"килограмм": "тонна"})
name = D["Наименование товара"].str.lower()
ok = ~D["cancel"]
pname = P.set_index("ИНН")["Наименование"]
Q = []


def add(qid, lang, q, note="", tol=0.005, **exp):
    Q.append({"id": qid, "lang": lang, "q": q, "tol": tol, "note": note, **exp})


# 1 petrol AI-92 sold in two units: litres AND tonnes must both be reported, never added
s = D[name.str.contains("92") & name.str.contains("бензин") & (D.year == 2025) & ok]
lit = s[s.unit == "литр"]["vol"].sum(); ton = s[s.unit == "тонна"]["vol"].sum()
add("ai92_units", "uz", "2025-yilda AI-92 benzin qancha sotilgan?", nums_all=[round(lit), round(ton, 1)],
    note="litr va tonna alohida")

# 2 diesel DT-E-K5 weighted price per tonne, Oct 2026 (kg normalized)
s = D[name.str.contains("дт-е-к5") & (D.ym == "2026-10") & ok]
add("dtek5_price", "ru", "Средневзвешенная цена дизельного топлива ДТ-Е-К5 за тонну в октябре 2026 года?",
    nums_any=[round(s.uzs.sum() / s.vol_t.sum())], tol=0.003)

# 3 exports in UZS 2025 (converted at deal-date rate)
s = D[(D["Тип контракта"] == "Экспортный") & (D.year == 2025) & ok]
add("export_uzs_2025", "uz", "2025-yilda eksport bitimlarining umumiy summasi so'mda qancha (bekor qilinganlarsiz)?",
    nums_any=[round(s.uzs.sum())], tol=0.003)

# 4 partial deliveries of sugar 2025: contracted vs delivered tonnes
s = D[name.str.contains("сахар") & (D.year == 2025) & (D["Состояние сделки"] == "Исполнен(Частично)")]
add("sugar_partial", "ru", "По частично исполненным сделкам с сахаром в 2025 году: сколько тонн было законтрактовано и сколько фактически поставлено?",
    nums_all=[round(s.vol.sum()), round((s.deliv * s.lot).sum())])

# 5 late payments 2024
s = D[(D.year == 2024) & D.pay.notna()]
late = (s.pay - s.date).dt.days > s.pterm
add("late_pay_2024", "uz", "2024-yilda nechta bitim to'lov muddatidan kechikib to'langan?", nums_any=[int(late.sum())])

# 6 seller with most late deliveries 2025
s = D[(D.year == 2025) & D.dlv.notna() & D.pay.notna()]
s = s[(s.dlv - s.pay).dt.days > s.dterm]
inn = s["ИНН продавца"].value_counts().index[0]
add("late_dlv_seller", "ru", "Какой продавец чаще всего задерживал поставку в 2025 году (по числу сделок)?",
    texts_any=[inn], note=str(pname.get(inn)))

# 7 same broker on both sides 2025
s = D[(D.year == 2025) & (D["Брокер продавца"] == D["Брокер покупателя"])]
add("same_broker_2025", "uz", "2025-yilda sotuvchi va xaridor bitta brokerdan foydalangan bitimlar soni nechta?",
    nums_any=[len(s), int((~s.cancel).sum())])

# 8 top seller–buyer pair all time
pc = D.groupby(["ИНН продавца", "ИНН покупателя"]).size().sort_values(ascending=False)
(si, bi), n = pc.index[0], int(pc.iloc[0])
add("top_pair", "ru", "Какая пара продавец–покупатель заключила больше всего сделок за всё время и сколько?",
    nums_any=[n], texts_all=[[si], [bi]])

# 9 month with highest turnover 2025
m = D[(D.year == 2025) & ok].groupby("ym")["uzs"].sum().idxmax()
mon = int(m[-2:])
uzm = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentyabr", "oktyabr", "noyabr", "dekabr"][mon - 1]
add("top_month_2025", "uz", "2025-yilning qaysi oyida savdo hajmi (so'mda) eng yuqori bo'lgan?", texts_any=[uzm, m])

# 10 average deal size 2023
s = D[(D.year == 2023) & ok]
add("avg_deal_2023", "ru", "Какова средняя сумма одной сделки в 2023 году в сумах (без аннулированных)?",
    nums_any=[round(s.uzs.mean())], tol=0.003)

# 11 English auctions closing >10% above start price, 2025
s = D[(D.year == 2025) & (D["Тип торгов"] == "Английский аукцион")]
hit = (s.amt / s.vol) > s.start * 1.10
add("eng_premium", "uz", "2025-yilda ingliz auksionida nechta bitim boshlang'ich narxdan 10% dan ko'proq qimmatga yopilgan?",
    nums_any=[int(hit.sum()), int((hit & ~s.cancel).sum())])

# 12 region with highest cancellation share 2024
r = D[D.year == 2024].groupby("Регион")["cancel"].mean().idxmax()
RU = {"Andijon": "андижан", "Buxoro": "бухар", "Jizzax": "джизак", "Qashqadaryo": "кашкадар", "Navoiy": "навои",
      "Namangan": "наманган", "Samarqand": "самарканд", "Surxondaryo": "сурхандар", "Sirdaryo": "сырдар",
      "Toshkent viloyati": "ташкентская", "Toshkent shahri": "ташкент", "Farg": "ферган", "Xorazm": "хорезм", "Qoraqalpog": "каракалп"}
alias = [r.split()[0]] + [v for k, v in RU.items() if r.startswith(k)]
add("cancel_region_2024", "ru", "В каком регионе была самая высокая доля аннулированных сделок в 2024 году?", texts_any=alias)

# 13 buyer with most cancelled deals all time
inn = D[D.cancel]["ИНН покупателя"].value_counts().index[0]
add("most_cancel_buyer", "uz", "Qaysi xaridorda butun davr mobaynida eng ko'p bekor qilingan bitim bor?", texts_any=[inn],
    note=str(pname.get(inn)))

# 14 unique buyers 2026
s = D[D.year == 2026]
add("buyers_2026", "ru", "Сколько уникальных покупателей совершили сделки в 2026 году?",
    nums_any=[s["ИНН покупателя"].nunique(), s[~s.cancel]["ИНН покупателя"].nunique()])

# 15 forwards currently 'Заключен'
add("fwd_open", "uz", "Hozir nechta forvard bitim 'Заключен' (imzolangan, to'lov muddati o'tmagan) holatida?",
    nums_any=[int(((D["Форма контракта"] == "Форвард") & (D["Состояние сделки"] == "Заключен")).sum())])

# 16 deals on last day
add("last_day", "ru", "Сколько сделок было заключено 30 октября 2026 года?", nums_any=[int((D["Дата сделки"] == "30.10.2026").sum())])

# 17 largest deal in UZS
i = D.uzs.idxmax()
add("max_deal", "uz", "So'mda eng katta bitim qaysi? Raqami va summasi qancha?", texts_all=[[D.loc[i, "Номер сделки"]]],
    nums_any=[round(D.loc[i, "uzs"]), round(D.loc[i, "amt"])])

# 18 raw cotton 1st grade 2nd class 2025 — sold in KILOGRAMS
s = D[name.str.contains("хлопок") & (D.year == 2025) & ok]
s = s[s["Номер контракта"].isin(C[(C["Наименование продукта"].str.lower().str.contains("хлоп"))]["Номер контракта"])]
cs = C.set_index("Номер контракта")
g = (cs["Сорт товара"].fillna("") + " " + cs["Наименование продукта"].fillna("")).str.lower()
k = (cs["Класс товара"].fillna("") + " " + cs["Наименование продукта"].fillna("")).str.lower()
is1 = g.str.contains(r"(?:\b1\b|\bi\b|перв)[ -]?(?:-?й)?\s*-?сорт|\b1-сорт|\bi сорт|первый", regex=True)
is2c = k.str.contains(r"(?:\b2\b|\bii\b)[ -]?класс|2-класс|ii класс", regex=True)
sel = s[s["Номер контракта"].map(is1 & is2c).fillna(False)]
add("cotton_1_2", "ru", "Сколько хлопка-сырца 1 сорта 2 класса продано в 2025 году?",
    nums_any=[round(sel.vol.sum()), round(sel.vol.sum() / 1000, 1)], tol=0.004, note="kg or tonnes")

# 19 sugar price change Oct vs Sep 2026 (weighted, %)
def wp(ym):
    x = D[name.str.contains("сахар") & (D.ym == ym) & ok]
    return x.uzs.sum() / x.vol_t.sum()
chg = (wp("2026-10") / wp("2026-09") - 1) * 100
add("sugar_chg", "uz", "2026-yil oktyabrda shakarning o'rtacha narxi sentyabrga nisbatan necha foizga o'zgargan?",
    nums_any=[round(chg, 1), round(chg, 2), round(abs(chg), 1), round(abs(chg), 2)], tol=0.02)

# 20 companies both seller and buyer: none
both = set(D["ИНН продавца"]) & set(D["ИНН покупателя"])
add("both_roles", "ru", "Сколько компаний выступали на бирже и продавцом, и покупателем?",
    texts_any=["0", "ни одн", "нет таких", "не было", "отсутству", "нет компаний", "ни разу"], note=f"answer {len(both)}")

# 21 deals by non-VAT buyers 2025
nonvat = set(P[P["Плательщик НДС"] == "Нет"]["ИНН"])
s = D[(D.year == 2025) & D["ИНН покупателя"].isin(nonvat)]
add("nonvat_2025", "uz", "QQS to'lovchisi bo'lmagan xaridorlar 2025-yilda nechta bitim tuzgan?",
    nums_any=[len(s), int((~s.cancel).sum())])

# 22 export share of 2024 turnover, %
s = D[(D.year == 2024) & ok]
sh = 100 * s[s["Тип контракта"] == "Экспортный"].uzs.sum() / s.uzs.sum()
add("export_share_2024", "ru", "Какую долю (в процентах) занимал экспорт в обороте биржи в 2024 году?",
    nums_any=[round(sh, 2), round(sh, 1)], tol=0.02)

# 23 contracts registered in 2025
add("contracts_2025", "uz", "2025-yilda nechta yangi shartnoma (kontrakt kartochkasi) ro'yxatdan o'tgan?",
    nums_any=[int(C["Дата регистрации"].str.endswith(".2025").sum())])

# 24 average payment term for spot contracts
t = C[C["Форма контракта"] == "Спот"]["Срок оплаты"].astype(int).mean()
add("spot_pterm", "ru", "Какой средний срок оплаты (в днях) по спотовым контрактам?", nums_any=[round(t, 1), round(t, 2), round(t)],
    tol=0.02)

# 25 weekday with most deals
wd = D["date"].dt.dayofweek.value_counts().idxmax()
uzd = ["dushanba", "seshanba", "chorshanba", "payshanba", "juma", "shanba", "yakshanba"][wd]
add("weekday", "uz", "Haftaning qaysi kunida eng ko'p bitim tuziladi?", texts_any=[uzd])

# 26 busiest hour 2025
h = D[D.year == 2025]["Время сделки"].str[:2].value_counts().idxmax()
add("busy_hour", "ru", "В какой час дня в 2025 году заключалось больше всего сделок?", texts_any=[f"{h}:", f"{int(h)}:00", f"{int(h)} час", f"с {int(h)}"])

# 27 cement in Tashkent REGION (not city) 2024 — Russian region name vs Uzbek data
s = D[name.str.contains("цемент") & (D.year == 2024) & ok & (D["Регион"] == "Toshkent viloyati")]
add("cement_tash_obl", "ru", "Сколько тонн цемента продано в Ташкентской области в 2024 году?", nums_any=[round(s.vol.sum(), 1), round(s.vol.sum())])

# 28 Uzbek Cyrillic question: sugar tonnes 2025
s = D[name.str.contains("сахар") & (D.year == 2025) & ok]
add("sugar_cyr", "uz_cyrl", "2025 йилда қанча шакар сотилган?", nums_any=[round(s.vol.sum(), 1), round(s.vol.sum())])

# 29 copper cathode export USD 2025
s = D[name.str.contains("катод") & (D["Тип контракта"] == "Экспортный") & (D.year == 2025) & ok]
add("copper_usd_2025", "ru", "На какую сумму в долларах экспортирован медный катод в 2025 году?", nums_any=[round(s.amt.sum(), 2), round(s.amt.sum())],
    tol=0.003)

# 30–33 traps
add("trap_dec2026", "uz", "2026-yil dekabr oyida nechta bitim tuzilgan?", not_found=True)
add("trap_bk000", "ru", "Сколько сделок у брокера BK000?", not_found=True)
add("trap_gold", "uz", "Birjada qancha oltin sotilgan?", not_found=True)
add("trap_stock", "ru", "Какова текущая цена акций UZEX на бирже?", not_found=True)

# 34 false premise: there WERE cancellations in 2023
n23 = int(D[(D.year == 2023) & D.cancel].shape[0])
add("false_premise", "uz", "Nega 2023-yilda birorta ham bitim bekor qilinmagan?", nums_any=[n23],
    note="must correct the premise")

# 35 company by Cyrillic transliteration of a Latin name
inn = P[P["Наименование"].str.contains("Pudexiz Plast")]["ИНН"].iloc[0]
s = D[D["ИНН продавца"] == inn]
add("translit_company", "ru", "Сколько сделок продажи заключила компания «Пудексиз Пласт»?", nums_any=[len(s), int((~s.cancel).sum())],
    texts_any=[inn])

# 36 top-3 products by tonnage 2025 (mass units only)
s = D[(D.year == 2025) & ok & (D.unit_t == "тонна")]
base = s["Номер контракта"].map(cs["Наименование продукта"]).str.lower()
add("top3_tonnage", "uz", "2025-yilda hajm bo'yicha (tonnada) eng ko'p sotilgan 3 ta tovar qaysilar?",
    texts_all=[["хлоп", "paxta"]], note=str(s.groupby(base)["vol_t"].sum().sort_values(ascending=False).head(5).to_dict()))

# 37 paid but not yet delivered
s = D[D["Состояние сделки"] == "Оплачен"]
add("paid_not_delivered", "ru", "Сколько сделок оплачено, но ещё не поставлено, и на какую сумму в сумах?",
    nums_all=[len(s)], nums_any=[round(s.uzs.sum())], tol=0.003)

# 38 delivered without payment: none
x = int((D.dlv.notna() & D.pay.isna()).sum())
add("dlv_no_pay", "uz", "To'lanmasdan yetkazib berilgan bitimlar bormi? Nechta?",
    texts_any=["0", "yo'q", "yo‘q", "mavjud emas", "uchramaydi", "hech qanday", "birorta ham"], note=f"answer {x}")

# 39 broker with most export deals on buyer side
b = D[D["Тип контракта"] == "Экспортный"]["Брокер покупателя"].value_counts().index[0]
add("export_broker", "ru", "Какой брокер обслуживал больше всего экспортных сделок на стороне покупателя?", texts_any=[b])

# 40 top product by turnover in Fergana region 2024
s = D[(D.year == 2024) & ok & (D["Регион"] == "Farg‘ona viloyati")]
top = s.assign(b=s["Номер контракта"].map(cs["Наименование продукта"]).str.lower()).groupby("b")["uzs"].sum().idxmax()
add("fergana_top_2024", "uz", "2024-yilda Farg'ona viloyatida summa bo'yicha eng ko'p sotilgan tovar qaysi?",
    texts_any=[top.split()[0][:6]], note=top)

json.dump(Q, open(out, "w"), ensure_ascii=False, indent=1, default=str)
print(len(Q), "hard questions ->", out)
for q in Q:
    print(q["id"], {k: q[k] for k in ("nums_any", "nums_all", "texts_any", "texts_all", "note") if k in q})

# ---------------- round 2: 10 more adversarial questions
Q2 = []
def add2(qid, lang, q, note="", tol=0.005, **exp):
    Q2.append({"id": qid, "lang": lang, "q": q, "tol": tol, "note": note, **exp})

# 41 two-part question
s24 = D[(D.year == 2024) & ok]; s25 = D[(D.year == 2025) & ok]
add2("two_part", "uz", "2024 va 2025-yillarda bekor qilinmagan bitimlar soni qancha bo'lgan?", nums_all=[len(s24), len(s25)])
# 42 YoY growth of turnover 2025 vs 2024, %
g = (s25.uzs.sum() / s24.uzs.sum() - 1) * 100
add2("yoy_growth", "ru", "На сколько процентов вырос оборот биржи в 2025 году по сравнению с 2024 годом?", nums_any=[round(g, 1), round(g, 2)], tol=0.01)
# 43 typo in product + question
s = D[name.str.contains("карбамид") & (D.year == 2025) & ok]
add2("typo", "uz", "2025-yilda karbamit qancha tonna sotilgan?", nums_any=[round(s.vol.sum()), round(s.vol.sum(), 1)])
# 44 mixed language
s = D[name.str.contains("сахар") & (D.year == 2024)]
add2("mixed_lang", "uz", "2024-yilda сахар белый bo'yicha nechta сделка bo'lgan?", nums_any=[len(s), int((~s.cancel).sum())])
# 45 USD rate on a date
add2("usd_rate", "ru", "Какой был курс доллара 15 марта 2025 года по данным биржи?",
     nums_any=[float(rate[pd.Timestamp("2025-03-15")])], tol=0.0005)
# 46 contract base price
cid = "102557"
add2("contract_price", "uz", f"{cid}-raqamli shartnomaning bazis narxi qancha va qaysi tovar?",
     nums_any=[float(cs.loc[cid, "Базисная цена"])], texts_any=["бензин", "benzin", "92"])
# 47 average delivery delay among late deliveries 2025
s = D[(D.year == 2025) & D.dlv.notna() & D.pay.notna()]
late = (s.dlv - s.pay).dt.days - s.dterm
add2("avg_delay", "ru", "На сколько дней в среднем опаздывали поставки в 2025 году (среди опоздавших)?",
     nums_any=[round(late[late > 0].mean(), 1), round(late[late > 0].mean(), 2)], tol=0.03)
# 48 top-5 brokers by deals (either side)
tb = pd.concat([D["Брокер продавца"], D["Брокер покупателя"]]).value_counts().head(5).index.tolist()
add2("top5_brokers", "uz", "Bitimlar soni bo'yicha eng faol 5 ta broker qaysilar?", texts_all=[[b] for b in tb])
# 49 Uzbek Cyrillic, company by INN
inn = "908181397"; s = D[D["ИНН покупателя"] == inn]
add2("cyr_inn", "uz_cyrl", f"СТИР {inn} харидор сифатида нечта битим тузган?", nums_any=[len(s), int((~s.cancel).sum())])
# 50 ambiguous price for petrol sold in litres and tonnes
s = D[name.str.contains("92") & name.str.contains("бензин") & (D.ym == "2026-10") & ok]
pl = s[s.unit == "литр"]; pt = s[s.unit == "тонна"]
add2("petrol_price_units", "ru", "Сколько стоил бензин АИ-92 в октябре 2026 года?",
     nums_all=[round(pl.uzs.sum() / pl.vol.sum()), round(pt.uzs.sum() / pt.vol.sum())], tol=0.01,
     note="must give per-litre AND per-tonne")

Q += Q2
json.dump(Q, open(out, "w"), ensure_ascii=False, indent=1, default=float)
print("total", len(Q))
for q in Q2:
    print(q["id"], {k: q[k] for k in ("nums_any", "nums_all", "texts_any", "texts_all") if k in q})
