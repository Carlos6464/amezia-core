from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_root_env_file() -> Path | None:
    """
    Autor: Carlos Adriano
    Data: 2026-08-06
    Descrição: Sobe os diretórios a partir deste arquivo até achar o .env da
    raiz do monorepo. Localmente aponta pro .env real; dentro do container
    não existe (env vars chegam via `env_file` do docker-compose), então
    retorna None e o pydantic-settings usa só as variáveis de ambiente.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".env"
        if candidate.exists():
            return candidate
    return None


ROOT_ENV_FILE = _find_root_env_file()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: str = "development"

    DATABASE_URL: str
    REDIS_URL: str
    JWT_SECRET: str
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30
    REPORT_VIEW_TOKEN_EXPIRE_MINUTES: int = 60

    FRONTEND_URL: str = "http://localhost:8080"

    GEMINI_API_KEY: str | None = None
    GROK_API_KEY: str | None = None

    EVOLUTION_API_URL: str | None = None
    EVOLUTION_API_KEY: str | None = None
    EVOLUTION_QR_CODE_TTL_SECONDS: int = 45

    RESEND_API_KEY: str | None = None
    MAIL_FROM_ADDRESS: str = "no-reply@amezia.app"
    MAIL_FROM_NAME: str = "Amezia"

    GOOGLE_OAUTH_CLIENT_ID: str | None = None
    GOOGLE_OAUTH_CLIENT_SECRET: str | None = None
    GOOGLE_OAUTH_REDIRECT_URI: str | None = None

    AES_ENCRYPTION_KEY: str | None = None
    PHONE_HASH_SECRET: str | None = None

    BACKBLAZE_KEY_ID: str | None = None
    BACKBLAZE_APPLICATION_KEY: str | None = None
    BACKBLAZE_BUCKET_NAME: str | None = None
    BACKBLAZE_ENDPOINT_URL: str | None = None
    BACKBLAZE_REGION: str | None = None

    STRIPE_SECRET_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None
    STRIPE_PRICE_PRO_MONTHLY: str | None = None
    STRIPE_PRICE_PRO_ANNUAL: str | None = None
    STRIPE_PRICE_PREMIUM_MONTHLY: str | None = None
    STRIPE_PRICE_PREMIUM_ANNUAL: str | None = None

    RAG_SIMILARITY_THRESHOLD: float = 0.72
    RAG_POOL_SIZE: int = 300
    RAG_TOP_K: int = 4
    EMBEDDING_DIMENSION: int = 768
    CONVERSATION_ACTIVE_WINDOW_HOURS: int = 24
    CONVERSATION_SUMMARY_THRESHOLD: int = 20
    CATEGORY_DEDUP_THRESHOLD: float = 0.85
    AI_CHAT_TIMEOUT_SECONDS: int = 20

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


@lru_cache
def get_settings() -> Settings:
    """
    Autor: Carlos Adriano
    Data: 2026-08-06
    Descrição: Carrega e cacheia as Settings a partir do .env único na raiz
    do monorepo, evitando reler o arquivo a cada injeção de dependência.
    """
    return Settings()
