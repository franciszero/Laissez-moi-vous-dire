from pathlib import Path
import shutil

import manifest
from streamlit.testing.v1 import AppTest


def test_l21_checkpoint_navigation_has_list_and_prev_next(tmp_path):
    db_path = Path("dictation.db")
    backup_path = tmp_path / "dictation.db.bak"
    if db_path.exists():
        shutil.copy2(db_path, backup_path)

    try:
        expected_count = len(manifest.checkpoints(manifest.load("../L21/manifest.json")))

        at = AppTest.from_file("app.py", default_timeout=10)
        at.run()
        assert not at.exception

        at.selectbox(key="sel_lesson").set_value("L21").run()
        assert not at.exception

        button_label = f"📝 知识点（{expected_count}）"
        knowledge_button = next((b for b in at.button if b.label == button_label), None)
        assert knowledge_button is not None

        knowledge_button.click().run()
        assert not at.exception
        assert f"📝 知识点 1/{expected_count}" in [s.value for s in at.subheader]
        assert any("点按钮跳转" in c.value for c in at.caption)

        second_list_button = next((b for b in at.button if b.label.startswith("2. ")), None)
        assert second_list_button is not None
        second_list_button.click().run()
        assert not at.exception
        assert f"📝 知识点 2/{expected_count}" in [s.value for s in at.subheader]

        first_list_button = next((b for b in at.button if b.label.startswith("1. ")), None)
        assert first_list_button is not None
        first_list_button.click().run()
        assert not at.exception
        assert f"📝 知识点 1/{expected_count}" in [s.value for s in at.subheader]

        next_buttons = [b for b in at.button if b.label == "下一个 →" and not b.disabled]
        assert next_buttons
        next_buttons[0].click().run()
        assert not at.exception
        assert f"📝 知识点 2/{expected_count}" in [s.value for s in at.subheader]

        prev_buttons = [b for b in at.button if b.label == "← 上一个" and not b.disabled]
        assert prev_buttons
        prev_buttons[0].click().run()
        assert not at.exception
        assert f"📝 知识点 1/{expected_count}" in [s.value for s in at.subheader]
    finally:
        if backup_path.exists():
            shutil.copy2(backup_path, db_path)
        elif db_path.exists():
            db_path.unlink()
