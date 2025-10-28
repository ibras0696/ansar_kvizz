from __future__ import annotations

import pytest
from sqlalchemy import select

from quizbot.keyboards import BUZZER_CB
from quizbot.models import Game, Team, TeamMember
from quizbot.services.game_state import get_state


class FakeMessage:
    """Имитация сообщения для проверки ответов callback-хэндлера."""

    def __init__(self, chat_id: int) -> None:
        """
        Создаёт объект сообщения с указанным чат ID.

        :param chat_id: Идентификатор тестового чата.
        :return: None
        """
        self.chat = type("Chat", (), {"id": chat_id})()
        self.sent = []

    async def answer(self, text: str) -> None:
        """
        Эмулирует отправку сообщения ботом.

        :param text: Текст сообщения.
        :return: None
        """
        self.sent.append(text)


class FakeCallback:
    """Имитация CallbackQuery."""

    def __init__(self, chat_id: int, user_id: int) -> None:
        """
        Формирует поддельный callback с заданными ID.

        :param chat_id: Идентификатор чата.
        :param user_id: Идентификатор пользователя.
        :return: None
        """
        self.from_user = type("User", (), {"id": user_id})()
        self.message = FakeMessage(chat_id)
        self.data = BUZZER_CB
        self.responses = []

    async def answer(self, text: str, show_alert: bool = False) -> None:
        """
        Сохраняет ответ callback-хэндлера.

        :param text: Возвращаемый текст.
        :param show_alert: Флаг необходимости алерта.
        :return: None
        """
        self.responses.append((text, show_alert))


@pytest.mark.asyncio
async def test_on_buzzer_announces_first(session_factory, monkeypatch):
    """
    Проверяет, что первый нажимающий объявляется и очередь дополняется корректно.

    :param session_factory: Фабрика асинхронных сессий.
    :param monkeypatch: Фикстура для подмены SessionLocal.
    :return: None
    """
    from quizbot.handlers import callbacks

    monkeypatch.setattr(callbacks, "SessionLocal", session_factory)

    chat_id = 5000
    user_id = 42

    async with session_factory() as session:
        team = Team(chat_id=chat_id, name="Rockets")
        game = Game(chat_id=chat_id, owner_user_id=user_id, status="running")
        session.add_all([team, game])
        await session.flush()
        session.add(TeamMember(chat_id=chat_id, team_id=team.id, tg_user_id=user_id))
        await session.commit()

    cb = FakeCallback(chat_id, user_id)
    await callbacks.on_buzzer(cb)

    assert cb.responses[-1][0] == "Вы первые!"
    assert "Отвечает: Rockets" in cb.message.sent[-1]

    # Нажатие второго игрока добавляет его в очередь
    async with session_factory() as session:
        second_team = Team(chat_id=chat_id, name="Lions")
        session.add(second_team)
        await session.flush()
        session.add(TeamMember(chat_id=chat_id, team_id=second_team.id, tg_user_id=99))
        await session.commit()

    cb2 = FakeCallback(chat_id, 99)
    await callbacks.on_buzzer(cb2)
    assert "Принято" in cb2.responses[-1][0]
    assert get_state(chat_id).queue[-1] != get_state(chat_id).queue[0]
