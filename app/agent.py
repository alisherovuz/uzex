"""Orchestration: primary agent + independent verifier + reconciliation, packaged with its proof."""
import asyncio
import json
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


GPT_OK = {"ok": True}


def _providers():
    has_c, has_o = bool(config.ANTHROPIC_API_KEY), bool(config.OPENAI_API_KEY) and GPT_OK["ok"]
    if has_c and has_o:
        return ("claude", config.CLAUDE_MODEL), ("gpt", config.OPENAI_MODEL)
    if has_c:  # independent check: a different Claude model verifies
        return ("claude", config.CLAUDE_MODEL), ("claude", config.VERIFIER_CLAUDE_MODEL)
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


def _coerce(v, kind):
    """Models sometimes send nested fields as JSON strings; normalize them."""
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except Exception:  # noqa: BLE001
            return [v] if kind is list and v.strip() else None
    return v if isinstance(v, kind) else None


def _normalize(f: dict) -> dict:
    f["chart"] = _coerce(f.get("chart"), dict)
    f["key_figures"] = [k for k in (_coerce(f.get("key_figures"), list) or []) if isinstance(k, dict)]
    for k in ("assumptions", "followups", "used_query_ids"):
        f[k] = [str(x) for x in (_coerce(f.get(k), list) or [])]
    return f


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


VERIFY: dict[str, asyncio.Task] = {}
EXTRAS: dict[str, asyncio.Task] = {}

EXTRAS_PROMPT = """You help a voice assistant for the UZEX exchange. Given a question and the final answer, return ONLY
JSON: {"speech": "...", "followups": ["...", "...", "..."]}.
speech: 1–2 short sentences in the answer's language (Uzbek always in Latin script) that a native-speaker voice will
read aloud. Write EVERY number in words, rounded (e.g. "taxminan yuz yetmish olti ming tonna", "около ста семидесяти
шести тысяч тонн"). No digits, INNs, ids, % signs, codes like ДТ-Е-К5, brackets or markdown. In Uzbek use everyday
Uzbek product names (dizel yoqilg'isi, shakar, bug'doy, sement, paxta, un), not Russian registry names. Never add facts
that are not in the answer.
followups: 3 short natural next questions in the same language that can be answered from the same deal registry."""


async def make_extras(res: dict) -> dict:
    import anthropic
    lang = res.get("language", "uz")
    try:
        client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY, max_retries=1)
        r = await asyncio.wait_for(client.messages.create(
            model=config.FAST_MODEL, max_tokens=500, system=EXTRAS_PROMPT,
            messages=[{"role": "user", "content": f"Language: {lang}\nQuestion: {res.get('question')}\n"
                                                  f"Answer:\n{res.get('answer')}"}]), timeout=20)
        txt = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
        m = re.search(r"\{.*\}", txt, re.S)
        data = json.loads(m.group(0)) if m else {}
    except Exception:  # noqa: BLE001
        data = {}
    speech = data.get("speech") or re.sub(r"\*\*|[-•] ", "", (res.get("answer") or "").split("\n")[0])
    res["speech"] = speech
    res["followups"] = [str(x) for x in (data.get("followups") or [])][:3]
    return {"speech": res["speech"], "followups": res["followups"]}


def _pack(rid, question, lang, p: Run, v: Run, verification, t0) -> dict:
    f = _normalize(p.final)
    return {
        "id": rid, "question": question, "status": f.get("status"), "language": f.get("language", lang),
        "answer": f.get("answer", ""), "speech": f.get("speech", ""), "assumptions": f.get("assumptions", []),
        "key_figures": f.get("key_figures", []), "verification": verification,
        "followups": (f.get("followups") or [])[:3],
        "numbers_check": {"ok": not p.unbacked, "unbacked": p.unbacked},
        "queries": _pack_queries(p), "lookups": p.lookups,
        "verifier_queries": [{"purpose": q["purpose"], "sql": q["sql"]} for q in v.queries.values()],
        "evidence": _evidence(p), "chart": _chart(p),
        "seconds": round(time.time() - t0, 1), "created": int(time.time()),
    }


