from aiogram import F, Router
from aiogram.types import CallbackQuery

from quizbot.db import SessionLocal
from quizbot.keyboards import BUZZER_CB
from quizbot.services.game_service import get_order, press_buzzer
from quizbot.utils import head_and_tail

router = Router()


@router.callback_query(F.data == BUZZER_CB)
async def on_buzzer(callback: CallbackQuery) -> None:
    """
    Обрабатывает нажатие кнопки «БАЗЗЕР» и объявляет очередь.

    :param callback: CallbackQuery от Telegram.
    :return: None
    """
    chat = callback.message.chat  # type: ignore[attr-defined]
    user_id = callback.from_user.id

    async with SessionLocal() as session:
        message, position = await press_buzzer(session, chat.id, user_id)

        await callback.answer(message, show_alert=False)

        if position == 1:
            order = await get_order(session, chat.id)
            head, tail = head_and_tail(order)
            await callback.message.answer(f"Отвечает: {head}\nДалее по очереди: {tail}")
