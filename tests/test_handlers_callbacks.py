from __future__ import annotations

from types import SimpleNamespace

import pytest

from quizbot.config import settings
from quizbot.handlers import callbacks
from quizbot.keyboards import (
    ADMIN_CORRECT_PREFIX,
    ADMIN_FINISH_GAME_CB,
    ADMIN_SHOW_SCORES_CB,
    ADMIN_START_GAME_CB,
    ADMIN_START_QUESTION_CB,
    ADMIN_WRONG_CB,
    PLAYER_BUZZER_CB,
    PLAYER_REGISTER_CB,
)
from quizbot.services import registration_state
from quizbot.services.game_service import (
    award_score,
    create_game,
    finish_question,
    get_active_game,
    get_or_create_player,
    press_buzzer,
    register_team,
    start_game,
    start_question,
)


class FakeBot:
    """Минимальная заглушка бота — фиксирует отправленные сообщения."""

    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []

    async def send_message(self, chat_id: int, text: str, reply_markup=None) -> None:
        self.sent.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})


class FakeMessage:
    """Сообщение, реагирующее на answer/edit_text."""

    def __init__(self) -> None:
        self.answers: list[str] = []
        self.edits: list[dict[str, object]] = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)

    async def edit_text(self, text: str, reply_markup=None) -> None:
        self.edits.append({"text": text, "reply_markup": reply_markup})


class FakeCallback:
    """Заглушка CallbackQuery."""

    def __init__(self, data: str, user_id: int, bot: FakeBot) -> None:
        self.data = data
        self.from_user = SimpleNamespace(id=user_id, username="cb-user", first_name="CB", last_name=None)
        self.bot = bot
        self.message = FakeMessage()
        self._answers: list[dict[str, object]] = []

    async def answer(self, text: str, show_alert: bool = False) -> None:
        self._answers.append({"text": text, "alert": show_alert})

    @property
    def answers(self) -> list[dict[str, object]]:
        return self._answers


@pytest.mark.asyncio
async def test_player_register_callback_sets_pending(monkeypatch):
    """Кнопка регистрации инициирует ожидание названия."""

    monkeypatch.setattr(callbacks, "SessionLocal", lambda: None)  # не используется
    registration_state.clear(999)
    cb = FakeCallback(PLAYER_REGISTER_CB, user_id=999, bot=FakeBot())
    await callbacks.on_player_register(cb)
    assert registration_state.is_pending(999) is True
    assert cb.message.answers[-1].startswith("Введи название")


@pytest.mark.asyncio
async def test_admin_start_game_creates_broadcast(monkeypatch, session_factory):
    """Запуск игры переводит статус и рассылает сообщения игрокам."""

    settings.default_admin_ids_raw = "1"
    monkeypatch.setattr(callbacks, "SessionLocal", session_factory)

    # подготовим игроков
    async with session_factory() as session:
        player_with_team = await get_or_create_player(session, 101, "with", "Player With")
        await register_team(session, player_with_team, "Comets")
        await get_or_create_player(session, 202, "without", "Player Without")
        await session.commit()

    bot = FakeBot()
    cb = FakeCallback(ADMIN_START_GAME_CB, user_id=1, bot=bot)
    await callbacks.on_admin_start_game(cb)

    # Проверяем изменение статуса игры
    async with session_factory() as session:
        game = await get_active_game(session)
        assert game is not None and game.status == "running"

    # Убедимся, что бот отправил сообщения обеим группам
    recipients = {msg["chat_id"] for msg in bot.sent}
    assert recipients == {101, 202}

    # Сообщение админа должно содержать панель
    assert cb.message.edits[-1]["reply_markup"].inline_keyboard[0][0].callback_data == ADMIN_START_QUESTION_CB


