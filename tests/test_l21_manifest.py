from pathlib import Path

import manifest


def test_l21_manifest_covers_all_reviewed_species():
    data = manifest.load(str(Path("../L21/manifest.json")))
    assert manifest.validate(data) == []
    assert data["coverage"]["source_type"] == "within_region_species"
    assert data["coverage"]["expected_species_count"] == 73

    cards = manifest.checkpoints(data)
    species_cards = [c for c in cards if c.get("source_species")]
    assert len(species_cards) == 73
    assert len({c["source_species"] for c in species_cards}) == 73
    assert all(c.get("front") and c.get("back") for c in species_cards)
    assert all(c.get("evidence_refs") for c in species_cards)


def test_l21_manifest_has_pronoun_review_without_worksheet_answers():
    data = manifest.load(str(Path("../L21/manifest.json")))
    cards = manifest.checkpoints(data)
    pronoun_cards = [c for c in cards if "mixed-pronoun-review" in c.get("tags", [])]
    assert len(pronoun_cards) == 12
    assert all(not c.get("answer") for c in pronoun_cards)
    assert all(not c.get("source_species") for c in pronoun_cards)
    assert any("重新做这个题" in c.get("back", "") for c in pronoun_cards)


def test_l21_manifest_keeps_vocab_items():
    data = manifest.load(str(Path("../L21/manifest.json")))
    vocab = manifest.vocab_items(data)
    assert len(vocab) == 94
    assert any(v["fr"] == "le quartier" for v in vocab)
