# L18 词库 + 听写双模式 + Anki 只读富化 实现计划（Phase 1）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 L18 复习词整理成结构化词表，并升级听写为「学习/考试」双模式、答完显示中文词义、对已制卡的词只读拉取 Anki 富内容。

**Architecture:** 纯逻辑拆进可测模块（`vocab.py` 清洗/解析/加载、`anki.py` 只读 AnkiConnect+去 HTML、`store.py` sqlite 导入/查询），`app.py` 只做 Streamlit 编排并加缓存。词义内容运行时从 `../L*/vocab.json` 读，不改 DB 表结构，历史零改动。

**Tech Stack:** Python 3.11、Streamlit、sqlite3、macOS `say`、AnkiConnect v6（只读）、pytest。

参考 spec：`docs/specs/2026-06-08-l18-wordbank-dual-mode-anki-enrichment-design.md`

---

## 文件结构

- `store.py`（新）：`DB_PATH`、`get_conn`、`import_vocab_into_db`、`get_ids_for_lemmas`。无 streamlit 依赖，可单测。
- `vocab.py`（新）：`clean_lemma`、`derive_pos`、`parse_lesson_table`、`load_all_vocab`。无 streamlit 依赖，可单测。
- `anki.py`（新）：`html_to_text`、`first_example`、`enrich`（只读 AnkiConnect 客户端）。无 streamlit 依赖，可单测（网络部分 monkeypatch）。
- `scripts/build_vocab.py`（新）：从课表 + `words.txt` 生成 `../L17/vocab.json`、`../L18/vocab.json`，并打印样本/diff。
- `本地录屏课/L18/source/lecon23.tsv|lecon24.tsv|lecon25.tsv`（新）：用户提供的三张课表原文（制表符：类别<TAB>Français<TAB>中文）。
- `本地录屏课/L17/vocab.json`、`本地录屏课/L18/vocab.json`（生成）。
- `app.py`（改）：导入 store/vocab/anki；双模式侧栏；答后词义面板。
- `tests/test_vocab.py`、`tests/test_anki.py`、`tests/test_store.py`（新）。

> 路径说明：`app.py` 的工作目录是 `听写/`，课程文件夹是其同级 `../L17`、`../L18`。

---

## Task 0:（可选）初始化 git，建立回滚基线

**Files:** Create `.gitignore`

- [ ] **Step 1: 写 `.gitignore`**

```gitignore
__pycache__/
*.pyc
dictation.db
dictation.db.*.bak
.streamlit/secrets.toml
venv/
```

- [ ] **Step 2: 初始化并提交当前状态作为基线**

```bash
git init
git add -A
git commit -m "chore: baseline before L18 wordbank + dual-mode dictation"
```

Expected: 一个初始提交。若你不想用 git，跳过本任务，后续各 Task 的 commit 步骤视为 no-op（用 `dictation.db.*.bak` 做回滚）。

---

## Task 1: 落地三张课表原文为数据文件

**Files:** Create `../L18/source/lecon23.tsv`, `../L18/source/lecon24.tsv`, `../L18/source/lecon25.tsv`

来源 = 本设计会话中用户提供的三张课表。每行 `类别<TAB>Français<TAB>中文`，去掉表头与分隔线。

- [ ] **Step 1: 建目录**

Run: `mkdir -p ../L18/source`

- [ ] **Step 2: 写入三张表**（lecon23 = Leçon 23 / lecon24 = Leçon 24 / lecon25 = Leçon 25，各取对应那张表的全部词行）

`lecon23.tsv` 开头示例（完整内容按会话里的 Leçon 23 表）：

```
NOMS	la confiture	果酱
NOMS	le légume	蔬菜
...
AUTRES	à table	进餐
```

`lecon24.tsv`、`lecon25.tsv` 同理（分别是 Leçon 24、Leçon 25 全部词行）。

- [ ] **Step 3: 校验行数**

Run: `wc -l ../L18/source/lecon23.tsv ../L18/source/lecon24.tsv ../L18/source/lecon25.tsv`
Expected: 约 42 / 44 / 56 行（与课表词数一致，无表头行）。

