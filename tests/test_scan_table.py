"""表格 HTML 的结构断言。渲染是字符串拼接，可以脱离浏览器测。"""
from __future__ import annotations

import pathlib


def _load_app_fns():
    """只取 app.py 里那几个纯函数，不执行整个脚本（docs/BACKLOG.md 第 7 条）。"""
    import ast

    src = pathlib.Path("app.py").read_text("utf-8")
    tree = ast.parse(src)
    wanted = {"_scan_table_html", "_saved_index"}
    fns = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
    assert {n.name for n in fns} == wanted, f"app.py 里缺函数：{wanted - {n.name for n in fns}}"
    # 它们还用到模块级的 _SCAN_* 常量，不一起搬过来 exec 时会 NameError。
    consts = [
        n for n in tree.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id.startswith("_SCAN") for t in n.targets)
    ]
    ns = {}
    import html as html_mod
    ns["html"] = html_mod
    import scan as scan_mod
    ns["scan"] = scan_mod
    exec(compile(ast.Module(body=consts + fns, type_ignores=[]), "app.py", "exec"), ns)
    return ns


ROWS = [
    {"no": 1, "word_id": 11, "fr": "la confiture", "zh": "果酱"},
    {"no": 2, "word_id": 12, "fr": "s'installer", "zh": "定居"},
    {"no": 3, "word_id": 13, "fr": "la province", "zh": "外省"},
]
URLS = {11: "/app/static/audio/a.m4a", 12: "/app/static/audio/b.m4a"}   # 13 号没音频


def test_meaning_direction_covers_only_chinese():
    fn = _load_app_fns()["_scan_table_html"]
    out = fn(ROWS, "看法→想中", URLS, 0)
    assert "la confiture" in out and "果酱" in out
    assert out.index("la confiture") < out.index("果酱")   # 法语在前、中文被盖
    assert out.count("scan-cover") == 3                     # 每行盖一格
    assert "data-locked" not in out


def test_produce_direction_locks_the_play_button():
    fn = _load_app_fns()["_scan_table_html"]
    out = fn(ROWS, "看中→想法", URLS, 0)
    assert "data-locked='1'" in out


def test_audio_direction_covers_both():
    fn = _load_app_fns()["_scan_table_html"]
    out = fn(ROWS, "听音→想双", URLS, 0)
    assert out.count("scan-cover") == 6                     # 每行盖两格


def _rows_of(out):
    """把每个 <tr class='scan-row' ...> 开标签切出来，方便逐行断言。"""
    import re
    return re.findall(r"<tr class='scan-row'[^>]*>", out)


def test_exactly_one_row_is_current_and_it_is_the_cursor_row():
    fn = _load_app_fns()["_scan_table_html"]
    out = fn(ROWS, "看法→想中", URLS, 1)          # 光标在第 2 行（no=2）
    tags = _rows_of(out)
    assert len(tags) == 3
    current = [t for t in tags if "data-current='1'" in t]
    assert len(current) == 1
    assert "data-no='2'" in current[0]


def test_play_button_is_visible_only_on_the_current_row():
    """每行都渲染播放键，但只有当前行可见——光标移动时脚本只翻样式，不造 DOM。"""
    fn = _load_app_fns()["_scan_table_html"]
    out = fn(ROWS, "看法→想中", URLS, 0)
    # 数 class='scan-play 而不是裸的 scan-play：没音频那行的 class 是
    # 'scan-play scan-play-dead'，裸子串会数成两次。
    assert out.count("class='scan-play") == 3
    assert out.count("visibility:hidden") == 2              # 另两行藏起来


def test_dead_play_button_when_audio_missing():
    fn = _load_app_fns()["_scan_table_html"]
    out = fn(ROWS, "看法→想中", URLS, 2)                    # 光标落在没音频的第 3 行
    assert "scan-play-dead" in out
    assert "发音还没生成好" in out


def test_cover_is_a_block_so_it_can_actually_be_clicked():
    """内联 span 遇到两行中文时中心点落在行间距里，elementFromPoint 返回 <td>。
    撑成 inline-block + width:100% 才点得中——v1 修过的，不许回潮。"""
    style = _load_app_fns()["_SCAN_COVER_STYLE"]
    assert "display:inline-block" in style
    assert "width:100%" in style


def test_html_is_escaped():
    fn = _load_app_fns()["_scan_table_html"]
    rows = [{"no": 1, "word_id": 1, "fr": "<script>x</script>", "zh": "&"}]
    out = fn(rows, "看法→想中", {}, 0)
    assert "<script>x</script>" not in out
    assert "&lt;script&gt;" in out


def test_every_row_carries_its_lesson_wide_number_and_word_id():
    fn = _load_app_fns()["_scan_table_html"]
    rows = [{"no": 21, "word_id": 99, "fr": "a", "zh": "甲"}]
    out = fn(rows, "看法→想中", {}, 0)
    assert "data-no='21'" in out
    assert "data-wid='99'" in out          # 键盘回传要靠它拼 word_id


def test_mouse_era_markup_is_gone():
    """防回潮：勾选框和 data-rev 是鼠标那一套的残留，不许再出现。"""
    fn = _load_app_fns()["_scan_table_html"]
    out = fn(ROWS, "看法→想中", URLS, 0)
    assert "scan-miss" not in out
    assert "data-rev" not in out
    assert "checkbox" not in out


def test_saved_index_falls_back_instead_of_exploding():
    fn = _load_app_fns()["_saved_index"]
    opts = ["看法→想中", "看中→想法", "听音→想双"]
    assert fn(opts, "看中→想法", "看法→想中") == 1
    assert fn(opts, "已经改名的旧值", "听音→想双") == 2
    assert fn(opts, None, None) == 0
    assert fn([], "x", "y") == 0
