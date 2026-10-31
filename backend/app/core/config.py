import os
from pathlib import Path
from typing import List, Union, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AliasChoices, Field

# Locate root directory and potential .env files
CURRENT_FILE = Path(__file__).resolve()
ROOT_DIR = CURRENT_FILE.parent.parent.parent.parent
BACKEND_DIR = CURRENT_FILE.parent.parent.parent

# Detect primary env file
ENV_FILE = None
for candidate in [
    os.environ.get("ENV_FILE"),
    ROOT_DIR / ".env",
    BACKEND_DIR / ".env",
    Path(".env")
]:
    if candidate and Path(candidate).exists():
        ENV_FILE = Path(candidate)
        break


class Settings(BaseSettings):
    PROJECT_NAME: str = "UrbanPulse Backend API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Environment mode (dev | prod | development | production)
    ENV: str = Field(
        default="dev",
        validation_alias=AliasChoices("ENV", "ENVIRONMENT", "env", "environment")
    )
    
    # Database connection
    DATABASE_URL: str = Field(
        default="postgresql+psycopg2://localhost:5432/urbanpulse",
        validation_alias=AliasChoices("DATABASE_URL", "database_url")
    )
    
    # Supabase credentials (keep private secrets server-side only)
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_JWT_SECRET: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    
    # Optional administrative initialization credentials (never hardcoded with defaults)
    ADMIN_INITIAL_EMAIL: str = ""
    ADMIN_INITIAL_PASSWORD: str = ""
    
    # CORS Origins
    ALLOWED_ORIGINS: Union[str, List[str]] = Field(
        default="http://localhost:8080,http://127.0.0.1:8080,http://localhost:8000,http://127.0.0.1:8000,http://localhost:3000",
        validation_alias=AliasChoices("ALLOWED_ORIGINS", "CORS_ORIGINS", "allowed_origins", "cors_origins")
    )
    
    DATA_GOV_IN_API_KEY: str = ""
    GOOGLE_AQI_API_KEY: str = ""  # Google Air Quality API key — server-side only

    # Map & Routing Provider Configuration
    ROUTING_PROVIDER: str = "osrm"  # osrm | custom
    OSRM_BASE_URL: str = "https://router.project-osrm.org"
    NOMINATIM_BASE_URL: str = "https://nominatim.openstreetmap.org"
    OVERPASS_BASE_URL: str = "https://overpass-api.de/api/interpreter"
    MAP_REQUEST_TIMEOUT_SECONDS: int = 8

    # UrbanPulse Intelligence Assistant & Semantic Cache Configuration
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "qwen3:4b"           # legacy alias
    OLLAMA_PRIMARY_MODEL: str = "qwen3:4b"   # Level-2 preferred general model
    OLLAMA_FALLBACK_MODEL: str = "mistral"   # Level-3 fallback
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"
    OLLAMA_TIMEOUT_SECONDS: int = 30         # Per-request LLM timeout
    REDIS_URL: str = "redis://127.0.0.1:6379/0"
    REDIS_CACHE_TTL: int = 86400             # 24 hours
    REDIS_SIMILARITY_THRESHOLD: float = 0.90

    @property
    def is_prod(self) -> bool:
        norm = self.ENV.strip().lower()
        return norm in ("prod", "production")

    @property
    def allowed_origins_list(self) -> List[str]:
        if isinstance(self.ALLOWED_ORIGINS, list):
            return [o.strip() for o in self.ALLOWED_ORIGINS if o.strip()]
        if isinstance(self.ALLOWED_ORIGINS, str):
            return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]
        return []

    @property
    def cors_origins_list(self) -> List[str]:
        return self.allowed_origins_list

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE) if ENV_FILE else None,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow"
    )


settings = Settings()
