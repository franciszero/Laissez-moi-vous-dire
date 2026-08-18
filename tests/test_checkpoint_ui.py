from pathlib import Path
import re
import shutil

import manifest
import vocab
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
        import json as _json
        data = manifest.load("../L22/manifest.json")
        cards = manifest.checkpoints(data)
        # 知识点 deck = checkpoint 卡 + 动词变位卡 + AI 产出卡（D2/P4：卡即数据，统一一个 deck）
        _conj = _json.load(open("../L22/conjugation.json"))["verbs"]
        group_count = sum(c.get("study_group") == "future-tense-system" for c in cards)

        at = AppTest.from_file("app.py", default_timeout=10)
        at.run()
        assert not at.exception

        at.selectbox(key="sel_lesson").set_value("L22").run()
        assert not at.exception
        knowledge_button = next(
            (b for b in at.button if b.label.startswith("📝 知识点（")), None
        )
        assert knowledge_button is not None

        knowledge_button.click().run()
        assert not at.exception
        deck = at.session_state.cp_cards
        assert len(deck) >= len(cards) + len(_conj)          # 含 checkpoint + 变位（+产出）
        assert f"📝 知识点 1/{len(deck)}" in [s.value for s in at.subheader]
        assert at.dataframe

        table = at.dataframe[0].value                        # 时态组仍连续在最前（变位/产出在其后）
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


def test_l23_lesson_is_visible_and_checkpoint_deck_starts(tmp_path):
    """新课写入 vocab/manifest 后，应能在侧栏选课并进入知识点 deck。"""
    db_path = Path("dictation.db")
    backup_path = tmp_path / "dictation.db.bak"
    if db_path.exists():
        shutil.copy2(db_path, backup_path)

    try:
        expected_count = len(manifest.checkpoints(manifest.load("../L23/manifest.json")))

        at = AppTest.from_file("app.py", default_timeout=10)
        at.run()
        assert not at.exception

        at.selectbox(key="sel_lesson").set_value("L23").run()
        assert not at.exception
        # 行为：L23 可选课且有可练词。N 来自实时 dictation.db（已排除「🙈 不用背」隐藏词），
        # 与 manifest 静态词数本就可不同，故不硬比计数——只断言按钮存在且 N>0。
        start = next((b for b in at.button if b.label.startswith("开始这一课（")), None)
        assert start is not None
        n = int(start.label.split("（")[1].split(" 词")[0])
        assert n > 0

        knowledge_button = next(
            (b for b in at.button if b.label == f"📝 知识点（{expected_count}）"),
            None,
        )
        assert knowledge_button is not None

        knowledge_button.click().run()
        assert not at.exception
        assert at.session_state.cp_label == "知识点 · L23"
        assert len(at.session_state.cp_cards) == expected_count
        assert f"📝 知识点 1/{expected_count}" in [s.value for s in at.subheader]
    finally:
        if backup_path.exists():
            shutil.copy2(backup_path, db_path)
        elif db_path.exists():
            db_path.unlink()


def test_l24_lesson_is_visible_and_checkpoint_deck_starts(tmp_path):
    """新课写入 vocab/manifest 后，应能在侧栏选课并进入知识点 deck。"""
    db_path = Path("dictation.db")
    backup_path = tmp_path / "dictation.db.bak"
    if db_path.exists():
        shutil.copy2(db_path, backup_path)

    try:
        expected_count = len(manifest.checkpoints(manifest.load("../L24/manifest.json")))

        at = AppTest.from_file("app.py", default_timeout=10)
        at.run()
        assert not at.exception

        at.selectbox(key="sel_lesson").set_value("L24").run()
        assert not at.exception
        # 行为：L24 可选课且有可练词。N 来自实时 dictation.db（已排除「🙈 不用背」隐藏词），
        # 与 manifest 静态词数本就可不同，故不硬比计数——只断言按钮存在且 N>0。
        start = next((b for b in at.button if b.label.startswith("开始这一课（")), None)
        assert start is not None
        n = int(start.label.split("（")[1].split(" 词")[0])
        assert n > 0

        knowledge_button = next(
            (b for b in at.button if b.label == f"📝 知识点（{expected_count}）"),
            None,
        )
        assert knowledge_button is not None

        knowledge_button.click().run()
        assert not at.exception
        assert at.session_state.cp_label == "知识点 · L24"
        assert len(at.session_state.cp_cards) == expected_count
        assert f"📝 知识点 1/{expected_count}" in [s.value for s in at.subheader]
    finally:
        if backup_path.exists():
            shutil.copy2(backup_path, db_path)
        elif db_path.exists():
            db_path.unlink()


