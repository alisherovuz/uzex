"""Build the cleaned DuckDB database from the raw UZEX CSV export.

Usage: python scripts/build_db.py <raw_dir_or_zip> <out.duckdb>

Everything the agent queries comes from here: numbers parsed, dates typed,
amounts in both UZS and USD, a canonical product catalogue that merges the
many spellings sellers use, regions unified, payment/delivery lateness derived.
"""
import glob
import os
import re
import sys
import tempfile
import zipfile

import duckdb
import pandas as pd

RU_REGION_TO_UZ = {
    "Андижанская область": "Andijon viloyati",
    "Бухарская область": "Buxoro viloyati",
    "Джизакская область": "Jizzax viloyati",
    "Кашкадарьинская область": "Qashqadaryo viloyati",
    "Навоийская область": "Navoiy viloyati",
    "Наманганская область": "Namangan viloyati",
    "Самаркандская область": "Samarqand viloyati",
    "Сурхандарьинская область": "Surxondaryo viloyati",
    "Сырдарьинская область": "Sirdaryo viloyati",
    "Ташкентская область": "Toshkent viloyati",
    "Ферганская область": "Farg‘ona viloyati",
    "Хорезмская область": "Xorazm viloyati",
    "г. Ташкент": "Toshkent shahri",
    "Республика Каракалпакстан": "Qoraqalpog‘iston Respublikasi",
}

# Base-name synonyms: different spellings sellers use for the same product.
BASE_SYNONYMS = {
    "хлопок сырец": "хлопок-сырец",
    "хлопковое масло": "масло хлопковое",
    "подсолнечное масло": "масло подсолнечное",
    "сахар-песок": "сахар белый",
    "сахар песок": "сахар белый",
    "питьевая вода": "вода питьевая",
    "шрот хлопковых семян": "шрот хлопковый",
    "цемент портландский": "портландцемент",
    "дизельное топливо": "топливо дизельное",
    "бензин автомобильный": "бензин",
    "сжиженный углеводородный газ": "газ сжиженный",
    "сжиженный газ": "газ сжиженный",
    "газ сжиженный пропан-бутан": "газ сжиженный",
    "серная кислота": "кислота серная",
    "мочевина (карбамид)": "карбамид",
    "селитра аммиачная": "аммиачная селитра",
    "трубы полиэтиленовые": "труба пэ",
    "пиломатериалы": "пиломатериал обрезной",
    "медный катод": "катод медный",
    "алюминиевый профиль": "профиль алюминиевый",
    "арматура стальная": "арматура",
    "пряжа хлопковая": "пряжа хлопчатобумажная",
    "мука пшеничная": "мука",
    "пшеница продовольственная": "пшеница",
    "рис шлифованный": "рис",
    "соль поваренная пищевая": "соль пищевая",
    "мазут топочный": "мазут",
    "битум нефтяной": "битум",
    "гипс строительный": "гипс",
    "кирпич керамический": "кирпич",
    "стекло флоат": "стекло листовое",
    "эмаль алкидная": "эмаль",
    "полиэтилен гранулированный": "полиэтилен",
    "известь строительная": "известь",
    "известь негашеная": "известь",
}

ROMAN = {"i": "1", "ii": "2", "iii": "3", "iv": "4"}
WORD_NUM = {"первый": "1", "первого": "1", "второй": "2", "второго": "2", "третий": "3", "третьего": "3"}


def num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(
        s.astype("string").str.replace(" ", "", regex=False).str.replace(" ", "", regex=False)
        .str.replace(",", ".", regex=False),
        errors="coerce",
    )


def date(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, format="%d.%m.%Y", errors="coerce").dt.date


def low(x) -> str:
    return "" if pd.isna(x) else str(x).strip().lower().replace("ё", "е")


def norm_grade(text: str) -> str:
    t = low(text)
    if not t:
        return ""
    if re.search(r"высш|в/с", t):
        return "высший"
    m = re.search(r"\b(первый|первого|второй|второго|третий|третьего)\b", t)
    if m:
        return WORD_NUM[m.group(1)]
    m = re.search(r"\b(iv|iii|ii|i|\d)\b", t)
    if m:
        return ROMAN.get(m.group(1), m.group(1))
    return t


