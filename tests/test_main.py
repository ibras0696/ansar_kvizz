import asyncio
from types import SimpleNamespace

import pytest


class DummyDispatcher:
    """Заглушка Dispatcher, фиксирующая вызовы."""

    def __init__(self) -> None:
        self.routers = []
        self.started = False

    def include_router(self, router) -> None:
        self.routers.append(router)

    async def start_polling(self, _bot) -> None:
        self.started = True


class DummyBot:
    """Заглушка для aiogram.Bot."""

    def __init__(self, *args, **kwargs) -> None:  # noqa: D401 - совместимость сигнатуры
        """Сохраняет аргументы и ничего не делает."""
        self.args = args
        self.kwargs = kwargs


@pytest.mark.asyncio
async def test_main_async(monkeypatch):
    from quizbot import __main__

    dummy_dispatcher = DummyDispatcher()

    async def fake_init_db() -> None:
        """Имитирует инициализацию БД."""

    monkeypatch.setattr(__main__, "init_db", fake_init_db)
    monkeypatch.setattr(__main__, "Dispatcher", lambda: dummy_dispatcher)
    monkeypatch.setattr(__main__, "Bot", DummyBot)

    await __main__.main_async()

    assert dummy_dispatcher.started is True
    assert dummy_dispatcher.routers  # оба роутера подключены


def test_main_wrapper(monkeypatch):
    from quizbot import __main__

    called = {}

    def fake_run(coro):
        called["coro"] = coro
        coro.close()

    monkeypatch.setattr(asyncio, "run", fake_run)

    __main__.main()

    assert called["coro"].cr_code is __main__.main_async.__code__