def test_l25_lesson_is_visible_and_checkpoint_deck_starts(tmp_path):
    """新课写入 vocab/manifest 后，应能在侧栏选课并进入知识点 deck。"""
    db_path = Path("dictation.db")
    backup_path = tmp_path / "dictation.db.bak"
    if db_path.exists():
        shutil.copy2(db_path, backup_path)

    try:
        expected_count = len(manifest.checkpoints(manifest.load("../L25/manifest.json")))

        at = AppTest.from_file("app.py", default_timeout=10)
        at.run()
        assert not at.exception

        at.selectbox(key="sel_lesson").set_value("L25").run()
        assert not at.exception
        # 行为：L25 可选课且有可练词。N 来自实时 dictation.db（已排除「🙈 不用背」隐藏词），
        # 与 manifest 静态词数本就可不同，故不硬比计数——只断言按钮存在且 N>0。
        start = next((b for b in at.button if b.label.startswith("开始这一课（")), None)
        assert start is not None
        n = int(start.label.split("（")[1].split(" 词")[0])
        assert n > 0

        knowledge_button = next(
            (b for b in at.button if b.label == f"📝 知识点（{expected_count}）"),
            None,
        )
        assert knowledge_button is not None

        knowledge_button.click().run()
        assert not at.exception
        assert at.session_state.cp_label == "知识点 · L25"
        assert len(at.session_state.cp_cards) == expected_count
        assert f"📝 知识点 1/{expected_count}" in [s.value for s in at.subheader]
    finally:
        if backup_path.exists():
            shutil.copy2(backup_path, db_path)
        elif db_path.exists():
            db_path.unlink()


def test_l26_lesson_is_visible_and_checkpoint_deck_starts(tmp_path):
    """新课写入 vocab/manifest 后，应能在侧栏选课并进入知识点 deck。"""
    db_path = Path("dictation.db")
    backup_path = tmp_path / "dictation.db.bak"
    if db_path.exists():
        shutil.copy2(db_path, backup_path)

    try:
        expected_count = len(manifest.checkpoints(manifest.load("../L26/manifest.json")))

        at = AppTest.from_file("app.py", default_timeout=10)
        at.run()
        assert not at.exception

        at.selectbox(key="sel_lesson").set_value("L26").run()
        assert not at.exception
        # 行为：L26 可选课且有可练词。N 来自实时 dictation.db（已排除「🙈 不用背」隐藏词），
        # 与 manifest 静态词数本就可不同，故不硬比计数——只断言按钮存在且 N>0。
        start = next((b for b in at.button if b.label.startswith("开始这一课（")), None)
        assert start is not None
        n = int(start.label.split("（")[1].split(" 词")[0])
        assert n > 0

        knowledge_button = next(
            (b for b in at.button if b.label == f"📝 知识点（{expected_count}）"),
            None,
        )
        assert knowledge_button is not None

        knowledge_button.click().run()
        assert not at.exception
        assert at.session_state.cp_label == "知识点 · L26"
        assert len(at.session_state.cp_cards) == expected_count
        assert f"📝 知识点 1/{expected_count}" in [s.value for s in at.subheader]
    finally:
        if backup_path.exists():
            shutil.copy2(backup_path, db_path)
        elif db_path.exists():
            db_path.unlink()


