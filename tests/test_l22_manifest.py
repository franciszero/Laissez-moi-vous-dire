import manifest


OLD_PILOT_IDS = {
    "L22:practice:future-voudrai",
    "L22:practice:conditional-voudrais",
    "L22:practice:future-finirons",
    "L22:practice:conditional-finirions",
    "L22:practice:future-anterior-aura-fini",
    "L22:practice:future-anterior-auront-trouve",
}

ANCHOR_ANSWERS = {
    "L22:practice:form-parler-passe-compose": "j'ai parlé",
    "L22:practice:contrast-parler-imparfait": "je parlais",
    "L22:practice:contrast-parler-futur-simple": "je parlerai",
    "L22:practice:form-parler-futur-anterieur": "j'aurai parlé",
    "L22:practice:contrast-parler-conditionnel": "je parlerais",
    "L22:practice:form-finir-passe-compose": "j'ai fini",
    "L22:practice:form-finir-imparfait": "je finissais",
    "L22:practice:form-finir-futur-simple": "je finirai",
    "L22:practice:form-finir-futur-anterieur": "j'aurai fini",
    "L22:practice:form-finir-conditionnel": "je finirais",
    "L22:practice:form-avoir-passe-compose": "j'ai eu",
    "L22:practice:form-avoir-imparfait": "j'avais",
    "L22:practice:form-avoir-futur-simple": "j'aurai",
    "L22:practice:form-avoir-futur-anterieur": "j'aurai eu",
    "L22:practice:form-avoir-conditionnel": "j'aurais",
    "L22:practice:form-etre-passe-compose": "j'ai été",
    "L22:practice:form-etre-imparfait": "j'étais",
    "L22:practice:form-etre-futur-simple": "je serai",
    "L22:practice:form-etre-futur-anterieur": "j'aurai été",
    "L22:practice:form-etre-conditionnel": "je serais",
    "L22:practice:form-aller-passe-compose": "je suis allé",
    "L22:practice:form-aller-imparfait": "j'allais",
    "L22:practice:form-aller-futur-simple": "j'irai",
    "L22:practice:form-aller-futur-anterieur": "je serai allé",
    "L22:practice:form-aller-conditionnel": "j'irais",
}

ROOT_ANSWERS = {"aur", "ser", "ir", "fer", "devr", "saur", "viendr", "verr", "voudr"}


def test_l22_tense_system_deck_is_complete_and_ordered():
    data = manifest.load("../L22/manifest.json")
    assert manifest.validate(data) == []
    assert data["coverage"]["expected_species_count"] == 103

    cards = manifest.checkpoints(data)
    species_cards = [c for c in cards if c.get("source_species")]
    practice_cards = [c for c in cards if c.get("parent_group") == "future-tense-system"]
    grouped_cards = [c for c in cards if c.get("study_group") == "future-tense-system"]
    by_id = {c["id"]: c for c in cards}

    assert len(cards) == 141
    assert len(species_cards) == 103
    assert len({c["source_species"] for c in species_cards}) == 103
    assert len(practice_cards) == 38
    assert len(grouped_cards) == 57
    assert all(c["study_group_label"] == "时态变位系统" for c in grouped_cards)
    assert all(c.get("curated") for c in practice_cards)
    assert sum(c.get("answer") is not None for c in practice_cards) == 34
    assert sum(c.get("answer") is None for c in practice_cards) == 4
    assert OLD_PILOT_IDS.isdisjoint(by_id)

    assert {card_id: by_id[card_id]["answer"] for card_id in ANCHOR_ANSWERS} == ANCHOR_ANSWERS
    root_cards = [c for c in practice_cards if c["id"].startswith("L22:practice:root-")]
    assert len(root_cards) == 9
    assert {c["answer"] for c in root_cards} == ROOT_ANSWERS

    trio = [
        "L22:practice:contrast-parler-imparfait",
        "L22:practice:contrast-parler-futur-simple",
        "L22:practice:contrast-parler-conditionnel",
    ]
    trio_positions = [cards.index(by_id[card_id]) for card_id in trio]
    assert trio_positions == list(range(trio_positions[0], trio_positions[0] + 3))

    root_overview = next(
        c for c in species_cards
        if c["source_species"] == "memorize irregular future stems and past participles by repeated retrieval"
    )
    assert all(f"{root}-" in root_overview["back"] for root in ROOT_ANSWERS)
