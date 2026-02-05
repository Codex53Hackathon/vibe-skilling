from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")

    app_name: str = "Backend API"
    mongo_uri: str | None = Field(default=None, validation_alias="MONGODB_URI")
    mongo_database: str = Field(default="vibe_skilling", validation_alias="MONGODB_DATABASE")
    mongo_collection: str = Field(
        default="conversation_events", validation_alias="MONGODB_COLLECTION"
    )
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", validation_alias="OPENAI_MODEL")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
