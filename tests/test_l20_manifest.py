from pathlib import Path

import manifest


MOVED_VOCAB = {
    "l'économie", "le domaine", "la construction", "varier", "varié",
    "prédominer", "principal", "agricole", "occuper", "vaste", "industriel",
    "à la fois", "l'automobile", "le quartier", "un voisin", "voisin",
    "la salle de bains", "le bain", "un cours d'eau", "l'Allemagne",
    "la pomme de terre", "la betterave", "le tabac", "l'élevage", "un immigré",
    "un travailleur immigré", "dur", "la main-d'œuvre", "le patron", "révolter",
    "l'injustice", "la guerre", "le développement", "les médias", "un isolement",
    "le progrès", "le transport", "une autoroute", "une eau douce", "la liaison",
    "le réseau", "la décentralisation", "l'ordre du jour", "le pouvoir",
    "une activité", "le festival", "le théâtre", "actuellement", "à côté de",
    "aller et retour", "volontiers", "la pauvreté", "l'Europe occidentale",
}


def test_l20_manifest_covers_all_reviewed_species():
    data = manifest.load(str(Path("../L20/manifest.json")))

    assert manifest.validate(data) == []
    assert data["lesson"] == "L20"
    assert data["coverage"]["source_type"] == "within_region_species"
    assert data["coverage"]["expected_species_count"] == 68

    cards = manifest.checkpoints(data)
    assert len(cards) == 68
    assert len({card["source_species"] for card in cards}) == 68
    assert all(card.get("curated") for card in cards)
    assert all(card.get("front") and card.get("back") for card in cards)
    assert all(card.get("evidence_refs") for card in cards)
    assert not any(card["front"].startswith("【") for card in cards)
    assert not any("用法语怎么说" in card["front"] for card in cards)


def test_l20_manifest_keeps_dictation_vocab():
    data = manifest.load(str(Path("../L20/manifest.json")))
    vocab = manifest.vocab_items(data)

    assert len(vocab) == 123
    assert len({item["fr"] for item in vocab}) == 123
    assert MOVED_VOCAB <= {item["fr"] for item in vocab}
    assert not any(item["fr"] == "les medias" for item in vocab)
    assert any(item["fr"] == "s'enrichir" for item in vocab)
    assert any(item["fr"] == "l'Europe occidentale" for item in vocab)


def test_l20_manifest_has_machine_and_self_review_cards():
    cards = manifest.checkpoints(manifest.load("../L20/manifest.json"))

    assert any(card.get("answer") is not None for card in cards)
    assert any(card.get("answer") is None for card in cards)
