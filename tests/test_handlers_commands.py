from __future__ import annotations

from typing import Any, List

import pytest
from sqlalchemy import select, update

from quizbot.models import Game, Team, TeamMember
from quizbot.services.game_state import STATE, get_state


class FakeChat:
    """Простая модель чата для имитации aiogram объекта."""

    def __init__(self, chat_id: int, chat_type: str = "group") -> None:
        """
        Инициализирует поддельный чат с нужным типом.

        :param chat_id: Идентификатор чата.
        :param chat_type: Тип чата (group/supergroup/private).
        :return: None
        """
        self.id = chat_id
        self.type = chat_type


class FakeUser:
    """Минимальная модель пользователя."""

    def __init__(self, user_id: int) -> None:
        """
        Запоминает идентификатор пользователя.

        :param user_id: Telegram ID пользователя.
        :return: None
        """
        self.id = user_id


class FakeMessage:
    """Сообщение, перехватывающее вызовы answer()."""

    def __init__(self, chat_id: int, user_id: int, text: str, chat_type: str = "group") -> None:
        """
        Создаёт сообщение с контекстом чата и пользователя.

        :param chat_id: Идентификатор чата.
        :param user_id: Telegram ID отправителя.
        :param text: Текст команды/сообщения.
        :param chat_type: Тип чата (по умолчанию group).
        :return: None
        """
        self.chat = FakeChat(chat_id, chat_type)
        self.from_user = FakeUser(user_id)
        self.text = text
        self._answers: List[dict[str, Any]] = []

    async def answer(self, text: str, reply_markup: Any | None = None) -> None:
        """
        Имитирует ответ бота и сохраняет его в историю.

        :param text: Текст ответа.
        :param reply_markup: Переданная клавиатура (если есть).
        :return: None
        """
        self._answers.append({"text": text, "reply_markup": reply_markup})

    @property
    def answers(self) -> List[dict[str, Any]]:
        """
        Возвращает накопленные ответы сообщения.

        :return: Список словарей с текстами и клавиатурами.
        """
        return self._answers


@pytest.mark.asyncio
async def test_cmd_start_shows_keyboard(monkeypatch):
    """
    Проверяет, что команда /start возвращает клавиатуру с «БАЗЗЕРом».

    :param monkeypatch: Фикстура monkeypatch (не используется напрямую).
    :return: None
    """
    from quizbot.handlers import commands

    msg = FakeMessage(chat_id=1, user_id=1, text="/start")
    msg.chat.type = "group"

    await commands.cmd_start(msg)

    assert msg.answers
    assert msg.answers[-1]["reply_markup"] is not None


@pytest.mark.asyncio
async def test_cmd_register_creates_team(session_factory, monkeypatch):
    """
    Удостоверяется, что регистрация команды создаёт Team и TeamMember.

    :param session_factory: Фабрика асинхронных сессий.
    :param monkeypatch: Фикстура для подмены SessionLocal.
    :return: None
    """
    from quizbot.handlers import commands

    monkeypatch.setattr(commands, "SessionLocal", session_factory)
    msg = FakeMessage(chat_id=10, user_id=100, text="/register_team Alpha")

    await commands.cmd_register(msg)

    async with session_factory() as session:
        team = await session.scalar(select(Team).where(Team.chat_id == 10, Team.name == "Alpha"))
        assert team is not None
        member = await session.scalar(
            select(TeamMember).where(
                TeamMember.chat_id == 10, TeamMember.tg_user_id == 100, TeamMember.team_id == team.id
            )
        )
        assert member is not None


@pytest.mark.asyncio
async def test_cmd_new_game_creates_owner(session_factory, monkeypatch):
    """
    Проверяет, что /new_game назначает ведущего и очищает очередь.

    :param session_factory: Фабрика асинхронных сессий.
    :param monkeypatch: Фикстура для подмены SessionLocal.
    :return: None
    """
    from quizbot.handlers import commands

    monkeypatch.setattr(commands, "SessionLocal", session_factory)
    chat_id = 20
    message = FakeMessage(chat_id=chat_id, user_id=200, text="/new_game")

    state = get_state(chat_id)
    state.queue.extend([1, 2])

    # Ensure previous unfinished game exists
    async with session_factory() as session:
        session.add(Game(chat_id=chat_id, owner_user_id=999, status="running"))
        await session.commit()

    await commands.cmd_new_game(message)

    async with session_factory() as session:
        game = await session.scalar(select(Game).where(Game.chat_id == chat_id))
        assert game is not None
        assert game.owner_user_id == 200
        assert game.status == "idle"

    assert state.queue == []


