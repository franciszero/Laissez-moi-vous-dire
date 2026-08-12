"""搜词 → 开卷：能到达当前轮次之外的词，并看到它的来处与练习记录。"""
from pathlib import Path
import shutil

from streamlit.testing.v1 import AppTest


def _app(tmp_path):
    db, bak = Path("dictation.db"), tmp_path / "dictation.db.bak"
    if db.exists():
        shutil.copy2(db, bak)
    return AppTest.from_file("app.py", default_timeout=25).run(), db, bak


def _restore(db, bak):
    if bak.exists():
        shutil.copy2(bak, db)
    elif db.exists():
        db.unlink()


def test_search_reaches_a_word_outside_the_current_round(tmp_path):
    at, db, bak = _app(tmp_path)
    try:
        at.selectbox(key="sel_lesson").set_value("L34").run()
        next(b for b in at.button if b.label.startswith("开始这一课")).click().run()
        assert at.session_state.round_lesson == "L34"

        # 整词（去重音也行）——半截词现在归 near() 的「是不是想找」，不进结果列表
        at.text_input(key="word_search").set_value("s'integrer").run()
        assert not at.exception
        keys = [b.key for b in at.button if b.key and b.key.startswith("sr_")]
        assert "sr_s'intégrer" in keys, f"没搜到 L31 的词：{keys}"

        next(b for b in at.button if b.key == "sr_s'intégrer").click().run()
        assert not at.exception
        assert any("s'intégrer" in h.value for h in at.subheader), "应打开该词的开卷视图"
        # 跨课来源：当前轮是 L34，这个词只属于 L31，按当前课过滤会是一片空白
        assert [e for e in at.expander if e.label == "📚 为什么收录这个词"], \
            "开卷视图必须跨课取 provenance，否则搜到别课的词看不到来处"
    finally:
        _restore(db, bak)


def test_search_without_accents_and_by_chinese(tmp_path):
    at, db, bak = _app(tmp_path)
    try:
        at.text_input(key="word_search").set_value("securite").run()
        assert "sr_la sécurité" in [b.key for b in at.button if b.key], "去重音搜不到"

        at.text_input(key="word_search").set_value("长期").run()
        assert "sr_à long terme" in [b.key for b in at.button if b.key], "中文搜不到"
    finally:
        _restore(db, bak)


def test_empty_search_falls_back_to_the_word_list(tmp_path):
    at, db, bak = _app(tmp_path)
    try:
        at.text_input(key="word_search").set_value("").run()
        assert not at.exception
        assert not [b for b in at.button if b.key and b.key.startswith("sr_")]
    finally:
        _restore(db, bak)


def test_miss_says_so_without_crashing(tmp_path):
    at, db, bak = _app(tmp_path)
    try:
        at.text_input(key="word_search").set_value("zzzznotaword").run()
        assert not at.exception
        assert any("没有" in c.value for c in at.caption)
    finally:
        _restore(db, bak)


def test_partial_input_offers_guesses_instead_of_results(tmp_path):
    """半截词不该混进结果列表，但也不能就此断掉——给「是不是想找」。"""
    at, db, bak = _app(tmp_path)
    try:
        at.text_input(key="word_search").set_value("sécu").run()
        assert not at.exception
        assert not [b for b in at.button if b.key and b.key.startswith("sr_")], \
            "半截词不该出现在「N 个结果」里"
        guesses = [b.key for b in at.button if b.key and b.key.startswith("sn_")]
        assert "sn_la sécurité" in guesses, f"应给出猜测：{guesses}"
        assert any("猜的" in c.value for c in at.caption), "必须标明这是猜的"
    finally:
        _restore(db, bak)
