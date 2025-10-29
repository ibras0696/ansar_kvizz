from __future__ import annotations

import pytest

from quizbot.services.game_service import (
    award_score,
    create_game,
    finish_question,
    get_active_game,
    get_or_create_player,
    get_player_team,
    get_scores,
    pop_queue,
    press_buzzer,
    register_team,
    start_game,
    start_question,
    finish_game,
    pop_queue,
)


@pytest.mark.asyncio
async def test_register_team_unique(session):
    """
    Убеждается, что игроку нельзя иметь две команды и имена уникальны.

    :param session: Асинхронная тестовая сессия.
    :return: None
    """

    player = await get_or_create_player(session, 100, "user", "Test User")
    team = await register_team(session, player, "Rockets")
    assert await get_player_team(session, player) == team

    with pytest.raises(ValueError):
        await register_team(session, player, "Another")

    other = await get_or_create_player(session, 101, "other", "Other User")
    with pytest.raises(ValueError):
        await register_team(session, other, "ROCKETS")


@pytest.mark.asyncio
async def test_press_buzzer_queue(session):
    """
    Проверяет, что «БАЗЗЕР» работает только во время вопроса и сохраняет очередь.

    :param session: Асинхронная тестовая сессия.
    :return: None
    """

    admin_id = 1
    player1 = await get_or_create_player(session, 201, "alpha", "Alpha Player")
    player2 = await get_or_create_player(session, 202, "beta", "Beta Player")
    team1 = await register_team(session, player1, "Alpha")
    team2 = await register_team(session, player2, "Beta")

    game = await create_game(session, owner_user_id=admin_id)
    await start_game(session, game)

    result_idle = await press_buzzer(session, game, player1)
    assert "нет активного вопроса" in result_idle.message

    await start_question(session, game)
    result_first = await press_buzzer(session, game, player1)
    assert result_first.position == 1
    assert result_first.team.id == team1.id

    result_second = await press_buzzer(session, game, player2)
    assert result_second.position == 2
    assert result_second.team.id == team2.id


@pytest.mark.asyncio
async def test_award_score_updates_table(session):
    """
    Проверяет начисление очков и закрытие вопроса.

    :param session: Асинхронная тестовая сессия.
    :return: None
    """

    admin_id = 1
    player = await get_or_create_player(session, 301, "captain", "Captain")
    team = await register_team(session, player, "Captains")

    game = await create_game(session, owner_user_id=admin_id)
    await start_game(session, game)
    await start_question(session, game)
    await press_buzzer(session, game, player)

    await award_score(session, game, team.id, points=2)
    await finish_question(session, game)
    scores = await get_scores(session, game)
    assert scores == [(team.name, 2)]

    active = await get_active_game(session)
    assert active is not None and active.status == "running"


@pytest.mark.asyncio
async def test_full_game_flow(session):
    """
    Имитация полного сценария игры: запуск, вопросы, очередь, начисление очков, завершение.

    :param session: Асинхронная тестовая сессия.
    :return: None
    """

    admin_id = 1
    # Три игрока и команды
    players = [
        await get_or_create_player(session, 401, "p1", "Player One"),
        await get_or_create_player(session, 402, "p2", "Player Two"),
        await get_or_create_player(session, 403, "p3", "Player Three"),
    ]
    teams = [
        await register_team(session, players[0], "Alpha"),
        await register_team(session, players[1], "Beta"),
        await register_team(session, players[2], "Gamma"),
    ]

    game = await create_game(session, owner_user_id=admin_id)
    await start_game(session, game)

    # Вопрос №1: Alpha первая, получает балл
    await start_question(session, game)
    res_alpha = await press_buzzer(session, game, players[0])
    assert res_alpha.position == 1
    res_beta = await press_buzzer(session, game, players[1])
    assert res_beta.position == 2
    await award_score(session, game, teams[0].id)
    await finish_question(session, game)
    scores = await get_scores(session, game)
    assert scores == [("Alpha", 1), ("Beta", 0), ("Gamma", 0)]

    # Вопрос №2: Beta нажимает первой, но отвечает неверно -> Gamma получает шанс
    await start_question(session, game)
    await press_buzzer(session, game, players[1])
    await press_buzzer(session, game, players[2])
    removed, queue_after = await pop_queue(game)
    assert removed == teams[1].id
    assert queue_after == [teams[2].id]
    await award_score(session, game, teams[2].id)
    await finish_question(session, game)

    # Завершение игры
    await finish_game(session, game)
    final_scores = dict(await get_scores(session, game))
    assert final_scores == {"Alpha": 1, "Beta": 0, "Gamma": 1}
