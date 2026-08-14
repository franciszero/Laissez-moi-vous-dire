# 速过视图设计（⚡ 扫读 / 「认」技能）

日期：2026-08-13
状态：设计已定，待实现
影响：`app.py`（新增一个 overlay 视图）、`store.py`、`mastery.py`、新增 `scan.py` / `scanaudio.py`

---

## 1. 要解决的问题

一节课现在 150+ 个词（L36 是 164 条）。现有的词练习是**逐词**流程：读题 → 敲 → 回车 →
rerun → 看判分 → 点「下一题」→ rerun。一个词至少两次前后端往返，把「听法语→敲法语」
「看中文→敲法语」「听法语→敲中文」三个方向各过一遍，就是 **450 次 rerun**。
即使每次只花 4 秒，光是等待就一个多小时。

用户要的是纸质词表的背法：一页词摊开，用手盖住一列，眼睛顺着往下扫，想不起来的
挪开手看一眼，扫完再回头收拾没记住的那几个。三种盖法：

- 盖中文（看法语，回想中文）
- 盖法语（看中文，回想法语）
- 都盖住（只听发音，回想法语拼写和中文）

这套动作的本质是**交互的原子单位从「一个词」变成「一页词」**，判定从「机器判拼写」
变成「自己心里判」。一页 20 行、扫完提交一次，150 词从 450 次往返降到 8 次。

## 2. 非目标

- **不替代现有的打字/念法语练习。** 扫读没有拼写证据，它只回答「认不认得」，
  不回答「写不写得出」。`check_fr` 的零容错口径（见 `docs/BACKLOG.md` 第 3 条）
  一个字都不动。
- **不引入 SRS 到期调度。** 扫读是「整课过一遍」，不需要挑到期的词。
- **不做跨课的「认」总榜。** 课自己拥有自己的词（HANDOFF §5），扫读也按课走。
- **不碰知识点卡。** 本设计只针对词表。知识点卡的三块式结构保持原样。

## 3. 交互形态

### 3.1 入口

侧栏「学习」区，和「错词」「变形」「📝 知识点」同层，新增：

```
⚡ 速过（164）
```

进入方式与既有 overlay 完全同构：`_leave_overlays()` 先关掉别的覆盖层，再置
`st.session_state.scan_active = True`。`_leave_overlays()` 里补一行
`st.session_state.pop("scan_active", None)`，让三个 overlay（知识点 / 写作 / 速过）
互斥的规则只有一处。

速过**不碰** `pool` / `index` / `current_word` / `at_rest` / `round_results` ——
它有自己的一套 `scan_*` 状态，和逐词状态机零共享。

### 3.2 页面结构

```
方向： [看法→想中] [看中→想法] [听音→想双]        揭法： [点行] [悬停] [整页]
────────────────────────────────────────────────────────
 #   ▶     法语                 中文（盖住）        不会
 1   ▶     la confiture         ████████            ☐
 2   ▶     s'installer          ████████            ☐
 …
20   ▶     se plaindre          ████████            ☐
────────────────────────────────────────────────────────
第 1/9 页 · 已标 3 个不会          [揭晓这一页]  [记下这一页 ▶]
```

三个方向决定哪些格子被盖，也决定 ▶ 摆在哪：

| 方向 | 明码列 | 盖住列 | ▶ 的位置 |
|---|---|---|---|
| 看法→想中 (`rec_meaning`) | 法语 | 中文 | 常驻可点（听发音不算泄题，法语本来就明摆着） |
| 看中→想法 (`rec_produce`) | 中文 | 法语 | **归进盖住区**，揭开后才能点——否则一听就等于给了答案 |
| 听音→想双 (`rec_audio`) | 无 | 法语 + 中文 | 常驻可点，它就是唯一的题面 |

三种揭法都做，用户随时切：

- **点行显形**：点一格永久显形。最接近手拿纸往下挪——已经对过的行一直开着，
  没对的还盖着，一眼看得出扫到哪了。触屏也能用。
- **悬停显形**：鼠标扫过就显，移开又盖上。最快，但回头看分不出哪些行对过。
- **整页一次揭晓**：先在心里把一整页过完，按一次「揭晓这一页」全开。自欺最少。

选择用 `save_setting("scan_reveal", ...)` 持久化，下次进来还是上次那个（和
`last_lesson` 同一个机制）。方向同样持久化为 `scan_direction`。

### 3.3 页大小

