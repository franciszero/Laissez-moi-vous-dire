"""一个词的「掌握度」0~1：从历史听写算。
思路：按天聚合（一天只算当天最后一次，避免狂刷刷高）→ 近期加权（半衰期）→
Wilson 置信下界（练得少 = 不确定 = 偏低；练多次 + 跨多天 + 近期高正确率 = 偏高）。
再映射成 灰→黄→绿 渐变色。
"""
from __future__ import annotations

import math
from datetime import datetime

Z = 1.28            # ~80% 单侧置信；越大越保守（越难变绿）
HALFLIFE_DAYS = 14.0  # 近期加权半衰期


def _parse(ts: str):
    try:
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def wilson_lower(correct: float, total: float, z: float = Z) -> float:
    """二项成功率的 Wilson 置信下界。total 小 → 拉低（不确定）。"""
    if total <= 0:
        return 0.0
    phat = correct / total
    z2 = z * z
    centre = phat + z2 / (2 * total)
    margin = z * math.sqrt((phat * (1 - phat) + z2 / (4 * total)) / total)
    return max(0.0, min(1.0, (centre - margin) / (1 + z2 / total)))


def mastery_score(attempts, now: datetime | None = None) -> float:
    """attempts: 可迭代的 (is_correct, created_at_iso)。返回 0~1。"""
    now = now or datetime.now()
    by_day: dict = {}
    for ok, ts in attempts:
        dt = _parse(ts)
        if dt is None:
            continue
        day = dt.date()
        cur = by_day.get(day)
        if cur is None or dt < cur[1]:
            by_day[day] = (bool(ok), dt)   # 当天第一次为准（防「看答案重输」刷分）
    if not by_day:
        return 0.0
    c = t = 0.0
    for ok, dt in by_day.values():
        age = max(0.0, (now - dt).total_seconds() / 86400.0)
        w = 0.5 ** (age / HALFLIFE_DAYS)
        t += w
        if ok:
            c += w
    return wilson_lower(c, t)


BASE_SKILLS = ("transcribe", "produce", "meaning", "pron")
# 听写(音→拼写) / 产出(意→拼写) / 理解(法→意) / 音(发音)，每个词都适用
SKILLS = BASE_SKILLS + ("morph",)           # 变(阴阳性变形)：仅有阴性的词适用


def skill_scores(attempts):
    """attempts: [(is_correct, created_at, skill)]。返回 {skill: 掌握度}。"""
    by_skill: dict = {}
    for ok, ts, skill in attempts:
        by_skill.setdefault(skill or "form", []).append((ok, ts))
    return {sk: mastery_score(v) for sk, v in by_skill.items()}


def overall(skill_to_score: dict, skills=BASE_SKILLS) -> float:
    """一个词的总掌握 = 适用技能里最弱那项（没练的算 0）。默认只看 形/义/音；
    有阴性的词由调用方传 skills=BASE_SKILLS+('morph',)。"""
    return min(float(skill_to_score.get(s, 0.0)) for s in skills)


def _hex(c: str):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def _lerp(c1: str, c2: str, p: float) -> str:
    a, b = _hex(c1), _hex(c2)
    return "#%02x%02x%02x" % tuple(round(a[i] + (b[i] - a[i]) * p) for i in range(3))


def mastery_color(score: float) -> str:
    """0=灰(没记住) → 黄 → 1=绿(记牢)。"""
    s = max(0.0, min(1.0, score))
    if s < 0.5:
        return _lerp("#e6e6e6", "#ffd54f", s / 0.5)
    return _lerp("#ffd54f", "#66bb6a", (s - 0.5) / 0.5)
