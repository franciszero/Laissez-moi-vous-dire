# 速过键盘化施工卡

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按 `docs/specs/2026-08-20-vocab-scan-keyboard-design.md`，把速过从鼠标点选改成键盘驱动，每次表态立刻写库。

**Architecture:** 纯逻辑继续留在 `scan.py` / `store.py`（无 Streamlit 依赖，可单测）；`app.py` 里删掉三种揭法、勾选框、表单提交那一整套，换成一段注入的键盘脚本 + 一个 `st.fragment` 回传回路。数据模型一行不动。

**Tech Stack:** Python 3 / sqlite3（只在 store.py）/ macOS `say` / Streamlit 1.58 的 `st.fragment` + `components.html` 注入 / `streamlit.testing.v1.AppTest` / pytest。

## Global Constraints

- `scan.py` 禁止 import `streamlit`、`sqlite3`、`app`（既有纯度测试强制）。
- **扫读绝不 UPDATE `words` 表**。新增的删除能力同样不许碰 `words`。
- `delete_last_scan_attempt` 的删除范围三条同时满足才删（skill 在 `SCAN_SKILLS` 里、匹配 word_id+skill、`answer` 以 `（扫读·` 开头）。**任何放宽都是事故**——放宽一格就能删到用户打字练出来的历史。
- 不新增数据库表、不改任何既有列。
- 不改 `matcher.check_fr` 的判分口径（`docs/BACKLOG.md` 第 3 条）。
- 测试禁止裸 `import app`（`docs/BACKLOG.md` 第 7 条）。
- 新写的 UI 测试若会让 `pool` 非空，必须带 `_keep_the_saved_round()` 那类还原（`docs/BACKLOG.md` 第 9 条）。
- 不加任何新依赖。
- 每张卡结束：先跑本卡目标测试，再跑全量 `python3 -m pytest -q`，全绿才 commit。

## 卡片总览与派工

**粒度按执行者区分**：Sonnet 的卡必须小、给完整代码、零设计自由度；总管自己做的卡不重复抄代码给自己看，写清契约和验收清单即可，而且允许更大张——互相咬合的东西拆开就没法独立验证。

| 卡 | 内容 | 执行者 | 依赖 |
|---|---|---|---|
| K1 | `scan.parse_ops` 解析回传串 | **Sonnet 5** | 无 |
| K2 | `store.delete_last_scan_attempt` 撤销一条扫读 | **Sonnet 5** | 无 |
| K3 | 删掉鼠标那一套，表格简化成当前行模型 | **总管（Opus）** | 无 |
| K4 | 键盘脚本 + fragment 回传 + 翻页时序 | **总管（Opus）** | K1, K2, K3 |
| K5 | 真机验收，结论写回文档 | **总管（Opus）** | K4 |
| F | 真实练一课 | **用户本人** | K5 |

执行顺序固定：**K1 → K2 → K3 → K4 → K5 → F**。不并行——K3 之后每张卡都碰 `app.py`。

---

### Task K1: `scan.parse_ops` 解析回传串（Sonnet）

**Files:**
- Modify: `scan.py`（文件末尾追加）
- Test: `tests/test_scan.py`（追加，不动既有用例）

**Interfaces:**
- Consumes: 无
- Produces: `scan.parse_ops(raw) -> list[tuple]`，每项是 `("mark", word_id:int, ok:bool)` 或 `("undo", word_id:int, None)`。K4 按原样调用，元组形状不得改。

- [ ] **Step 1: 写失败测试**

在 `tests/test_scan.py` 末尾追加：

