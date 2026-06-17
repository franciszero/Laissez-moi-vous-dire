"""从课表 TSV + words.txt 生成 L17/L18 的 vocab.json，并打印样本/对齐 diff。
用法：python3 scripts/build_vocab.py"""
from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vocab import parse_lesson_table  # noqa: E402

HERE = Path(__file__).resolve().parents[1]
L18_SRC = HERE.parent / "L18" / "source"
L17_JSON = HERE.parent / "L17" / "vocab.json"
L18_JSON = HERE.parent / "L18" / "vocab.json"
WORDS_TXT = HERE / "words.txt"


def _norm(s: str) -> str:
    s = " ".join(s.strip().lower().split()).replace("’", "'")
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _strip_article(s: str) -> str:
    low = s.lower()
    for p in ("le ", "la ", "les ", "un ", "une "):
        if low.startswith(p):
            return s[len(p):]
    if low.startswith("l'") or low.startswith("l’"):
        return s[2:]
    return s


def main() -> None:
    l23 = parse_lesson_table((L18_SRC / "lecon23.tsv").read_text("utf-8"), "L18", "Leçon23")
    l24 = parse_lesson_table((L18_SRC / "lecon24.tsv").read_text("utf-8"), "L18", "Leçon24")
    l25 = parse_lesson_table((L18_SRC / "lecon25.tsv").read_text("utf-8"), "L18", "Leçon25")
    l18 = l23 + l24 + l25

    # L17 = 以 words.txt 为 lemma 权威，用 Leçon25 表补 zh/pos（保历史逐字一致）
    words = [w.strip() for w in WORDS_TXT.read_text("utf-8").splitlines()
             if w.strip() and not w.startswith("#")]
    by_core = {_norm(_strip_article(e["lemma"])): e for e in l25}
    l17 = []
    misses = []
    for w in words:
        e = by_core.get(_norm(_strip_article(w)))
        if e is None:
            misses.append(w)
            l17.append({"lemma": w, "pos": "", "zh": "", "lesson": "L17",
                        "source_lesson": "Leçon25", "category": "", "example": None, "raw": w})
        else:
            l17.append({**e, "lemma": w, "lesson": "L17"})

    L17_JSON.write_text(json.dumps(l17, ensure_ascii=False, indent=2), "utf-8")
    L18_JSON.write_text(json.dumps(l18, ensure_ascii=False, indent=2), "utf-8")

    print(f"L18: {len(l18)} 词 -> {L18_JSON}")
    print(f"L17: {len(l17)} 词 -> {L17_JSON}")
    print("\n--- L18 样本（每课前 4）---")
    for sl in ("Leçon23", "Leçon24", "Leçon25"):
        print(f"  [{sl}]")
        for e in [x for x in l18 if x["source_lesson"] == sl][:4]:
            print(f"    {e['lemma']:24} [{e['pos']:6}] {e['zh']}   <= {e['raw']}")
    print("\n--- 阴阳性/词形对清洗检查（raw 含逗号者）---")
    for e in [x for x in l18 if "," in x["raw"]][:12]:
        print(f"    {e['raw']:24} -> {e['lemma']}")
    if misses:
        print(f"\n⚠️ L17 有 {len(misses)} 个 words.txt 词未在 Leçon25 表里匹配到（zh/pos 留空，请人工确认）：")
        for m in misses:
            print("   ", m)
    else:
        print("\n✅ L17 全部 words.txt 词都对齐到了 Leçon25 表（zh/pos 已补全，历史不受影响）。")


if __name__ == "__main__":
    main()
