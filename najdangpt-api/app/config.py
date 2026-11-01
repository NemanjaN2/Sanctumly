"""Sanctumly configuration. Free-tier controls are environment-overridable."""
import os

# Provider keys
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
SERPER_API_KEY = os.environ.get("SERPER_API_KEY", "")

# AI models (Groq production model IDs; vision model was updated from retired Llama Vision)
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_VISION_MODEL = os.environ.get("GROQ_VISION_MODEL", "qwen/qwen3.8-27b")

# Cloudflare Workers AI (optional until the new token is added to Railway).
CLOUDFLARE_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
CLOUDFLARE_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
CLOUDFLARE_MODEL = os.environ.get("CLOUDFLARE_MODEL", "@cf/qwen/qwen3-30b-a3b-fp8")
# Stop before the provider's 10,000-Neuron Free allocation to leave room for
# external Cloudflare usage and in-flight calls. Set to 10000 to use the full cap.
CLOUDFLARE_DAILY_NEURON_BUDGET = min(
    10000.0, max(100.0, float(os.environ.get("CLOUDFLARE_DAILY_NEURON_BUDGET", "9000")))
)
# Conservative estimate based on observed API usage (about 0.027 Neurons/token).
CLOUDFLARE_NEURONS_PER_ESTIMATED_TOKEN = float(
    os.environ.get("CLOUDFLARE_NEURONS_PER_ESTIMATED_TOKEN", "0.04")
)
CLOUDFLARE_MIN_NEURON_RESERVATION = float(
    os.environ.get("CLOUDFLARE_MIN_NEURON_RESERVATION", "10")
)
CLOUDFLARE_FAILURE_COOLDOWN_SECONDS = int(
    os.environ.get("CLOUDFLARE_FAILURE_COOLDOWN_SECONDS", "60")
)
CLOUDFLARE_FREE_MAX_OUTPUT_TOKENS = int(
    os.environ.get("CLOUDFLARE_FREE_MAX_OUTPUT_TOKENS", os.environ.get("FREE_MAX_OUTPUT_TOKENS", "1024"))
)
CLOUDFLARE_CREATOR_MAX_OUTPUT_TOKENS = int(
    os.environ.get("CLOUDFLARE_CREATOR_MAX_OUTPUT_TOKENS", "4096")
)

# Database
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASS = os.environ.get("DB_PASS")
DB_NAME = os.environ.get("DB_NAME", "najdangpt")
DATABASE_URL = os.environ.get("DATABASE_URL")

# Security
MAX_FILE_SIZE = int(os.environ.get("MAX_FILE_SIZE", str(20 * 1024 * 1024)))  # creator ceiling
FREE_MAX_FILE_SIZE = int(os.environ.get("FREE_MAX_FILE_SIZE", str(5 * 1024 * 1024)))
MAX_USERNAME_LENGTH = 50
MIN_USERNAME_LENGTH = 3
SESSION_EXPIRY_DAYS = int(os.environ.get("SESSION_EXPIRY_DAYS", "30"))
MAX_MESSAGE_CHARS = int(os.environ.get("MAX_MESSAGE_CHARS", "8000"))

# Signup and abuse prevention
MAX_ACCOUNTS_PER_HOUR = int(os.environ.get("MAX_ACCOUNTS_PER_HOUR", "3"))
MAX_MESSAGES_PER_HOUR = int(os.environ.get("MAX_MESSAGES_PER_HOUR", "20"))
MAX_FAILED_LOGINS_PER_HOUR = int(os.environ.get("MAX_FAILED_LOGINS_PER_HOUR", "5"))

# Free plan limits requested for Sanctumly
FREE_DAILY_TEXT_REQUESTS = int(os.environ.get("FREE_DAILY_TEXT_REQUESTS", "5"))
FREE_DAILY_IMAGE_ANALYSES = int(os.environ.get("FREE_DAILY_IMAGE_ANALYSES", "1"))
FREE_DAILY_WEB_SEARCHES = int(os.environ.get("FREE_DAILY_WEB_SEARCHES", "2"))
FREE_DAILY_DOCUMENT_UPLOADS = int(os.environ.get("FREE_DAILY_DOCUMENT_UPLOADS", "2"))
FREE_DAILY_TRANSCRIPTION_SECONDS = int(os.environ.get("FREE_DAILY_TRANSCRIPTION_SECONDS", "300"))
FREE_DAILY_ENGLISH_TTS_CHARS = int(os.environ.get("FREE_DAILY_ENGLISH_TTS_CHARS", "1000"))
FREE_MAX_OUTPUT_TOKENS = int(os.environ.get("FREE_MAX_OUTPUT_TOKENS", "1024"))
FREE_DAILY_AI_BUDGET_USD = float(os.environ.get("FREE_DAILY_AI_BUDGET_USD", "0.05"))

# Conservative provider cost estimates, USD. Recheck provider pricing periodically.
GROQ_TEXT_INPUT_USD_PER_M = float(os.environ.get("GROQ_TEXT_INPUT_USD_PER_M", "0.15"))
GROQ_TEXT_OUTPUT_USD_PER_M = float(os.environ.get("GROQ_TEXT_OUTPUT_USD_PER_M", "0.60"))
GROQ_VISION_INPUT_USD_PER_M = float(os.environ.get("GROQ_VISION_INPUT_USD_PER_M", "0.80"))
GROQ_VISION_OUTPUT_USD_PER_M = float(os.environ.get("GROQ_VISION_OUTPUT_USD_PER_M", "4.00"))
GROQ_WHISPER_USD_PER_HOUR = float(os.environ.get("GROQ_WHISPER_USD_PER_HOUR", "0.04"))
GROQ_ORPHEUS_USD_PER_M_CHARS = float(os.environ.get("GROQ_ORPHEUS_USD_PER_M_CHARS", "22.00"))
SERPER_USD_PER_SEARCH = float(os.environ.get("SERPER_USD_PER_SEARCH", "0.001"))

# Miscellaneous processing safety
MAX_EXTRACTED_DOCUMENT_CHARS = int(os.environ.get("MAX_EXTRACTED_DOCUMENT_CHARS", "250000"))
MAX_AUDIO_BYTES = int(os.environ.get("MAX_AUDIO_BYTES", str(20 * 1024 * 1024)))

# CORS - Allowed Origins (NO WILDCARD!)
ALLOWED_ORIGINS = [
    origin.strip() for origin in os.environ.get(
        "ALLOWED_ORIGINS",
        "https://sanctumly.space,https://www.sanctumly.space,https://najdangpt.space,https://www.najdangpt.space,http://localhost:3000,http://localhost:3001"
    ).split(",") if origin.strip()
]

SUPPORTED_FILE_TYPES = ["pdf", "txt", "docx", "xlsx", "xls", "csv", "epub"]
