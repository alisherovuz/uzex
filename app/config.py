import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = os.getenv("DB_PATH", str(ROOT / "data" / "uzex.duckdb"))
WEB_DIR = ROOT / "web"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
CLAUDE_EFFORT = os.getenv("CLAUDE_EFFORT", "low")  # low = fastest; empty = model default
FAST_MODEL = os.getenv("FAST_MODEL", "claude-haiku-5-5")  # speech text + follow-ups
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-6-astra")
OPENAI_REASONING = os.getenv("OPENAI_REASONING", "low")  # for reasoning models; empty disables

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVEN_STT_MODEL = os.getenv("ELEVEN_STT_MODEL", "scribe_v1")
ELEVEN_TTS_MODEL_UZ = os.getenv("ELEVEN_TTS_MODEL_UZ", "eleven_v4")  # falls back to eleven_v3
ELEVEN_TTS_MODEL_RU = os.getenv("ELEVEN_TTS_MODEL_RU", "eleven_flash_v2_5")  # fast, supports Russian
ELEVEN_VOICE_ID = os.getenv("ELEVEN_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")  # fallback: "Sarah", young, clear
ELEVEN_VOICE_ID_UZ = os.getenv("ELEVEN_VOICE_ID_UZ", "")  # empty = auto-pick a native Uzbek voice from the library
ELEVEN_VOICE_ID_RU = os.getenv("ELEVEN_VOICE_ID_RU", "")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
DEEPGRAM_STT_MODEL = os.getenv("DEEPGRAM_STT_MODEL", "nova-3")
DEEPGRAM_TTS_MODEL_RU = os.getenv("DEEPGRAM_TTS_MODEL_RU", "")
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "native")  # native = Microsoft neural voices (uz-UZ, ru-RU); eleven = ElevenLabs
NATIVE_VOICE_UZ = os.getenv("NATIVE_VOICE_UZ", "uz-UZ-MadinaNeural")
NATIVE_VOICE_RU = os.getenv("NATIVE_VOICE_RU", "ru-RU-SvetlanaNeural")  # empty = use ElevenLabs for Russian speech

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "isbotli")
PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")

ANSWER_BUDGET_S = float(os.getenv("ANSWER_BUDGET_S", "75"))  # jury limit is 90 s per answer
VERIFY_BUDGET_S = float(os.getenv("VERIFY_BUDGET_S", "70"))
VERIFIER_CLAUDE_MODEL = os.getenv("VERIFIER_CLAUDE_MODEL", "claude-opus-5-5")
