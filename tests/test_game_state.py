import pytest

from quizbot.services.game_state import STATE, get_state, reset_round


@pytest.mark.asyncio
async def test_game_state_queue_reset():
    """Состояние игры создаётся по требованию и очищается reset_round."""

    game_id = 777
    state = get_state(game_id)
    state.queue.extend([1, 2, 3])
    assert STATE[game_id].queue == [1, 2, 3]

    await reset_round(game_id)
    assert STATE[game_id].queue == []
