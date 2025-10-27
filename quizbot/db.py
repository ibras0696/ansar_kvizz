from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from quizbot.config import settings

engine = create_async_engine(settings.database_url, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _) -> None:
    """
    Включает поддержку каскадов для SQLite соединений.

    :param dbapi_conn: DB-API соединение.
    :param _: Дополнительный аргумент события (не используется).
    :return: None
    """
    try:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    except Exception:
        pass


class Base(DeclarativeBase):
    """Базовый класс для ORM-моделей SQLAlchemy."""


async def init_db() -> None:
    """
    Создаёт структуру БД и проверяет соединение.

    :return: None
    """
    from quizbot import models  # noqa: F401 - ensure models import

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