def test_l27_lesson_is_visible_and_checkpoint_deck_starts(tmp_path):
    """新课写入 vocab/manifest 后，应能在侧栏选课并进入知识点 deck。"""
    db_path = Path("dictation.db")
    backup_path = tmp_path / "dictation.db.bak"
    if db_path.exists():
        shutil.copy2(db_path, backup_path)

    try:
        expected_count = len(manifest.checkpoints(manifest.load("../L27/manifest.json")))

        at = AppTest.from_file("app.py", default_timeout=10)
        at.run()
        assert not at.exception

        at.selectbox(key="sel_lesson").set_value("L27").run()
        assert not at.exception
        # 行为：L27 可选课且有可练词。N 来自实时 dictation.db（已排除「🙈 不用背」隐藏词），
        # 与 manifest 静态词数本就可不同，故不硬比计数——只断言按钮存在且 N>0。
        start = next((b for b in at.button if b.label.startswith("开始这一课（")), None)
        assert start is not None
        n = int(start.label.split("（")[1].split(" 词")[0])
        assert n > 0

        knowledge_button = next(
            (b for b in at.button if b.label == f"📝 知识点（{expected_count}）"),
            None,
        )
        assert knowledge_button is not None

        knowledge_button.click().run()
        assert not at.exception
        assert at.session_state.cp_label == "知识点 · L27"
        assert len(at.session_state.cp_cards) == expected_count
        assert f"📝 知识点 1/{expected_count}" in [s.value for s in at.subheader]
    finally:
        if backup_path.exists():
            shutil.copy2(backup_path, db_path)
        elif db_path.exists():
            db_path.unlink()


def test_l28_lesson_is_visible_and_checkpoint_deck_starts(tmp_path):
    """新课写入 vocab/manifest 后，应能在侧栏选课并进入知识点 deck。"""
    db_path = Path("dictation.db")
    backup_path = tmp_path / "dictation.db.bak"
    if db_path.exists():
        shutil.copy2(db_path, backup_path)

    try:
        expected_count = len(manifest.checkpoints(manifest.load("../L28/manifest.json")))

        at = AppTest.from_file("app.py", default_timeout=10)
        at.run()
        assert not at.exception

        at.selectbox(key="sel_lesson").set_value("L28").run()
        assert not at.exception
        # 行为：L28 可选课且有可练词。N 来自实时 dictation.db（已排除「🙈 不用背」隐藏词），
        # 与 manifest 静态词数本就可不同，故不硬比计数——只断言按钮存在且 N>0。
        start = next((b for b in at.button if b.label.startswith("开始这一课（")), None)
        assert start is not None
        n = int(start.label.split("（")[1].split(" 词")[0])
        assert n > 0

        knowledge_button = next(
            (b for b in at.button if b.label == f"📝 知识点（{expected_count}）"),
            None,
        )
        assert knowledge_button is not None

        knowledge_button.click().run()
        assert not at.exception
        assert at.session_state.cp_label == "知识点 · L28"
        assert len(at.session_state.cp_cards) == expected_count
        assert f"📝 知识点 1/{expected_count}" in [s.value for s in at.subheader]
    finally:
        if backup_path.exists():
            shutil.copy2(backup_path, db_path)
        elif db_path.exists():
            db_path.unlink()


def test_l29_lesson_is_visible_and_checkpoint_deck_starts(tmp_path):
    """新课写入 vocab/manifest 后，应能在侧栏选课并进入知识点 deck。"""
    db_path = Path("dictation.db")
    backup_path = tmp_path / "dictation.db.bak"
    if db_path.exists():
        shutil.copy2(db_path, backup_path)

    try:
        expected_count = len(manifest.checkpoints(manifest.load("../L29/manifest.json")))

        at = AppTest.from_file("app.py", default_timeout=10)
        at.run()
        assert not at.exception

        at.selectbox(key="sel_lesson").set_value("L29").run()
        assert not at.exception
        # 行为：L29 可选课且有可练词。N 来自实时 dictation.db（已排除「🙈 不用背」隐藏词），
        # 与 manifest 静态词数本就可不同，故不硬比计数——只断言按钮存在且 N>0。
        start = next((b for b in at.button if b.label.startswith("开始这一课（")), None)
        assert start is not None
        n = int(start.label.split("（")[1].split(" 词")[0])
        assert n > 0

        knowledge_button = next(
            (b for b in at.button if b.label == f"📝 知识点（{expected_count}）"),
            None,
        )
        assert knowledge_button is not None

        knowledge_button.click().run()
        assert not at.exception
        assert at.session_state.cp_label == "知识点 · L29"
        assert len(at.session_state.cp_cards) == expected_count
        assert f"📝 知识点 1/{expected_count}" in [s.value for s in at.subheader]
    finally:
        if backup_path.exists():
            shutil.copy2(backup_path, db_path)
        elif db_path.exists():
            db_path.unlink()


