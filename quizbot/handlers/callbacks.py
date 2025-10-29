from __future__ import annotations

from contextlib import suppress

from aiogram import F, Router
from aiogram.types import CallbackQuery

from quizbot.config import settings
from quizbot.db import SessionLocal
from quizbot.keyboards import (
    ADMIN_CORRECT_PREFIX,
    ADMIN_FINISH_GAME_CB,
    ADMIN_SHOW_SCORES_CB,
    ADMIN_START_GAME_CB,
    ADMIN_START_QUESTION_CB,
    ADMIN_WRONG_CB,
    PLAYER_BUZZER_CB,
    PLAYER_REGISTER_CB,
    admin_answer_kb,
    admin_panel_kb,
    player_menu_kb,
)
from quizbot.services import registration_state
from quizbot.services.game_service import (
    award_score,
    create_game,
    finish_game,
    finish_question,
    get_active_game,
    get_all_players,
    get_or_create_player,
    get_player_team,
    get_players_without_team,
    get_scores,
    get_team_members,
    pop_queue,
    press_buzzer,
    start_game,
    start_question,
    teams_by_ids,
)

router = Router()


def _is_admin(user_id: int) -> bool:
    """
    Проверяет, является ли пользователь администратором.

    :param user_id: Telegram ID пользователя.
    :return: True, если пользователь админ.
    """

    return user_id in settings.default_admin_ids


async def _send_bulk(bot, players, text: str, reply_markup=None) -> None:
    """
    Рассылает сообщение списку игроков.

    :param bot: Экземпляр бота.
    :param players: Итерируемый список объектов Player.
    :param text: Текст сообщения.
    :param reply_markup: Клавиатура (опционально).
    :return: None
    """

    for player in players:
        try:
            await bot.send_message(player.tg_user_id, text, reply_markup=reply_markup)
        except Exception:
            continue


async def _notify_team(bot, session, team_id: int, text: str) -> None:
    """
    Отправляет сообщение всем участникам команды.

    :param bot: Экземпляр бота.
    :param session: Асинхронная сессия БД.
    :param team_id: Идентификатор команды.
    :param text: Текст уведомления.
    :return: None
    """

    members = await get_team_members(session, team_id)
    await _send_bulk(bot, members, text)


@router.callback_query(F.data == PLAYER_REGISTER_CB)
async def on_player_register(callback: CallbackQuery) -> None:
    """
    Запускает процесс регистрации команды для пользователя.

    :param callback: CallbackQuery от Telegram.
    :return: None
    """

    user = callback.from_user
    if not user:
        return

    registration_state.request_name(user.id)
    if callback.message:
        await callback.message.answer("Введи название команды одним сообщением 👇")
    await callback.answer("Жду название команды", show_alert=False)


@router.callback_query(F.data == PLAYER_BUZZER_CB)
async def on_player_buzzer(callback: CallbackQuery) -> None:
    """
    Обрабатывает нажатие «БАЗЗЕР» обычным игроком.

    :param callback: CallbackQuery от Telegram.
    :return: None
    """

    user = callback.from_user
    if not user:
        return

    async with SessionLocal() as session:
        game = await get_active_game(session)
        if not game:
            await callback.answer("❗ Сейчас нет активной игры. Подожди сигнал ведущего.", show_alert=True)
            return

        player = await get_or_create_player(
            session,
            tg_user_id=user.id,
            username=user.username,
            full_name=" ".join(filter(None, [user.first_name, user.last_name])),
        )
        result = await press_buzzer(session, game, player)
        await session.commit()

    await callback.answer(result.message, show_alert=False)

    if result.position == 1 and result.team:
        await callback.bot.send_message(
            game.owner_user_id,
            f"🔥 Команда «{result.team.name}» жмёт первой! Отметь результат кнопками ниже.",
            reply_markup=admin_answer_kb(result.team.id),
        )
        async with SessionLocal() as session:
            await _notify_team(
                callback.bot,
                session,
                result.team.id,
                "Вы первые! 📣 Сообщите ведущему, что готовы отвечать.",
            )