async def answer(question: str, emit=None, wait_verify: bool = False) -> dict:
    """Answer as soon as the primary model is done; the independent check finishes in the background
    (VERIFY[rid]) and updates the stored answer (and the stream, via `emit`) when it completes."""
    question = question.strip()
    t0 = time.time()
    deadline = t0 + config.ANSWER_BUDGET_S
    lang = detect_lang(question)
    key = re.sub(r"\s+", " ", question.lower())
    if key in _CACHE and _CACHE[key] in ANSWERS:
        rid = _CACHE[key]
        if wait_verify and rid in VERIFY:
            await VERIFY[rid]
        return ANSWERS[rid]

    async def em(ev):
        if emit:
            try:
                await emit(ev)
            except Exception:  # noqa: BLE001
                pass

    primary_p, verifier_p = _providers()
    if not primary_p:
        return {"id": None, "status": "error", "language": lang,
                "answer": "LLM API key is not configured (ANTHROPIC_API_KEY / OPENAI_API_KEY)."}

    hint = f"\n\n[Question language detected: {lang}. Today in the data = 2026-10-30.]"
    p = Run("A", question + hint, primary_p[1])
    v = Run("B", question + hint, verifier_p[1])
    verification = {"state": "pending", "primary": primary_p[1], "verifier": verifier_p[1], "note": ""}
    await em({"type": "step", "text": "start", "primary": primary_p[1], "verifier": verifier_p[1]})

    async def safe(loop, run, dl):
        try:
            await loop(run, em, dl)
        except Exception as e:  # noqa: BLE001
            run.error = f"{type(e).__name__}: {str(e)[:300]}"
        return run

    vdeadline = t0 + config.VERIFY_BUDGET_S

    async def verify():
        await safe(_loop(verifier_p[0]), v, vdeadline)
        if v.final is None and verifier_p[0] == "gpt" and config.ANTHROPIC_API_KEY and vdeadline - time.time() > 20:
            if v.error and ("401" in v.error or "auth" in v.error.lower()):
                GPT_OK["ok"] = False  # stop calling a key that is rejected
            v.__init__("B", question + hint, config.VERIFIER_CLAUDE_MODEL)
            verification["verifier"] = config.VERIFIER_CLAUDE_MODEL
            await safe(claude_loop, v, vdeadline)
        return v

    pt = asyncio.create_task(safe(_loop(primary_p[0]), p, deadline - 3))
    vt = asyncio.create_task(verify())
    await pt
    if p.final is None:  # primary failed: use the verifier's answer if it gets one
        await vt
        if v.final is None:
            msg = {"ru": "Не удалось получить ответ за отведённое время. Попробуйте переформулировать вопрос.",
                   "uz_cyrl": "Ажратилган вақтда жавоб олинмади. Саволни бошқача беринг.",
                   "uz": "Ajratilgan vaqtda javob olinmadi. Savolni boshqacha bering."}[lang]
            return {"id": None, "status": "error", "language": lang, "answer": msg, "speech": msg,
                    "error": p.error or v.error}
        p, v = v, Run("C", question, "")
        verification["state"] = "single"

    rid = uuid.uuid4().hex[:10]
    res = await asyncio.to_thread(_pack, rid, question, lang, p, v, verification, t0)
    ANSWERS[rid] = res
    _CACHE[key] = rid
    while len(ANSWERS) > 2000:
        ANSWERS.popitem(last=False)

    async def finish():
        if verification["state"] != "pending":
            return
        await vt
        if v.final is None:
            verification["state"] = "single"
        else:
            _normalize(v.final)
            ok, missing = figures_agree(p.final.get("key_figures", []), v.final.get("key_figures", []))
            if p.final.get("status") != v.final.get("status") and "not_found" in (p.final.get("status"), v.final.get("status")):
                ok = False
            verification["verifier_figures"] = v.final.get("key_figures", [])
            if ok:
                verification["state"] = "verified"
            elif primary_p[0] == "claude":
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
                prev = dict(p.final)
                p.final = None
                await safe(claude_loop, p, time.time() + 40)
                if p.final is None:
                    p.final = prev
                ok2, _ = figures_agree(p.final.get("key_figures", []), vf.get("key_figures", []))
                verification["state"] = "verified" if ok2 else "reconciled"
                verification["note"] = "" if ok2 else ", ".join(missing)
                if p.final is not prev:
                    new = await asyncio.to_thread(_pack, rid, question, lang, p, v, verification, t0)
                    new["seconds"] = res["seconds"]
                    res.update(new)
                    await em({"type": "revised", "result": res})
            else:
                verification["state"] = "mismatch"
                verification["note"] = ", ".join(missing)
        res["verifier_queries"] = [{"purpose": q["purpose"], "sql": q["sql"]} for q in v.queries.values()]
        res["verification"] = verification
        res["verify_seconds"] = round(time.time() - t0, 1)
        await em({"type": "verification", "id": rid, "verification": verification,
                  "verifier_queries": res["verifier_queries"], "verify_seconds": res["verify_seconds"]})

    async def extras():
        ex = await make_extras(res)
        await em({"type": "extras", "id": rid, **ex})

    xt = asyncio.create_task(extras())
    EXTRAS[rid] = xt
    xt.add_done_callback(lambda _t: EXTRAS.pop(rid, None))
    task = asyncio.create_task(finish())
    VERIFY[rid] = task
    task.add_done_callback(lambda _t: VERIFY.pop(rid, None))
    if wait_verify:
        await task
        await xt
    return res
