from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str = Field(alias="BOT_TOKEN")
    database_url: str = Field(alias="DATABASE_URL")

    group_chat_id: int = Field(alias="GROUP_CHAT_ID")

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




@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