@router.callback_query(F.data == ADMIN_START_GAME_CB)
async def on_admin_start_game(callback: CallbackQuery) -> None:
    """
    Запускает игру (только для админа).

    :param callback: CallbackQuery от Telegram.
    :return: None
    """

    user = callback.from_user
    if not user or not _is_admin(user.id):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return

    async with SessionLocal() as session:
        game = await get_active_game(session)
        if not game:
            game = await create_game(session, owner_user_id=user.id)
        else:
            game.owner_user_id = user.id

        await start_game(session, game)

        all_players = await get_all_players(session)
        without_team = {player.id for player in await get_players_without_team(session)}
        with_team = [player for player in all_players if player.id not in without_team]
        without_team_players = [player for player in all_players if player.id in without_team]

        await session.commit()

    await callback.answer("Игра запущена.")
    if callback.message:
        await callback.message.edit_text(
            "Игра запущена 🚀\nКак только будешь готов — нажми «Запустить вопрос».",
            reply_markup=admin_panel_kb("running"),
        )

    await _send_bulk(
        callback.bot,
        with_team,
        "Игра стартовала! ⚡ Совсем скоро будет первый вопрос.",
        reply_markup=player_menu_kb(has_team=True, can_press=False),
    )
    await _send_bulk(
        callback.bot,
        without_team_players,
        "Игра стартовала, но у тебя ещё нет команды. 🆕 Зарегистрируй её через кнопку в меню.",
        reply_markup=player_menu_kb(has_team=False, can_press=False),
    )


@router.callback_query(F.data == ADMIN_START_QUESTION_CB)
async def on_admin_start_question(callback: CallbackQuery) -> None:
    """
    Стартует новый вопрос (очередь и нажимания).

    :param callback: CallbackQuery от Telegram.
    :return: None
    """

    user = callback.from_user
    if not user or not _is_admin(user.id):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return

    async with SessionLocal() as session:
        game = await get_active_game(session)
        if not game or game.status == "finished":
            await callback.answer("Нет активной игры.", show_alert=True)
            return

        await start_question(session, game)

        players = await get_all_players(session)
        without_team_ids = {p.id for p in await get_players_without_team(session)}
        ready_players = [p for p in players if p.id not in without_team_ids]

        await session.commit()

    await callback.answer("Вопрос запущен.")
    if callback.message:
        await callback.message.edit_text(
            "Вопрос активирован ❓\nЖду нажатий на «БАЗЗЕР».",
            reply_markup=admin_panel_kb("question"),
        )

    await _send_bulk(
        callback.bot,
        ready_players,
        "❓ Новый вопрос! Кто первый нажмёт «БАЗЗЕР», тот отвечает.",
        reply_markup=player_menu_kb(has_team=True, can_press=True),
    )


@router.callback_query(F.data == ADMIN_FINISH_GAME_CB)
async def on_admin_finish_game(callback: CallbackQuery) -> None:
    """
    Завершает игру и рассылает итог.

    :param callback: CallbackQuery от Telegram.
    :return: None
    """

    user = callback.from_user
    if not user or not _is_admin(user.id):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return

    async with SessionLocal() as session:
        game = await get_active_game(session)
        if not game:
            await callback.answer("Игра уже завершена.", show_alert=True)
            return

        await finish_game(session, game)
        scores = await get_scores(session, game)
        players = await get_all_players(session)
        await session.commit()

    await callback.answer("Игра завершена.")
    if callback.message:
        await callback.message.edit_text(
            "Игра завершена 🎉 Спасибо за раунд!", reply_markup=admin_panel_kb("finished")
        )

    table = "\n".join(
        f"{idx+1}. {team} — {score}" for idx, (team, score) in enumerate(scores)
    ) or "Таблица пустая."
    await callback.bot.send_message(user.id, f"🏁 Итоги игры:\n{table}")
    await _send_bulk(
        callback.bot,
        players,
        f"🏁 Игра завершена! Итоги:\n{table}",
    )


@router.callback_query(F.data == ADMIN_SHOW_SCORES_CB)
async def on_admin_show_scores(callback: CallbackQuery) -> None:
    """
    Показывает текущую таблицу очков.

    :param callback: CallbackQuery от Telegram.
    :return: None
    """

    user = callback.from_user
    if not user or not _is_admin(user.id):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return

    async with SessionLocal() as session:
        game = await get_active_game(session)
        if not game:
            await callback.answer("Нет активной игры.", show_alert=True)
            return
        scores = await get_scores(session, game)

    table = "\n".join(
        f"{idx+1}. {team} — {score}" for idx, (team, score) in enumerate(scores)
    ) or "Пока нет очков."
    await callback.answer("Показаны актуальные очки.")
    await callback.bot.send_message(user.id, f"📊 Текущие очки:\n{table}")


