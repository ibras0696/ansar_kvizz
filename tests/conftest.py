from __future__ import annotations

import os
from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from quizbot.db import Base
from quizbot.services.game_state import STATE
from quizbot.services import registration_state

# Минимальный набор переменных окружения для Settings.
os.environ.setdefault("BOT_TOKEN", "TEST:TOKEN")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("DEFAULT_ADMIN_IDS", "1")


@pytest_asyncio.fixture
async def engine() -> AsyncGenerator[any, None]:
    """
    Создаёт in-memory SQLite движок для проверки сервисов.

    :return: Асинхронный движок.
    """

    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield test_engine
    await test_engine.dispose()


@pytest.fixture
def session_factory(engine) -> async_sessionmaker[AsyncSession]:
    """
    Предоставляет фабрику асинхронных сессий поверх тестового движка.

    :param engine: Асинхронный движок.
    :return: async_sessionmaker.
    """

    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def session(session_factory: async_sessionmaker[AsyncSession]) -> AsyncGenerator[AsyncSession, None]:
    """
    Возвращает асинхронную сессию для теста.

    :param session_factory: Фабрика сессий.
    :return: Автоуправляемая сессия.
    """

    async with session_factory() as db:
        yield db


@pytest.fixture(autouse=True)
def clear_state() -> Generator[None, None, None]:
    """
    Сбрасывает очередь в памяти перед каждым тестом.

    :return: None
    """

    STATE.clear()
    registration_state.PENDING_REGISTRATION.clear()
    yield
    STATE.clear()
    registration_state.PENDING_REGISTRATION.clear()
