"""全库搜词：词表只列当前一轮的池子，搜索是唯一能到达任意一个词的入口。"""
from __future__ import annotations

from pathlib import Path

import pytest
import vocab


@pytest.fixture(scope="module")
def entries():
    v, _ = vocab.load_all_vocab(Path(".."))
    assert len(v) > 500, "词库没加载起来，测试等于没跑"
    return v


def test_fold_drops_accents_and_case():
    assert vocab.fold("La Sécurité") == "la securite"
    assert vocab.fold("l’intégration") == "l'integration"


def test_search_finds_word_without_accents(entries):
    """记不清 sécurité 上面有没有那一撇，正是要来查的原因。"""
    assert "la sécurité" in vocab.search(entries, "securite")
    assert "la sécurité" in vocab.search(entries, "SÉCU")


def test_search_by_chinese(entries):
    assert "à long terme" in vocab.search(entries, "长期")


def test_shorter_lemma_ranks_first(entries):
    """搜 plat 时想要的多半是 le plat，不是 un plat principal。"""
    hits = vocab.search(entries, "plat")
    assert hits[0] in ("le plat", "un plat"), hits[:3]
    assert "un plat principal" in hits


def test_prefix_beats_substring(entries):
    hits = vocab.search(entries, "integr")
    assert hits, "去重音后应能命中 s'intégrer / l'intégration"
    assert all("ntégr" in h or "ntegr" in h for h in hits)


def test_search_respects_limit_and_empty_query(entries):
    assert vocab.search(entries, "e", limit=5) == vocab.search(entries, "e", limit=5)[:5]
    assert len(vocab.search(entries, "e", limit=5)) <= 5
    assert vocab.search(entries, "") == []
    assert vocab.search(entries, "   ") == []


def test_search_miss_returns_empty(entries):
    assert vocab.search(entries, "zzzzzznotaword") == []


# ---- 变形：你多半是在别处读到一个变形才来查的 ----

def test_feminine_form_finds_its_lemma(entries):
    """intéressant 的 fem 字段字面就是 intéressante，但搜索一度不看这个字段——
    110 个带阴性的词整类搜不到。"""
    assert "intéressant" in vocab.search(entries, "intéressante")
    assert "intelligent" in vocab.search(entries, "intelligente")


def test_feminine_match_outranks_a_coincidental_substring(entries):
    """cliente 是 un client 的阴性；une clientèle 只是碰巧含这几个字母。"""
    hits = vocab.search(entries, "cliente")
    assert hits[0] in ("client", "un client"), hits[:3]


def test_plural_finds_the_singular(entries):
    assert "le plat" in vocab.search(entries, "plats")
    assert "la sécurité" in vocab.search(entries, "sécurités")


def test_direct_hit_still_ranks_first(entries):
    hits = vocab.search(entries, "plat")
    assert hits[0] in ("le plat", "un plat"), hits[:3]


def test_lemmatizer_does_not_confuse_lookalikes(entries):
    """plateformes 的原型是 plateforme，不是 plat——手写的「前缀 + 容忍几个字母」
    会把它错配到 le plat 上，查表式还原不会。"""
    assert "le plat" not in vocab.search(entries, "plateformes")
    assert vocab.lemma_of("plateformes") == "plateforme"


def test_conjugated_verb_resolves_to_its_infinitive(entries):
    """手写规则做不到这个：irai → aller 是不规则变位，没有可套的后缀模式。"""
    assert vocab.lemma_of("irai") == "aller"
    assert vocab.lemma_of("dégusterez") == "déguster"
    assert vocab.lemma_of("allés") == "aller"


def test_irregular_feminine_resolves(entries):
    """coûteuse → coûteux 也不是「去掉一个 e」能办到的。"""
    assert vocab.lemma_of("coûteuse") == "coûteux"
    assert "coûteux" in vocab.search(entries, "coûteuse")


def test_lemmatizer_leaves_non_french_alone(entries):
    """中文、多词短语、已是原型的词都不能被改坏。"""
    for w in ("长期", "à long terme", "intéressant", "le plat", "L35"):
        assert vocab.lemma_of(w) == w, w
    assert "à long terme" in vocab.search(entries, "长期")


def test_near_suggests_when_search_finds_nothing(entries):
    assert vocab.search(entries, "intéressassion") == []
    assert "intéressant" in vocab.near(entries, "intéressassion")


def test_near_stays_quiet_on_garbage_and_short_input(entries):
    assert vocab.near(entries, "zzzznope") == []
    assert vocab.near(entries, "ab") == []
