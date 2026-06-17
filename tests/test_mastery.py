from datetime import datetime, timedelta

import mastery


def test_wilson_lower_basics():
    assert mastery.wilson_lower(0, 0) == 0.0
    assert 0.0 < mastery.wilson_lower(1, 1) < 0.6          # 练一次全对：不确定，偏低
    # 样本越多、全对，置信下界越高（单调）
    seq = [mastery.wilson_lower(n, n) for n in (1, 3, 6, 12, 30)]
    assert seq == sorted(seq)
    assert mastery.wilson_lower(100, 100) > 0.9


def _att(days_ago, ok):
    return (ok, (datetime.now() - timedelta(days=days_ago)).isoformat(timespec="seconds"))


def test_mastery_score():
    now = datetime.now()
    assert mastery.mastery_score([], now) == 0.0
    # 只练一天（哪怕当天刷很多次）→ 偏低（按天聚合，防狂刷）
    cram = [_att(0, True) for _ in range(10)]
    assert mastery.mastery_score(cram, now) < 0.6
    # 跨 6 个不同的近期日子、全对 → 高
    spread = [_att(d, True) for d in range(6)]
    assert mastery.mastery_score(spread, now) > 0.7
    # 同样跨度但近期答错 → 更低
    spread_recent_wrong = [_att(d, d != 0) for d in range(6)]  # 今天错
    assert mastery.mastery_score(spread_recent_wrong, now) < mastery.mastery_score(spread, now)


def test_mastery_first_of_day_anti_gaming():
    now = datetime.now()
    base = now - timedelta(hours=2)
    # 同一天先错后对（刷答案）：按「当天第一次」=错，应低于老老实实第一次就对
    gamed = [(False, base.isoformat()), (True, (base + timedelta(minutes=1)).isoformat())]
    honest = [(True, base.isoformat())]
    assert mastery.mastery_score(gamed, now) < mastery.mastery_score(honest, now)


def test_skill_scores_and_overall():
    now = datetime.now()
    att = [(True, (now - timedelta(days=d)).isoformat(), "form") for d in range(6)]
    att.append((True, now.isoformat(), "meaning"))
    sc = mastery.skill_scores(att)
    assert sc.get("form", 0) > 0.5      # 形练了多天 -> 高
    assert "pron" not in sc             # 音从没练
    assert mastery.overall(sc) == 0.0   # 总掌握 = 最弱（音=0）
    assert mastery.overall({"form": 0.8, "meaning": 0.8, "pron": 0.8}) == 0.8


def test_overall_default_ignores_morph():
    # 默认只看 form/meaning/pron，三项满即满（morph 不拉低）
    assert mastery.overall({"form": 0.8, "meaning": 0.8, "pron": 0.8}) == 0.8


def test_overall_with_morph_applicable():
    sc = {"form": 0.8, "meaning": 0.8, "pron": 0.8, "morph": 0.0}
    # 显式带上 morph 时，morph=0 -> 总掌握 0
    assert mastery.overall(sc, skills=mastery.BASE_SKILLS + ("morph",)) == 0.0
    assert "morph" in mastery.SKILLS


def test_mastery_color():
    g = mastery.mastery_color(0.0)
    y = mastery.mastery_color(0.5)
    grn = mastery.mastery_color(1.0)
    assert g.startswith("#") and len(g) == 7
    assert y.lower() == "#ffd54f"               # 中点为黄
    # 满分偏绿：G 通道明显大于 R 通道
    r, gch, b = int(grn[1:3], 16), int(grn[3:5], 16), int(grn[5:7], 16)
    assert gch > r
