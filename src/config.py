import os
from typing import List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Central configuration class loading values from environment variables."""

    # Storage Engine ('sheets' or 'mysql')
    STORAGE_ENGINE: str = os.getenv("STORAGE_ENGINE", "sheets").lower()
    GOOGLE_SHEET_ID: str = os.getenv("GOOGLE_SHEET_ID", "")

    # Google Classroom API & Auth
    GOOGLE_CLIENT_SECRETS_FILE: str = os.getenv("GOOGLE_CLIENT_SECRETS_FILE", "credentials.json")
    GOOGLE_TOKEN_FILE: str = os.getenv("GOOGLE_TOKEN_FILE", "token.json")

    # Google Classroom & Google Sheets Scopes
    CLASSROOM_SCOPES: List[str] = [
        "https://www.googleapis.com/auth/classroom.courses.readonly",
        "https://www.googleapis.com/auth/classroom.coursework.me.readonly",
        "https://www.googleapis.com/auth/classroom.coursework.students.readonly",
        "https://www.googleapis.com/auth/spreadsheets"
    ]
    GOOGLE_SCOPES: List[str] = CLASSROOM_SCOPES
    _course_ids_raw: str = os.getenv("CLASSROOM_COURSE_IDS", "")
    CLASSROOM_COURSE_IDS: List[str] = [c.strip() for c in _course_ids_raw.split(",") if c.strip()]

    # AI Chat API
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "gemini").lower()
    AI_API_KEY: str = os.getenv("AI_API_KEY", "")
    AI_MODEL: str = os.getenv("AI_MODEL", "gemini-1.5-flash")
    AI_BASE_URL: str = os.getenv("AI_BASE_URL", "")

    # MariaDB (XAMPP Default)
    DB_HOST: str = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_NAME: str = os.getenv("DB_NAME", "project_planner_db")

    # Gmail SMTP Notification
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes")
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_APP_PASSWORD: str = os.getenv("SMTP_APP_PASSWORD", "").replace(" ", "")
    NOTIFICATION_RECIPIENT: str = os.getenv("NOTIFICATION_RECIPIENT", "")

    # Application & Retry Settings
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    RETRY_BACKOFF_FACTOR: float = float(os.getenv("RETRY_BACKOFF_FACTOR", "2.0"))

    @classmethod
    def validate_db_config(cls) -> bool:
        return bool(cls.DB_HOST and cls.DB_USER and cls.DB_NAME)

    @classmethod
    def validate_ai_config(cls) -> bool:
        return bool(cls.AI_API_KEY)

    @classmethod
    def validate_smtp_config(cls) -> bool:
        return bool(cls.SMTP_USER and cls.SMTP_APP_PASSWORD and cls.NOTIFICATION_RECIPIENT)
