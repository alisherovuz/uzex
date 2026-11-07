# Aniq 2035 — MLP

Static web app for the "Exchange of 2035 — Reinvent UZEX" task.

Flow: need in plain Uzbek/Russian → locked agent mandate → verified lots + price passport → sealed-bid second-price agent auction with shill filter → escrow with automatic refund → hash-chained deal proof.

- **From the organizers' dataset** (`market.json`, built by `scripts/build_market.py data/… mlp/market.json`): 120-day price ranges, daily medians, outlier deals with deal numbers, sellers, INN, contract delivery terms, on-time delivery records.
- **Simulated**: lot sizes, warehouse receipts, other bidding agents, escrow and delivery events. No real money.
- **AI boundary**: language understanding only (rule-based parser in this build, replaceable by an LLM behind `validateIntent`). Prices, eligibility, auction and state changes are deterministic code in `logic.js`.

Tests: `node mlp/test.mjs`