- [ ] **Step 4: Commit**

```bash
git add ../L18/source/*.tsv
git commit -m "data: capture Leçon 23/24/25 source tables for L18"
```

---

## Task 2: `vocab.clean_lemma` —— 清洗听写目标

**Files:** Create `vocab.py`, `tests/test_vocab.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_vocab.py
from vocab import clean_lemma

def test_clean_lemma_strips_grammar_abbr_and_ipa_and_notes():
    cases = {
        "la confiture": "la confiture",
        "un sandwich [sãdwitʃ]": "un sandwich",
        "l'eau n. f.": "l'eau",
        "les gens n. m. pl.": "les gens",
        "sentir v. t.": "sentir",
        "approcher v. t. ind": "approcher",
        "augmenter v. i. ou v. t.": "augmenter",
        "prévoir v. t.（变位同 voir）": "prévoir",
        "choisir v. t.（第二组动词）": "choisir",
        "peu adv.": "peu",
        "en dehors de loc. prép.": "en dehors de",
        "d'autre part loc. adv.": "d'autre part",
        "or conj.": "or",
        "Parisien, ne": "Parisien",
        "client, e": "client",
        "conducteur, trice": "conducteur",
        "délicieux, se": "délicieux",
        "tenir compte de": "tenir compte de",
        "se garer": "se garer",
        "à la place de": "à la place de",
    }
    for raw, expected in cases.items():
        assert clean_lemma(raw) == expected, raw
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m pytest tests/test_vocab.py::test_clean_lemma_strips_grammar_abbr_and_ipa_and_notes -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'vocab'`）

- [ ] **Step 3: 实现 `clean_lemma`**

```python
# vocab.py
from __future__ import annotations

import re

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


def clean_lemma(raw: str) -> str:
    """从课表 Français 单元格得到朗读&听写目标。"""
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
    if "," in s:                              # 阴阳性/词形对取基本形
        s = s.split(",", 1)[0]
    return s.strip()
```

- [ ] **Step 4: 运行确认通过**

Run: `python3 -m pytest tests/test_vocab.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add vocab.py tests/test_vocab.py
git commit -m "feat(vocab): clean_lemma with grammar/IPA/note stripping"
```

---

## Task 3: `vocab.derive_pos` —— 推导词性

**Files:** Modify `vocab.py`, `tests/test_vocab.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_vocab.py（追加）
from vocab import derive_pos

def test_derive_pos():
    assert derive_pos("NOMS", "la confiture") == "noun"
    assert derive_pos("VERBES", "manger v. t.") == "verb"
    assert derive_pos("ADJECTIFS", "délicieux, se") == "adj"
    assert derive_pos("AUTRES", "peu adv.") == "adverb"
    assert derive_pos("AUTRES", "or conj.") == "conj"
    assert derive_pos("AUTRES", "en dehors de loc. prép.") == "prep"
    assert derive_pos("AUTRES", "à table") == "expr"
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m pytest tests/test_vocab.py::test_derive_pos -v`
Expected: FAIL（`ImportError: cannot import name 'derive_pos'`）

- [ ] **Step 3: 实现 `derive_pos`**

```python
# vocab.py（追加）
_POS_BY_CATEGORY = {"NOMS": "noun", "VERBES": "verb", "ADJECTIFS": "adj"}


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
```

- [ ] **Step 4: 运行确认通过**

Run: `python3 -m pytest tests/test_vocab.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add vocab.py tests/test_vocab.py
git commit -m "feat(vocab): derive_pos from category/abbreviation"
```

---

## Task 4: `vocab.parse_lesson_table` —— 解析一张课表 TSV

