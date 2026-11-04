import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = os.getenv("DB_PATH", str(ROOT / "data" / "uzex.duckdb"))
WEB_DIR = ROOT / "web"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")
OPENAI_REASONING = os.getenv("OPENAI_REASONING", "low")  # for reasoning models; empty disables

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVEN_STT_MODEL = os.getenv("ELEVEN_STT_MODEL", "scribe_v1")
ELEVEN_TTS_MODEL_UZ = os.getenv("ELEVEN_TTS_MODEL_UZ", "eleven_v3")
ELEVEN_TTS_MODEL_RU = os.getenv("ELEVEN_TTS_MODEL_RU", "eleven_multilingual_v2")
ELEVEN_VOICE_ID = os.getenv("ELEVEN_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
DEEPGRAM_STT_MODEL = os.getenv("DEEPGRAM_STT_MODEL", "nova-3")
DEEPGRAM_TTS_MODEL_RU = os.getenv("DEEPGRAM_TTS_MODEL_RU", "")  # empty = use ElevenLabs for Russian speech

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "isbotli")
PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")

ANSWER_BUDGET_S = float(os.getenv("ANSWER_BUDGET_S", "75"))  # jury limit is 90 s per answer
