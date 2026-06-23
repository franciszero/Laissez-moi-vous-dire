import pytest

import conjugate


def test_parler_group1():
    c = conjugate.conjugate("parler", "er")
    assert c["présent"] == ("parle", "parles", "parle", "parlons", "parlez", "parlent")
    assert c["imparfait"] == ("parlais", "parlais", "parlait", "parlions", "parliez", "parlaient")
    assert c["futur_simple"] == ("parlerai", "parleras", "parlera", "parlerons", "parlerez", "parleront")
    assert c["conditionnel"] == ("parlerais", "parlerais", "parlerait", "parlerions", "parleriez", "parleraient")
    assert c["futur_proche"][0] == "vais parler" and c["futur_proche"][3] == "allons parler"
    assert c["participe_passé"] == "parlé"


def test_finir_group2():
    c = conjugate.conjugate("finir", "ir2")
    assert c["présent"] == ("finis", "finis", "finit", "finissons", "finissez", "finissent")
    assert c["imparfait"] == ("finissais", "finissais", "finissait", "finissions", "finissiez", "finissaient")
    assert c["futur_simple"] == ("finirai", "finiras", "finira", "finirons", "finirez", "finiront")
    assert c["participe_passé"] == "fini"


def test_attendre_group3_regular():
    c = conjugate.conjugate("attendre", "re")
    assert c["présent"] == ("attends", "attends", "attend", "attendons", "attendez", "attendent")
    assert c["futur_simple"] == ("attendrai", "attendras", "attendra", "attendrons", "attendrez", "attendront")
    assert c["participe_passé"] == "attendu"


def test_ger_spelling_softening():
    c = conjugate.conjugate("changer", "er")
    assert c["présent"][3] == "changeons"          # nous：g 前补 e
    assert c["présent"][5] == "changent"           # ils：无 a/o，不补
    assert c["imparfait"] == ("changeais", "changeais", "changeait", "changions", "changiez", "changeaient")


def test_unknown_type_rejected():
    with pytest.raises(KeyError):
        conjugate.conjugate("aller", "irregular")  # 不规则不在此生成
