from typing import List, Optional

from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Подгружаем переменные из .env до создания Settings
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)


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
    default_admin_ids_raw: Optional[str] = Field(default=None, alias="DEFAULT_ADMIN_IDS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    @property
    def default_admin_ids(self) -> List[int]:
        """Возвращает список администраторов из строки окружения."""

        if not self.default_admin_ids_raw:
            return []
        result: List[int] = []
        for chunk in self.default_admin_ids_raw.split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            result.append(int(chunk))
        return result


settings = Settings()