def test_l30_lesson_is_visible_and_checkpoint_deck_starts(tmp_path):
    """新课写入 vocab/manifest 后，应能在侧栏选课并进入知识点 deck。"""
    db_path = Path("dictation.db")
    backup_path = tmp_path / "dictation.db.bak"
    if db_path.exists():
        shutil.copy2(db_path, backup_path)

    try:
        expected_count = len(manifest.checkpoints(manifest.load("../L30/manifest.json")))
        by_lemma, by_lesson = vocab.load_all_vocab("..")
        l30_meanings = [
            by_lemma[lemma]["zh_by_lesson"]["L30"]
            for lemma in by_lesson["L30"]
        ]
        source_tag = re.compile(r"^\[(?:T4Q\d+(?:/Q\d+)*(?: 补)?|L30课前复习)\] ")
        codex_supplement = re.compile(r"^\[T4Q\d+(?:/Q\d+)* 补\].* \[Codex 建议：.+\]$")
        assert l30_meanings
        assert all(source_tag.match(meaning) for meaning in l30_meanings)
        supplement_meanings = [meaning for meaning in l30_meanings if " 补]" in meaning]
        assert supplement_meanings
        assert all(codex_supplement.match(meaning) for meaning in supplement_meanings)

        at = AppTest.from_file("app.py", default_timeout=10)
        at.run()
        assert not at.exception

        at.selectbox(key="sel_lesson").set_value("L30").run()
        assert not at.exception
        # 行为：L30 可选课且有可练词。N 来自实时 dictation.db（已排除「🙈 不用背」隐藏词），
        # 与 manifest 静态词数本就可不同，故不硬比计数——只断言按钮存在且 N>0。
        start = next((b for b in at.button if b.label.startswith("开始这一课（")), None)
        assert start is not None
        n = int(start.label.split("（")[1].split(" 词")[0])
        assert n > 0

        knowledge_button = next(
            (b for b in at.button if b.label == f"📝 知识点（{expected_count}）"),
            None,
        )
        assert knowledge_button is not None

        knowledge_button.click().run()
        assert not at.exception
        assert at.session_state.cp_label == "知识点 · L30"
        assert len(at.session_state.cp_cards) == expected_count
        assert f"📝 知识点 1/{expected_count}" in [s.value for s in at.subheader]
    finally:
        if backup_path.exists():
            shutil.copy2(backup_path, db_path)
        elif db_path.exists():
            db_path.unlink()


def test_l31_lesson_is_visible_and_checkpoint_deck_starts(tmp_path):
    """新课写入 vocab/manifest 后，应能在侧栏选课并进入知识点 deck。"""
    db_path = Path("dictation.db")
    backup_path = tmp_path / "dictation.db.bak"
    if db_path.exists():
        shutil.copy2(db_path, backup_path)

    try:
        expected_count = len(manifest.checkpoints(manifest.load("../L31/manifest.json")))

        at = AppTest.from_file("app.py", default_timeout=10)
        at.run()
        assert not at.exception

        at.selectbox(key="sel_lesson").set_value("L31").run()
        assert not at.exception
        start = next((b for b in at.button if b.label.startswith("开始这一课（")), None)
        assert start is not None
        n = int(start.label.split("（")[1].split(" 词")[0])
        assert n > 0

        knowledge_button = next(
            (b for b in at.button if b.label == f"📝 知识点（{expected_count}）"),
            None,
        )
        assert knowledge_button is not None

        knowledge_button.click().run()
        assert not at.exception
        assert at.session_state.cp_label == "知识点 · L31"
        assert len(at.session_state.cp_cards) == expected_count
        assert f"📝 知识点 1/{expected_count}" in [s.value for s in at.subheader]
    finally:
        if backup_path.exists():
            shutil.copy2(backup_path, db_path)
        elif db_path.exists():
            db_path.unlink()