```python
def test_parse_ops_reads_marks_and_undos_in_order():
    assert scan.parse_ops("1201:1,1202:0,U:1202,1202:1") == [
        ("mark", 1201, True),
        ("mark", 1202, False),
        ("undo", 1202, None),
        ("mark", 1202, True),
    ]


def test_parse_ops_keeps_duplicates():
    """同一个词表两次是合法的（改判后重表），不许去重——服务端靠顺序增量写。"""
    assert scan.parse_ops("7:1,7:1") == [("mark", 7, True), ("mark", 7, True)]


def test_parse_ops_drops_garbage_silently():
    """这串从浏览器来，宁可少记一条，也不能让整页的提交炸掉。"""
    assert scan.parse_ops("") == []
    assert scan.parse_ops(None) == []
    assert scan.parse_ops(",,") == []
    assert scan.parse_ops("nocolon") == []
    assert scan.parse_ops("abc:1") == []          # word_id 不是数字
    assert scan.parse_ops("12:2") == []           # 判定不是 0/1
    assert scan.parse_ops("12:") == []            # 判定缺失
    assert scan.parse_ops("U:abc") == []          # 撤销目标不是数字
    assert scan.parse_ops("U") == []              # 撤销没带目标
    assert scan.parse_ops("-3:1") == []           # 负号不是 isdigit


def test_parse_ops_survives_a_dirty_item_in_the_middle():
    assert scan.parse_ops("1:1,junk,2:0") == [("mark", 1, True), ("mark", 2, False)]


def test_parse_ops_tolerates_spaces():
    assert scan.parse_ops(" 1:1 , U:1 ") == [("mark", 1, True), ("undo", 1, None)]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m pytest tests/test_scan.py -q`
Expected: FAIL，`AttributeError: module 'scan' has no attribute 'parse_ops'`

- [ ] **Step 3: 在 `scan.py` 末尾追加实现（照抄）**

```python
def parse_ops(raw) -> list[tuple]:
    """把键盘回传串解析成有序的操作列表。

    格式：逗号分隔，每项二选一——
      "<word_id>:1"  → ("mark", word_id, True)     会
      "<word_id>:0"  → ("mark", word_id, False)    不会
      "U:<word_id>"  → ("undo", word_id, None)     撤销该词最近一条扫读记录

    **顺序必须保留、重复不许去掉**：服务端记「已处理到第几条」做增量写入，
    动了顺序或条数就会重写或漏写。

    脏值静默丢弃——这串是从浏览器来的，宁可少记一条，也不能让一次提交整个炸掉。
    """
    out: list[tuple] = []
    for chunk in (raw or "").replace(" ", "").split(","):
        if not chunk:
            continue
        head, sep, tail = chunk.partition(":")
        if not sep:
            continue
        if head == "U":
            if tail.isdigit():
                out.append(("undo", int(tail), None))
        elif head.isdigit() and tail in ("0", "1"):
            out.append(("mark", int(head), tail == "1"))
    return out
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 -m pytest tests/test_scan.py -q`
Expected: 15 passed（既有 10 条 + 新增 5 条）

- [ ] **Step 5: 全量回归**

Run: `python3 -m pytest -q`
Expected: 全绿，无新增 failure

- [ ] **Step 6: 提交**

```bash
git add scan.py tests/test_scan.py
git commit -m "速过键盘化：parse_ops 解析回传的累积操作串"
```

---

### Task K2: `store.delete_last_scan_attempt` 撤销一条扫读（Sonnet）

**Files:**
- Modify: `store.py`（文件末尾追加）
- Test: `tests/test_scan_store.py`（追加，不动既有用例）

**Interfaces:**
- Consumes: 既有的 `store.SCAN_SKILLS`、`get_conn()`
- Produces: `store.delete_last_scan_attempt(word_id: int, skill: str) -> int`，返回删掉的条数（0 或 1）

- [ ] **Step 1: 写失败测试**

在 `tests/test_scan_store.py` 末尾追加（`_fresh_db` 和 `_seed_word` 是该文件里已有的辅助函数，直接用）：

