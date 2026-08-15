from __future__ import annotations

from streamlit.testing.v1 import AppTest


def _run():
    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    return at


def _button(at, startswith):
    for b in at.button:
        if b.label.startswith(startswith):
            return b
    raise AssertionError(f"没找到 {startswith!r}：{[b.label for b in at.button]}")


def test_no_handoff_button_before_any_page_is_submitted():
    at = _run()
    _button(at, "⚡ 速过").click().run()
    assert not [b for b in at.button if b.label.startswith("把这")]


def test_handoff_starts_a_round_with_exactly_the_missed_words():
    at = _run()
    _button(at, "⚡ 速过").click().run()
    ids = at.session_state["scan_ids"][:2]
    at.session_state["scan_missed_last"] = ids
    at.run()
    _button(at, "把这").click().run()
    assert at.session_state["pool"] == ids
    # _leave_overlays 弹掉 scan_active，下一轮初始化块把它重建成 False（见 B2 卡）
    assert at.session_state["scan_active"] is False


def test_handoff_button_hidden_when_nothing_was_missed():
    at = _run()
    _button(at, "⚡ 速过").click().run()
    at.session_state["scan_missed_last"] = []
    at.run()
    assert not [b for b in at.button if b.label.startswith("把这")]
