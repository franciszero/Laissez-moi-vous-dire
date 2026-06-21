from pathlib import Path
import shutil

import manifest
from streamlit.testing.v1 import AppTest


def _has_answer(at: AppTest) -> bool:
    return any(m.value == "**📖 答案**" for m in at.markdown)


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
        initial_table_key = at.dataframe[0].key
        assert not [b for b in at.button if "跳到" in (b.label or "")]

        # 「显示答案」开关存在且可切换（给表加「答案」列），不抛异常
        show_answer = next((c for c in at.checkbox if c.label == "显示答案"), None)
        assert show_answer is not None
        show_answer.set_value(True).run()
        assert not at.exception
        assert len(at.dataframe) >= 1

        # 上方「下一个」用于做题导航：换卡并隐藏答案
        reveal = next((b for b in at.button if b.label == "👁 揭示答案"), None)
        assert reveal is not None
        reveal.click().run()
        assert not at.exception
        assert _has_answer(at)

        top_next = next((b for b in at.button if b.key == "cp_next_top"), None)
        assert top_next is not None and not top_next.disabled
        top_next.click().run()
        assert not at.exception
        assert f"📝 知识点 2/{expected_count}" in [s.value for s in at.subheader]
        # AppTest 不能模拟 dataframe 点行；key 随当前卡变化可以清掉旧选择态，
        # 避免用户用按钮翻页后再次点表格时被上一条 selection 卡住。
        assert at.dataframe[0].key != initial_table_key
        assert not _has_answer(at)

        # 上方「上一个」仍可导航
        prev_buttons = [b for b in at.button if b.label == "← 上一个" and not b.disabled]
        assert prev_buttons
        prev_buttons[0].click().run()
        assert not at.exception
        assert f"📝 知识点 1/{expected_count}" in [s.value for s in at.subheader]

        # 自评卡：揭示答案后用「我对」推进；不再有冗余的底部「下一个」
        reveal = next((b for b in at.button if b.label == "👁 揭示答案"), None)
        assert reveal is not None
        reveal.click().run()
        assert not at.exception
        assert _has_answer(at)
        assert not [b for b in at.button if b.key == "cp_next_self"]  # 冗余按钮已删

        graded_next = next((b for b in at.button if b.label == "✅ 我对"), None)
        assert graded_next is not None
        graded_next.click().run()
        assert not at.exception
        assert f"📝 知识点 2/{expected_count}" in [s.value for s in at.subheader]
    finally:
        if backup_path.exists():
            shutil.copy2(backup_path, db_path)
        elif db_path.exists():
            db_path.unlink()


def test_l22_future_tense_group_is_contiguous_in_native_table(tmp_path):
    db_path = Path("dictation.db")
    backup_path = tmp_path / "dictation.db.bak"
    if db_path.exists():
        shutil.copy2(db_path, backup_path)

    try:
        data = manifest.load("../L22/manifest.json")
        cards = manifest.checkpoints(data)
        expected_count = len(cards)
        group_count = sum(c.get("study_group") == "future-tense-system" for c in cards)

        at = AppTest.from_file("app.py", default_timeout=10)
        at.run()
        assert not at.exception

        at.selectbox(key="sel_lesson").set_value("L22").run()
        assert not at.exception
        knowledge_button = next(
            (b for b in at.button if b.label == f"📝 知识点（{expected_count}）"), None
        )
        assert knowledge_button is not None

        knowledge_button.click().run()
        assert not at.exception
        assert f"📝 知识点 1/{expected_count}" in [s.value for s in at.subheader]
        assert at.dataframe

        table = at.dataframe[0].value
        assert list(table["类别"].iloc[:group_count]) == ["时态变位系统"] * group_count
        assert any("构成 01/22" in title for title in table["知识点"].iloc[:group_count])
        assert any("词根 09/09" in title for title in table["知识点"].iloc[:group_count])
        assert any("辨析 07/07" in title for title in table["知识点"].iloc[:group_count])
        assert table["类别"].iloc[group_count] != "时态变位系统"
    finally:
        if backup_path.exists():
            shutil.copy2(backup_path, db_path)
        elif db_path.exists():
            db_path.unlink()