```python
def _raw_attempt(db, word_id, skill, answer, is_correct=1):
    """直接插一条 attempts，用来造「非扫读记录」这种对照组。"""
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO attempts (word_id, answer, is_correct, created_at, skill) "
        "VALUES (?,?,?,?,?)",
        (word_id, answer, is_correct, "2026-08-20T10:00:00", skill),
    )
    conn.commit()
    conn.close()


def _attempts(db):
    conn = sqlite3.connect(db)
    rows = conn.execute("SELECT skill, answer FROM attempts ORDER BY id").fetchall()
    conn.close()
    return rows


def test_delete_removes_only_the_last_scan_attempt(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path, monkeypatch)
    wid = _seed_word(db)
    store.record_scan_page([(wid, True)], "rec_meaning")
    store.record_scan_page([(wid, False)], "rec_meaning")
    assert store.delete_last_scan_attempt(wid, "rec_meaning") == 1
    assert _attempts(db) == [("rec_meaning", "（扫读·会）")]      # 只剩第一条


def test_delete_never_touches_typed_history(tmp_path, monkeypatch):
    """这是本卡最要紧的一条：打字练出来的记录一条都不许被删到。"""
    db = _fresh_db(tmp_path, monkeypatch)
    wid = _seed_word(db)
    _raw_attempt(db, wid, "produce", "chien")          # 打字练的
    _raw_attempt(db, wid, "rec_meaning", "chien")      # skill 对但不是扫读格式
    assert store.delete_last_scan_attempt(wid, "rec_meaning") == 0
    assert _attempts(db) == [("produce", "chien"), ("rec_meaning", "chien")]


def test_delete_is_scoped_to_the_given_skill(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path, monkeypatch)
    wid = _seed_word(db)
    store.record_scan_page([(wid, True)], "rec_meaning")
    store.record_scan_page([(wid, True)], "rec_produce")
    assert store.delete_last_scan_attempt(wid, "rec_meaning") == 1
    assert _attempts(db) == [("rec_produce", "（扫读·会）")]


def test_delete_is_scoped_to_the_given_word(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path, monkeypatch)
    a = _seed_word(db, "la confiture")
    b = _seed_word(db, "s'installer")
    store.record_scan_page([(a, True)], "rec_meaning")
    assert store.delete_last_scan_attempt(b, "rec_meaning") == 0
    assert len(_attempts(db)) == 1


def test_delete_still_leaves_words_row_untouched(tmp_path, monkeypatch):
    """v1 的核心不变量继续守：扫读这条路无论增删都不碰 words 的 SRS 状态。"""
    db = _fresh_db(tmp_path, monkeypatch)
    wid = _seed_word(db)
    store.record_scan_page([(wid, False)], "rec_produce")
    conn = sqlite3.connect(db)
    before = conn.execute("SELECT * FROM words WHERE id = ?", (wid,)).fetchone()
    conn.close()

    store.delete_last_scan_attempt(wid, "rec_produce")

    conn = sqlite3.connect(db)
    after = conn.execute("SELECT * FROM words WHERE id = ?", (wid,)).fetchone()
    conn.close()
    assert after == before


def test_delete_on_nothing_is_a_quiet_zero(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path, monkeypatch)
    wid = _seed_word(db)
    assert store.delete_last_scan_attempt(wid, "rec_audio") == 0


def test_delete_rejects_non_scan_skill(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    for bad in ("produce", "transcribe", "meaning", "pron", "morph", ""):
        with pytest.raises(ValueError):
            store.delete_last_scan_attempt(1, bad)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m pytest tests/test_scan_store.py -q`
Expected: FAIL，`AttributeError: module 'store' has no attribute 'delete_last_scan_attempt'`

- [ ] **Step 3: 在 `store.py` 末尾追加实现（照抄）**

```python
def delete_last_scan_attempt(word_id: int, skill: str) -> int:
    """撤销一条扫读自判（键盘流里按 ↑ 改判用）。返回删掉的条数（0 或 1）。

    为什么必须真删、不能再插一条覆盖：mastery.mastery_score 按天聚合时取的是
    「当天第一次」（`if cur is None or dt < cur[1]`）。手滑按错之后再插一条正确
    的，这一天仍然按错的那条算——改判会静默失效。

    删除范围三条同时满足才动手：
      1. skill 必须在 SCAN_SKILLS 里；
      2. 只看该 word_id + 该 skill；
      3. answer 必须以「（扫读·」开头。
    打字、念法语、变形练出来的历史一条都碰不到。**任何放宽都是事故。**
    """
    if skill not in SCAN_SKILLS:
        raise ValueError(f"delete_last_scan_attempt 只接受 {SCAN_SKILLS}，收到 {skill!r}")
    conn = get_conn()
    row = conn.execute(
        "SELECT id FROM attempts "
        "WHERE word_id = ? AND skill = ? AND answer LIKE '（扫读·%' "
        "ORDER BY id DESC LIMIT 1",
        (word_id, skill),
    ).fetchone()
    if row is None:
        conn.close()
        return 0
    conn.execute("DELETE FROM attempts WHERE id = ?", (row[0],))
    conn.commit()
    conn.close()
    return 1
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 -m pytest tests/test_scan_store.py -q`
Expected: 12 passed（既有 5 条 + 新增 7 条）

- [ ] **Step 5: 全量回归**

Run: `python3 -m pytest -q`
Expected: 全绿

- [ ] **Step 6: 提交**

```bash
git add store.py tests/test_scan_store.py
git commit -m "速过键盘化：撤销一条扫读自判，删除范围卡死在扫读记录内"
```

