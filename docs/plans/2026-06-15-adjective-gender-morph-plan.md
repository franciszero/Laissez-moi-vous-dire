# 形容词阴阳性「变形」练习 实施计划

> **For agentic workers:** 用 superpowers:executing-plans 或 subagent-driven-development 逐任务实施。步骤用 `- [ ]`。
> **本项目非 git 仓库**：所有「Commit」步骤替换为「跑 pytest + 必要时 AppTest 验证」。改 app.py 这类被 import 的模块后，验证完要 **重启 streamlit**（`pkill -f "streamlit run app.py"; nohup streamlit run app.py --server.port 8501 --server.headless true >/tmp/dictation_app.log 2>&1 &`）。
> **shell 开了 `set -e`**：多行 bash 开头加 `set +e`。
> **碰真实 DB 的验证**：先 `cp dictation.db /tmp/dictation.db.bak`，测完 `cp /tmp/dictation.db.bak dictation.db`。

**Goal:** 让用户练「看阳性→写阴性」，作为新掌握维度「变」(morph) 跟踪/上色，阴性数据从现有 vocab.json 回填。

**Architecture:** vocab.py 解析时重建阴性(`fem`/`fem_raw`)；一次性回填脚本补现有词表；mastery 加 morph 维度且 `overall` 只对适用技能取 min；app.py 加「看阳性→写阴性」模式 + 侧栏「变形(N)」入口 + 词表第 4 列「变」。

**Tech Stack:** Python 3.11, Streamlit 1.58, SQLite, pytest, streamlit.testing AppTest。

参考 spec：`docs/specs/2026-06-15-adjective-gender-morph-design.md`

---

### Task 1: `vocab.feminine_form` + 解析时捕获阴性

**Files:**
- Modify: `vocab.py`（重构 `clean_lemma`，加 `_strip_notations`/`split_gender`/`feminine_form`；`parse_lesson_table` 与 `parse_uploaded` 给每条加 `fem`/`fem_raw`）
- Test: `tests/test_vocab.py`

- [ ] **Step 1: 写失败测试**

加到 `tests/test_vocab.py`：

```python
import vocab


def test_feminine_form_rules():
    f = vocab.feminine_form
    assert f("court", "e") == "courte"
    assert f("épicier", "ère") == "épicière"
    assert f("chanteur", "euse") == "chanteuse"
    assert f("conducteur", "trice") == "conductrice"
    assert f("délicieux", "se") == "délicieuse"
    assert f("neuf", "ve") == "neuve"
    assert f("Parisien", "ne") == "Parisienne"
    assert f("naturel", "le") == "naturelle"
    assert f("occidental", "occidentale") == "occidentale"   # 完整词
    assert f("beau", "belle") == "belle"                      # 完整词
    assert f("autonome", None) is None                        # 无标记
    assert f("secret", "ète") is None                         # 拿不准 -> None


def test_split_gender():
    assert vocab.split_gender("court, e") == ("court", "e")
    assert vocab.split_gender("occidental, occidentale (adj; x)") == ("occidental", "occidentale")
    assert vocab.split_gender("autonome") == ("autonome", None)


def test_parse_uploaded_captures_fem():
    text = "ADJECTIFS\tcourt, e\t短的\nADJECTIFS\tautonome\t自主的"
    entries, _ = vocab.parse_uploaded(text, lesson="LX")
    by = {e["lemma"]: e for e in entries}
    assert by["court"]["fem"] == "courte"
    assert by["court"]["fem_raw"] == "e"
    assert by["autonome"]["fem"] is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m pytest tests/test_vocab.py -q`
Expected: FAIL（`feminine_form`/`split_gender` 不存在；`fem` 键缺失）

- [ ] **Step 3: 实现**

在 `vocab.py`：把现有 `clean_lemma` 的"去标记"部分抽成 `_strip_notations`，再加三个函数。

