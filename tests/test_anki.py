import anki
from anki import html_to_text, first_example


def test_html_to_text():
    assert html_to_text('<div class="x"><p>用于正式场合</p></div>') == "用于正式场合"
    assert html_to_text('a<br>b') == "a b"
    assert html_to_text('Tom &amp; Jerry') == "Tom & Jerry"
    assert html_to_text("") == ""


def test_first_example():
    html = ('<ul class="examples"><li><span class="sentence">Allez-y, je vous écoute.</span></li>'
            '<li><span class="sentence">Deuxième phrase.</span></li></ul>')
    assert first_example(html) == "Allez-y, je vous écoute."


def test_enrich_hit(monkeypatch):
    def fake(action, **params):
        if action == "findNotes":
            return [111]
        if action == "notesInfo":
            return [{"note": 111, "fields": {
                "Lemma": {"value": '<span class="targetword">augmenter</span>'},
                "Core Meaning": {"value": "<p>增长，提高</p>"},
                "Example Sentences": {"value": '<ul><li><span>Les prix augmentent.</span></li></ul>'},
                "IPA + Pronunciation Notes": {"value": "<p>/ɔɡmɑ̃te/</p>"},
            }}]
        return []
    monkeypatch.setattr(anki, "_anki", fake)
    out = anki.enrich("augmenter")
    assert out["core_meaning"] == "增长，提高"
    assert out["example"] == "Les prix augmentent."
    assert "ɔɡm" in out["ipa"]


def test_enrich_degrades_when_anki_down(monkeypatch):
    def boom(action, **params):
        raise OSError("connection refused")
    monkeypatch.setattr(anki, "_anki", boom)
    assert anki.enrich("augmenter") is None


def test_enrich_returns_none_on_wrong_lemma(monkeypatch):
    # 模拟 l'eau 搜不到自己、却搜到含 "eau" 的别的卡 -> 必须返回 None，不能瞎显示
    def fake(action, **params):
        if action == "findNotes":
            return [999]
        if action == "notesInfo":
            return [{"note": 999, "fields": {
                "Lemma": {"value": '<span class="targetword">entrer</span>'},
                "Core Meaning": {"value": "<p>进入</p>"},
            }}]
        return []
    monkeypatch.setattr(anki, "_anki", fake)
    assert anki.enrich("l'eau") is None


def test_render_card_returns_answer(monkeypatch):
    def fake(action, **params):
        if action == "findNotes":
            return [111]
        if action == "notesInfo":
            return [{"noteId": 111, "cards": [222],
                     "fields": {"Lemma": {"value": '<span class="targetword">proche</span>'}}}]
        if action == "cardsInfo":
            return [{"answer": "<style>.card{}</style><div class='card'>proche adjectif</div>"}]
        return []
    monkeypatch.setattr(anki, "_anki", fake)
    html = anki.render_card("proche")
    assert "proche adjectif" in html and "<div class='card'>" in html


def test_render_card_strips_sound(monkeypatch):
    def fake(action, **params):
        if action == "findNotes":
            return [111]
        if action == "notesInfo":
            return [{"noteId": 111, "cards": [222], "fields": {"Lemma": {"value": "proche"}}}]
        if action == "cardsInfo":
            return [{"answer": "hello [sound:x.mp3] world"}]
        return []
    monkeypatch.setattr(anki, "_anki", fake)
    assert anki.render_card("proche") == "hello  world"


def test_render_card_none_when_down(monkeypatch):
    monkeypatch.setattr(anki, "_anki", lambda *a, **k: (_ for _ in ()).throw(OSError("down")))
    assert anki.render_card("proche") is None
