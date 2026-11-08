# iBek — website + AI Q&A assistant

The public site for iBek, an agent-first commodity exchange for UZEX: what it is, how the auction works, how to reach it by SMS or phone call, and a chat assistant (text or voice) that answers the judges' questions from `knowledge.md`.

- `server.js`: zero-dependency Node server that serves `public/` and streams answers from Claude at `POST /api/chat`
- `knowledge.md`: everything the assistant knows; edit this to change its answers
- `public/index.html`: the site, including the chat panel (voice input via the Web Speech API, read-aloud via speechSynthesis)

Env vars: `ANTHROPIC_API_KEY` (required for chat), `IBEK_PHONE` (the number shown for SMS/calls), `CLAUDE_MODEL` (default `claude-sonnet-5-5`), `PORT`.

Run: `npm start`