---

### Task K3: 删掉鼠标那一套，表格简化成当前行模型（总管自做）

不写完整代码——这张卡是删除加改写，代码由执行者（总管）现场决定，契约和验收如下。

**Files:**
- Modify: `app.py`
- Modify: `tests/test_scan_table.py`（跟着删/改）
- Modify: `tests/test_scan_ui.py`（去掉揭法相关断言）
- Delete: `tests/test_scan_commit.py`（`commit`/`parse_missed` 的调用点没了）

**删除清单**（设计文档 §6）：

| 删除 | 当前规模 |
|---|---|
| `_scan_behavior_script()` 三种揭法 | 54 行 |
| `_scan_sync_script()` 勾选框同步 | 42 行 |
| 表格里的 `.scan-miss` 勾选框列 | — |
| 「揭法」selectbox 与 `scan_reveal` 设置 | — |
| `data-rev` / `scan_rev` 清勾选机制 | — |
| `st.form` 与「记下这一页 ▶」按钮 | — |
| 带标签的序号输入框 | — |
| `scan.commit` / `scan.parse_missed` 及其测试 | — |

**`_scan_table_html` 改写后的契约**：

- 签名去掉 `rev` 参数，新增 `cursor: int`（当前是本页第几行，0-based）
- 当前行带 `data-current='1'`，其余行没有
- 播放按钮只画在当前行，尺寸放大到整格可点（约 40×32px），且仍受 `play_locked` 约束
- 盖住格保留 `class='scan-cover'` 与 `display:inline-block;width:100%`（v1 修过的点击命中问题不许回潮）
- 输出里不再出现 `scan-miss`、`data-rev`

**验收**：

- [ ] `grep -c "scan-miss\|data-rev\|scan_reveal\|_scan_sync_script\|_scan_behavior_script" app.py` 结果为 0
- [ ] `tests/test_scan_table.py` 有一条测试断言输出里**没有** `scan-miss` 和 `data-rev`（防回潮）
- [ ] 有测试断言当前行带 `data-current='1'` 且只有一行带
- [ ] 有测试断言播放按钮只出现在当前行
- [ ] 全量 `python3 -m pytest -q` 全绿
- [ ] 提交信息说明删了什么、为什么（键盘接管后无使用场景）

---

### Task K4: 键盘脚本 + fragment 回传 + 翻页时序（总管自做）

本卡三部分互相咬合，拆开就没法独立验证，所以合成一张。

**Files:**
- Modify: `app.py`
- Test: `tests/test_scan_keyboard.py`（新建）、`tests/test_scan_ui.py`（追加）

**Interfaces:**
- Consumes: `scan.parse_ops`（K1）、`store.delete_last_scan_attempt`（K2）、`store.record_scan_page`
- Produces: `app._scan_keyboard_script(direction, autoplay) -> str`；session key `scan_written`

**必须实现的契约**（设计文档 §3–§5、§7）：

| 项 | 要求 |
|---|---|
| 键位 | `?`/`/`/`E`=揭晓；`空格`=播放；`←`/`A`=会；`→`/`D`=不会；`↓`/`S`=跳过；`↑`/`W`=回退 |
| 焦点让路 | `activeElement` 是 `input`/`textarea`/`select`/`contentEditable` 时全部不接管 |
| `preventDefault` | 六个键都要挡，尤其 `/`（Firefox 快速查找）和方向键（页面滚动） |
| 自动播放 | `rec_audio` 切词必播；`rec_meaning` 默认播可关；`rec_produce` 永不 |
| 空格锁 | `rec_produce` 揭晓前不发声，当前行边框闪一下作静默提示 |
| 回传 | 累积操作串写进 `scan_sink`（native setter + `input` 事件），点 `scan_flush` |
| 增量写入 | 服务端 `scan_written` 记已处理条数，只处理 `ops[scan_written:]` |
| 翻页时序 | 先 flush → 轮询回执直到 `scan_written == ops.length`（超时 3 秒）→ 才翻页；等不到就不翻并提示 |
| 隐藏元素 | `scan_sink` / `scan_flush` / 回执用作用域 CSS 藏掉，不带 `!important` |
| 视觉 | 当前行高亮 + `scrollIntoView({block:'center'})`；表态后底色闪绿/红再前进 |

**验收**：

