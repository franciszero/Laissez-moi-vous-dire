from pathlib import Path
import shutil

import store
from streamlit.testing.v1 import AppTest


def test_l31_provenance_is_hidden_until_answer_then_reconnects_to_source(tmp_path):
    db_path = Path("dictation.db")
    backup_path = tmp_path / "dictation.db.bak"
    if db_path.exists():
        shutil.copy2(db_path, backup_path)

    try:
        at = AppTest.from_file("app.py", default_timeout=10).run()
        assert not at.exception
        at.selectbox(key="mode").set_value("听法语 → 敲法语").run()

        word_id = store.get_ids_for_lemmas(["se mettre à"])[0]
        word = {"id": word_id, "text": "se mettre à"}
        at.session_state.pool = [word_id]
        at.session_state.index = 1
        at.session_state.current_word = word
        at.session_state.round_total = 1
        at.session_state.round_lesson = "L31"
        at.session_state.round_label = "学习 · L31"
        at.session_state.show_answer = False
        at.session_state.feedback = None
        at.session_state.graded = False
        at.run()

        assert not at.exception
        assert "📚 为什么收录这个词" not in [item.label for item in at.expander]

        next(button for button in at.button if button.label == "显示答案").click().run()

        assert not at.exception
        assert "📚 为什么收录这个词" in [item.label for item in at.expander]
        rendered = "\n".join(item.value for item in at.markdown)
        assert "L31 · 阅读 Test 5 · 第 15 题 · 选项 D" in rendered
        assert "为解释前缀 re-" in rendered
        assert "对比辨析" in rendered
        assert "1157-1231" in rendered
        captions = "\n".join(item.value for item in at.caption)
        assert "不属于选项的完整表层词形" in captions
    finally:
        if backup_path.exists():
            shutil.copy2(backup_path, db_path)
        elif db_path.exists():
            db_path.unlink()
