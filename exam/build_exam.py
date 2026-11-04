"""Build the exam: questions in Uzbek and Russian with ground-truth answers computed by plain pandas directly
from the RAW CSV files (an independent code path from the cleaned DuckDB the agent uses).

Usage: python exam/build_exam.py data/uzex_spot_data.zip exam/questions.json
"""
import glob
import json
import os
import random
import sys
import tempfile
import zipfile

import pandas as pd

random.seed(7)
src = sys.argv[1]
out = sys.argv[2]
if src.endswith(".zip"):
    tmp = tempfile.mkdtemp()
    zipfile.ZipFile(src).extractall(tmp)
    src = os.path.dirname(glob.glob(os.path.join(tmp, "**", "contracts.csv"), recursive=True)[0])

rd = lambda f: pd.read_csv(os.path.join(src, f), dtype=str, keep_default_na=False, na_values=[""])
D = pd.concat([rd(os.path.basename(f)) for f in sorted(glob.glob(os.path.join(src, "deals_*.csv")))], ignore_index=True)
C = rd("contracts.csv")
P = rd("participants.csv")
R = rd("usd_rates.csv")
num = lambda s: pd.to_numeric(s.str.replace(" ", "", regex=False), errors="coerce")
D["qty"] = num(D["Количество"]); D["lot"] = num(D["Лот"]); D["amt"] = num(D["Сумма сделки"])
D["date"] = pd.to_datetime(D["Дата сделки"], format="%d.%m.%Y"); D["year"] = D["date"].dt.year
D["ym"] = D["date"].dt.strftime("%Y-%m")
D["cancel"] = D["Состояние сделки"].str.startswith("Аннулирован")
cur = C.set_index("Номер контракта")["Валюта"]
D["cur"] = D["Номер контракта"].map(cur)
rate = R.assign(d=pd.to_datetime(R["Дата"], format="%d.%m.%Y"), r=num(R["Курс"])).set_index("d")["r"]
D["rate"] = D["date"].map(rate)
D["uzs"] = D["amt"].where(D["cur"] == "Узбекский сум", D["amt"] * D["rate"])
D["vol"] = D["qty"] * D["lot"]
D["vol_t"] = D["vol"].where(D["Единица измерения"] != "килограмм", D["vol"] / 1000)
name = D["Наименование товара"].str.lower()
names = P.set_index("ИНН")["Наименование"]

Q = []


def add(qid, uz, ru, expected, kind="number", tol=0.005, note=""):
    Q.append({"id": qid, "uz": uz, "ru": ru, "expected": expected, "kind": kind, "tol": tol, "note": note})


# 1-2 deal counts by product + year (total registered deals)
for prod, uzp, mask in [("сахар", "shakar", name.str.contains("сахар")),
                        ("карбамид", "karbamid", name.str.contains("карбамид")),
                        ("цемент", "sement", name.str.contains("цемент")),
                        ("аммиачная селитра", "ammiakli selitra", name.str.contains("селитр"))]:
    y = random.choice([2023, 2024, 2025])
    sub = D[mask & (D["year"] == y)]
    add(f"count_{prod}_{y}", f"{y}-yilda {uzp} bo'yicha nechta bitim tuzilgan?",
        f"Сколько сделок по товару «{prod}» было заключено в {y} году?",
        [int(len(sub)), int((~sub["cancel"]).sum())], "any_of",
        note="total registered deals or non-cancelled deals")

# 3 volume in tonnes, all diesel, excluding cancelled
for y in (2024, 2025):
    sub = D[name.str.contains("дизел") & (D["year"] == y) & ~D["cancel"]]
    add(f"diesel_t_{y}", f"{y}-yilda qancha dizel yoqilg'isi sotilgan (tonnada)?",
        f"Сколько тонн дизельного топлива продано в {y} году?", round(sub["vol_t"].sum(), 1), tol=0.002)

# 4 top seller by turnover in a year
for y in (2024, 2026):
    sub = D[(D["year"] == y) & ~D["cancel"]].groupby("ИНН продавца")["uzs"].sum().sort_values(ascending=False)
    inn = sub.index[0]
    add(f"top_seller_{y}", f"{y}-yilda savdo hajmi bo'yicha eng yirik sotuvchi kim?",
        f"Какой продавец был крупнейшим по обороту в {y} году?", inn, "text_inn", note=names.get(inn, ""))

# 5 cancellation share per year
for y in (2023, 2025):
    sub = D[D["year"] == y]
    add(f"cancel_share_{y}", f"{y}-yilda bekor qilingan bitimlar ulushi necha foiz?",
        f"Какова доля аннулированных сделок в {y} году (в процентах)?", round(100 * sub["cancel"].mean(), 2), tol=0.01)

# 6 export deals count and USD sum
for y in (2022, 2024):
    sub = D[(D["Тип контракта"] == "Экспортный") & (D["year"] == y)]
    add(f"export_count_{y}", f"{y}-yilda nechta eksport bitimi tuzilgan?",
        f"Сколько экспортных сделок было заключено в {y} году?",
        [int(len(sub)), int((~sub["cancel"]).sum())], "any_of")
    add(f"export_usd_{y}", f"{y}-yilda eksport bitimlarining umumiy summasi necha dollar (bekor qilinganlarsiz)?",
        f"Какова общая сумма экспортных сделок в {y} году в долларах (без аннулированных)?",
        round(sub[~sub["cancel"]]["amt"].sum(), 2), tol=0.002)

