"""确定性法语【规则】动词变位——动词变位卡的答案键来源。**绝不用 LLM 生成答案键**。

只处理规则动词，且**由显式 type 驱动，绝不靠词尾猜测**（partir 也是 -ir 但不规则，猜会出错）：
- "er"  第一组 -er（含 -ger/-cer 在 a/o 词尾前的拼写微调）
- "ir2" 第二组 -ir（finir 型，带 -iss-）
- "re"  规则第三组 -re（attendre 型）

不规则动词不在此生成（`conjugate` 抛 KeyError / 不在表里就别建卡），需另用核对过的表或库。
覆盖时态：présent / imparfait / futur_simple / conditionnel / futur_proche / participe_passé。
每个时态返回 6 个形（je/tu/il/nous/vous/ils）；展示层把 elle≈il、elles≈ils。
"""
from __future__ import annotations

PERSONS = ("je", "tu", "il", "nous", "vous", "ils")
_ALLER_PRESENT = ("vais", "vas", "va", "allons", "allez", "vont")

# 时态 → 6 个词尾
_END = {
    "er": {
        "présent": ("e", "es", "e", "ons", "ez", "ent"),
        "imparfait": ("ais", "ais", "ait", "ions", "iez", "aient"),
    },
    "ir2": {
        "présent": ("is", "is", "it", "issons", "issez", "issent"),
        "imparfait": ("issais", "issais", "issait", "issions", "issiez", "issaient"),
    },
    "re": {
        "présent": ("s", "s", "", "ons", "ez", "ent"),
        "imparfait": ("ais", "ais", "ait", "ions", "iez", "aient"),
    },
}
_FUT_END = ("ai", "as", "a", "ons", "ez", "ont")          # 简单将来时
_COND_END = ("ais", "ais", "ait", "ions", "iez", "aient")  # 条件式现在时


def _stem(inf: str) -> str:
    return inf[:-2] if inf.endswith(("er", "ir")) else inf[:-2]  # er/ir/re 都去掉末 2/最后…见下


def _soften(stem: str, ending: str, vtype: str) -> str:
    """-ger/-cer 在以 a/o 开头的词尾前做拼写微调（changeons / commençons）。"""
    if ending[:1] in ("a", "o"):
        if stem.endswith("g"):
            return stem + "e" + ending
        if stem.endswith("c"):
            return stem[:-1] + "ç" + ending
    return stem + ending


def _future_stem(inf: str, vtype: str) -> str:
    return inf[:-1] if vtype == "re" else inf       # attendre→attendr ；-er/-ir 用整个不定式


