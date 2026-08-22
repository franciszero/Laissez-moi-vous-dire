from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest


def _run():
    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    return at


def _button(at, startswith):
    for b in at.button:
        if b.label.startswith(startswith):
            return b
    raise AssertionError(f"没找到以 {startswith!r} 开头的按钮：{[b.label for b in at.button]}")


def _peek(at, key):
    """AppTest 的 SafeSessionState 没有 .get()——属性访问会被当成 key 查找。"""
    return at.session_state[key] if key in at.session_state else None


def test_sidebar_has_scan_entry():
    at = _run()
    b = _button(at, "⚡ 速过")
    assert "（" in b.label and "）" in b.label      # 带词数


def test_scan_does_not_disturb_the_word_round():
    """速过是独立 overlay，绝不许碰逐词状态机。"""
    at = _run()
    before = (_peek(at, "pool"), _peek(at, "current_word"), _peek(at, "index"))
    _button(at, "⚡ 速过").click().run()
    assert at.session_state["scan_active"] is True
    after = (_peek(at, "pool"), _peek(at, "current_word"), _peek(at, "index"))
    assert after == before


def test_scan_closes_other_overlays():
    at = _run()
    at.session_state["cp_active"] = True
    at.session_state["writing_active"] = True
    at.run()
    _button(at, "⚡ 速过").click().run()
    assert at.session_state["cp_active"] is False
    assert "writing_active" not in at.session_state


def test_leaving_scan_returns_to_practice():
    at = _run()
    _button(at, "⚡ 速过").click().run()
    _button(at, "← 回到练习").click().run()
    # _leave_overlays 弹掉 scan_active，下一轮的初始化块把它重建成 False
    # （和 cp_active 一个套路）。所以这里查的是 False，不是 None。
    assert at.session_state["scan_active"] is False


def test_stale_saved_setting_does_not_break_the_scan_view():
    """真实场景：以前存过一个方向名，后来改了名字。旧值还躺在 app_state 里，
    一进速过 list.index() 就抛 ValueError。这条守住兜底真的接上了。"""
    import store

    old_dir = store.load_setting("scan_direction", None)
    try:
        store.save_setting("scan_direction", "这个方向已经不存在了")
        at = _run()
        _button(at, "⚡ 速过").click().run()
        assert not at.exception, [e.message for e in at.exception]
        assert at.session_state["scan_active"] is True
    finally:
        if old_dir is not None:
            store.save_setting("scan_direction", old_dir)


def _enter_scan(at):
    _button(at, "⚡ 速过").click().run()
    return at.session_state["scan_ids"]


@pytest.fixture
def scratch():
    """在真实 dictation.db 上做增量断言，并且只清理本用例造出来的行。

    **绝不能用 delete_last_scan_attempt 收尾**：它删的是「这个词最近一条扫读
    记录」，分不清是测试造的还是用户真背出来的。2026-08-21 就是这么把用户
    一条真实记录删掉的（id 3103，无法恢复）。这里改成记下水位线、只删水位线
    以上的 rec_* 行。
    """
    import sqlite3
    import store

    conn = sqlite3.connect(store.DB_PATH)
    mark = conn.execute("SELECT COALESCE(MAX(id), 0) FROM attempts").fetchone()[0]
    conn.close()
    try:
        yield mark
    finally:
        conn = sqlite3.connect(store.DB_PATH)
        conn.execute(
            "DELETE FROM attempts WHERE id > ? AND skill LIKE 'rec\\_%' ESCAPE '\\'",
            (mark,),
        )
        conn.commit()
        conn.close()


def _new_scan_rows(mark):
    """水位线之上的扫读记录 —— 只看本用例造出来的，不看用户已有的。"""
    import sqlite3
    import store

    conn = sqlite3.connect(store.DB_PATH)
    rows = conn.execute(
        "SELECT word_id, is_correct, skill FROM attempts "
        "WHERE id > ? AND skill LIKE 'rec\\_%' ESCAPE '\\' ORDER BY id",
        (mark,),
    ).fetchall()
    conn.close()
    return [(w, bool(ok), sk) for w, ok, sk in rows]


def _flush(at, raw):
    """模拟键盘脚本：把累积串写进 sink，再提交那个表单。

    sink 必须在 st.form 里——裸的 st.text_input 只在失焦或回车时才把值发回
    服务端，用 native setter 改值只更新前端 React 状态。K5 真机实测就是这么
    翻车的：sink 里明明是 "1275:1,246:0"，库里一条没有。
    """
    at.session_state["scan_sink"] = raw
    at.run()
    _button(at, "flush").click().run()


def test_keyboard_marks_reach_the_database(scratch):
    at = _run()
    ids = _enter_scan(at)
    a, b = ids[0], ids[1]
    _flush(at, f"{a}:1,{b}:0")
    assert _new_scan_rows(scratch) == [(a, True, "rec_meaning"), (b, False, "rec_meaning")]
    assert at.session_state["scan_written"] == 2
    assert b in at.session_state["scan_missed_last"]
    assert a not in at.session_state["scan_missed_last"]


def test_resending_the_same_string_does_not_double_write(scratch):
    """连按时脚本会整串重发；服务端靠 scan_written 增量写，不许重复入库。"""
    at = _run()
    a = _enter_scan(at)[0]
    _flush(at, f"{a}:1")
    _button(at, "flush").click().run()      # 同一串再发一次
    assert _new_scan_rows(scratch) == [(a, True, "rec_meaning")]
    assert at.session_state["scan_written"] == 1


def test_undo_removes_the_record_and_the_missed_entry(scratch):
    """按错了 → ↑ 回退 → 重表。必须真删：mastery 取当天第一条，覆盖没用。"""
    at = _run()
    a = _enter_scan(at)[0]
    _flush(at, f"{a}:0")
    assert a in at.session_state["scan_missed_last"]
    _flush(at, f"{a}:0,U:{a},{a}:1")
    assert _new_scan_rows(scratch) == [(a, True, "rec_meaning")]
    assert a not in at.session_state["scan_missed_last"]


def test_words_row_is_untouched_by_the_whole_keyboard_round_trip(scratch):
    """v1 的核心不变量，键盘这条路上继续守。"""
    import sqlite3
    import store

    at = _run()
    a = _enter_scan(at)[0]
    conn = sqlite3.connect(store.DB_PATH)
    before = conn.execute("SELECT * FROM words WHERE id = ?", (a,)).fetchone()
    conn.close()

    _flush(at, f"{a}:0,U:{a},{a}:1")

    conn = sqlite3.connect(store.DB_PATH)
    after = conn.execute("SELECT * FROM words WHERE id = ?", (a,)).fetchone()
    conn.close()
    assert after == before