# 7 broker activity
b = random.choice(sorted(D["Брокер продавца"].unique()))
sub = D[(D["Брокер продавца"] == b) | (D["Брокер покупателя"] == b)]
add(f"broker_{b}", f"{b} brokeri nechta bitimda qatnashgan (sotuvchi yoki xaridor tomonida)?",
    f"В скольких сделках участвовал брокер {b} (на стороне продавца или покупателя)?",
    [int(len(sub)), int((~sub["cancel"]).sum())], "any_of")
top_b = pd.concat([D["Брокер продавца"], D["Брокер покупателя"]]).value_counts()
add("top_broker", "Qaysi broker eng ko'p bitimlarda qatnashgan?", "Какой брокер участвовал в наибольшем числе сделок?",
    top_b.index[0], "text")

# 8 buyer company
inn = D["ИНН покупателя"].value_counts().index[5]
sub = D[D["ИНН покупателя"] == inn]
add(f"buyer_{inn}", f"STIR {inn} xaridor sifatida nechta bitim tuzgan?",
    f"Сколько сделок заключил покупатель с ИНН {inn}?", [int(len(sub)), int((~sub["cancel"]).sum())], "any_of")

# 9 weighted avg price sugar in a month (UZS per tonne)
sub = D[name.str.contains("сахар") & (D["ym"] == "2026-10") & ~D["cancel"]]
add("sugar_price_2026_10", "2026-yil oktyabr oyida shakarning o'rtacha narxi qancha bo'lgan (1 tonna uchun)?",
    "Какова средняя цена сахара за тонну в октябре 2026 года?",
    [round(sub["uzs"].sum() / sub["vol_t"].sum(), 0), round((sub["amt"] / sub["vol_t"]).mean(), 0)], "any_of", tol=0.003,
    note="weighted or simple average")

# 10 region leader by deals
y = 2025
reg = D[D["year"] == y]["Регион"].value_counts()
add(f"region_top_{y}", f"{y}-yilda qaysi viloyatda eng ko'p bitim tuzilgan?",
    f"В каком регионе было больше всего сделок в {y} году?", reg.index[0], "text")

# 11 late delivery
c_term = C.set_index("Номер контракта")["Срок поставки"].astype(int)
pay = pd.to_datetime(D["Дата оплаты"], format="%d.%m.%Y"); dlv = pd.to_datetime(D["Дата поставки"], format="%d.%m.%Y")
late = (dlv - pay).dt.days > D["Номер контракта"].map(c_term)
sub = D[late & (D["year"] == 2025)]
add("late_delivery_2025", "2025-yilda nechta bitim muddatidan kechikib yetkazib berilgan?",
    "Сколько сделок в 2025 году было поставлено с опозданием?", int(len(sub)))

# 12 total turnover 2025 in UZS (non cancelled)
add("turnover_2025", "2025-yilda birjaning umumiy savdo hajmi necha so'm bo'lgan (bekor qilinganlarsiz)?",
    "Каков общий оборот биржи в 2025 году в сумах (без аннулированных)?",
    round(D[(D["year"] == 2025) & ~D["cancel"]]["uzs"].sum(), 0), tol=0.002)

# 13 partial executions
add("partial_2026", "2026-yilda nechta bitim qisman ijro etilgan?", "Сколько сделок в 2026 году исполнено частично?",
    int(((D["year"] == 2026) & (D["Состояние сделки"] == "Исполнен(Частично)")).sum()))

# 14 auction types
add("reverse_auction_2024", "2024-yilda teskari (pasaytiruvchi) auksionda nechta bitim tuzilgan?",
    "Сколько сделок было заключено на обратном аукционе в 2024 году?",
    [int(((D["year"] == 2024) & (D["Тип торгов"] == "Обратный аукцион")).sum()),
     int(((D["year"] == 2024) & (D["Тип торгов"] == "Обратный аукцион") & ~D["cancel"]).sum())], "any_of")

# 15 futures
add("futures_total", "Jami nechta fyuchers bitimi bor?", "Сколько всего фьючерсных сделок?",
    [int((D["Форма контракта"] == "Фьючерс").sum()), int(((D["Форма контракта"] == "Фьючерс") & ~D["cancel"]).sum())],
    "any_of")

# ---------- trap questions: the honest answer is "not in the data"
traps = [
    ("trap_inn", "STIR 123456789 kompaniyasi nechta bitim tuzgan?", "Сколько сделок заключила компания с ИНН 123456789?"),
    ("trap_product", "2025-yilda qancha titan kukuni sotilgan?", "Сколько титанового порошка продано в 2025 году?"),
    ("trap_year", "2021-yilda nechta bitim tuzilgan?", "Сколько сделок было заключено в 2021 году?"),
    ("trap_broker", "BK999 brokeri nechta bitimda qatnashgan?", "В скольких сделках участвовал брокер BK999?"),
    ("trap_future", "2027-yilda shakar narxi qancha bo'ladi?", "Какой будет цена сахара в 2027 году?"),
    ("trap_company", "\"Uzbekneftegaz\" AJ birjada qancha sotgan?", "Сколько продало АО «Узбекнефтегаз» на бирже?"),
]
for qid, uz, ru in traps:
    add(qid, uz, ru, None, "not_found")

json.dump(Q, open(out, "w"), ensure_ascii=False, indent=1, default=str)
print(f"{len(Q)} questions x 2 languages -> {out}")