新设置 `scan_page_size`，默认 20，可调 5–200。调到 ≥ 本课词数就等于不分页，
一整张表滚着看——那是最像纸的形态，代价是音频一次性加载全课、且中途没有存档点。
默认给 20 是折中：一屏放得下，扫完有个自然的落点。

### 3.4 逐词播放

每行一个 ▶，点它就出声，想听几遍听几遍，顺序随意。这是**纯浏览器行为**
（内嵌 `<audio>` + 一个 click handler），Streamlit 完全不参与，不产生 rerun。

另有一个「串播这一页」按钮，把整页按固定间隔连着播一遍，模拟老师听写的节奏。
它是可选的附加形态，不是主路径。间隔用 macOS `say` 的 `[[slnc <ms>]]` 内嵌命令
一次合成，不需要轮询（实测可用）。

## 4. 数据模型：零 schema 变更

这是本设计最要紧的一节。

### 4.1 「认」不能走 `record_attempt`

`app.py:827` 的 `record_attempt()` 做两件事：往 `attempts` 插一行，**并且**更新
`words` 表那一行的 `correct_streak` / `interval_days` / `due_at` / `wrong_count`。
`words` 的 SRS 状态是**每个词一份、所有技能共用**的。所以只要扫读调用它，无证据的
自判就会重置打字练出来的 streak、改掉到期日。

另一条同样致命：`mastery.mastery_score()` 按天聚合时取**当天第一次**为准
（`if cur is None or dt < cur[1]`）。早上扫读手滑漏一个词，这一整天就被钉成错，
晚上打字打对了也救不回来。

结论：**扫读结果写 `attempts`，但绝不 UPDATE `words`。**

### 4.2 新的 skill 值

`attempts.skill` 是自由文本列，新增三个值即可，**不需要任何 migration**：

```
rec_meaning   看法语，回想中文
rec_produce   看中文，回想法语
rec_audio     只听发音，回想双向
```

隔离是自动成立的：`mastery.skill_scores()` 第一步就是按 skill 分组，所以
`rec_*` 和 `transcribe / produce / meaning / pron / morph` 的历史互不可见，
「当天第一次为准」也各算各的。

`mastery.overall()` 默认只看 `BASE_SKILLS`，`rec_*` 不在其中 → 扫读不会把
「词」列的总掌握度拉高或拉低。这正是要的。

`init_db()` 里那条 `UPDATE attempts SET skill='transcribe' WHERE skill='form' OR skill IS NULL`
只动 `form`/NULL，对新值无害，不用改。

### 4.3 写入函数放哪

`docs/BACKLOG.md` 第 7 条：测试里禁止裸 `import app`（import 即执行整个 Streamlit
脚本）。所以要单测的东西必须在 `app.py` 之外。

`record_scan_attempt()` 放 `store.py`——那里已经有 `get_conn()`、
`get_attempts_for_words()`、`save_checkpoint_attempt()`，是本仓库放「可测的 DB 写入」
的既有位置，也已经有 `tests/test_store.py`。

```python
def record_scan_attempt(word_id: int, skill: str, ok: bool) -> None:
    """扫读自判：只写 attempts，不碰 words 的 SRS 状态。

    words.correct_streak / due_at / wrong_count 由 app.record_attempt 独占，
    那是有拼写证据的技能才有资格改的东西。
    """
```

`answer` 列写固定串 `"（扫读·会）"` / `"（扫读·不会）"`，这样
「查看这个词的最近记录」里一眼能认出哪几条是扫来的。

### 4.4 掌握度 UI

`render_word_panel()`（`app.py:1947`，色值映射在 2005–2012）现在有 词/听/产/义/音/变
六个色列。加第七列
「认」：

```python
"认": mastery_mod.mastery_color(
    mastery_mod.overall(sc, skills=("rec_meaning", "rec_produce", "rec_audio"))
),
```

取三个方向里最弱的，和「词」列用同一个 `overall()`，语义一致：**没扫过的方向算 0**。
所以只扫过一个方向时「认」是灰的——这和现有「没练的算 0」完全一致，不是 bug。

`render_word_panel` 那段 caption 一并补上「认」的解释。

## 5. 模块划分

对标 `roundlogic.py` / `mastery.py` / `srs.py` 的做法：**纯逻辑抽出去，Streamlit 只做编排。**

### `scan.py`（新，无 Streamlit 依赖）

