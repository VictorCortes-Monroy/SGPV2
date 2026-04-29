"""Configuración de la aplicación, cargada desde variables de entorno."""

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings tipados. Se lee desde .env y variables de entorno."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Aplicación
    app_env: Literal["development", "staging", "production"] = "development"
    app_debug: bool = True
    app_port: int = 8000

    # Database
    database_url: str = "postgresql+asyncpg://sgp:sgp_dev_password@localhost:5432/sgp_dev"

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_postgres_scheme(cls, v: str) -> str:
        """Railway/Heroku/etc. inyectan `postgresql://` (driver psycopg2 default).
        SQLAlchemy async requiere `postgresql+asyncpg://`. Auto-traducimos para
        que el operador no tenga que masagear la env var en el panel."""
        if isinstance(v, str) and v.startswith("postgresql://"):
            return "postgresql+asyncpg://" + v[len("postgresql://"):]
        return v

    # Auth
    auth_mode: Literal["mock", "clerk"] = "mock"
    clerk_secret_key: str | None = None
    clerk_jwt_verification_key: str | None = None

    # CORS
    cors_origins: str = "http://localhost:3000"

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "console"

    # Storage de adjuntos (Railway volume hoy, Azure Blob a futuro).
    # `storage_path` debe ser un path en disco persistente: en Railway viene
    # del volume mount, en local debería ser un bind mount del docker-compose.
    storage_path: str = "/data/sgp/adjuntos"
    storage_max_file_mb: int = 10
    storage_allowed_mimes: str = (
        "application/pdf,"
        "image/png,image/jpeg,image/webp,"
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,"
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document,"
        "text/plain,text/csv"
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def storage_allowed_mimes_set(self) -> set[str]:
        return {m.strip() for m in self.storage_allowed_mimes.split(",") if m.strip()}

    @property
    def storage_max_file_bytes(self) -> int:
        return self.storage_max_file_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Singleton de settings. Cacheado para evitar re-lectura."""
    return Settings()
