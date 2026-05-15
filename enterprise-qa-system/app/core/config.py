import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Project root: enterprise-qa-system/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Settings:
    # Database
    DB_TYPE: str = os.getenv("ENTERPRISE_QA_DB_TYPE", "sqlite")
    DB_PATH: str = os.getenv(
        "ENTERPRISE_QA_DB_PATH",
        os.path.join(BASE_DIR, "enterprise.db"),
    )

    # Knowledge base
    KB_PATH: str = os.getenv(
        "ENTERPRISE_QA_KB_PATH",
        os.path.join(BASE_DIR, "knowledge"),
    )

    # Timezone
    TIMEZONE: str = os.getenv("ENTERPRISE_QA_TIMEZONE", "Asia/Shanghai")

    # Current reference date for the exam
    CURRENT_DATE: str = os.getenv("ENTERPRISE_QA_CURRENT_DATE", "2026-03-27")

    # API
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8001"))


settings = Settings()