def norm_class(text: str) -> str:
    t = low(text)
    if not t:
        return ""
    m = re.search(r"\b(iv|iii|ii|i|\d)\b[ -]?класс", t) or re.search(r"^(iv|iii|ii|i|\d)\b", t)
    if m:
        return ROMAN.get(m.group(1), m.group(1))
    return t.upper().replace(" ", "")


def norm_brand(text: str) -> str:
    t = low(text)
    return t.upper().replace(" ", "") if t else ""


def norm_size(text: str) -> str:
    t = low(text)
    if not t:
        return ""
    return t.replace(" ", "").replace("х", "x").replace("Ø", "ø")


GRADE_RE = re.compile(r"(высшего сорта|высший сорт|в/с|(?:первый|второй|третий|iv|iii|ii|i|\d)[ -]?сорт[а]?)")
CLASS_RE = re.compile(r"((?:iv|iii|ii|i|\d)[ -]?класс[а]?)")
SIZE_RE = re.compile(r"(ø\s?\d+\s?мм|\d+[xх]\d+(?:[xх]\d+)?\s?мм|\d+\s?мм|\d+,\d+\s?л)")


def build_catalogue(contracts: pd.DataFrame) -> pd.DataFrame:
    brands = sorted({norm_brand(b) for b in contracts["Марка товара"].dropna()}, key=len, reverse=True)
    types = sorted({low(t) for t in contracts["Тип товара"].dropna()}, key=len, reverse=True)
    rows = []
    for _, r in contracts.iterrows():
        name = low(r["Наименование продукта"])
        grade = norm_grade(r["Сорт товара"]) if not pd.isna(r["Сорт товара"]) else ""
        klass = norm_class(r["Класс товара"]) if not pd.isna(r["Класс товара"]) else ""
        brand = norm_brand(r["Марка товара"])
        size = norm_size(r["Размер товара"])
        typ = low(r["Тип товара"])
        rest = name
        # attributes embedded in the name itself
        m = GRADE_RE.search(rest)
        if m:
            grade = grade or norm_grade(m.group(1))
            rest = rest.replace(m.group(1), " ")
        m = CLASS_RE.search(rest)
        if m:
            klass = klass or norm_class(m.group(1))
            rest = rest.replace(m.group(1), " ")
        m = SIZE_RE.search(rest)
        if m:
            size = size or norm_size(m.group(1))
            rest = rest.replace(m.group(1), " ")
        for t in types:
            if t and t in rest:
                typ = typ or t
                rest = rest.replace(t, " ")
        up = rest.upper().replace(" ", "")
        for b in brands:
            if b and len(b) >= 2 and b in up:
                brand = brand or b
                # remove brand from rest (spacing-insensitive)
                pat = r"\s*".join(re.escape(ch) for ch in b.lower())
                rest = re.sub(pat, " ", rest)
                break
        base = re.sub(r"\s+", " ", rest).strip(" -,")
        base = BASE_SYNONYMS.get(base, base)
        form_suffix = ""
        m = re.search(r"\((спот|форвард|фьючерс)\)", base)
        if m:
            form_suffix = m.group(1)
            base = re.sub(r"\s*\((спот|форвард|фьючерс)\)", "", base).strip()
            base = BASE_SYNONYMS.get(base, base)
        parts = [base]
        if brand:
            parts.append(f"марка {brand}")
        if grade:
            parts.append(f"сорт {grade}")
        if klass:
            parts.append(f"класс {klass}")
        if typ:
            parts.append(typ)
        if size:
            parts.append(size)
        rows.append(
            dict(
                contract_id=int(r["Номер контракта"]),
                product_base=base,
                product_key=" | ".join(parts),
                p_brand=brand or None,
                p_grade=grade or None,
                p_class=klass or None,
                p_type=typ or None,
                p_size=size or None,
            )
        )
    return pd.DataFrame(rows)


