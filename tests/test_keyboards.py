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


def test_player_menu_buttons():
    """Клавиатура игрока должна показывать нужные кнопки в зависимости от состояния."""

    without_team = player_menu_kb(has_team=False, can_press=False)
    assert without_team.inline_keyboard[0][0].callback_data == PLAYER_REGISTER_CB
    assert "🆕" in without_team.inline_keyboard[0][0].text

    with_team_wait = player_menu_kb(has_team=True, can_press=False)
    assert with_team_wait.inline_keyboard[0][0].callback_data == PLAYER_BUZZER_CB
    assert "🔕" in with_team_wait.inline_keyboard[0][0].text

    with_team_question = player_menu_kb(has_team=True, can_press=True)
    assert "🛎️" in with_team_question.inline_keyboard[0][0].text


def test_admin_panel_states():
    """Панель админа подбирает кнопки в зависимости от статуса игры."""

    idle = admin_panel_kb("idle").inline_keyboard
    assert idle[0][0].callback_data == ADMIN_START_GAME_CB

    running = admin_panel_kb("running").inline_keyboard
    callbacks = {btn.callback_data for row in running for btn in row}
    assert {ADMIN_START_QUESTION_CB, ADMIN_SHOW_SCORES_CB, ADMIN_FINISH_GAME_CB}.issubset(callbacks)


def test_admin_answer_keyboard():
    """Клавиатура отметки ответа содержит expected callback-data."""

    kb = admin_answer_kb(42).inline_keyboard
    callbacks = [btn.callback_data for btn in kb[0]]
    assert callbacks == [f"{ADMIN_CORRECT_PREFIX}42", ADMIN_WRONG_CB]
