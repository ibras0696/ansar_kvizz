from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

PLAYER_REGISTER_CB = "player_register"
PLAYER_BUZZER_CB = "player_buzzer"

ADMIN_START_GAME_CB = "admin_start_game"
ADMIN_START_QUESTION_CB = "admin_start_question"
ADMIN_FINISH_GAME_CB = "admin_finish_game"
ADMIN_SHOW_SCORES_CB = "admin_show_scores"
ADMIN_CORRECT_PREFIX = "admin_correct:"
ADMIN_WRONG_CB = "admin_wrong"


def player_menu_kb(has_team: bool, can_press: bool) -> InlineKeyboardMarkup:
    """Формирует клавиатуру игрока."""

    rows: list[list[InlineKeyboardButton]] = []
    if not has_team:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🆕 Зарегистрировать команду",
                    callback_data=PLAYER_REGISTER_CB,
                )
            ]
        )
    if has_team:
        text = "🛎️ Нажать БАЗЗЕР" if can_press else "🔕 БАЗЗЕР недоступен"
        rows.append([InlineKeyboardButton(text=text, callback_data=PLAYER_BUZZER_CB)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_panel_kb(status: str) -> InlineKeyboardMarkup:
    """
    Возвращает клавиатуру для администратора с управлением игрой.

    :param status: Текущий статус игры.
    :return: InlineKeyboardMarkup.
    """

    rows: list[list[InlineKeyboardButton]] = []
    if status in {"idle", "finished"}:
        rows.append([InlineKeyboardButton(text="🚀 Запустить игру", callback_data=ADMIN_START_GAME_CB)])
    else:
        rows.append([InlineKeyboardButton(text="❓ Запустить вопрос", callback_data=ADMIN_START_QUESTION_CB)])
        rows.append([InlineKeyboardButton(text="📊 Таблица очков", callback_data=ADMIN_SHOW_SCORES_CB)])
        rows.append([InlineKeyboardButton(text="🛑 Завершить игру", callback_data=ADMIN_FINISH_GAME_CB)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_answer_kb(team_id: int) -> InlineKeyboardMarkup:
    """
    Клавиатура администратора для отметки ответа команды.

    :param team_id: Идентификатор команды.
    :return: InlineKeyboardMarkup.
    """

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Верно",
                    callback_data=f"{ADMIN_CORRECT_PREFIX}{team_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Неверно",
                    callback_data=ADMIN_WRONG_CB,
                ),
            ]
        ]
    )