@pytest.mark.asyncio
async def test_cmd_start_denies_non_admin(session_factory, monkeypatch):
    """
    Убеждается, что неведущий получает отказ при запуске игры.

    :param session_factory: Фабрика асинхронных сессий.
    :param monkeypatch: Фикстура для подмены SessionLocal.
    :return: None
    """
    from quizbot.handlers import commands

    monkeypatch.setattr(commands, "SessionLocal", session_factory)
    chat_id = 30

    async with session_factory() as session:
        session.add(Game(chat_id=chat_id, owner_user_id=1, status="idle"))
        await session.commit()

    message = FakeMessage(chat_id=chat_id, user_id=999, text="/start_game")
    await commands.cmd_start_game(message)

    assert message.answers[-1]["text"] == "Только ведущий может начать игру."


@pytest.mark.asyncio
async def test_cmd_start_game_allows_admin(session_factory, monkeypatch):
    """
    Проверяет, что ведущий может перевести игру в статус running.

    :param session_factory: Фабрика асинхронных сессий.
    :param monkeypatch: Фикстура для подмены SessionLocal.
    :return: None
    """
    from quizbot.handlers import commands

    monkeypatch.setattr(commands, "SessionLocal", session_factory)
    chat_id = 40
    user_id = 400

    async with session_factory() as session:
        session.add(Game(chat_id=chat_id, owner_user_id=user_id, status="idle"))
        await session.commit()

    message = FakeMessage(chat_id=chat_id, user_id=user_id, text="/start_game")
    await commands.cmd_start_game(message)

    async with session_factory() as session:
        game = await session.scalar(select(Game).where(Game.chat_id == chat_id))
        assert game.status == "running"

    assert "Игра началась" in message.answers[-1]["text"]


@pytest.mark.asyncio
async def test_cmd_order_displays_queue(session_factory, monkeypatch):
    """
    Удостоверяется, что /order показывает текущую очередь команд.

    :param session_factory: Фабрика асинхронных сессий.
    :param monkeypatch: Фикстура для подмены SessionLocal.
    :return: None
    """
    from quizbot.handlers import commands

    monkeypatch.setattr(commands, "SessionLocal", session_factory)
    chat_id = 50
    owner = 500

    async with session_factory() as session:
        team = Team(chat_id=chat_id, name="Delta")
        session.add_all([team, Game(chat_id=chat_id, owner_user_id=owner, status="running")])
        await session.flush()
        get_state(chat_id).queue.append(team.id)
        await session.commit()

    message = FakeMessage(chat_id=chat_id, user_id=owner, text="/order")
    await commands.cmd_order(message)

    assert "Очередь: 1) Delta" in message.answers[-1]["text"]


@pytest.mark.asyncio
async def test_cmd_order_when_empty(session_factory, monkeypatch):
    """
    Проверяет, что /order сообщает об отсутствии очереди.

    :param session_factory: Фабрика асинхронных сессий.
    :param monkeypatch: Фикстура для подмены SessionLocal.
    :return: None
    """
    from quizbot.handlers import commands

    monkeypatch.setattr(commands, "SessionLocal", session_factory)
    chat_id = 55
    owner = 505

    async with session_factory() as session:
        session.add(Game(chat_id=chat_id, owner_user_id=owner, status="running"))
        await session.commit()

    message = FakeMessage(chat_id=chat_id, user_id=owner, text="/order")
    await commands.cmd_order(message)

    assert message.answers[-1]["text"] == "Очередь пуста."


