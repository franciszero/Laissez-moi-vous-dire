from __future__ import annotations

import pytest

import store


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "test.db"))
    return store


def test_tables_idempotent(tmp_db):
    h = tmp_db.StoreWritingHistory()
    assert h.list_versions("t") == ()
    assert h.list_versions("t") == ()  # 第二次触发建表也不炸


def test_draft_overwrite_and_missing_is_none(tmp_db):
    h = tmp_db.StoreWritingHistory()
    assert h.load_draft("t1") is None
    h.save_draft("t1", "premier")
    d = h.save_draft("t1", "deuxième")
    assert d.text == "deuxième"
    assert h.load_draft("t1").text == "deuxième"


def test_versions_append_only_ordered_persistent(tmp_db):
    h = tmp_db.StoreWritingHistory()
    v1 = h.submit_version("t1", "un")
    v2 = h.submit_version("t1", "deux", parent_version_id=v1.version_id)
    h.submit_version("t2", "autre")
    got = h.list_versions("t1")
    assert [v.text for v in got] == ["un", "deux"]
    assert got[1].parent_version_id == v1.version_id
    assert v1.version_id != v2.version_id
    # 新实例（模拟重启）仍可读
    assert [v.text for v in tmp_db.StoreWritingHistory().list_versions("t1")] == ["un", "deux"]
