from __future__ import annotations

from typing import Dict


PENDING_REGISTRATION: Dict[int, bool] = {}


def request_name(user_id: int) -> None:
    """
    Помечает пользователя, для которого ожидается ввод названия команды.

    :param user_id: Telegram ID пользователя.
    :return: None
    """

    PENDING_REGISTRATION[user_id] = True


def is_pending(user_id: int) -> bool:
    """
    Проверяет, ожидается ли от пользователя название команды.

    :param user_id: Telegram ID пользователя.
    :return: True, если нужно обработать следующее сообщение как название.
    """

    return PENDING_REGISTRATION.get(user_id, False)


def clear(user_id: int) -> None:
    """
    Сбрасывает ожидание ввода названия команды.

    :param user_id: Telegram ID пользователя.
    :return: None
    """

    PENDING_REGISTRATION.pop(user_id, None)