```python
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
    s = re.sub(r"\[[^\]]*\]", "", s)
    s = re.sub(r"（[^）]*）", "", s)
    s = re.sub(r"\([^)]*\)", "", s)
    changed = True
    while changed:
        changed = False
        s = s.strip()
        for abbr in _GRAM_ABBR:
            if s.endswith(abbr):
                s = s[: -len(abbr)]
                changed = True
                break
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
```

把 `clean_lemma` 改成复用 `_strip_notations`：

```python
def clean_lemma(raw: str) -> str:
    """从课表 Français 单元格得到朗读&听写目标。"""
    s = _strip_notations(raw)
    if "," in s:                              # 阴阳性/词形对取基本形
        s = s.split(",", 1)[0]
    return s.strip()
```

在 `parse_lesson_table` 构造词条 dict 里（`"raw": french` 那条之后）加：

```python
                "fem": feminine_form(*split_gender(french)),
                "fem_raw": split_gender(french)[1],
```

（`parse_uploaded` 若是先把上传文本规整成 `类别\tfr\tzh` 再调用 `parse_lesson_table`，则无需再改；否则在它构造词条处同样加这两行。先读 `parse_uploaded` 确认。）

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 -m pytest tests/test_vocab.py -q`
Expected: PASS

- [ ] **Step 5: 验证（代提交）**

Run: `set +e; python3 -m pytest -q 2>&1 | tail -1`
Expected: 全绿（原有用例不破）

---

### Task 2: 回填脚本补现有 vocab.json

**Files:**
- Create: `scripts/backfill_fem.py`

- [ ] **Step 1: 写脚本**

```python
#!/usr/bin/env python3
"""给现有 ../L*/vocab.json 回填 fem/fem_raw（从每条的 raw 重算）。跑一次即可。"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import vocab  # noqa: E402

BASE = pathlib.Path(__file__).resolve().parent.parent.parent  # 本地录屏课/


def main() -> None:
    for vj in sorted(BASE.glob("L*/vocab.json")):
        data = json.loads(vj.read_text("utf-8"))
        n = 0
        for e in data:
            masc, marker = vocab.split_gender(e.get("raw") or e.get("lemma") or "")
            fem = vocab.feminine_form(masc, marker)
            e["fem"] = fem
            e["fem_raw"] = marker
            if fem:
                n += 1
        vj.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
        print(f"{vj.parent.name}: {len(data)} 词，回填阴性 {n} 个")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 跑脚本**

Run: `set +e; cd "/Users/francis/Documents/法语/本地录屏课/听写"; python3 scripts/backfill_fem.py`
Expected: 打印每课词数 + 回填数（L20 应有十几个）

- [ ] **Step 3: 抽查结果合理**

Run:
```bash
set +e; python3 -c "
import json
d=json.load(open('../L20/vocab.json'))
for e in d:
    if e.get('fem'): print(e['lemma'],'->',e['fem'],'(',e['fem_raw'],')')
" | head
```
Expected: `court -> courte ( e )`、`habitant -> habitante ( e )` 等合理；不规则的若 fem 为空、fem_raw 仍在（可手改）。

---

### Task 3: mastery 加 morph 维度，overall 只对适用技能取 min

**Files:**
- Modify: `mastery.py`
- Test: `tests/test_mastery.py`

- [ ] **Step 1: 写失败测试**

加到 `tests/test_mastery.py`：

```python
def test_overall_default_ignores_morph():
    # 默认只看 form/meaning/pron，三项满即满（morph 不拉低）
    assert mastery.overall({"form": 0.8, "meaning": 0.8, "pron": 0.8}) == 0.8


def test_overall_with_morph_applicable():
    sc = {"form": 0.8, "meaning": 0.8, "pron": 0.8, "morph": 0.0}
    # 显式带上 morph 时，morph=0 -> 总掌握 0
    assert mastery.overall(sc, skills=mastery.BASE_SKILLS + ("morph",)) == 0.0
    assert "morph" in mastery.SKILLS
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m pytest tests/test_mastery.py -q`
Expected: FAIL（`BASE_SKILLS` 不存在 / `overall` 不接受 `skills`）

- [ ] **Step 3: 实现**

`mastery.py` 把 SKILLS/overall 改成：

```python
BASE_SKILLS = ("form", "meaning", "pron")          # 每个词都适用
SKILLS = BASE_SKILLS + ("morph",)                  # 变形：仅有阴性的词适用


def overall(skill_to_score: dict, skills=BASE_SKILLS) -> float:
    """一个词的总掌握 = 适用技能里最弱那项（没练的算 0）。"""
    return min(float(skill_to_score.get(s, 0.0)) for s in skills)
```

（`skill_scores` 不用改：它按 attempts 里出现的 skill 自动分组，"morph" 会自然产生一项。）

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 -m pytest tests/test_mastery.py -q`
Expected: PASS（含原有 `test_skill_scores_and_overall`）

- [ ] **Step 5: 验证**

Run: `set +e; python3 -m pytest -q 2>&1 | tail -1`
Expected: 全绿

---

### Task 4: app.py 加「看阳性→写阴性」模式（提示 + 输入 + 判定 + 入库）

**Files:**
- Modify: `app.py`（MODES；prompt 显示；form 输入；submit 处理；加 `_finalize_morph`）

- [ ] **Step 1: MODES 加模式**

`MODES` 字典末尾（`"看法语 → 念法语"` 那条之后）加：

```python
    "看阳性 → 写阴性": ("fr_morph", ("fem",), "morph"),
```

- [ ] **Step 2: 加 `_finalize_morph`**

在 `_finalize` 函数之后加（紧挨 `render_answer_table` 旁）：

```python
def _finalize_morph(word, fem_ans) -> None:
    """变形模式落定：对照 VOCAB[词].fem，记 skill=morph。"""
    fem = VOCAB.get(word["text"], {}).get("fem")
    ok = bool(fem) and matcher.check_fr(fem_ans, fem)
    record_attempt(word["id"], (fem_ans or "").strip() or "（空）", ok, "morph")
    st.session_state.round_results[word["id"]] = ok
    st.session_state.graded = True
    st.session_state.feedback = {
        "type": "success" if ok else "error",
        "message": "✅ 对" if ok else "❌ 有错",
        "rows": [("阴性", (fem_ans or "").strip() or "（空）", fem or "（无阴性）", ok)],
    }
```

- [ ] **Step 3: prompt 显示分支**

在 prompt 区（`if PROMPT_TYPE == "zh_text": ... elif PROMPT_TYPE == "fr_text": ...` 处）加一支：

```python
        elif PROMPT_TYPE == "fr_morph":
            st.info(f"阳性：{current_word['text']} — {zh_gloss}，写出它的阴性形式")
```

- [ ] **Step 4: 输入分支（无阴性兜底 + fem 输入框 + 提交）**

在渲染答题区的 `if ANSWER_FIELDS == ("speak_fr",): render_speak(...)` 之前加一支处理 morph（放在 speak 分支前，pending 分支前）：

```python
        elif ANSWER_FIELDS == ("fem",):
            if not VOCAB.get(current_word["text"], {}).get("fem"):
                st.caption("（这个词没有阴阳性变化）")
                if st.button("下一题 ▶", type="primary"):
                    next_word()
                    st.rerun()
            else:
                col_p, col_a, col_b = st.columns(3)
                if col_p.button("上一题", disabled=st.session_state.index <= 1):
                    if prev_word():
                        st.rerun()
                if col_a.button("显示答案"):
                    st.session_state.show_answer = True
                    if not st.session_state.graded:
                        record_attempt(current_word["id"], "（看了答案）", False, "morph")
                        st.session_state.round_results[current_word["id"]] = False
                        st.session_state.graded = True
                if col_b.button("下一题"):
                    next_word()
                    st.rerun()
                with st.form("morph_form", clear_on_submit=True):
                    fem_ans = st.text_input("阴性形式：", key="ans_fem")
                    submitted_m = st.form_submit_button("提交答案", type="primary")
                if st.session_state.focus_input:
                    focus_answer_input()
                    st.session_state.focus_input = False
                if submitted_m:
                    if st.session_state.graded:
                        ok = bool(matcher.check_fr(fem_ans, VOCAB[current_word["text"]]["fem"]))
                        st.session_state.feedback = {
                            "type": "success" if ok else "error",
                            "message": ("✅（练习，不计分）" if ok else "❌（练习，不计分）")
                            + VOCAB[current_word["text"]]["fem"],
                        }
                    else:
                        _finalize_morph(current_word, fem_ans)
                        if auto_next and st.session_state.feedback["type"] == "success":
                            time.sleep(0.6)
                            next_word()
                    st.rerun()
```

注：`show_answer` 显示答案那块（`if st.session_state.show_answer: st.info(f"答案：{current_word['text']} — {zh_gloss}")`）对 morph 应显示阴性。把那行改成：

```python
            if st.session_state.show_answer:
                if ANSWER_FIELDS == ("fem",):
                    st.info(f"阴性：{VOCAB.get(current_word['text'], {}).get('fem', '（无）')}")
                else:
                    st.info(f"答案：{current_word['text']} — {zh_gloss}")
```

（反馈区 `fb_rows>=2 用表格、否则消息` 逻辑不用改：morph 的 rows 只有 1 行，会走消息分支，已带 ✅/❌ 文案。）

- [ ] **Step 5: 验证（AppTest，备份真实 DB）**

```bash
set +e
cd "/Users/francis/Documents/法语/本地录屏课/听写"
cp dictation.db /tmp/dictation.db.bak
python3 -m py_compile app.py && echo "compile OK"
python3 - <<'PY' 2>/dev/null
from streamlit.testing.v1 import AppTest
at = AppTest.from_file("app.py", default_timeout=30); at.run(); assert not at.exception
at.selectbox(key="mode").set_value("看阳性 → 写阴性").run(); assert not at.exception
[b for b in at.button if b.label.startswith("开始这一课")][0].click().run(); assert not at.exception
print("morph 模式渲染 OK")
PY
cp /tmp/dictation.db.bak dictation.db
```
Expected: `compile OK` + `morph 模式渲染 OK`，无异常。

---

### Task 5: 词表加「变」列 + overall 带上适用 morph

**Files:**
- Modify: `app.py` `render_word_panel`

- [ ] **Step 1: 改 scores/列/上色**

`render_word_panel` 里：

把 caption 补上「变」说明（"形/义/音/变"）。

`df` 的列加「变」：

```python
            "变": ["" for _ in rows],
```

`_style` 里 `cmap` 加 morph，并按"该词是否有阴性"决定适用技能：

```python
    def _style(row):
        wid = rows[row.name]["id"]
        sc = scores[wid]
        has_fem = bool(VOCAB.get(rows[row.name]["text"], {}).get("fem"))
        skills = mastery_mod.BASE_SKILLS + (("morph",) if has_fem else ())
        cmap = {
            "词": mastery_mod.mastery_color(mastery_mod.overall(sc, skills=skills)),
            "形": mastery_mod.mastery_color(sc.get("form", 0.0)),
            "义": mastery_mod.mastery_color(sc.get("meaning", 0.0)),
            "音": mastery_mod.mastery_color(sc.get("pron", 0.0)),
            "变": mastery_mod.mastery_color(sc.get("morph", 0.0)) if has_fem else "#f5f5f5",
        }
        return [
            f"background-color:{cmap[c]}; color:#1a1a1a" if c in cmap else ""
            for c in row.index
        ]
```

`cols` 加「变」：

```python
    cols = ["词", "形", "义", "音", "变", "翻译"] if show_trans else ["词", "形", "义", "音", "变"]
```

无阴性的词「变」格用浅灰 `#f5f5f5`（视觉上=不适用）。

- [ ] **Step 2: 验证（AppTest）**

```bash
set +e; cd "/Users/francis/Documents/法语/本地录屏课/听写"
cp dictation.db /tmp/dictation.db.bak
python3 -m py_compile app.py && echo OK
python3 - <<'PY' 2>/dev/null
from streamlit.testing.v1 import AppTest
at=AppTest.from_file("app.py",default_timeout=30); at.run(); assert not at.exception
[b for b in at.button if b.label.startswith("开始这一课")][0].click().run(); assert not at.exception
print("词表(含变列)渲染 OK")
PY
cp /tmp/dictation.db.bak dictation.db
```
Expected: `OK` + `词表(含变列)渲染 OK`，无异常。

---

### Task 6: 侧栏「变形(N)」入口 + 自动切到变形模式

**Files:**
- Modify: `app.py`（加 `_fem_ids`、`start_lesson_morph`；侧栏加按钮）

- [ ] **Step 1: 加 helper + start 函数**

紧挨 `_lesson_ids` 之后加：

```python
def _fem_ids(lesson: str, lessons_map: dict) -> list[int]:
    """某一课里「有阴性形式」的词 id（变形练习的词池）。"""
    rows = get_words_by_ids(_lesson_ids(lesson, lessons_map))
    return [r["id"] for r in rows if VOCAB.get(r["text"], {}).get("fem")]
```

紧挨 `start_lesson_review` 之后加：

```python
def start_lesson_morph(lesson: str, lessons_map: dict, batch_size: int) -> int:
    """变形练习：只练这一课里有阴性的词，并自动切到「看阳性→写阴性」模式。"""
    ids = _fem_ids(lesson, lessons_map)
    reset_round(ids, batch_size)
    st.session_state.round_lesson = lesson
    st.session_state.round_label = "变形 · 全部" if lesson == "全部" else f"变形 · {lesson}"
    st.session_state["mode"] = "看阳性 → 写阴性"   # 下次渲染 selectbox 会读到
    return len(ids)
```

- [ ] **Step 2: 侧栏按钮**

在侧栏「学习」块里，`cw, cd = st.columns(2)`（错词/到期）那段之后、`st.caption("错词=...")` 之前加：

```python
    _n_fem = len(_fem_ids(chosen_lesson, LESSONS))
    if st.button(f"变形（{_n_fem}）", disabled=_n_fem == 0):
        save_setting("last_lesson", chosen_lesson)
        start_lesson_morph(chosen_lesson, LESSONS, batch_size)
        st.rerun()
```

把那条 caption 补一句：`形=听写、义=词义、音=发音、变=阴阳性变形。`

- [ ] **Step 3: 验证（AppTest 全流程，备份 DB）**

```bash
set +e; cd "/Users/francis/Documents/法语/本地录屏课/听写"
cp dictation.db /tmp/dictation.db.bak
python3 -m py_compile app.py && echo "compile OK"
python3 - <<'PY' 2>/dev/null
from streamlit.testing.v1 import AppTest
import sqlite3
at = AppTest.from_file("app.py", default_timeout=30); at.run(); assert not at.exception
# 选 L20（阴性词多），点「变形（N）」
at.selectbox(key="sel_lesson").set_value("L20").run(); assert not at.exception
mbtn = [b for b in at.button if b.label.startswith("变形（")]
print("变形按钮:", [b.label for b in mbtn])
assert mbtn and not mbtn[0].disabled
mbtn[0].click().run(); assert not at.exception
print("模式已切:", at.session_state["mode"], "| 词池:", len(at.session_state["pool"]))
assert at.session_state["mode"] == "看阳性 → 写阴性"
# 提交一个阴性
w = at.session_state["current_word"]; fem = None
import json; v = json.load(open("../L20/vocab.json"))
fem = next((e["fem"] for e in v if e["lemma"] == w["text"]), None)
at.text_input(key="ans_fem").set_value(fem or "x")
[b for b in at.button if b.label == "提交答案"][0].click().run(); assert not at.exception
hit = sqlite3.connect("dictation.db").execute(
    "SELECT skill,is_correct FROM attempts WHERE word_id=? ORDER BY id DESC LIMIT 1", (w["id"],)
).fetchone()
print("最后一条 attempt:", hit, "（应 skill=morph）")
assert hit[0] == "morph"
print("变形全流程 OK ✅")
PY
cp /tmp/dictation.db.bak dictation.db
```
Expected: `compile OK` → 变形按钮带数字且可点 → 模式切到「看阳性 → 写阴性」、词池>0 → 最后一条 attempt `skill=morph` → `变形全流程 OK ✅`。

---

### Task 7: 全量验证 + 回填真实词表 + 重启

- [ ] **Step 1: 全测试**

Run: `set +e; cd "/Users/francis/Documents/法语/本地录屏课/听写"; python3 -m pytest -q 2>&1 | tail -2`
Expected: 全绿（原 34 + 新增用例）

- [ ] **Step 2: 回填真实词表（一次性，改的是 ../L*/vocab.json，不是 DB，无需备份）**

Run: `set +e; python3 scripts/backfill_fem.py`
Expected: 各课打印回填数

- [ ] **Step 3: 重启 server（应用 app.py 改动 + 重扫词表）**

```bash
set +e; cd "/Users/francis/Documents/法语/本地录屏课/听写"
pkill -f "streamlit run app.py"; sleep 1
nohup streamlit run app.py --server.port 8501 --server.headless true >/tmp/dictation_app.log 2>&1 &
curl --retry 30 --retry-delay 1 --retry-connrefused -s -o /dev/null -w "health: %{http_code}\n" localhost:8501/_stcore/health
grep -icE 'error|traceback|exception' /tmp/dictation_app.log
```
Expected: `health: 200`、报错数 `0`

- [ ] **Step 4: 更新 HANDOFF.md**

在 §3 加一条 ✅ 「变形(morph)维度 + 看阳性→写阴性模式 + 阴性回填」；在文件地图把 `scripts/backfill_fem.py` 列上；§5 记 `feminine_form`/`split_gender`、`BASE_SKILLS`/`overall(skills=)`、morph 模式与「变形(N)」入口。

---

## 自检（Self-Review）

- **Spec 覆盖**：①阴性数据(回填+解析)=Task1+2 ✅；②morph 维度+overall 修正=Task3 ✅；③看阳性→写阴性模式=Task4 ✅；④词表「变」列=Task5 ✅；⑤「变形(N)」入口=Task6 ✅；⑥不规则兜底=feminine_form 返回 None + fem_raw 保留(Task1) ✅。
- **占位符**：无 TBD/TODO；新逻辑均给了完整代码。
- **类型/命名一致**：`feminine_form`/`split_gender`/`_strip_notations`(Task1)、`BASE_SKILLS`/`overall(skills=)`(Task3)、`_finalize_morph`/`_fem_ids`/`start_lesson_morph`(Task4/6)、字段 `fem`/`fem_raw`、skill 字符串 `"morph"`、模式名 `"看阳性 → 写阴性"`、prompt 类型 `"fr_morph"` —— 全程一致。
- **风险**：①不规则阴性重建可能漏(beau/belle 靠"完整词"分支命中，其余罕见→None+手改)；②变形模式遇无阴性词靠 caption+下一题兜底(Task4 Step4)；③`st.session_state["mode"]` 在按钮里赋值靠下次 rerun 生效(Task6)——AppTest Step3 已验证。