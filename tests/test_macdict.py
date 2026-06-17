import macdict


def test_looks_french():
    assert macdict._looks_french("réfrigérateur nom masculin Appareil…")
    assert macdict._looks_french("drôle adjectif Amusant, comique")
    assert not macdict._looks_french("manger | ˈmānjər | noun a long open box")


def test_strip_article():
    assert macdict._strip_article("le réfrigérateur") == "réfrigérateur"
    assert macdict._strip_article("l'eau") == "eau"
    assert macdict._strip_article("augmenter") == "augmenter"


def test_define_suppresses_english(monkeypatch):
    monkeypatch.setattr(macdict, "_AVAILABLE", True)
    monkeypatch.setattr(macdict, "_raw_lookup", lambda w: "manger | ˈmānjər | noun a trough")
    assert macdict.define("manger") is None


def test_define_returns_french(monkeypatch):
    monkeypatch.setattr(macdict, "_AVAILABLE", True)
    monkeypatch.setattr(macdict, "_raw_lookup", lambda w: "drôle adjectif Amusant, comique")
    assert macdict.define("drôle").startswith("drôle adjectif")


def test_define_unavailable(monkeypatch):
    monkeypatch.setattr(macdict, "_AVAILABLE", False)
    assert macdict.define("drôle") is None
