"""On-server OpenAI model benchmark. Runs in the background at startup only when BENCH=1.

The sandbox used to develop this project cannot reach api.openai.com, so the OpenAI
side of the benchmark runs here, where the server can. Results are logged (one
BENCHRESULT json line per model/tier) and written to /tmp so they survive until restart.
It uses the exact same 296-question bank and code-computed answer keys as
exam/bench_models.py, and the same scorer, so OpenAI and Anthropic numbers are comparable.
"""
import asyncio
import json
import logging
import time
from pathlib import Path

from . import config, llm
from .validate import parse_numbers

log = logging.getLogger("bench")
ROOT = Path(__file__).resolve().parent.parent
E = ROOT / "exam"


def build_bank() -> list[dict]:
    bank: list[dict] = []
    for q in json.load(open(E / "questions.json")):
        if q["kind"] == "number":
            spec = {"nums_any": [q["expected"]]}
        elif q["kind"] == "any_of":
            spec = {"nums_any": q["expected"]}
        elif q["kind"] in ("text", "text_inn"):
            spec = {"texts_any": [str(q["expected"])]}
        elif q["kind"] == "not_found":
            spec = {"not_found": True}
        else:
            spec = {}
        for lang in ("uz", "ru"):
            bank.append({"id": f"std_{q['id']}_{lang}", "q": q[lang], "tol": q["tol"], **spec})
    for f in ("hard.json", "bench.json"):
        for q in json.load(open(E / f)):
            bank.append({**q, "id": f"{f[:5]}_{q['id']}"})
    return bank


def score(q: dict, f: dict | None) -> bool:
    if f is None:
        return False
    if q.get("not_found"):
        return f.get("status") in ("not_found", "clarify")
    if f.get("status") == "not_found":
        return False
    ans = f.get("answer", "")
    low = ans.lower().replace("’", "'").replace("ʻ", "'")
    kfs = f.get("key_figures") or []
    nums = [n for _, n, _ in parse_numbers(ans)] + [
        k["value"] for k in kfs if isinstance(k, dict) and isinstance(k.get("value"), (int, float))
    ]

    def near(e: float) -> bool:
        tol = max(abs(e) * q["tol"], 0.51 if abs(e) >= 100 else 0.051)
        return any(abs(n - e) <= tol for n in nums)

    if "nums_any" in q and not any(near(e) for e in q["nums_any"]):
        return False
    if any(not near(e) for e in q.get("nums_all", [])):
        return False
    if "texts_any" in q and not any(t.lower() in low for t in q["texts_any"]):
        return False
    if any(not any(t.lower() in low for t in g) for g in q.get("texts_all", [])):
        return False
    return True


async def discover_models(candidates: list[str]) -> list[str]:
    """Keep only model ids the key can actually list."""
    import openai
    client = openai.AsyncOpenAI(api_key=config.OPENAI_API_KEY)
    try:
        available = {m.id async for m in client.models.list()}
    except Exception as e:  # noqa: BLE001
        log.warning("bench: could not list models (%s); trying all candidates", str(e)[:200])
        return candidates
    ok = [m for m in candidates if m in available]
    missing = [m for m in candidates if m not in available]
    log.info("bench: available=%s  missing=%s", ok, missing)
    gpt = sorted(m for m in available if m.startswith(("gpt-6", "gpt-5")))
    log.info("bench: all gpt-5/6 models on key: %s", gpt)
    return ok


async def run_one(model: str, tier: str, bank: list[dict], conc: int) -> dict:
    sem = asyncio.Semaphore(conc)
    res: list[dict] = []

    async def one(q: dict) -> None:
        async with sem:
            r = llm.Run("A", q["q"] + "\n\n[Today in the data = 2026-10-30.]", model)
            r.tier = None if tier == "default" else tier
            t0 = time.time()
            try:
                await llm.gpt_loop(r, None, time.time() + 75)
            except Exception as e:  # noqa: BLE001
                r.error = f"{type(e).__name__}: {str(e)[:160]}"
            dt = time.time() - t0
            res.append({"id": q["id"], "ok": score(q, r.final), "sec": round(dt, 2),
                        "err": r.error, "final": r.final})

    t = time.time()
    await asyncio.gather(*[one(q) for q in bank])
    res.sort(key=lambda r: r["sec"])
    secs = [r["sec"] for r in res]
    n = len(res)
    correct = sum(r["ok"] for r in res)
    summ = {
        "config": f"{model}{'' if tier == 'default' else '/' + tier}",
        "model": model, "tier": tier, "n": n, "correct": correct,
        "accuracy": round(100 * correct / n, 1),
        "avg_s": round(sum(secs) / n, 2), "p50_s": secs[n // 2],
        "p90_s": secs[int(n * 0.9)], "p99_s": secs[int(n * 0.99)], "max_s": secs[-1],
        "errors": sum(1 for r in res if r["err"]),
        "wall_min": round((time.time() - t) / 60, 1),
    }
    out = Path("/tmp") / f"bench_{model.replace('/', '_')}_{tier}.json"
    try:
        json.dump({"summary": summ, "results": res}, open(out, "w"), ensure_ascii=False, indent=1, default=str)
    except Exception:  # noqa: BLE001
        pass
    log.info("BENCHRESULT %s", json.dumps(summ, ensure_ascii=False))
    errs = [r for r in res if r["err"]][:3]
    if errs:
        log.info("bench: sample errors for %s: %s", summ["config"], [(e["id"], e["err"]) for e in errs])
    wrong = [r["id"] for r in res if not r["ok"] and not r["err"]][:12]
    if wrong:
        log.info("bench: wrong (no error) for %s: %s", summ["config"], wrong)
    return summ


async def run_openai_bench() -> None:
    if not config.OPENAI_API_KEY:
        log.warning("bench: no OpenAI key; nothing to do")
        return
    await asyncio.sleep(8)  # let the server finish starting and serve any early jury traffic first
    bank = build_bank()
    candidates = [m.strip() for m in config.BENCH_MODELS.split(",") if m.strip()] or [config.OPENAI_MODEL]
    tiers = [t.strip() for t in config.BENCH_TIERS.split(",") if t.strip()] or ["default"]
    log.info("bench: start  models=%s tiers=%s bank=%d conc=%d", candidates, tiers, len(bank), config.BENCH_CONC)
    models = await discover_models(candidates)
    if not models:
        log.warning("bench: none of the requested models are available on this key")
        return
    summaries = []
    for model in models:
        for tier in tiers:
            try:
                summaries.append(await run_one(model, tier, bank, config.BENCH_CONC))
            except Exception as e:  # noqa: BLE001
                log.warning("bench: %s/%s failed: %s", model, tier, str(e)[:200])
    log.info("BENCHDONE %s", json.dumps(summaries, ensure_ascii=False))
