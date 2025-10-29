from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class GameState:
    """
    Хранит очередь команд и lock для синхронизации.

    :ivar queue: Порядок команд в текущем раунде.
    :ivar lock: Асинхронный замок для безопасных изменений.
    """
    queue: List[int] = field(default_factory=list)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


STATE: Dict[int, GameState] = {}


def get_state(game_id: int) -> GameState:
    """
    Возвращает состояние игры для конкретного идентификатора.

    :param game_id: Идентификатор игры.
    :return: Объект GameState.
    """
    if game_id not in STATE:
        STATE[game_id] = GameState()
    return STATE[game_id]


async def reset_round(game_id: int) -> None:
    """
    Очищает очередь команд для указанной игры.

    :param game_id: Идентификатор игры.
    :return: None
    """
    state = get_state(game_id)
    async with state.lock:
        state.queue.clear()
