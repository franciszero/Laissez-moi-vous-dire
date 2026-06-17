"""macOS 系统词典（Dictionary Services）只读查词，作为没有 Anki 卡时的降级兜底。
只在结果像法语时返回，避免英文词典污染（很多法语词也是英文词头）。"""
from __future__ import annotations

try:
    from CoreServices import DCSCopyTextDefinition
    _AVAILABLE = True
except Exception:  # 没装 pyobjc-framework-CoreServices / 非 macOS
    DCSCopyTextDefinition = None
    _AVAILABLE = False

# 法语词典条目里的特征词（英文词典用 noun/verb/adjective，不会命中这些）
_FR_MARKERS = (
    "nom masculin", "nom féminin", "adjectif", "verbe", "adverbe",
    "préposition", "conjonction", "pronom", "SYNONYME", "Prononciation",
    " féminin", " masculin",
)


def _strip_article(s: str) -> str:
    low = (s or "").lower()
    for p in ("le ", "la ", "les ", "un ", "une "):
        if low.startswith(p):
            return s[len(p):]
    if low.startswith("l'") or low.startswith("l’"):
        return s[2:]
    return s


def _looks_french(text: str) -> bool:
    return any(m in text for m in _FR_MARKERS)


def _raw_lookup(word: str) -> str | None:
    if not _AVAILABLE or not word:
        return None
    try:
        d = DCSCopyTextDefinition(None, word, (0, len(word)))
    except Exception:
        return None
    return " ".join(str(d).split()) if d else None


def define(lemma: str) -> str | None:
    """查 lemma；先试整词（含 l' 省音），再试去冠词裸词。只返回像法语的释义。"""
    lemma = (lemma or "").strip()
    if not lemma:
        return None
    for cand in (lemma, _strip_article(lemma).strip()):
        text = _raw_lookup(cand)
        if text and _looks_french(text):
            return text[:280]
    return None
