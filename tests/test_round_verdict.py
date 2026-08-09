"""法+中模式的本轮判定：两项分开，法语拼错不抹掉中文答对。

背景：check_fr 是硬 bool（重音敏感、无申诉），check_zh 拿不准时交人工点
「中文算我对/算我错」。以前 round_results 存的是两者的 AND，所以法语一旦
❌，中文那两个按钮点哪个整题都是 ❌——按钮看起来没用。底层的 transcribe /
meaning 两条技能记录一直是分开的，被 AND 掉的只有本轮显示。
"""
from __future__ import annotations

import ast
from pathlib import Path

APP = Path(__file__).parents[1] / "app.py"


def _load(name: str):
    """从 app.py 里单独取一个纯函数——app.py 是 Streamlit 脚本，整体 import
    会把整个 UI 跑一遍并污染后续测试。"""
    tree = ast.parse(APP.read_text("utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    ns: dict = {}
    exec(compile(ast.Module([fn], []), str(APP), "exec"), ns)
    return ns[name]


def test_single_skill_mark_is_unchanged():
    mark = _load("_round_mark")
    assert mark(True) == "✅ "
    assert mark(False) == "❌ "
    assert mark(None) == ""          # 还没作答


def test_both_mode_shows_two_marks_front_fr_back_zh():
    mark = _load("_round_mark")
    assert mark({"fr": False, "zh": True}) == "❌✅ ", "法语错、中文对，两个标记都要在"
    assert mark({"fr": True, "zh": True}) == "✅✅ "
    assert mark({"fr": True, "zh": False}) == "✅❌ "


def test_tally_counts_fields_separately():
    tally = _load("_round_tally")
    out = tally({1: {"fr": False, "zh": True}, 2: {"fr": True, "zh": True}})
    assert "法语 对 1 / 错 1" in out
    assert "中文 对 2 / 错 0" in out


def test_tally_still_handles_single_skill_rounds():
    tally = _load("_round_tally")
    assert tally({1: True, 2: False, 3: True}) == "对 2 / 错 1"


def test_tally_handles_a_mixed_restored_round():
    """刷新续上的旧轮次里可能同时有 bool 和 dict，不能炸。"""
    tally = _load("_round_tally")
    out = tally({1: True, 2: {"fr": False, "zh": True}})
    assert "对 1 / 错 0" in out and "法语 对 0 / 错 1" in out


def test_tally_of_empty_round():
    assert _load("_round_tally")({}) == "对 0 / 错 0"
