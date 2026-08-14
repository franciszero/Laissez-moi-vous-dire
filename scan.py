"""扫读（速过）的纯逻辑：方向表、分页、一页的行模型与提交结果。

无 Streamlit / sqlite3 依赖，可单测。对标 roundlogic.py、mastery.py、srs.py。
"""
from __future__ import annotations

# 方向名 → (skill, 明码字段, 盖住字段, ▶是否跟着一起锁)
#
# 「看中→想法」的 ▶ 必须锁：法语被盖住的时候还能听发音，等于把答案念出来了。
# 另外两档的发音不构成泄题——看法→想中时法语本来就明摆着；听音→想双时
# 发音就是唯一的题面。
DIRECTIONS: dict[str, tuple[str, str | None, tuple[str, ...], bool]] = {
    "看法→想中": ("rec_meaning", "fr", ("zh",), False),
    "看中→想法": ("rec_produce", "zh", ("fr",), True),
    "听音→想双": ("rec_audio", None, ("fr", "zh"), False),
}

REC_SKILLS: tuple[str, ...] = tuple(spec[0] for spec in DIRECTIONS.values())


def paginate(word_ids, page_size: int) -> list[list[int]]:
    """切页。page_size <= 0 或大于总数都视为不分页（全部一页）。空表返回 []。"""
    ids = list(word_ids)
    if not ids:
        return []
    if page_size <= 0 or page_size >= len(ids):
        return [ids]
    return [ids[i:i + page_size] for i in range(0, len(ids), page_size)]


def page_rows(page_ids, id_to_lemma: dict, lemma_to_zh: dict, start_no: int = 1) -> list[dict]:
    """一页的行模型。

    序号 no 是**整课连续编号**，不是页内编号——用户在第 2 页看到 21..40，
    和整课进度对得上，回头说「第 27 个不会」也有意义。
    """
    rows = []
    for offset, wid in enumerate(page_ids):
        lemma = id_to_lemma.get(wid, "")
        rows.append(
            {
                "no": start_no + offset,
                "word_id": wid,
                "fr": lemma,
                "zh": lemma_to_zh.get(lemma) or "（无释义）",
            }
        )
    return rows


def commit(rows, missed_nos) -> list[tuple[int, bool]]:
    """一页的行 + 用户勾了哪几个序号 → [(word_id, 是否算会), ...]。

    没勾的算会：扫读的默认动作是「过」，只有想不起来才动手标。
    """
    missed = set(missed_nos)
    return [(r["word_id"], r["no"] not in missed) for r in rows]


def parse_missed(raw) -> set[int]:
    """把 "3,7,12" 这种回传串解析成序号集合。脏值静默丢弃——这串是从
    浏览器来的，宁可少标一个也不能让一页的提交整个炸掉。"""
    out: set[int] = set()
    for chunk in (raw or "").replace(" ", "").split(","):
        if chunk.isdigit():
            out.add(int(chunk))
    return out
