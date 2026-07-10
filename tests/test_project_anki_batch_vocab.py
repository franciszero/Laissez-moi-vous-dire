import pytest

from scripts.project_anki_batch_vocab import project_rows


def _anki_line(*, lemma: str, core_meaning: str, collocations: str) -> str:
    fields = ["N/A"] * 15
    fields[0] = f'<span class="targetword">{lemma}</span>'
    fields[2] = '<span class="subtitle">v.t.</span>'
    fields[5] = f'<div class="section-content"><p>{core_meaning}</p></div>'
    fields[10] = (
        '<div class="highlight-box"><ul class="examples"><li>'
        f'<span class="sentence"><b>{collocations}</b></span>'
        '<i class="translation">(瞥一眼)</i></li></ul></div>'
    )
    return "|".join(fields)


def test_projection_uses_core_meaning_without_promoting_collocation_gloss():
    api_payload = {
        "batch_id": "batch-test",
        "items": [
            {
                "decision": "accept",
                "meta": {"word": "jeter", "word_class": "verb"},
                "accepted_unit_audit": {
                    "accepted_target_text": "jeter",
                    "source_sentence_or_context": "Jetez un coup d'œil à cette annonce.",
                },
            }
        ],
    }
    lines = [
        _anki_line(
            lemma="jeter",
            core_meaning="把某物抛出或丢弃，强调主动投掷或去除。",
            collocations="jeter un coup d'œil",
        )
    ]

    rows = project_rows(lines, api_payload)

    assert rows == [
        {
            "lemma": "jeter",
            "pos": "verb",
            "zh": "把某物抛出或丢弃，强调主动投掷或去除。",
            "example": "Jetez un coup d'œil à cette annonce.",
            "raw": "jeter",
            "source_batch": "batch-test",
            "source_decision": "accept",
            "zh_source": "anki_core_meaning",
        }
    ]
    assert "瞥一眼" not in rows[0]["zh"]


def test_projection_fails_closed_when_export_shape_changes():
    with pytest.raises(ValueError, match="expected 15 Anki fields"):
        project_rows(
            ["jeter|too|short"],
            {"batch_id": "batch-test", "items": []},
        )
