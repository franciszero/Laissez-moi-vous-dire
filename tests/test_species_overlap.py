"""跨课知识点重复检测的行为约束。"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

from species_overlap_report import (  # noqa: E402
    find_overlaps,
    load_species,
    normalize_item,
    render,
)


def _species(lesson, label, items, status="reviewed", primary_class="lexical_usage"):
    return {
        "adjudication_status": status,
        "lesson": lesson,
        "species_label": label,
        "primary_class": primary_class,
        "french_items": items,
    }


def _write(tmp_path, lesson, entries):
    path = tmp_path / f"{lesson}.species.json"
    path.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    return path


def test_cross_lesson_shared_item_is_reported(tmp_path):
    _write(tmp_path, "L37", [_species("L37", "entretien is a job interview", ["un entretien"])])
    _write(tmp_path, "L38", [_species("L38", "dictation replays reading", ["un entretien"])])

    hits = find_overlaps(load_species(tmp_path))

    assert len(hits) == 1
    assert hits[0]["shared"] == ["entretien"]
    # 课号小的排在左边
    assert hits[0]["a"]["lesson"] == "L37"
    assert hits[0]["b"]["lesson"] == "L38"


def test_same_lesson_overlap_is_not_reported(tmp_path):
    _write(
        tmp_path,
        "L38",
        [
            _species("L38", "card one", ["une boutique"]),
            _species("L38", "card two", ["une boutique"]),
        ],
    )

    assert find_overlaps(load_species(tmp_path)) == []


def test_article_difference_still_matches(tmp_path):
    """le quartier / quartier 归一化后是同一项——冠词不该让重复漏网。"""
    _write(tmp_path, "L37", [_species("L37", "left", ["le quartier"])])
    _write(tmp_path, "L38", [_species("L38", "right", ["quartier"])])

    hits = find_overlaps(load_species(tmp_path))

    assert len(hits) == 1
    assert hits[0]["shared"] == ["quartier"]


def test_une_is_stripped_whole_not_leaving_a_stray_e():
    """正则交替顺序的回归：une 必须整体去掉，不能只吃掉 un。"""
    assert normalize_item("une boutique") == "boutique"
    assert normalize_item("une épreuve") == "épreuve"
    assert normalize_item("un entretien") == "entretien"
    assert normalize_item("de la soupe") == "soupe"


def test_unreviewed_species_are_ignored(tmp_path):
    _write(tmp_path, "L37", [_species("L37", "left", ["un entretien"])])
    _write(
        tmp_path,
        "L38",
        [_species("L38", "right", ["un entretien"], status="draft")],
    )

    assert find_overlaps(load_species(tmp_path)) == []


def test_lesson_filter_limits_the_pairs(tmp_path):
    _write(tmp_path, "L36", [_species("L36", "a", ["un chauffeur"])])
    _write(tmp_path, "L37", [_species("L37", "b", ["un chauffeur"])])
    _write(tmp_path, "L38", [_species("L38", "c", ["un chauffeur"])])

    rows = load_species(tmp_path)

    assert len(find_overlaps(rows)) == 3           # L36-L37, L36-L38, L37-L38
    assert len(find_overlaps(rows, "L38")) == 2    # 只剩带 L38 的那两组


def test_report_says_so_when_there_is_nothing(tmp_path):
    _write(tmp_path, "L37", [_species("L37", "left", ["un entretien"])])
    _write(tmp_path, "L38", [_species("L38", "right", ["une boutique"])])

    rows = load_species(tmp_path)
    text = render(rows, find_overlaps(rows), None)

    assert "未发现跨课重复 ✅" in text
