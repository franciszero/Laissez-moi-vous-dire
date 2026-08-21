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