def test_l32_lesson_is_visible_and_checkpoint_deck_starts(tmp_path):
    """新课写入 vocab/manifest 后，应能在侧栏选课并进入知识点 deck。"""
    db_path = Path("dictation.db")
    backup_path = tmp_path / "dictation.db.bak"
    if db_path.exists():
        shutil.copy2(db_path, backup_path)

    try:
        expected_count = len(manifest.checkpoints(manifest.load("../L32/manifest.json")))

        at = AppTest.from_file("app.py", default_timeout=10)
        at.run()
        assert not at.exception

        at.selectbox(key="sel_lesson").set_value("L32").run()
        assert not at.exception
        start = next((b for b in at.button if b.label.startswith("开始这一课（")), None)
        assert start is not None
        n = int(start.label.split("（")[1].split(" 词")[0])
        assert n > 0

        knowledge_button = next(
            (b for b in at.button if b.label == f"📝 知识点（{expected_count}）"),
            None,
        )
        assert knowledge_button is not None

        knowledge_button.click().run()
        assert not at.exception
        assert at.session_state.cp_label == "知识点 · L32"
        assert len(at.session_state.cp_cards) == expected_count
        assert f"📝 知识点 1/{expected_count}" in [s.value for s in at.subheader]
    finally:
        if backup_path.exists():
            shutil.copy2(backup_path, db_path)
        elif db_path.exists():
            db_path.unlink()


def test_l33_lesson_is_visible_and_checkpoint_deck_starts(tmp_path):
    """新课写入 vocab/manifest 后，应能在侧栏选课并进入知识点 deck。"""
    db_path = Path("dictation.db")
    backup_path = tmp_path / "dictation.db.bak"
    if db_path.exists():
        shutil.copy2(db_path, backup_path)

    try:
        expected_count = len(manifest.checkpoints(manifest.load("../L33/manifest.json")))

        at = AppTest.from_file("app.py", default_timeout=10)
        at.run()
        assert not at.exception

        at.selectbox(key="sel_lesson").set_value("L33").run()
        assert not at.exception
        start = next((b for b in at.button if b.label.startswith("开始这一课（")), None)
        assert start is not None
        n = int(start.label.split("（")[1].split(" 词")[0])
        assert n > 0

        knowledge_button = next(
            (b for b in at.button if b.label == f"📝 知识点（{expected_count}）"),
            None,
        )
        assert knowledge_button is not None

        knowledge_button.click().run()
        assert not at.exception
        assert at.session_state.cp_label == "知识点 · L33"
        assert len(at.session_state.cp_cards) == expected_count
        assert f"📝 知识点 1/{expected_count}" in [s.value for s in at.subheader]
    finally:
        if backup_path.exists():
            shutil.copy2(backup_path, db_path)
        elif db_path.exists():
            db_path.unlink()


def _load_answer_renderer():
    """用 ast 静态取出答案渲染函数，**不 import app**。

    docs/BACKLOG.md §7：裸 import 会在 pytest 进程里把 app.py 整个跑一遍（含写库），
    后面 AppTest 起的用例会连环失败。这里只把需要的几个函数定义抠出来 exec。
    """
    import ast
    import html as html_mod
    import re as re_mod

    want = {"_strip_answer_markup", "_format_answer_inline", "_checkpoint_answer_html"}
    tree = ast.parse(Path("app.py").read_text("utf-8"))
    picked = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in want]
    assert {n.name for n in picked} == want, "app.py 里的答案渲染函数改名了"
    ns = {"re": re_mod, "html": html_mod, "CHECKPOINT_ANSWER_CSS": ""}
    exec(compile(ast.Module(body=picked, type_ignores=[]), "app.py", "exec"), ns)
    return ns["_checkpoint_answer_html"]


