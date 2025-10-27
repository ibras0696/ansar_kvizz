from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

BUZZER_CB = "buzzer_press"


def buzzer_kb() -> InlineKeyboardMarkup:
    """
    Возвращает инлайн-клавиатуру с кнопкой «БАЗЗЕР».

    :return: Объект InlineKeyboardMarkup.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="БАЗЗЕР 🛎️", callback_data=BUZZER_CB)]]
    )
