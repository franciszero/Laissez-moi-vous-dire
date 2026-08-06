"""预约制作单词卡：系统词典释义不够用时，攒一张高质量 Anki 卡的意愿。

这里只测「意愿被记住、可撤销、在侧栏看得见」——生成卡片是课后另一条链路。
"""
from pathlib import Path
import shutil

import store
from streamlit.testing.v1 import AppTest


def test_requested_word_shows_in_sidebar_and_can_be_cancelled(tmp_path):
    db_path = Path("dictation.db")
    backup_path = tmp_path / "dictation.db.bak"
    if db_path.exists():
        shutil.copy2(db_path, backup_path)

    try:
        lemma = "une assiette"
        assert store.get_ids_for_lemmas([lemma]), "词库里没有这个词，测试前提不成立"
        store.set_card_requested(lemma, True)

        at = AppTest.from_file("app.py", default_timeout=10).run()
        assert not at.exception

        expander = next(
            item for item in at.expander if item.label.startswith("📌 已预约制卡（")
        )
        assert expander.label == "📌 已预约制卡（1）"
        assert any(item.value.startswith(lemma) for item in at.markdown)

        word_id = store.get_ids_for_lemmas([lemma])[0]
        next(b for b in at.button if b.key == f"unreq_side_{word_id}").click().run()

        assert not at.exception
        assert store.is_card_requested(lemma) is False
        assert next(
            item for item in at.expander if item.label.startswith("📌 已预约制卡（")
        ).label == "📌 已预约制卡（0）"
    finally:
        if backup_path.exists():
            shutil.copy2(backup_path, db_path)
        elif db_path.exists():
            db_path.unlink()
