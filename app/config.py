from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str = Field(alias="BOT_TOKEN")
    database_url: str = Field(alias="DATABASE_URL")

    group_chat_id: int = Field(alias="GROUP_CHAT_ID")
    topic_id: Optional[int] = Field(default=None, alias="TOPIC_ID")

    tz: str = Field(default="Europe/Moscow", alias="TZ")
    daily_post_hour: int = Field(default=9, alias="DAILY_POST_HOUR")
    daily_post_minute: int = Field(default=0, alias="DAILY_POST_MINUTE")

    owner_user_id: int = Field(alias="OWNER_USER_ID")

    callback_secret: str = Field(alias="CALLBACK_SECRET")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    @field_validator("topic_id", mode="before")
    @classmethod
    def _normalize_topic_id(cls, value):  # type: ignore[no-untyped-def]
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            if stripped == "":
                return None
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
