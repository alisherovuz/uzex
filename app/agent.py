"""Orchestration: primary agent + independent verifier + reconciliation, packaged with its proof."""
import asyncio
import re
import time
import uuid
from collections import OrderedDict

from . import config, db
from .llm import Run, claude_followup, claude_loop, gpt_loop
from .validate import figures_agree

ANSWERS: "OrderedDict[str, dict]" = OrderedDict()
_CACHE: dict[str, str] = {}


def detect_lang(text: str) -> str:
    if re.search(r"[ўқғҳЎҚҒҲ]", text):
        return "uz_cyrl"
    if re.search(r"[а-яА-ЯёЁ]", text):
        uz_cyr_words = r"\b(қанча|нечта|битим|сотувчи|харидор|йил|ой|қайси|бўйича|ва|учун|эди|топ)\b"
        return "uz_cyrl" if re.search(uz_cyr_words, text.lower()) else "ru"
    return "uz"


def _providers():
    has_c, has_o = bool(config.ANTHROPIC_API_KEY), bool(config.OPENAI_API_KEY)
    if has_c and has_o:
        return ("claude", config.CLAUDE_MODEL), ("gpt", config.OPENAI_MODEL)
    if has_c:
        return ("claude", config.CLAUDE_MODEL), ("claude", config.CLAUDE_MODEL)
    if has_o:
        return ("gpt", config.OPENAI_MODEL), ("gpt", config.OPENAI_MODEL)
    return None, None


def _loop(kind):
    return claude_loop if kind == "claude" else gpt_loop


def _evidence(run: Run) -> list[dict]:
    """Collect sample deal ids returned by the evidence query (or any query) and fetch those deals."""
    ids: list[int] = []
    order = []
    ev = (run.final or {}).get("evidence_query_id")
    if ev in run.queries:
        order.append(run.queries[ev])
    order += [q for q in run.queries.values() if q is not (run.queries.get(ev))]
    for q in order:
        cols = q.get("columns", [])
        for ci, c in enumerate(cols):
            if "deal" in c.lower() and "id" in c.lower():
                for row in q.get("rows", [])[:20]:
                    v = row[ci]
                    for x in (v if isinstance(v, list) else [v]):
                        if isinstance(x, (int, float)) and x > 100000 and int(x) not in ids:
                            ids.append(int(x))
        if len(ids) >= 5:
            break
    ids = ids[:5]
    if not ids:
        return []
    r = db.run_sql(
        "SELECT d.deal_id, d.deal_date, d.product_raw, d.volume, d.unit, d.amount, d.currency, d.status, "
        "d.seller_inn, s.name AS seller, d.buyer_inn, b.name AS buyer FROM deals d "
        "LEFT JOIN companies s ON s.inn=d.seller_inn LEFT JOIN companies b ON b.inn=d.buyer_inn "
        f"WHERE d.deal_id IN ({','.join(map(str, ids))}) ORDER BY d.deal_id")
    return [dict(zip(r["columns"], row)) for row in r.get("rows", [])]


def _chart(run: Run):
    ch = (run.final or {}).get("chart")
    if not ch or ch.get("query_id") not in run.queries:
        return None
    q = run.queries[ch["query_id"]]
    cols = q.get("columns", [])
    if ch.get("x") not in cols or ch.get("y") not in cols:
        return None
    xi, yi = cols.index(ch["x"]), cols.index(ch["y"])
    rows = q.get("rows", [])[:40]
    vals = [r[yi] for r in rows]
    if not all(isinstance(v, (int, float)) for v in vals):
        return None
    return {"type": ch.get("type", "bar"), "title": ch.get("title", ""), "labels": [str(r[xi]) for r in rows],
            "values": vals}


def _pack_queries(run: Run) -> list[dict]:
    out = []
    for q in run.queries.values():
        out.append({k: q.get(k) for k in ("id", "purpose", "sql", "columns", "row_count", "ms", "error")} |
                   {"rows": (q.get("rows") or [])[:50]})
    return out


