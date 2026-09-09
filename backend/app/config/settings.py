"""
Cortex Gateway — Centralized Application Settings.

All configuration is loaded from environment variables and/or a .env file.
DATABASE_URL and REDIS_URL are auto-constructed from component variables;
callers should always use the computed properties, never raw component vars.

Phase 2 adds provider API keys, enable flags, timeout, and routing defaults.
Provider API keys are NEVER logged or returned to clients.
"""

from functools import lru_cache
from typing import List

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    app_name: str = "Cortex Gateway"
    app_version: str = "1.0.0"
    app_description: str = (
        "Intelligent Multi-LLM Gateway and AI Infrastructure Platform"
    )
    environment: str = "development"
    debug: bool = False

    # ── API Server ────────────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # ── PostgreSQL component variables (source of truth) ─────────────────────
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "cortex_gateway"
    postgres_user: str = "cortex_user"
    postgres_password: str = "change_me"

    # ── PostgreSQL connection URL (auto-composed; can override) ───────────────
    database_url: str = ""

    # ── Redis component variables (source of truth) ───────────────────────────
    redis_host: str = "redis"
    redis_port: int = 6379

    # ── Redis connection URL (auto-composed; can override) ────────────────────
    redis_url: str = ""

    # ── Security ──────────────────────────────────────────────────────────────
    secret_key: str = "change_me"

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = "INFO"

    # ── CORS ─────────────────────────────────────────────────────────────────
    cors_origins: str = "http://localhost:5173"

    # ── Provider: Global ─────────────────────────────────────────────────────
    provider_timeout_seconds: int = 30
    default_provider: str = ""
    default_model: str = ""

    # ── Provider: Google Gemini ───────────────────────────────────────────────
    gemini_api_key: str = ""
    gemini_enabled: bool = True
    gemini_timeout_seconds: int = 30

    # ── Provider: Groq ────────────────────────────────────────────────────────
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_enabled: bool = True
    groq_timeout_seconds: int = 30

    # ── Provider: Ollama (Local / Self-hosted) ─────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    ollama_enabled: bool = True
    ollama_timeout_seconds: int = 60

    # ── Provider: OpenAI (Deprecated / Inactive) ──────────────────────────────
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_enabled: bool = False

    # ── Routing Engine (Phase 3) ──────────────────────────────────────────────
    routing_enabled: bool = True
    routing_default_mode: str = "auto"
    routing_health_weight: float = 0.30
    routing_success_rate_weight: float = 0.30
    routing_latency_weight: float = 0.20
    routing_cost_weight: float = 0.20
    routing_ollama_cost_per_1k: float = 0.00

    # ── Reliability & Resilience (Phase 4) ────────────────────────────────────
    reliability_total_request_timeout_seconds: int = 120
    reliability_max_retries: int = 2
    reliability_retry_base_delay_seconds: float = 0.25
    reliability_retry_max_delay_seconds: float = 2.0
    reliability_retry_jitter: bool = True
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_cooldown_seconds: float = 30.0
    circuit_breaker_half_open_trials: int = 1
    reliability_max_failover_attempts: int = 2

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: object) -> object:
        # Accept comma-separated string or already a list
        return v

    @property
    def cors_origins_list(self) -> List[str]:
        """Return CORS origins as a list of strings."""
        raw = self.cors_origins
        if isinstance(raw, list):
            return [o.strip() for o in raw if o.strip()]
        return [o.strip() for o in raw.split(",") if o.strip()]

    @model_validator(mode="after")
    def compose_connection_urls(self) -> "Settings":
        """
        Auto-build DATABASE_URL and REDIS_URL from component parts when they
        are not explicitly provided.  The asyncpg driver is used for async I/O.
        """
        if not self.database_url:
            self.database_url = (
                f"postgresql+asyncpg://{self.postgres_user}:"
                f"{self.postgres_password}@{self.postgres_host}:"
                f"{self.postgres_port}/{self.postgres_db}"
            )
        if not self.redis_url:
            self.redis_url = (
                f"redis://{self.redis_host}:{self.redis_port}"
            )
        return self

    @property
    def is_development(self) -> bool:
        return self.environment.lower() == "development"

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    # ── Provider availability helpers ─────────────────────────────────────────

    @property
    def gemini_available(self) -> bool:
        return self.gemini_enabled and bool(self.gemini_api_key)

    @property
    def groq_available(self) -> bool:
        return self.groq_enabled and bool(self.groq_api_key)

    @property
    def ollama_available(self) -> bool:
        """Ollama is local and available whenever enabled with a base URL."""
        return self.ollama_enabled and bool(self.ollama_base_url)

    @property
    def openai_available(self) -> bool:
        return self.openai_enabled and bool(self.openai_api_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the singleton Settings instance (cached after first call)."""
    return Settings()
