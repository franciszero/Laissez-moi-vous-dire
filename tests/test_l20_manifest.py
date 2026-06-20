from pathlib import Path

import manifest


def test_l20_manifest_covers_all_reviewed_species():
    data = manifest.load(str(Path("../L20/manifest.json")))

    assert manifest.validate(data) == []
    assert data["lesson"] == "L20"
    assert data["coverage"]["source_type"] == "within_region_species"
    assert data["coverage"]["expected_species_count"] == 118

    cards = manifest.checkpoints(data)
    assert len(cards) == 118
    assert len({card["source_species"] for card in cards}) == 118
    assert all(card.get("curated") for card in cards)
    assert all(card.get("front") and card.get("back") for card in cards)
    assert all(card.get("evidence_refs") for card in cards)
    assert not any(card["front"].startswith("【") for card in cards)


def test_l20_manifest_keeps_dictation_vocab():
    data = manifest.load(str(Path("../L20/manifest.json")))
    vocab = manifest.vocab_items(data)

    assert len(vocab) == 120
    assert len({item["fr"] for item in vocab}) == 120
    assert any(item["fr"] == "s'enrichir" for item in vocab)
    assert any(item["fr"] == "l'Europe occidentale" for item in vocab)


def test_l20_manifest_has_machine_and_self_review_cards():
    cards = manifest.checkpoints(manifest.load("../L20/manifest.json"))

    assert any(card.get("answer") is not None for card in cards)
    assert any(card.get("answer") is None for card in cards)