async def answer(question: str, emit=None) -> dict:
    question = question.strip()
    t0 = time.time()
    deadline = t0 + config.ANSWER_BUDGET_S
    lang = detect_lang(question)
    key = re.sub(r"\s+", " ", question.lower())
    if key in _CACHE and _CACHE[key] in ANSWERS:
        res = ANSWERS[_CACHE[key]]
        if emit:
            await emit({"type": "step", "text": "cache"})
        return res

    async def em(ev):
        if emit:
            await emit(ev)

    primary_p, verifier_p = _providers()
    if not primary_p:
        return {"id": None, "status": "error", "language": lang,
                "answer": "LLM API key is not configured (ANTHROPIC_API_KEY / OPENAI_API_KEY)."}

    hint = (f"\n\n[Question language detected: {lang}. Today in the data = 2026-10-30.]")
    p = Run("A", question + hint, primary_p[1])
    v = Run("B", question + hint, verifier_p[1])
    await em({"type": "step", "text": "start", "primary": primary_p[1], "verifier": verifier_p[1]})

    async def safe(loop, run, dl):
        try:
            await loop(run, em, dl)
        except Exception as e:  # noqa: BLE001
            run.error = f"{type(e).__name__}: {str(e)[:300]}"
        return run

    pt = asyncio.create_task(safe(_loop(primary_p[0]), p, deadline - 3))
    vt = asyncio.create_task(safe(_loop(verifier_p[0]), v, deadline - 18))
    await pt
    if p.final is None:
        # primary failed: fall back to the verifier's answer if it finishes
        await vt
        if v.final is not None:
            p, v = v, Run("C", question, "")
    else:
        await em({"type": "step", "text": "primary_done"})
        try:
            await asyncio.wait_for(asyncio.shield(vt), timeout=max(1, deadline - 18 - time.time()))
        except asyncio.TimeoutError:
            pass

    verification = {"state": "single", "primary": primary_p[1], "verifier": verifier_p[1], "note": ""}
    if p.final is not None and v.final is not None:
        ok, missing = figures_agree(p.final.get("key_figures", []), v.final.get("key_figures", []))
        if p.final.get("status") != v.final.get("status") and "not_found" in (p.final.get("status"), v.final.get("status")):
            ok = False
        if ok:
            verification["state"] = "verified"
        elif primary_p[0] == "claude" and deadline - time.time() > 22:
            await em({"type": "step", "text": "reconcile"})
            vf = v.final
            vq = "\n".join(f"- {q['purpose']}: {q['sql']}" for q in v.queries.values())[:4000]
            claude_followup(p, (
                "An independent analyst (another model) answered the same question differently.\n"
                f"Their key figures: {vf.get('key_figures')}\nTheir status: {vf.get('status')}\n"
                f"Their assumptions: {vf.get('assumptions')}\nTheir SQL:\n{vq}\n\n"
                "Find out which result is correct (run queries to check the difference, e.g. filters on cancelled "
                "deals, product variants, currency, period). Then call final_answer again with the correct answer. "
                "Write the answer text for the end user from scratch, exactly as a normal answer: do NOT mention "
                "the other analyst, a first/second answer or this check in `answer` or `speech` (you may add one "
                "short line about the cross-check to `assumptions`)."))
            prev = dict(p.final) if p.final else None
            p.final = None
            await safe(claude_loop, p, deadline - 2)
            if p.final is None:
                p.final = prev
            ok2, _ = figures_agree(p.final.get("key_figures", []), vf.get("key_figures", []))
            verification["state"] = "verified" if ok2 else "reconciled"
            verification["note"] = "" if ok2 else ", ".join(missing)
        else:
            verification["state"] = "mismatch"
            verification["note"] = ", ".join(missing)
        verification["verifier_figures"] = v.final.get("key_figures", [])
    elif not vt.done():
        vt.cancel()

    f = p.final
    if f is None:
        msg = {"ru": "Не удалось получить ответ за отведённое время. Попробуйте переформулировать вопрос.",
               "uz_cyrl": "Ажратилган вақтда жавоб олинмади. Саволни бошқача беринг.",
               "uz": "Ajratilgan vaqtda javob olinmadi. Savolni boshqacha bering."}[lang]
        res = {"id": None, "status": "error", "language": lang, "answer": msg, "speech": msg,
               "error": p.error or v.error}
        return res

    rid = uuid.uuid4().hex[:10]
    res = {
        "id": rid, "question": question, "status": f.get("status"), "language": f.get("language", lang),
        "answer": f.get("answer", ""), "speech": f.get("speech", ""), "assumptions": f.get("assumptions", []),
        "key_figures": f.get("key_figures", []), "verification": verification,
        "numbers_check": {"ok": not p.unbacked, "unbacked": p.unbacked},
        "queries": _pack_queries(p), "lookups": p.lookups,
        "verifier_queries": [{"purpose": q["purpose"], "sql": q["sql"]} for q in v.queries.values()],
        "evidence": await asyncio.to_thread(_evidence, p), "chart": _chart(p),
        "seconds": round(time.time() - t0, 1), "created": int(time.time()),
    }
    ANSWERS[rid] = res
    _CACHE[key] = rid
    while len(ANSWERS) > 2000:
        ANSWERS.popitem(last=False)
    return res
