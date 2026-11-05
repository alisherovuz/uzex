import asyncio
import csv
import io
import json
import logging

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import agent, config, db, insights, tg, voice
from .llm import get_system

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("isbotli")
app = FastAPI(title="Aniq — UZEX deals analyst", docs_url="/api/docs")
app.mount("/static", StaticFiles(directory=str(config.WEB_DIR / "static")), name="static")


@app.on_event("startup")
async def startup():
    await asyncio.to_thread(get_system)
    await asyncio.to_thread(insights.overview)
    for lang in ("uz", "ru"):
        await asyncio.to_thread(insights.briefing, lang)
    if config.OPENAI_API_KEY:
        asyncio.create_task(_check_openai())
    asyncio.create_task(voice.init_voices())
    if config.TELEGRAM_BOT_TOKEN and config.PUBLIC_URL:
        asyncio.create_task(tg.set_webhook())
    log.info("ready: claude=%s openai=%s eleven=%s deepgram=%s telegram=%s", bool(config.ANTHROPIC_API_KEY),
             bool(config.OPENAI_API_KEY), bool(config.ELEVENLABS_API_KEY), bool(config.DEEPGRAM_API_KEY),
             bool(config.TELEGRAM_BOT_TOKEN))


async def _check_openai():
    import httpx
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"})
        if r.status_code in (401, 403):
            agent.GPT_OK["ok"] = False
            log.warning("OpenAI key rejected (%s): verifier falls back to an independent Claude run", r.status_code)
    except Exception as e:  # noqa: BLE001
        log.warning("OpenAI check failed: %s", e)


@app.get("/")
async def index():
    return FileResponse(config.WEB_DIR / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/favicon.ico")
async def favicon():
    return FileResponse(config.WEB_DIR / "static" / "logo.svg", media_type="image/svg+xml")


@app.get("/a/{rid}")
async def answer_page(rid: str):
    return FileResponse(config.WEB_DIR / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/api/health")
async def health():
    return {"ok": True, "llm": {"claude": bool(config.ANTHROPIC_API_KEY), "gpt": bool(config.OPENAI_API_KEY) and agent.GPT_OK["ok"],
                                "claude_model": config.CLAUDE_MODEL, "gpt_model": config.OPENAI_MODEL},
            "voice": {"elevenlabs": bool(config.ELEVENLABS_API_KEY), "deepgram": bool(config.DEEPGRAM_API_KEY)},
            "telegram": bool(config.TELEGRAM_BOT_TOKEN)}


@app.get("/api/overview")
async def overview():
    return JSONResponse(json.loads(json.dumps(insights.overview(), default=str)))


@app.get("/api/briefing")
async def briefing(lang: str = "uz"):
    return insights.briefing("ru" if lang == "ru" else "uz")


@app.post("/api/ask")
async def ask(payload: dict):
    q = (payload.get("question") or "").strip()
    if not q:
        raise HTTPException(400, "question is required")
    return await agent.answer(q[:1000])


@app.post("/api/ask/stream")
async def ask_stream(payload: dict):
    q = (payload.get("question") or "").strip()[:1000]
    if not q:
        raise HTTPException(400, "question is required")
    queue: asyncio.Queue = asyncio.Queue()

    async def emit(ev):
        await queue.put(ev)

    async def worker():
        try:
            res = await agent.answer(q, emit)
            await queue.put({"type": "final", "result": res})
        except Exception as e:  # noqa: BLE001
            log.exception("answer failed")
            await queue.put({"type": "final", "result": {"status": "error", "answer": f"Error: {e}"}})

    task = asyncio.create_task(worker())

    async def gen():
        while True:
            try:
                ev = await asyncio.wait_for(queue.get(), timeout=10)
            except asyncio.TimeoutError:
                yield json.dumps({"type": "ping"}) + "\n"
                continue
            yield json.dumps(ev, ensure_ascii=False, default=str) + "\n"
            if ev.get("type") == "final":
                break
        await task

    return StreamingResponse(gen(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/answer/{rid}")
async def get_answer(rid: str):
    if rid not in agent.ANSWERS:
        raise HTTPException(404, "answer not found (the server may have restarted)")
    return agent.ANSWERS[rid]


@app.get("/api/answer/{rid}/{qid}.csv")
async def query_csv(rid: str, qid: str):
    a = agent.ANSWERS.get(rid)
    q = next((x for x in (a or {}).get("queries", []) if x["id"] == qid), None)
    if not q:
        raise HTTPException(404, "not found")
    r = await asyncio.to_thread(db.run_sql, q["sql"], 20000, 30)
    if "error" in r:
        raise HTTPException(400, r["error"])
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(r["columns"])
    w.writerows(r["rows"])
    return Response("﻿" + buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="isbotli_{rid}_{qid}.csv"'})


@app.post("/api/stt")
async def stt(file: UploadFile = File(...), lang: str = Form("auto")):
    audio = await file.read()
    if len(audio) > 15_000_000:
        raise HTTPException(413, "audio too large")
    return await voice.stt(audio, file.content_type or "audio/webm", lang)


@app.post("/api/tts")
async def tts(payload: dict):
    out = await voice.tts(payload.get("text", ""), payload.get("lang", "uz"))
    if not out:
        raise HTTPException(503, "speech is not available")
    return Response(out[0], media_type=out[1])


@app.get("/voices")
async def voices_page():
    return FileResponse(config.WEB_DIR / "voices.html", headers={"Cache-Control": "no-cache"})


@app.get("/api/voices")
async def voices(lang: str = "uz"):
    lang = "ru" if lang == "ru" else "uz"
    try:
        lib = await voice.library(lang, 24)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"voice library unavailable: {e}")
    return {"current": voice.VOICE.get(lang), "current_info": voice.VOICE_INFO.get(lang), "voices": lib}


@app.post("/api/voices/select")
async def voices_select(payload: dict):
    if payload.get("key") != config.TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(403, "admin key required")
    lang = "ru" if payload.get("lang") == "ru" else "uz"
    return await voice.choose(lang, payload.get("voice_id"))


@app.post("/tg/{secret}")
async def telegram_webhook(secret: str, request: Request):
    if secret != config.TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(403)
    update = await request.json()
    asyncio.create_task(tg.handle_update(update))
    return {"ok": True}
