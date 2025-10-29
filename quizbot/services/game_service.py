from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable, List, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from quizbot.models import Game, GameParticipant, Player, Team, TeamMember
from quizbot.services.game_state import get_state, reset_round as reset_round_state


@dataclass
class BuzzerResult:
    """
    Итог обработки нажатия «БАЗЗЕР».

    :ivar message: Текстовый ответ игроку.
    :ivar position: Позиция команды в очереди (None, если не встала).
    :ivar team: Команда игрока, если она добавлена в очередь.
    """

    message: str
    position: int | None
    team: Team | None


async def get_or_create_player(
    session: AsyncSession, tg_user_id: int, username: str | None, full_name: str | None
) -> Player:
    """
    Возвращает игрока или создаёт новую запись в таблице players.

    :param session: Асинхронная сессия БД.
    :param tg_user_id: Уникальный Telegram ID пользователя.
    :param username: Username пользователя.
    :param full_name: Полное имя (first_name + last_name).
    :return: Экземпляр Player.
    """

    player = await session.scalar(select(Player).where(Player.tg_user_id == tg_user_id))
    if player:
        # Обновим метаданные, если они изменились.
        updated = False
        if username and player.username != username:
            player.username = username
            updated = True
        if full_name and player.full_name != full_name:
            player.full_name = full_name
            updated = True
        if updated:
            await session.flush()
        return player

    player = Player(tg_user_id=tg_user_id, username=username, full_name=full_name)
    session.add(player)
    await session.flush()
    return player


async def get_player_team(session: AsyncSession, player: Player) -> Team | None:
    """
    Возвращает команду, в которой состоит игрок.

    :param session: Асинхронная сессия БД.
    :param player: Объект игрока.
    :return: Команда или None.
    """

    query = (
        select(Team)
        .join(TeamMember, TeamMember.team_id == Team.id)
        .where(TeamMember.player_id == player.id)
    )
    return await session.scalar(query)


async def register_team(session: AsyncSession, player: Player, team_name: str) -> Team:
    """
    Регистрирует игрока в команде. Создаёт новую, если её ещё нет.

    :param session: Асинхронная сессия БД.
    :param player: Объект игрока.
    :param team_name: Желаемое имя команды.
    :return: Команда, в которую добавлен игрок.
    :raises ValueError: Если пользователь уже состоит в другой команде.
    """

    existing_team = await get_player_team(session, player)
    if existing_team:
        raise ValueError("Игрок уже состоит в команде.")

    normalized = team_name.strip()
    if not normalized:
        raise ValueError("Название команды не может быть пустым.")

    existing_name = await session.scalar(select(Team).where(func.lower(Team.name) == normalized.lower()))
    if existing_name:
        raise ValueError("Команда с таким названием уже существует.")

    team = Team(name=normalized)
    session.add(team)
    await session.flush()

    session.add(TeamMember(team_id=team.id, player_id=player.id))
    await session.flush()
    return team


async def get_all_players(session: AsyncSession) -> Sequence[Player]:
    """
    Возвращает список всех пользователей, когда-либо писавших боту.

    :param session: Асинхронная сессия БД.
    :return: Список игроков.
    """

    return (await session.scalars(select(Player))).all()


async def get_players_without_team(session: AsyncSession) -> Sequence[Player]:
    """
    Возвращает пользователей, не состоящих ни в одной команде.

    :param session: Асинхронная сессия БД.
    :return: Список игроков без команды.
    """

    subquery = select(TeamMember.player_id)
    players = await session.scalars(
        select(Player).where(Player.id.notin_(subquery.scalar_subquery()))
    )
    return players.all()


async def get_team_members(session: AsyncSession, team_id: int) -> Sequence[Player]:
    """
    Возвращает список игроков команды.

    :param session: Асинхронная сессия БД.
    :param team_id: Идентификатор команды.
    :return: Список игроков.
    """

    return (
        await session.scalars(
            select(Player)
            .join(TeamMember, TeamMember.player_id == Player.id)
            .where(TeamMember.team_id == team_id)
        )
    ).all()


async def get_active_game(session: AsyncSession) -> Game | None:
    """
    Возвращает активную игру (любую, что не завершена).

    :param session: Асинхронная сессия БД.
    :return: Активная игра или None.
    """

    return await session.scalar(
        select(Game).where(Game.status != "finished").order_by(Game.created_at.desc())
    )


async def create_game(session: AsyncSession, owner_user_id: int) -> Game:
    """
    Создаёт новую игру в статусе idle.

    :param session: Асинхронная сессия БД.
    :param owner_user_id: Telegram ID администратора.
    :return: Созданная игра.
    """

    game = Game(owner_user_id=owner_user_id, status="idle")
    session.add(game)
    await session.flush()
    return game


async def ensure_participants(session: AsyncSession, game: Game) -> None:
    """
    Гарантирует наличие записей GameParticipant для всех команд.

    :param session: Асинхронная сессия БД.
    :param game: Текущая игра.
    :return: None
    """

    existing_pairs = set(
        await session.scalars(
            select(GameParticipant.team_id).where(GameParticipant.game_id == game.id)
        )
    )
    teams = (await session.scalars(select(Team))).all()
    for team in teams:
        if team.id not in existing_pairs:
            session.add(GameParticipant(game_id=game.id, team_id=team.id, score=0))
    await session.flush()


