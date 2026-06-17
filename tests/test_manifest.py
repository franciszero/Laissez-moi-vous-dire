import manifest

GOOD = {"lesson": "L21", "source": "x.md", "chunks": [
    {"id": "c1", "bucket": "vocab",
     "items": [{"type": "vocab", "fr": "le quartier", "pos": "nom", "zh": "社区"}]},
    {"id": "c2", "bucket": "checkpoint",
     "items": [{"type": "checkpoint", "id": "L21:c2:0", "front": "f", "back": "b", "answer": None,
                "source_species": "quartier-collocations"}]},
    {"id": "c3", "bucket": "skip"}]}


def test_validate_good():
    assert manifest.validate(GOOD) == []


def test_validate_catches():
    bad = {"lesson": "L21", "source": "x", "chunks": [
        {"id": "c1"},                                            # 缺 bucket
        {"id": "c2", "bucket": "zzz", "items": []},              # bucket 非法 + 非skip空
        {"id": "c3", "bucket": "vocab", "items": []},            # 非 skip 但空
        {"id": "c4", "bucket": "checkpoint",
         "items": [{"type": "checkpoint", "id": "a", "front": "f"}]},  # 缺 back
    ]}
    probs = manifest.validate(bad)
    assert len(probs) >= 4


def test_helpers_extract():
    assert [c["id"] for c in manifest.checkpoints(GOOD)] == ["L21:c2:0"]
    assert [v["fr"] for v in manifest.vocab_items(GOOD)] == ["le quartier"]


def test_validate_species_coverage_contract():
    data = dict(GOOD)
    data["coverage"] = {
        "source_type": "within_region_species",
        "expected_species_count": 1,
    }
    assert manifest.validate(data) == []


def test_validate_species_coverage_catches_missing_and_duplicate():
    data = {"lesson": "L21", "source": "x.md",
            "coverage": {"source_type": "within_region_species", "expected_species_count": 3},
            "chunks": [
                {"id": "c1", "bucket": "checkpoint",
                 "items": [
                     {"type": "checkpoint", "id": "L21:a", "front": "f", "back": "b",
                      "source_species": "same"},
                     {"type": "checkpoint", "id": "L21:b", "front": "f", "back": "b",
                      "source_species": "same"},
                 ]}]}
    probs = manifest.validate(data)
    assert any("source_species 重复" in p for p in probs)
    assert any("species 覆盖数" in p for p in probs)
