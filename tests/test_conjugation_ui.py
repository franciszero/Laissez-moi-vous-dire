import shutil
from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_conjugation_card_renders_inside_knowledge_deck(tmp_path):
    """动词变位卡已并入「知识点」deck（D2）：进入知识点、跳到一张 conj 卡，应渲染变位网格。"""
    db = Path("dictation.db")
    bak = tmp_path / "db.bak"
    if db.exists():
        shutil.copy2(db, bak)
    try:
        at = AppTest.from_file("app.py", default_timeout=10).run()
        at.selectbox(key="sel_lesson").set_value("L22").run()
        next(b for b in at.button if b.label.startswith("📝 知识点（")).click().run()
        assert not at.exception
        cards = at.session_state.cp_cards
        idx = next(i for i, c in enumerate(cards) if c.get("kind") == "conj")
        at.session_state.cp_index = idx
        at.run()
        assert not at.exception
        md = " ".join(m.value for m in at.markdown)
        assert cards[idx]["verb"] in md          # 该动词标题
        assert "直陈式现在时" in md                # 变位网格渲染出来了
    finally:
        if bak.exists():
            shutil.copy2(bak, db)
        elif db.exists():
            db.unlink()
