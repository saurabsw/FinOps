import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    PROJECT_NAME: str = "Cloud Cost Optimizer & Remediation Engine"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # SQLite Database - Free, zero-setup, persistent, embedded
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'finops.db'}")
    
    # File storage paths
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = BASE_DIR / "data"
    SAMPLES_DIR: Path = BASE_DIR / "data" / "samples"
    RULES_DIR: Path = BASE_DIR / "data" / "rules"
    UPLOADS_DIR: Path = BASE_DIR / "data" / "uploads"
    STATIC_DIR: Path = BASE_DIR / "app" / "static"
    
    # Safety Gates
    DEFAULT_SAFETY_GATE: bool = True
    ALLOW_FORCE_FLAGS: bool = False  # Explicitly forbidden per FinOps.md

    model_config = SettingsConfigDict(env_file=".env", extra="allow")

settings = Settings()

# Ensure directories exist
settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
settings.SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
settings.RULES_DIR.mkdir(parents=True, exist_ok=True)
