import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from loguru import logger

from quizbot.config import settings
from quizbot.db import init_db
from quizbot.handlers import callbacks, commands


def setup_logging() -> None:
    """
    Настраивает loguru и уровень логирования aiogram.

    :return: None
    """
    logging.getLogger("aiogram").setLevel(settings.log_level)
    logger.remove()
    logger.add(
        sink=sys.stdout,
        level=settings.log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    )


async def main_async() -> None:
    """
    Инициализирует ресурсы и запускает polling.

    :return: None
    """
    setup_logging()
    try:
        import uvloop

        uvloop.install()
    except ImportError:
        logger.debug("uvloop not installed; using default event loop.")

    await init_db()

    dispatcher = Dispatcher()
    dispatcher.include_router(commands.router)
    dispatcher.include_router(callbacks.router)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    logger.info("Starting polling...")
    await dispatcher.start_polling(bot)


def main() -> None:
    """
    Точка входа приложения (обёртка для asyncio.run).

    :return: None
    """
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
