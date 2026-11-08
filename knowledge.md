# iBek — knowledge base

(The project was earlier called "Aniq" in internal notes. The name is now **iBek**. Always say iBek.)

## One-paragraph idea
By 2035 people won't open the UZEX (Uzbekistan Republican Commodity Exchange) website; their personal AI agent will trade for them. So iBek builds the exchange for agents. There are two "doors":
- **iBek Agent** — our own agent that people subscribe to. They reach it by phone call (in Uzbek), SMS, Telegram or a simple app.
- **iBek MCP** — a connector that any personal agent (Claude, ChatGPT, a Telegram bot, etc.) can plug into.
Both doors lead to the same fair auction, where every winning buyer pays the same price.

Pitch lines:
- "In 2035 nobody opens the UZEX website. Your agent trades for you."
- "Every buyer in a round pays the same price, so no bot gets an unfair edge."
- "Your agent can only spend what you allowed. The exchange checks the limit, not the AI."

Positioning: iBek is "designed for 2035" and is a working **prototype / MVP** built for the UZEX AI Hackathon. We do not claim everyone has an agent today.

## Why we believe it works by 2035
In 2026 personal agents went mainstream, and business buying (our market) moves first.
- Big tech is shipping agents that act for you. The New York Times podcast The Daily ("Call My A.I. Agent") followed a reporter living with Meta's Muse agent. Axios called it "the era of the personal agent".
- B2B goes first: Gartner predicts 90% of B2B buying will run through AI agents by 2028.
- San Francisco: about 1 in 5 people use an agent regularly (team estimate: 73% of Bay Area workers use AI (Carnegie California AI Survey 2026) × 24% of AI users use an agent regularly (Menlo Ventures 2026) ≈ 18%; about 30% have tried one). Across the US about 15%. No survey counts SF agent users directly yet — this is our estimate, say so.
- Uzbekistan follows: 89.5% of people are online (DataReportal), and a national AI strategy runs to 2030. By 2035 the same wave reaches Uzbekistan, through Telegram and phone.

## Product: two doors, one market
Both doors call the same tools and the same auction engine, so every buyer gets the same rules and the same price.

| | Door 1: iBek Agent | Door 2: iBek MCP |
|---|---|---|
| Who it is for | People without their own agent: farmers, small shops, builders | People and companies whose agent already runs their life or procurement |
| How they reach it | Phone call in Uzbek, SMS, Telegram, simple app | Their own agent adds the iBek connector once |
| How UZEX earns | Monthly subscription + 0.1% deal fee | 0.1% deal fee (agent access free or a small API plan — still to decide) |
| What the agent does | Finds lots, suggests a price, places the sealed bid, calls back with the result | The same, through the same tools |
| Safety | Limits set by the person; confirmation by voice or tap | Limits signed once by the person (mandate); the engine rejects anything outside them |

Why this beats "another assistant": the official agent is only one door. The open MCP door means UZEX is ready for whatever agent people own in 2035.

## How a person uses iBek (phone / SMS)
- **Call**: the person calls the iBek number. The agent speaks Uzbek, tells them which lots are open (e.g. cement, diesel, wheat), asks how much they need and the most they will pay per tonne, can suggest a fair price from real UZEX deal history, reads the order back for confirmation, and places a sealed bid. When the round clears, iBek calls them back with the result (how many tonnes, at what price).
- **SMS**: the person texts the same number in plain words (Uzbek, Russian or English), e.g. "I need 20 tonnes of cement, at most 980,000 so'm per tonne." The agent replies, confirms, places the bid and texts back the result.
- iBek can also call the user (outbound) — for example to take an order or report a result.
- **Own agent (MCP)**: a person's own AI agent connects to iBek and uses the same tools.
- The exact phone number is shown on the iBek website.