**Files:** Modify `vocab.py`, `tests/test_vocab.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_vocab.py（追加）
from vocab import parse_lesson_table

def test_parse_lesson_table():
    raw = (
        "NOMS\tla confiture\t果酱\n"
        "VERBES\tprévoir v. t.（变位同 voir）\t预备\n"
        "AUTRES\ten dehors de loc. prép.\t在……外面\n"
        "\n"  # 空行跳过
    )
    rows = parse_lesson_table(raw, lesson="L18", source_lesson="Leçon25")
    assert rows[0] == {
        "lemma": "la confiture", "pos": "noun", "zh": "果酱",
        "lesson": "L18", "source_lesson": "Leçon25",
        "category": "NOMS", "example": None, "raw": "la confiture",
    }
    assert rows[1]["lemma"] == "prévoir" and rows[1]["pos"] == "verb"
    assert rows[2]["lemma"] == "en dehors de" and rows[2]["pos"] == "prep"
    assert len(rows) == 3
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m pytest tests/test_vocab.py::test_parse_lesson_table -v`
Expected: FAIL（`ImportError`）

- [ ] **Step 3: 实现 `parse_lesson_table`**

```python
# vocab.py（追加）
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
            }
        )
    return out
```

- [ ] **Step 4: 运行确认通过**

Run: `python3 -m pytest tests/test_vocab.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add vocab.py tests/test_vocab.py
git commit -m "feat(vocab): parse_lesson_table -> structured entries"
```

---

## Task 5: 生成 vocab.json（含 L17 历史对齐 + 样本评审）

**Files:** Create `scripts/build_vocab.py`

- [ ] **Step 1: 写生成脚本**

```python
# scripts/build_vocab.py
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
    s = " ".join(s.strip().lower().split())
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
    print("\n--- L18 样本（前 8）---")
    for e in l18[:8]:
        print(f"  {e['lemma']:24} [{e['pos']:6}] {e['zh']}   <= {e['raw']}")
    if misses:
        print(f"\n⚠️ L17 有 {len(misses)} 个 words.txt 词未在 Leçon25 表里匹配到（zh/pos 留空，请人工确认）：")
        for m in misses:
            print("   ", m)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 运行生成并人工评审样本**

Run: `python3 scripts/build_vocab.py`
Expected: 打印 L18/L17 词数 + 前 8 样本 + 未匹配清单。**停下来人工核对样本 lemma/pos/zh 是否合理、未匹配项是否需要手工补**。如清洗有错，回到 Task 2/3 调规则再跑。

- [ ] **Step 3: 抽查生成的 JSON**

Run: `python3 -c "import json;d=json.load(open('../L18/vocab.json'));print(len(d));print(d[0]);print([x['lemma'] for x in d if ',' in x['raw']][:10])"`
Expected: 词数合理；阴阳性词条 lemma 不含逗号。

- [ ] **Step 4: Commit**

```bash
git add scripts/build_vocab.py ../L17/vocab.json ../L18/vocab.json
git commit -m "feat(vocab): generate L17/L18 vocab.json from source tables"
```

---

## Task 6: `vocab.load_all_vocab` —— 运行时加载并合并

**Files:** Modify `vocab.py`, `tests/test_vocab.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_vocab.py（追加）
import json
from vocab import load_all_vocab

def test_load_all_vocab(tmp_path):
    base = tmp_path / "本地录屏课"
    (base / "L17").mkdir(parents=True)
    (base / "L18").mkdir(parents=True)
    (base / "L17" / "vocab.json").write_text(json.dumps(
        [{"lemma": "aussi", "pos": "adverb", "zh": "也", "lesson": "L17",
          "source_lesson": "Leçon25", "category": "AUTRES", "example": None, "raw": "aussi adv."}],
        ensure_ascii=False), "utf-8")
    (base / "L18" / "vocab.json").write_text(json.dumps(
        [{"lemma": "aussi", "pos": "adverb", "zh": "也", "lesson": "L18",
          "source_lesson": "Leçon25", "category": "AUTRES", "example": None, "raw": "aussi adv."},
         {"lemma": "la confiture", "pos": "noun", "zh": "果酱", "lesson": "L18",
          "source_lesson": "Leçon23", "category": "NOMS", "example": None, "raw": "la confiture"}],
        ensure_ascii=False), "utf-8")

    by_lemma, by_lesson = load_all_vocab(base)
    assert by_lemma["la confiture"]["zh"] == "果酱"
    assert set(by_lemma["aussi"]["lessons"]) == {"L17", "L18"}   # 跨课合并
    assert by_lesson["L18"] == ["aussi", "la confiture"]
    assert by_lesson["L17"] == ["aussi"]
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m pytest tests/test_vocab.py::test_load_all_vocab -v`
Expected: FAIL（`ImportError`）

- [ ] **Step 3: 实现 `load_all_vocab`**

```python
# vocab.py（追加）
import json
from pathlib import Path


