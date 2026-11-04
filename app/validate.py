"""Anti-hallucination check: every number written in an answer must be traceable to a query result
(or to the question itself). Also compares the primary answer with the independent verifier."""
import re
from typing import Iterable

NUM_RE = re.compile(r"(?<![\w.,])[-−]?\d{1,3}(?:[   ]\d{3})+(?:[.,]\d+)?(?![\d])|(?<![\w.,])[-−]?\d+(?:[.,]\d+)?(?![\d])")
DATE_RE = re.compile(r"\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b|\b\d{4}-\d{2}(?:-\d{2})?\b")


def parse_numbers(text: str) -> list[tuple[str, float, int]]:
    """Return (raw, value, decimals) for every number in the text (dates are skipped)."""
    text = DATE_RE.sub(" ", text)
    text = re.sub(r"\bBK\d+\b", " ", text)  # broker codes
    out = []
    for m in NUM_RE.finditer(text):
        raw = m.group(0)
        s = raw.replace(" ", "").replace(" ", "").replace(" ", "").replace("−", "-")
        dec = 0
        if "," in s and "." in s:
            s = s.replace(",", "")
        if "," in s:
            s = s.replace(",", ".")
        if "." in s:
            dec = len(s.split(".")[1])
        try:
            out.append((raw.strip(), float(s), dec))
        except ValueError:
            pass
    return out


def _flatten(v) -> Iterable[float]:
    if isinstance(v, bool) or v is None:
        return
    if isinstance(v, (int, float)):
        yield float(v)
    elif isinstance(v, (list, tuple)):
        for x in v:
            yield from _flatten(x)
    elif isinstance(v, str):
        for _, n, _ in parse_numbers(v):
            yield n


def _matches(n: float, dec: int, candidates: list[float]) -> bool:
    tol = 0.5 * 10 ** (-dec) + 1e-9
    for v in candidates:
        for c in (v, v * 100, abs(v)):
            if abs(c - n) <= tol:
                return True
            if abs(round(c, dec) - n) <= 1e-9:
                return True
            # rounded to thousands etc. ("12 345 000" from 12 345 678) is NOT accepted on purpose
    return False


def check_answer(answer: str, question: str, results: dict[str, dict], key_figures: list[dict]) -> list[str]:
    """Return list of numbers in `answer` that are not backed by any query result."""
    cands: list[float] = []
    for r in results.values():
        for row in r.get("rows", []):
            cands.extend(_flatten(row))
    q_nums = [n for _, n, _ in parse_numbers(question)]
    unbacked = []
    for raw, n, dec in parse_numbers(answer):
        if n in q_nums:
            continue
        if dec == 0 and 1 <= n <= 12 and len(raw) <= 2:  # small ordinals: "top 5", "3 sort", months
            continue
        if 2020 <= n <= 2030 and dec == 0:  # years
            continue
        if not _matches(n, dec, cands):
            unbacked.append(raw)
    for kf in key_figures or []:
        v = kf.get("value")
        if isinstance(v, (int, float)) and not _matches(float(v), 2, cands) and not _matches(float(v), 0, cands):
            unbacked.append(f"key_figure {kf.get('label')}={v}")
    return unbacked


def figures_agree(a: list[dict], b: list[dict], rel: float = 0.005) -> tuple[bool, list[str]]:
    """The primary model's main figure must appear among the verifier's figures (or vice versa)."""
    num = lambda xs: [float(x["value"]) for x in xs if isinstance(x.get("value"), (int, float))
                      and not isinstance(x.get("value"), bool)]
    av, bv = num(a), num(b)
    if not av:
        return True, []
    if not bv:
        return False, [f"{a[0].get('label')}={av[0]}"]
    close = lambda v, w: abs(v - w) <= max(abs(v), abs(w), 1e-9) * rel or abs(v - w) < 0.51
    if any(close(av[0], w) for w in bv) or any(close(bv[0], v) for v in av):
        return True, []
    return False, [f"{a[0].get('label')}={av[0]}"]
