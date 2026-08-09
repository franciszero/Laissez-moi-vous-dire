"""答案匹配。
- 法语：精确、重音敏感（épicier ≠ epicier），仅忽略大小写与空格。
- 中文：分层匹配（精确 → 义项切分 → 占位符骨架）；拿不准返回 None，交人工自判，绝不自动判错。
"""
from __future__ import annotations

import re
import unicodedata


# ---------- 法语 ----------

# 撇号风格只在「判分时」归一：键盘只能打直撇号 '，而词表/DB/Anki/课文里常是排版
# 弯撇号 ’。lemma 是 DB、vocab.json、Anki 三处共用的关联键，绝不能改存储——只在比较
# 这一步把两种撇号视作等价即可。重音仍严格：épicier ≠ epicier。
_APOS = str.maketrans({"’": "'", "‘": "'", "ʼ": "'"})


def norm_fr(t: str) -> str:
    return " ".join((t or "").strip().lower().translate(_APOS).split())


def check_fr(answer: str, target: str) -> bool:
    return bool(answer.strip()) and norm_fr(answer) == norm_fr(target)


# ---------- 中文 ----------

# 占位符 / 省略号（"……" 要在 "…" 前面，先吃成对的）
_PLACEHOLDERS = ["……", "…", "...", "。。。", "某人", "某事", "某物", "某地", "某", "XX", "xx", "××", "_"]
_SEP = re.compile(r"[，,、;；/／]")
# 中文义前面的来源标签。原先只认 [T4Q12] 和 [L30课前复习] 两种，后来又加了
# [L34课外题]、[L34写作T1/T2]，它们剥不掉就会留在核心义里，判分退化成人工自判。
# 这里按「课级标签」统一收口：L<数字> 开头的任意短标签都算来源，不再逐个枚举。
# 允许连着写多个标签（如 [L34课前复习][T8Q16]）——一个词有两个来源是正常的。
_ONE_SOURCE_TAG = (
    r"\[(?:T\d+Q\d+(?:/Q\d+)*(?:\s*[;；]\s*T\d+Q\d+(?:/Q\d+)*)*"
    r"|L\d+[^\]\s]{0,12})(?:\s*补)?\]"
)
_SOURCE_PREFIX = re.compile(rf"^\s*(?:{_ONE_SOURCE_TAG}\s*)+")
# 选词理由后缀。原先把署名写死成 Codex，换成 Opus5 之后 46 条 L34 词条的
# 后缀剥不掉。署名会随执行的模型变，所以不锁定具体名字。
_AGENT_NOTE_SUFFIX = re.compile(r"\s*\[[^\]]{0,20}建议\s*[:：][^\]]*\]\s*$")


def _norm_zh(t: str) -> str:
    return re.sub(r"\s+", "", (t or "").strip())


def _senses(gloss: str) -> list[str]:
    return [s for s in (_norm_zh(x) for x in _SEP.split(gloss or "")) if s]


def zh_senses(gloss: str) -> list[str]:
    """中文义里的各个义项（已去掉来源标签和建议后缀）。

    判分用不到这个公开入口——它是给 UI 遮答案用的：出题时要把这些字串从
    「为什么收录这个词」里挡掉，否则理由文字本身就把答案写出来了。
    """
    return _senses(_core_zh_gloss(gloss))


_MASK = "▢▢▢"
_CJK = re.compile(r"[\u4e00-\u9fff]")


def redact(text: str, secrets) -> str:
    """把 secrets 里的字串遮成 ▢▢▢。

    用途是出题时挡住「为什么收录这个词」里的答案原文——那段文字在答题前
    就展开，而入库理由常常原样写着目标词（老师在 à court terme 旁边红笔
    补写 à long terme…），照着敲就得分，听写白做。揭示答案后调用方不传
    secrets，原文照常显示。
    """
    if not text:
        return text
    # 长的先替，否则短词会把长短语切碎（先替 terme 就再也匹配不到 à long terme）。
    for s in sorted((x for x in secrets if len(x) >= 3), key=len, reverse=True):
        # 中文没有词边界，汉字本身算 \w，加前界守卫会让「就长期的」里的
        # 「长期的」永远匹配不上；拉丁词则需要前界，否则 an 会打碎 dans。
        guard = "" if _CJK.search(s) else r"(?<!\w)"
        # 只卡前边界不卡后边界：宁可把 services 挡成 ▢▢▢s，也不能因为多一个 s
        # 就把答案漏出去——后边界留着会让复数和变位形式整片漏光。
        text = re.sub(rf"{guard}{re.escape(s)}", _MASK, text, flags=re.I)
    return text


def _skeleton(t: str) -> str:
    s = _norm_zh(t)
    for p in _PLACEHOLDERS:
        s = s.replace(p, "")
    return s


def _core_zh_gloss(gloss: str) -> str:
    """去掉学习来源和选词理由；这些内容保留显示，但不参与中文判分。"""
    core = _SOURCE_PREFIX.sub("", gloss or "")
    return _AGENT_NOTE_SUFFIX.sub("", core).strip()


def check_zh(answer: str, gloss: str):
    """返回 True=算对；None=拿不准（交人工自判）。永不自动判错。"""
    a = _norm_zh(answer)
    if not a:
        return None
    core_gloss = _core_zh_gloss(gloss)
    senses = _senses(core_gloss)
    if a in senses:
        return True
    a_sk = _skeleton(answer)
    if a_sk and (a_sk == _skeleton(core_gloss) or a_sk in {_skeleton(s) for s in senses}):
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