- [ ] `tests/test_scan_keyboard.py` 断言脚本字符串含全部六个键的绑定、WASD 镜像、焦点让路判断、`preventDefault`
- [ ] `tests/test_scan_ui.py` 有用例：写入累积串 → fragment 重跑 → 记录进库
- [ ] 同一串重复提交不重复写（幂等）
- [ ] `U:` 能撤销，且撤销后 `words` 那一行仍逐字节未变
- [ ] 三个方向各有一条测试断言自动播放/锁定的取值正确
- [ ] 全量 `python3 -m pytest -q` 全绿
- [ ] **本卡的单测只能证明字符串和数据流，证明不了按键真的响应**——真机验证是 K5，不许拿本卡的绿当成功能可用

---

### Task K5: 真机验收（总管自做，不派 Sonnet）

照 v1 里 S0 的办法：起真实 app，在浏览器里逐项过，把**真实观察到的输出**写回设计文档。

**跑之前必须备份**：`cp dictation.db /tmp/kb-verify.bak`，验完恢复并删除备份（v1 里就是这么干的，别省）。

**逐项清单**：

- [ ] 六个键在箭头侧全部响应，含 `?` 和 `/` 两种打法
- [ ] WASD + `E` 侧完全等效
- [ ] 空格能出声，连按能重播
- [ ] `看中→想法` 档：揭晓前按空格不发声；揭晓后能发声
- [ ] `听音→想双` 档：切词自动响一次
- [ ] `看法→想中` 档：切词自动响，关掉开关后不响
- [ ] 连按 `←←←` 三下，回查数据库三条都在（**不丢判定**）
- [ ] 按错后按 ↑ 改判，回查数据库是改后的那条，且**只有一条**
- [ ] 焦点点进侧栏「选课」后按方向键，选项**不被切换**、扫读也不响应
- [ ] 在本页最后一个词表态，翻页后回查数据库那条确实写进去了
- [ ] 走完一页自动翻页，新页光标在第一行、无残留高亮

- [ ] 把每项的真实结果（不是预期）写进 `docs/specs/2026-08-20-vocab-scan-keyboard-design.md` 的验收小节并提交
- [ ] 恢复 `dictation.db`，确认 `attempts` 行数与备份时一致

---

### Task F: 真实练一课（用户本人，不派任何模型）

- [ ] 拿 L36 那 164 个词，三个方向各键盘过一遍，记录实际耗时
- [ ] 确认双手键位都顺手，累了能换手
- [ ] 定出「看法→想中」档自动播放到底该默认开还是关，把结论写回设计文档 §12
- [ ] 确认词表里那些词的 听/产/义/音 四列**没有**因为扫读而变动
- [ ] 决定滚筒（第二步）值不值得做

## Self-Review

**1. 设计文档覆盖检查**

| 设计文档章节 | 落在哪张卡 |
|---|---|
| §3 键位与焦点让路 | K4 |
| §4 三档发音规则与空格锁 | K4（实现）+ K5（真机验） |
| §5 每次按键立刻入库 | K4 |
| §5.1 累积操作列表 | K1（解析）+ K4（回传与增量写入） |
| §5.2 改判必须真删 | K2 |
| §6 删掉鼠标那一套 | K3 |
| §7 客户端状态与翻页时序 | K4 |
| §8 模块边界 | K1/K2/K3/K4 各自对应 |
| §9 错误处理与降级 | K1（脏值）、K2（无可删返回 0）、K4（预热未完、脚本挂不上） |
| §10 测试 | 各卡自带 + K5 收人工项 |
| §11 第二步滚筒 | 不在本计划，F 卡收结论 |
| §12 未决 | F 卡收「自动播放默认值」；作用域 CSS 在 K4 里落地 |

**2. 无占位符**：K1/K2 给了完整代码与完整测试；K3/K4/K5 是总管自做的卡，按本计划开头声明的粒度规则给契约与验收清单而非代码，这是刻意的，不是待填。

**3. 类型一致性**

- `scan.parse_ops` 在 K1 定为返回 `[("mark", int, bool)]` / `[("undo", int, None)]`，K4 按此消费 —— 一致。
- `store.delete_last_scan_attempt(word_id, skill) -> int` 在 K2 定义，K4 按此调用 —— 一致。
- `_scan_table_html` 在 K3 去掉 `rev`、加 `cursor`，K4 不再传 `rev` —— 一致。
- `SCAN_SKILLS` 沿用 v1 已有的常量，K2 复用不重复定义 —— 一致。
