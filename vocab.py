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

_PROVENANCE_REQUIRED_TEXT = (
    "source_kind",
    "source_ref",
    "teacher_action",
    "selection_reason",
)
_PROVENANCE_OPTIONAL_TEXT = ("learning_note",)
_EVIDENCE_OPTIONAL_TEXT = ("time", "lines")


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


def normalize_provenance_item(item: dict, *, context: str = "provenance") -> dict:
    """Validate and normalize one learner-facing vocabulary provenance record."""
    if not isinstance(item, dict):
        raise ValueError(f"{context} must be an object")

    normalized: dict = {}
    for field in _PROVENANCE_REQUIRED_TEXT:
        value = item.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{context} requires non-empty {field}")
        normalized[field] = value.strip()

    evidence = item.get("evidence")
    if not isinstance(evidence, dict):
        raise ValueError(f"{context} requires evidence object")
    evidence_file = evidence.get("file")
    if not isinstance(evidence_file, str) or not evidence_file.strip():
        raise ValueError(f"{context} requires non-empty evidence.file")
    normalized_evidence = {"file": evidence_file.strip()}
    for field in _EVIDENCE_OPTIONAL_TEXT:
        value = evidence.get(field)
        if value is None:
            continue
        if not isinstance(value, str):
            raise ValueError(f"{context} evidence.{field} must be a string")
        if value.strip():
            normalized_evidence[field] = value.strip()
    normalized["evidence"] = normalized_evidence

    for field in _PROVENANCE_OPTIONAL_TEXT:
        value = item.get(field)
        if value is None:
            continue
        if not isinstance(value, str):
            raise ValueError(f"{context} {field} must be a string")
        if value.strip():
            normalized[field] = value.strip()
    return normalized


