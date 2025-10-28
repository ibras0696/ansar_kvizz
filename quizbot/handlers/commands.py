from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from quizbot.config import settings
from quizbot.db import SessionLocal
from quizbot.keyboards import buzzer_kb
from quizbot.models import Game, Team, TeamMember
from quizbot.services.game_service import get_order, pop_next, reset_round
from quizbot.services.game_state import STATE
from quizbot.utils import head_and_tail

router = Router()


async def _is_admin(message: Message, session: AsyncSession) -> bool:
    """
    Проверяет, является ли пользователь ведущим или системным админом.

    :param message: Исходное сообщение из Telegram.
    :param session: Асинхронная сессия БД.
    :return: True, если у пользователя есть права ведущего.
    """
    if message.from_user.id in settings.default_admin_ids:
        return True
    query = select(Game).where(Game.chat_id == message.chat.id, Game.status != "finished")
    game = await session.scalar(query)
    return bool(game and game.owner_user_id == message.from_user.id)


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """
    Показывает справку и кнопку «БАЗЗЕР» при старте.

    :param message: Сообщение пользователя.
    :return: None
    """
    await message.answer(
        (
            "Привет! Это бот для викторины.\n"
            "Команды:\n"
            "/register_team — зарегистрировать команду\n"
            "/new_game — создать игру (ведущий)\n"
            "/start_game — начать раунд (очистить очередь)\n"
            "/next_round — следующий вопрос (очистить очередь)\n"
            "/order — показать текущую очередь (ведущий)\n"
            "/correct — отметить правильный ответ\n"
            "/wrong — перейти к следующей команде\n"
            "/finish_game — завершить игру"
        ),
        reply_markup=buzzer_kb() if message.chat.type in {"group", "supergroup"} else None,
    )


@router.message(Command("register_team"))
async def cmd_register(message: Message) -> None:
    """
    Регистрирует команду и добавляет пользователя в участники.

    :param message: Сообщение команды с названием.
    :return: None
    """
    parts = message.text.split(maxsplit=1) if message.text else []
    if len(parts) < 2:
        await message.answer("Укажи название: /register_team &lt;название&gt;")
        return

    name = parts[1].strip()
    if not name:
        await message.answer("Название команды не может быть пустым.")
        return

    chat_id = message.chat.id
    user_id = message.from_user.id

    async with SessionLocal() as session:
        team = await session.scalar(
            select(Team).where(Team.chat_id == chat_id, Team.name == name)
        )
        if not team:
            team = Team(chat_id=chat_id, name=name)
            session.add(team)
            await session.flush()

        member = await session.scalar(
            select(TeamMember).where(
                TeamMember.chat_id == chat_id, TeamMember.tg_user_id == user_id
            )
        )
        if not member:
            session.add(TeamMember(chat_id=chat_id, team_id=team.id, tg_user_id=user_id))

        await session.commit()

    await message.answer(f"Ок! Ты в команде «{name}».", reply_markup=buzzer_kb())


@router.message(Command("new_game"))
async def cmd_new_game(message: Message) -> None:
    """
    Создаёт новую игру и назначает ведущего.

    :param message: Сообщение ведущего.
    :return: None
    """
    chat_id = message.chat.id
    user_id = message.from_user.id

    await reset_round(chat_id)
    async with SessionLocal() as session:
        existing = await session.scalar(select(Game).where(Game.chat_id == chat_id))
        if existing:
            existing.owner_user_id = user_id
            existing.status = "idle"
            existing.finished_at = None
        else:
            session.add(Game(chat_id=chat_id, owner_user_id=user_id, status="idle"))
        await session.commit()

    await message.answer("Игра создана. Ведущий назначен. Используй /start_game.")


@router.message(Command("start_game"))
async def cmd_start_game(message: Message) -> None:
    """
    Переводит игру в статус «running» и очищает очередь.

    :param message: Сообщение от ведущего.
    :return: None
    """
    async with SessionLocal() as session:
        if not await _is_admin(message, session):
            await message.answer("Только ведущий может начать игру.")
            return

        await reset_round(message.chat.id)
        await session.execute(
            update(Game)
            .where(Game.chat_id == message.chat.id, Game.status != "finished")
            .values(status="running")
        )
        await session.commit()

    await message.answer("Игра началась! Готовьтесь к вопросу.", reply_markup=buzzer_kb())


@router.message(Command("next_round"))
async def cmd_next_round(message: Message) -> None:
    """
    Сбрасывает очередь, чтобы перейти к следующему вопросу.

    :param message: Сообщение ведущего.
    :return: None
    """
    async with SessionLocal() as session:
        if not await _is_admin(message, session):
            await message.answer("Только ведущий.")
            return

        await reset_round(message.chat.id)
        await session.commit()

    await message.answer("Новый вопрос! Очередь сброшена.", reply_markup=buzzer_kb())


@router.message(Command("order"))
async def cmd_order(message: Message) -> None:
    """
    Показывает ведущему текущую очередь команд.

    :param message: Сообщение от ведущего.
    :return: None
    """
    async with SessionLocal() as session:
        if not await _is_admin(message, session):
            await message.answer("Только ведущий.")
            return

        names = await get_order(session, message.chat.id)

    if not names:
        await message.answer("Очередь пуста.")
        return

    listing = " → ".join(f"{idx + 1}) {name}" for idx, name in enumerate(names))
    await message.answer(f"Очередь: {listing}")


@router.message(Command("correct"))
async def cmd_correct(message: Message) -> None:
    """
    Отмечает правильный ответ и очищает очередь.

    :param message: Сообщение ведущего.
    :return: None
    """
    async with SessionLocal() as session:
        if not await _is_admin(message, session):
            await message.answer("Только ведущий.")
            return

        await reset_round(message.chat.id)
        await session.commit()

    await message.answer("Верно! Очередь очищена. Готовьтесь к следующему вопросу.")


@router.message(Command("wrong"))
async def cmd_wrong(message: Message) -> None:
    """
    Убирает текущую команду и объявляет следующую в очереди.

    :param message: Сообщение ведущего.
    :return: None
    """
    async with SessionLocal() as session:
        if not await _is_admin(message, session):
            await message.answer("Только ведущий.")
            return

        order = await pop_next(session, message.chat.id)
        await session.commit()

    if not order:
        await message.answer("Очередь пуста.")
        return

    head, tail = head_and_tail(order)
    await message.answer(f"Следующая команда отвечает: {head}\nДалее: {tail}")


@router.message(Command("finish_game"))
async def cmd_finish(message: Message) -> None:
    """
    Завершает игру и очищает in-memory состояние.

    :param message: Сообщение ведущего.
    :return: None
    """
    async with SessionLocal() as session:
        if not await _is_admin(message, session):
            await message.answer("Только ведущий.")
            return

        await reset_round(message.chat.id)
        await session.execute(
            update(Game)
            .where(Game.chat_id == message.chat.id, Game.status != "finished")
            .values(status="finished")
        )
        await session.commit()

    STATE.pop(message.chat.id, None)
    await message.answer("Игра завершена! Спасибо за участие.")
