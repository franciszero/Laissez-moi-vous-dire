from __future__ import annotations

import scan


def test_page_commit_maps_marks_to_rows():
    """提交语义：没勾的算会，勾了的算不会。这条不随 A/B 路变。"""
    rows = scan.page_rows(
        [11, 12, 13],
        {11: "a", 12: "b", 13: "c"},
        {"a": "甲", "b": "乙", "c": "丙"},
        start_no=21,
    )
    missed = scan.parse_missed("22")
    assert scan.commit(rows, missed) == [(11, True), (12, False), (13, True)]


def test_dirty_payload_does_not_lose_the_page():
    rows = scan.page_rows([11], {11: "a"}, {"a": "甲"}, start_no=1)
    assert scan.commit(rows, scan.parse_missed("x,,-3")) == [(11, True)]
