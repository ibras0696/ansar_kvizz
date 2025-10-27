import os
from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

ORIGINAL_ENV = {key: os.environ.get(key) for key in ["BOT_TOKEN", "DATABASE_URL", "LOG_LEVEL"]}
os.environ.setdefault("BOT_TOKEN", "TEST:TOKEN")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("LOG_LEVEL", "WARNING")

from quizbot.db import Base
from quizbot.services.game_state import STATE


@pytest.fixture(autouse=True, scope="session")
def restore_env() -> Generator[None, None, None]:
    """
    Возвращает переменные окружения к исходным значениям после тестов.

    :return: None
    """
    yield
    for key, value in ORIGINAL_ENV.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@pytest_asyncio.fixture
async def engine() -> AsyncGenerator[Any, None]:
    """
    Создаёт и инициализирует in-memory SQLite движок для тестов.

    :return: Асинхронный генератор с движком.
    """
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield test_engine
    await test_engine.dispose()


@pytest.fixture
def session_factory(engine: Any) -> Any:
    """
    Предоставляет фабрику сессий поверх тестового движка.

    :param engine: Асинхронный движок SQLite.
    :return: Фабрика асинхронных сессий.
    """
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def session(session_factory: Any) -> AsyncGenerator[AsyncSession, None]:
    """
    Возвращает асинхронную сессию БД для использования в тесте.

    :param session_factory: Фабрика асинхронных сессий.
    :return: Асинхронная сессия SQLAlchemy.
    """
    async with session_factory() as db:
        yield db


@pytest.fixture(autouse=True)
def clear_state() -> Generator[None, None, None]:
    """
    Сбрасывает in-memory состояние очередей перед и после каждого теста.

    :return: None
    """
    STATE.clear()
    yield
    STATE.clear()