```python
DIRECTIONS = {                      # 方向 → (skill, 明码字段, 盖住字段, ▶是否归盖住区)
    "看法→想中": ("rec_meaning", "fr", "zh", False),
    "看中→想法": ("rec_produce", "zh", "fr", True),
    "听音→想双": ("rec_audio", None, "fr+zh", False),
}

def paginate(word_ids, page_size) -> list[list[int]]
def page_rows(word_ids, vocab) -> list[dict]      # 一页的行模型：序号/lemma/zh
def commit(rows, missed_indices) -> list[tuple]   # → [(word_id, ok), ...]
```

`commit()` 是纯函数：给它一页的行和「用户勾了哪几个序号」，返回要写的
`(word_id, ok)` 列表。没勾的算会。这是最值得单测的一块。

### `scanaudio.py`（新，无 Streamlit 依赖）

```python
def cache_path(lemma, voice) -> Path
def ensure(lemma, voice) -> Path        # 缺就用 say 生成
def warm(lemmas, voice) -> None         # 后台线程批量预热
```

生成命令（实测：0.78 秒一个词，37KB，浏览器可播的 AAC）：

```bash
say -v Thomas "la confiture" -o <path>.m4a --file-format=m4af --data-format=aac
```

缓存键是 `lemma + voice`（lemma 先过一层文件名安全化），文件直接落在
`static/audio/`——就是下面静态服务要用的那个目录，不额外建一层再软链。
`static/` 加进 `.gitignore`。跨课复用：`la province` 在 L33 生成过，L36 直接拿。
整课首次约 2 分钟，之后零等待。

**预热策略**：进「速过」时起一个后台线程生成整课，当前页排在队首。页面上显示
「音频准备中 34/164」，没生成好的行 ▶ 置灰，其余照常可扫——扫读不依赖音频，
只有「听音→想双」这一档才必须等。

**文件怎么送到浏览器**：优先走 Streamlit 静态服务——`.streamlit/config.toml` 加

```toml
[server]
enableStaticServing = true
```

页面里用 `<audio src="/app/static/audio/xxx.m4a">`，页面本身很轻。
退路是 base64 data URI 内联（20 词约 740KB，能用但不优雅）。

### `app.py` 里的 `render_scan_view()`

只做编排，对标 `render_checkpoint()` / `render_writing_view()`：
读 session state → 调 `scan.py` 算出这一页 → 渲染 → 收提交 → 调
`store.record_scan_attempt()`。

## 6. 零 rerun 是怎么做到的

三层，全部是这个仓库已经在用的手法：

1. **表格本身**：`st.markdown(..., unsafe_allow_html=True)` 渲染带内联样式的
   HTML 表——`render_answer_table()`（`app.py:1623`）和 `_checkpoint_answer_html()`
   已经是这个模式。
2. **盖/揭 与 ▶**：`components.html(<script>, height=0)` 注入脚本，通过
   `window.parent.document` 给表格挂 handler。`focus_answer_input()`（`app.py:496`）
   和 `wire_form_enter_submit()`（`app.py:524`）已经在这么干，是本仓库的成熟套路。
3. **批量提交**：整个表包在 `st.form` 里。form 内的 widget 改动不触发 rerun，
   只有 `st.form_submit_button` 触发一次。`answer_form` / `morph_form` 已是这个模式。

### 6.1 唯一的技术风险，以及退路

「行内直接勾 ☐不会」要求把纯 HTML 的勾选状态送回 Python。计划是：form 里放一个
隐藏的 `st.text_input`，JS 把勾中的序号同步成 `"3,7,12"` 写进去，用户点真正的
`st.form_submit_button` 提交。

写 React 受控组件的值必须用 native setter + 派发 `input` 事件，这是标准做法但
依赖 Streamlit 内部实现。**实现时第一件事就是把这条打通并写一个回归测试**，
不要先建整个视图。

打不通就退到**方案 B**：表格照旧（HTML，带 ▶ 和三种揭法），勾选改用表格下方的
`st.pills(..., selection_mode="multi")` 列出 1–20 的序号，点你漏掉的那几个。
原生组件，零 JS 风险，代价是眼睛要从行挪到序号条。功能完整，只是没那么顺手。

方案 B 是**保底可交付形态**，不是失败。

## 7. 与慢流程的接口

这是用户明确要的：「认」是第一遍粗筛，跑完要能顺势喂给现有的慢流程。

**每页提交后**，页脚出现：

```
这一页漏了 7 个 → [用「看中文 → 敲法语」把这 7 个练一遍]
```

