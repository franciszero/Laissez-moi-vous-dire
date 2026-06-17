"""答案匹配。
- 法语：精确、重音敏感（épicier ≠ epicier），仅忽略大小写与空格。
- 中文：分层匹配（精确 → 义项切分 → 占位符骨架）；拿不准返回 None，交人工自判，绝不自动判错。
"""
from __future__ import annotations

import re
import unicodedata


# ---------- 法语 ----------

def norm_fr(t: str) -> str:
    return " ".join((t or "").strip().lower().split())


def check_fr(answer: str, target: str) -> bool:
    return bool(answer.strip()) and norm_fr(answer) == norm_fr(target)


# ---------- 中文 ----------

# 占位符 / 省略号（"……" 要在 "…" 前面，先吃成对的）
_PLACEHOLDERS = ["……", "…", "...", "。。。", "某人", "某事", "某物", "某地", "某", "XX", "xx", "××", "_"]
_SEP = re.compile(r"[，,、;；/／]")


def _norm_zh(t: str) -> str:
    return re.sub(r"\s+", "", (t or "").strip())


def _senses(gloss: str) -> list[str]:
    return [s for s in (_norm_zh(x) for x in _SEP.split(gloss or "")) if s]


def _skeleton(t: str) -> str:
    s = _norm_zh(t)
    for p in _PLACEHOLDERS:
        s = s.replace(p, "")
    return s


def check_zh(answer: str, gloss: str):
    """返回 True=算对；None=拿不准（交人工自判）。永不自动判错。"""
    a = _norm_zh(answer)
    if not a:
        return None
    senses = _senses(gloss)
    if a in senses:
        return True
    a_sk = _skeleton(answer)
    if a_sk and (a_sk == _skeleton(gloss) or a_sk in {_skeleton(s) for s in senses}):
        return True
    return None


# ---------- 念法语（口述 ASR 判分，宽松、重音不敏感、容许小转写误差）----------

_PUNCT = re.compile(r"[.,!?;:…«»\"'’\-()\[\]/]")


def _strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _lev(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a or not b:
        return len(a) + len(b)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


_SPEECH_ARTICLES = ("le ", "la ", "les ", "un ", "une ", "des ", "du ", "de ", "l'", "l’")


def _drop_article(s: str) -> str:
    for p in _SPEECH_ARTICLES:
        if s.startswith(p):
            return s[len(p):]
    return s


def check_speech(heard: str, target: str):
    """口述判分：True=对；None=拿不准（交人工自判）。重音不敏感、去标点、冠词可省、容许小误差。"""
    h = " ".join(_strip_accents(norm_fr(_PUNCT.sub(" ", heard or ""))).split())
    t = _strip_accents(norm_fr(target))
    if not h:
        return None
    for a, b in ((h, t), (_drop_article(h), _drop_article(t))):
        if a == b or _lev(a, b) <= max(1, len(b) // 6):
            return True
    return None
