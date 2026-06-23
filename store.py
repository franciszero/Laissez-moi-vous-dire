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


def get_due_checkpoints(card_ids) -> list[str]:
    """到期该复习的知识点卡 id：due_at<=现在，或从没练过；按到期时间最早优先。"""
    card_ids = list(card_ids)
    if not card_ids:
        return []
    states = get_checkpoint_state(card_ids)
    now = datetime.now()
    due: list[tuple[str, str]] = []
    for cid in card_ids:
        s = states.get(cid)
        if s is None:
            due.append((cid, ""))                          # 没练过：最优先
            continue
        try:
            d = datetime.fromisoformat(s["due_at"]) if s["due_at"] else datetime.min
        except (ValueError, TypeError):
            d = datetime.min
        if d <= now:
            due.append((cid, s["due_at"] or ""))
    due.sort(key=lambda t: t[1])
    return [cid for cid, _ in due]


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


def _ensure_ai_attempts_table(conn) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS ai_attempts ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, cue_id TEXT, created_at TEXT, "
        "answer TEXT, verdict TEXT, minimal TEXT, natural TEXT, feedback TEXT, "
        "hint_level TEXT, model TEXT)"
    )


def save_ai_attempt(cue_id, answer, *, verdict, minimal="", natural="",
                    feedback=None, hint_level="", model="") -> None:
    """存一次 AI 精练作答（含 spans，供「上次→这次」回翻重新染色）。"""
    conn = get_conn()
    _ensure_ai_attempts_table(conn)
    conn.execute(
        "INSERT INTO ai_attempts "
        "(cue_id, created_at, answer, verdict, minimal, natural, feedback, hint_level, model) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (cue_id, _now(), answer, verdict, minimal, natural,
         json.dumps(feedback or [], ensure_ascii=False), hint_level, model),
    )
    conn.commit()
    conn.close()


def get_ai_attempts(cue_id, limit=5) -> list[dict]:
    """同题历次作答，最近在前（自包含：不依赖规范版本）。"""
    conn = get_conn()
    _ensure_ai_attempts_table(conn)
    rows = conn.execute(
        "SELECT created_at, answer, verdict, minimal, natural, feedback, hint_level "
        "FROM ai_attempts WHERE cue_id = ? ORDER BY id DESC LIMIT ?",
        (cue_id, limit),
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        try:
            fb = json.loads(r[5]) if r[5] else []
        except ValueError:
            fb = []
        out.append({"created_at": r[0], "answer": r[1], "verdict": r[2], "minimal": r[3],
                    "natural": r[4], "feedback": fb, "hint_level": r[6]})
    return out


def _ensure_checkpoint_attempts_table(conn) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS checkpoint_attempts ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, card_id TEXT, created_at TEXT, "
        "user_answer TEXT, correct INTEGER)"
    )


def save_checkpoint_attempt(card_id: str, user_answer, correct: bool) -> None:
    """记一次知识点卡作答历史（机判/自评）。AI 产出题不走这里——它进 ai_attempts，避免双写。"""
    conn = get_conn()
    _ensure_checkpoint_attempts_table(conn)
    conn.execute(
        "INSERT INTO checkpoint_attempts (card_id, created_at, user_answer, correct) VALUES (?,?,?,?)",
        (card_id, _now(), user_answer, 1 if correct else 0),
    )
    conn.commit()
    conn.close()


def get_checkpoint_attempts(card_id: str, limit: int = 3) -> list[dict]:
    """同一张知识点卡的历次作答，最近在前。"""
    conn = get_conn()
    _ensure_checkpoint_attempts_table(conn)
    rows = conn.execute(
        "SELECT created_at, user_answer, correct FROM checkpoint_attempts "
        "WHERE card_id = ? ORDER BY id DESC LIMIT ?",
        (card_id, limit),
    ).fetchall()
    conn.close()
    return [{"created_at": r[0], "user_answer": r[1], "correct": bool(r[2])} for r in rows]


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