def main(src: str, out: str) -> None:
    tmp = None
    if src.endswith(".zip"):
        tmp = tempfile.mkdtemp()
        with zipfile.ZipFile(src) as z:
            z.extractall(tmp)
        cands = glob.glob(os.path.join(tmp, "**", "contracts.csv"), recursive=True)
        src = os.path.dirname(cands[0])

    rd = lambda f: pd.read_csv(os.path.join(src, f), dtype=str, keep_default_na=False, na_values=[""])

    contracts = rd("contracts.csv")
    participants = rd("participants.csv")
    brokers = rd("brokers.csv")
    rates = rd("usd_rates.csv")
    deals = pd.concat([rd(os.path.basename(f)) for f in sorted(glob.glob(os.path.join(src, "deals_*.csv")))],
                      ignore_index=True)

    cat = build_catalogue(contracts)

    # ---- contracts
    c = pd.DataFrame({
        "contract_id": contracts["Номер контракта"].astype(int),
        "product_name_raw": contracts["Наименование продукта"],
        "brand_raw": contracts["Марка товара"], "size_raw": contracts["Размер товара"],
        "grade_raw": contracts["Сорт товара"], "type_raw": contracts["Тип товара"],
        "class_raw": contracts["Класс товара"],
        "hs_code": contracts["Код ТН ВЭД"], "product_group": contracts["Группа товара"],
        "category": contracts["Категория товара"], "industry": contracts["Отрасль промышленности"],
        "unit": contracts["Единица измерения"], "lot_size": num(contracts["Лот"]),
        "currency": contracts["Валюта"].map({"Узбекский сум": "UZS", "Доллар США": "USD"}),
        "base_price": num(contracts["Базисная цена"]),
        "deposit_pct": num(contracts["Сумма залога"].str.replace("%", "", regex=False)),
        "delivery_basis": contracts["Базис поставки"],
        "region": contracts["Регион"].map(RU_REGION_TO_UZ).fillna(contracts["Регион"]),
        "region_ru": contracts["Регион"],
        "warehouse_address": contracts["Адрес склада"],
        "auction_type": contracts["Тип торгов"], "contract_type": contracts["Тип контракта"],
        "contract_form": contracts["Форма контракта"],
        "payment_term_days": num(contracts["Срок оплаты"]).astype("Int64"),
        "delivery_term_days": num(contracts["Срок поставки"]).astype("Int64"),
        "packaging": contracts["Упаковка"], "seller_inn": contracts["ИНН продавца"],
        "registered_date": date(contracts["Дата регистрации"]), "valid_until": date(contracts["Действует до"]),
    }).merge(cat, on="contract_id", how="left")

    # ---- deals
    d = pd.DataFrame({
        "deal_id": deals["Номер сделки"].astype(int),
        "deal_date": date(deals["Дата сделки"]),
        "deal_time": deals["Время сделки"],
        "auction_type": deals["Тип торгов"],
        "qty_lots": num(deals["Количество"]),
        "amount": num(deals["Сумма сделки"]),
        "start_price": num(deals["Стартовая цена"]),
        "contract_id": deals["Номер контракта"].astype(int),
        "product_raw": deals["Наименование товара"],
        "lot_size": num(deals["Лот"]),
        "unit": deals["Единица измерения"],
        "region": deals["Регион"],
        "contract_type": deals["Тип контракта"],
        "contract_form": deals["Форма контракта"],
        "status": deals["Состояние сделки"],
        "seller_inn": deals["ИНН продавца"], "buyer_inn": deals["ИНН покупателя"],
        "seller_broker": deals["Брокер продавца"], "buyer_broker": deals["Брокер покупателя"],
        "payment_date": date(deals["Дата оплаты"]), "delivery_date": date(deals["Дата поставки"]),
        "delivered_lots": num(deals["Поставлено"]),
    })
    meta = c[["contract_id", "currency", "product_base", "product_key", "p_brand", "p_grade", "p_class",
              "p_type", "p_size", "hs_code", "product_group", "category", "industry",
              "payment_term_days", "delivery_term_days"]]
    d = d.merge(meta, on="contract_id", how="left")

    r = pd.DataFrame({"rate_date": date(rates["Дата"]), "usd_rate": num(rates["Курс"])})

    con = duckdb.connect(out)
    con.register("d_df", d); con.register("c_df", c); con.register("r_df", r)
    con.execute("CREATE OR REPLACE TABLE usd_rates AS SELECT * FROM r_df ORDER BY rate_date")
    con.execute("CREATE OR REPLACE TABLE contracts AS SELECT * FROM c_df ORDER BY contract_id")
    con.execute("""
    CREATE OR REPLACE TABLE deals AS
    SELECT d.*,
      year(d.deal_date)::INT AS year, month(d.deal_date)::INT AS month,
      strftime(d.deal_date, '%Y-%m') AS ym,
      d.qty_lots * d.lot_size AS volume,
      d.delivered_lots * d.lot_size AS delivered_volume,
      CASE WHEN d.unit = 'килограмм' THEN 'тонна' ELSE d.unit END AS unit_norm,
      d.qty_lots * d.lot_size / CASE WHEN d.unit = 'килограмм' THEN 1000 ELSE 1 END AS volume_norm,
      CASE WHEN d.currency='USD' THEN d.amount * r.usd_rate ELSE d.amount END
        / NULLIF(d.qty_lots * d.lot_size / CASE WHEN d.unit = 'килограмм' THEN 1000 ELSE 1 END, 0) AS unit_price_norm_uzs,
      r.usd_rate,
      CASE WHEN d.currency='USD' THEN d.amount * r.usd_rate ELSE d.amount END AS amount_uzs,
      CASE WHEN d.currency='USD' THEN d.amount ELSE d.amount / r.usd_rate END AS amount_usd,
      d.amount / NULLIF(d.qty_lots * d.lot_size, 0) AS unit_price,
      CASE WHEN d.currency='USD' THEN d.amount * r.usd_rate ELSE d.amount END
        / NULLIF(d.qty_lots * d.lot_size, 0) AS unit_price_uzs,
      d.status LIKE 'Аннулирован%' AS is_cancelled,
      d.status IN ('Исполнен', 'Исполнен(Частично)') AS is_executed,
      d.deal_date + CAST(d.payment_term_days AS INT) AS payment_due_date,
      CASE WHEN d.payment_date IS NOT NULL THEN date_diff('day', d.deal_date + CAST(d.payment_term_days AS INT), d.payment_date) END AS payment_delay_days,
      CASE WHEN d.payment_date IS NOT NULL THEN d.payment_date + CAST(d.delivery_term_days AS INT) END AS delivery_due_date,
      CASE WHEN d.delivery_date IS NOT NULL AND d.payment_date IS NOT NULL
           THEN date_diff('day', d.payment_date + CAST(d.delivery_term_days AS INT), d.delivery_date) END AS delivery_delay_days
    FROM d_df d LEFT JOIN r_df r ON r.rate_date = d.deal_date
    ORDER BY d.deal_id
    """)
    con.execute("""
    CREATE OR REPLACE TABLE companies AS SELECT
      "ИНН" AS inn, "Наименование" AS name, "Регион" AS region, "Вид деятельности" AS activity,
      "Роль" AS role, "Плательщик НДС" = 'Да' AS vat_payer
    FROM read_csv(?, all_varchar=true)""", [os.path.join(src, "participants.csv")])
    con.execute("""
    CREATE OR REPLACE TABLE brokers AS SELECT
      "Код брокера" AS broker_code, "Наименование" AS name, "ИНН" AS inn, "Регион" AS region
    FROM read_csv(?, all_varchar=true)""", [os.path.join(src, "brokers.csv")])
    # product catalogue: one row per canonical product with its raw spellings
    con.execute("""
    CREATE OR REPLACE TABLE products AS
    SELECT product_key, any_value(product_base) AS product_base, any_value(category) AS category,
           any_value(unit) AS unit, count(*) AS deals,
           list(DISTINCT product_raw ORDER BY product_raw) AS raw_names
    FROM deals GROUP BY product_key ORDER BY deals DESC
    """)
    con.execute("CREATE INDEX IF NOT EXISTS ix_seller ON deals(seller_inn)")
    con.execute("CREATE INDEX IF NOT EXISTS ix_buyer ON deals(buyer_inn)")
    meta_rows = {
        "deals": con.execute("SELECT count(*) FROM deals").fetchone()[0],
        "first_date": str(con.execute("SELECT min(deal_date) FROM deals").fetchone()[0]),
        "last_date": str(con.execute("SELECT max(deal_date) FROM deals").fetchone()[0]),
    }
    con.execute("CREATE OR REPLACE TABLE meta AS SELECT * FROM (VALUES " +
                ",".join(f"('{k}','{v}')" for k, v in meta_rows.items()) + ") t(k, v)")
    con.close()
    print("built", out, meta_rows)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