@pytest.mark.asyncio
async def test_player_buzzer_notifies_admin(monkeypatch, session_factory):
    """Первый нажатый «БАЗЗЕР» сообщает ведущему о команде."""

    settings.default_admin_ids_raw = "1"
    monkeypatch.setattr(callbacks, "SessionLocal", session_factory)

    async with session_factory() as session:
        admin_id = 1
        player = await get_or_create_player(session, 303, "alpha", "Alpha")
        team = await register_team(session, player, "Alpha")
        game = await create_game(session, owner_user_id=admin_id)
        await start_game(session, game)
        await start_question(session, game)
        await session.commit()

    bot = FakeBot()
    cb = FakeCallback(PLAYER_BUZZER_CB, user_id=303, bot=bot)
    await callbacks.on_player_buzzer(cb)

    assert cb.answers[-1]["text"].startswith("Вы первые")
    # Ведущий должен получить сообщение о команде
    assert any("Alpha" in msg["text"] for msg in bot.sent if msg["chat_id"] == 1)
    # Команда получает уведомление
    assert any(msg["chat_id"] == 303 for msg in bot.sent)


@pytest.mark.asyncio
async def test_admin_correct_awards_score(monkeypatch, session_factory):
    """Отметка «верно» начисляет баллы и завершает вопрос."""

    settings.default_admin_ids_raw = "1"
    monkeypatch.setattr(callbacks, "SessionLocal", session_factory)

    async with session_factory() as session:
        admin_id = 1
        player = await get_or_create_player(session, 404, "bravo", "Bravo")
        team = await register_team(session, player, "Bravo")
        game = await create_game(session, owner_user_id=admin_id)
        await start_game(session, game)
        await start_question(session, game)
        await press_buzzer(session, game, player)
        await session.commit()
        team_id = team.id

    bot = FakeBot()
    cb = FakeCallback(f"{ADMIN_CORRECT_PREFIX}{team_id}", user_id=1, bot=bot)
    await callbacks.on_admin_correct(cb)

    from quizbot.services.game_service import get_scores

    async with session_factory() as session:
        game = await get_active_game(session)
        scoreboard = await get_scores(session, game)
        assert scoreboard[0][0] == "Bravo"
        assert scoreboard[0][1] == 1

    # Админ получил сообщение с таблицей
    assert any("Bravo" in msg["text"] for msg in bot.sent if msg["chat_id"] == 1)


@pytest.mark.asyncio
async def test_admin_start_question_pushes_buzzer(monkeypatch, session_factory):
    """Запуск вопроса рассылает сигнал игрокам с командами."""

    settings.default_admin_ids_raw = "1"
    monkeypatch.setattr(callbacks, "SessionLocal", session_factory)

    async with session_factory() as session:
        player = await get_or_create_player(session, 505, "delta", "Delta")
        await register_team(session, player, "Delta")
        game = await create_game(session, owner_user_id=1)
        await start_game(session, game)
        await session.commit()

    bot = FakeBot()
    cb = FakeCallback(ADMIN_START_QUESTION_CB, user_id=1, bot=bot)
    await callbacks.on_admin_start_question(cb)

    assert cb.answers[-1]["text"] == "Вопрос запущен."
    assert any("Новый вопрос" in msg["text"] for msg in bot.sent)


@pytest.mark.asyncio
async def test_admin_finish_game_sends_scores(monkeypatch, session_factory):
    """Завершение игры формирует таблицу и рассылает всем."""

    settings.default_admin_ids_raw = "1"
    monkeypatch.setattr(callbacks, "SessionLocal", session_factory)

    async with session_factory() as session:
        player = await get_or_create_player(session, 606, "echo", "Echo")
        team = await register_team(session, player, "Echo")
        game = await create_game(session, owner_user_id=1)
        await start_game(session, game)
        await start_question(session, game)
        await press_buzzer(session, game, player)
        await award_score(session, game, team.id)
        await finish_question(session, game)
        await session.commit()

    bot = FakeBot()
    cb = FakeCallback(ADMIN_FINISH_GAME_CB, user_id=1, bot=bot)
    await callbacks.on_admin_finish_game(cb)

    assert any("Итоги игры" in msg["text"] for msg in bot.sent if msg["chat_id"] == 1)
    assert any("Игра завершена" in msg["text"] for msg in bot.sent)


