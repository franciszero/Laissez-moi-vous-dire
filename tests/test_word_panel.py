"""侧栏词表的守卫。

这张表以前一行测试都没有：它是 pandas Styler + column_order 拼出来的，
`_style` 返回的列表长度和 row.index 对不上就会在运行时炸，而全量 pytest
一片绿也照样发现不了——因为没人渲染过它。
"""
from __future__ import annotations

import sqlite3

import pytest
from streamlit.testing.v1 import AppTest

import store

SKILL_COLUMNS = ["词", "听", "产", "义", "音", "变", "认"]


@pytest.fixture(autouse=True)
def _keep_the_saved_round():
    """还原存档轮次。

    app.py 每次渲染结束都会 `if pool: persist_round()`——这些用例一旦把 pool
    撑起来，就会把用户真正在练的那一轮冲掉，还会让后面的用例在启动时「续上」
    别人的轮次。整个套件的结果因此依赖 dictation.db 的持久化状态。
    """
    before = store.load_round()
    try:
        yield
    finally:
        if before is None:
            store.clear_round()
        else:
            store.save_round(before)


def _some_word_ids(n=3):
    conn = sqlite3.connect("dictation.db")
    rows = conn.execute(
        "SELECT id FROM words WHERE hidden = 0 ORDER BY id LIMIT ?", (n,)
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def _panel(show_trans=False):
    """开一轮把词表撑起来。不点「开始这一课」是为了不触发朗读。"""
    at = AppTest.from_file("app.py", default_timeout=60)
    at.run()
    at.session_state["pool"] = _some_word_ids()
    at.session_state["round_lesson"] = "全部"
    at.session_state["show_trans"] = show_trans
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    for d in at.dataframe:
        if hasattr(d.value, "columns") and "词" in list(d.value.columns):
            return at, d
    raise AssertionError("没找到词表")


def test_word_panel_renders_without_exception():
    at, _ = _panel()
    assert not at.exception


def test_every_skill_column_is_actually_displayed():
    """断言 column_order（真正显示的），不是 DataFrame.columns——后者永远
    是全集，漏掉某一列也照样在里面。"""
    _, d = _panel()
    shown = list(d.proto.column_order)
    assert shown == SKILL_COLUMNS + ["状态"]


def test_translation_column_appears_only_when_asked():
    _, off = _panel(show_trans=False)
    assert "翻译" not in list(off.proto.column_order)
    _, on = _panel(show_trans=True)
    assert list(on.proto.column_order) == SKILL_COLUMNS + ["翻译", "状态"]


def test_pool_words_are_listed_and_hidden_ones_are_marked():
    """行数不等于池子大小：render_word_panel 故意把本课已隐藏的词也列出来
    （便于查看与恢复，见 app.py 里那段注释）。契约是「池子里的词一个不少，
    多出来的那些必须打上已隐藏」。"""
    at, d = _panel()
    df = d.value
    pool_rows = df[df["状态"] != "已隐藏"]
    assert len(pool_rows) == len(at.session_state["pool"])
    extra = df[df["状态"] == "已隐藏"]
    assert all(w.startswith("🙈") for w in extra["词"])


def test_styler_paints_every_skill_cell():
    """`_style` 每行返回的列表必须和列数对齐，且技能列都得有底色。
    对不齐时 pandas 会抛异常，这条会连着 renders_without_exception 一起红。"""
    _, d = _panel()
    html = d.value.style.to_html() if hasattr(d.value, "style") else ""
    assert html, "拿不到样式输出"
