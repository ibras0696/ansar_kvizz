from typing import List, Tuple


def head_and_tail(names: List[str]) -> Tuple[str, str]:
    """
    Выделяет первую команду и строку с остальными.

    :param names: Список названий команд.
    :return: Кортеж из ведущей команды и форматированной строки оставшихся.
    """
    if not names:
        return ("—", "—")
    head = names[0]
    tail = ", ".join(names[1:]) if len(names) > 1 else "—"
    return (head, tail)
