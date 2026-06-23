import importlib.util
import json
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "llm_grade_bakeoff", _root / "scripts" / "llm_grade_bakeoff.py"
)
bakeoff = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bakeoff)


def test_score_case_flags_false_negative_and_overall_mismatch():
    case = {"should_flag": ["habitais", "en Paris"], "expected_overall": "错"}
    result = {"parse_error": False, "总判定": "对"}              # 把错句判成对
    segs = [{"text": "ils habitais en Paris", "状态": "正确"}]     # 没标出真错
    s = bakeoff.score_case(case, result, segs)
    assert s["false_negative"] == ["habitais", "en Paris"]      # 最高危：漏标
    assert s["overall_match"] is False


def test_score_case_flags_false_positive_else_clean():
    case = {"should_accept": ["s'installeront"], "expected_overall": "对"}
    result = {"parse_error": False, "总判定": "对"}
    segs = [{"text": "s'installeront", "状态": "错误"}, {"text": " à Paris", "状态": "正确"}]
    s = bakeoff.score_case(case, result, segs)
    assert s["false_positive"] == ["s'installeront"]            # 把对的判错
    assert s["false_negative"] == [] and s["overall_match"] is True


def test_seed_gold_file_is_valid_and_self_contained():
    cases = json.loads((_root / "scripts" / "gold" / "l22_ai_gold.json").read_text("utf-8"))
    assert len(cases) >= 5
    for c in cases:
        assert c["spec"].get("references") and "answer" in c
        assert "expected_overall" in c
