import sqlite3

import store


def _make_db(path):
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE words (id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT NOT NULL UNIQUE, wrong_count INTEGER NOT NULL DEFAULT 0,
        correct_streak INTEGER NOT NULL DEFAULT 0, interval_days INTEGER NOT NULL DEFAULT 0,
        due_at TEXT, last_seen_at TEXT, created_at TEXT NOT NULL)""")
    conn.commit()
    conn.close()


def test_import_is_idempotent_and_preserves_existing(tmp_path, monkeypatch):
    db = tmp_path / "d.db"
    _make_db(db)
    monkeypatch.setattr(store, "DB_PATH", str(db))
    # 预置一条带历史的老词
    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO words (text, wrong_count, created_at) VALUES ('aussi', 5, '2026-01-01')")
    conn.commit()
    conn.close()

    assert store.import_vocab_into_db({"aussi": {}, "la confiture": {}}) == 1   # 只插新词
    assert store.import_vocab_into_db({"aussi": {}, "la confiture": {}}) == 0   # 幂等
    conn = sqlite3.connect(db)
    wc = conn.execute("SELECT wrong_count FROM words WHERE text='aussi'").fetchone()[0]
    n = conn.execute("SELECT COUNT(*) FROM words").fetchone()[0]
    conn.close()
    assert wc == 5 and n == 2   # 历史不动、无重复


def test_get_ids_for_lemmas(tmp_path, monkeypatch):
    db = tmp_path / "d.db"
    _make_db(db)
    monkeypatch.setattr(store, "DB_PATH", str(db))
    store.import_vocab_into_db({"aussi": {}, "la confiture": {}})
    ids = store.get_ids_for_lemmas(["aussi", "nope", "la confiture"])
    assert len(ids) == 2


def test_save_load_clear_round(tmp_path, monkeypatch):
    db = tmp_path / "d.db"
    _make_db(db)
    monkeypatch.setattr(store, "DB_PATH", str(db))
    assert store.load_round() is None
    store.save_round({"pool": [1, 2, 3], "index": 2, "round_first_ids": [1]})
    got = store.load_round()
    assert got["pool"] == [1, 2, 3] and got["index"] == 2
    store.save_round({"pool": [9], "index": 1})   # 覆盖
    assert store.load_round()["pool"] == [9]
    store.clear_round()
    assert store.load_round() is None


def _make_db_with_card_requested(path):
    """带 card_requested 列的 words 表（app.init_db 迁移后的形状）。"""
    _make_db(path)
    conn = sqlite3.connect(path)
    conn.execute("ALTER TABLE words ADD COLUMN card_requested INTEGER NOT NULL DEFAULT 0")
    conn.commit()
    conn.close()


def test_card_request_roundtrip_is_per_lemma(tmp_path, monkeypatch):
    db = tmp_path / "d.db"
    _make_db_with_card_requested(db)
    monkeypatch.setattr(store, "DB_PATH", str(db))
    store.import_vocab_into_db({"la retraite": {}, "un départ": {}})

    assert store.is_card_requested("la retraite") is False
    assert store.get_card_requested_words() == []

    store.set_card_requested("la retraite", True)
    assert store.is_card_requested("la retraite") is True
    assert store.is_card_requested("un départ") is False       # 只影响这一条
    assert [r["text"] for r in store.get_card_requested_words()] == ["la retraite"]

    store.set_card_requested("la retraite", False)             # 可撤销
    assert store.is_card_requested("la retraite") is False
    assert store.get_card_requested_words() == []


def test_card_request_on_unknown_lemma_is_a_noop(tmp_path, monkeypatch):
    """词不在库里时静默不写，不抛异常——UI 上没有这个词就没有按钮。"""
    db = tmp_path / "d.db"
    _make_db_with_card_requested(db)
    monkeypatch.setattr(store, "DB_PATH", str(db))

    store.set_card_requested("inexistant", True)
    assert store.is_card_requested("inexistant") is False
    assert store.get_card_requested_words() == []
