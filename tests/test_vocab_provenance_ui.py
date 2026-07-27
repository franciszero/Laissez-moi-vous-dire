from pathlib import Path
import json
import shutil

import store
from streamlit.testing.v1 import AppTest


def test_l31_provenance_is_available_before_answer_without_revealing_answer_panel(tmp_path):
    db_path = Path("dictation.db")
    backup_path = tmp_path / "dictation.db.bak"
    if db_path.exists():
        shutil.copy2(db_path, backup_path)

    try:
        at = AppTest.from_file("app.py", default_timeout=10).run()
        assert not at.exception
        at.selectbox(key="mode").set_value("听法语 → 敲法语").run()

        word_id = store.get_ids_for_lemmas(["une assiette"])[0]
        word = {"id": word_id, "text": "une assiette"}
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
        provenance_expander = next(
            item for item in at.expander if item.label == "📚 为什么收录这个词"
        )
        assert provenance_expander.proto.expanded is True
        rendered = "\n".join(item.value for item in at.markdown)
        assert "L31 · 阅读 Test 5 · 第 8 题" in rendered
        assert "纠正把 `plat` 理解成盘子的错误" in rendered
        assert "对比辨析" in rendered
        assert "32:30-35:30 · 50" in rendered
        assert not any(item.value.startswith("答案：") for item in at.info)

        next(button for button in at.button if button.label == "显示答案").click().run()

        assert not at.exception
        assert [item.label for item in at.expander].count("📚 为什么收录这个词") == 1
        assert any(item.value.startswith("答案：") for item in at.info)
    finally:
        if backup_path.exists():
            shutil.copy2(backup_path, db_path)
        elif db_path.exists():
            db_path.unlink()


def test_every_l31_word_has_structured_provenance():
    rows = json.loads(Path("../L31/vocab.json").read_text("utf-8"))

    assert len(rows) == 117
    assert all(row.get("provenance") for row in rows)
