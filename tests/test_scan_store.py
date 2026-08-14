"""扫读入库的守卫测试。

核心不变量：扫读是自判、没有拼写证据，所以只许往 attempts 插行，
绝不许改 words 的 SRS 状态——那是 app.record_attempt 独占的。
"""
from __future__ import annotations

import sqlite3

import pytest

import store


def _fresh_db(tmp_path, monkeypatch):
    """独立的 dictation.db。init_db() 在 app.py 里，而测试禁止裸 import app
    （docs/BACKLOG.md 第 7 条），所以这里自建 store 用得到的两张表。"""
    db = tmp_path / "t.db"
    conn = sqlite3.connect(db)
    conn.execute(
        """CREATE TABLE words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL UNIQUE,
            wrong_count INTEGER NOT NULL DEFAULT 0,
            correct_streak INTEGER NOT NULL DEFAULT 0,
            interval_days INTEGER NOT NULL DEFAULT 0,
            due_at TEXT, last_seen_at TEXT, created_at TEXT NOT NULL,
            hidden INTEGER NOT NULL DEFAULT 0)"""
    )
    conn.execute(
        """CREATE TABLE attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word_id INTEGER NOT NULL, answer TEXT NOT NULL,
            is_correct INTEGER NOT NULL, created_at TEXT NOT NULL, skill TEXT)"""
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(store, "DB_PATH", str(db))
    return db


def _seed_word(db, text="la confiture"):
    """种一个「已经练出成绩」的词：streak 4、间隔 7 天、错过 2 次。"""
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO words (text, created_at, correct_streak, interval_days, "
        "due_at, wrong_count, last_seen_at) VALUES (?,?,?,?,?,?,?)",
        (text, "2026-08-01T00:00:00", 4, 7, "2026-09-01T00:00:00", 2,
         "2026-08-01T00:00:00"),
    )
    conn.commit()
    wid = conn.execute("SELECT id FROM words WHERE text = ?", (text,)).fetchone()[0]
    conn.close()
    return wid


def test_writes_attempts_with_scan_skill(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path, monkeypatch)
    wid = _seed_word(db)
    assert store.record_scan_page([(wid, True), (wid, False)], "rec_meaning") == 2
    conn = sqlite3.connect(db)
    rows = conn.execute("SELECT skill, is_correct, answer FROM attempts ORDER BY id").fetchall()
    conn.close()
    assert rows == [
        ("rec_meaning", 1, "（扫读·会）"),
        ("rec_meaning", 0, "（扫读·不会）"),
    ]


def test_never_touches_words_srs_state(tmp_path, monkeypatch):
    """本设计的核心不变量。标「不会」之后 words 那一行必须一个字节都没变。"""
    db = _fresh_db(tmp_path, monkeypatch)
    wid = _seed_word(db)
    conn = sqlite3.connect(db)
    before = conn.execute("SELECT * FROM words WHERE id = ?", (wid,)).fetchone()
    conn.close()

    store.record_scan_page([(wid, False)], "rec_produce")

    conn = sqlite3.connect(db)
    after = conn.execute("SELECT * FROM words WHERE id = ?", (wid,)).fetchone()
    conn.close()
    assert after == before


def test_rejects_non_scan_skill(tmp_path, monkeypatch):
    """不许拿这个函数去写有证据的技能——那会绕过 words 的 SRS 更新。"""
    _fresh_db(tmp_path, monkeypatch)
    for bad in ("produce", "transcribe", "meaning", "pron", "morph", ""):
        with pytest.raises(ValueError):
            store.record_scan_page([(1, True)], bad)


def test_empty_page_is_noop(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path, monkeypatch)
    assert store.record_scan_page([], "rec_audio") == 0
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0] == 0
    conn.close()


def test_scan_attempts_are_visible_to_mastery(tmp_path, monkeypatch):
    """扫读的记录要能被 get_attempts_for_words 取到，词表的「认」列才有数据。"""
    db = _fresh_db(tmp_path, monkeypatch)
    wid = _seed_word(db)
    store.record_scan_page([(wid, True)], "rec_meaning")
    got = store.get_attempts_for_words([wid])
    assert wid in got
    assert any(a[2] == "rec_meaning" for a in got[wid])
