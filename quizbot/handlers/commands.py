from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from quizbot.config import settings
from quizbot.db import SessionLocal
from quizbot.keyboards import admin_panel_kb, player_menu_kb
from quizbot.services import registration_state
from quizbot.services.game_service import (
    create_game,
    ensure_participants,
    get_active_game,
    get_or_create_player,
    get_player_team,
    register_team,
)

router = Router()


def _status_label(status: str | None) -> str:
    mapping = {
        "idle": "подготовка",
        "running": "идёт игра",
        "question": "идёт вопрос",
        "finished": "игра завершена",
    }
    return mapping.get(status or "", "нет активной игры")


def _is_admin(user_id: int) -> bool:
    """
    Проверяет, является ли пользователь администратором.

    :param user_id: Telegram ID пользователя.
    :return: True, если пользователь может управлять игрой.
    """

    return user_id in settings.default_admin_ids


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """
    Обрабатывает команду /start и показывает актуальное меню.

    :param message: Входящее сообщение от пользователя.
    :return: None
    """

    if not message.from_user:
        return

    user = message.from_user
    async with SessionLocal() as session:
        player = await get_or_create_player(
            session,
            tg_user_id=user.id,
            username=user.username,
            full_name=" ".join(filter(None, [user.first_name, user.last_name])),
        )
        game = await get_active_game(session)

        if _is_admin(user.id):
            if not game:
                game = await create_game(session, owner_user_id=user.id)
            elif game.owner_user_id != user.id:
                game.owner_user_id = user.id

            await session.commit()
            status_text = _status_label(game.status)
            await message.answer(
                "Привет, ведущий! 🎙️\n"
                f"Текущий статус: <b>{status_text}</b>\n"
                "Используй кнопки ниже, чтобы управлять раундом.",
                reply_markup=admin_panel_kb(game.status),
            )
            return

        team = await get_player_team(session, player)
        status_text = _status_label(game.status if game else None)
        can_press = bool(game and game.status == "question" and team)

        await session.commit()
        await message.answer(
            "Привет! 🔔 Это бот «БАЗЗЕР».\n"
            f"Текущий статус: <b>{status_text}</b>\n"
            "Нажимай кнопки под сообщением, чтобы зарегистрировать команду и не пропустить сигнал ведущего.",
            reply_markup=player_menu_kb(has_team=team is not None, can_press=can_press),
        )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """
    Выводит краткую справку по возможностям бота.

    :param message: Сообщение пользователя.
    :return: None
    """

    await message.answer(
        "ℹ️ <b>Как всё устроено:</b>\n"
        "— Ведущий запускает раунды через панель.\n"
        "— Игроки регистрируют команды и жмут «БАЗЗЕР» по сигналу.\n"
        "— Бот фиксирует очередь и считает очки до финала."
    )


@router.message()
async def handle_registration_input(message: Message) -> None:
    """
    Обрабатывает текстовые сообщения, ожидаемые после запроса регистрации команды.

    :param message: Входящее сообщение.
    :return: None
    """

    if not message.from_user or not message.text:
        return

    user_id = message.from_user.id
    if not registration_state.is_pending(user_id):
        return

    async with SessionLocal() as session:
        player = await get_or_create_player(
            session,
            tg_user_id=user_id,
            username=message.from_user.username,
            full_name=" ".join(filter(None, [message.from_user.first_name, message.from_user.last_name])),
        )

        try:
            team = await register_team(session, player, message.text)
        except ValueError as exc:
            await session.rollback()
            await message.answer(f"⚠️ {exc}")
            return

        game = await get_active_game(session)
        if game:
            await ensure_participants(session, game)
        await session.commit()

    registration_state.clear(user_id)
    await message.answer(
        f"Готово! 🎉 Ты в команде «{team.name}». Нажми /start, чтобы увидеть обновлённое меню."
    )
