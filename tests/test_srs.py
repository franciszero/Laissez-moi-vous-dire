from datetime import datetime

import srs


def test_next_schedule_correct_grows():
    now = datetime(2026, 6, 17, 12, 0, 0)
    s1, i1, d1 = srs.next_schedule(0, True, now)     # 第一次答对
    s2, i2, d2 = srs.next_schedule(s1, True, now)    # 再答对
    assert s1 == 1 and s2 == 2
    assert i2 >= i1 >= 1                              # 间隔不减
    assert d1 > now.isoformat()                       # due 在未来（ISO 字符串可比）


def test_next_schedule_wrong_resets():
    now = datetime(2026, 6, 17, 12, 0, 0)
    s, i, d = srs.next_schedule(5, False, now)
    assert s == 0 and i == 0                          # 答错重置


def test_intervals_match_app():
    # 与 app.record_attempt 现用值一致
    assert srs.INTERVALS == [1, 2, 4, 7, 15, 30]
