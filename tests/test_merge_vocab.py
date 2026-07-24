import json

import pytest

from scripts.merge_vocab import merge_vocab


def _write(path, rows):
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", "utf-8")


def test_merge_vocab_preserves_existing_rows_and_adds_only_missing(tmp_path):
    target = tmp_path / "L20" / "vocab.json"
    target.parent.mkdir()
    existing = {
        "lemma": "volontiers",
        "pos": "adverb",
        "zh": "原释义保留",
        "lesson": "L20",
        "source_lesson": "Leçon28",
        "category": "AUTRES",
        "example": None,
        "raw": "volontiers adv.",
        "fem": None,
        "fem_raw": None,
    }
    _write(target, [existing])

    result = merge_vocab(
        target,
        [
            {"lemma": " volontiers ", "pos": "expr", "zh": "不得覆盖"},
            {"lemma": "l’économie", "pos": "noun", "zh": "经济"},
            {"lemma": "l'économie", "pos": "noun", "zh": "经济"},
            {
                "lemma": "occidental",
                "pos": "adj",
                "zh": "西方的",
                "raw": "occidental, occidentale",
            },
        ],
    )

    rows = json.loads(target.read_text("utf-8"))
    assert rows[0] == existing
    assert [row["lemma"] for row in rows] == ["volontiers", "l'économie", "occidental"]
    assert rows[1]["lesson"] == "L20"
    assert rows[1]["category"] == "NOMS"
    assert rows[2]["fem"] == "occidentale"
    assert rows[2]["fem_raw"] == "occidentale"
    assert result.added == 2
    assert result.provenance_added == 0
    assert result.skipped_existing == 1
    assert result.skipped_duplicate == 1


def test_merge_vocab_is_idempotent(tmp_path):
    target = tmp_path / "L20" / "vocab.json"
    target.parent.mkdir()
    _write(target, [])
    batch = [{"lemma": "la gare", "pos": "noun", "zh": "火车站"}]

    first = merge_vocab(target, batch)
    after_first = target.read_bytes()
    second = merge_vocab(target, batch)

    assert first.added == 1
    assert second.added == 0
    assert second.provenance_added == 0
    assert second.skipped_existing == 1
    assert target.read_bytes() == after_first


def test_merge_vocab_rejects_conflicting_batch_duplicates_without_writing(tmp_path):
    target = tmp_path / "L20" / "vocab.json"
    target.parent.mkdir()
    _write(target, [])
    before = target.read_bytes()

    with pytest.raises(ValueError, match="conflicting duplicate lemma"):
        merge_vocab(
            target,
            [
                {"lemma": "le domaine", "pos": "noun", "zh": "领域"},
                {"lemma": "le domaine", "pos": "noun", "zh": "庄园"},
            ],
        )

    assert target.read_bytes() == before


def _provenance(reason="讲选项关键词时补充的近义词", source_ref="L31:T5Q10:option-B"):
    return {
        "source_kind": "teacher_extension",
        "source_ref": source_ref,
        "teacher_action": "synonym",
        "selection_reason": reason,
        "evidence": {
            "file": "docker-data/outputs/L31/L31_final_working.md",
            "time": "01:12:00-01:13:00",
        },
        "learning_note": "与选项一起理解，但不属于题目原文",
    }


def test_merge_vocab_preserves_provenance_on_new_entry(tmp_path):
    target = tmp_path / "L31" / "vocab.json"
    target.parent.mkdir()
    _write(target, [])

    result = merge_vocab(
        target,
        [{"lemma": "se mettre à", "pos": "verb", "zh": "开始做", "provenance": [_provenance()]}],
    )

    row = json.loads(target.read_text("utf-8"))[0]
    assert row["provenance"] == [_provenance()]
    assert result.added == 1
    assert result.provenance_added == 0


def test_merge_vocab_appends_provenance_to_existing_without_overwriting_fields(tmp_path):
    target = tmp_path / "L31" / "vocab.json"
    target.parent.mkdir()
    existing = {
        "lemma": "se mettre à",
        "pos": "verb",
        "zh": "原释义保留",
        "lesson": "L31",
        "source_lesson": "L31",
        "category": "VERBES",
        "example": "原例句",
        "raw": "se mettre à",
        "fem": None,
        "fem_raw": None,
    }
    _write(target, [existing])

    result = merge_vocab(
        target,
        [{
            "lemma": "se mettre à",
            "pos": "expr",
            "zh": "不得覆盖",
            "example": "不得覆盖",
            "provenance": [_provenance()],
        }],
    )

    row = json.loads(target.read_text("utf-8"))[0]
    for field, value in existing.items():
        assert row[field] == value
    assert row["provenance"] == [_provenance()]
    assert result.added == 0
    assert result.provenance_added == 1
    assert result.skipped_existing == 1


def test_merge_vocab_provenance_is_idempotent_but_distinct_evidence_appends(tmp_path):
    target = tmp_path / "L31" / "vocab.json"
    target.parent.mkdir()
    _write(target, [])
    first_record = _provenance()
    second_record = _provenance(
        reason="复盘题目时再次用来做反义对比",
        source_ref="L31:T5Q10:review",
    )

    merge_vocab(
        target,
        [{"lemma": "se mettre à", "pos": "verb", "zh": "开始做", "provenance": [first_record]}],
    )
    unchanged = target.read_bytes()
    duplicate = merge_vocab(
        target,
        [{"lemma": "se mettre à", "pos": "verb", "zh": "开始做", "provenance": [first_record]}],
    )
    after_duplicate = target.read_bytes()
    appended = merge_vocab(
        target,
        [{"lemma": "se mettre à", "pos": "verb", "zh": "开始做", "provenance": [second_record]}],
    )

    assert duplicate.provenance_added == 0
    assert after_duplicate == unchanged
    assert appended.provenance_added == 1
    row = json.loads(target.read_text("utf-8"))[0]
    assert row["provenance"] == [first_record, second_record]


@pytest.mark.parametrize(
    "provenance, message",
    [
        ({}, "must be an array"),
        ([{"source_kind": "teacher_extension"}], "requires non-empty source_ref"),
        ([{
            "source_kind": "teacher_extension",
            "source_ref": "L31:T5Q10",
            "teacher_action": "explain",
            "selection_reason": "课堂讲解",
            "evidence": {},
        }], "requires non-empty evidence.file"),
    ],
)
def test_merge_vocab_rejects_invalid_provenance_without_writing(tmp_path, provenance, message):
    target = tmp_path / "L31" / "vocab.json"
    target.parent.mkdir()
    _write(target, [])
    before = target.read_bytes()

    with pytest.raises(ValueError, match=message):
        merge_vocab(
            target,
            [{"lemma": "se mettre à", "pos": "verb", "zh": "开始做", "provenance": provenance}],
        )

    assert target.read_bytes() == before
