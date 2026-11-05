"""Telegram bot via webhook (same backend as the web app). Text and voice questions."""
import asyncio
import html
import logging
import re

import httpx

from . import agent, config, insights, voice

log = logging.getLogger("tg")
API = "https://api.telegram.org"
LANG: dict[int, str] = {}  # chat_id -> 'uz' | 'ru' (voice recognition preference)

EXAMPLES = {
    "uz": ["2025-yilda qancha dizel yoqilg'isi sotilgan?", "Qaysi broker eng ko'p bitim tuzgan?",
           "2026-yilda bekor qilingan bitimlar ulushi qancha?"],
    "ru": ["Какой товар лидирует по обороту в 2026 году?", "Средняя цена сахара белого в октябре 2026?",
           "Сколько экспортных сделок было в 2024 году?"],
}


async def call(method: str, **params):
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as c:
        r = await c.post(f"{API}/bot{config.TELEGRAM_BOT_TOKEN}/{method}", **params)
    try:
        j = r.json()
    except Exception:  # noqa: BLE001
        j = {"ok": False, "description": r.text[:200]}
    if not j.get("ok"):
        log.warning("telegram %s failed: %s", method, j.get("description"))
    return j


async def set_webhook():
    url = f"{config.PUBLIC_URL}/tg/{config.TELEGRAM_WEBHOOK_SECRET}"
    await call("setWebhook", json={"url": url, "allowed_updates": ["message"], "drop_pending_updates": True})
    await call("setMyCommands", json={"commands": [
        {"command": "start", "description": "Boshlash / Начать"},
        {"command": "brifing", "description": "Bozor brifingi / Сводка рынка"},
        {"command": "uz", "description": "Ovozli savollar: o'zbekcha"},
        {"command": "ru", "description": "Голосовые вопросы: русский"},
    ]})
    log.info("telegram webhook set: %s", url)


def md_to_html(text: str) -> str:
    t = html.escape(text)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?m)^\s*[-*•]\s+", "• ", t)
    return t


def format_answer(res: dict) -> str:
    lang = res.get("language", "uz")
    ru = lang == "ru"
    parts = [md_to_html(res.get("answer", ""))]
    v = (res.get("verification") or {}).get("state")
    badge = {
        "verified": "✅ Ikki mustaqil model natijasi mos keldi" if not ru else "✅ Две независимые модели получили одинаковый результат",
        "reconciled": "🟡 Natija qayta tekshirildi" if not ru else "🟡 Результат перепроверен",
        "mismatch": "⚠️ Modellar natijasi farq qildi — ehtiyot bo'ling" if not ru else "⚠️ Результаты моделей расходятся",
        "single": "☑️ Ma'lumotlar bazasidan hisoblandi" if not ru else "☑️ Рассчитано по базе данных",
    }.get(v)
    if res.get("status") == "answered" and badge:
        parts.append(badge)
    if res.get("assumptions"):
        parts.append(("<b>Asos:</b>" if not ru else "<b>Основание:</b>") + "\n" +
                     "\n".join("• " + html.escape(a) for a in res["assumptions"][:5]))
    ev = res.get("evidence") or []
    if ev:
        ids = ", ".join(f"#{e['deal_id']}" for e in ev[:5])
        parts.append(("Namuna bitimlar: " if not ru else "Примеры сделок: ") + ids)
    nq = len(res.get("queries") or [])
    if nq:
        parts.append(f"<i>{nq} SQL · {res.get('seconds')} s</i>")
    if config.PUBLIC_URL and res.get("id"):
        parts.append(f'<a href="{config.PUBLIC_URL}/a/{res["id"]}">' +
                     ("To'liq isbot (SQL, jadval, CSV) →" if not ru else "Полное доказательство (SQL, таблица, CSV) →") + "</a>")
    out = "\n\n".join(parts)
    return out[:4000]


async def _typing(chat_id: int, stop: asyncio.Event):
    while not stop.is_set():
        await call("sendChatAction", json={"chat_id": chat_id, "action": "typing"})
        try:
            await asyncio.wait_for(stop.wait(), timeout=4.5)
        except asyncio.TimeoutError:
            pass


