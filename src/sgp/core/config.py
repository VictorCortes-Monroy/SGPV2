"""Configuración de la aplicación, cargada desde variables de entorno."""

from functools import lru_cache
from typing import Literal

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

    # Auth
    auth_mode: Literal["mock", "clerk"] = "mock"
    clerk_secret_key: str | None = None
    clerk_jwt_verification_key: str | None = None

    # CORS
    cors_origins: str = "http://localhost:3000"

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "console"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Singleton de settings. Cacheado para evitar re-lectura."""
    return Settings()
