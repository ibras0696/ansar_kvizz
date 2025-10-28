from quizbot.config import Settings


def test_settings_parse_admin_ids():
    """
    Проверяет разбор CSV-списка идентификаторов админов.

    :return: None
    """
    settings = Settings(
        BOT_TOKEN="token",
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        DEFAULT_ADMIN_IDS="1,  2,3",
        LOG_LEVEL="INFO",
    )
    assert settings.default_admin_ids == [1, 2, 3]


def test_settings_accepts_list():
    """
    Убеждается, что список идентификаторов используется как есть.

    :return: None
    """
    settings = Settings(
        BOT_TOKEN="token",
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        DEFAULT_ADMIN_IDS=[7, 8],
        LOG_LEVEL="INFO",
    )
    assert settings.default_admin_ids == [7, 8]
