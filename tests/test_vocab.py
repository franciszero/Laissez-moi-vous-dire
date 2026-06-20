import json

from vocab import (
    clean_lemma,
    derive_pos,
    parse_lesson_table,
    load_all_vocab,
    parse_uploaded,
    feminine_form,
    split_gender,
)


def test_parse_uploaded_2col_and_3col_tab_and_comma():
    text = (
        "le chat\t猫\n"                      # 2 列 tab
        "VERBES\tmanger v. t.\t吃\n"          # 3 列 tab
        "le chien,狗\n"                       # 2 列 逗号
        "\n"                                   # 空行跳过
        "badline\n"                            # 只有 1 列 -> skip
    )
    entries, skipped = parse_uploaded(text, lesson="L19")
    assert entries[0] == {"lemma": "le chat", "pos": "expr", "zh": "猫",
                          "lesson": "L19", "source_lesson": "L19",
                          "category": "", "example": None, "raw": "le chat",
                          "fem": None, "fem_raw": None}
    assert entries[1]["lemma"] == "manger" and entries[1]["pos"] == "verb"
    assert entries[2]["lemma"] == "le chien" and entries[2]["zh"] == "狗"
    assert len(entries) == 3 and skipped == 1


def test_parse_uploaded_markdown_table_and_header():
    text = (
        "| 类别 | Français | 中文 |\n"
        "| --- | --- | --- |\n"
        "| NOMS | la confiture | 果酱 |\n"
        "| AUTRES | en dehors de loc. prép. | 在外面 |\n"
    )
    entries, skipped = parse_uploaded(text, lesson="L20")
    assert [e["lemma"] for e in entries] == ["la confiture", "en dehors de"]
    assert entries[1]["pos"] == "prep"
    assert skipped == 2  # 表头 + 分隔行


def test_clean_lemma_strips_grammar_abbr_and_ipa_and_notes():
    cases = {
        "la confiture": "la confiture",
        "un sandwich [sãdwitʃ]": "un sandwich",
        "l'eau n. f.": "l'eau",
        "les gens n. m. pl.": "les gens",
        "sentir v. t.": "sentir",
        "approcher v. t. ind": "approcher",
        "augmenter v. i. ou v. t.": "augmenter",
        "prévoir v. t.（变位同 voir）": "prévoir",
        "choisir v. t.（第二组动词）": "choisir",
        "peu adv.": "peu",
        "en dehors de loc. prép.": "en dehors de",
        "d'autre part loc. adv.": "d'autre part",
        "or conj.": "or",
        "Parisien, ne": "Parisien",
        "client, e": "client",
        "conducteur, trice": "conducteur",
        "délicieux, se": "délicieux",
        "tenir compte de": "tenir compte de",
        "se garer": "se garer",
        "à la place de": "à la place de",
        "un hors-d'œuvre": "un hors-d'œuvre",
    }
    for raw, expected in cases.items():
        assert clean_lemma(raw) == expected, raw


def test_derive_pos():
    assert derive_pos("NOMS", "la confiture") == "noun"
    assert derive_pos("VERBES", "manger v. t.") == "verb"
    assert derive_pos("ADJECTIFS", "délicieux, se") == "adj"
    assert derive_pos("AUTRES", "peu adv.") == "adverb"
    assert derive_pos("AUTRES", "or conj.") == "conj"
    assert derive_pos("AUTRES", "en dehors de loc. prép.") == "prep"
    assert derive_pos("AUTRES", "à table") == "expr"


def test_parse_lesson_table():
    raw = (
        "NOMS\tla confiture\t果酱\n"
        "VERBES\tprévoir v. t.（变位同 voir）\t预备\n"
        "AUTRES\ten dehors de loc. prép.\t在……外面\n"
        "\n"  # 空行跳过
    )
    rows = parse_lesson_table(raw, lesson="L18", source_lesson="Leçon25")
    assert rows[0] == {
        "lemma": "la confiture", "pos": "noun", "zh": "果酱",
        "lesson": "L18", "source_lesson": "Leçon25",
        "category": "NOMS", "example": None, "raw": "la confiture",
        "fem": None, "fem_raw": None,
    }
    assert rows[1]["lemma"] == "prévoir" and rows[1]["pos"] == "verb"
    assert rows[2]["lemma"] == "en dehors de" and rows[2]["pos"] == "prep"
    assert len(rows) == 3