def test_every_lesson_answer_renders_as_closed_html_without_markup_leaking():
    """全库体检：每张知识卡的答案都要渲染成闭合的 HTML，且不漏 markdown 记号。

    答案里的 **加粗** 和 `词形` 记号是数据带进来的（L33 起 900+ 张卡里 600+ 张在用），
    单张卡的用例盯不住。真出过的问题有两类：
      1. 记号不解析，星号/反引号原样显示给学习者；
      2. 解析之后，"de + …" 那条下划线正则一路吞掉注入的标签，
         生成 <u>de + x</strong></u> 这种交错嵌套（实测 20 张卡中招）。
    """
    from html.parser import HTMLParser

    render = _load_answer_renderer()

    class Balance(HTMLParser):
        def __init__(self):
            super().__init__()
            self.stack, self.errors = [], []

        def handle_starttag(self, tag, attrs):
            if tag not in ("br", "hr", "img"):
                self.stack.append(tag)

        def handle_endtag(self, tag):
            if not self.stack:
                self.errors.append(f"多出闭合 </{tag}>")
            elif self.stack[-1] != tag:
                self.errors.append(f"嵌套错位：期望 </{self.stack[-1]}>，实际 </{tag}>")
                self.stack.pop()
            else:
                self.stack.pop()

    problems = []
    marked = 0
    for mf in sorted(Path("..").glob("L*/manifest.json")):
        for card in manifest.checkpoints(manifest.load(str(mf))):
            back = str(card.get("back") or "")
            if not back:
                continue
            if "**" in back or "`" in back:
                marked += 1
            out = render(card)
            checker = Balance()
            checker.feed(out)
            if checker.errors or checker.stack:
                problems.append(f"{mf.parent.name}/{card.get('id')}: {checker.errors or checker.stack}")
            if "**" in out:
                problems.append(f"{mf.parent.name}/{card.get('id')}: 渲染结果里还有 **")
            if re.search(r"(?<!<)`", out):
                problems.append(f"{mf.parent.name}/{card.get('id')}: 渲染结果里还有反引号")

    assert marked > 0, "没有一张卡用 ** 或 ` 记号，这个体检就是空的"
    assert not problems, "答案渲染有问题：\n" + "\n".join(problems[:10])


def test_checkpoint_answer_bold_is_rendered_not_shown_as_asterisks(tmp_path):
    """答案里的 **加粗** 要真的加粗，星号不能露给学习者。

    card_overrides 从 L33 起就用 **…** 标重点，但答案渲染只做 HTML 转义、不解析
    markdown，星号一直原样显示在卡面上。这里按用户看到的结果断言，不断言实现。
    """
    db_path = Path("dictation.db")
    backup_path = tmp_path / "dictation.db.bak"
    if db_path.exists():
        shutil.copy2(db_path, backup_path)

    try:
        cards = manifest.checkpoints(manifest.load("../L36/manifest.json"))
        # 防止空断言：这一课必须真的有卡片在答案里用了 **…**
        assert any("**" in str(c.get("back") or "") for c in cards)

        at = AppTest.from_file("app.py", default_timeout=10)
        at.run()
        at.selectbox(key="sel_lesson").set_value("L36").run()

        knowledge_button = next(
            b for b in at.button if b.label.startswith("📝 知识点（")
        )
        knowledge_button.click().run()
        assert not at.exception

        # 第一张是机判卡，随便提交一个答案就能揭示背面
        at.text_input(key="cp_ans").set_value("peu importe").run()
        next(b for b in at.button if b.label == "提交").click().run()
        assert not at.exception

        answer_html = next(
            m.value for m in at.markdown if "checkpoint-answer" in m.value
        )
        assert "**" not in answer_html, "答案里的星号漏到页面上了"
        assert "<strong" in answer_html, "答案里的重点没有被加粗"
    finally:
        if backup_path.exists():
            shutil.copy2(backup_path, db_path)
        elif db_path.exists():
            db_path.unlink()


def test_l37_lesson_is_visible_and_checkpoint_deck_starts(tmp_path):
    """新课写入 vocab/manifest 后，应能在侧栏选课并进入知识点 deck。"""
    db_path = Path("dictation.db")
    backup_path = tmp_path / "dictation.db.bak"
    if db_path.exists():
        shutil.copy2(db_path, backup_path)

    try:
        expected_count = len(manifest.checkpoints(manifest.load("../L37/manifest.json")))

        at = AppTest.from_file("app.py", default_timeout=10)
        at.run()
        assert not at.exception

        at.selectbox(key="sel_lesson").set_value("L37").run()
        assert not at.exception
        start = next((b for b in at.button if b.label.startswith("开始这一课（")), None)
        assert start is not None
        n = int(start.label.split("（")[1].split(" 词")[0])
        assert n > 0

        knowledge_button = next(
            (b for b in at.button if b.label == f"📝 知识点（{expected_count}）"),
            None,
        )
        assert knowledge_button is not None

        knowledge_button.click().run()
        assert not at.exception
        assert at.session_state.cp_label == "知识点 · L37"
        assert len(at.session_state.cp_cards) == expected_count
        assert f"📝 知识点 1/{expected_count}" in [s.value for s in at.subheader]
    finally:
        if backup_path.exists():
            shutil.copy2(backup_path, db_path)
        elif db_path.exists():
            db_path.unlink()


