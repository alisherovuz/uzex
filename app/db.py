"""Read-only data access: safe SQL execution and entity lookup tools."""
import datetime as dt
import decimal
import re
import threading
import time
from typing import Any

import duckdb

from .config import DB_PATH

_con = duckdb.connect(DB_PATH, read_only=True)
_con.execute("SET threads TO 4")

FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|create|alter|attach|detach|copy|export|import|install|load|pragma|set|call|"
    r"read_csv|read_parquet|read_json|glob|httpfs)\b", re.I)


def cursor():
    return _con.cursor()


def _clean(v: Any) -> Any:
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, float):
        return round(v, 6)
    if isinstance(v, (list, tuple)):
        return [_clean(x) for x in v]
    return v


def run_sql(sql: str, max_rows: int = 200, timeout_s: float = 20.0) -> dict:
    s = sql.strip().rstrip(";").strip()
    if not re.match(r"^(select|with)\b", s, re.I):
        return {"error": "Only SELECT / WITH queries are allowed."}
    if ";" in s:
        return {"error": "Only one statement is allowed."}
    if FORBIDDEN.search(re.sub(r"'[^']*'", "''", s)):
        return {"error": "Query uses a forbidden keyword or function."}
    cur = cursor()
    timer = threading.Timer(timeout_s, cur.interrupt)
    t0 = time.time()
    timer.start()
    try:
        res = cur.execute(s)
        cols = [d[0] for d in res.description]
        rows = res.fetchmany(max_rows + 1)
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {str(e)[:600]}"}
    finally:
        timer.cancel()
        cur.close()
    truncated = len(rows) > max_rows
    rows = [[_clean(v) for v in r] for r in rows[:max_rows]]
    return {"columns": cols, "rows": rows, "row_count": len(rows), "truncated": truncated,
            "ms": int((time.time() - t0) * 1000)}


# ---------------------------------------------------------------- lookups
UZ_PRODUCT_GLOSSARY = {
    # Uzbek / colloquial word -> Russian catalogue word
    "paxta": "хлопок", "пахта": "хлопок", "xom ashyo": "хлопок-сырец", "chigit": "шрот",
    "sement": "цемент", "семент": "цемент", "bug'doy": "пшеница", "bugdoy": "пшеница", "буғдой": "пшеница",
    "un": "мука", "ун": "мука", "dizel": "дизельное", "дизел": "дизельное", "solyarka": "дизельное",
    "benzin": "бензин", "бензин": "бензин", "polietilen": "полиэтилен", "suyultirilgan gaz": "газ сжиженный",
    "gaz": "газ", "propan": "газ сжиженный", "armatura": "арматура", "shakar": "сахар", "шакар": "сахар",
    "paxta yog'i": "масло хлопковое", "yog'": "масло", "ёғ": "масло", "kungaboqar": "подсолнечное",
    "karbamid": "карбамид", "mochevina": "карбамид", "polipropilen": "полипропилен", "selitra": "селитра",
    "ammiakli": "селитра", "kunjara": "шрот", "shrot": "шрот", "bitum": "битум", "pvx": "поливинилхлорид",
    "polivinilxlorid": "поливинилхлорид", "g'isht": "кирпич", "gisht": "кирпич", "ғишт": "кирпич",
    "sulfat": "серная", "kislota": "кислота", "mazut": "мазут", "mis": "медный", "katod": "катод",
    "yog'och": "пиломатериал", "taxta": "пиломатериал", "guruch": "рис", "гуруч": "рис",
    "shisha": "стекло", "oyna": "стекло", "po'lat": "стальной", "list": "лист", "ip": "пряжа",
    "kalava": "пряжа", "tuz": "соль", "туз": "соль", "yem": "комбикорм", "omixta": "комбикорм",
    "gips": "гипс", "sim": "проволока", "alyumin": "алюминиевый", "profil": "профиль",
    "kaustik": "каустическая", "soda": "сода", "kabel": "кабель", "emal": "эмаль", "bo'yoq": "эмаль",
    "ohak": "известь", "azot": "азот", "suv": "вода", "сув": "вода", "podshipnik": "подшипник",
    "quvur": "труба", "truba": "труба", "argon": "аргон",
}

