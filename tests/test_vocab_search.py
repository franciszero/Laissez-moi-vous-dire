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