def test_l36_lesson_is_visible_and_checkpoint_deck_starts(tmp_path):
    """新课写入 vocab/manifest 后，应能在侧栏选课并进入知识点 deck。"""
    db_path = Path("dictation.db")
    backup_path = tmp_path / "dictation.db.bak"
    if db_path.exists():
        shutil.copy2(db_path, backup_path)

    try:
        expected_count = len(manifest.checkpoints(manifest.load("../L36/manifest.json")))

        at = AppTest.from_file("app.py", default_timeout=10)
        at.run()
        assert not at.exception

        at.selectbox(key="sel_lesson").set_value("L36").run()
        assert not at.exception
        start = next((b for b in at.button if b.label.startswith("开始这一课（")), None)
        assert start is not None
        n = int(start.label.split("（")[1].split(" 词")[0])
        assert n > 0

        knowledge_button = next(
            (b for b in at.button if b.label == f"📝 知识点（{expected_count}）"),
            None,
        )
        assert knowledge_button is not None

        knowledge_button.click().run()
        assert not at.exception
        assert at.session_state.cp_label == "知识点 · L36"
        assert len(at.session_state.cp_cards) == expected_count
        assert f"📝 知识点 1/{expected_count}" in [s.value for s in at.subheader]
    finally:
        if backup_path.exists():
            shutil.copy2(backup_path, db_path)
        elif db_path.exists():
            db_path.unlink()


def test_l35_lesson_is_visible_and_checkpoint_deck_starts(tmp_path):
    """新课写入 vocab/manifest 后，应能在侧栏选课并进入知识点 deck。"""
    db_path = Path("dictation.db")
    backup_path = tmp_path / "dictation.db.bak"
    if db_path.exists():
        shutil.copy2(db_path, backup_path)

    try:
        expected_count = len(manifest.checkpoints(manifest.load("../L35/manifest.json")))

        at = AppTest.from_file("app.py", default_timeout=10)
        at.run()
        assert not at.exception

        at.selectbox(key="sel_lesson").set_value("L35").run()
        assert not at.exception
        start = next((b for b in at.button if b.label.startswith("开始这一课（")), None)
        assert start is not None
        n = int(start.label.split("（")[1].split(" 词")[0])
        assert n > 0

        knowledge_button = next(
            (b for b in at.button if b.label == f"📝 知识点（{expected_count}）"),
            None,
        )
        assert knowledge_button is not None

        knowledge_button.click().run()
        assert not at.exception
        assert at.session_state.cp_label == "知识点 · L35"
        assert len(at.session_state.cp_cards) == expected_count
        assert f"📝 知识点 1/{expected_count}" in [s.value for s in at.subheader]
    finally:
        if backup_path.exists():
            shutil.copy2(backup_path, db_path)
        elif db_path.exists():
            db_path.unlink()


def test_l34_lesson_is_visible_and_checkpoint_deck_starts(tmp_path):
    """新课写入 vocab/manifest 后，应能在侧栏选课并进入知识点 deck。"""
    db_path = Path("dictation.db")
    backup_path = tmp_path / "dictation.db.bak"
    if db_path.exists():
        shutil.copy2(db_path, backup_path)

    try:
        expected_count = len(manifest.checkpoints(manifest.load("../L34/manifest.json")))

        at = AppTest.from_file("app.py", default_timeout=10)
        at.run()
        assert not at.exception

        at.selectbox(key="sel_lesson").set_value("L34").run()
        assert not at.exception
        start = next((b for b in at.button if b.label.startswith("开始这一课（")), None)
        assert start is not None
        n = int(start.label.split("（")[1].split(" 词")[0])
        assert n > 0

        knowledge_button = next(
            (b for b in at.button if b.label == f"📝 知识点（{expected_count}）"),
            None,
        )
        assert knowledge_button is not None

        knowledge_button.click().run()
        assert not at.exception
        assert at.session_state.cp_label == "知识点 · L34"
        assert len(at.session_state.cp_cards) == expected_count
        assert f"📝 知识点 1/{expected_count}" in [s.value for s in at.subheader]
    finally:
        if backup_path.exists():
            shutil.copy2(backup_path, db_path)
        elif db_path.exists():
            db_path.unlink()
