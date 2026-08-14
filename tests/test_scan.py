from __future__ import annotations

import ast
import pathlib

import scan


def test_directions_shape():
    assert list(scan.DIRECTIONS) == ["看法→想中", "看中→想法", "听音→想双"]
    assert scan.DIRECTIONS["看法→想中"] == ("rec_meaning", "fr", ("zh",), False)
    assert scan.DIRECTIONS["看中→想法"] == ("rec_produce", "zh", ("fr",), True)
    assert scan.DIRECTIONS["听音→想双"] == ("rec_audio", None, ("fr", "zh"), False)
    assert scan.REC_SKILLS == ("rec_meaning", "rec_produce", "rec_audio")


def test_produce_direction_locks_the_play_button():
    """看中→想法：一听发音就等于给了法语答案，▶ 必须跟着一起锁。"""
    assert scan.DIRECTIONS["看中→想法"][3] is True
    assert scan.DIRECTIONS["看法→想中"][3] is False
    assert scan.DIRECTIONS["听音→想双"][3] is False


def test_paginate_basic():
    assert scan.paginate([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]
    assert scan.paginate([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]


def test_paginate_edges():
    assert scan.paginate([], 20) == []
    assert scan.paginate([7], 20) == [[7]]
    assert scan.paginate([1, 2, 3], 0) == [[1, 2, 3]]      # 0 = 不分页
    assert scan.paginate([1, 2, 3], -5) == [[1, 2, 3]]
    assert scan.paginate([1, 2, 3], 99) == [[1, 2, 3]]


def test_page_rows_numbers_are_lesson_wide():
    """序号是整课连续编号，不是页内编号——第 2 页第 1 行应该是 21。"""
    rows = scan.page_rows(
        [11, 12],
        {11: "la confiture", 12: "s'installer"},
        {"la confiture": "果酱", "s'installer": "定居"},
        start_no=21,
    )
    assert [r["no"] for r in rows] == [21, 22]
    assert rows[0] == {"no": 21, "word_id": 11, "fr": "la confiture", "zh": "果酱"}


def test_page_rows_missing_gloss():
    rows = scan.page_rows([9], {9: "truc"}, {}, start_no=1)
    assert rows[0]["zh"] == "（无释义）"


def test_commit_unmarked_counts_as_known():
    rows = scan.page_rows(
        [1, 2, 3], {1: "a", 2: "b", 3: "c"}, {"a": "甲", "b": "乙", "c": "丙"}
    )
    assert scan.commit(rows, {2}) == [(1, True), (2, False), (3, True)]
    assert scan.commit(rows, set()) == [(1, True), (2, True), (3, True)]


def test_commit_ignores_out_of_range_numbers():
    rows = scan.page_rows([1], {1: "a"}, {"a": "甲"})
    assert scan.commit(rows, {1, 99}) == [(1, False)]


def test_parse_missed():
    assert scan.parse_missed("3,7,12") == {3, 7, 12}
    assert scan.parse_missed(" 3 , 7 ") == {3, 7}
    assert scan.parse_missed("") == set()
    assert scan.parse_missed(None) == set()
    assert scan.parse_missed("3,,x,-1,7") == {3, 7}      # 脏值静默丢弃


def test_scan_module_is_pure():
    """scan.py 不许碰 streamlit / sqlite3 / app —— 它必须能脱离 Streamlit 单测。"""
    tree = ast.parse(pathlib.Path("scan.py").read_text("utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    assert not (names & {"streamlit", "sqlite3", "app"})