def test_feminine_form_rules():
    f = feminine_form
    assert f("court", "e") == "courte"
    assert f("épicier", "ère") == "épicière"
    assert f("chanteur", "euse") == "chanteuse"
    assert f("conducteur", "trice") == "conductrice"
    assert f("délicieux", "se") == "délicieuse"
    assert f("neuf", "ve") == "neuve"
    assert f("Parisien", "ne") == "Parisienne"
    assert f("naturel", "le") == "naturelle"
    assert f("occidental", "occidentale") == "occidentale"   # 完整词
    assert f("beau", "belle") == "belle"                      # 完整词
    assert f("autonome", None) is None                        # 无标记
    assert f("secret", "ète") is None                         # 拿不准 -> None


def test_split_gender():
    assert split_gender("court, e") == ("court", "e")
    assert split_gender("occidental, occidentale (adj; x)") == ("occidental", "occidentale")
    assert split_gender("autonome") == ("autonome", None)


def test_parse_uploaded_captures_fem():
    text = "ADJECTIFS\tcourt, e\t短的\nADJECTIFS\tautonome\t自主的"
    entries, _ = parse_uploaded(text, lesson="LX")
    by = {e["lemma"]: e for e in entries}
    assert by["court"]["fem"] == "courte"
    assert by["court"]["fem_raw"] == "e"
    assert by["autonome"]["fem"] is None


def test_load_all_vocab(tmp_path):
    base = tmp_path / "本地录屏课"
    (base / "L17").mkdir(parents=True)
    (base / "L18").mkdir(parents=True)
    (base / "L17" / "vocab.json").write_text(json.dumps(
        [{"lemma": "aussi", "pos": "adverb", "zh": "也", "lesson": "L17",
          "source_lesson": "Leçon25", "category": "AUTRES", "example": None, "raw": "aussi adv."}],
        ensure_ascii=False), "utf-8")
    (base / "L18" / "vocab.json").write_text(json.dumps(
        [{"lemma": "aussi", "pos": "adverb", "zh": "也", "lesson": "L18",
          "source_lesson": "Leçon25", "category": "AUTRES", "example": None, "raw": "aussi adv."},
         {"lemma": "la confiture", "pos": "noun", "zh": "果酱", "lesson": "L18",
          "source_lesson": "Leçon23", "category": "NOMS", "example": None, "raw": "la confiture"}],
        ensure_ascii=False), "utf-8")

    # 非 "L" 开头的自定义课，也要被扫到（脱离命名约束）
    (base / "考试集").mkdir()
    (base / "考试集" / "vocab.json").write_text(json.dumps(
        [{"lemma": "bonjour", "pos": "expr", "zh": "你好", "lesson": "考试集",
          "source_lesson": "考试集", "category": "", "example": None, "raw": "bonjour"}],
        ensure_ascii=False), "utf-8")

    by_lemma, by_lesson = load_all_vocab(base)
    assert by_lemma["la confiture"]["zh"] == "果酱"
    assert set(by_lemma["aussi"]["lessons"]) == {"L17", "L18"}   # 跨课合并
    assert by_lesson["L18"] == ["aussi", "la confiture"]
    assert by_lesson["L17"] == ["aussi"]
    assert by_lesson["考试集"] == ["bonjour"]   # 任意文件夹名都能识别


def test_load_all_vocab_keeps_per_lesson_zh(tmp_path):
    # 同一个词在不同课释义不同时，要分课保留（避免按字母序的课覆盖掉当前课的释义）
    base = tmp_path / "本地录屏课"
    (base / "L20").mkdir(parents=True)
    (base / "L21").mkdir(parents=True)
    (base / "L20" / "vocab.json").write_text(json.dumps(
        [{"lemma": "volontiers", "pos": "expr", "zh": "乐意地，很愿意", "lesson": "L20"}],
        ensure_ascii=False), "utf-8")
    (base / "L21" / "vocab.json").write_text(json.dumps(
        [{"lemma": "volontiers", "pos": "expr", "zh": "欣然，乐意地", "lesson": "L21"}],
        ensure_ascii=False), "utf-8")
    by_lemma, _ = load_all_vocab(base)
    per = by_lemma["volontiers"]["zh_by_lesson"]
    assert per["L20"] == "乐意地，很愿意"
    assert per["L21"] == "欣然，乐意地"
