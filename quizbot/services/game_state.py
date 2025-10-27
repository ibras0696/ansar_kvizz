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


def get_state(chat_id: int) -> GameState:
    """
    Возвращает состояние игры для конкретного чата.

    :param chat_id: Идентификатор чата.
    :return: Объект GameState.
    """
    if chat_id not in STATE:
        STATE[chat_id] = GameState()
    return STATE[chat_id]


async def reset_round(chat_id: int) -> None:
    """
    Очищает очередь команд в раунде.

    :param chat_id: Идентификатор чата.
    :return: None
    """
    state = get_state(chat_id)
    async with state.lock:
        state.queue.clear()