@pytest.mark.asyncio
async def test_cmd_wrong_advances_queue(session_factory, monkeypatch):
    """
    Проверяет, что /wrong сдвигает очередь и объявляет следующего.

    :param session_factory: Фабрика асинхронных сессий.
    :param monkeypatch: Фикстура для подмены SessionLocal.
    :return: None
    """
    from quizbot.handlers import commands

    monkeypatch.setattr(commands, "SessionLocal", session_factory)
    chat_id = 60
    owner = 600

    async with session_factory() as session:
        alpha = Team(chat_id=chat_id, name="Alpha")
        beta = Team(chat_id=chat_id, name="Beta")
        session.add_all([alpha, beta, Game(chat_id=chat_id, owner_user_id=owner, status="running")])
        await session.flush()
        get_state(chat_id).queue.extend([alpha.id, beta.id])
        await session.commit()

    message = FakeMessage(chat_id=chat_id, user_id=owner, text="/wrong")
    await commands.cmd_wrong(message)

    assert "Следующая команда отвечает: Beta" in message.answers[-1]["text"]
    assert "Далее: —" in message.answers[-1]["text"]


@pytest.mark.asyncio
async def test_cmd_finish_clears_state(session_factory, monkeypatch):
    """
    Проверяет, что /finish_game завершает игру и очищает STATE.

    :param session_factory: Фабрика асинхронных сессий.
    :param monkeypatch: Фикстура для подмены SessionLocal.
    :return: None
    """
    from quizbot.handlers import commands

    monkeypatch.setattr(commands, "SessionLocal", session_factory)
    chat_id = 70
    owner = 700

    async with session_factory() as session:
        session.add(Game(chat_id=chat_id, owner_user_id=owner, status="running"))
        await session.commit()

    state = get_state(chat_id)
    state.queue.append(123)

    message = FakeMessage(chat_id=chat_id, user_id=owner, text="/finish_game")
    await commands.cmd_finish(message)

    assert chat_id not in STATE
    async with session_factory() as session:
        game = await session.scalar(select(Game).where(Game.chat_id == chat_id))
        assert game.status == "finished"


@pytest.mark.asyncio
async def test_cmd_correct_resets_queue(session_factory, monkeypatch):
    """
    Убеждается, что /correct очищает очередь текущего чата.

    :param session_factory: Фабрика асинхронных сессий.
    :param monkeypatch: Фикстура для подмены SessionLocal.
    :return: None
    """
    from quizbot.handlers import commands

    monkeypatch.setattr(commands, "SessionLocal", session_factory)
    chat_id = 80
    owner = 800

    async with session_factory() as session:
        session.add(Game(chat_id=chat_id, owner_user_id=owner, status="running"))
        await session.commit()

    get_state(chat_id).queue.append(1)

    message = FakeMessage(chat_id=chat_id, user_id=owner, text="/correct")
    await commands.cmd_correct(message)

    assert get_state(chat_id).queue == []


@pytest.mark.asyncio
async def test_cmd_next_round_resets_queue(session_factory, monkeypatch):
    """
    Проверяет, что /next_round обнуляет очередь перед новым вопросом.

    :param session_factory: Фабрика асинхронных сессий.
    :param monkeypatch: Фикстура для подмены SessionLocal.
    :return: None
    """
    from quizbot.handlers import commands

    monkeypatch.setattr(commands, "SessionLocal", session_factory)
    chat_id = 85
    owner = 850

    async with session_factory() as session:
        session.add(Game(chat_id=chat_id, owner_user_id=owner, status="running"))
        await session.commit()

    get_state(chat_id).queue.extend([1, 2])

    message = FakeMessage(chat_id=chat_id, user_id=owner, text="/next_round")
    await commands.cmd_next_round(message)

    assert get_state(chat_id).queue == []


@pytest.mark.asyncio
async def test_is_admin_accepts_default_admin(monkeypatch):
    """
    Удостоверяется, что ID из DEFAULT_ADMIN_IDS распознаётся как ведущий.

    :param monkeypatch: Фикстура monkeypatch для замены списка админов.
    :return: None
    """
    from quizbot.handlers import commands
    from quizbot.config import settings

    monkeypatch.setattr(settings, "default_admin_ids", [900])
    message = FakeMessage(chat_id=1, user_id=900, text="/start")

    class DummySession:
        async def scalar(self, *_args, **_kwargs):
            return None

    assert await commands._is_admin(message, DummySession())