模式名取侧栏当前选的那个。点它就 `_leave_overlays()` + 用这 7 个 word_id 起一轮
——复用 `reset_round(word_ids, batch_size)`（`app.py:1002`），不需要新的轮次机制。
练完回到常规的轮次结束页，速过的分页进度存在 session state 里，可以再进去接着扫。

**整课扫完**，给一次全课汇总的同款按钮，外加「只扫漏掉的那些再来一遍」——
后者不写库，纯粹是再过一遍眼。

注意：漏词清单来自本次扫读的 session state，**不是**从 `get_due_wrong_words()` 取的。
错词表读 `words.wrong_count`，而扫读根本不写 `words`（§4.1），所以两者天然分开：
错词表仍然只装「有拼写证据的失败」。

## 8. 错误处理与降级

| 情况 | 行为 |
|---|---|
| `say` 不可用 / 生成失败 | ▶ 置灰并带 title 说明；看法/看中两档照常可用；「听音→想双」入口禁用并说明原因 |
| 音频还没预热完 | 该行 ▶ 置灰，页面顶部显示进度；不阻塞扫读 |
| 某词没有中文释义 | 中文格显示 `（无释义）`，仍可标「不会」 |
| 本课词数为 0 | 入口按钮 disabled，和「错词（0）」「变形（0）」一致 |
| 提交时 word_id 不在库 | 照插不误。`record_attempt` 是先插 `attempts` 再查 `words`，不存在的 id 同样会留下一条记录——扫读保持一致行为，不另立规矩 |
| 隐藏词（`hidden=1`） | 不进扫读池，和其他练习一致 |

## 9. 测试

按本仓库规矩：**测用户行为和应用不变量，不测实现细节**。全部避开裸 `import app`。

`tests/test_scan.py`（纯逻辑）
- `paginate` 的边界：0 词、1 词、正好整除、page_size 大于总数
- `commit`：没勾的算会、勾了的算不会、序号越界不炸

`tests/test_scan_audio.py`
- `cache_path` 对同一 lemma+voice 稳定，对不同 voice 不同
- `ensure` 命中缓存时不调 `say`（mock subprocess 断言调用次数为 0）
- `say` 失败时抛出可识别的异常而不是留下半个空文件

`tests/test_store.py`（补充）— **最关键的一组**
- `record_scan_attempt` 写进 `attempts` 且 `skill` 正确
- `record_scan_attempt` 之后，该词 `words` 行的 `correct_streak` / `due_at` /
  `wrong_count` / `interval_days` **一个字节都没变**
- 扫读记了错之后，该词**不出现在** `get_due_wrong_words()` 里
- `skill_scores` 能把 `rec_*` 和 `transcribe` 分开算

`tests/test_scan_ui.py`（`AppTest.from_file("app.py")`）
- 侧栏有「⚡ 速过」入口，数字等于本课词数
- 点进去之后 `pool` / `current_word` 没被改动
- 速过打开时，知识点/写作 overlay 被关掉（`_leave_overlays` 的不变量）
- 方向和揭法的选择经 `save_setting` 持久化

`tests/test_mode_exclusion.py`（既有文件，补充）— 速过加入 overlay 互斥矩阵。

## 10. 遵循的既有约定

明确记下来，免得后来人当成新发现重改：

- **既有模式优先**：HTML 表走 `render_answer_table` 的路子；注入 JS 走
  `focus_answer_input` 的路子；批量提交走 `st.form` 的路子；overlay 走
  `cp_active` / `writing_active` 的路子；轮次复用 `reset_round`。没有一处是新架构。
- **不做假表格、不堆按钮墙**（AGENTS.md 的既有模式闸门）：一行一个 `st.button`
  是明令禁止的形态，本设计一个都没有。
- **不给 `check_fr` 加容错**（BACKLOG #3）：扫读根本不判拼写，绕开这个争议。
- **课拥有自己的词**（HANDOFF §5）：不建跨课的「认」注册表。
- **撇号只在匹配时归一化**（`matcher.norm_fr`）：扫读只显示不匹配，不涉及。

## 11. 未决

- 「认」色列取三方向最弱，意味着只扫过一个方向时永远是灰的。语义上和现有
  「没练的算 0」一致，但用起来可能显得没反馈。**先按一致的口径做，用几天再定**
  要不要改成「只算扫过的方向」。
- 串播这一页的默认间隔（`[[slnc ?]]`）取多少，等实际听过再定，先给 3000ms 并可调。
- 页大小默认 20 是估的，不是实测的。用户自己调出舒服的值之后，把那个值写回默认。
