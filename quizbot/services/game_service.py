from __future__ import annotations

from typing import List, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from quizbot.models import Game, Team, TeamMember
from quizbot.services.game_state import get_state, reset_round as reset_round_state


async def ensure_team_for_user(
    session: AsyncSession, chat_id: int, user_id: int
) -> Team | None:
    """
    Находит команду пользователя в рамках заданного чата.

    :param session: Асинхронная сессия БД.
    :param chat_id: Идентификатор чата.
    :param user_id: Telegram ID пользователя.
    :return: Команда или None, если пользователь ещё не состоит в команде.
    """
    query = (
        select(Team)
        .join(TeamMember, TeamMember.team_id == Team.id)
        .where(TeamMember.chat_id == chat_id, TeamMember.tg_user_id == user_id)
    )
    return await session.scalar(query)


async def _get_team_name(session: AsyncSession, team_id: int) -> str | None:
    """
    Возвращает название команды по её идентификатору.

    :param session: Асинхронная сессия БД.
    :param team_id: Идентификатор команды.
    :return: Название команды или None.
    """
    team = await session.scalar(select(Team).where(Team.id == team_id))
    return team.name if team else None


async def press_buzzer(
    session: AsyncSession, chat_id: int, user_id: int
) -> Tuple[str, int | None]:
    """
    Обрабатывает нажатие на кнопку «БАЗЗЕР».

    :param session: Асинхронная сессия БД.
    :param chat_id: Идентификатор чата.
    :param user_id: Telegram ID пользователя.
    :return: Сообщение для пользователя и позиция в очереди (если применимо).
    """
    game = await session.scalar(
        select(Game).where(Game.chat_id == chat_id, Game.status == "running")
    )
    if not game:
        return ("Раунд ещё не начат. Ведущий: /start_game", None)

    team = await ensure_team_for_user(session, chat_id, user_id)
    if not team:
        return ("Вы не в команде. Используйте /register_team <название>", None)

    state = get_state(chat_id)
    async with state.lock:
        if team.id in state.queue:
            position = state.queue.index(team.id) + 1
            return (f"Вы уже в очереди, ваша позиция: №{position}", position)
        state.queue.append(team.id)
        position = len(state.queue)
        if position == 1:
            return ("Вы первые!", position)
        return (f"Принято! Ваша позиция: №{position}", position)


async def get_order(session: AsyncSession, chat_id: int) -> List[str]:
    """
    Возвращает список названий команд в текущей очереди.

    :param session: Асинхронная сессия БД.
    :param chat_id: Идентификатор чата.
    :return: Имена команд по порядку.
    """
    state = get_state(chat_id)
    async with state.lock:
        queue_snapshot = list(state.queue)
    if not queue_snapshot:
        return []
    teams = (await session.scalars(select(Team).where(Team.id.in_(queue_snapshot)))).all()
    teams_by_id = {team.id: team for team in teams}
    return [teams_by_id[team_id].name for team_id in queue_snapshot if team_id in teams_by_id]


async def pop_next(session: AsyncSession, chat_id: int) -> List[str]:
    """
    Снимает команду с головы очереди и возвращает обновлённый порядок.

    :param session: Асинхронная сессия БД.
    :param chat_id: Идентификатор чата.
    :return: Список названий команд после удаления первой.
    """
    state = get_state(chat_id)
    async with state.lock:
        if state.queue:
            state.queue.pop(0)
        queue_snapshot = list(state.queue)

    if not queue_snapshot:
        return []

    teams = (await session.scalars(select(Team).where(Team.id.in_(queue_snapshot)))).all()
    teams_by_id = {team.id: team for team in teams}
    return [teams_by_id[team_id].name for team_id in queue_snapshot if team_id in teams_by_id]


async def reset_round(chat_id: int) -> None:
    """
    Сбрасывает очередь раунда (обёртка над state.reset_round).

    :param chat_id: Идентификатор чата.
    :return: None
    """
    await reset_round_state(chat_id)
