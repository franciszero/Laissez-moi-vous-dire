import shutil
from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_word_entry_leaves_card_overlay(tmp_path):
    """从「知识点」覆盖视图点「开始这一课」，应离开卡模式回到词练习（_leave_overlays）。"""
    db = Path("dictation.db")
    bak = tmp_path / "db.bak"
    if db.exists():
        shutil.copy2(db, bak)
    try:
        at = AppTest.from_file("app.py", default_timeout=10).run()
        at.selectbox(key="sel_lesson").set_value("L22").run()
        next(b for b in at.button if b.label.startswith("📝 知识点（")).click().run()
        assert at.session_state.cp_active is True
        next(b for b in at.button if b.label.startswith("开始这一课")).click().run()
        assert not at.exception
        assert at.session_state.cp_active is False        # 不再被卡模式遮挡
    finally:
        if bak.exists():
            shutil.copy2(bak, db)
        elif db.exists():
            db.unlink()