async def answer_and_reply(chat_id: int, question: str, reply_to: int | None, speak: bool):
    stop = asyncio.Event()
    typing = asyncio.create_task(_typing(chat_id, stop))
    try:
        res = await agent.answer(question)
    except Exception as e:  # noqa: BLE001
        log.exception("agent failed")
        res = {"answer": f"Xatolik / Ошибка: {e}", "language": "uz"}
    finally:
        stop.set()
        await typing
    await call("sendMessage", json={"chat_id": chat_id, "text": format_answer(res), "parse_mode": "HTML",
                                    "reply_to_message_id": reply_to, "disable_web_page_preview": True})
    if speak and res.get("speech"):
        audio = await voice.tts(res["speech"], "ru" if res.get("language") == "ru" else "uz")
        if audio:
            await call("sendVoice", data={"chat_id": str(chat_id)}, files={"voice": ("answer.mp3", audio[0], audio[1])})


async def handle_update(update: dict):
    try:
        msg = update.get("message") or {}
        chat_id = (msg.get("chat") or {}).get("id")
        if not chat_id:
            return
        text = (msg.get("text") or "").strip()
        if text.startswith("/start"):
            kb = {"keyboard": [[{"text": q}] for q in EXAMPLES["uz"][:2] + EXAMPLES["ru"][:2]] +
                              [[{"text": "📊 Bozor brifingi"}, {"text": "📊 Сводка рынка"}]],
                  "resize_keyboard": True}
            await call("sendMessage", json={"chat_id": chat_id, "parse_mode": "HTML", "reply_markup": kb, "text": (
                "<b>Aniq Agent</b> — UZEX birja bitimlari bo'yicha savollarga aniq javob beraman.\n"
                "Har bir raqam ma'lumotlar bazasidan hisoblanadi va isboti bilan beriladi. "
                "Ma'lumotlarda yo'q narsani o'ylab topmayman.\n\n"
                "<b>Aniq Agent</b> — отвечаю на вопросы о сделках биржи UZEX. Каждое число посчитано по базе "
                "и показано с доказательством. Ничего не выдумываю.\n\n"
                "✍️ Savol yozing yoki 🎙 ovozli xabar yuboring / Напишите вопрос или отправьте голосовое.")})
            return
        if text in ("/uz", "/ru"):
            LANG[chat_id] = text[1:]
            await call("sendMessage", json={"chat_id": chat_id, "text": "✅ O'zbek tili" if text == "/uz" else "✅ Русский язык"})
            return
        if text.startswith("/brifing") or text in ("📊 Bozor brifingi", "📊 Сводка рынка"):
            lang = "ru" if "Сводка" in text or LANG.get(chat_id) == "ru" else "uz"
            b = insights.briefing(lang)
            await call("sendMessage", json={"chat_id": chat_id, "text": md_to_html(b["text"]), "parse_mode": "HTML"})
            audio = await voice.tts(b["speech"], lang)
            if audio:
                await call("sendVoice", data={"chat_id": str(chat_id)}, files={"voice": ("brief.mp3", audio[0], audio[1])})
            return
        voice_obj = msg.get("voice") or msg.get("audio")
        if voice_obj:
            f = await call("getFile", json={"file_id": voice_obj["file_id"]})
            path = (f.get("result") or {}).get("file_path")
            if not path:
                return
            async with httpx.AsyncClient(timeout=60) as c:
                audio = (await c.get(f"{API}/file/bot{config.TELEGRAM_BOT_TOKEN}/{path}")).content
            st = await voice.stt(audio, voice_obj.get("mime_type", "audio/ogg"), LANG.get(chat_id, "auto"))
            heard = st.get("text", "")
            if not heard:
                await call("sendMessage", json={"chat_id": chat_id, "text": "🎙 Ovozni tanib bo'lmadi / Не удалось распознать голос."})
                return
            await call("sendMessage", json={"chat_id": chat_id, "parse_mode": "HTML", "reply_to_message_id": msg.get("message_id"),
                                            "text": f"🎙 <b>{'Услышал' if st.get('language') == 'ru' else 'Eshitdim'}:</b> {html.escape(heard)}"})
            await answer_and_reply(chat_id, heard, msg.get("message_id"), speak=True)
            return
        if text:
            await answer_and_reply(chat_id, text, msg.get("message_id"), speak=False)
    except Exception:  # noqa: BLE001
        log.exception("telegram update failed")
