"""
Sanctumly Configuration
All environment variables and settings in one place
"""
import os

# API Keys
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")  # kept for RAG embeddings only

# Groq Model Config
GROQ_MODEL = "moonshotai/kimi-k2-instruct-0905"
GROQ_VISION_MODEL = "llama-3.2-90b-vision-preview"

# Database
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASS = os.environ.get("DB_PASS")
DB_NAME = os.environ.get("DB_NAME", "najdangpt")
DATABASE_URL = os.environ.get("DATABASE_URL")

# Security Configuration
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
MAX_USERNAME_LENGTH = 50
MIN_USERNAME_LENGTH = 3
SESSION_EXPIRY_DAYS = 30

# Rate Limiting
MAX_ACCOUNTS_PER_HOUR = 3
MAX_MESSAGES_PER_HOUR = 20
MAX_FAILED_LOGINS_PER_HOUR = 5

# CORS - Allowed Origins (NO WILDCARD!)
ALLOWED_ORIGINS = [
    "https://sanctumly.space",
    "https://www.sanctumly.space",
    "https://najdangpt.space",
    "https://www.najdangpt.space",
    "http://localhost:3000",
    "http://localhost:3001",
]

# Supported File Types
SUPPORTED_FILE_TYPES = ["pdf", "txt", "docx", "xlsx", "xls", "csv", "epub"]
