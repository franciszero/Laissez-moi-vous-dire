"""键盘脚本的字符串层断言。

**这些测试证明不了按键真的响应**——那只能在真浏览器里逐项过（见施工卡 K5）。
它们守的是「该有的绑定和防护没有被误删」，是回潮的哨兵，不是功能验收。
"""
from __future__ import annotations

import json
import pathlib


def _script(direction, autoplay):
    import ast

    src = pathlib.Path("app.py").read_text("utf-8")
    tree = ast.parse(src)
    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name == "_scan_keyboard_script")
    ns = {}
    import scan as scan_mod
    ns["scan"] = scan_mod
    ns["json"] = json
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "app.py", "exec"), ns)
    return ns["_scan_keyboard_script"](direction, autoplay)


ALL_KEYS = ["ArrowLeft", "ArrowRight", "ArrowDown", "ArrowUp", '"a"', '"d"', '"s"', '"w"',
            '"e"', '"?"', '"/"', '" "']


def test_every_key_is_bound_on_both_hands():
    out = _script("看法→想中", True)
    for k in ALL_KEYS:
        assert k in out, f"缺少键位绑定：{k}"


def test_focus_guard_lets_form_controls_through():
    """焦点在侧栏选课上时按方向键，不许被扫读接管——否则会串着切选项。"""
    out = _script("看法→想中", True)
    for token in ["activeElement", "textarea", "select", "isContentEditable", "isComposing"]:
        assert token in out, f"缺少焦点防护：{token}"


def test_keys_are_prevented_from_doing_their_default_thing():
    """/ 在 Firefox 是快速查找，方向键会滚页面，空格会翻页——全都要挡掉。"""
    out = _script("看法→想中", True)
    assert "preventDefault" in out


def test_listener_is_replaced_not_stacked():
    """完整 rerun 会重新注入本脚本。不先摘掉旧的监听器就会一次按键判定两遍。"""
    out = _script("看法→想中", True)
    assert "removeEventListener" in out
    assert "__scanKb" in out


def test_play_lock_only_in_the_produce_direction():
    assert '"playLocked": true' in _script("看中→想法", False)
    assert '"playLocked": false' in _script("看法→想中", True)
    assert '"playLocked": false' in _script("听音→想双", True)


def test_autoplay_flag_is_passed_through():
    assert '"autoplay": true' in _script("听音→想双", True)
    assert '"autoplay": false' in _script("看中→想法", False)


def test_page_turn_waits_for_the_receipt():
    """翻页是完整 rerun，会把表格连脚本一起重建；不等写库落定就翻会丢判定。"""
    out = _script("看法→想中", True)
    assert "scan-receipt" in out
    assert "nextBtn.click()" in out
    # 等待逻辑必须在点翻页之前
    assert out.index("scan-receipt") < out.index("nextBtn.click()")


def test_undo_is_emitted_when_stepping_back_over_a_mark():
    out = _script("看法→想中", True)
    assert '"U:"' in out or "'U:'" in out


def test_ops_are_sent_cumulatively():
    """连按时单条格式会被覆盖丢判定，必须整串重发。"""
    out = _script("看法→想中", True)
    assert 'ops.join(",")' in out
