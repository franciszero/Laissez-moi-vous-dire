# 速过视图施工卡（Sonnet 5 可执行版）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按 `docs/specs/2026-08-13-vocab-scan-design.md`，把 150+ 词的过词从「逐词打字、450 次 rerun」换成「整页扫读、每页 1 次提交」，并新增独立的「认」技能维度。

**Architecture:** 纯逻辑抽成 `scan.py` / `scanaudio.py`（无 Streamlit 依赖，可单测），持久化落在 `store.py`，`app.py` 只做编排并新增第三个 overlay。盖/揭与逐词播放全在浏览器端完成，不产生 rerun；一页的勾选经 `st.form` 一次回传。

**Tech Stack:** Python 3 / sqlite3（只在 store.py）/ macOS `say` / Streamlit 1.58 原生组件 + `components.html` 注入脚本（本仓库既有手法）/ `streamlit.testing.v1.AppTest` / pytest。

## Global Constraints

- `scan.py`、`scanaudio.py` 禁止 import `streamlit`、`sqlite3`、`app`（A1/A3 卡内有 import 纯度测试强制）。
- **扫读绝不 UPDATE `words` 表**。`words.correct_streak / interval_days / due_at / wrong_count` 归 `app.record_attempt` 独占。A2 卡有专门的不变量测试守这条。
- 不改 `matcher.check_fr` 的判分口径（`docs/BACKLOG.md` 第 3 条：零容错是用户的明确选择）。
- 不新增数据库表、不改任何既有列。`attempts.skill` 是自由文本列，只加三个新值：`rec_meaning` / `rec_produce` / `rec_audio`。
- 测试禁止裸 `import app`（`docs/BACKLOG.md` 第 7 条），一律用 `AppTest.from_file("app.py")`。
- 不做假表格、不堆按钮墙、不加全局 CSS `!important`（`AGENTS.md` 既有模式闸门）。一行一个 `st.button` 是明令禁止的形态。
- 新文件以 `from __future__ import annotations` 开头，中文注释风格与仓库一致。
- 不加任何新依赖。
- 每张卡结束：先跑本卡目标测试，再跑全量 `python3 -m pytest -q`，全绿才 commit。

## 卡片总览与派工

| 卡 | 内容 | 执行者 | 依赖 |
|---|---|---|---|
| S0 | JS→Streamlit 回传验证 | ~~人工~~ **已完成，结论 A** | — |
| A1 | `scan.py` 纯逻辑（方向表/分页/行模型/提交） | Sonnet 5 | 无 |
| A2 | `store.record_scan_page` + words 不变量测试 | Sonnet 5 | 无 |
| A3 | `scanaudio.py` 发音缓存 + 静态服务配置 | Sonnet 5 | 无 |
| B1 | `mastery.REC_SKILLS` + 词表「认」色列 | Sonnet 5 | A1 |
| B2 | overlay 骨架：侧栏入口 + 互斥 + 空壳视图 | Sonnet 5 | A1 |
| B3 | 扫读表渲染：三种揭法 + 逐词 ▶ | Sonnet 5 | A3, B2 |
| B4 | 提交回路：form + 勾选回传 + 入库（走 A 路） | Sonnet 5 | A2, B3 |
| B5 | 接慢流程：漏词 → `reset_round` + 端到端 | Sonnet 5 | B4 |
| F | 用户真实使用验收 | **人工** | B5 |

执行顺序固定：**A1 → A2 → A3 → B1 → B2 → B3 → B4 → B5 → F**（S0 已完成）。
不并行——A2/B1/B2 之后每张卡都碰 `app.py`。

---

### Task S0: 回传通路验证（已完成 2026-08-13，结论 **A**）

> **不用再跑。** 2026-08-13 在 Streamlit 1.58.0 + macOS 上真机验过：
> 页面显示 `Python 收到：'2,4'`，`.st-key-spike_missed input` 选择器命中，
> native setter + `input` 事件的写法被 React 收到。**B4 走 A 路。**
>
> 追加验证（比原卡多做的一步）：提交触发 rerun 之后再勾一个，sink 立刻变成
> `"2,3,4"` —— 重挂脚本这条路也是通的。这一步暴露了 B3 原稿的一个 bug，
> 已在 B3/B4 卡里改掉（见那两张卡的注释）。
>
> 下面的原始步骤保留作记录，**总管不需要执行**。

**目的：** 确认能否用注入的 JS 把纯 HTML 的勾选状态写进 Streamlit 的 `text_input` 并在 form 提交时被 Python 读到。**结论决定 B4 走 A 路还是 B 路，其余卡片不受影响。**

**Files:**
- Create: `tmp/scan_spike.py`（一次性验证脚本，验完即删，不提交）

- [ ] **Step 1: 写验证脚本**

```python
# tmp/scan_spike.py
"""S0 验证：注入的 JS 能否把值写进 Streamlit text_input 并被 form 提交读到。
跑法：python3 -m streamlit run tmp/scan_spike.py --server.port 8599
"""
from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

st.write("勾几个，然后点提交。下面应显示你勾的序号。")

st.markdown(
    "<table id='spike'>"
    + "".join(
        f"<tr><td>{i}</td><td>"
        f"<input type='checkbox' class='spike-miss' data-no='{i}'></td></tr>"
        for i in range(1, 6)
    )
    + "</table>",
    unsafe_allow_html=True,
)

with st.form("spike_form"):
    missed = st.text_input("missed", key="spike_missed", label_visibility="collapsed")
    submitted = st.form_submit_button("提交")

components.html(
    """
    <script>
    (function () {
      const doc = window.parent.document;
      function setInput(el, value) {
        const proto = window.parent.HTMLInputElement.prototype;
        Object.getOwnPropertyDescriptor(proto, "value").set.call(el, value);
        el.dispatchEvent(new (window.parent.Event)("input", {bubbles: true}));
      }
      function bind() {
        const boxes = doc.querySelectorAll(".spike-miss");
        const sink = doc.querySelector(".st-key-spike_missed input");
        if (!boxes.length || !sink) return false;
        boxes.forEach(function (b) {
          b.onchange = function () {
            const on = [...doc.querySelectorAll(".spike-miss")]
              .filter(x => x.checked).map(x => x.dataset.no);
            setInput(sink, on.join(","));
          };
        });
        return true;
      }
      if (!bind()) { setTimeout(bind, 50); setTimeout(bind, 200); }
    })();
    </script>
    """,
    height=0,
    width=0,
)

if submitted:
    st.success(f"Python 收到：{missed!r}")
```

- [ ] **Step 2: 起服务并在真实浏览器里点**

Run: `python3 -m streamlit run tmp/scan_spike.py --server.port 8599`
浏览器打开 http://localhost:8599 ，勾第 2 和第 4 个，点「提交」。

- [ ] **Step 3: 判定**

- 页面显示 `Python 收到：'2,4'` → **A 路成立**，B4 按 A 路写，本卡结论记为 `A`。
- 显示 `Python 收到：''` 或报错 → **A 路不通**，B4 改走 B 路（`st.pills` 多选序号），本卡结论记为 `B`。

两种结论都是正常产出，B 路功能完整、零 JS 风险，只是勾选要从表格挪到下方的序号条。

- [ ] **Step 4: 清理**

```bash
rm -f tmp/scan_spike.py
```

不提交任何东西。把结论（`A` 或 `B`）连同浏览器里看到的真实文字写进给用户的报告。

---

### Task A1: scan.py 纯逻辑

**Files:**
- Create: `scan.py`
- Test: `tests/test_scan.py`

**Interfaces:**
- Consumes: 无
- Produces: `scan.DIRECTIONS`（方向名 → `(skill, 明码字段, 盖住字段元组, ▶是否锁)`）、`scan.REC_SKILLS`、`scan.paginate`、`scan.page_rows`、`scan.commit`、`scan.parse_missed`。后续卡按原样引用，键名与字段名不得改动。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_scan.py
from __future__ import annotations

import ast
import pathlib

import scan


def test_directions_shape():
    assert list(scan.DIRECTIONS) == ["看法→想中", "看中→想法", "听音→想双"]
    assert scan.DIRECTIONS["看法→想中"] == ("rec_meaning", "fr", ("zh",), False)
    assert scan.DIRECTIONS["看中→想法"] == ("rec_produce", "zh", ("fr",), True)
    assert scan.DIRECTIONS["听音→想双"] == ("rec_audio", None, ("fr", "zh"), False)
    assert scan.REC_SKILLS == ("rec_meaning", "rec_produce", "rec_audio")


