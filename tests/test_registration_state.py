from quizbot.services import registration_state


def test_registration_state_flow():
    """Проверяет цикл запрос → проверка → сброс для регистрации команды."""

    user_id = 12345
    assert registration_state.is_pending(user_id) is False

    registration_state.request_name(user_id)
    assert registration_state.is_pending(user_id) is True

    registration_state.clear(user_id)
    assert registration_state.is_pending(user_id) is False