CYR2LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "j", "з": "z", "и": "i",
    "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ф": "f", "х": "x", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "'", "ы": "i", "ь": "",
    "э": "e", "ю": "yu", "я": "ya", "ў": "o'", "қ": "q", "ғ": "g'", "ҳ": "h",
}


def cyr2lat(s: str) -> str:
    return "".join(CYR2LAT.get(ch, ch) for ch in s.lower())


def lat2cyr(s: str) -> str:
    s = s.lower().replace("‘", "'").replace("’", "'").replace("ʻ", "'").replace("`", "'")
    pairs = [("o'", "ў"), ("g'", "ғ"), ("sh", "ш"), ("ch", "ч"), ("yo", "ё"), ("yu", "ю"), ("ya", "я"),
             ("ts", "ц")]
    for a, b in pairs:
        s = s.replace(a, b)
    single = {"a": "а", "b": "б", "v": "в", "g": "г", "d": "д", "e": "е", "j": "ж", "z": "з", "i": "и",
              "y": "й", "k": "к", "l": "л", "m": "м", "n": "н", "o": "о", "p": "п", "r": "р", "s": "с",
              "t": "т", "u": "у", "f": "ф", "x": "х", "q": "қ", "h": "ҳ", "'": "ъ"}
    return "".join(single.get(ch, ch) for ch in s)


def _norm(s: str) -> str:
    s = s.lower().replace("ё", "е").replace("‘", "'").replace("’", "'").replace("ʻ", "'")
    return re.sub(r"\s+", " ", s).strip()


_PRODUCTS = None


def _products():
    global _PRODUCTS
    if _PRODUCTS is None:
        cur = cursor()
        _PRODUCTS = cur.execute(
            "SELECT product_key, product_base, category, unit, deals, raw_names FROM products").fetchall()
        cur.close()
    return _PRODUCTS


def find_product(query: str, limit: int = 15) -> dict:
    q = _norm(query)
    terms = set(re.findall(r"[\w'\-/,\.ø]+", q))
    for k, v in UZ_PRODUCT_GLOSSARY.items():
        if k in q:
            terms.update(v.split())
    for t in list(terms):  # latin spelling of grades like ai-92 / dt-e-k5 -> cyrillic
        if re.search(r"[a-z]", t) and re.search(r"\d", t):
            terms.add(lat2cyr(t).replace("ъ", ""))
            terms.add(t.replace("ai", "аи").replace("dt", "дт"))
    terms = {t for t in terms if len(t) >= 2}
    scored = []
    for key, base, cat, unit, deals, raws in _products():
        hay = _norm(key + " " + " ".join(raws))
        hay_compact = hay.replace(" ", "").replace("-", "")
        score = 0.0
        for t in terms:
            tc = t.replace(" ", "").replace("-", "")
            if t in hay:
                score += 2 + len(t) / 10
            elif len(tc) >= 3 and tc in hay_compact:
                score += 1.5
            elif len(t) >= 5 and t[:-2] in hay:  # crude stemming for Russian endings
                score += 1
        if score > 0:
            scored.append((score, deals, key, base, cat, unit, raws))
    scored.sort(key=lambda x: (-x[0], -x[1]))
    out = [{"product_key": k, "product_base": b, "category": c, "unit": u, "deals": d,
            "raw_spellings": len(r), "example_raw_names": r[:4]}
           for _, d, k, b, c, u, r in scored[:limit]]
    return {"query": query, "matches": out,
            "note": "Filter deals with product_key = '...' for an exact variant, or product_base = '...' for all "
                    "variants of a product. If no match fits, the product is NOT in the data."}


