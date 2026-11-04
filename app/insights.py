"""Dashboard overview and the 'market briefing' — fixed SQL, every number computed from data."""
from functools import lru_cache

from . import db


def q(sql: str) -> list[dict]:
    r = db.run_sql(sql, max_rows=500)
    if "error" in r:
        raise RuntimeError(r["error"])
    return [dict(zip(r["columns"], row)) for row in r["rows"]]


@lru_cache(maxsize=1)
def overview() -> dict:
    k = q("""SELECT count(*) AS deals, count(*) FILTER (WHERE is_cancelled) AS cancelled,
                    count(*) FILTER (WHERE is_executed) AS executed,
                    round(sum(amount_uzs) FILTER (WHERE NOT is_cancelled)) AS amount_uzs,
                    round(sum(amount_usd) FILTER (WHERE NOT is_cancelled)) AS amount_usd,
                    count(DISTINCT seller_inn) AS sellers, count(DISTINCT buyer_inn) AS buyers,
                    count(DISTINCT product_key) AS products, count(DISTINCT seller_broker) AS brokers,
                    min(deal_date) AS first_date, max(deal_date) AS last_date FROM deals""")[0]
    k["cancel_rate"] = round(100 * k["cancelled"] / k["deals"], 2)
    monthly = q("""SELECT ym, count(*) AS deals, round(sum(amount_uzs) FILTER (WHERE NOT is_cancelled)/1e9, 2) AS bln_uzs,
                          round(100.0*count(*) FILTER (WHERE is_cancelled)/count(*), 2) AS cancel_rate
                   FROM deals GROUP BY ym ORDER BY ym""")
    cats = q("""SELECT category, count(*) AS deals, round(sum(amount_uzs) FILTER (WHERE NOT is_cancelled)/1e9, 1) AS bln_uzs
                FROM deals GROUP BY 1 ORDER BY bln_uzs DESC""")
    prods = q("""SELECT product_base, count(*) AS deals, round(sum(amount_uzs) FILTER (WHERE NOT is_cancelled)/1e9, 1) AS bln_uzs
                 FROM deals GROUP BY 1 ORDER BY bln_uzs DESC LIMIT 10""")
    regions = q("""SELECT region, count(*) AS deals, round(sum(amount_uzs) FILTER (WHERE NOT is_cancelled)/1e9, 1) AS bln_uzs
                   FROM deals GROUP BY 1 ORDER BY bln_uzs DESC""")
    status = q("SELECT status, count(*) AS deals FROM deals GROUP BY 1 ORDER BY 2 DESC")
    risky = q("""SELECT d.buyer_inn AS inn, c.name, count(*) AS deals, count(*) FILTER (WHERE is_cancelled) AS cancelled,
                        round(100.0*count(*) FILTER (WHERE is_cancelled)/count(*), 1) AS cancel_rate
                 FROM deals d LEFT JOIN companies c ON c.inn=d.buyer_inn
                 GROUP BY 1,2 HAVING count(*) >= 20 ORDER BY cancel_rate DESC, deals DESC LIMIT 8""")
    by_year = q("""SELECT year, count(*) AS deals, round(sum(amount_uzs) FILTER (WHERE NOT is_cancelled)/1e9, 1) AS bln_uzs
                   FROM deals GROUP BY 1 ORDER BY 1""")
    return {"kpi": k, "monthly": monthly, "categories": cats, "products": prods, "regions": regions,
            "status": status, "risky_buyers": risky, "by_year": by_year}


def _fmt(x, d=0) -> str:
    s = f"{x:,.{d}f}".replace(",", " ").replace(".", ",")
    return s


