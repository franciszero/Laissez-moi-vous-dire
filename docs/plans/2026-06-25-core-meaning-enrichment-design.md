# 设计：Anki «Core Meaning» 答后内联富化

最后更新：2026-06-25。状态：**设计已批准，待出实施计划**。
背景：背单词答完/看答案时，高质量的 Anki «Core Meaning» 目前**只**埋在 820px「📇 完整 Anki 卡片」整卡 iframe 里，没单独露出。把它在「释义」之后内联呈现，作为**答后理解富化**。配套：feature 验证（cue vs 富化的取舍）见对话记录与 `HANDOFF.md`。

## 0. 一句话
在 `render_learn_panel` 的「释义」下方加一行小字「🧠 核心义：…」，取自 `anki.enrich().core_meaning`（已抽好的字段），缓存调用；**不当 cue、不碰判分**。

## 1. 已定（brainstorm 结论）
- **当富化不当 cue**：听写/看中文的 cue 仍是 `word_zh`（vocab.zh）。理由：core_meaning 是**整句定义**（`pain`→「一种用面粉烘焙成的主食块状食品」）不是 gloss，做 cue 啰嗦/有歧义/读不出，且约半数为 `N/A`。
- **放哪/形态**：「释义：{zh}」**下方**、整卡 expander **之前**，`st.caption` 小字一行。
- **缺失呈现**：`stub`（有笔记、字段未生成）→ 显示「暂无（待重新生成）」；`missing`（没笔记 / Anki 没开）→ **静默**。理由：Anki 整个没开时不该满屏「暂无」；提示聚焦在真·残卡（= 你想标记的"待生成卡"）。
- **取数**：新增 `enrich_cached`（`@st.cache_data`），与现有 `card_state_cached`/`macdict_cached` 同款，避免每次 rerun 打 Anki。

## 2. 改动（两处，均在 app.py）

### 2a. 新增缓存包装（紧挨 `card_state_cached` [app.py:258](app.py:258)）
```python
@st.cache_data(show_spinner=False)
def enrich_cached(lemma: str):
    return anki_mod.enrich(lemma)
```

### 2b. `render_learn_panel`（[app.py:274](app.py:274)）插一段
现状：
```python
    zh = word_zh(lemma)
    if zh:
        st.markdown(f"**释义**：{zh}")
    state = card_state_cached(lemma)
    if state["status"] == "ok":
        with st.expander("📇 完整 Anki 卡片", expanded=True):
            ...
```
在 `state = card_state_cached(lemma)` 之后、`if state["status"] == "ok":`（开整卡 expander）之前插入：
```python
    if state["status"] == "ok":
        cm = (enrich_cached(lemma) or {}).get("core_meaning", "")
        if cm and cm.upper() != "N/A":
            st.caption(f"🧠 核心义：{cm}")
    elif state["status"] == "stub":
        st.caption("🧠 核心义：暂无（Anki 卡待重新生成）")
    # status == "missing" → 静默
```
（整卡 expander 那段保持不变，紧随其后。）

## 3. 不做
- 不当 cue、不改判分、不改 `word_zh`、不改 `MODES`。
- 不区分 `missing` 的子情况（Anki 没开 vs 没笔记）——都静默。
- 不动 R0/R3 / 词流程 / DB。

## 4. 测试（AppTest，新文件或并入既有 UI 测试）
进入一个词的"答后/显示答案"态，monkeypatch `enrich_cached`（或 `anki_mod.enrich`）+ `card_state_cached` 注入三态：
- **ok + 有 core_meaning** → 出现「🧠 核心义：…」caption。
- **ok + core_meaning == "N/A"/空** → 不出现核心义行（但整卡 expander 在）。
- **stub** → 出现「🧠 核心义：暂无（Anki 卡待重新生成）」。
- **missing** → 不出现核心义行。
- **cue 不变**：`word_zh` / 听写提示不受影响。

## 5. 验收
- 上述 4 个 UI 断言通过；cue/判分零变化；全套绿（≥105 passed）。
- 范围干净：仅 app.py（两处）+ 测试文件；不碰 R0/R3、词流程、DB。
- 走审核门后再合并。
