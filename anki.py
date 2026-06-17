from __future__ import annotations

import html as _html
import json
import re
import unicodedata
import urllib.error
import urllib.request

ANKI_URL = "http://127.0.0.1:8765"
DECK = "Français"


def html_to_text(s: str) -> str:
    if not s:
        return ""
    s = re.sub(r"(?i)<br\s*/?>", " ", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = _html.unescape(s)
    s = s.replace(" ", " ")
    return re.sub(r"\s+", " ", s).strip()


def first_example(html: str) -> str:
    """从 Example Sentences 字段的 HTML 里取第一条句子文本。"""
    if not html:
        return ""
    parts = re.split(r"(?i)<li[ >]", html)
    chunk = parts[1] if len(parts) > 1 else html
    return html_to_text(chunk)


def _anki(action: str, **params):
    req = urllib.request.Request(
        ANKI_URL,
        data=json.dumps({"action": action, "version": 6, "params": params}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=3) as r:
        payload = json.load(r)
    if payload.get("error"):
        raise RuntimeError(payload["error"])
    return payload["result"]


def _norm(s: str) -> str:
    s = " ".join((s or "").strip().lower().split())
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _strip_article(s: str) -> str:
    low = (s or "").lower()
    for p in ("le ", "la ", "les ", "un ", "une "):
        if low.startswith(p):
            return s[len(p):]
    if low.startswith("l'") or low.startswith("l’"):
        return s[2:]
    return s


def _find_note(lemma: str):
    core = _strip_article(lemma)
    target = _norm(lemma)
    target_core = _norm(core)
    # 先在 Lemma 字段里找（窄），再退回全文搜（宽）
    ids: list = []
    for q in (f'deck:"{DECK}" "Lemma:*{core}*"', f'deck:"{DECK}" "{core}"'):
        try:
            ids = _anki("findNotes", query=q)
        except RuntimeError:
            ids = []
        if ids:
            break
    if not ids:
        return None
    for info in _anki("notesInfo", notes=ids[:60]):
        lem = html_to_text(info.get("fields", {}).get("Lemma", {}).get("value", ""))
        full = _norm(lem)
        core2 = _norm(_strip_article(lem))
        if target in (full, core2) or target_core in (full, core2):
            return info
    return None  # 找不到精确匹配就别显示，宁缺毋错


def enrich(lemma: str):
    """只读：返回 {core_meaning, example, ipa}；Anki 没开/未命中/异常 -> None。"""
    try:
        info = _find_note(lemma)
        if not info:
            return None
        fields = info.get("fields", {})

        def f(name):
            return html_to_text(fields.get(name, {}).get("value", ""))

        return {
            "core_meaning": f("Core Meaning"),
            "example": first_example(fields.get("Example Sentences", {}).get("value", "")),
            "ipa": f("IPA + Pronunciation Notes")[:120],
        }
    except (urllib.error.URLError, OSError, RuntimeError, ValueError, IndexError, KeyError):
        return None


def render_card(lemma: str) -> str | None:
    """只读：返回该词 Anki 卡【背面】的完整渲染 HTML（Anki 自己渲染好的，自带 <style> 和 .card 外层）。
    没卡 / Anki 没开 / 异常 -> None。"""
    try:
        info = _find_note(lemma)
        if not info:
            return None
        cards = info.get("cards") or []
        if not cards:
            return None
        ci = _anki("cardsInfo", cards=[cards[0]])
        answer = (ci[0].get("answer") if ci else "") or ""
        if not answer.strip():
            return None
        # 网页里放不了的音频记号去掉（图片若有则保持原样）
        return re.sub(r"\[sound:[^\]]*\]", "", answer)
    except (urllib.error.URLError, OSError, RuntimeError, ValueError, IndexError, KeyError):
        return None
