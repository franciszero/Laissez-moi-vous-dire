from matcher import check_fr, check_zh, check_speech


def test_check_speech_lenient():
    assert check_speech("épicier", "épicier") is True
    assert check_speech("epicier", "épicier") is True       # 重音不敏感
    assert check_speech("Augmenter.", "augmenter") is True  # 标点/大小写不计
    assert check_speech("réfrigerateur", "réfrigérateur") is True  # 容 1 个误差
    assert check_speech("réfrigérateur", "le réfrigérateur") is True  # 冠词可省
    assert check_speech("", "eau") is None
    assert check_speech("chien", "chat") is None            # 差太远 -> 自判


def test_check_fr_accent_strict():
    assert check_fr("épicier", "épicier")
    assert check_fr("Épicier", "épicier")          # 大小写不计
    assert check_fr("  épicier ", "épicier")        # 空格不计
    assert not check_fr("epicier", "épicier")       # 重音算数
    assert not check_fr("epicie", "épicier")
    assert not check_fr("", "épicier")


def test_check_zh_exact_and_senses():
    assert check_zh("水", "水") is True
    assert check_zh("增长", "增长，提高") is True     # 多义并列，命中其一
    assert check_zh("提高", "增长，提高") is True
    assert check_zh(" 提高 ", "增长，提高") is True   # 空格不计


def test_check_zh_placeholder_skeleton():
    assert check_zh("在某事之前", "在...之前") is True   # 占位符骨架
    assert check_zh("在...之前", "在...之前") is True
    assert check_zh("在……之前", "在...之前") is True     # 全角省略号
    assert check_zh("在某之前", "在...之前") is True


def test_check_zh_uncertain_returns_none():
    assert check_zh("增加", "增长，提高") is None       # 近义但不同 -> 自判
    assert check_zh("火", "水") is None
    assert check_zh("", "水") is None
