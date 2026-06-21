import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_checkpoints_from_species as builder


def _write_json(path: Path, value) -> Path:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def _species(label: str) -> dict:
    return {
        "species_label": label,
        "adjudication_status": "reviewed",
        "primary_class": "grammar_rule",
        "tags": ["conjugation"],
        "french_items": [],
        "occurrences": [{"ref": f"pass1:{label}"}],
    }


def _vocab() -> list[dict]:
    return [{"lemma": "parler", "pos": "verb", "zh": "说话"}]


def test_checkpoint_groups_sort_cards_and_preserve_species_coverage(tmp_path):
    species_path = _write_json(tmp_path / "species.json", [_species("alpha"), _species("beta")])
    vocab_path = _write_json(tmp_path / "vocab.json", _vocab())
    groups_path = _write_json(
        tmp_path / "groups.json",
        {
            "groups": [
                {
                    "id": "future-tense-system",
                    "label": "将来时系统",
                    "order": 10,
                    "species": [{"source_species": "beta", "order": 10}],
                    "practice_cards": [
                        {
                            "id": "future-ai",
                            "order": 20,
                            "front": "Demain, je parler__.",
                            "back": "简单将来时用 **-ai**。",
                            "answer": "ai",
                        }
                    ],
                }
            ]
        },
    )

    data = builder.build_manifest(
        "Lx", "source.md", species_path, vocab_path, checkpoint_groups_path=groups_path
    )
    cards = builder.manifest.checkpoints(data)

    assert [card.get("source_species") for card in cards] == ["beta", None, "alpha"]
    assert cards[0]["study_group_label"] == "将来时系统"
    assert cards[1]["id"] == "Lx:practice:future-ai"
    assert cards[1]["answer"] == "ai"
    assert cards[1]["parent_group"] == "future-tense-system"
    assert data["coverage"]["expected_species_count"] == 2


def test_checkpoint_groups_reject_unknown_species(tmp_path):
    species_path = _write_json(tmp_path / "species.json", [_species("alpha")])
    vocab_path = _write_json(tmp_path / "vocab.json", _vocab())
    groups_path = _write_json(
        tmp_path / "groups.json",
        {
            "groups": [
                {
                    "id": "future",
                    "label": "将来时系统",
                    "order": 10,
                    "species": [{"source_species": "missing", "order": 10}],
                    "practice_cards": [],
                }
            ]
        },
    )

    with pytest.raises(SystemExit, match="unknown species.*missing"):
        builder.build_manifest(
            "Lx", "source.md", species_path, vocab_path, checkpoint_groups_path=groups_path
        )


def test_checkpoint_groups_reject_duplicate_practice_ids(tmp_path):
    species_path = _write_json(tmp_path / "species.json", [_species("alpha")])
    vocab_path = _write_json(tmp_path / "vocab.json", _vocab())
    practice = {"id": "same", "order": 10, "front": "Q", "back": "A", "answer": "x"}
    groups_path = _write_json(
        tmp_path / "groups.json",
        {
            "groups": [
                {
                    "id": "g1",
                    "label": "组一",
                    "order": 10,
                    "species": [],
                    "practice_cards": [practice],
                },
                {
                    "id": "g2",
                    "label": "组二",
                    "order": 20,
                    "species": [],
                    "practice_cards": [practice],
                },
            ]
        },
    )

    with pytest.raises(SystemExit, match="duplicate practice card id.*same"):
        builder.build_manifest(
            "Lx", "source.md", species_path, vocab_path, checkpoint_groups_path=groups_path
        )
