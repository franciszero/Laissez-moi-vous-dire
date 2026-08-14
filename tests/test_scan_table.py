"""表格 HTML 的结构断言。渲染是字符串拼接，可以脱离浏览器测。"""
from __future__ import annotations

import pathlib


def _load_app_fns():
    """只取 app.py 里的两个纯函数，不执行整个脚本（docs/BACKLOG.md 第 7 条）。

    做法：把源码解析成 AST，挑出这两个函数定义单独 exec。
    """
    import ast

    src = pathlib.Path("app.py").read_text("utf-8")
    tree = ast.parse(src)
    wanted = {"_scan_table_html", "_scan_behavior_script"}
    fns = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
    assert {n.name for n in fns} == wanted, "app.py 里没找到这两个函数"
    # 这两个函数还用到模块级的 _SCAN_* 常量，不一起搬过来 exec 时会 NameError。
    consts = [
        n for n in tree.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id.startswith("_SCAN")
                for t in n.targets)
    ]
    picked = consts + fns
    ns = {}
    import html as html_mod
    ns["html"] = html_mod
    import scan as scan_mod
    ns["scan"] = scan_mod
    exec(compile(ast.Module(body=picked, type_ignores=[]), "app.py", "exec"), ns)
    return ns


ROWS = [
    {"no": 1, "word_id": 11, "fr": "la confiture", "zh": "果酱"},
    {"no": 2, "word_id": 12, "fr": "s'installer", "zh": "定居"},
]
URLS = {11: "/app/static/audio/a.m4a"}      # 12 号故意没有音频


def test_meaning_direction_covers_only_chinese():
    fn = _load_app_fns()["_scan_table_html"]
    out = fn(ROWS, "看法→想中", URLS, "0-0")
    assert "la confiture" in out and "果酱" in out
    assert "scan-cover" in out
    # 中文被盖、法语没被盖
    assert out.index("la confiture") < out.index("果酱")
    assert "data-locked" not in out


def test_produce_direction_locks_the_play_button():
    fn = _load_app_fns()["_scan_table_html"]
    out = fn(ROWS, "看中→想法", URLS, "0-0")
    assert "data-locked='1'" in out


def test_missing_audio_renders_a_dead_play_button():
    fn = _load_app_fns()["_scan_table_html"]
    out = fn(ROWS, "看法→想中", URLS, "0-0")
    assert out.count("scan-play") == 1          # 只有 11 号有音频


def test_html_is_escaped():
    fn = _load_app_fns()["_scan_table_html"]
    rows = [{"no": 1, "word_id": 1, "fr": "<script>x</script>", "zh": "&"}]
    out = fn(rows, "看法→想中", {}, "0-0")
    assert "<script>x</script>" not in out
    assert "&lt;script&gt;" in out


def test_every_row_carries_its_lesson_wide_number():
    fn = _load_app_fns()["_scan_table_html"]
    rows = [{"no": 21, "word_id": 1, "fr": "a", "zh": "甲"}]
    out = fn(rows, "看法→想中", {}, "0-0")
    assert "data-no='21'" in out


def test_rev_token_reaches_the_table():
    """同步脚本靠它认出「这是新的一页，把上一页的勾清掉」。"""
    fn = _load_app_fns()["_scan_table_html"]
    rows = [{"no": 1, "word_id": 1, "fr": "a", "zh": "甲"}]
    assert "data-rev='0-0'" in fn(rows, "看法→想中", {}, "0-0")
    assert "data-rev='3-7'" in fn(rows, "看法→想中", {}, "3-7")


def test_behavior_script_covers_three_modes():
    fn = _load_app_fns()["_scan_behavior_script"]
    for mode in ("click", "hover", "page"):
        out = fn(mode)
        assert f'"{mode}"' in out
        assert "window.parent.document" in out
