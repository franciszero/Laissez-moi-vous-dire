from __future__ import annotations

import pytest

import mastery
import scan


def test_rec_skills_match_scan_directions():
    assert mastery.REC_SKILLS == scan.REC_SKILLS


def test_rec_skills_stay_out_of_base():
    """扫读没有拼写证据，不许参与总掌握度。"""
    assert not set(mastery.REC_SKILLS) & set(mastery.BASE_SKILLS)


def test_overall_ignores_rec_skills():
    sc = {"transcribe": 0.9, "produce": 0.8, "meaning": 0.9, "pron": 0.7,
          "rec_meaning": 0.0, "rec_produce": 0.0, "rec_audio": 0.0}
    assert mastery.overall(sc) == pytest.approx(0.7)      # 最弱的是 pron，不是 rec_*


def test_rec_column_takes_the_weakest_direction():
    sc = {"rec_meaning": 0.9, "rec_produce": 0.3, "rec_audio": 0.6}
    assert mastery.overall(sc, skills=mastery.REC_SKILLS) == pytest.approx(0.3)


def test_unscanned_direction_counts_as_zero():
    """只扫过一个方向时「认」是灰的——和既有「没练的算 0」口径一致，不是 bug。"""
    sc = {"rec_meaning": 0.9}
    assert mastery.overall(sc, skills=mastery.REC_SKILLS) == 0.0


def test_skill_scores_isolates_scan_from_typed_skills():
    """同一个词、同一天：扫读标错不许把打字的 meaning 拉下来。"""
    attempts = [
        (True, "2026-08-13T09:00:00", "meaning"),
        (False, "2026-08-13T08:00:00", "rec_meaning"),
    ]
    scores = mastery.skill_scores(attempts)
    assert scores["meaning"] > 0.0
    assert scores["rec_meaning"] == 0.0
