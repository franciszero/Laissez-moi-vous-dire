import aigrade


def test_normalize_result_valid():
    raw = '{"片段":[{"片段":"en Paris","维度":"用词","状态":"错误","依据":"城市用 à","替换":"à Paris"}],"最小修正":"Ils s\'installeront à Paris.","更自然版":"Ils s\'installeront à Paris.","总判定":"部分"}'
    r = aigrade.normalize_result(raw)
    assert r["parse_error"] is False
    assert r["spans"][0]["片段"] == "en Paris" and r["spans"][0]["状态"] == "错误"
    assert r["总判定"] == "部分"


def test_normalize_result_unknown_status_becomes_uncertain():
    r = aigrade.normalize_result('{"片段":[{"片段":"x","状态":"瞎编"}]}')
    assert r["spans"][0]["状态"] == "拿不准"


def test_normalize_result_handles_fences_and_garbage():
    assert aigrade.normalize_result("```json\n{\"总判定\":\"对\"}\n```")["总判定"] == "对"
    assert aigrade.normalize_result("not json at all")["parse_error"] is True


def test_anchor_drops_hallucinated_fragment():
    # "habiter" 不在原句里 → 必须丢弃，不能染色
    segs = aigrade.anchor_and_segment(
        "Je vais à Paris.",
        [{"片段": "habiter", "状态": "错误"}, {"片段": "à Paris", "状态": "正确"}],
    )
    texts = [(s["text"], s["状态"]) for s in segs]
    assert ("à Paris", "正确") in texts
    assert all("habiter" not in t for t, _ in texts)
    # 片段拼回去 == 原句（覆盖完整、无丢字）
    assert "".join(s["text"] for s in segs) == "Je vais à Paris."


def test_anchor_covers_gaps_as_unmarked():
    segs = aigrade.anchor_and_segment(
        "ils habitais en Paris",
        [{"片段": "habitais", "状态": "错误"}, {"片段": "en", "状态": "错误"}],
    )
    assert "".join(s["text"] for s in segs) == "ils habitais en Paris"
    assert any(s["状态"] == "未标注" for s in segs)        # "ils "、" " 等空隙
    assert any(s["text"] == "habitais" and s["状态"] == "错误" for s in segs)


def test_anchor_apostrophe_insensitive():
    # 学生用直撇号、模型片段用弯撇号，也要能定位
    segs = aigrade.anchor_and_segment("je m'installe", [{"片段": "m’installe", "状态": "正确"}])
    assert any(s["text"] == "m'installe" and s["状态"] == "正确" for s in segs)


def test_to_html_escapes_and_colors():
    out = aigrade.to_html([{"text": "<b>&", "状态": "错误"}])
    assert "&lt;b&gt;&amp;" in out and "background:#ffcdd2" in out


def test_build_prompt_includes_spec_and_answer():
    spec = {"target": "他们会定居", "candidates": [{"zh": "定居", "fr": ["s'installer"]}],
            "references": ["Ils s'installeront à Paris."], "ignore": "找到工作后"}
    p = aigrade.build_prompt(spec, "ils habite en Paris")
    assert "s'installer" in p and "ils habite en Paris" in p and "找到工作后" in p
    assert "可接受变体" in p          # 开放状态集写进了 prompt
