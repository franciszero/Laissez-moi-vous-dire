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


def test_check_fr_apostrophe_style_unified():
    # 键盘直撇号 ' 判等于词表/Anki 里的弯撇号 ’（只在判分归一，不改任何存储的词）
    assert check_fr("être à l'heure", "être à l’heure")
    assert check_fr("être à l’heure", "être à l'heure")
    assert check_fr("l'eau", "l’eau")
    # 撇号归一不能放松重音严格性
    assert not check_fr("etre à l'heure", "être à l’heure")


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


def test_check_zh_ignores_visible_learning_metadata():
    assert check_zh("调查", "[T4Q12] 调查；民意调查") is True
    assert check_zh("民意调查", "[T4Q12] 调查；民意调查") is True
    assert check_zh("预留的", "[T4Q6/Q11] 预留的；专供的") is True
    assert check_zh("体验", "[T4Q5; T5Q2] 体验") is True
    assert check_zh("相反", "[L30课前复习] 相反；反而") is True
    assert check_zh(
        "调查",
        "[T4Q12 补] 调查；民意调查 [Codex 建议：TCF 常考同义替换]",
    ) is True
    # 署名会随执行的模型变，别锁死成 Codex——L34 的 46 条词条署的是 Opus5，
    # 曾经因此整批退化成人工自判。
    assert check_zh("发型", "[T8Q2 补] 发型 [Opus5 建议：Q2 干扰项]") is True
    assert check_zh("发型", "[T8Q2 补] 发型 [某新模型 建议：随便谁写的]") is True
    # 课级标签不止「课前复习」一种
    assert check_zh("旧货市场", "[L34课外题] 旧货市场；二手市集") is True
    assert check_zh("感受", "[L34写作T2] 感受") is True
    assert check_zh("计划", "[L34写作T1] 计划") is True
    # 一个词有两个来源时，标签连着写也要能剥干净
    assert check_zh("避免", "[L34课前复习][T8Q16] 避免") is True
    assert check_zh("避免", "[L34课前复习] [T8Q16] 避免") is True


def test_check_zh_does_not_eat_real_meaning():
    """剥标签不能顺手把正经义项吃掉——中括号里不是来源标签就得留着。"""
    assert check_zh("避免", "避免") is True
    assert check_zh("[非标签] 避免", "[非标签] 避免") is True   # 原样比对仍成立
    from matcher import _core_zh_gloss
    assert _core_zh_gloss("[X9] 避免") == "[X9] 避免"          # 不认识的标签不动
    assert _core_zh_gloss("避免 [T8Q1]") == "避免 [T8Q1]"      # 只剥开头，不剥中间


def test_check_zh_uncertain_returns_none():
    assert check_zh("增加", "增长，提高") is None       # 近义但不同 -> 自判
    assert check_zh("火", "水") is None
    assert check_zh("", "水") is None


def test_every_real_vocab_gloss_strips_clean():
    """真实词表体检：剥完来源标签和建议后缀，核心义里不该再有中括号。

    残留会让 check_zh 拿核心义去比对时匹配不上，判分从「自动判对」退化成
    「人工自判」——不报错、不判错，安静地把整批词的自动判分废掉。L34 曾有
    53/123 行处于这个状态（46 行是 Opus5 署名，7 行是新加的课级标签）。
    单测盯不住这个，因为新标签是数据带进来的，不是代码写出来的。
    """
    import glob
    import json
    from pathlib import Path

    from matcher import _core_zh_gloss

    files = sorted(glob.glob(str(Path("..") / "L*" / "vocab.json")))
    assert files, "没扫到任何 vocab.json，测试等于没跑"

    bad = [
        (Path(f).parent.name, row["lemma"], row["zh"], _core_zh_gloss(row["zh"]))
        for f in files
        for row in json.loads(Path(f).read_text("utf-8"))
        if "[" in _core_zh_gloss(row.get("zh", "")) or "]" in _core_zh_gloss(row.get("zh", ""))
    ]
    assert not bad, (
        f"{len(bad)} 行剥完标签仍有中括号残留，自动判分会失效。"
        f"要么把新标签加进 matcher 的 _SOURCE_PREFIX，要么改 zh 的写法。前 5 行：{bad[:5]}"
    )


# ---------- 出题时遮答案 ----------

def test_redact_hides_the_target_but_keeps_the_contrast_word():
    """真实案例：à long terme 的入库理由里原样写着答案，照着敲就得分。
    遮住答案，但配对词 à court terme 必须留着——那是这条理由的教学价值。"""
    from matcher import redact
    t = "老师在 à court terme 旁边红笔补写 à long terme，成对给出"
    out = redact(t, ["à long terme", "long terme"])
    assert "à long terme" not in out
    assert "à court terme" in out, "配对词不是答案，不该遮"
    assert "▢▢▢" in out


def test_redact_matches_chinese_without_word_boundary():
    """汉字本身算 \\w，加前界守卫会让「就长期的」里的「长期的」永远匹配不上。"""
    from matcher import redact
    assert "长期的" not in redact("原话“就长期的，可以放到一起记”", ["长期的"])


def test_redact_needs_a_left_boundary_for_latin_words():
    """拉丁词必须卡前界，否则短词会打碎无关的长单词。"""
    from matcher import redact
    assert redact("dans un an", ["ans"]) == "dans un an"      # ans 不在 dans 里被切
    assert "▢▢▢" in redact("des services publics", ["service"])  # 但复数要挡住


def test_redact_replaces_longest_secret_first():
    """先替短词会把长短语切碎，长的就再也匹配不到了。"""
    from matcher import redact
    out = redact("il faut voir à long terme", ["terme", "à long terme"])
    assert out.count("▢▢▢") == 1, f"应该整体遮成一处，实际：{out}"


def test_redact_ignores_too_short_secrets():
    from matcher import redact
    assert redact("un an de plus", ["an"]) == "un an de plus"


def test_redact_is_a_noop_without_secrets():
    from matcher import redact
    assert redact("原文照常显示", []) == "原文照常显示"
    assert redact("", ["x"]) == ""
