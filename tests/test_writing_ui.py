from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

HARNESS = str(Path(__file__).parents[1] / "writing" / "tests" / "harness_app.py")


def _app() -> AppTest:
    at = AppTest.from_file(HARNESS, default_timeout=10)
    at.run()
    assert not at.exception
    return at


def _btn(at: AppTest, label: str):
    b = next((b for b in at.button if b.label == label), None)
    assert b is not None, f"找不到按钮: {label}"
    return b


def test_layout_has_editor_and_word_count():
    at = _app()
    assert at.text_area(key="wr_text_T1") is not None
    assert any("字数" in c.value for c in at.caption)


def test_draft_save_then_restore_caption():
    at = _app()
    at.text_area(key="wr_text_T1").set_value("Salut, je cherche un studio.").run()
    _btn(at, "💾 保存草稿").click().run()
    assert not at.exception
    assert any(c.value.startswith("草稿已存") for c in at.caption)


def test_exit_calls_on_exit():
    at = _app()
    _btn(at, "↩︎ 退出写作").click().run()
    assert at.session_state["harness_exited"] is True
