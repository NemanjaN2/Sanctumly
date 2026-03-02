"""
NajdanGPT Configuration
All environment variables and settings in one place
"""

import os

# API Keys & Cloud Config
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "valid-meridian-477320-c1")
LOCATION = os.environ.get("GOOGLE_CLOUD_REGION", "us-central1")
MODEL_NAME = "gemini-2.5-pro"

# Database
INSTANCE_CONNECTION_NAME = os.environ.get("INSTANCE_CONNECTION_NAME")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASS = os.environ.get("DB_PASS")
DB_NAME = os.environ.get("DB_NAME", "najdangpt")

# Security Configuration
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
MAX_USERNAME_LENGTH = 50
MIN_USERNAME_LENGTH = 3
SESSION_EXPIRY_DAYS = 30

# Rate Limiting
MAX_ACCOUNTS_PER_HOUR = 7
MAX_MESSAGES_PER_HOUR = 30
MAX_FAILED_LOGINS_PER_HOUR = 5

# CORS - Allowed Origins (NO WILDCARD!)
ALLOWED_ORIGINS = [
    "https://najdangpt.space",
    "https://www.najdangpt.space",
    "http://localhost:3000",
    "http://localhost:3001",
    "https://sanctumly.space",
    "https://www.sanctumly.space",
]

# Supported File Types
SUPPORTED_FILE_TYPES = ["pdf", "txt", "docx", "xlsx", "xls", "csv", "epub"]
