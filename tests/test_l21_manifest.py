from pathlib import Path

import manifest


def test_l21_manifest_covers_all_reviewed_species():
    data = manifest.load(str(Path("../L21/manifest.json")))
    assert manifest.validate(data) == []
    assert data["coverage"]["source_type"] == "within_region_species"
    assert data["coverage"]["expected_species_count"] == 73

    cards = manifest.checkpoints(data)
    assert len(cards) == 73
    assert len({c["source_species"] for c in cards}) == 73
    assert all(c.get("front") and c.get("back") for c in cards)
    assert all(c.get("evidence_refs") for c in cards)


def test_l21_manifest_keeps_vocab_items():
    data = manifest.load(str(Path("../L21/manifest.json")))
    vocab = manifest.vocab_items(data)
    assert len(vocab) == 94
    assert any(v["fr"] == "le quartier" for v in vocab)
