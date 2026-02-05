from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", extra="ignore")

    app_name: str = "Backend API"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