@lru_cache(maxsize=4)
def briefing(lang: str = "uz") -> dict:
    m = q("""SELECT ym, count(*) AS deals, sum(amount_uzs) FILTER (WHERE NOT is_cancelled) AS amt,
                    100.0*count(*) FILTER (WHERE is_cancelled)/count(*) AS cr
             FROM deals WHERE ym IN ('2026-09','2026-10') GROUP BY ym ORDER BY ym""")
    sep, octo = m[0], m[1]
    top = q("""SELECT product_base, sum(amount_uzs) AS amt FROM deals
               WHERE ym='2026-10' AND NOT is_cancelled GROUP BY 1 ORDER BY 2 DESC LIMIT 1""")[0]
    px = q("""WITH p AS (SELECT product_key || ' (' || unit_norm || ')' AS product_key, ym, sum(amount_uzs)/sum(volume_norm) AS price, count(*) AS n FROM deals
                         WHERE ym IN ('2026-09','2026-10') AND NOT is_cancelled GROUP BY 1,2)
              SELECT a.product_key, round(100*(b.price/a.price-1), 1) AS chg FROM p a JOIN p b
                ON a.product_key=b.product_key AND a.ym='2026-09' AND b.ym='2026-10'
              WHERE a.n>=30 AND b.n>=30 ORDER BY abs(b.price/a.price-1) DESC LIMIT 1""")[0]
    late = q("""SELECT count(*) AS n FROM deals WHERE ym='2026-10' AND delivery_delay_days > 0""")[0]["n"]
    risky = q("""SELECT c.name, d.buyer_inn, round(100.0*count(*) FILTER (WHERE is_cancelled)/count(*),1) AS cr, count(*) AS n
                 FROM deals d LEFT JOIN companies c ON c.inn=d.buyer_inn WHERE year=2026
                 GROUP BY 1,2 HAVING count(*)>=15 ORDER BY cr DESC LIMIT 1""")[0]
    dchg = 100 * (octo["deals"] / sep["deals"] - 1)
    achg = 100 * (octo["amt"] / sep["amt"] - 1)
    v = dict(deals=_fmt(octo["deals"]), dchg=_fmt(dchg, 1), amt=_fmt(octo["amt"] / 1e9, 1), achg=_fmt(achg, 1),
             top=top["product_base"], topamt=_fmt(top["amt"] / 1e9, 1), pk=px["product_key"], pchg=_fmt(px["chg"], 1),
             cr=_fmt(octo["cr"], 1), late=_fmt(late), rname=risky["name"], rinn=risky["buyer_inn"],
             rcr=_fmt(risky["cr"], 1), rn=_fmt(risky["n"]))
    sign = lambda x: "+" if float(str(x).replace(",", ".").replace(" ", "")) > 0 else ""
    if lang == "ru":
        text = (f"Октябрь 2026: **{v['deals']}** сделок ({sign(v['dchg'])}{v['dchg']}% к сентябрю), оборот без "
                f"аннулированных — **{v['amt']} млрд сум** ({sign(v['achg'])}{v['achg']}%).\n"
                f"Лидер по обороту — {v['top']} ({v['topamt']} млрд сум).\n"
                f"Сильнее всего изменилась цена: {v['pk']} ({sign(v['pchg'])}{v['pchg']}% за месяц).\n"
                f"Доля аннулированных сделок — {v['cr']}%, поставок с опозданием — {v['late']}.\n"
                f"Риск: покупатель {v['rname']} (ИНН {v['rinn']}) — {v['rcr']}% аннулированных из {v['rn']} сделок в 2026 году.")
        speech = (f"В октябре заключено {v['deals']} сделок, оборот {v['amt']} миллиарда сумов. "
                  f"Лидер — {v['top']}. Доля аннулированных — {v['cr']} процента.")
    else:
        text = (f"2026-yil oktyabr: **{v['deals']}** ta bitim (sentyabrga nisbatan {sign(v['dchg'])}{v['dchg']}%), "
                f"bekor qilinganlarsiz savdo hajmi — **{v['amt']} mlrd so'm** ({sign(v['achg'])}{v['achg']}%).\n"
                f"Savdo hajmi bo'yicha yetakchi — {v['top']} ({v['topamt']} mlrd so'm).\n"
                f"Narxi eng ko'p o'zgargan tovar: {v['pk']} (bir oyda {sign(v['pchg'])}{v['pchg']}%).\n"
                f"Bekor qilingan bitimlar ulushi — {v['cr']}%, kechikib yetkazilganlar — {v['late']} ta.\n"
                f"Xavf: xaridor {v['rname']} (STIR {v['rinn']}) — 2026-yilda {v['rn']} ta bitimning {v['rcr']}% bekor qilingan.")
        speech = (f"Oktyabr oyida {v['deals']} ta bitim tuzildi, savdo hajmi {v['amt']} milliard so'm. "
                  f"Yetakchi tovar — {v['top']}. Bekor qilingan bitimlar ulushi {v['cr']} foiz.")
    return {"text": text, "speech": speech, "values": v}
