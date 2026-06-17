"""间隔复习排期：词与知识点卡共用。答对涨间隔，答错重置。
间隔表与 app.record_attempt 现用值一致 [1,2,4,7,15,30]。"""
from __future__ import annotations

from datetime import datetime, timedelta

INTERVALS = [1, 2, 4, 7, 15, 30]


def next_schedule(correct_streak: int, ok: bool, now: datetime | None = None):
    """返回 (correct_streak, interval_days, due_at_iso)。"""
    now = now or datetime.now()
    if ok:
        streak = correct_streak + 1
        interval = INTERVALS[min(streak - 1, len(INTERVALS) - 1)]
    else:
        streak = 0
        interval = 0
    due = now + timedelta(days=interval)
    return streak, interval, due.isoformat(timespec="seconds")


def checkpoint_mastery_score(correct_streak: int = 0, interval_days: int = 0) -> float:
    """知识点掌握度 0~1：用 SRS 间隔映射，间隔越长越接近绿。"""
    try:
        streak = int(correct_streak or 0)
        interval = int(interval_days or 0)
    except (TypeError, ValueError):
        return 0.0
    if streak <= 0:
        return 0.0
    if interval <= 0:
        return min(1.0, streak / len(INTERVALS))
    for idx, days in enumerate(INTERVALS):
        if interval <= days:
            return (idx + 1) / len(INTERVALS)
    return 1.0
