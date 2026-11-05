"""Voice: Uzbek via ElevenLabs, Russian via Deepgram (with automatic fallbacks)."""
import asyncio
import logging
import re

import httpx

from . import config

TIMEOUT = httpx.Timeout(40.0, connect=10.0)
log = logging.getLogger("voice")


def clean_transcript(t: str) -> str:
    """Drop audio-event tags like [тишина], (music), [silence]; empty if nothing meaningful is left."""
    t = re.sub(r"[\[(（][^\])）]{0,40}[\])）]", " ", t or "")
    t = re.sub(r"\s+", " ", t).strip(" .,-—")
    return t if len(re.sub(r"\W", "", t)) >= 3 else ""


async def stt(audio: bytes, mime: str, lang: str = "auto") -> dict:
    res = await _stt(audio, mime, lang)
    if "text" in res:
        res["text"] = clean_transcript(res["text"])
    return res


async def _stt(audio: bytes, mime: str, lang: str = "auto") -> dict:
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


VOICE = {"uz": None, "ru": None}       # active voice ids
VOICE_INFO = {"uz": None, "ru": None}  # name/accent of the chosen voice
_TTS_CACHE: dict = {}
_BAD: set = set()
EL = "https://api.elevenlabs.io"


async def library(lang: str, n: int = 12) -> list[dict]:
    """Native voices for a language from the ElevenLabs shared voice library, most used first."""
    code = {"uz": "uz", "ru": "ru"}[lang]
    async with httpx.AsyncClient(timeout=TIMEOUT) as c:
        r = await c.get(f"{EL}/v1/shared-voices", headers={"xi-api-key": config.ELEVENLABS_API_KEY},
                        params={"language": code, "page_size": n, "sort": "usage_character_count_1y"})
    r.raise_for_status()
    out = []
    for v in r.json().get("voices", []):
        out.append({k: v.get(k) for k in ("voice_id", "public_owner_id", "name", "gender", "age", "accent",
                                          "descriptive", "use_case", "preview_url", "language",
                                          "usage_character_count_1y")})
    return out


async def _add(v: dict, lang: str) -> str | None:
    async with httpx.AsyncClient(timeout=TIMEOUT) as c:
        r = await c.post(f"{EL}/v1/voices/add/{v['public_owner_id']}/{v['voice_id']}",
                         headers={"xi-api-key": config.ELEVENLABS_API_KEY},
                         json={"new_name": f"Aniq {lang.upper()} - {v.get('name', '')}"[:60]})
    if r.status_code == 200:
        return r.json().get("voice_id")
    if "already" in r.text.lower():
        return v["voice_id"]
    log.warning("voice add failed %s: %s", r.status_code, r.text[:200])
    return None


async def choose(lang: str, voice_id: str | None = None) -> dict:
    """Pick (and add to the account) a native voice. voice_id selects a specific library voice."""
    voices = await library(lang, 30)
    pick = next((v for v in voices if v["voice_id"] == voice_id), None) if voice_id else None
    pick = pick or (voices[0] if voices else None)
    if not pick:
        return {"ok": False, "error": f"no {lang} voices in the library"}
    vid = await _add(pick, lang) or pick["voice_id"]
    VOICE[lang], VOICE_INFO[lang] = vid, pick
    _TTS_CACHE.clear()
    log.info("TTS voice for %s: %s (%s, %s)", lang, pick.get("name"), pick.get("gender"), vid)
    return {"ok": True, "voice": pick, "voice_id": vid}


async def init_voices():
    if config.TTS_PROVIDER == "native":
        for lang in ("uz", "ru"):
            ok = await _native_tts("Salom" if lang == "uz" else "Привет", lang)
            log.info("native TTS self-test %s: %s", lang, "OK" if ok else "FAILED (ElevenLabs fallback)")
    if not config.ELEVENLABS_API_KEY:
        return
    for lang, vid in (("uz", config.ELEVEN_VOICE_ID_UZ), ("ru", config.ELEVEN_VOICE_ID_RU)):
        if vid:
            VOICE[lang] = vid
            ok = await tts("Salom! Men Aniq Agentman." if lang == "uz" else "Здравствуйте! Я Aniq Agent.", lang)
            log.info("custom ElevenLabs voice %s for %s: %s", vid, lang, "OK" if ok else "FAILED")
    for lang, env in (("uz", config.ELEVEN_VOICE_ID_UZ), ("ru", config.ELEVEN_VOICE_ID_RU)):
        if env:
            VOICE[lang] = env
            continue
        try:
            await choose(lang)
        except Exception as e:  # noqa: BLE001
            log.warning("voice auto-pick for %s failed: %s", lang, e)


