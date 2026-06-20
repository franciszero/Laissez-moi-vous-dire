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
