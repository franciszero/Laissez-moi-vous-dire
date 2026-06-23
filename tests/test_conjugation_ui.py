import shutil
from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_conjugation_view_enters_and_renders_grid(tmp_path):
    db = Path("dictation.db")
    bak = tmp_path / "db.bak"
    if db.exists():
        shutil.copy2(db, bak)
    try:
        at = AppTest.from_file("app.py", default_timeout=10).run()
        assert not at.exception
        at.selectbox(key="sel_lesson").set_value("L22").run()
        next(b for b in at.button if b.label.startswith("🔠 动词变位")).click().run()
        assert not at.exception
        assert "🔠 动词变位" in [s.value for s in at.subheader]
        md = " ".join(m.value for m in at.markdown)
        assert "finir" in md                 # 第一张卡（conjugation.json 顺序）
        assert "直陈式现在时" in md            # 时态网格渲染出来了
        # 退出回到词表，无异常
        next(b for b in at.button if b.label == "↩︎ 退出变位").click().run()
        assert not at.exception
        assert "🔠 动词变位" not in [s.value for s in at.subheader]
    finally:
        if bak.exists():
            shutil.copy2(bak, db)
        elif db.exists():
            db.unlink()