def load_all_vocab(base_dir):
    """扫描 base_dir/L*/vocab.json，返回 (by_lemma, by_lesson)。
    by_lemma[lemma] = {pos, zh, example, lessons:[...]}；by_lesson[lesson] = [lemma,...]（按文件顺序）。"""
    base = Path(base_dir)
    by_lemma: dict[str, dict] = {}
    by_lesson: dict[str, list[str]] = {}
    for vj in sorted(base.glob("L*/vocab.json")):
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
                        "example": e.get("example"), "lessons": []}
            )
            if lesson not in slot["lessons"]:
                slot["lessons"].append(lesson)
            if not slot["zh"] and e.get("zh"):
                slot["zh"] = e["zh"]
    return by_lemma, by_lesson
```

- [ ] **Step 4: 运行确认通过**

Run: `python3 -m pytest tests/test_vocab.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add vocab.py tests/test_vocab.py
git commit -m "feat(vocab): load_all_vocab runtime merge"
```

---

## Task 7: `store` —— sqlite 导入/查询（可测）

**Files:** Create `store.py`, `tests/test_store.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_store.py
import sqlite3
import store

def _make_db(path):
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE words (id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT NOT NULL UNIQUE, wrong_count INTEGER NOT NULL DEFAULT 0,
        correct_streak INTEGER NOT NULL DEFAULT 0, interval_days INTEGER NOT NULL DEFAULT 0,
        due_at TEXT, last_seen_at TEXT, created_at TEXT NOT NULL)""")
    conn.commit(); conn.close()

def test_import_is_idempotent_and_preserves_existing(tmp_path, monkeypatch):
    db = tmp_path / "d.db"; _make_db(db)
    monkeypatch.setattr(store, "DB_PATH", str(db))
    # 预置一条带历史的老词
    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO words (text, wrong_count, created_at) VALUES ('aussi', 5, '2026-01-01')")
    conn.commit(); conn.close()

    assert store.import_vocab_into_db({"aussi": {}, "la confiture": {}}) == 1   # 只插新词
    assert store.import_vocab_into_db({"aussi": {}, "la confiture": {}}) == 0   # 幂等
    conn = sqlite3.connect(db)
    wc = conn.execute("SELECT wrong_count FROM words WHERE text='aussi'").fetchone()[0]
    n = conn.execute("SELECT COUNT(*) FROM words").fetchone()[0]
    conn.close()
    assert wc == 5 and n == 2   # 历史不动、无重复

def test_get_ids_for_lemmas(tmp_path, monkeypatch):
    db = tmp_path / "d.db"; _make_db(db)
    monkeypatch.setattr(store, "DB_PATH", str(db))
    store.import_vocab_into_db({"aussi": {}, "la confiture": {}})
    ids = store.get_ids_for_lemmas(["aussi", "nope", "la confiture"])
    assert len(ids) == 2
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m pytest tests/test_store.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'store'`）

- [ ] **Step 3: 实现 `store.py`**

```python
# store.py
from __future__ import annotations

import sqlite3
from datetime import datetime

DB_PATH = "dictation.db"


def get_conn():
    return sqlite3.connect(DB_PATH)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def import_vocab_into_db(vocab) -> int:
    """把词表里的新 lemma 插入 words 表（已存在跳过）。返回新插入数。"""
    conn = get_conn()
    cur = conn.cursor()
    inserted = 0
    for lemma in vocab:
        try:
            cur.execute("INSERT INTO words (text, created_at) VALUES (?, ?)", (lemma, _now()))
            inserted += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()
    return inserted


def get_ids_for_lemmas(lemmas) -> list[int]:
    lemmas = list(lemmas)
    if not lemmas:
        return []
    conn = get_conn()
    ph = ",".join(["?"] * len(lemmas))
    rows = conn.execute(f"SELECT id FROM words WHERE text IN ({ph})", lemmas).fetchall()
    conn.close()
    return [r[0] for r in rows]
```

- [ ] **Step 4: 运行确认通过**

Run: `python3 -m pytest tests/test_store.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add store.py tests/test_store.py
git commit -m "feat(store): testable vocab import + lemma->id lookup"
```

---

## Task 8: `anki.html_to_text` 与 `first_example`

**Files:** Create `anki.py`, `tests/test_anki.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_anki.py
from anki import html_to_text, first_example

def test_html_to_text():
    assert html_to_text('<div class="x"><p>用于正式场合</p></div>') == "用于正式场合"
    assert html_to_text('a<br>b') == "a b"
    assert html_to_text('Tom &amp; Jerry') == "Tom & Jerry"
    assert html_to_text("") == ""

def test_first_example():
    html = ('<ul class="examples"><li><span class="sentence">Allez-y, je vous écoute.</span></li>'
            '<li><span class="sentence">Deuxième phrase.</span></li></ul>')
    assert first_example(html) == "Allez-y, je vous écoute."
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m pytest tests/test_anki.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'anki'`）

> 注意：模块命名为本地 `anki.py`，确保运行测试时工作目录是 `听写/`，不会与外部包冲突。

- [ ] **Step 3: 实现 html 工具**

```python
# anki.py
from __future__ import annotations

import html as _html
import re


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
```

- [ ] **Step 4: 运行确认通过**

Run: `python3 -m pytest tests/test_anki.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add anki.py tests/test_anki.py
git commit -m "feat(anki): html_to_text + first_example"
```

---

## Task 9: `anki.enrich` —— 只读拉取词卡富内容

**Files:** Modify `anki.py`, `tests/test_anki.py`

- [ ] **Step 1: 写失败测试（monkeypatch 掉网络层 `_anki`）**

```python
# tests/test_anki.py（追加）
import anki

def test_enrich_hit(monkeypatch):
    calls = {}
    def fake(action, **params):
        calls[action] = params
        if action == "findNotes":
            return [111]
        if action == "notesInfo":
            return [{"note": 111, "fields": {
                "Lemma": {"value": '<span class="targetword">augmenter</span>'},
                "Core Meaning": {"value": "<p>增长，提高</p>"},
                "Example Sentences": {"value": '<ul><li><span>Les prix augmentent.</span></li></ul>'},
                "IPA + Pronunciation Notes": {"value": "<p>/ɔɡmɑ̃te/</p>"},
            }}]
        return []
    monkeypatch.setattr(anki, "_anki", fake)
    out = anki.enrich("augmenter")
    assert out["core_meaning"] == "增长，提高"
    assert out["example"] == "Les prix augmentent."
    assert "ɔɡmɑ" in out["ipa"]

def test_enrich_degrades_when_anki_down(monkeypatch):
    def boom(action, **params):
        raise OSError("connection refused")
    monkeypatch.setattr(anki, "_anki", boom)
    assert anki.enrich("augmenter") is None
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m pytest tests/test_anki.py -k enrich -v`
Expected: FAIL（`AttributeError: module 'anki' has no attribute '_anki'`）

- [ ] **Step 3: 实现只读客户端 + `enrich`**

```python
# anki.py（追加）
import json
import unicodedata
import urllib.error
import urllib.request

ANKI_URL = "http://127.0.0.1:8765"
DECK = "Français"


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
    ids = _anki("findNotes", query=f'deck:"{DECK}" "{core}"')
    if not ids:
        return None
    infos = _anki("notesInfo", notes=ids[:10])
    target = _norm(lemma)
    target_core = _norm(core)
    for info in infos:
        lem = html_to_text(info.get("fields", {}).get("Lemma", {}).get("value", ""))
        if _norm(lem) == target or _norm(_strip_article(lem)) == target_core:
            return info
    return infos[0] if infos else None


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
```

- [ ] **Step 4: 运行确认通过**

Run: `python3 -m pytest tests/test_anki.py -v`
Expected: PASS

- [ ] **Step 5:（可选）真机联调**

Run: `python3 -c "import anki; print(anki.enrich('un autobus')); print(anki.enrich('zzz不存在'))"`
Expected: 前者打印含 core_meaning 的 dict（Anki 开着且已制卡）；后者 `None`。

- [ ] **Step 6: Commit**

```bash
git add anki.py tests/test_anki.py
git commit -m "feat(anki): read-only enrich() over AnkiConnect"
```

---

## Task 10: app.py 接入 —— 启动加载词表 + 导入新词

**Files:** Modify `app.py`

- [ ] **Step 1: 顶部接入模块与缓存加载**

在 `import` 区加入（紧挨现有 `import` 之后）：

```python
from pathlib import Path
import vocab as vocab_mod
import anki as anki_mod
from store import import_vocab_into_db, get_ids_for_lemmas

BASE_DIR = Path(__file__).resolve().parent.parent  # 本地录屏课/


@st.cache_data(show_spinner=False)
def load_vocab():
    return vocab_mod.load_all_vocab(BASE_DIR)


@st.cache_data(show_spinner=False)
def enrich_cached(lemma: str):
    return anki_mod.enrich(lemma)
```

- [ ] **Step 2: `init_db()` 之后导入词表新词**

定位 `init_db()` 调用（页面区，`st.set_page_config` 之后），改为：

```python
init_db()

VOCAB, LESSONS = load_vocab()
import_vocab_into_db(VOCAB)   # 仅插入新 lemma，老词历史不动
```

- [ ] **Step 3: 启动一次，确认无报错且词已入库**

Run: `streamlit run app.py --server.headless true --server.port 8540 >/tmp/st.log 2>&1 & sleep 4; curl -s -o /dev/null -w "%{http_code}\n" localhost:8540/_stcore/health; grep -iE "error|traceback" /tmp/st.log || echo no-errors; pkill -f "server.port 8540"`
Expected: `200` + `no-errors`

Run: `sqlite3 dictation.db "SELECT COUNT(*) FROM words;"`
Expected: 比原来的 58 多（新增 Leçon23/24 词）。

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat(app): load vocab.json at startup and import new lemmas"
```

---

## Task 11: app.py —— 学习模式（选课）侧栏

**Files:** Modify `app.py`

- [ ] **Step 1: 新增 `start_lesson_round` 辅助函数**

放在现有 `start_full_round` 旁：

```python
def start_lesson_round(lesson: str, lessons_map: dict, batch_size: int) -> int:
    """学习模式：练某一课（或「全部」）。返回总词数。"""
    if lesson == "全部":
        ids = [row["id"] for row in get_all_words()]
    else:
        ids = get_ids_for_lemmas(lessons_map.get(lesson, []))
    random.shuffle(ids)
    reset_round(ids, batch_size)
    return len(ids)
```

- [ ] **Step 2: 侧栏把「开始新一轮：完整词库」换成选课**

定位侧栏中：

```python
    if st.button("开始新一轮：完整词库随机不放回"):
        start_full_round(batch_size)
        st.rerun()
```

替换为：

```python
    st.subheader("学习模式")
    lesson_options = ["全部"] + sorted(LESSONS)
    chosen_lesson = st.selectbox("选课", lesson_options)
    if st.button("开始这一课"):
        n = start_lesson_round(chosen_lesson, LESSONS, batch_size)
        if n == 0:
            st.warning("这一课还没有词。")
        else:
            st.rerun()

    st.subheader("考试模式")
```

（保留其后的 `review_due_only` 复选框与「开始复习：错题库按优先级」按钮，作为考试模式。）

- [ ] **Step 3: 启动点测两模式入口**

Run: `streamlit run app.py --server.headless true --server.port 8541 >/tmp/st.log 2>&1 & sleep 4; curl -s -o /dev/null -w "%{http_code}\n" localhost:8541/_stcore/health; grep -iE "error|traceback" /tmp/st.log || echo no-errors; pkill -f "server.port 8541"`
Expected: `200` + `no-errors`（人工浏览器里确认侧栏出现「学习模式/选课」与「考试模式」）。

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat(app): study mode (per-lesson) sidebar + exam mode label"
```

---

## Task 12: app.py —— 答后词义面板（中文 + Anki 只读富化）

**Files:** Modify `app.py`

- [ ] **Step 1: 新增渲染函数**

```python
def render_learn_panel(lemma: str) -> None:
    """答完/显示答案后，展示中文词义 + 可选的 Anki 富内容。"""
    entry = VOCAB.get(lemma)
    if entry and entry.get("zh"):
        st.markdown(f"**释义**：{entry['zh']}")
    rich = enrich_cached(lemma)
    if rich:
        if rich.get("core_meaning"):
            st.markdown(f"**Anki·核心义**：{rich['core_meaning']}")
        if rich.get("example"):
            st.markdown(f"**例句**：{rich['example']}")
        if rich.get("ipa"):
            st.caption(f"IPA：{rich['ipa']}")
```

- [ ] **Step 2: 在「显示答案」与「提交后反馈」处调用**

定位显示答案分支：

```python
    if st.session_state.show_answer:
        st.info(f"答案：{current_word['text']}")
```

改为：

```python
    if st.session_state.show_answer:
        st.info(f"答案：{current_word['text']}")
        render_learn_panel(current_word["text"])
```

定位反馈渲染块：

```python
    if st.session_state.feedback:
        if st.session_state.feedback["type"] == "success":
            st.success(st.session_state.feedback["message"])
        else:
            st.error(st.session_state.feedback["message"])
```

在其后追加：

```python
        render_learn_panel(current_word["text"])
```

（注意缩进与 `if st.session_state.feedback:` 同级块内。）

- [ ] **Step 3: 真机点测学习闭环**

Run: `streamlit run app.py`（前台），浏览器里：
1. 学习模式选 `L18` → 开始这一课 → 听写一个词 → 提交 → 应看到「释义」（中文）；若该词已制卡且 Anki 开着，应看到「Anki·核心义/例句/IPA」。
2. 关掉 Anki（或不开）→ 同样流程 → 只看到中文释义，无报错。
3. 考试模式（错题复习）→ 答完同样能看到释义。

Expected: 释义稳定出现；Anki 没开时安静降级。

- [ ] **Step 4: 跑全部单测**

Run: `python3 -m pytest -q`
Expected: 全绿。

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "feat(app): show meaning + read-only Anki enrichment after answering"
```

---

## Self-Review（写完计划后的自查结论）

- **Spec 覆盖**：3.1 词表→Task1-6；历史对齐→Task5；3.2 双模式→Task11、答后词义→Task12；3.3 最小改动导入→Task7、Task10；3.4 Anki 只读→Task8、Task9；3.6 测试→各 Task 的 TDD + Task7/9 关键分支。无遗漏。
- **占位符**：无 TBD；唯一"数据录入"在 Task1（用户已提供原表，执行时落盘）。
- **类型/命名一致**：`load_all_vocab(base)->(by_lemma,by_lesson)`、`LESSONS` 即 `by_lesson`、`VOCAB` 即 `by_lemma`；`start_lesson_round(lesson, lessons_map, batch_size)`、`enrich(lemma)->{core_meaning,example,ipa}|None`、`import_vocab_into_db/get_ids_for_lemmas` 在 Task7 定义、Task10/11 使用，一致。
- **风险兜底**：迁移前已有 `dictation.db.*.bak`；导入只插新词（Task7 幂等测试）；Anki 全程只读（Task9 降级测试）。
```