# 不规则动词：人工核对过的表（test_conjugate.py 逐格验证）。简单时态(présent/imparfait/
# futur_simple/conditionnel) + 过去分词；futur_proche 由 aller 现在时 + 不定式自动拼。
_IRREGULAR: dict[str, dict] = {
    "être": {
        "présent": ("suis", "es", "est", "sommes", "êtes", "sont"),
        "imparfait": ("étais", "étais", "était", "étions", "étiez", "étaient"),
        "futur_simple": ("serai", "seras", "sera", "serons", "serez", "seront"),
        "conditionnel": ("serais", "serais", "serait", "serions", "seriez", "seraient"),
        "participe_passé": "été",
    },
    "avoir": {
        "présent": ("ai", "as", "a", "avons", "avez", "ont"),
        "imparfait": ("avais", "avais", "avait", "avions", "aviez", "avaient"),
        "futur_simple": ("aurai", "auras", "aura", "aurons", "aurez", "auront"),
        "conditionnel": ("aurais", "aurais", "aurait", "aurions", "auriez", "auraient"),
        "participe_passé": "eu",
    },
    "aller": {
        "présent": ("vais", "vas", "va", "allons", "allez", "vont"),
        "imparfait": ("allais", "allais", "allait", "allions", "alliez", "allaient"),
        "futur_simple": ("irai", "iras", "ira", "irons", "irez", "iront"),
        "conditionnel": ("irais", "irais", "irait", "irions", "iriez", "iraient"),
        "participe_passé": "allé",
    },
    "faire": {
        "présent": ("fais", "fais", "fait", "faisons", "faites", "font"),
        "imparfait": ("faisais", "faisais", "faisait", "faisions", "faisiez", "faisaient"),
        "futur_simple": ("ferai", "feras", "fera", "ferons", "ferez", "feront"),
        "conditionnel": ("ferais", "ferais", "ferait", "ferions", "feriez", "feraient"),
        "participe_passé": "fait",
    },
    "voir": {
        "présent": ("vois", "vois", "voit", "voyons", "voyez", "voient"),
        "imparfait": ("voyais", "voyais", "voyait", "voyions", "voyiez", "voyaient"),
        "futur_simple": ("verrai", "verras", "verra", "verrons", "verrez", "verront"),
        "conditionnel": ("verrais", "verrais", "verrait", "verrions", "verriez", "verraient"),
        "participe_passé": "vu",
    },
    "pouvoir": {
        "présent": ("peux", "peux", "peut", "pouvons", "pouvez", "peuvent"),
        "imparfait": ("pouvais", "pouvais", "pouvait", "pouvions", "pouviez", "pouvaient"),
        "futur_simple": ("pourrai", "pourras", "pourra", "pourrons", "pourrez", "pourront"),
        "conditionnel": ("pourrais", "pourrais", "pourrait", "pourrions", "pourriez", "pourraient"),
        "participe_passé": "pu",
    },
    "vouloir": {
        "présent": ("veux", "veux", "veut", "voulons", "voulez", "veulent"),
        "imparfait": ("voulais", "voulais", "voulait", "voulions", "vouliez", "voulaient"),
        "futur_simple": ("voudrai", "voudras", "voudra", "voudrons", "voudrez", "voudront"),
        "conditionnel": ("voudrais", "voudrais", "voudrait", "voudrions", "voudriez", "voudraient"),
        "participe_passé": "voulu",
    },
}


def conjugate(infinitive: str, vtype: str) -> dict[str, object]:
    """返回 {tense: (6 forms)} + participe_passé(单值)。vtype ∈ {er, ir2, re, irregular}。"""
    if vtype == "irregular":
        tbl = _IRREGULAR.get(infinitive)
        if tbl is None:
            raise KeyError(f"无核对过的不规则表: {infinitive}")
        out = dict(tbl)
        out["futur_proche"] = tuple(f"{a} {infinitive}" for a in _ALLER_PRESENT)
        return out
    if vtype not in _END:
        raise KeyError(f"未知规则类型: {vtype}（不规则动词请用核对过的表）")
    stem = infinitive[:-2]                            # er/ir 去 2；re 去 2（attend|re）
    out: dict[str, object] = {}
    out["présent"] = tuple(_soften(stem, e, vtype) for e in _END[vtype]["présent"])
    out["imparfait"] = tuple(_soften(stem, e, vtype) for e in _END[vtype]["imparfait"])
    fstem = _future_stem(infinitive, vtype)
    out["futur_simple"] = tuple(fstem + e for e in _FUT_END)
    out["conditionnel"] = tuple(fstem + e for e in _COND_END)
    out["futur_proche"] = tuple(f"{a} {infinitive}" for a in _ALLER_PRESENT)
    pp = {"er": stem + "é", "ir2": stem + "i", "re": stem + "u"}[vtype]
    out["participe_passé"] = pp
    return out


# 时态中文标签（展示用）
TENSE_LABELS = {
    "présent": "直陈式现在时",
    "imparfait": "未完成过去时",
    "futur_simple": "简单将来时",
    "conditionnel": "条件式现在时",
    "futur_proche": "最近将来时",
    "participe_passé": "过去分词",
}
