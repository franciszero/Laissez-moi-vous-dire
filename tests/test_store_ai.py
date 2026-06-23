from datetime import datetime, timedelta

import store


def test_get_due_checkpoints_filters_and_orders(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "c.db"))
    conn = store.get_conn()
    conn.execute(
        "CREATE TABLE checkpoints (card_id TEXT PRIMARY KEY, lesson TEXT, "
        "correct_streak INTEGER DEFAULT 0, interval_days INTEGER DEFAULT 0, "
        "due_at TEXT, last_seen_at TEXT, created_at TEXT)"
    )
    past = (datetime.now() - timedelta(days=2)).isoformat(timespec="seconds")
    future = (datetime.now() + timedelta(days=5)).isoformat(timespec="seconds")
    conn.executemany(
        "INSERT INTO checkpoints (card_id, lesson, due_at, created_at) VALUES (?,?,?,?)",
        [("due-old", "L22", past, past), ("not-due", "L22", future, future)],
    )
    conn.commit()
    conn.close()
    due = store.get_due_checkpoints(["never-practiced", "due-old", "not-due"])
    assert "not-due" not in due                 # 未到期：不推
    assert "due-old" in due                     # 已到期：推
    assert due[0] == "never-practiced"          # 没练过：最优先
    assert store.get_due_checkpoints([]) == []


def test_checkpoint_attempts_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "h.db"))
    store.save_checkpoint_attempt("L22:practice:demo-celle-voiture", "Ceux", False)
    store.save_checkpoint_attempt("L22:practice:demo-celle-voiture", "Celle", True)
    store.save_checkpoint_attempt("L22:species:some-self-judge", None, True)   # 自评：无答案
    rows = store.get_checkpoint_attempts("L22:practice:demo-celle-voiture")
    assert len(rows) == 2
    assert rows[0] == {"created_at": rows[0]["created_at"], "user_answer": "Celle", "correct": True}
    assert rows[1]["user_answer"] == "Ceux" and rows[1]["correct"] is False     # 最近在前
    self_rows = store.get_checkpoint_attempts("L22:species:some-self-judge")
    assert self_rows[0]["user_answer"] is None and self_rows[0]["correct"] is True
    assert store.get_checkpoint_attempts("never-answered") == []


def test_ai_attempts_roundtrip_recent_first(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "t.db"))
    store.save_ai_attempt(
        "cue1", "ils habite en Paris", verdict="我错",
        minimal="ils habitent à Paris", natural="Ils habitent à Paris.",
        feedback=[{"片段": "en Paris", "状态": "错误"}], hint_level="词表", model="m",
    )
    store.save_ai_attempt(
        "cue1", "ils habitent à Paris", verdict="我对",
        feedback=[{"片段": "ils habitent à Paris", "状态": "正确"}],
    )
    rows = store.get_ai_attempts("cue1")
    assert len(rows) == 2
    assert rows[0]["verdict"] == "我对"                     # 最近在前
    assert rows[1]["hint_level"] == "词表"
    assert rows[1]["feedback"][0]["状态"] == "错误"          # spans 可回放重新染色
    assert store.get_ai_attempts("untouched-cue") == []