@router.callback_query(F.data.startswith(ADMIN_CORRECT_PREFIX))
async def on_admin_correct(callback: CallbackQuery) -> None:
    """
    Обрабатывает отметку «верно» от ведущего.

    :param callback: CallbackQuery от Telegram.
    :return: None
    """

    user = callback.from_user
    if not user or not _is_admin(user.id):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return

    try:
        team_id = int(callback.data.split(":", 1)[1])
    except (ValueError, AttributeError, IndexError):
        await callback.answer("Некорректные данные.", show_alert=True)
        return

    async with SessionLocal() as session:
        game = await get_active_game(session)
        if not game:
            await callback.answer("Нет активной игры.", show_alert=True)
            return

        removed_team_id, queue = await pop_queue(game)
        await award_score(session, game, team_id)
        await finish_question(session, game)
        scores = await get_scores(session, game)
        await session.commit()

    await callback.answer("Баллы начислены.")
    table = "\n".join(
        f"{idx+1}. {team} — {score}" for idx, (team, score) in enumerate(scores)
    ) or "Пока пусто."
    with suppress(Exception):
        if callback.message:
            await callback.message.delete()
    await callback.bot.send_message(
        user.id,
        f"📊 Очки обновлены:\n{table}",
        reply_markup=admin_panel_kb("running"),
    )
    async with SessionLocal() as session:
        await _notify_team(
            callback.bot,
            session,
            team_id,
            "✅ Ответ засчитан! Команда получила балл.",
        )


@router.callback_query(F.data == ADMIN_WRONG_CB)
async def on_admin_wrong(callback: CallbackQuery) -> None:
    """
    Обрабатывает отметку «неверно» и переходит к следующему.

    :param callback: CallbackQuery от Telegram.
    :return: None
    """

    user = callback.from_user
    if not user or not _is_admin(user.id):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return

    async with SessionLocal() as session:
        game = await get_active_game(session)
        if not game:
            await callback.answer("Нет активной игры.", show_alert=True)
            return

        removed_team_id, queue_after = await pop_queue(game)

        if not queue_after:
            await finish_question(session, game)
            team_map = {}
            if removed_team_id is not None:
                team_map = await teams_by_ids(session, [removed_team_id])
            await session.commit()
            await callback.answer("Очередь пуста. Запустите новый вопрос.")
            with suppress(Exception):
                if callback.message:
                    await callback.message.delete()
            if removed_team_id is not None:
                removed_team = team_map.get(removed_team_id)
                if removed_team:
                    await _notify_team(
                        callback.bot,
                        session,
                        removed_team_id,
                        "Ответ неверный. Подождите следующего вопроса.",
                    )
                    await callback.bot.send_message(
                        user.id,
                        f"Команда «{removed_team.name}» ответила неверно. Очередь закончилась.",
                        reply_markup=admin_panel_kb("running"),
                    )
                    return
            await callback.bot.send_message(
                user.id,
                "Очередь закончилась. Нажми «Запустить вопрос», чтобы начать заново.",
                reply_markup=admin_panel_kb("running"),
            )
            return

        await session.commit()

    await callback.answer("Переходим к следующей команде.")
    with suppress(Exception):
        if callback.message:
            await callback.message.delete()
    async with SessionLocal() as session:
        team_map = await teams_by_ids(session, [removed_team_id] + queue_after if removed_team_id else queue_after)
        if removed_team_id is not None:
            removed_team = team_map.get(removed_team_id)
            if removed_team:
                await _notify_team(
                    callback.bot, session, removed_team_id, "Ответ неверный. Ждите следующего вопроса."
                )

        next_team_id = queue_after[0]
        next_team = team_map.get(next_team_id)
        if next_team:
            await _notify_team(
                callback.bot, session, next_team_id, "Предыдущая команда ответила неверно. Вы на очереди!"
            )
            await callback.bot.send_message(
                user.id,
                f"Теперь отвечает команда «{next_team.name}».",
                reply_markup=admin_answer_kb(next_team_id),
            )
