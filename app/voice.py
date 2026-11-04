"""Voice: Uzbek via ElevenLabs, Russian via Deepgram (with automatic fallbacks)."""
import httpx

from . import config

TIMEOUT = httpx.Timeout(40.0, connect=10.0)


async def stt(audio: bytes, mime: str, lang: str = "auto") -> dict:
    """Transcribe. lang: 'uz' | 'ru' | 'auto'. Returns {text, language, provider}."""
    errors = []
    order = []
    if lang == "ru" and config.DEEPGRAM_API_KEY:
        order = ["deepgram", "eleven"]
    else:
        order = ["eleven", "deepgram"] if lang != "ru" else ["eleven"]
    for prov in order:
        try:
            if prov == "eleven" and config.ELEVENLABS_API_KEY:
                data = {"model_id": config.ELEVEN_STT_MODEL}
                if lang == "uz":
                    data["language_code"] = "uzb"
                elif lang == "ru":
                    data["language_code"] = "rus"
                async with httpx.AsyncClient(timeout=TIMEOUT) as c:
                    r = await c.post("https://api.elevenlabs.io/v1/speech-to-text",
                                     headers={"xi-api-key": config.ELEVENLABS_API_KEY},
                                     data=data, files={"file": ("audio", audio, mime or "audio/webm")})
                r.raise_for_status()
                j = r.json()
                code = (j.get("language_code") or "").lower()
                return {"text": (j.get("text") or "").strip(), "provider": "ElevenLabs Scribe",
                        "language": "ru" if code.startswith("ru") else "uz"}
            if prov == "deepgram" and config.DEEPGRAM_API_KEY:
                async with httpx.AsyncClient(timeout=TIMEOUT) as c:
                    r = await c.post("https://api.deepgram.com/v1/listen",
                                     params={"model": config.DEEPGRAM_STT_MODEL, "language": "ru",
                                             "smart_format": "true", "punctuate": "true"},
                                     headers={"Authorization": f"Token {config.DEEPGRAM_API_KEY}",
                                              "Content-Type": mime or "audio/webm"},
                                     content=audio)
                r.raise_for_status()
                alt = r.json()["results"]["channels"][0]["alternatives"][0]
                return {"text": alt.get("transcript", "").strip(), "provider": "Deepgram", "language": "ru"}
        except Exception as e:  # noqa: BLE001
            errors.append(f"{prov}: {type(e).__name__} {str(e)[:200]}")
    return {"text": "", "error": "; ".join(errors) or "no speech provider configured"}


async def tts(text: str, lang: str) -> tuple[bytes, str] | None:
    """Return (audio_bytes, mime) or None."""
    text = (text or "").strip()[:600]
    if not text:
        return None
    if lang == "ru" and config.DEEPGRAM_API_KEY and config.DEEPGRAM_TTS_MODEL_RU:
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as c:
                r = await c.post("https://api.deepgram.com/v1/speak", params={"model": config.DEEPGRAM_TTS_MODEL_RU},
                                 headers={"Authorization": f"Token {config.DEEPGRAM_API_KEY}"}, json={"text": text})
            r.raise_for_status()
            return r.content, r.headers.get("content-type", "audio/mpeg")
        except Exception:  # noqa: BLE001
            pass
    if not config.ELEVENLABS_API_KEY:
        return None
    models = [config.ELEVEN_TTS_MODEL_RU if lang == "ru" else config.ELEVEN_TTS_MODEL_UZ, "eleven_v3",
              "eleven_multilingual_v2"]
    seen = set()
    for m in models:
        if m in seen:
            continue
        seen.add(m)
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as c:
                r = await c.post(f"https://api.elevenlabs.io/v1/text-to-speech/{config.ELEVEN_VOICE_ID}",
                                 params={"output_format": "mp3_44100_128"},
                                 headers={"xi-api-key": config.ELEVENLABS_API_KEY},
                                 json={"text": text, "model_id": m})
            if r.status_code == 200:
                return r.content, "audio/mpeg"
        except Exception:  # noqa: BLE001
            continue
    return None
