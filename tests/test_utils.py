from quizbot.utils import head_and_tail


def test_head_and_tail_formats_queue():
    assert head_and_tail([]) == ("—", "—")
    assert head_and_tail(["Alpha"]) == ("Alpha", "—")
    assert head_and_tail(["Alpha", "Beta", "Gamma"]) == ("Alpha", "Beta, Gamma")
