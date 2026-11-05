# Aniq Agent — UZEX AI Hackathon

*Aniq* means "exact" in Uzbek.

An AI agent that answers questions about UZEX exchange deals in **Uzbek and Russian**. It **never invents a number**: every figure is computed with SQL, checked by a guard, cross-checked by a second independent model, and shown with its proof.

- **Web dashboard** (no registration): chat + live market overview + market briefing + voice
- **Telegram bot**: text and voice messages, same backend
- **Voice**: Uzbek → ElevenLabs Scribe / TTS, Russian → Deepgram (ElevenLabs fallback)

## How an answer is produced

1. **Entity check**: products, companies (INN / name, Latin or Cyrillic) and brokers are resolved against the data. Anything that does not exist → an honest "not in the data".
2. **SQL only**: the primary model (Claude) writes DuckDB SQL; all counts, sums, averages and percentages come from query results.
3. **Number guard**: before an answer is accepted, every number in its text must appear in a query result. Otherwise it is rejected and the model must recompute.
4. **Independent cross-check**: a second model (GPT) answers the same question with its own SQL. If the key figures match, the answer gets **✓ verified**. If not, the primary model re-checks the difference (reconciliation).
5. **Proof**: filters and assumptions, key figures, SQL text, result tables, CSV download, and real deal numbers the jury can check.

## Data layer (`scripts/build_db.py`)

Built from the raw export at image build time (~10 s):
- 697 raw product spellings → **94 canonical products** (42 base products). Grade, class, brand and size are normalized (e.g. `1-сорта`, `I сорт`, `первый сорт` → `1`).
- Amounts in **UZS and USD** (export deals converted at the rate on the deal date).
- **Volume = Количество × Лот**. Kilograms are normalized to tonnes (the same product is sold in kg *and* t). Litres are never added to tonnes.
- **Cancelled deals** (`Аннулирован(Не оплачен)`) are flagged and excluded from volume and money.
- Payment/delivery due dates and delays are derived from contract terms.
- Regions are unified (Russian contract names → Uzbek Latin).

## Exam (`exam/`)

`build_exam.py` computes ground truth with plain pandas directly from the **raw CSVs** (an independent code path), for 30 questions × 2 languages, including 6 trap questions (fake INN, non-existent product, 2021, BK999, future prices, a company not in the data).

```bash
python exam/build_exam.py data/uzex_spot_data.zip exam/questions.json
python exam/run_exam.py https://<app-url> both 3
```

## Run

```bash
pip install -r requirements.txt
python scripts/build_db.py data/uzex_spot_data.zip data/uzex.duckdb
uvicorn app.main:app --port 8000
```

or `docker build -t aniq . && docker run -p 8000:8000 --env-file .env aniq`.

### Environment variables

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | primary model (Claude) |
| `OPENAI_API_KEY` | independent verifier (GPT) |
| `CLAUDE_MODEL` | default `claude-sonnet-5-5` |
| `OPENAI_MODEL` | default `gpt-5` |
| `ELEVENLABS_API_KEY` | Uzbek speech-to-text and text-to-speech |
| `DEEPGRAM_API_KEY` | Russian speech-to-text |
| `TELEGRAM_BOT_TOKEN` | Telegram bot (webhook) |
| `PUBLIC_URL` | public https URL of the app (needed for the Telegram webhook and proof links) |
| `TELEGRAM_WEBHOOK_SECRET` | path secret for the webhook (default `isbotli`) |

With only one LLM key, the same provider runs a second independent pass as the verifier.

## API

- `POST /api/ask` `{"question": "..."}` → answer with proof
- `POST /api/ask/stream` → NDJSON progress events + final answer
- `GET /api/answer/{id}`, `GET /api/answer/{id}/{query_id}.csv`
- `GET /api/overview`, `GET /api/briefing?lang=uz|ru`
- `POST /api/stt` (multipart audio), `POST /api/tts`
- `POST /tg/{secret}` Telegram webhook
