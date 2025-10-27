from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Загружает настройки приложения из переменных окружения.

    :ivar bot_token: Telegram Bot API токен.
    :ivar database_url: URL подключения к базе данных.
    :ivar default_admin_ids: Базовый список админов, которым разрешён доступ.
    :ivar log_level: Уровень логирования.
    """
    bot_token: str = Field(alias="BOT_TOKEN")
    database_url: str = Field(default="sqlite+aiosqlite:///data/bot.db", alias="DATABASE_URL")
    default_admin_ids: List[int] = Field(default_factory=list, alias="DEFAULT_ADMIN_IDS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    @field_validator("default_admin_ids", mode="before")
    @classmethod
    def _split_admins(cls, value: str | List[int] | None) -> List[int]:
        """
        Преобразует строку идентификаторов в список чисел.

        :param value: Исходное значение из конфигурации.
        :return: Список чисел администраторов.
        """
        if isinstance(value, str) and value.strip():
            return [int(item) for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return value
        return []


settings = Settings()
