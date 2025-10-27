from quizbot.keyboards import BUZZER_CB, buzzer_kb


def test_buzzer_keyboard_layout():
    keyboard = buzzer_kb()
    assert keyboard.inline_keyboard
    button = keyboard.inline_keyboard[0][0]
    assert button.text.startswith("БАЗЗЕР")
    assert button.callback_data == BUZZER_CB
