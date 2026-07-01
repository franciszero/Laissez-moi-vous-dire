# 设计：Anki «Core Meaning» 答后内联富化

最后更新：2026-06-25。状态：**设计已批准，待出实施计划**。
背景：背单词答完/看答案时，高质量的 Anki «Core Meaning» 目前**只**埋在 820px「📇 完整 Anki 卡片」整卡 iframe 里，没单独露出。把它在「释义」之后内联呈现，作为**答后理解富化**。配套：feature 验证（cue vs 富化的取舍）见对话记录与 `HANDOFF.md`。

## 0. 一句话
在 `render_learn_panel` 的「释义」下方加一行小字「🧠 核心义：…」，取自 `anki.enrich().core_meaning`（已抽好的字段），缓存调用；**不当 cue、不碰判分**。

## 1. 已定（brainstorm 结论）
- **当富化不当 cue**：听写/看中文的 cue 仍是 `word_zh`（vocab.zh）。理由：core_meaning 是**整句定义**（`pain`→「一种用面粉烘焙成的主食块状食品」）不是 gloss，做 cue 啰嗦/有歧义/读不出，且约半数为 `N/A`。
- **放哪/形态**：「释义：{zh}」**下方**、整卡 expander **之前**，`st.caption` 小字一行。
- **缺失呈现（writing-plans 收敛）**：富化**只在 `ok` 时**加核心义行。`stub` 靠 `render_learn_panel` 现有提示「⚠️ Anki 卡…待重新生成」（[app.py:290](app.py:290)），不重复；`missing` 静默。（原定 stub→「暂无」，核到现有 UI 已覆盖，故去掉。）
- **逻辑放 `anki.py`**：取值判断抽成纯函数 `core_meaning_text(enrich_result)`（可 `test_anki.py` 单元测、不碰 Streamlit/缓存）；`app.py` 只留缓存包装 + `st.caption`。
- **取数**：新增 `enrich_cached`（`@st.cache_data`），与现有 `card_state_cached`/`macdict_cached` 同款，避免每次 rerun 打 Anki。

## 2. 改动

### 2a. `anki.py` — 纯逻辑函数（可单元测，无 Streamlit）
```python
def core_meaning_text(enrich_result) -> str | None:
    """从 enrich() 结果取可显示的 core_meaning；None / 空 / "N/A" → None。"""
    cm = (enrich_result or {}).get("core_meaning", "")
    return cm if cm and cm.upper() != "N/A" else None
```

### 2b. `app.py` — 缓存包装（紧挨 `card_state_cached` [app.py:258](app.py:258)，同款 pattern）
```python
@st.cache_data(show_spinner=False)
def enrich_cached(lemma: str):
    return anki_mod.enrich(lemma)
```

### 2c. `app.py` — `render_learn_panel`（[app.py:274](app.py:274)）只在 `ok` 分支插一行
在 `if state["status"] == "ok":` 内、`with st.expander("📇 完整 Anki 卡片", expanded=True):` **之前**插入：
```python
        cm = anki_mod.core_meaning_text(enrich_cached(lemma))
        if cm:
            st.caption(f"🧠 核心义：{cm}")
```
`stub` / `missing` 分支不动（stub 现有行 290 已有「待重新生成」提示；missing 静默）。

## 3. 不做
- 不当 cue、不改判分、不改 `word_zh`、不改 `MODES`。
- 不区分 `missing` 的子情况（Anki 没开 vs 没笔记）——都静默。
- 不动 R0/R3 / 词流程 / DB。

## 4. 测试
- **`tests/test_anki.py` 单元测 `core_meaning_text`**（纯、稳、无缓存）：`{"core_meaning":"…"}`→原文；`None`/`{}`/`{"core_meaning":""}`→`None`；`"N/A"`/`"n/a"`→`None`。
- **boot 自检**：改完 `render_learn_panel` 后 `streamlit run` health 200、0 error，确认 wire 不崩。
- （纯函数已覆盖三态取值逻辑；`render_learn_panel` 内仅 `if cm: st.caption` 两行 trivial wire，故不再写走答后态的 AppTest——绕开 `@st.cache_data` 串味且更稳。）

## 5. 验收
- 上述 4 个 UI 断言通过；cue/判分零变化；全套绿（≥105 passed）。
- 范围干净：仅 app.py（两处）+ 测试文件；不碰 R0/R3、词流程、DB。
- 走审核门后再合并。