async def start_game(session: AsyncSession, game: Game) -> None:
    """
    Переводит игру в статус running и готовит участников.

    :param session: Асинхронная сессия БД.
    :param game: Игра для запуска.
    :return: None
    """

    game.status = "running"
    game.finished_at = None
    await ensure_participants(session, game)
    await session.flush()
    await reset_round_state(game.id)


async def start_question(session: AsyncSession, game: Game) -> None:
    """
    Переводит игру в статус question (ждём нажатий на «БАЗЗЕР»).

    :param session: Асинхронная сессия БД.
    :param game: Активная игра.
    :return: None
    """

    game.status = "question"
    await reset_round_state(game.id)
    await session.flush()


async def finish_question(session: AsyncSession, game: Game) -> None:
    """
    Возвращает игру в статус running (вопрос завершён).

    :param session: Асинхронная сессия БД.
    :param game: Активная игра.
    :return: None
    """

    game.status = "running"
    await reset_round_state(game.id)
    await session.flush()


async def finish_game(session: AsyncSession, game: Game) -> None:
    """
    Завершает игру.

    :param session: Асинхронная сессия БД.
    :param game: Игра для завершения.
    :return: None
    """

    game.status = "finished"
    game.finished_at = datetime.now(UTC)
    await reset_round_state(game.id)
    await session.flush()


async def press_buzzer(session: AsyncSession, game: Game, player: Player) -> BuzzerResult:
    """
    Обрабатывает нажатие кнопки «БАЗЗЕР» пользователем.

    :param session: Асинхронная сессия БД.
    :param game: Активная игра.
    :param player: Игрок, нажавший кнопку.
    :return: Результат с сообщением и позицией.
    """

    if game.status != "question":
        return BuzzerResult("❗ Сейчас нет активного вопроса. Ждите сигнал от ведущего.", None, None)

    team = await get_player_team(session, player)
    if not team:
        return BuzzerResult(
            "👥 Ты ещё без команды. Используй кнопку регистрации, чтобы участвовать.",
            None,
            None,
        )

    await ensure_participants(session, game)

    state = get_state(game.id)
    async with state.lock:
        if team.id in state.queue:
            position = state.queue.index(team.id) + 1
            return BuzzerResult(f"ℹ️ Ты уже в очереди, твой номер — №{position}.", position, team)
        state.queue.append(team.id)
        position = len(state.queue)

    if position == 1:
        return BuzzerResult("Вы первые! 🔥 Готовьтесь отвечать.", position, team)
    return BuzzerResult(f"Записал! Твоя позиция — №{position}.", position, team)


async def pop_queue(game: Game) -> tuple[int | None, list[int]]:
    """
    Убирает первую команду из очереди и возвращает обновлённый порядок.

    :param game: Активная игра.
    :return: Кортеж (удалённый team_id или None, текущая очередь).
    """

    state = get_state(game.id)
    async with state.lock:
        removed = state.queue.pop(0) if state.queue else None
        return removed, list(state.queue)


async def current_queue(game: Game) -> list[int]:
    """
    Возвращает копию текущей очереди.

    :param game: Активная игра.
    :return: Список team_id.
    """

    state = get_state(game.id)
    async with state.lock:
        return list(state.queue)


async def award_score(session: AsyncSession, game: Game, team_id: int, points: int = 1) -> None:
    """
    Начисляет очки команде в рамках игры.

    :param session: Асинхронная сессия БД.
    :param game: Активная игра.
    :param team_id: Идентификатор команды.
    :param points: Количество очков (по умолчанию 1).
    :return: None
    """

    participant = await session.scalar(
        select(GameParticipant).where(
            GameParticipant.game_id == game.id, GameParticipant.team_id == team_id
        )
    )
    if participant is None:
        participant = GameParticipant(game_id=game.id, team_id=team_id, score=0)
        session.add(participant)
        await session.flush()
    participant.score += points
    await session.flush()


async def get_scores(session: AsyncSession, game: Game) -> list[tuple[str, int]]:
    """
    Возвращает таблицу счёта для игры.

    :param session: Асинхронная сессия БД.
    :param game: Игра.
    :return: Список пар (название команды, счёт).
    """

    rows = (
        await session.execute(
            select(Team.name, GameParticipant.score)
            .join(Team, Team.id == GameParticipant.team_id)
            .where(GameParticipant.game_id == game.id)
            .order_by(GameParticipant.score.desc(), Team.name.asc())
        )
    ).all()
    return [(row[0], row[1]) for row in rows]


async def teams_by_ids(session: AsyncSession, team_ids: Iterable[int]) -> dict[int, Team]:
    """
    Возвращает словарь команда -> объект Team.

    :param session: Асинхронная сессия БД.
    :param team_ids: Список идентификаторов.
    :return: Словарь id -> Team.
    """

    ids = list(team_ids)
    if not ids:
        return {}
    teams = (await session.scalars(select(Team).where(Team.id.in_(ids)))).all()
    return {team.id: team for team in teams}
