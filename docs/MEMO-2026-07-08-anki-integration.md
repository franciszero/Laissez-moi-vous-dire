# 备忘录 · Anki 集成（读侧 + 生成侧）+ 调查手册（2026-07-08）

一句话：**app 只读 Anki（`anki.py`），卡片内容由外部工具 anki-wordsmith 生成。** 本文记录读侧模型、
生成侧词条格式、本 session 修的两个 bug，以及排查 Anki 问题的调查手册与可复制证据命令。让下个
agent 不必重新逆向。相关：`anki.py`、`tests/test_anki.py`、生成工具见 §3、路线图 `docs/specs/2026-06-08-l18-wordbank-dual-mode-anki-enrichment-design.md`。

## 1. 读侧：app 怎么读 Anki（`anki.py`，只读，绝不写）
- AnkiConnect `http://127.0.0.1:8765`，牌组 `Français`，note type `Francis 的 法语单词卡`。**只用读 action**（findNotes/notesInfo/cardsInfo）；**永不** addNote/updateNoteFields/deleteNotes。
- `_find_note(lemma)`：去冠词 + `_norm`（小写 + 去重音）双向匹配；**找不到精确匹配返回 None**（宁缺毋错，曾因 fallback 返回错词卡，已删）。
- `card_state(lemma)` → `{status, html, reason}`：
  - `ok`：有真内容 → 渲染 html。
  - `stub`：笔记在但**生成失败**——QA Summary 含「解析失败」，或核心四字段 `Core Meaning / Définition FR / Grammar Frame / Example Sentences` 全空/全 `N/A` → 不显示空卡，给「待重新生成」提示。
  - `missing`：没笔记/没卡/Anki 没开 → 静默（沿用宁缺毋错）。
- `memoized_state(cache, lemma)`：**只缓存 `ok`**；`missing`/`stub` 每次重查 → 运行期间新生成的卡立即出现。app 端 `card_state_cached` 用 `st.session_state["_anki_ok_cache"]`；「🔄 重新扫描词表」会清它。
- note 字段：`Lemma / QA Summary / POS + Core Grammar Tag / Article·Number·Basic Form / IPA + Pronunciation Notes / Core Meaning / Définition FR / Grammar Frame / Register / Usage Comparison / Collocations / Example Sentences / Faux Amis / Mini Dialogues / My Output`。

## 2. 本 session 修的两个读侧 bug（根因 + commit）
- **残卡显示成一片 N/A**（`5fa3005`）：生成失败的 note 字段全 N/A，app 老实渲染成空卡（L23 `une attitude`）。根因＝`render_card` 只判「note 在不在」。修＝`card_state` 识别 stub、隐藏空卡 + 提示。
- **新生成的卡网站看不到**（`3bbfb62`）：`card_state_cached` 曾用 `@st.cache_data` 无失效，把「missing」**永久缓存**；「🔄 重新扫描」也不清它 → 卡生成后仍看不到，非重启不可（L27 `le poste de télévision`）。根因＝负结果被永久缓存。修＝`memoized_state` 只缓存 ok。
- 调查关键：**先在进程内直接 `A.card_state(lemma)`**——若返回 ok 但网站 missing，就是缓存/刷新问题，不是匹配 bug。

## 3. 生成侧：anki-wordsmith（app 不含，但每课都要用它补卡）
- 位置：`/Users/francis/Documents/Georgian_College/GitHub/anki-wordsmith`（法语制卡流水线）。
- **输入词条格式**（权威＝`src/french/input_parser.py`，一行一条）：
  - `lemma` / `lemma (词性)` / `lemma (词性; 消歧上下文)` / `lemma (消歧上下文)`。
  - 括号内若非词性 → 整体作 `USAGE_CONTEXT`（消歧/对齐）；`词性; 上下文` 用**分号**分隔（只切第一个 `;`）。
  - **词性 token 必须精确**（`schema.POS_HINT_MAP`）：`n/noun · v/verb · adj · adv · conj · prep · pron · det · loc/expression/idiom · interj`。⚠️ `n.m.`/`n. m.` **不认**，会被当成上下文。
  - **名词必须带冠词**（le/la/les/un/une/l'），否则 `_parse_line` 抛 `ValueError`。
  - 「消歧上下文」是让生成器选对词义/用法，**不是最终例句**（流水线自己生成卡内例句）。上下文里别放 `(` `)`（会破坏解析）。
