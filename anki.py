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


def core_meaning_text(enrich_result) -> str | None:
    """从 enrich() 结果取可显示的 core_meaning；None / 空 / "N/A" → None。"""
    cm = (enrich_result or {}).get("core_meaning", "")
    return cm if cm and cm.upper() != "N/A" else None


_EXC = (urllib.error.URLError, OSError, RuntimeError, ValueError, IndexError, KeyError)
# 卡片「有没有真内容」看这几个核心字段——全空/全 N/A 就是生成失败的残卡。
_CONTENT_FIELDS = ("Core Meaning", "Définition FR", "Grammar Frame", "Example Sentences")


def _answer_html(info) -> str | None:
    """从一张 note info 渲染卡背 HTML（Anki 自带 <style>/.card）；没卡 / 空 -> None。"""
    cards = info.get("cards") or []
    if not cards:
        return None
    ci = _anki("cardsInfo", cards=[cards[0]])
    answer = (ci[0].get("answer") if ci else "") or ""
    if not answer.strip():
        return None
    # 网页里放不了的音频记号去掉（图片若有则保持原样）
    return re.sub(r"\[sound:[^\]]*\]", "", answer)


def _stub_reason(info) -> str | None:
    """笔记存在但生成失败（残卡）：QA Summary 标记解析失败，或核心字段全空/全 N/A。
    返回给用户看的简短提示；不是残卡 -> None。"""
    fields = info.get("fields", {})

    def f(name):
        return html_to_text(fields.get(name, {}).get("value", "")).strip()

    if "解析失败" in f("QA Summary"):
        return "卡片生成解析失败"
    vals = [f(n) for n in _CONTENT_FIELDS]
    if all((not v) or v.upper() == "N/A" for v in vals):
        return "卡片字段未生成（全为 N/A）"
    return None


def render_card(lemma: str) -> str | None:
    """只读：返回该词 Anki 卡【背面】的完整渲染 HTML（Anki 自己渲染好的，自带 <style> 和 .card 外层）。
    没卡 / Anki 没开 / 异常 -> None。"""
    try:
        info = _find_note(lemma)
        if not info:
            return None
        return _answer_html(info)
    except _EXC:
        return None


def card_state(lemma: str) -> dict:
    """只读：返回 {'status': 'ok'|'stub'|'missing', 'html': str|None, 'reason': str|None}。
    - ok      = 有真内容的卡（html 可渲染）
    - stub    = 笔记在、但生成失败 / 字段全 N/A（待重新生成；reason 给提示，不显示空卡）
    - missing = 没笔记 / 没卡 / Anki 没开（沿用「宁缺毋错」，不显示）"""
    try:
        info = _find_note(lemma)
        if not info:
            return {"status": "missing", "html": None, "reason": None}
        reason = _stub_reason(info)
        if reason:
            return {"status": "stub", "html": None, "reason": reason}
        html = _answer_html(info)
        if not html:
            return {"status": "missing", "html": None, "reason": None}
        return {"status": "ok", "html": html, "reason": None}
    except _EXC:
        return {"status": "missing", "html": None, "reason": None}


def memoized_state(cache: dict, lemma: str) -> dict:
    """card_state 的记忆化：只缓存稳定的 'ok'；'missing'/'stub' 每次都重查。
    这样在 app 运行期间新生成的 Anki 卡能马上出现，不必重启（负结果不会被永久缓存）。
    `cache` 由调用方持有（如 st.session_state 里的 dict）。"""
    hit = cache.get(lemma)
    if hit is not None:
        return hit
    state = card_state(lemma)
    if state.get("status") == "ok":
        cache[lemma] = state
    return state