def test_produce_direction_locks_the_play_button():
    """看中→想法：一听发音就等于给了法语答案，▶ 必须跟着一起锁。"""
    assert scan.DIRECTIONS["看中→想法"][3] is True
    assert scan.DIRECTIONS["看法→想中"][3] is False
    assert scan.DIRECTIONS["听音→想双"][3] is False


def test_paginate_basic():
    assert scan.paginate([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]
    assert scan.paginate([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]


def test_paginate_edges():
    assert scan.paginate([], 20) == []
    assert scan.paginate([7], 20) == [[7]]
    assert scan.paginate([1, 2, 3], 0) == [[1, 2, 3]]      # 0 = 不分页
    assert scan.paginate([1, 2, 3], -5) == [[1, 2, 3]]
    assert scan.paginate([1, 2, 3], 99) == [[1, 2, 3]]


def test_page_rows_numbers_are_lesson_wide():
    """序号是整课连续编号，不是页内编号——第 2 页第 1 行应该是 21。"""
    rows = scan.page_rows(
        [11, 12],
        {11: "la confiture", 12: "s'installer"},
        {"la confiture": "果酱", "s'installer": "定居"},
        start_no=21,
    )
    assert [r["no"] for r in rows] == [21, 22]
    assert rows[0] == {"no": 21, "word_id": 11, "fr": "la confiture", "zh": "果酱"}


def test_page_rows_missing_gloss():
    rows = scan.page_rows([9], {9: "truc"}, {}, start_no=1)
    assert rows[0]["zh"] == "（无释义）"


def test_commit_unmarked_counts_as_known():
    rows = scan.page_rows(
        [1, 2, 3], {1: "a", 2: "b", 3: "c"}, {"a": "甲", "b": "乙", "c": "丙"}
    )
    assert scan.commit(rows, {2}) == [(1, True), (2, False), (3, True)]
    assert scan.commit(rows, set()) == [(1, True), (2, True), (3, True)]


def test_commit_ignores_out_of_range_numbers():
    rows = scan.page_rows([1], {1: "a"}, {"a": "甲"})
    assert scan.commit(rows, {1, 99}) == [(1, False)]


def test_parse_missed():
    assert scan.parse_missed("3,7,12") == {3, 7, 12}
    assert scan.parse_missed(" 3 , 7 ") == {3, 7}
    assert scan.parse_missed("") == set()
    assert scan.parse_missed(None) == set()
    assert scan.parse_missed("3,,x,-1,7") == {3, 7}      # 脏值静默丢弃


def test_scan_module_is_pure():
    """scan.py 不许碰 streamlit / sqlite3 / app —— 它必须能脱离 Streamlit 单测。"""
    tree = ast.parse(pathlib.Path("scan.py").read_text("utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    assert not (names & {"streamlit", "sqlite3", "app"})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m pytest tests/test_scan.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'scan'`）

- [ ] **Step 3: 实现 scan.py（照抄）**

```python
# scan.py
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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 -m pytest tests/test_scan.py -v`
Expected: 10 passed

- [ ] **Step 5: 全量回归**

Run: `python3 -m pytest -q`
Expected: 全绿，无新增 failure

- [ ] **Step 6: 提交**

```bash
git add scan.py tests/test_scan.py
git commit -m "速过：scan.py 纯逻辑（方向表/分页/行模型/提交）"
```

---

### Task A2: 扫读入库，且绝不动 words

**Files:**
- Modify: `store.py`（文件末尾追加）
- Test: `tests/test_scan_store.py`（新建；不改既有 `tests/test_store.py`）

**Interfaces:**
- Consumes: 无（不 import `scan`，skill 白名单在本卡内独立定义，避免 store 依赖 scan）
- Produces: `store.SCAN_SKILLS`、`store.record_scan_page(results, skill) -> int`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_scan_store.py
"""扫读入库的守卫测试。

核心不变量：扫读是自判、没有拼写证据，所以只许往 attempts 插行，
绝不许改 words 的 SRS 状态——那是 app.record_attempt 独占的。
"""
from __future__ import annotations

import sqlite3

import pytest

import store


def _fresh_db(tmp_path, monkeypatch):
    """独立的 dictation.db。init_db() 在 app.py 里，而测试禁止裸 import app
    （docs/BACKLOG.md 第 7 条），所以这里自建 store 用得到的两张表。"""
    db = tmp_path / "t.db"
    conn = sqlite3.connect(db)
    conn.execute(
        """CREATE TABLE words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL UNIQUE,
            wrong_count INTEGER NOT NULL DEFAULT 0,
            correct_streak INTEGER NOT NULL DEFAULT 0,
            interval_days INTEGER NOT NULL DEFAULT 0,
            due_at TEXT, last_seen_at TEXT, created_at TEXT NOT NULL,
            hidden INTEGER NOT NULL DEFAULT 0)"""
    )
    conn.execute(
        """CREATE TABLE attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word_id INTEGER NOT NULL, answer TEXT NOT NULL,
            is_correct INTEGER NOT NULL, created_at TEXT NOT NULL, skill TEXT)"""
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(store, "DB_PATH", str(db))
    return db


def _seed_word(db, text="la confiture"):
    """种一个「已经练出成绩」的词：streak 4、间隔 7 天、错过 2 次。"""
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO words (text, created_at, correct_streak, interval_days, "
        "due_at, wrong_count, last_seen_at) VALUES (?,?,?,?,?,?,?)",
        (text, "2026-08-01T00:00:00", 4, 7, "2026-09-01T00:00:00", 2,
         "2026-08-01T00:00:00"),
    )
    conn.commit()
    wid = conn.execute("SELECT id FROM words WHERE text = ?", (text,)).fetchone()[0]
    conn.close()
    return wid


def test_writes_attempts_with_scan_skill(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path, monkeypatch)
    wid = _seed_word(db)
    assert store.record_scan_page([(wid, True), (wid, False)], "rec_meaning") == 2
    conn = sqlite3.connect(db)
    rows = conn.execute("SELECT skill, is_correct, answer FROM attempts ORDER BY id").fetchall()
    conn.close()
    assert rows == [
        ("rec_meaning", 1, "（扫读·会）"),
        ("rec_meaning", 0, "（扫读·不会）"),
    ]


def test_never_touches_words_srs_state(tmp_path, monkeypatch):
    """本设计的核心不变量。标「不会」之后 words 那一行必须一个字节都没变。"""
    db = _fresh_db(tmp_path, monkeypatch)
    wid = _seed_word(db)
    conn = sqlite3.connect(db)
    before = conn.execute("SELECT * FROM words WHERE id = ?", (wid,)).fetchone()
    conn.close()

    store.record_scan_page([(wid, False)], "rec_produce")

    conn = sqlite3.connect(db)
    after = conn.execute("SELECT * FROM words WHERE id = ?", (wid,)).fetchone()
    conn.close()
    assert after == before


def test_rejects_non_scan_skill(tmp_path, monkeypatch):
    """不许拿这个函数去写有证据的技能——那会绕过 words 的 SRS 更新。"""
    _fresh_db(tmp_path, monkeypatch)
    for bad in ("produce", "transcribe", "meaning", "pron", "morph", ""):
        with pytest.raises(ValueError):
            store.record_scan_page([(1, True)], bad)


def test_empty_page_is_noop(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path, monkeypatch)
    assert store.record_scan_page([], "rec_audio") == 0
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0] == 0
    conn.close()


def test_scan_attempts_are_visible_to_mastery(tmp_path, monkeypatch):
    """扫读的记录要能被 get_attempts_for_words 取到，词表的「认」列才有数据。"""
    db = _fresh_db(tmp_path, monkeypatch)
    wid = _seed_word(db)
    store.record_scan_page([(wid, True)], "rec_meaning")
    got = store.get_attempts_for_words([wid])
    assert wid in got
    assert any(a[2] == "rec_meaning" for a in got[wid])
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m pytest tests/test_scan_store.py -v`
Expected: FAIL（`AttributeError: module 'store' has no attribute 'record_scan_page'`）

- [ ] **Step 3: 在 store.py 末尾追加实现（照抄）**

```python
# ---------- 扫读（速过）的自判记录 ----------
# 扫读只回答「认不认得」，没有拼写证据。所以它写 attempts，但**绝不**更新
# words 的 SRS 状态：app.record_attempt 会改 correct_streak / interval_days /
# due_at / wrong_count，而那份状态是每个词一份、所有技能共用的——让无证据的
# 自判去改它，等于用手滑抹掉打字练出来的成绩。
# 另外 mastery.mastery_score 按天聚合时取「当天第一次」，早上扫读漏一个词就会
# 把这一整天钉成错，晚上打字打对也救不回来。所以隔离必须在写入这一层做死。

SCAN_SKILLS = ("rec_meaning", "rec_produce", "rec_audio")


def record_scan_page(results, skill: str) -> int:
    """一页扫读结果批量入库。results: [(word_id, 是否算会), ...]。返回写入条数。

    skill 必须是 SCAN_SKILLS 之一；拿有证据的技能名调用会直接抛错，
    避免有人图省事用它绕过 words 的 SRS 更新。
    """
    if skill not in SCAN_SKILLS:
        raise ValueError(f"record_scan_page 只接受 {SCAN_SKILLS}，收到 {skill!r}")
    rows = list(results)
    if not rows:
        return 0
    now = _now()
    conn = get_conn()
    conn.executemany(
        "INSERT INTO attempts (word_id, answer, is_correct, created_at, skill) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            (wid, "（扫读·会）" if ok else "（扫读·不会）", 1 if ok else 0, now, skill)
            for wid, ok in rows
        ],
    )
    conn.commit()
    conn.close()
    return len(rows)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 -m pytest tests/test_scan_store.py -v`
Expected: 5 passed

- [ ] **Step 5: 全量回归**

Run: `python3 -m pytest -q`
Expected: 全绿

- [ ] **Step 6: 提交**

```bash
git add store.py tests/test_scan_store.py
git commit -m "速过：扫读自判入库，且守住 words 的 SRS 状态不被自判污染"
```

---

### Task A3: scanaudio.py 发音缓存

**Files:**
- Create: `scanaudio.py`
- Modify: `.streamlit/config.toml`（追加 `[server]` 段）
- Modify: `.gitignore`（追加 `static/`）
- Test: `tests/test_scan_audio.py`

**Interfaces:**
- Consumes: 无
- Produces: `scanaudio.AudioUnavailable`、`scanaudio.AUDIO_DIR`、`scanaudio.cache_name(lemma, voice) -> str`、`scanaudio.cache_path(lemma, voice) -> Path`、`scanaudio.ensure(lemma, voice) -> Path`、`scanaudio.static_url(path) -> str`、`scanaudio.warm(lemmas, voice) -> dict`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_scan_audio.py
from __future__ import annotations

import ast
import pathlib
import subprocess

import pytest

import scanaudio


def _redirect(tmp_path, monkeypatch):
    monkeypatch.setattr(scanaudio, "AUDIO_DIR", tmp_path / "audio")


def test_cache_name_is_stable_and_distinct(tmp_path, monkeypatch):
    _redirect(tmp_path, monkeypatch)
    a = scanaudio.cache_name("la confiture", "Thomas")
    assert a == scanaudio.cache_name("la confiture", "Thomas")
    assert a != scanaudio.cache_name("la confiture", "Amelie")
    assert a != scanaudio.cache_name("s'installer", "Thomas")
    assert a.endswith(".m4a")
    assert "la-confiture" in a          # 前缀可读，出问题时人能在 Finder 里认出来


def test_cache_name_survives_hostile_lemmas(tmp_path, monkeypatch):
    _redirect(tmp_path, monkeypatch)
    for lemma in ("l'été", "中文", "a/b", "..", ""):
        name = scanaudio.cache_name(lemma, "Thomas")
        assert "/" not in name and not name.startswith(".")


def test_ensure_generates_then_hits_cache(tmp_path, monkeypatch):
    _redirect(tmp_path, monkeypatch)
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        out = pathlib.Path(cmd[cmd.index("-o") + 1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"fake-audio")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(scanaudio.subprocess, "run", fake_run)
    p1 = scanaudio.ensure("la confiture", "Thomas")
    assert p1.exists() and len(calls) == 1
    p2 = scanaudio.ensure("la confiture", "Thomas")
    assert p2 == p1 and len(calls) == 1          # 第二次不再调 say


def test_ensure_leaves_no_stub_on_failure(tmp_path, monkeypatch):
    """say 失败时不许留半个空文件——那会永久冒充缓存，再也生成不出来。"""
    _redirect(tmp_path, monkeypatch)

    def boom(cmd, **kw):
        out = pathlib.Path(cmd[cmd.index("-o") + 1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"")
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(scanaudio.subprocess, "run", boom)
    with pytest.raises(scanaudio.AudioUnavailable):
        scanaudio.ensure("la confiture", "Thomas")
    assert not scanaudio.cache_path("la confiture", "Thomas").exists()
    assert list((tmp_path / "audio").glob("*.part")) == []


def test_ensure_raises_when_say_is_missing(tmp_path, monkeypatch):
    _redirect(tmp_path, monkeypatch)

    def missing(cmd, **kw):
        raise FileNotFoundError("say")

    monkeypatch.setattr(scanaudio.subprocess, "run", missing)
    with pytest.raises(scanaudio.AudioUnavailable):
        scanaudio.ensure("x", "Thomas")


def test_warm_reports_progress_and_survives_failures(tmp_path, monkeypatch):
    _redirect(tmp_path, monkeypatch)
    seen = []

    def half_broken(cmd, **kw):
        lemma = cmd[3]
        seen.append(lemma)
        if lemma == "bad":
            raise subprocess.CalledProcessError(1, cmd)
        out = pathlib.Path(cmd[cmd.index("-o") + 1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"fake")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(scanaudio.subprocess, "run", half_broken)
    status = scanaudio.warm(["a", "bad", "c", "a"], "Thomas")
    status["thread"].join(timeout=10)
    assert status["total"] == 3                  # 去重
    assert status["done"] == 3
    assert status["failed"] == 1
    assert status["running"] is False


def test_static_url(tmp_path, monkeypatch):
    _redirect(tmp_path, monkeypatch)
    p = scanaudio.cache_path("la confiture", "Thomas")
    assert scanaudio.static_url(p) == f"/app/static/audio/{p.name}"


def test_module_is_pure():
    tree = ast.parse(pathlib.Path("scanaudio.py").read_text("utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    assert not (names & {"streamlit", "sqlite3", "app"})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m pytest tests/test_scan_audio.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'scanaudio'`）

- [ ] **Step 3: 实现 scanaudio.py（照抄）**

```python
# scanaudio.py
"""扫读的逐词发音缓存：macOS say → m4a，落在 static/audio/ 由 Streamlit 静态服务送出。

页面里用 <audio src="/app/static/audio/xxx.m4a">，点 ▶ 是纯浏览器行为，
不产生 rerun——这是速过能比逐词模式快两个数量级的前提之一。

无 Streamlit / sqlite3 依赖，可单测。
"""
from __future__ import annotations

import hashlib
import re
import subprocess
import threading
from pathlib import Path

AUDIO_DIR = Path(__file__).resolve().parent / "static" / "audio"
STATIC_PREFIX = "/app/static/audio"
SAY_TIMEOUT = 30

_UNSAFE = re.compile(r"[^a-zA-Z0-9]+")


class AudioUnavailable(RuntimeError):
    """这个词的发音生成不出来（say 缺失、超时、或合成失败）。"""


def cache_name(lemma: str, voice: str) -> str:
    """文件名 = 可读前缀 + 内容哈希。

    哈希保证不同 lemma/voice 不撞车（重音、撇号、中文都安全）；
    前缀保证出问题时人能在 Finder 里一眼认出是哪个词。
    """
    slug = _UNSAFE.sub("-", lemma).strip("-").lower()[:24] or "x"
    digest = hashlib.sha1(f"{lemma}\x00{voice}".encode("utf-8")).hexdigest()[:10]
    return f"{slug}-{digest}.m4a"


def cache_path(lemma: str, voice: str) -> Path:
    return AUDIO_DIR / cache_name(lemma, voice)


def static_url(path: Path) -> str:
    return f"{STATIC_PREFIX}/{Path(path).name}"


def ensure(lemma: str, voice: str) -> Path:
    """缓存命中直接返回；否则用 say 生成。失败抛 AudioUnavailable。"""
    path = cache_path(lemma, voice)
    if path.exists() and path.stat().st_size > 0:
        return path
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    try:
        subprocess.run(
            ["say", "-v", voice, lemma, "-o", str(tmp),
             "--file-format=m4af", "--data-format=aac"],
            check=True,
            capture_output=True,
            timeout=SAY_TIMEOUT,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        tmp.unlink(missing_ok=True)   # 半个空文件会永久冒充缓存，必须清掉
        raise AudioUnavailable(f"{lemma!r} 的发音生成失败：{exc}") from exc
    tmp.replace(path)                 # 原子改名：只有完整文件才配叫最终名
    return path


def warm(lemmas, voice: str) -> dict:
    """后台预热整课发音。返回一个 status dict，主线程每次 rerun 直接读：

        {"total": n, "done": 0, "failed": 0, "running": True, "thread": Thread}

    故意不回调、不碰 session_state——工作线程没有 Streamlit 的脚本上下文，
    往 session_state 写会炸。主线程轮询这个普通 dict 最省事也最稳。
    """
    items = list(dict.fromkeys(lemmas))   # 去重且保序
    status = {"total": len(items), "done": 0, "failed": 0, "running": True}

    def run() -> None:
        for lemma in items:
            try:
                ensure(lemma, voice)
            except AudioUnavailable:
                status["failed"] += 1
            status["done"] += 1
        status["running"] = False

    thread = threading.Thread(target=run, daemon=True, name="scanaudio-warm")
    status["thread"] = thread
    thread.start()
    return status
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 -m pytest tests/test_scan_audio.py -v`
Expected: 8 passed

- [ ] **Step 5: 打开静态服务**

在 `.streamlit/config.toml` 末尾追加（`[client]`、`[theme]` 两段保持原样不动）：

```toml

[server]
# 扫读的逐词发音走静态文件，点 ▶ 不经过 Streamlit（见 scanaudio.py）
enableStaticServing = true
```

在 `.gitignore` 末尾追加：

```

# 扫读的发音缓存（本地生成，按需重建）
static/
```

- [ ] **Step 6: 真机验证发音真的生成得出来**

Run:
```bash
python3 -c "import scanaudio; p = scanaudio.ensure('la confiture', 'Thomas'); print(p, p.stat().st_size)"
```
Expected: 打印 `static/audio/la-confiture-<hash>.m4a` 和一个大于 10000 的字节数。

- [ ] **Step 7: 全量回归**

Run: `python3 -m pytest -q`
Expected: 全绿

- [ ] **Step 8: 提交**

```bash
git add scanaudio.py tests/test_scan_audio.py .streamlit/config.toml .gitignore
git commit -m "速过：逐词发音缓存 + 静态服务，点播不经过 Streamlit"
```

---

### Task B1: 「认」进掌握度色表

**Files:**
- Modify: `mastery.py`（在 `SKILLS` 定义之后追加）
- Modify: `app.py`（`render_word_panel` 内三处：caption、DataFrame 列、`_style` 的 cmap）
- Test: `tests/test_scan_mastery.py`

**Interfaces:**
- Consumes: `scan.REC_SKILLS`（只用于对齐断言，`mastery.py` 自己独立定义常量，不 import scan）
- Produces: `mastery.REC_SKILLS`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_scan_mastery.py
from __future__ import annotations

import pytest

import mastery
import scan


def test_rec_skills_match_scan_directions():
    assert mastery.REC_SKILLS == scan.REC_SKILLS


def test_rec_skills_stay_out_of_base():
    """扫读没有拼写证据，不许参与总掌握度。"""
    assert not set(mastery.REC_SKILLS) & set(mastery.BASE_SKILLS)


def test_overall_ignores_rec_skills():
    sc = {"transcribe": 0.9, "produce": 0.8, "meaning": 0.9, "pron": 0.7,
          "rec_meaning": 0.0, "rec_produce": 0.0, "rec_audio": 0.0}
    assert mastery.overall(sc) == pytest.approx(0.7)      # 最弱的是 pron，不是 rec_*


def test_rec_column_takes_the_weakest_direction():
    sc = {"rec_meaning": 0.9, "rec_produce": 0.3, "rec_audio": 0.6}
    assert mastery.overall(sc, skills=mastery.REC_SKILLS) == pytest.approx(0.3)


def test_unscanned_direction_counts_as_zero():
    """只扫过一个方向时「认」是灰的——和既有「没练的算 0」口径一致，不是 bug。"""
    sc = {"rec_meaning": 0.9}
    assert mastery.overall(sc, skills=mastery.REC_SKILLS) == 0.0


def test_skill_scores_isolates_scan_from_typed_skills():
    """同一个词、同一天：扫读标错不许把打字的 meaning 拉下来。"""
    attempts = [
        (True, "2026-08-13T09:00:00", "meaning"),
        (False, "2026-08-13T08:00:00", "rec_meaning"),
    ]
    scores = mastery.skill_scores(attempts)
    assert scores["meaning"] > 0.0
    assert scores["rec_meaning"] == 0.0
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m pytest tests/test_scan_mastery.py -v`
Expected: FAIL（`AttributeError: module 'mastery' has no attribute 'REC_SKILLS'`）

- [ ] **Step 3: 在 mastery.py 里 `SKILLS = ...` 那一行之后追加**

锚点文本（不要用行号找）：

```python
SKILLS = BASE_SKILLS + ("morph",)           # 变(阴阳性变形)：仅有阴性的词适用
```

在这一行**下面**插入：

```python

# 认(扫读自判)：认得出/想得起来，但没有拼写证据。三个方向分开记，因为
# 「看法语想中文」比「看中文想法语」容易得多，混成一个会被简单的那一档拉高。
# 故意不进 BASE_SKILLS——overall() 是「适用技能里最弱那项」，让无证据的自判
# 参与总掌握度，会把打字练出来的成绩虚高或虚低。
REC_SKILLS = ("rec_meaning", "rec_produce", "rec_audio")
```

- [ ] **Step 4: 在 app.py 的 `render_word_panel` 里加「认」列（三处）**

**4a.** 找到锚点文本：

```python
        "听=听写(听法语写法语)、产=产出(看/听中文写法语)、义=理解(听法语写中文)、音=发音、变=阴阳性变形，"
```

把它整行替换为：

```python
        "听=听写(听法语写法语)、产=产出(看/听中文写法语)、义=理解(听法语写中文)、音=发音、变=阴阳性变形、"
        "认=扫读自判(速过里自己判会不会，没有拼写证据，不参与「词」列)，"
```

**4b.** 找到锚点文本：

```python
            "变": ["" for _ in rows],
            "翻译": [word_zh(r["text"]) for r in rows],
```

替换为：

```python
            "变": ["" for _ in rows],
            "认": ["" for _ in rows],
            "翻译": [word_zh(r["text"]) for r in rows],
```

**4c.** 找到锚点文本：

```python
            "变": mastery_mod.mastery_color(sc.get("morph", 0.0)) if has_fem else "#f5f5f5",
        }
```

替换为：

```python
            "变": mastery_mod.mastery_color(sc.get("morph", 0.0)) if has_fem else "#f5f5f5",
            "认": mastery_mod.mastery_color(
                mastery_mod.overall(sc, skills=mastery_mod.REC_SKILLS)
            ),
        }
```

**4d.** 找到锚点文本：

```python
    cols = ["词", "听", "产", "义", "音", "变", "翻译", "状态"] if show_trans else ["词", "听", "产", "义", "音", "变", "状态"]
```

替换为：

```python
    cols = (
        ["词", "听", "产", "义", "音", "变", "认", "翻译", "状态"] if show_trans
        else ["词", "听", "产", "义", "音", "变", "认", "状态"]
    )
```

- [ ] **Step 5: 跑测试确认通过**

Run: `python3 -m pytest tests/test_scan_mastery.py -v`
Expected: 6 passed

- [ ] **Step 6: 全量回归**

Run: `python3 -m pytest -q`
Expected: 全绿

- [ ] **Step 7: 提交**

```bash
git add mastery.py app.py tests/test_scan_mastery.py
git commit -m "速过：词表加「认」色列，与有证据的技能完全隔离"
```

---

### Task B2: overlay 骨架

**Files:**
- Modify: `app.py`（四处：session 初始化、`_leave_overlays`、侧栏按钮、视图分派 + 新函数）
- Test: `tests/test_scan_ui.py`

**Interfaces:**
- Consumes: `scan.paginate`
- Produces: session key `scan_active` / `scan_lesson` / `scan_ids` / `scan_page`；函数 `start_scan(lesson, word_ids)`、`render_scan_view()`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_scan_ui.py
from __future__ import annotations

from streamlit.testing.v1 import AppTest


def _run():
    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    return at


def _button(at, startswith):
    for b in at.button:
        if b.label.startswith(startswith):
            return b
    raise AssertionError(f"没找到以 {startswith!r} 开头的按钮：{[b.label for b in at.button]}")


def test_sidebar_has_scan_entry():
    at = _run()
    b = _button(at, "⚡ 速过")
    assert "（" in b.label and "）" in b.label      # 带词数


def test_scan_does_not_disturb_the_word_round():
    """速过是独立 overlay，绝不许碰逐词状态机。"""
    at = _run()
    before = (at.session_state.get("pool"), at.session_state.get("current_word"),
              at.session_state.get("index"))
    _button(at, "⚡ 速过").click().run()
    assert at.session_state["scan_active"] is True
    after = (at.session_state.get("pool"), at.session_state.get("current_word"),
             at.session_state.get("index"))
    assert after == before


def test_scan_closes_other_overlays():
    at = _run()
    at.session_state["cp_active"] = True
    at.session_state["writing_active"] = True
    at.run()
    _button(at, "⚡ 速过").click().run()
    assert at.session_state["cp_active"] is False
    assert at.session_state.get("writing_active") is None


def test_leaving_scan_returns_to_practice():
    at = _run()
    _button(at, "⚡ 速过").click().run()
    _button(at, "← 回到练习").click().run()
    assert at.session_state.get("scan_active") is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m pytest tests/test_scan_ui.py -v`
Expected: FAIL（找不到 `⚡ 速过` 按钮）

- [ ] **Step 3a: app.py 顶部 import 补 scan**

找到锚点文本：

```python
import roundlogic
```

在它下面加一行：

```python
import scan
```

（若 import 区没有 `import roundlogic` 这一行，就加在 `import mastery as mastery_mod` 之类的同类 import 旁边，保持字母序不是硬要求，与邻近风格一致即可。）

- [ ] **Step 3b: 加 session 初始化**

找到锚点文本：

```python
if "cp_active" not in st.session_state:   # 「📝 知识点」是独立流程，绝不碰 pool/current_word
    st.session_state.cp_active = False
    st.session_state.cp_cards = []
    st.session_state.cp_index = 0
    st.session_state.cp_show_back = False
```

在这一块**下面**插入：

```python

if "scan_active" not in st.session_state:  # 「⚡ 速过」同样是独立流程，和逐词状态机零共享
    st.session_state.scan_active = False
    st.session_state.scan_lesson = ""
    st.session_state.scan_ids = []
    st.session_state.scan_page = 0
```

- [ ] **Step 3c: 让 `_leave_overlays` 认识速过**

找到锚点文本：

```python
    st.session_state.cp_active = False
    st.session_state.pop("writing_active", None)   # 写作视图同属覆盖层
```

替换为：

```python
    st.session_state.cp_active = False
    st.session_state.pop("writing_active", None)   # 写作视图同属覆盖层
    st.session_state.pop("scan_active", None)      # 速过同属覆盖层
```

- [ ] **Step 3d: 在 `_leave_overlays` 之后加 `start_scan`**

找到 `_leave_overlays` 函数结尾的锚点文本（就是 3c 改完的那两行），在整个函数之后、`def _writing_content():` 之前插入：

```python
def start_scan(lesson: str, word_ids: list[int]) -> None:
    """进入速过。只写 scan_* 这几个 key，逐词状态机一个都不碰。"""
    st.session_state.scan_active = True
    st.session_state.scan_lesson = lesson
    st.session_state.scan_ids = list(word_ids)
    st.session_state.scan_page = 0


```

- [ ] **Step 3e: 侧栏加入口**

找到锚点文本：

```python
    st.caption("错词=做错过的；到期=顶部按遗忘曲线提醒；变形=有阴阳性的词；"
```

在这一行**上面**插入：

```python
    _scan_pool = _lesson_ids(chosen_lesson, LESSONS)
    if st.button(f"⚡ 速过（{len(_scan_pool)}）", disabled=not _scan_pool,
                 use_container_width=True):
        _leave_overlays()
        save_setting("last_lesson", chosen_lesson)
        start_scan(chosen_lesson, _scan_pool)
        st.rerun()

```

- [ ] **Step 3f: 加 `render_scan_view` 空壳**

在 `def render_search_panel():` 这一行**上面**插入：

```python
def render_scan_view() -> None:
    """速过：整页扫读。B3 补表格、B4 补提交、B5 补接慢流程。"""
    ids = st.session_state.scan_ids
    pages = scan.paginate(ids, int(load_setting("scan_page_size", 20)))
    page_no = min(st.session_state.scan_page, max(0, len(pages) - 1))
    st.session_state.scan_page = page_no

    st.subheader(f"⚡ 速过 · {st.session_state.scan_lesson}")
    st.caption(f"共 {len(ids)} 词 · 第 {page_no + 1}/{max(1, len(pages))} 页")

    if st.button("← 回到练习"):
        _leave_overlays()
        st.rerun()


```

- [ ] **Step 3g: 挂上视图分派**

找到主区里判断 `cp_active` 的那一处分派（`render_checkpoint()` 的调用点），在同一条 if/elif 链里，**在 `cp_active` 分支之前**加一支：

```python
if st.session_state.get("scan_active"):
    render_scan_view()
elif ...
```

具体写法照抄该处既有链条的缩进与结构；只加这一支，不动其余分支。

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 -m pytest tests/test_scan_ui.py -v`
Expected: 4 passed

- [ ] **Step 5: 全量回归**

Run: `python3 -m pytest -q`
Expected: 全绿

- [ ] **Step 6: 提交**

```bash
git add app.py tests/test_scan_ui.py
git commit -m "速过：overlay 骨架与侧栏入口，逐词状态机零共享"
```

---

### Task B3: 扫读表渲染（三种揭法 + 逐词 ▶）

**Files:**
- Modify: `app.py`（`render_scan_view` 内补渲染 + 两个新私有函数）
- Test: `tests/test_scan_table.py`

**Interfaces:**
- Consumes: `scan.DIRECTIONS`、`scan.page_rows`、`scanaudio.*`
- Produces: `_scan_table_html(rows, direction, audio_urls) -> str`、`_scan_behavior_script(reveal) -> str`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_scan_table.py
"""表格 HTML 的结构断言。渲染是字符串拼接，可以脱离浏览器测。"""
from __future__ import annotations

import importlib.util
import pathlib


def _load_app_fns():
    """只取 app.py 里的两个纯函数，不执行整个脚本（docs/BACKLOG.md 第 7 条）。

    做法：把源码解析成 AST，挑出这两个函数定义单独 exec。
    """
    import ast

    src = pathlib.Path("app.py").read_text("utf-8")
    tree = ast.parse(src)
    wanted = {"_scan_table_html", "_scan_behavior_script"}
    picked = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
    assert {n.name for n in picked} == wanted, "app.py 里没找到这两个函数"
    ns = {}
    import html as html_mod
    ns["html"] = html_mod
    import scan as scan_mod
    ns["scan"] = scan_mod
    exec(compile(ast.Module(body=picked, type_ignores=[]), "app.py", "exec"), ns)
    return ns


ROWS = [
    {"no": 1, "word_id": 11, "fr": "la confiture", "zh": "果酱"},
    {"no": 2, "word_id": 12, "fr": "s'installer", "zh": "定居"},
]
URLS = {11: "/app/static/audio/a.m4a"}      # 12 号故意没有音频


def test_meaning_direction_covers_only_chinese():
    fn = _load_app_fns()["_scan_table_html"]
    out = fn(ROWS, "看法→想中", URLS, "0-0")
    assert "la confiture" in out and "果酱" in out
    assert "scan-cover" in out
    # 中文被盖、法语没被盖
    assert out.index("la confiture") < out.index("果酱")
    assert 'data-locked="1"' not in out


def test_produce_direction_locks_the_play_button():
    fn = _load_app_fns()["_scan_table_html"]
    out = fn(ROWS, "看中→想法", URLS, "0-0")
    assert 'data-locked="1"' in out


def test_missing_audio_renders_a_dead_play_button():
    fn = _load_app_fns()["_scan_table_html"]
    out = fn(ROWS, "看法→想中", URLS, "0-0")
    assert out.count("scan-play") == 1          # 只有 11 号有音频


def test_html_is_escaped():
    fn = _load_app_fns()["_scan_table_html"]
    rows = [{"no": 1, "word_id": 1, "fr": "<script>x</script>", "zh": "&"}]
    out = fn(rows, "看法→想中", {}, "0-0")
    assert "<script>x</script>" not in out
    assert "&lt;script&gt;" in out


def test_every_row_carries_its_lesson_wide_number():
    fn = _load_app_fns()["_scan_table_html"]
    rows = [{"no": 21, "word_id": 1, "fr": "a", "zh": "甲"}]
    out = fn(rows, "看法→想中", {}, "0-0")
    assert 'data-no="21"' in out


def test_rev_token_reaches_the_table():
    """同步脚本靠它认出「这是新的一页，把上一页的勾清掉」。"""
    fn = _load_app_fns()["_scan_table_html"]
    rows = [{"no": 1, "word_id": 1, "fr": "a", "zh": "甲"}]
    assert 'data-rev="0-0"' in fn(rows, "看法→想中", {}, "0-0")
    assert 'data-rev="3-7"' in fn(rows, "看法→想中", {}, "3-7")


def test_behavior_script_covers_three_modes():
    fn = _load_app_fns()["_scan_behavior_script"]
    for mode in ("click", "hover", "page"):
        out = fn(mode)
        assert f'"{mode}"' in out
        assert "window.parent.document" in out
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m pytest tests/test_scan_table.py -v`
Expected: FAIL（`AssertionError: app.py 里没找到这两个函数`）

- [ ] **Step 3: 在 app.py 的 `render_scan_view` 之前插入两个函数（照抄）**

```python
_SCAN_COVER_STYLE = (
    "cursor:pointer;filter:blur(5px);background:#f2f2f2;"
    "border-radius:4px;padding:0 4px;transition:filter .12s"
)


def _scan_table_html(rows, direction: str, audio_urls: dict, rev: str) -> str:
    """一页扫读表。被盖的格子打 class='scan-cover'，行为由注入脚本挂（见下）。

    渲染和行为分开：这里只吐静态 HTML，所以能脱离浏览器单测。

    rev 是「这是第几次渲染的哪一页」的令牌。停在最后一页连着提交两次时，
    表格 HTML 一模一样，React 会复用同一批 DOM 节点，勾选状态就会留在上一次
    —— 而 form 那边的隐藏输入已经清空了，两边对不上。同步脚本靠 rev 变化
    识别出「这是新的一页」并清干净。
    """
    _skill, _open, covered, play_locked = scan.DIRECTIONS[direction]
    head = (
        "<tr>"
        "<td style='width:36px;color:#999;font-size:.78em;padding:2px 0'>#</td>"
        "<td style='width:32px'></td>"
        "<td style='color:#999;font-size:.78em;padding:2px 0'>法语</td>"
        "<td style='color:#999;font-size:.78em;padding:2px 0'>中文</td>"
        "<td style='width:48px;color:#999;font-size:.78em;text-align:right'>不会</td>"
        "</tr>"
    )
    body = ""
    for r in rows:
        url = audio_urls.get(r["word_id"], "")
        if url:
            lock = ' data-locked="1"' if play_locked else ""
            play = (
                f"<span class='scan-play' data-no='{r['no']}'"
                f" data-src='{html.escape(url, quote=True)}'{lock}"
                f" style='cursor:pointer;color:#1a7f37'>▶</span>"
            )
        else:
            play = "<span style='color:#ccc' title='这个词的发音还没生成好'>▶</span>"

        cells = {}
        for field in ("fr", "zh"):
            safe = html.escape(r[field])
            if field in covered:
                cells[field] = (
                    f"<span class='scan-cover' data-no='{r['no']}'"
                    f" style='{_SCAN_COVER_STYLE}'>{safe}</span>"
                )
            else:
                cells[field] = safe

        body += (
            f"<tr data-no='{r['no']}'>"
            f"<td style='color:#999;font-size:.82em;padding:6px 0'>{r['no']}</td>"
            f"<td style='padding:6px 0'>{play}</td>"
            f"<td style='padding:6px 0'>{cells['fr']}</td>"
            f"<td style='padding:6px 0'>{cells['zh']}</td>"
            f"<td style='padding:6px 0;text-align:right'>"
            f"<input type='checkbox' class='scan-miss' data-no='{r['no']}'></td>"
            "</tr>"
        )
    return (
        f"<table class='scan-table' data-rev='{html.escape(rev, quote=True)}' "
        "style='border-collapse:collapse;width:100%;font-size:15px'>"
        f"{head}{body}</table>"
    )


def _scan_behavior_script(reveal: str) -> str:
    """盖/揭与逐词播放的行为脚本。

    走 components.html 注入、操作 window.parent.document —— 和
    focus_answer_input / wire_form_enter_submit 同一套手法。全部在浏览器端
    完成，一次 rerun 都不产生。
    """
    return """
    <script>
    (function () {
      const doc = window.parent.document;
      const mode = "%s";
      function uncover(el) {
        el.style.filter = "none";
        el.style.background = "transparent";
        const tr = el.closest("tr");
        if (tr) tr.dataset.revealed = "1";
      }
      function cover(el) {
        el.style.filter = "blur(5px)";
        el.style.background = "#f2f2f2";
      }
      function bind() {
        // 不要加「已挂过就跳过」的守卫。提交会触发 rerun，rerun 之后必须重新挂；
        // S0 实测确认了这一点。下面全部用 el.onclick = ... 赋值挂载，重复挂只是
        // 覆盖同一个函数，不会叠加，所以本来也不需要守卫。
        const table = doc.querySelector(".scan-table");
        if (!table) return false;
        table.querySelectorAll(".scan-cover").forEach(function (el) {
          if (mode === "hover") {
            el.onmouseenter = function () { uncover(el); };
            el.onmouseleave = function () { cover(el); };
          } else if (mode === "click") {
            el.onclick = function () { uncover(el); };
          }
        });
        table.querySelectorAll(".scan-play").forEach(function (el) {
          el.onclick = function () {
            const tr = el.closest("tr");
            if (el.dataset.locked === "1" && !(tr && tr.dataset.revealed)) return;
            new (window.parent.Audio)(el.dataset.src).play();
          };
        });
        const all = doc.querySelector(".scan-reveal-all");
        if (all) all.onclick = function () {
          table.querySelectorAll(".scan-cover").forEach(uncover);
        };
        return true;
      }
      if (!bind()) { setTimeout(bind, 50); setTimeout(bind, 200); }
    })();
    </script>
    """ % reveal
```

- [ ] **Step 4: 在 `render_scan_view` 里接上（替换 B2 建的空壳主体）**

把 B2 写的 `render_scan_view` 函数体整个替换为：

```python
    ids = st.session_state.scan_ids
    page_size = int(load_setting("scan_page_size", 20))
    pages = scan.paginate(ids, page_size)
    page_no = min(st.session_state.scan_page, max(0, len(pages) - 1))
    st.session_state.scan_page = page_no

    st.subheader(f"⚡ 速过 · {st.session_state.scan_lesson}")
    st.caption(f"共 {len(ids)} 词 · 第 {page_no + 1}/{max(1, len(pages))} 页")

    c_dir, c_rev = st.columns(2)
    direction = c_dir.selectbox(
        "方向", list(scan.DIRECTIONS),
        index=list(scan.DIRECTIONS).index(load_setting("scan_direction", "看法→想中")),
        key="scan_direction_sel",
    )
    reveal_labels = {"click": "点行显形", "hover": "悬停显形", "page": "整页一次揭晓"}
    reveal = c_rev.selectbox(
        "揭法", list(reveal_labels),
        index=list(reveal_labels).index(load_setting("scan_reveal", "click")),
        format_func=lambda k: reveal_labels[k],
        key="scan_reveal_sel",
    )
    save_setting("scan_direction", direction)
    save_setting("scan_reveal", reveal)

    if not pages:
        st.info("这一课还没有词。")
        if st.button("← 回到练习"):
            _leave_overlays()
            st.rerun()
        return

    page_ids = pages[page_no]
    rows = scan.page_rows(
        page_ids,
        {r["id"]: r["text"] for r in get_words_by_ids(page_ids)},
        {lemma: word_zh(lemma) for lemma in VOCAB},
        start_no=page_no * max(1, page_size) + 1,
    )

    voice = st.session_state.get("scan_voice", "Thomas")
    warm_status = st.session_state.get("scan_warm")
    if warm_status is None:
        warm_status = scanaudio.warm([r["text"] for r in get_words_by_ids(ids)], voice)
        st.session_state.scan_warm = warm_status
    if warm_status.get("running"):
        st.caption(f"发音准备中 {warm_status['done']}/{warm_status['total']}"
                   f"（不影响看法/看中两档）")

    audio_urls = {}
    for r in rows:
        p = scanaudio.cache_path(r["fr"], voice)
        if p.exists() and p.stat().st_size > 0:
            audio_urls[r["word_id"]] = scanaudio.static_url(p)

    rev = f"{page_no}-{st.session_state.get('scan_rev', 0)}"
    st.markdown(_scan_table_html(rows, direction, audio_urls, rev), unsafe_allow_html=True)
    if reveal == "page":
        st.markdown(
            "<button class='scan-reveal-all' type='button'>揭晓这一页</button>",
            unsafe_allow_html=True,
        )
    components.html(_scan_behavior_script(reveal), height=0, width=0)

    if st.button("← 回到练习"):
        _leave_overlays()
        st.rerun()
```

同时在 app.py 顶部 import 区加一行（放在 `import scan` 旁边）：

```python
import scanaudio
```

- [ ] **Step 5: 跑测试确认通过**

Run: `python3 -m pytest tests/test_scan_table.py -v`
Expected: 7 passed

- [ ] **Step 6: 全量回归**

Run: `python3 -m pytest -q`
Expected: 全绿

- [ ] **Step 7: 提交**

```bash
git add app.py tests/test_scan_table.py
git commit -m "速过：扫读表渲染，三种揭法与逐词播放全在浏览器端完成"
```

---

### Task B4: 提交回路

**S0 已判定为 `A`（2026-08-13 真机验过）。做 Step 3（A 路），Step 3（B 路）整段跳过。**
B 路保留在文档里只作为退路记录：只有当 Streamlit 升级后 A 路回归失败、且 S0 重跑
确认打不通时才启用，那时再由用户决定。

**Files:**
- Modify: `app.py`（`render_scan_view` 内补 form 与入库）
- Test: `tests/test_scan_commit.py`

**Interfaces:**
- Consumes: `scan.commit`、`scan.parse_missed`、`store.record_scan_page`
- Produces: session key `scan_missed_last`（上一页标了几个，B5 要用）

- [ ] **Step 1: 写失败测试（两路通用）**

```python
# tests/test_scan_commit.py
from __future__ import annotations

import scan


def test_page_commit_maps_marks_to_rows():
    """提交语义：没勾的算会，勾了的算不会。这条不随 A/B 路变。"""
    rows = scan.page_rows(
        [11, 12, 13],
        {11: "a", 12: "b", 13: "c"},
        {"a": "甲", "b": "乙", "c": "丙"},
        start_no=21,
    )
    missed = scan.parse_missed("22")
    assert scan.commit(rows, missed) == [(11, True), (12, False), (13, True)]


def test_dirty_payload_does_not_lose_the_page():
    rows = scan.page_rows([11], {11: "a"}, {"a": "甲"}, start_no=1)
    assert scan.commit(rows, scan.parse_missed("x,,-3")) == [(11, True)]
```

- [ ] **Step 2: 跑测试确认通过（纯逻辑已在 A1 到位，这一步应直接绿）**

Run: `python3 -m pytest tests/test_scan_commit.py -v`
Expected: 2 passed

- [ ] **Step 3（A 路）: 行内勾选 + JS 回传**

在 `render_scan_view` 里，把 `st.markdown(_scan_table_html(...))` 那一段连同 `components.html(...)` 一起，包进一个 form：

```python
    rev = f"{page_no}-{st.session_state.get('scan_rev', 0)}"
    # 不要用 clear_on_submit：它只清得掉 Streamlit 自己的隐藏输入，清不掉表格里
    # 那些裸 HTML 的 checkbox，两边会对不上。清理统一交给同步脚本按 rev 做。
    with st.form(f"scan_form_{page_no}"):
        st.markdown(_scan_table_html(rows, direction, audio_urls, rev), unsafe_allow_html=True)
        if reveal == "page":
            st.markdown(
                "<button class='scan-reveal-all' type='button'>揭晓这一页</button>",
                unsafe_allow_html=True,
            )
        missed_raw = st.text_input(
            "missed", key="scan_missed", label_visibility="collapsed"
        )
        submitted = st.form_submit_button("记下这一页 ▶", type="primary")
    components.html(_scan_behavior_script(reveal), height=0, width=0)
    components.html(_scan_sync_script(), height=0, width=0)
```

并在 `_scan_behavior_script` 之后加同步脚本：

```python
def _scan_sync_script() -> str:
    """把行内勾选同步进 form 里那个隐藏 text_input。

    写 React 受控组件的值必须走 native setter 再派发 input 事件，直接赋
    .value 不会被 React 看见。这条通路由 S0 卡在真实浏览器里验证过。
    """
    return """
    <script>
    (function () {
      const doc = window.parent.document;
      function setInput(el, value) {
        const proto = window.parent.HTMLInputElement.prototype;
        Object.getOwnPropertyDescriptor(proto, "value").set.call(el, value);
        el.dispatchEvent(new (window.parent.Event)("input", {bubbles: true}));
      }
      function bind() {
        const table = doc.querySelector(".scan-table");
        const boxes = doc.querySelectorAll(".scan-miss");
        const sink = doc.querySelector(".st-key-scan_missed input");
        if (!table || !boxes.length || !sink) return false;
        // 新的一页（含「停在最后一页又提交一次」）：把上一页留下的勾清干净。
        // 裸 HTML 的 checkbox 不归 React 管，clear_on_submit 碰不到它们。
        const rev = table.dataset.rev || "";
        if (sink.dataset.scanRev !== rev) {
          sink.dataset.scanRev = rev;
          boxes.forEach(function (b) { b.checked = false; });
          setInput(sink, "");
        }
        boxes.forEach(function (b) {
          b.onchange = function () {
            const on = [...doc.querySelectorAll(".scan-miss")]
              .filter(x => x.checked).map(x => x.dataset.no);
            setInput(sink, on.join(","));
          };
        });
        return true;
      }
      if (!bind()) { setTimeout(bind, 50); setTimeout(bind, 200); }
    })();
    </script>
    """
```

- [ ] **Step 3（B 路）: 表格下方序号条**

不写 `_scan_sync_script`，也不在表格里放 checkbox——把 `_scan_table_html` 里这一段：

```python
            f"<td style='padding:6px 0;text-align:right'>"
            f"<input type='checkbox' class='scan-miss' data-no='{r['no']}'></td>"
```

替换为：

```python
            "<td></td>"
```

`render_scan_view` 里的 form 改成：

```python
    rev = f"{page_no}-{st.session_state.get('scan_rev', 0)}"
    with st.form(f"scan_form_{page_no}", clear_on_submit=True):
        st.markdown(_scan_table_html(rows, direction, audio_urls, rev), unsafe_allow_html=True)
        if reveal == "page":
            st.markdown(
                "<button class='scan-reveal-all' type='button'>揭晓这一页</button>",
                unsafe_allow_html=True,
            )
        st.caption("下面点掉你想不起来的序号，其余默认算会。")
        picked = st.pills(
            "不会的", [r["no"] for r in rows], selection_mode="multi",
            key="scan_missed_pills", label_visibility="collapsed",
        )
        submitted = st.form_submit_button("记下这一页 ▶", type="primary")
    components.html(_scan_behavior_script(reveal), height=0, width=0)
    missed_raw = ",".join(str(n) for n in (picked or []))
```

- [ ] **Step 4（两路通用）: 提交后入库并翻页**

在 form 之后、`if st.button("← 回到练习")` 之前插入：

```python
    if submitted:
        skill = scan.DIRECTIONS[direction][0]
        missed = scan.parse_missed(missed_raw)
        results = scan.commit(rows, missed)
        store.record_scan_page(results, skill)
        st.session_state.scan_missed_last = [
            wid for wid, ok in results if not ok
        ]
        st.session_state.scan_rev = st.session_state.get("scan_rev", 0) + 1
        if page_no + 1 < len(pages):
            st.session_state.scan_page = page_no + 1
        st.rerun()
```

并确认 app.py 顶部的 `from store import (...)` 里含 `record_scan_page`；没有就加进去，与既有 import 风格一致。

- [ ] **Step 5: 全量回归**

Run: `python3 -m pytest -q`
Expected: 全绿

- [ ] **Step 6: 真机验一页**

Run: `./run.sh`，浏览器进「⚡ 速过」，扫一页、标 2 个不会、点「记下这一页」。
Expected: 翻到下一页，**新页面上一个勾都没有**；回到词表能看到那 2 个词的「认」列没变绿。

再翻到最后一页，连着提交两次（第二次一个都不标）。
Expected: 第二次提交后表格里的勾全部清掉了——这是 `data-rev` 那段守的场景。

- [ ] **Step 7: 提交**

```bash
git add app.py tests/test_scan_commit.py
git commit -m "速过：一页一次提交，扫读结果按方向写进「认」"
```

---

### Task B5: 接慢流程

**Files:**
- Modify: `app.py`（`render_scan_view` 末尾追加）
- Test: `tests/test_scan_handoff.py`

**Interfaces:**
- Consumes: `st.session_state.scan_missed_last`、`reset_round`
- Produces: 无

- [ ] **Step 1: 写失败测试**

```python
# tests/test_scan_handoff.py
from __future__ import annotations

from streamlit.testing.v1 import AppTest


def _run():
    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    return at


def _button(at, startswith):
    for b in at.button:
        if b.label.startswith(startswith):
            return b
    raise AssertionError(f"没找到 {startswith!r}：{[b.label for b in at.button]}")


def test_no_handoff_button_before_any_page_is_submitted():
    at = _run()
    _button(at, "⚡ 速过").click().run()
    assert not [b for b in at.button if b.label.startswith("把这")]


def test_handoff_starts_a_round_with_exactly_the_missed_words():
    at = _run()
    _button(at, "⚡ 速过").click().run()
    ids = at.session_state["scan_ids"][:2]
    at.session_state["scan_missed_last"] = ids
    at.run()
    _button(at, "把这").click().run()
    assert at.session_state["pool"] == ids
    assert at.session_state.get("scan_active") is None    # 已离开 overlay


def test_handoff_button_hidden_when_nothing_was_missed():
    at = _run()
    _button(at, "⚡ 速过").click().run()
    at.session_state["scan_missed_last"] = []
    at.run()
    assert not [b for b in at.button if b.label.startswith("把这")]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m pytest tests/test_scan_handoff.py -v`
Expected: FAIL（`test_handoff_starts_a_round...` 找不到「把这」按钮）

- [ ] **Step 3: 在 `render_scan_view` 里 `if st.button("← 回到练习")` 之前插入**

```python
    missed_ids = st.session_state.get("scan_missed_last") or []
    if missed_ids:
        st.divider()
        if st.button(f"把这 {len(missed_ids)} 个漏掉的用「{mode_name}」练一遍",
                     type="primary"):
            _leave_overlays()
            reset_round(missed_ids, st.session_state.get("batch_size_round", 10))
            st.session_state.round_lesson = st.session_state.scan_lesson
            st.session_state.round_label = f"速过漏词 · {st.session_state.scan_lesson}"
            st.session_state.pop("scan_missed_last", None)
            st.rerun()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 -m pytest tests/test_scan_handoff.py -v`
Expected: 3 passed

- [ ] **Step 5: 全量回归**

Run: `python3 -m pytest -q`
Expected: 全绿

- [ ] **Step 6: 提交**

```bash
git add app.py tests/test_scan_handoff.py
git commit -m "速过：漏掉的词一键转进现有的逐词精练"
```

---

### Task F: 真实使用验收（人工，用户本人）

不派任何模型。用户拿一节真课（L36，164 词）自己走一遍：

- [ ] 三个方向各扫一遍整课，记录实际耗时，对比"以前打字过一遍要多久"
- [ ] 三种揭法各用一页，定出自己顺手的那个
- [ ] 确认「认」色列的语义读起来不别扭（只扫过一个方向时它是灰的，见设计文档 §11）
- [ ] 定出顺手的页大小，把那个值写回 `render_scan_view` 里 `load_setting("scan_page_size", 20)` 的默认值
- [ ] 确认词表里那些词的 听/产/义/音 四列**没有**因为扫读而变动

## Self-Review

**1. 设计文档覆盖检查**

| 设计文档章节 | 落在哪张卡 |
|---|---|
| §3.1 入口与 overlay 互斥 | B2 |
| §3.2 三个方向、▶ 的锁定规则 | A1（数据）+ B3（渲染） |
| §3.2 三种揭法 | B3 |
| §3.3 页大小设置 | B3（`scan_page_size`）+ F（定默认值） |
| §3.4 逐词播放 | A3 + B3 |
| §4.1–4.3 零 schema 变更、不碰 words | A2 |
| §4.4 「认」色列 | B1 |
| §5 模块划分 | A1 / A3 / B2 |
| §6 零 rerun 三层 | B3（前两层）+ B4（第三层） |
| §6.1 回传风险与退路 | S0（判定）+ B4（两路） |
| §7 接慢流程 | B5 |
| §8 错误处理与降级 | A3（say 失败/预热未完）+ B3（▶ 置灰）+ B5（无漏词不出按钮）+ A1（无释义） |
| §9 测试 | 各卡自带 |

**未落卡的设计条目：**

- §3.4「串播这一页」（`[[slnc]]` 一次合成整页）——设计文档写明它是"可选的附加形态，不是主路径"，本次不做。要做时单开一张卡，不影响以上任何一张。
- §8 表格里「某词没有中文释义」由 `scan.page_rows` 的 `（无释义）` 覆盖（A1 有测试）；「本课词数为 0」由 B2 的 `disabled=not _scan_pool` 覆盖。

**1b. S0 跑完之后对本计划的两处修订**（2026-08-13，都是实测暴露的，不是重新设计）

- `_scan_behavior_script` 原稿有个 `table.dataset.bound === "1"` 的「已挂过就跳过」
  守卫。实测确认提交触发 rerun 后**必须重新挂**，这个守卫会让第二页起全部失灵。
  已删除；handler 都是 `el.onclick = ...` 赋值挂载，本来就幂等，不需要守卫。
- `_scan_table_html` 加了 `rev` 参数并把它写成 `data-rev`。停在最后一页连着提交
  两次时表格 HTML 完全一样，React 会复用 DOM 节点，裸 HTML 的 checkbox 会留着上次
  的勾，而 form 的隐藏输入已经清空——两边对不上。同步脚本改成按 `rev` 变化清理，
  `clear_on_submit` 一并去掉（它本来就管不到非 React 的 checkbox）。

**2. 与设计文档的一处修订**

设计文档 §8 写「提交时 word_id 不在库 → 静默跳过（对齐 `record_attempt` 里 `if not row: return`）」。实际读代码后确认：`record_attempt` 是**先插 attempts 再查 words**，所以不存在的 word_id 照样会留下一条 attempts。本计划的 `record_scan_page` 采用同样行为（无条件插入），与既有代码一致。设计文档那一行应据此更正。

**3. 类型一致性**

- `scan.DIRECTIONS` 的值在 A1 定为 4 元组，B3 用 `_skill, _open, covered, play_locked` 解包 —— 一致。
- `scan.commit` 返回 `[(word_id, ok)]`，`store.record_scan_page` 的入参正是这个形状 —— 一致。
- `scanaudio.warm` 返回的 dict 键 `total/done/failed/running/thread`，B3 只读 `running/done/total` —— 一致。
- `mastery.REC_SKILLS` 与 `scan.REC_SKILLS` 值相同但各自独立定义（B1 有断言守着不许漂移），避免 `mastery.py` 依赖 `scan.py`。