- **stub 的成因**：生成时模型输出解析失败 → 写占位 note（全 N/A + QA Summary「不建议直接学习/解析失败」）。**裸词/歧义词最容易失败**——带括号消歧正是为降低失败率。

## 4. 本 session 生成侧产物（工作记录）
- **L23 修 8 词**：残卡 `de nos jours / progrès / une attitude`（note 在、全 N/A）+ 缺卡 `poser une question à quelqu'un / au cœur de / avec le développement de / c'est pas grave / la maladie`。已给用户带括号词条，用户自行重生成。
- **L27 批 59 条**：把「做题/课文摘抄」转成标准词条——headword 归一到基本型（变位→不定式、复数名词→单数带冠词、gérondif/过去分词→不定式）、把填空题**解成正确例句**（关系代词 dont/où/que、代词 y/en/le·la·les、复合过去时性数配合、按语境定时态/祈使）、去重、名词补冠词。全部过 `parse_french_entries` 校验（0 problem）。

## 5. 调查手册（可复制的证据命令）
```python
# 读侧：探活 + 看某词的真实 note 字段（区分 ok/stub/missing）
import anki as A
print(A.card_state("le poste de télévision")["status"])
info = A._find_note("une attitude")
[print(k, "=", A.html_to_text(v["value"])[:60]) for k, v in info["fields"].items()]

# 扫一整课的坏卡（ok / stub / missing）
import json
for lm in [e["lemma"] for e in json.load(open("../L23/vocab.json"))]:
    info = A._find_note(lm)
    if not info: print("missing", lm); continue
    core = A.html_to_text(info["fields"].get("Core Meaning", {}).get("value","")).strip()
    print("stub" if (not core or core.upper()=="N/A") else "ok", lm)

# 生成侧：验证词条是否合法（含名词冠词检查）
import sys; sys.path.insert(0, "/Users/francis/Documents/Georgian_College/GitHub/anki-wordsmith/src")
from french.input_parser import parse_french_entries
for e in parse_french_entries("une attitude (n; ...)"):
    print(e.lemma, e.pos_hint, e.context)
```

## 6. 掌握度色块（另一条调查线，本 session 结论）
- 现行 `mastery.mastery_score` = 每天取第一次(冷启动) → 半衰期(14d) → Wilson 下界(Z=1.28)；`overall`=min(形/义/音)；颜色 0灰→中黄→1绿。
- 「**同日先错后对，色块不动**」= 设计（当天第一次为准，防看答案刷分），**不是 bug**。`✅`(本轮结果) 与色块(耐久掌握)是**两个信号**，别混。
- 用户直觉「色块应平滑表示记住程度」→ 已给数值定义（**间隔因子 s(Δt)=Δt/(Δt+τ) × 半衰期**），5 场景 + 真实数据验算，存 `docs/specs/2026-07-08-smooth-mastery-design.md`。**用户选择暂不实现。**
- 调查方法：查 DB `attempts` 表 + 用 `mastery.mastery_score` 离线重算任意词（attempts 自带时间戳）：
  ```python
  import sqlite3, mastery
  c = sqlite3.connect("dictation.db")
  wid = [r[0] for r in c.execute("SELECT id FROM words WHERE text=?", ("avoir l'air",))][0]
  tr = [(bool(ok), ts) for ok, ts in c.execute(
        "SELECT is_correct, created_at FROM attempts WHERE word_id=? AND skill='transcribe'", (wid,))]
  print(tr, mastery.mastery_score(tr), mastery.mastery_color(mastery.mastery_score(tr)))
  ```
