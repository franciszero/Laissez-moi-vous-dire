from __future__ import annotations

import json
import sqlite3
from datetime import datetime

import srs

DB_PATH = "dictation.db"


def get_conn():
    return sqlite3.connect(DB_PATH)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def import_vocab_into_db(vocab) -> int:
    """把词表里的新 lemma 插入 words 表（已存在跳过）。返回新插入数。"""
    conn = get_conn()
    cur = conn.cursor()
    inserted = 0
    for lemma in vocab:
        try:
            cur.execute("INSERT INTO words (text, created_at) VALUES (?, ?)", (lemma, _now()))
            inserted += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()
    return inserted


def get_ids_for_lemmas(lemmas) -> list[int]:
    lemmas = list(lemmas)
    if not lemmas:
        return []
    conn = get_conn()
    ph = ",".join(["?"] * len(lemmas))
    rows = conn.execute(f"SELECT id FROM words WHERE text IN ({ph})", lemmas).fetchall()
    conn.close()
    return [r[0] for r in rows]


def _ensure_state_table(conn) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS app_state (key TEXT PRIMARY KEY, value TEXT)")


def save_round(data: dict) -> None:
    """把当前一轮听写状态存进 DB（单行 JSON），刷新/重开可续上。"""
    conn = get_conn()
    _ensure_state_table(conn)
    conn.execute(
        "INSERT INTO app_state (key, value) VALUES ('round', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (json.dumps(data),),
    )
    conn.commit()
    conn.close()


def load_round() -> dict | None:
    conn = get_conn()
    _ensure_state_table(conn)
    row = conn.execute("SELECT value FROM app_state WHERE key = 'round'").fetchone()
    conn.close()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except ValueError:
        return None


def clear_round() -> None:
    conn = get_conn()
    _ensure_state_table(conn)
    conn.execute("DELETE FROM app_state WHERE key = 'round'")
    conn.commit()
    conn.close()


def save_setting(key: str, value) -> None:
    """存一个跨刷新/重开都记住的小设置（比如上次选的课）。"""
    conn = get_conn()
    _ensure_state_table(conn)
    conn.execute(
        "INSERT INTO app_state (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (f"setting:{key}", json.dumps(value)),
    )
    conn.commit()
    conn.close()


def load_setting(key: str, default=None):
    conn = get_conn()
    _ensure_state_table(conn)
    row = conn.execute(
        "SELECT value FROM app_state WHERE key = ?", (f"setting:{key}",)
    ).fetchone()
    conn.close()
    if not row:
        return default
    try:
        return json.loads(row[0])
    except ValueError:
        return default


def ensure_checkpoint(card_id: str, lesson: str) -> None:
    """首次见到这张卡：建一行 SRS 状态（due=现在，立即可练）。"""
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO checkpoints (card_id, lesson, due_at, created_at) VALUES (?, ?, ?, ?)",
        (card_id, lesson, _now(), _now()),
    )
    conn.commit()
    conn.close()


def get_checkpoint_state(card_ids):
    """{card_id: {correct_streak, interval_days, due_at}}。"""
    card_ids = list(card_ids)
    if not card_ids:
        return {}
    conn = get_conn()
    ph = ",".join(["?"] * len(card_ids))
    rows = conn.execute(
        f"SELECT card_id, correct_streak, interval_days, due_at FROM checkpoints WHERE card_id IN ({ph})",
        card_ids,
    ).fetchall()
    conn.close()
    return {r[0]: {"correct_streak": r[1], "interval_days": r[2], "due_at": r[3]} for r in rows}


def update_checkpoint(card_id: str, ok: bool) -> None:
    """判完一张卡：按 srs 排期写回。"""
    conn = get_conn()
    row = conn.execute(
        "SELECT correct_streak FROM checkpoints WHERE card_id = ?", (card_id,)
    ).fetchone()
    streak = row[0] if row else 0
    ns, ni, due = srs.next_schedule(streak, ok)
    conn.execute(
        "UPDATE checkpoints SET correct_streak = ?, interval_days = ?, due_at = ?, last_seen_at = ? WHERE card_id = ?",
        (ns, ni, due, _now(), card_id),
    )
    conn.commit()
    conn.close()


def get_attempts_for_words(word_ids):
    """返回 {word_id: [(is_correct:bool, created_at:str, skill:str), ...]}（按时间升序）。一次查询。"""
    word_ids = list(word_ids)
    if not word_ids:
        return {}
    conn = get_conn()
    ph = ",".join(["?"] * len(word_ids))
    rows = conn.execute(
        f"SELECT word_id, is_correct, created_at, skill FROM attempts "
        f"WHERE word_id IN ({ph}) ORDER BY created_at",
        word_ids,
    ).fetchall()
    conn.close()
    out: dict = {}
    for wid, ok, ts, skill in rows:
        out.setdefault(wid, []).append((bool(ok), ts, skill or "transcribe"))
    return out
