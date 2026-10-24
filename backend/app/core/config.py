import os
from typing import List, Union
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "UrbanPulse Backend API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Required environment settings
    ENV: str = "dev"  # dev | prod
    DATABASE_URL: str = "postgresql://localhost:5432/urbanpulse"
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_JWT_SECRET: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    ALLOWED_ORIGINS: Union[str, List[str]] = "http://localhost:8080,http://127.0.0.1:8080,http://localhost:8000,http://127.0.0.1:8000,http://localhost:3000"
    DATA_GOV_IN_API_KEY: str = ""
    GOOGLE_AQI_API_KEY: str = ""  # Google Air Quality API key — kept server-side only

    # UrbanPulse Intelligence Assistant & Semantic Cache Configuration
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "qwen3:8b"           # legacy alias — kept for back-compat
    OLLAMA_PRIMARY_MODEL: str = "qwen3:8b"   # Level-2 preferred general model
    OLLAMA_FALLBACK_MODEL: str = "mistral"   # Level-3 fallback (used if installed)
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"
    OLLAMA_TIMEOUT_SECONDS: int = 90         # Per-request LLM timeout
    REDIS_URL: str = "redis://127.0.0.1:6379/0"
    REDIS_CACHE_TTL: int = 86400             # 24 hours
    REDIS_SIMILARITY_THRESHOLD: float = 0.90

    # Legacy alias support if needed
    @property
    def is_prod(self) -> bool:
        return self.ENV.strip().lower() == "prod"

    @property
    def allowed_origins_list(self) -> List[str]:
        if isinstance(self.ALLOWED_ORIGINS, list):
            return [o.strip() for o in self.ALLOWED_ORIGINS if o.strip()]
        if isinstance(self.ALLOWED_ORIGINS, str):
            return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]
        return []

    # Backward compatibility properties
    @property
    def cors_origins_list(self) -> List[str]:
        return self.allowed_origins_list

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "allow"

settings = Settings()
