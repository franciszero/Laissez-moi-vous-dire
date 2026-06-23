#!/usr/bin/env python3
"""离线金标准 bakeoff：用固定金标准集跑 AI 精练 pipeline，按【类型】打分，
帮你选模型 / 决定是否开 thinking。pipeline 建好后用；**不在 pytest 里跑真模型**。

一次评一个配置（靠 env 切换，扫多个就改 env 重跑）：
  python3 scripts/llm_grade_bakeoff.py [gold.json]
  DICTATION_LLM_THINKING=1 python3 scripts/llm_grade_bakeoff.py
  DICTATION_LLM_MODEL=<27b> python3 scripts/llm_grade_bakeoff.py

金标准每例自包含：{spec, answer, should_flag[], should_accept[], expected_overall}。
种子只有几条够 smoke；真正选模型至少 20-30 条，并随真实学习记录增长（codex 评审 #5）。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import aigrade  # noqa: E402
import llm  # noqa: E402

DEFAULT_GOLD = Path(__file__).resolve().parent / "gold" / "l22_ai_gold.json"


def score_case(case: dict, result: dict, segments: list[dict]) -> dict:
    """纯函数：对照一例金标准给分（可单测，不碰模型）。"""
    err_text = " ".join(s.get("text", "") for s in segments if s.get("状态") in ("错误", "多余"))
    missed = [f for f in case.get("should_flag", []) if f not in err_text]   # 该标错却没标
    false_pos = []
    for ok_frag in case.get("should_accept", []):
        if any(ok_frag in s.get("text", "") and s.get("状态") == "错误" for s in segments):
            false_pos.append(ok_frag)                                        # 对/可接受却判错
    exp = case.get("expected_overall")
    return {
        "parse_ok": not result.get("parse_error"),
        "false_negative": missed,
        "false_positive": false_pos,
        "overall_match": (result.get("总判定") == exp) if exp else None,
    }


def run(gold_path: Path) -> None:
    cases = json.loads(gold_path.read_text("utf-8"))
    print(f"金标准：{gold_path}（{len(cases)} 例）")
    print(f"模型：{llm._session_model()}　thinking：{llm._thinking_enabled()}")
    print(f"加载 {llm.load():.1f}s\n")
    agg = {"parse_ok": 0, "fn": 0, "fp": 0, "om_ok": 0, "om_total": 0, "lat": []}
    try:
        for c in cases:
            t = time.monotonic()
            raw = llm.chat(aigrade.build_prompt(c["spec"], c["answer"]))
            agg["lat"].append(time.monotonic() - t)
            res = aigrade.normalize_result(raw)
            segs = aigrade.anchor_and_segment(c["answer"], res.get("spans", []))
            s = score_case(c, res, segs)
            agg["parse_ok"] += s["parse_ok"]
            agg["fn"] += len(s["false_negative"])
            agg["fp"] += len(s["false_positive"])
            if s["overall_match"] is not None:
                agg["om_total"] += 1
                agg["om_ok"] += int(s["overall_match"])
            mark = "✗FN" if s["false_negative"] else ("△FP" if s["false_positive"] else "ok ")
            print(f"  [{mark}] {c['answer'][:46]:46} 漏标={s['false_negative']} 误判={s['false_positive']}")
    finally:
        llm.unload()
    n = len(cases) or 1
    lat = agg["lat"]
    print("\n=== 配置汇总 ===")
    print(f"JSON 成功率：{agg['parse_ok']}/{len(cases)}")
    print(f"❗错句漏标(最高危) 总数：{agg['fn']}")
    print(f"对的被误判 总数：{agg['fp']}")
    if agg["om_total"]:
        print(f"总判定一致：{agg['om_ok']}/{agg['om_total']}")
    if lat:
        print(f"延迟：平均 {sum(lat) / len(lat):.1f}s，最大 {max(lat):.1f}s")


def main() -> None:
    run(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_GOLD)


if __name__ == "__main__":
    main()
