from __future__ import annotations

import json
import re
from pathlib import Path

# 语法缩写（按长度降序，避免 "v. t." 先吃掉 "v. t. ind"）
_GRAM_ABBR = sorted(
    [
        "n. f. pl.", "n. m. pl.", "n. f.", "n. m.",
        "v. t. ind", "v. i. ou v. t.", "v. t. ou v. i.", "v. t.", "v. i.",
        "loc. adv.", "loc. prép.", "adv.", "conj.", "prép.", "adj.",
    ],
    key=len,
    reverse=True,
)

_POS_BY_CATEGORY = {"NOMS": "noun", "VERBES": "verb", "ADJECTIFS": "adj"}


# 阴性后缀替换规则：(masc 结尾, marker, 去掉几个字符, 加什么)
_FEM_SUFFIX_RULES = [
    ("teur", "trice", 4, "trice"),
    ("eur", "euse", 3, "euse"),
    ("er", "ère", 2, "ère"),
    ("x", "se", 1, "se"),
    ("f", "ve", 1, "ve"),
]


def _strip_notations(raw: str) -> str:
    """去 [IPA]/（注释）/(注释)/尾部语法缩写，不做逗号切分。"""
    s = (raw or "").strip()
    s = re.sub(r"\[[^\]]*\]", "", s)        # 去 [IPA]
    s = re.sub(r"（[^）]*）", "", s)         # 去全角（中文注释）
    s = re.sub(r"\([^)]*\)", "", s)          # 去半角(注释)
    changed = True
    while changed:                            # 反复剥尾部语法缩写
        changed = False
        s = s.strip()
        for abbr in _GRAM_ABBR:
            if s.endswith(abbr):
                s = s[: -len(abbr)]
                changed = True
                break
    return s.strip()


def clean_lemma(raw: str) -> str:
    """从课表 Français 单元格得到朗读&听写目标。"""
    s = _strip_notations(raw)
    if "," in s:                              # 阴阳性/词形对取基本形
        s = s.split(",", 1)[0]
    return s.strip()


def split_gender(raw: str):
    """从 Français 单元格得到 (阳性 lemma, 阴性标记 或 None)。"""
    s = _strip_notations(raw)
    if "," in s:
        masc, marker = s.split(",", 1)
        return masc.strip(), marker.strip()
    return s.strip(), None


def feminine_form(masc, marker):
    """从阳性 + 逗号后标记重建阴性形式；拿不准返回 None。"""
    masc = (masc or "").strip()
    m = (marker or "").strip()
    if not masc or not m:
        return None
    if m == "e":
        return masc + "e"
    for end, mk, cut, add in _FEM_SUFFIX_RULES:
        if m == mk and masc.endswith(end):
            return masc[:-cut] + add
    if m in ("ne", "le"):
        return masc + m
    if len(m) >= 4:
        return m   # 完整阴性词（occidentale/belle/vieille…）
    return None


def derive_pos(category: str, raw: str) -> str:
    cat = (category or "").strip().upper()
    if cat in _POS_BY_CATEGORY:
        return _POS_BY_CATEGORY[cat]
    r = (raw or "").lower()
    if "prép." in r:        # loc. prép. / prép.
        return "prep"
    if "conj." in r:
        return "conj"
    if "adv." in r:         # loc. adv. / adv.
        return "adverb"
    return "expr"


def parse_lesson_table(raw: str, lesson: str, source_lesson: str) -> list[dict]:
    """解析 `类别<TAB>Français<TAB>中文` 的课表文本为词条列表。"""
    out: list[dict] = []
    for line in (raw or "").splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        category, french, zh = parts[0].strip(), parts[1].strip(), parts[2].strip()
        masc, marker = split_gender(french)
        out.append(
            {
                "lemma": clean_lemma(french),
                "pos": derive_pos(category, french),
                "zh": zh,
                "lesson": lesson,
                "source_lesson": source_lesson,
                "category": category.upper(),
                "example": None,
                "raw": french,
                "fem": feminine_form(masc, marker),
                "fem_raw": marker,
            }
        )
    return out


def parse_uploaded(text: str, lesson: str) -> tuple[list[dict], int]:
    """解析上传的词表：每行 2 列(法语,中文) 或 3 列(类别,法语,中文)。
    分隔符支持 Tab / 竖线 | / 逗号；自动跳过空行、表头、Markdown 分隔行。
    返回 (entries, skipped_行数)。"""
    entries: list[dict] = []
    skipped = 0
    for line in (text or "").splitlines():
        s = line.strip()
        if not s:
            continue
        if "\t" in s:
            parts = s.split("\t")
        elif "|" in s:
            parts = s.strip("|").split("|")
        else:
            parts = s.split(",")
        parts = [p.strip() for p in parts if p.strip() != ""]
        if len(parts) < 2:
            skipped += 1
            continue
        if len(parts) >= 3:
            category, french, zh = parts[0], parts[1], parts[2]
        else:
            category, french, zh = "", parts[0], parts[1]
        # 跳过表头行 / Markdown 分隔行（--- ）
        if french in ("Français", "Francais", "français", "francais") or category == "类别":
            skipped += 1
            continue
        if set(french) <= set("-—:| "):
            skipped += 1
            continue
        masc, marker = split_gender(french)
        entries.append(
            {
                "lemma": clean_lemma(french),
                "pos": derive_pos(category, french),
                "zh": zh,
                "lesson": lesson,
                "source_lesson": lesson,
                "category": category.upper(),
                "example": None,
                "raw": french,
                "fem": feminine_form(masc, marker),
                "fem_raw": marker,
            }
        )
    return entries, skipped


def load_all_vocab(base_dir):
    """扫描 base_dir/L*/vocab.json，返回 (by_lemma, by_lesson)。
    by_lemma[lemma] = {pos, zh, example, lessons:[...]}；by_lesson[lesson] = [lemma,...]（按文件顺序）。"""
    base = Path(base_dir)
    by_lemma: dict[str, dict] = {}
    by_lesson: dict[str, list[str]] = {}
    for vj in sorted(base.glob("*/vocab.json")):
        try:
            entries = json.loads(vj.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        for e in entries:
            lemma = e.get("lemma", "").strip()
            if not lemma:
                continue
            lesson = e.get("lesson", vj.parent.name)
            by_lesson.setdefault(lesson, [])
            if lemma not in by_lesson[lesson]:
                by_lesson[lesson].append(lemma)
            slot = by_lemma.setdefault(
                lemma, {"pos": e.get("pos", ""), "zh": e.get("zh", ""),
                        "example": e.get("example"), "fem": e.get("fem"), "lessons": []}
            )
            if lesson not in slot["lessons"]:
                slot["lessons"].append(lesson)
            if not slot["zh"] and e.get("zh"):
                slot["zh"] = e["zh"]
            if not slot.get("fem") and e.get("fem"):
                slot["fem"] = e["fem"]
    return by_lemma, by_lesson
