from __future__ import annotations

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


def _scan_attempts(word_ids):
    import store
    got = store.get_attempts_for_words(list(word_ids))
    out = []
    for wid, rows in got.items():
        for ok, _ts, skill in rows:
            if skill.startswith("rec_"):
                out.append((wid, ok, skill))
    return out


def _flush(at, raw):
    """模拟键盘脚本：把累积串写进 sink，再点 flush。"""
    at.session_state["scan_sink"] = raw
    at.run()
    _button(at, "flush").click().run()


def test_keyboard_marks_reach_the_database(tmp_path, monkeypatch):
    import store
    at = _run()
    ids = _enter_scan(at)
    a, b = ids[0], ids[1]
    try:
        _flush(at, f"{a}:1,{b}:0")
        got = sorted(_scan_attempts([a, b]))
        assert got == sorted([(a, True, "rec_meaning"), (b, False, "rec_meaning")])
        assert at.session_state["scan_written"] == 2
        assert b in at.session_state["scan_missed_last"]
        assert a not in at.session_state["scan_missed_last"]
    finally:
        for w in (a, b):
            for _ in range(5):
                if not store.delete_last_scan_attempt(w, "rec_meaning"):
                    break


def test_resending_the_same_string_does_not_double_write():
    """连按时脚本会整串重发；服务端靠 scan_written 增量写，不许重复入库。"""
    import store
    at = _run()
    ids = _enter_scan(at)
    a = ids[0]
    try:
        _flush(at, f"{a}:1")
        _button(at, "flush").click().run()      # 同一串再发一次
        assert len(_scan_attempts([a])) == 1
        assert at.session_state["scan_written"] == 1
    finally:
        while store.delete_last_scan_attempt(a, "rec_meaning"):
            pass


def test_undo_removes_the_record_and_the_missed_entry():
    """按错了 → ↑ 回退 → 重表。必须真删：mastery 取当天第一条，覆盖没用。"""
    import store
    at = _run()
    ids = _enter_scan(at)
    a = ids[0]
    try:
        _flush(at, f"{a}:0")
        assert a in at.session_state["scan_missed_last"]
        _flush(at, f"{a}:0,U:{a},{a}:1")
        got = _scan_attempts([a])
        assert got == [(a, True, "rec_meaning")], got
        assert a not in at.session_state["scan_missed_last"]
    finally:
        while store.delete_last_scan_attempt(a, "rec_meaning"):
            pass


def test_words_row_is_untouched_by_the_whole_keyboard_round_trip():
    """v1 的核心不变量，键盘这条路上继续守。"""
    import sqlite3
    import store
    at = _run()
    ids = _enter_scan(at)
    a = ids[0]
    conn = sqlite3.connect(store.DB_PATH)
    before = conn.execute("SELECT * FROM words WHERE id = ?", (a,)).fetchone()
    conn.close()
    try:
        _flush(at, f"{a}:0,U:{a},{a}:1")
        conn = sqlite3.connect(store.DB_PATH)
        after = conn.execute("SELECT * FROM words WHERE id = ?", (a,)).fetchone()
        conn.close()
        assert after == before
    finally:
        while store.delete_last_scan_attempt(a, "rec_meaning"):
            pass
