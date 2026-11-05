# Model benchmark — Aniq Agent (UZEX exchange-deals agent)

All answer keys are computed directly from the DuckDB database by code (not by any model),
so the keys cannot contain hallucinated values. Each model answers on its own (no second-model
cross-check during the benchmark). A question that exceeds 90 s (the hackathon's per-answer limit)
is counted as a failure. "p50" is the median answer time; "p90" the 9-in-10 time.

## Anthropic — full 296-question bank (both languages)

| Model | Accuracy | Avg | p50 | p90 | Max | Timeouts |
|---|---|---|---|---|---|---|
| Claude Opus 5.5 (fast mode) | 100% (296/296) | 3.9 s | 3.6 s | 5.0 s | 10.7 s | 0 |
| Claude Sonnet 5.5 | 100% (296/296) | 6.2 s | 5.9 s | 7.9 s | 11.7 s | 0 |
| Claude Haiku 5.5 | 99.3% (294/296) | 6.1 s | 4.9 s | 8.4 s | 75 s | 1 |
| Claude Opus 5.5 (normal) | 100% (296/296) | 9.6 s | 8.7 s | 13.2 s | 53.7 s | 0 |

## OpenAI GPT-6 — 20-question stratified subset (via the Responses API, reasoning=low)

| Model | Accuracy | Avg | p50 | p90 | Timeouts (>90 s) |
|---|---|---|---|---|---|
| gpt-6-luna | 90% (18/20) | 6.9 s | 6.6 s | 8.3 s | 0 |
| gpt-6-astra | 90% (18/20) | 15.7 s | 10.3 s | 21.9 s | 1 |
| gpt-6.1-terra | 85% (17/20) | 17.4 s | 9.2 s | 90 s | 2 |
| gpt-6-sol | 80% (16/20) | 19.9 s | 7.8 s | 90 s | 3 |

Notes:
- The OpenAI figures are on a 20-question subset (the account's rate limits made a full 296-run
  impractical during the event), so their accuracy has a wide margin; the Anthropic figures are on
  the full 296.
- GPT-6 reasoning models require the Responses API for tool use; `reasoning_effort` must be `low`
  or higher (not `none`/`minimal`) when tools are attached.
- Several GPT-6 models time out on some questions (>90 s) — those would be outright failures under
  the jury's 90 s-per-answer rule. The Claude models never timed out (except one Haiku case).

## Conclusion

Claude Opus 5.5 in fast mode is the clear winner: the fastest (median 3.6 s) and most accurate
(100%). The best GPT-6 model (Luna) is about twice as slow (median 6.6 s) and less accurate (90%),
and the others time out on some questions. The live agent therefore runs **Opus 5.5 fast** for
answers with **Sonnet 5.5** as an independent second-model cross-check — both 100% accurate and
both fast.
