"""Run the exam against a running Isbotli Agent and score it.

Usage: python exam/run_exam.py https://your-app-url [uz|ru|both] [concurrency]
Writes exam/results.json and prints the score, timing and every failure.
"""
import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.validate import parse_numbers  # noqa: E402

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8000"
LANGS = {"uz": ["uz"], "ru": ["ru"]}.get(sys.argv[2] if len(sys.argv) > 2 else "both", ["uz", "ru"])
CONC = int(sys.argv[3]) if len(sys.argv) > 3 else 3
QS = json.load(open(Path(__file__).parent / "questions.json"))


def close(a, b, tol):
    return abs(a - b) <= max(abs(b) * tol, 0.51 if abs(b) >= 100 else 0.006)


def score(q, res):
    ans = res.get("answer", "") or ""
    nums = [n for _, n, _ in parse_numbers(ans)] + [k.get("value") for k in res.get("key_figures", [])
                                                    if isinstance(k.get("value"), (int, float))]
    kind, exp = q["kind"], q["expected"]
    if kind == "not_found":
        return res.get("status") in ("not_found", "clarify")
    if res.get("status") == "not_found":
        return False
    if kind == "number":
        return any(close(n, exp, q["tol"]) for n in nums)
    if kind == "any_of":
        return any(close(n, e, q["tol"]) for n in nums for e in exp)
    if kind in ("text", "text_inn"):
        return str(exp).lower() in ans.lower()
    return False


async def main():
    sem = asyncio.Semaphore(CONC)
    results = []
    async with httpx.AsyncClient(timeout=httpx.Timeout(130.0)) as c:
        async def one(q, lang):
            async with sem:
                t0 = time.time()
                try:
                    r = await c.post(f"{BASE}/api/ask", json={"question": q[lang]})
                    res = r.json()
                except Exception as e:  # noqa: BLE001
                    res = {"answer": f"ERROR {e}", "status": "error"}
                dt = time.time() - t0
                ok = score(q, res)
                results.append({"id": q["id"], "lang": lang, "question": q[lang], "expected": q["expected"],
                                "ok": ok, "seconds": round(dt, 1), "status": res.get("status"),
                                "verification": (res.get("verification") or {}).get("state"),
                                "answer": res.get("answer"), "link": f"{BASE}/a/{res.get('id')}"})
                print(f"{'PASS' if ok else 'FAIL'} {dt:5.1f}s [{lang}] {q['id']}", flush=True)
        await asyncio.gather(*[one(q, lang) for q in QS for lang in LANGS])
    n = len(results)
    p = sum(r["ok"] for r in results)
    secs = [r["seconds"] for r in results]
    traps = [r for r in results if r["id"].startswith("trap_")]
    print(f"\nSCORE {p}/{n} = {100*p/n:.1f}%  | traps refused {sum(r['ok'] for r in traps)}/{len(traps)} "
          f"| avg {sum(secs)/n:.1f}s max {max(secs):.1f}s | verified "
          f"{sum(r['verification']=='verified' for r in results)}/{n}")
    for r in results:
        if not r["ok"]:
            print(f"\n✗ {r['id']} [{r['lang']}] expected={r['expected']}\n  Q: {r['question']}\n  A: {(r['answer'] or '')[:400]}\n  {r['link']}")
    json.dump(results, open(Path(__file__).parent / "results.json", "w"), ensure_ascii=False, indent=1, default=str)


asyncio.run(main())