def find_company(query: str, limit: int = 10) -> dict:
    q = query.strip()
    cur = cursor()
    try:
        digits = re.sub(r"\D", "", q)
        if len(digits) == 9:
            rows = cur.execute("SELECT inn, name, region, activity, role, vat_payer FROM companies WHERE inn = ?",
                               [digits]).fetchall()
            if not rows:
                return {"query": query, "matches": [], "note": f"INN {digits} does NOT exist in participants."}
        else:
            variants = {_norm(q), cyr2lat(_norm(q)), lat2cyr(_norm(q))}
            toks = [t for t in re.findall(r"[\w'ʻ‘’]+", _norm(q)) if len(t) >= 3 and t not in
                    {"mchj", "мчж", "ooo", "ооо", "ao", "ат", "xk", "хк", "mas'uliyati", "cheklangan", "jamiyati"}]
            conds, params = [], []
            for t in toks:
                alts = {t, cyr2lat(t), lat2cyr(t)}
                conds.append("(" + " OR ".join(["lower(name) LIKE ?"] * len(alts)) + ")")
                params += [f"%{a}%" for a in alts]
            if not conds:
                conds = ["lower(name) LIKE ?"]
                params = [f"%{list(variants)[0]}%"]
            rows = cur.execute(
                f"SELECT inn, name, region, activity, role, vat_payer FROM companies WHERE {' AND '.join(conds)} "
                f"LIMIT {limit}", params).fetchall()
        out = []
        for inn, name, region, act, role, vat in rows:
            s, b = cur.execute(
                "SELECT count(*) FILTER (WHERE seller_inn=?), count(*) FILTER (WHERE buyer_inn=?) FROM deals "
                "WHERE seller_inn=? OR buyer_inn=?", [inn, inn, inn, inn]).fetchone()
            out.append({"inn": inn, "name": name, "region": region, "activity": act, "role": role,
                        "vat_payer": vat, "deals_as_seller": s, "deals_as_buyer": b})
        return {"query": query, "matches": out,
                "note": "No match means the company is NOT in the data." if not out else ""}
    finally:
        cur.close()


def find_broker(query: str) -> dict:
    q = query.strip()
    cur = cursor()
    try:
        m = re.search(r"(bk|бк)\s*-?\s*(\d{1,3})", q, re.I)
        if m:
            code = f"BK{int(m.group(2)):03d}"
            rows = cur.execute("SELECT broker_code, name, inn, region FROM brokers WHERE broker_code=?",
                               [code]).fetchall()
        elif re.fullmatch(r"\d{9}", q):
            rows = cur.execute("SELECT broker_code, name, inn, region FROM brokers WHERE inn=?", [q]).fetchall()
        else:
            alts = {_norm(q), cyr2lat(_norm(q)), lat2cyr(_norm(q))}
            rows = cur.execute(
                "SELECT broker_code, name, inn, region FROM brokers WHERE " +
                " OR ".join(["lower(name) LIKE ?"] * len(alts)) + " LIMIT 10", [f"%{a}%" for a in alts]).fetchall()
        return {"query": query, "matches": [dict(zip(["broker_code", "name", "inn", "region"], r)) for r in rows],
                "note": "No match means the broker is NOT in the data." if not rows else ""}
    finally:
        cur.close()


def catalogue_text() -> str:
    lines = []
    for key, base, cat, unit, deals, raws in sorted(_products(), key=lambda r: (r[1], r[0])):
        lines.append(f"{key} [{unit}; {deals} deals]")
    return "\n".join(lines)


def enum_values() -> dict:
    cur = cursor()
    try:
        g = lambda sql: [r[0] for r in cur.execute(sql).fetchall()]
        return {
            "status": g("SELECT DISTINCT status FROM deals ORDER BY 1"),
            "auction_type": g("SELECT DISTINCT auction_type FROM deals ORDER BY 1"),
            "contract_type": g("SELECT DISTINCT contract_type FROM deals ORDER BY 1"),
            "contract_form": g("SELECT DISTINCT contract_form FROM deals ORDER BY 1"),
            "category": g("SELECT DISTINCT category FROM deals ORDER BY 1"),
            "industry": g("SELECT DISTINCT industry FROM deals ORDER BY 1"),
            "product_group": g("SELECT DISTINCT product_group FROM deals ORDER BY 1"),
            "region": g("SELECT DISTINCT region FROM deals ORDER BY 1"),
            "unit": g("SELECT DISTINCT unit FROM deals ORDER BY 1"),
            "activity": g("SELECT DISTINCT activity FROM companies ORDER BY 1"),
            "role": g("SELECT DISTINCT role FROM companies ORDER BY 1"),
        }
    finally:
        cur.close()
