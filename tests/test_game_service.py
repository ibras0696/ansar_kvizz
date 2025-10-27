import pytest
from sqlalchemy import select

from quizbot.models import Game, Team, TeamMember
from quizbot.services.game_service import (
    ensure_team_for_user,
    get_order,
    pop_next,
    press_buzzer,
    reset_round,
)
from quizbot.services.game_state import get_state


@pytest.mark.asyncio
async def test_press_buzzer_requires_running_game(session):
    message, position = await press_buzzer(session, chat_id=1, user_id=10)
    assert position is None
    assert message.startswith("Раунд ещё не начат")


@pytest.mark.asyncio
async def test_press_buzzer_queue_management(session):
    chat_id = 777
    # create running game and two teams
    alpha = Team(chat_id=chat_id, name="Alpha")
    beta = Team(chat_id=chat_id, name="Beta")
    game = Game(chat_id=chat_id, owner_user_id=1, status="running")
    session.add_all([alpha, beta, game])
    await session.flush()
    session.add_all(
        [
            TeamMember(chat_id=chat_id, team_id=alpha.id, tg_user_id=11),
            TeamMember(chat_id=chat_id, team_id=beta.id, tg_user_id=22),
        ]
    )
    await session.commit()

    # First press puts Alpha to head of queue
    msg1, pos1 = await press_buzzer(session, chat_id=chat_id, user_id=11)
    assert pos1 == 1
    assert msg1 == "Вы первые!"
    state = get_state(chat_id)
    assert state.queue == [alpha.id]

    # Duplicate press keeps position
    msg_dup, pos_dup = await press_buzzer(session, chat_id=chat_id, user_id=11)
    assert pos_dup == 1
    assert msg_dup == "Вы уже в очереди, ваша позиция: №1"
    assert state.queue == [alpha.id]

    # Second team joins queue
    msg2, pos2 = await press_buzzer(session, chat_id=chat_id, user_id=22)
    assert pos2 == 2
    assert msg2 == "Принято! Ваша позиция: №2"
    assert state.queue == [alpha.id, beta.id]

    # Order reflects queue
    names = await get_order(session, chat_id)
    assert names == ["Alpha", "Beta"]

    # pop_next removes head and returns remaining queue names
    remaining = await pop_next(session, chat_id)
    assert remaining == ["Beta"]

    # Next call clears queue completely
    remaining2 = await pop_next(session, chat_id)
    assert remaining2 == []

    # reset_round wipes queue
    state.queue = [alpha.id]
    await reset_round(chat_id)
    assert state.queue == []


@pytest.mark.asyncio
async def test_ensure_team_for_user_missing_and_found(session):
    chat_id = 555
    user_id = 42
    team = Team(chat_id=chat_id, name="Seekers")
    game = Game(chat_id=chat_id, owner_user_id=999, status="running")
    session.add_all([team, game])
    await session.flush()
    await session.commit()

    # No member yet
    found = await ensure_team_for_user(session, chat_id, user_id)
    assert found is None

    session.add(TeamMember(chat_id=chat_id, team_id=team.id, tg_user_id=user_id))
    await session.commit()

    found = await ensure_team_for_user(session, chat_id, user_id)
    assert found is not None
    assert found.id == team.id
