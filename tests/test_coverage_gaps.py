import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "coverage_report", Path(__file__).resolve().parent.parent / "scripts" / "coverage_report.py"
)
cov = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cov)


def test_statement_drill_gaps_flags_all_self_judge_group():
    cards = [
        {"study_group": "g1", "study_group_label": "全自评组", "answer": None},
        {"study_group": "g1", "study_group_label": "全自评组", "answer": None},
        {"study_group": "g2", "study_group_label": "有题组", "answer": "x"},
        {"study_group": "g2", "study_group_label": "有题组", "answer": None},
        {"answer": None},  # 无 study_group：忽略
    ]
    gaps = cov.statement_drill_gaps(cards)
    assert len(gaps) == 1 and "全自评组" in gaps[0]   # g1 全自评被标；g2 有机判不标
