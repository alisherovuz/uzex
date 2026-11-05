"""Benchmark model configurations on the full question bank (primary answer only, no verifier).
Usage: python exam/bench_models.py CONFIG [concurrency]   CONFIG in sonnet | haiku | opus | opus_fast"""
import asyncio, json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import llm  # noqa: E402
from app.validate import parse_numbers  # noqa: E402

CFG = {"sonnet": ("claude-sonnet-5-5", False), "haiku": ("claude-haiku-5-5", False),
       "opus": ("claude-opus-5-5", False), "opus_fast": ("claude-opus-5-5", True)}
name = sys.argv[1]; model, fast = CFG[name]; CONC = int(sys.argv[2]) if len(sys.argv) > 2 else 8
E = Path(__file__).parent
bank = []
for q in json.load(open(E / "questions.json")):  # standard exam, both languages
    spec = {"number": {"nums_any": [q["expected"]]} if not isinstance(q["expected"], list) else {},
            "any_of": {"nums_any": q["expected"]}, "text": {"texts_any": [str(q["expected"])]},
            "text_inn": {"texts_any": [str(q["expected"])]}, "not_found": {"not_found": True}}[q["kind"]]
    if q["kind"] == "number": spec = {"nums_any": [q["expected"]]}
    for lang in ("uz", "ru"):
        bank.append({"id": f"std_{q['id']}_{lang}", "q": q[lang], "tol": q["tol"], **spec})
for f in ("hard.json", "bench.json"):
    for q in json.load(open(E / f)):
        bank.append({**q, "id": f"{f[:5]}_{q['id']}"})


import os
if os.getenv("IDS"): bank = [q for q in bank if q["id"] in os.getenv("IDS").split(",")]
OUT = os.getenv("OUT", "")


def score(q, f):
    if f is None: return False
    if q.get("not_found"): return f.get("status") in ("not_found", "clarify")
    if f.get("status") == "not_found": return False
    ans = f.get("answer", ""); low = ans.lower().replace("’", "'").replace("ʻ", "'")
    kfs = f.get("key_figures") or []
    nums = [n for _, n, _ in parse_numbers(ans)] + [k["value"] for k in kfs if isinstance(k, dict) and isinstance(k.get("value"), (int, float))]
    near = lambda e: any(abs(n - e) <= max(abs(e) * q["tol"], 0.51 if abs(e) >= 100 else 0.051) for n in nums)
    if "nums_any" in q and not any(near(e) for e in q["nums_any"]): return False
    if any(not near(e) for e in q.get("nums_all", [])): return False
    if "texts_any" in q and not any(t.lower() in low for t in q["texts_any"]): return False
    if any(not any(t.lower() in low for t in g) for g in q.get("texts_all", [])): return False
    return True


async def main():
    sem = asyncio.Semaphore(CONC); res = []
    async def one(q):
        async with sem:
            r = llm.Run("A", q["q"] + "\n\n[Today in the data = 2026-10-30.]", model); r.fast = fast
            t0 = time.time()
            try:
                await llm.claude_loop(r, None, time.time() + 75)
            except Exception as e:  # noqa: BLE001
                r.error = str(e)[:200]
            dt = time.time() - t0
            ok = score(q, r.final)
            res.append({"id": q["id"], "ok": ok, "sec": round(dt, 2), "err": r.error,
                        "q": q["q"], "final": r.final,
                        "unbacked": len(r.unbacked), "rejections": r.rejections})
    t = time.time()
    await asyncio.gather(*[one(q) for q in bank])
    res.sort(key=lambda r: r["sec"])
    secs = [r["sec"] for r in res]; n = len(res); p = sum(r["ok"] for r in res)
    summ = {"config": name, "model": model, "fast": fast, "n": n, "correct": p, "accuracy": round(100 * p / n, 1),
            "avg_s": round(sum(secs) / n, 2), "p50_s": secs[n // 2], "p90_s": secs[int(n * .9)], "max_s": secs[-1],
            "errors": sum(1 for r in res if r["err"]), "wall_min": round((time.time() - t) / 60, 1)}
    print(json.dumps(summ))
    json.dump({"summary": summ, "results": res}, open(E / f"bench_{name}{OUT}.json", "w"), ensure_ascii=False, indent=1, default=str)

if __name__ == "__main__":
    asyncio.run(main())
