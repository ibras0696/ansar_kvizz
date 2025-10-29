from __future__ import annotations

from types import SimpleNamespace

import pytest

from quizbot.config import settings
from quizbot.handlers import commands
from quizbot.services import registration_state
from quizbot.services.game_service import get_active_game, get_or_create_player, register_team


class FakeMessage:
    """Простая заглушка aiogram Message."""

    def __init__(self, user_id: int, text: str, username: str | None = None) -> None:
        self.text = text
        self.from_user = SimpleNamespace(
            id=user_id,
            username=username,
            first_name="Test",
            last_name=None,
        )
        self.responses: list[dict[str, object]] = []

    async def answer(self, text: str, reply_markup=None) -> None:  # pragma: no cover - exercised in tests
        self.responses.append({"text": text, "reply_markup": reply_markup})


@pytest.mark.asyncio
async def test_cmd_start_player_without_team(monkeypatch, session_factory):
    """Игрок без команды должен получать кнопку регистрации."""

    settings.default_admin_ids_raw = "1"
    monkeypatch.setattr(commands, "SessionLocal", session_factory)

    message = FakeMessage(user_id=111, text="/start")
    await commands.cmd_start(message)

    assert message.responses
    markup = message.responses[-1]["reply_markup"]
    assert markup.inline_keyboard[0][0].callback_data == "player_register"


@pytest.mark.asyncio
async def test_cmd_start_admin_creates_game(monkeypatch, session_factory):
    """Админ при /start получает панель управления и создаёт игру."""

    settings.default_admin_ids_raw = "1"
    monkeypatch.setattr(commands, "SessionLocal", session_factory)

    message = FakeMessage(user_id=1, text="/start")
    await commands.cmd_start(message)

    assert message.responses
    panel = message.responses[-1]["reply_markup"]
    assert panel.inline_keyboard[0][0].callback_data == "admin_start_game"

    from quizbot.services.game_service import get_active_game

    async with session_factory() as session:
        active = await get_active_game(session)
        assert active is not None


@pytest.mark.asyncio
async def test_registration_input_creates_team(monkeypatch, session_factory):
    """После запроса названия игрок может создать команду."""

    settings.default_admin_ids_raw = "1"
    monkeypatch.setattr(commands, "SessionLocal", session_factory)

    user_id = 222
    registration_state.request_name(user_id)
    message = FakeMessage(user_id=user_id, text="Galaxy", username="galaxy")
    await commands.handle_registration_input(message)

    assert "Galaxy" in message.responses[-1]["text"]

    from quizbot.models import Team, TeamMember, Player
    from sqlalchemy import select

    async with session_factory() as session:
        player = await session.scalar(select(Player).where(Player.tg_user_id == user_id))
        assert player is not None
        team_member = await session.scalar(select(TeamMember).where(TeamMember.player_id == player.id))
        assert team_member is not None
        team = await session.scalar(select(Team).where(Team.id == team_member.team_id))
        assert team.name == "Galaxy"


@pytest.mark.asyncio
async def test_registration_duplicate_name(monkeypatch, session_factory):
    """Игрок получает понятное сообщение, если название команды уже занято."""

    settings.default_admin_ids_raw = "1"
    monkeypatch.setattr(commands, "SessionLocal", session_factory)

    # Сначала создаём команду
    async with session_factory() as session:
        player = await get_or_create_player(session, 999, "captain", "Captain")
        await register_team(session, player, "Nova")
        await session.commit()

    # Пытаемся зарегистрировать ту же команду вторым игроком
    user_id = 1001
    registration_state.request_name(user_id)
    message = FakeMessage(user_id=user_id, text="Nova", username="nova-user")
    await commands.handle_registration_input(message)

    assert "существует" in message.responses[-1]["text"]