@pytest.mark.asyncio
async def test_admin_show_scores(monkeypatch, session_factory):
    """Кнопка таблицы выводит текущие очки."""

    settings.default_admin_ids_raw = "1"
    monkeypatch.setattr(callbacks, "SessionLocal", session_factory)

    async with session_factory() as session:
        player = await get_or_create_player(session, 707, "foxtrot", "Foxtrot")
        team = await register_team(session, player, "Foxtrot")
        game = await create_game(session, owner_user_id=1)
        await start_game(session, game)
        await award_score(session, game, team.id)
        await session.commit()

    bot = FakeBot()
    cb = FakeCallback(ADMIN_SHOW_SCORES_CB, user_id=1, bot=bot)
    await callbacks.on_admin_show_scores(cb)
    assert any("Foxtrot" in msg["text"] for msg in bot.sent)


@pytest.mark.asyncio
async def test_admin_wrong_empty_queue(monkeypatch, session_factory):
    """Если очередь пуста, бот просит запустить новый вопрос."""

    settings.default_admin_ids_raw = "1"
    monkeypatch.setattr(callbacks, "SessionLocal", session_factory)

    async with session_factory() as session:
        game = await create_game(session, owner_user_id=1)
        await start_game(session, game)
        await start_question(session, game)
        await session.commit()

    bot = FakeBot()
    cb = FakeCallback(ADMIN_WRONG_CB, user_id=1, bot=bot)
    await callbacks.on_admin_wrong(cb)

    assert any("Очередь закончилась" in msg["text"] for msg in bot.sent)


@pytest.mark.asyncio
async def test_admin_wrong_moves_queue(monkeypatch, session_factory):
    """При неверном ответе очередь переходит к следующей команде."""

    settings.default_admin_ids_raw = "1"
    monkeypatch.setattr(callbacks, "SessionLocal", session_factory)

    async with session_factory() as session:
        admin_id = 1
        player1 = await get_or_create_player(session, 808, "team1", "Team1")
        team1 = await register_team(session, player1, "Team1")
        player2 = await get_or_create_player(session, 809, "team2", "Team2")
        team2 = await register_team(session, player2, "Team2")
        game = await create_game(session, owner_user_id=admin_id)
        await start_game(session, game)
        await start_question(session, game)
        await press_buzzer(session, game, player1)
        await press_buzzer(session, game, player2)
        await session.commit()

    bot = FakeBot()
    cb = FakeCallback(ADMIN_WRONG_CB, user_id=1, bot=bot)
    await callbacks.on_admin_wrong(cb)

    assert any("невер" in msg["text"] for msg in bot.sent if msg["chat_id"] == 808)
    assert any("Team2" in msg["text"] for msg in bot.sent if msg["chat_id"] == 1)


@pytest.mark.asyncio
async def test_player_buzzer_without_game(monkeypatch, session_factory):
    """Игрок получает сообщение, если игра не активна."""

    settings.default_admin_ids_raw = "1"
    monkeypatch.setattr(callbacks, "SessionLocal", session_factory)

    bot = FakeBot()
    cb = FakeCallback(PLAYER_BUZZER_CB, user_id=9999, bot=bot)
    await callbacks.on_player_buzzer(cb)
    assert cb.answers[-1]["alert"] is True and "нет активной игры" in cb.answers[-1]["text"].lower()


@pytest.mark.asyncio
async def test_player_buzzer_without_team(monkeypatch, session_factory):
    """Игроку без команды предлагается зарегистрироваться."""

    settings.default_admin_ids_raw = "1"
    monkeypatch.setattr(callbacks, "SessionLocal", session_factory)

    async with session_factory() as session:
        game = await create_game(session, owner_user_id=1)
        await start_game(session, game)
        await start_question(session, game)
        await session.commit()

    bot = FakeBot()
    cb = FakeCallback(PLAYER_BUZZER_CB, user_id=5555, bot=bot)
    await callbacks.on_player_buzzer(cb)
    assert "без команды" in cb.answers[-1]["text"]