async def _native_tts(text: str, lang: str):
    """Native-speaker neural voices (Microsoft uz-UZ Madina / ru-RU Svetlana) — correct Uzbek pronunciation."""
    try:
        import edge_tts
        voice_name = config.NATIVE_VOICE_UZ if lang == "uz" else config.NATIVE_VOICE_RU
        comm = edge_tts.Communicate(text, voice_name, rate="+4%")
        buf = bytearray()

        async def collect():
            async for chunk in comm.stream():
                if chunk.get("type") == "audio":
                    buf.extend(chunk["data"])
        await asyncio.wait_for(collect(), timeout=15)
        if buf:
            return bytes(buf), "audio/mpeg"
        log.warning("native tts returned no audio")
    except Exception as e:  # noqa: BLE001
        log.warning("native tts failed (%s): %s", lang, str(e)[:200])
    return None


async def tts(text: str, lang: str) -> tuple[bytes, str] | None:
    """Return (audio_bytes, mime) or None. Native voice per language; Uzbek on eleven_v3."""
    text = (text or "").strip()[:320]
    if not text:
        return None
    lang = "ru" if lang == "ru" else "uz"
    key = (lang, text)
    if key in _TTS_CACHE:
        return _TTS_CACHE[key]
    out = None
    custom = config.ELEVEN_VOICE_ID_UZ if lang == "uz" else config.ELEVEN_VOICE_ID_RU
    if config.TTS_PROVIDER == "native" and not (custom and config.ELEVENLABS_API_KEY):
        out = await _native_tts(text, lang)
    if out is None and lang == "ru" and config.DEEPGRAM_API_KEY and config.DEEPGRAM_TTS_MODEL_RU:
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as c:
                r = await c.post("https://api.deepgram.com/v1/speak", params={"model": config.DEEPGRAM_TTS_MODEL_RU},
                                 headers={"Authorization": f"Token {config.DEEPGRAM_API_KEY}"}, json={"text": text})
            r.raise_for_status()
            out = (r.content, r.headers.get("content-type", "audio/mpeg"))
        except Exception:  # noqa: BLE001
            out = None
    if out is None and config.ELEVENLABS_API_KEY:
        voice = VOICE.get(lang) or config.ELEVEN_VOICE_ID
        model = config.ELEVEN_TTS_MODEL_RU if lang == "ru" else config.ELEVEN_TTS_MODEL_UZ
        if lang == "uz":  # ElevenLabs models reject language_code "uz": the cloned voice carries the language
            attempts = [(model, False), ("eleven_v4", False), ("eleven_v3", False), ("eleven_multilingual_v2", False)]
        else:
            attempts = [(model, True), (model, False), ("eleven_v3", False), ("eleven_multilingual_v2", False)]
        seen = set()
        for m, with_lang in attempts:
            if (m, with_lang) in seen or (m, with_lang) in _BAD:
                continue
            seen.add((m, with_lang))
            body = {"text": text, "model_id": m,
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.8, "style": 0.0, "use_speaker_boost": True}}
            if with_lang:
                body["language_code"] = "uz" if lang == "uz" else "ru"
            try:
                async with httpx.AsyncClient(timeout=TIMEOUT) as c:
                    r = await c.post(f"{EL}/v1/text-to-speech/{voice}/stream",
                                     params={"output_format": "mp3_44100_128", "optimize_streaming_latency": "3"},
                                     headers={"xi-api-key": config.ELEVENLABS_API_KEY}, json=body)
                if r.status_code == 200:
                    out = (r.content, "audio/mpeg")
                    break
                log.warning("tts %s lang=%s failed %s: %s", m, with_lang, r.status_code, r.text[:160])
                if r.status_code in (400, 404, 422):
                    _BAD.add((m, with_lang))  # unsupported model/option: never retry it
            except Exception as e:  # noqa: BLE001
                log.warning("tts error: %s", e)
    if out:
        if len(_TTS_CACHE) > 300:
            _TTS_CACHE.clear()
        _TTS_CACHE[key] = out
    return out
