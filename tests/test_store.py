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
