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

        # 侧栏「知识点表」是真·表格(st.dataframe)，不再是按钮列表
        assert len(at.dataframe) >= 1
        assert not [b for b in at.button if "跳到" in (b.label or "")]

        # 「显示答案」开关存在且可切换（给表加「答案」列），不抛异常
        show_answer = next((c for c in at.checkbox if c.label == "显示答案"), None)
        assert show_answer is not None
        show_answer.set_value(True).run()
        assert not at.exception
        assert len(at.dataframe) >= 1

        # 卡片视图的上一个/下一个仍可导航
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