## The pitch deck (PARVOZ presentation) — what the judges saw, slide by slide
Style: black-and-white hand-drawn illustrations, almost no text. The story:
1. A horse-headed car (Uriah Smith's 1899 "Horsey Horseless", US patent D30551): when cars arrived, people bolted a horse's head onto them. Bolting AI onto today's exchange terminal is the same mistake. Don't automate the past.
2. A question mark over the exchange: what replaces terminals and brokers by 2035?
3. iBek.
4. A phone and a speech bubble: you just call or text.
5. Search → handshake → truck → wrench: the agent handles the whole chain (find, deal, deliver, service), not only the bid.
6. AI cost collapsing: GPT-3.5-level inference cost about $20 per million tokens in Nov 2022, $2 at gpt-3.5-turbo's launch (Mar 2023), $0.07 by Oct 2024 (Stanford AI Index 2025), about $0.05 for the cheapest GPT-3.5-class model in 2026 price tables, heading to about zero by 2035. Epoch AI (Sep 2026): the cost of a fixed AI capability falls about 13× per year.
7. A head with a crossed-out thought cloud: the user doesn't need to think about exchange mechanics.
8. A hand and a long queue walking into the exchange: iBek brings many new participants in.
9. A wall with a door high up and broken ladders: today's exchange is hard to enter — under the UZEX trading rules (1 Jun 2026), clause 4 limits who can be a client and clause 240 bans scripts/bots.
10. A farmer with a phone and an elderly man on a phone call: the target users — ordinary people who only need a phone.
11. Two circles, 1,260,000 vs 4,700: Uzbekistan has about 1.26 million operating small businesses (Statistics Committee, 1 Oct 2026; incl. 357.9k individual entrepreneurs and 330.8k dekhkan farms), but UZEX gained only about 4,700 new clients on its exchange trading platforms in 2025 (30,100 across all its systems; Kursiv, 5 Feb 2026). The gap is the opportunity.
12. Revenue bars: UZEX 2025 revenue UZS 444.5 billion. Illustrative iBek case: if 5% of small businesses join and each trades about UZS 120 million a year, with the agent and API free and fees charged only on new customers, UZEX gains about UZS 21 billion a year (+5%).
13. iBek. Then a QR code to this website, and the references.
Other context from the deck's references: Google I/O 2026 reported 3.2 quadrillion tokens per month across Google products; Visa (press release 18 Dec 2025) ran hundreds of controlled, real-world agent-initiated transactions; Google's Universal Commerce Protocol (Jan 2026) launched with Shopify, Walmart, Target, Visa, Mastercard and others; Gartner forecasts 90% of B2B buying will be agent-intermediated by 2028 (a forecast, not a measurement). UZEX tariffs from 1 Oct 2026: buyer 0.13%, seller 0.05%, clearing 0.05% per side, before VAT. The live demo call runs on iBek's simulated exchange; no real UZEX trade was executed.
Note on fees: the deck's revenue case uses UZEX's existing tariffs on new customers' trades; the earlier team notes mention a 0.1% deal fee plus a subscription for iBek Agent as one possible model. If asked, explain both and say the final pricing is still open.

## The hackathon task (official brief from the organizers)
Title: "The Exchange of 2035 — Reinvent UZEX". Imagine that by 2035 all traditional ideas about exchange trading are outdated: no trading terminals, complex interfaces, trading through brokers, or deep study of exchange mechanics. What replaced them? The task is NOT to improve the existing platform, build another AI assistant, or automate traditional processes. It is to use AI to create a fundamentally new model of how people and businesses interact with UZEX, starting from zero, without being limited by today's interfaces, roles or methods. Perhaps brokers are no longer needed; perhaps buyers and sellers find each other in a completely different way; perhaps AI changes how orders are formed, offers are found and deals are made. Key question: "If today's exchange trading system did not exist, how would you build it with AI?" Motto: "Don't automate the past. Reinvent the future of UZEX."
The solution must meet three principles:
- Accessibility (Qulaylik va hammaboplik): an ordinary person with no trading experience can use it easily.
- Transparency (Shaffoflik): participants understand deal terms, how prices are formed, and trading results.
- Safety (Xavfsizlik): the model manages risk, protects participants' interests and ensures compliance with rules.

## How iBek answers the brief
- New interaction model, not a better terminal: the user states a need ("20 tonnes of cement, at most X") by text or voice; an agent — iBek's own or the user's personal agent via MCP — does the rest. No terminal, no order book to watch, no broker required in the 2035 model.
- Not "another AI assistant": an assistant answers questions; iBek acts. And the market itself is redesigned for agents (sealed batch rounds, one common price), so the AI layer and the market mechanism change together.
- Accessibility: talk or text in Uzbek, Russian or English from any phone; no app, no training. A farmer buying 5 t gets the same price as a factory buying 500 t.
- Transparency: one rule anyone can say in a sentence; every round publishes the seed hash, then all bids, the price and allocations; anyone can press Verify and recompute.
- Safety: the deterministic engine, not the AI, enforces limits; money is reserved before the bid; by default the user confirms; mandates cap what agents may spend; invariants are tested; MyID identity and a UZEX sandbox pilot are the path to compliance.

## About UZEX (public facts, for context)
- UZEX is the Uzbek Republican Commodity Exchange, a joint-stock company registered in April 1994, separate from the Tashkent securities exchange. Its stated purpose is organizing open commodity auctions with prices formed by supply and demand, under principles of openness and equal competitive conditions. It also runs B2B commerce, public procurement (Xarid), mobile-number auctions and logistics services.
- Company-reported results for January–September 2026: more than 1.7 million concluded transactions, more than 27,600 new registered clients, total transaction value +29% year on year, exchange trading +31%.
- UZEX already uses AI: a procurement chatbot (launched May 2025), AI checks of offer consistency, and automated moderation of announcements. That is why iBek is not pitched as "UZEX's first AI assistant" — the new part is the agent-first trading model.
- Revenue context: UZEX earns transaction and clearing fees and sells information subscriptions. Transaction value passing through the exchange is not UZEX's own revenue.

## Feature pool and agent tools
Every feature is one tool an agent can call. Most already run live in the prototype.

| Feature | Agent tool (MCP) | Status |
|---|---|---|
| See open lots, terms, countdown | list_lots | Built |
| Fair price hint from 500k real deals | suggest_price | Built |
| Place a sealed bid inside the user's limits | place_order | Built |
| Cancel before the freeze | cancel_order | Built |
| Re-check price and allocation | verify_round | Built |
| Results and receipt | get_results | Built |
| Agent calls the user (order, result call-back) | call_user | Built |
| User calls the agent | inbound_call | Built |
| Spending limits signed by the user (mandate) | set_mandate | Planned |
| Alert when a wanted lot opens | watch_product | Planned |
| Repeat order every month | standing_order | Planned |
| Agent identity and keys | MCP OAuth | Planned |

Fits the brief: easy (talk, don't click), clear (one price, anyone can verify), safe (the engine checks limits and reserves money first).

## The auction: one price, many winners
In a normal auction one buyer takes the whole lot. In iBek, everyone who bids at or above the final price gets a share, and all of them pay the same price.
Technical name: **sealed batch auction with a uniform (common) clearing price**. Bids are collected privately for a fixed window, then cleared all at once. In the prototype a round is open for about one minute, then results are revealed.

### Comparison with the current UZEX workflow (from the UZEX manuals)
| Question | UZEX workflow today | iBek |
|---|---|---|
| What does the buyer submit? | Price and quantity through a trader (broker) | Quantity and maximum price, entered directly or by an AI agent |
| Can traders see competing orders? | The order book displays them | Individual orders stay private during collection |
| How does the buyer follow progress? | Watches orders, prices and status | Receives the result after the batch is processed |
| Does being earlier help? | Exact priority rules still need verification | No arrival-time priority within the batch |
| Equal-price orders exceed supply? | Product-specific rules need verification | Buyers at the cutoff share proportionally |
| What price do winners pay? | Depends on applicable rules | One common price for equivalent goods in that batch |

### Worked example: 100 tonnes, four buyers
Seller offers 100 tonnes, reserve (minimum) $100/t. Bids: Ali 40 t at max $110; Bek 60 t at max $105; Davron 60 t at max $105; Elena 40 t at max $100.
Result: clearing price **$105/t**. Ali gets 40 t, Bek 30 t, Davron 30 t, all paying $105. Elena gets nothing and her money stays hers.
Why: Ali bid above the cutoff so he's filled in full (40 t). 60 t remain; Bek and Davron asked for equal amounts at the cutoff, so each gets half. Elena's max is below the final price. Ali pays $105, not his $110. Three buyers share the lot instead of one, and Bek and Davron get the same result whether they bid first or one second before closing.

### The math step by step
Supply M tonnes, reserve price R. Each buyer i sends quantity qᵢ and maximum price bᵢ. Whole numbers only (tonnes and so'm) — no rounding errors.
1. Eligible bids: keep bids with bᵢ ≥ R. Total eligible demand D.
2. If D ≤ M, every eligible buyer is filled in full at price R.
3. Otherwise sort bids by price high→low (arrival time ignored), count tonnes down the list; the price where the count first reaches M is the clearing price p*. Formally p* = max{ p ≥ R : D(p) ≥ M }, where D(p) = sum of qᵢ for bids with bᵢ ≥ p.
4. Every bid with bᵢ > p* gets its full quantity.
5. Leftover tonnes are split between bids at exactly p*, proportional to what each asked: xᵢ = qᵢ × (M − D_above) / D_at. (Example: D_above = 40, D_at = 120, so 60 × 60/120 = 30 t each.)
6. Round fairly: each share rounded down to whole tonnes; the few leftover tonnes go to the largest remainders; exact ties broken by a lottery whose seed was locked (hash published) before the round opened. Example: 7 t left for three equal bids → each gets 2, the extra 1 t goes to one by the pre-locked lottery.
7. Pay and refund: each winner pays xᵢ × p* plus a 0.1% fee. Money was reserved up front at qᵢ × bᵢ + fee, so the difference is released immediately.

### Fairness guarantees (invariants checked after every round)
- Total sold ≤ supply — the seller never oversells.
- Each buyer gets ≤ what they asked — nobody is forced to take more.
- Everyone pays the same p* — no price discrimination.
- Nobody pays above their maximum — the user's limit is always respected.
- Same orders in any arrival order give the same result — speed and timing give no advantage.
Tested: 9 automated tests, including all 24 orderings of the same orders and 5,000 random markets.

### Audit trail
1. When a round opens, a SHA-256 hash of the secret lottery seed is published, so the seed cannot be changed later.
2. When it closes, the seed is revealed with the full protocol: bids, p*, every allocation.
3. Anyone, or any agent, can recompute it with the Verify button. Each record carries a SHA-256 fingerprint.

### Why this matters for agents
An agent only needs the user's real limit: "20 tonnes, at most X so'm".
- No speed race: bidding first or last gives the same result, so a cheap agent is as good as a fast trading bot.
- No guessing games: the winner pays p*, not their own bid, so stating the true maximum is safe.
- Small buyers get in: a farmer wanting 5 t shares the lot with a factory wanting 500 t, at the same price.
- Easy to explain: "everyone who bid at least the final price got goods, and all paid the same price."

### Honest limits (say them, don't hide them)
- A very large buyer can sometimes lower p* by bidding below their true value (demand reduction). Batch size and reserve prices limit this.
- A buyer at the cutoff may get only part of the amount asked for. The agent must tell the user before they bid.

## Risks and answers
- "Isn't this just another AI assistant?" — No. An assistant answers questions; iBek is an agent that acts. It connects to your phone and trades for you, like Instinct does for everyday tasks. iBek is the Instinct for the commodity exchange.
- The agent buys the wrong thing — the engine, not the AI, checks the user's limits. Money is reserved before the bid.
- People don't trust it to pay alone yet — by default the agent proposes and the user confirms by voice or tap. Full autonomy is opt-in, with small limits.
- Bots flood the market — rate limits and a deposit per order. Batch rounds make speed useless.
- No rules yet for agents on an exchange — MyID for identity, a full audit trail, and a sandbox pilot with UZEX.
- AI hallucinates a price — the AI never sets the clearing price; the deterministic engine does, with integer math and published invariants.

## Data used in the prototype
Market prices, price history and sellers come from the organizers' UZEX dataset: 500,000 deals from 3 Jan 2022 to 30 Oct 2026, 14,389 participants, about 193 trillion so'm turnover (last 30 days in the dataset: 17,476 deals, ~9.8 trillion so'm). Live rounds and the other bidders in the demo are simulated; no real money moves.

Products in the prototype (typical per-tonne prices from real deals: 10th / median / 90th percentile, so'm; number of deals):
- Diesel fuel (DT-E-K5): 13.5M / 14.6M / 16.0M; 26,631 deals
- Gasoline AI-92: 15.4M / 16.1M / 17.2M; 4,764 deals
- Liquefied gas (propane-butane): 7.9M / 8.4M / 9.2M; 14,937 deals
- Cement (CEM II/B-K 32.5N): 0.91M / 0.98M / 1.10M; 36,420 deals
- Rebar (A500C, Ø12 mm): 11.6M / 12.4M / 13.5M; 14,513 deals
- Wheat (food grade, class 4): 4.22M / 4.49M / 4.69M; 29,867 deals
- White sugar: 15.0M / 15.8M / 17.0M; 11,987 deals
The reserve price of each demo lot is set at about 97% of the historical median. suggest_price uses these distributions plus the buyer's urgency.

## Demo (3 minutes)
A juror's phone rings and iBek takes an order in Uzbek → a personal agent (Claude or ChatGPT) places a bid through iBek MCP → the round clears at one price → Verify → the phone rings again with the result.

## Tech
- Clearing engine in JavaScript (Node.js), integer arithmetic, invariant checks; web app in Uzbek.
- Voice: ElevenLabs conversational agents with telephony (Twilio/SIP) for inbound and outbound calls; the voice agent calls the same engine tools.
- Hosted on Livops.

## Open questions the team is still deciding (be honest that these are open)
- Monthly price for iBek Agent: flat plan or tiers by tonnes / number of rounds.
- How much of the MCP server is built vs shown as design (it wraps the existing endpoints).
- Default autonomy: always ask for confirmation, or allow bidding alone under a small limit.
- Who pays the 0.1% fee when an outside agent places the order: buyer, agent provider, or split.

## Sources
The New York Times, The Daily: "Call My A.I. Agent"; Axios: "The era of the personal agent has finally arrived"; Gartner top predictions for 2026 and beyond; Carnegie California AI Survey 2026; Menlo Ventures: The State of Consumer AI 2026; Built In: What is Instinct AI; DataReportal: Digital 2027 Uzbekistan.
