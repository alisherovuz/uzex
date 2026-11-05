"""Run the HARD exam against a running agent. Usage: python exam/run_hard.py URL [concurrency]"""
import asyncio, json, re, sys, time
from pathlib import Path
import httpx
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.validate import parse_numbers  # noqa: E402

BASE = sys.argv[1].rstrip("/"); CONC = int(sys.argv[2]) if len(sys.argv) > 2 else 3
QS = json.load(open(Path(__file__).parent / "hard.json"))
ONLY = set(sys.argv[3].split(",")) if len(sys.argv) > 3 else None


def has_num(nums, e, tol):
    return any(abs(n - e) <= max(abs(e) * tol, 0.51 if abs(e) >= 100 else 0.051) for n in nums)


def score(q, res):
    ans = (res.get("answer") or "")
    low = ans.lower().replace("ʻ", "'").replace("’", "'")
    nums = [n for _, n, _ in parse_numbers(ans)] + [k["value"] for k in res.get("key_figures", []) if isinstance(k, dict) and isinstance(k.get("value"), (int, float))]
    why = []
    if q.get("not_found"):
        return res.get("status") in ("not_found", "clarify"), "status=" + str(res.get("status"))
    if "nums_any" in q and not any(has_num(nums, e, q["tol"]) for e in q["nums_any"]):
        why.append(f"none of {q['nums_any']}")
    for e in q.get("nums_all", []):
        if not has_num(nums, e, q["tol"]):
            why.append(f"missing {e}")
    if "texts_any" in q and not any(t.lower() in low for t in q["texts_any"]):
        why.append(f"none of texts {q['texts_any'][:4]}")
    for grp in q.get("texts_all", []):
        if not any(t.lower() in low for t in grp):
            why.append(f"missing text {grp}")
    return not why, "; ".join(why)


async def main():
    sem = asyncio.Semaphore(CONC); out = []
    async with httpx.AsyncClient(timeout=httpx.Timeout(150.0)) as c:
        async def one(q):
            async with sem:
                t0 = time.time()
                try:
                    res = (await c.post(f"{BASE}/api/ask", json={"question": q["q"]})).json()
                except Exception as e:  # noqa: BLE001
                    res = {"answer": f"ERROR {e}"}
                ok, why = score(q, res)
                out.append({"id": q["id"], "ok": ok, "why": why, "sec": round(time.time() - t0, 1), "q": q["q"],
                            "answer": res.get("answer"), "status": res.get("status"),
                            "verification": (res.get("verification") or {}).get("state"), "note": q.get("note"),
                            "sql": [x.get("sql") for x in res.get("queries", [])], "assumptions": res.get("assumptions")})
                print(("PASS" if ok else "FAIL"), f"{time.time()-t0:5.1f}s", q["id"], "" if ok else why, flush=True)
        await asyncio.gather(*[one(q) for q in QS if not ONLY or q["id"] in ONLY])
    p = sum(r["ok"] for r in out)
    print(f"\nHARD SCORE {p}/{len(out)} | verified {sum(r['verification']=='verified' for r in out)}/{len(out)} | avg {sum(r['sec'] for r in out)/len(out):.1f}s")
    json.dump(out, open(Path(__file__).parent / "hard_results.json", "w"), ensure_ascii=False, indent=1, default=str)

asyncio.run(main())
