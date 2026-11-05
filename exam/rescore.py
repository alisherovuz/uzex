"""Re-score saved full answers (final objects) against the current keys. No model calls."""
import json, sys, runpy
from pathlib import Path
E = Path(__file__).parent
sys.argv = ["x", "sonnet"]
ns = runpy.run_path(str(E / "bench_models.py"), run_name="not_main")
by = {q["id"]: q for q in ns["bank"]}
for c in ("opus_fast", "opus", "sonnet", "haiku"):
    p = E / f"bench_{c}.json"; d = json.load(open(p)); s = d["summary"]
    for r in d["results"]: r["ok"] = ns["score"](by[r["id"]], r["final"])
    s["correct"] = sum(r["ok"] for r in d["results"]); s["accuracy"] = round(100 * s["correct"] / s["n"], 1)
    json.dump(d, open(p, "w"), ensure_ascii=False, indent=1, default=str)
    print(f'{c:10s} {s["correct"]}/{s["n"]}  avg {s["avg_s"]}  p50 {s["p50_s"]}  p90 {s["p90_s"]}', [r["id"] for r in d["results"] if not r["ok"]])