def normalize_provenance_list(value, *, context: str = "provenance") -> list[dict]:
    """Validate and de-duplicate a provenance array without changing its order."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{context} must be an array")
    normalized: list[dict] = []
    seen: set[str] = set()
    for index, item in enumerate(value, 1):
        record = normalize_provenance_item(item, context=f"{context}[{index}]")
        key = json.dumps(record, ensure_ascii=False, sort_keys=True)
        if key not in seen:
            normalized.append(record)
            seen.add(key)
    return normalized


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
                        "example": e.get("example"), "fem": e.get("fem"),
                        "zh_by_lesson": {}, "provenance_by_lesson": {},
                        "lessons": []}
            )
            if lesson not in slot["lessons"]:
                slot["lessons"].append(lesson)
            if e.get("zh"):                       # 保留每课各自的释义（同词跨课可能不同）
                slot["zh_by_lesson"][lesson] = e["zh"]
            if not slot["zh"] and e.get("zh"):
                slot["zh"] = e["zh"]
            if not slot.get("fem") and e.get("fem"):
                slot["fem"] = e["fem"]
            try:
                provenance = normalize_provenance_list(
                    e.get("provenance"),
                    context=f"{vj}: {lemma} provenance",
                )
            except ValueError:
                provenance = []
            if provenance:
                existing = slot["provenance_by_lesson"].setdefault(lesson, [])
                existing_keys = {
                    json.dumps(item, ensure_ascii=False, sort_keys=True)
                    for item in existing
                }
                for item in provenance:
                    key = json.dumps(item, ensure_ascii=False, sort_keys=True)
                    if key not in existing_keys:
                        existing.append(item)
                        existing_keys.add(key)
    return by_lemma, by_lesson


# ---------- 全库搜词 ----------
# 词库过千之后，侧栏词表只列当前这一轮的池子，够不到别的课的词。搜索是唯一
# 能到达任意一个词的入口，所以它必须是全库的、且对重音宽容——记不清 sécurité
# 上面有没有那一撇，正是要来查的原因。

import unicodedata


def fold(text: str) -> str:
    """搜索用的归一：去重音、小写、撇号统一、压空格。判分不用这个，判分严格。"""
    s = unicodedata.normalize("NFD", (text or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return " ".join(s.replace("’", "'").replace("‘", "'").split())


_SEARCH_ARTICLE = re.compile(r"^(le |la |les |un |une |des |du |l'|se |s')")
# 词边界：空格、撇号、连字符。用它切词而不是裸子串匹配——搜的是完整单词
# （哪怕是变形），命中词中间的一段字母对学习者没有任何用处：搜 ion 会撞出
# d'occasion / l'adoption / la passion 共 50 条，全是噪音；搜 irai 撞出
# part-irai-t。而按词切之后 plat→un plat principal、intéresser→s'intéresser à
# 这类「完整词命中短语里的一个词」一条不少。
_TOKEN_SPLIT = re.compile(r"[ '’\-]+")


def _tokens(folded: str) -> list[str]:
    return [t for t in _TOKEN_SPLIT.split(folded) if t]


_CJK = re.compile(r"[\u4e00-\u9fff]")

try:                      # 法语词形还原：查表式，无模型，结果确定
    import simplemma

    def lemma_of(text: str) -> str:
        """变形 → 原型。intéressante→intéressant、irai→aller、coûteuse→coûteux。

        手写规则做不了这件事：法语的阴性、复数、变位有大量不规则形式，靠
        「多出几个字母就算命中」既漏（intelligente）又错（plateaux 会匹上 plat）。
        simplemma 是查表，没有模型也没有随机性，同样的输入永远同样的输出。
        中文、多词短语、已是原型的词都原样返回，不会被改坏。
        """
        return " ".join(
            simplemma.lemmatize(tok, lang="fr") if tok else tok
            for tok in (text or "").split(" ")
        )
except ImportError:       # 没装就退化成不还原——搜得少一些，但不炸
    def lemma_of(text: str) -> str:
        return text or ""


def search(entries: dict, query: str, limit: int = 20) -> list[str]:
    """在 {lemma: entry} 里找词，法语和中文都能搜。返回 lemma 列表，按相关度排。

    你查一个词，多半是**在别处读到它**才来查的——那里出现的往往是变形：
    阴性 intéressante、复数 plats、变位 irai。词库存的是原形，直接比字符串就会
    告诉你「词库里没有」，而它其实躺在那儿。所以两边都先还原成原型再比：

    - 查询词过一遍 `lemma_of`（intéressante → intéressant）
    - 词库里每条也过一遍（`les vêtements` → `vêtement`），两边在原型层相遇
    - 外加 `fem` 字段：那是本词库自己标注的确定数据，优先级最高

    排序：正向命中 > 原型命中 > 词内命中 > 中文。同档按词长升序——短词更可能
    是你要的那个（搜 plat 时 le plat 排在 un plat principal 前面）。

    法语侧一律**整词相等**，既不做裸子串也不做前缀：你输入的是一个完整单词
    （哪怕是变形），拿半截去匹配只会返回你没在找的东西。输入不全时 search 返回
    空，由 `near()` 去给「是不是想找」——猜测和命中分开呈现，别混在一张列表里。
    中文侧保留子串——中文没有词边界。
    """
    q = fold(query)
    if not q:
        return []
    ql = fold(lemma_of(query.strip()))
    starts, lemma_hits, contains, zh_hits = [], [], [], []
    for lemma, entry in entries.items():
        f = fold(lemma)
        stem = fold(_SEARCH_ARTICLE.sub("", f))
        fem = fold(entry.get("fem") or "")
        if q in (f, stem, fold(_strip_notations(lemma))):
            starts.append(lemma)
        elif fem and (fem == q or fold(lemma_of(fem)) == ql):
            starts.append(lemma)          # 阴性是词库自己标的，不是推断
        elif ql != q and (fold(lemma_of(stem)) == ql or fold(lemma_of(f)) == ql):
            lemma_hits.append(lemma)      # 两边都还原成原型之后相等
        elif q in _tokens(f):
            contains.append(lemma)      # 完整词命中短语里的某一个词
        elif _CJK.search(query):
            # 只有中文查询才查中文义。拉丁查询走中文分支会撞上我自己写在
            # 「[Opus5 建议：…]」里的法语词——搜 ant 撞出 le marché（理由里有
            # brocante）和 primordial（理由里有 important），搜 ion 撞出 évaluer
            # （理由里有 estimation）。那不是这个词的意思，是注释里的字母。
            glosses = " ".join(
                [entry.get("zh") or ""] + list((entry.get("zh_by_lesson") or {}).values())
            )
            if query.strip() in glosses:
                zh_hits.append(lemma)
    key = lambda x: (len(x), x)
    return (sorted(starts, key=key) + sorted(lemma_hits, key=key)
            + sorted(contains, key=key) + sorted(zh_hits, key=key))[:limit]


def near(entries: dict, query: str, limit: int = 5) -> list[str]:
    """严格搜索为空时的「是不是想找」。

    按共同前缀长度排。故意和 search 分开：search 的结果是「找到了」，
    这里的结果是「猜的」，UI 上必须说清楚，否则学习者会以为词库里就长这样。
    """
    q = fold(query)
    if len(q) < 3:
        return []
    scored = []
    for lemma in entries:
        f = fold(_SEARCH_ARTICLE.sub("", fold(lemma)))
        n = 0
        for a, b in zip(q, f):
            if a != b:
                break
            n += 1
        if n >= 3:
            scored.append((-n, len(lemma), lemma))
    return [x[2] for x in sorted(scored)[:limit]]
