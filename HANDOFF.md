# HANDOFF — 听写 (French dictation app)

> 给**接手的 AI agent**：读完这一个文件就能开工。不要重读全部代码、不要重新推导下面已写明的决策。
> 需要细节时按「文件地图」里的指引**只读那一个函数**。面向人类使用者的说明在 `README.md`。
> 最后更新：2026-06-11。

---

## 0. 开工前必做（30 秒）

```bash
cd "/Users/francis/Documents/法语/本地录屏课/听写"
python3 -m pytest -q          # 应 34 passed
pkill -f "streamlit run app.py"   # 杀掉用户机上缓存了旧模块的旧实例（见 §6 陷阱①）
./run.sh                      # = streamlit run app.py，开在 http://localhost:8501
```

**当前已知唯一「故障」**：用户报过 `AttributeError: module 'mastery' has no attribute 'skill_scores'`。
**这不是 bug**——代码是对的（`mastery.skill_scores` 存在、测试过）。原因是 Streamlit 热重载不重载被 import 的模块，旧实例缓存了旧 `mastery`。**全量重启即解**（上面的 pkill + run.sh）。

---

## 1. 这是什么

个人法语「听写/默写」练习 Web app。技术栈：**Streamlit 1.58 + SQLite + macOS `say`（TTS）**。纯本地、单用户、无登录。
词表来自用户法语课（`../L0..L19/vocab.json`）。目标：按模式矩阵多维度练一个词，并用渐变色显示掌握度。

---

## 2. 文件地图（一句话 + 何时去读）

| 文件 | 作用 | 何时去读 |
|---|---|---|
| `app.py` (~1264 行) | 唯一 Streamlit 入口：UI、状态机、各模式渲染、DB 读写 | 改 UI/模式/流程 |
| `vocab.py` | 解析/清洗词表（`parse_uploaded`、`parse_lesson_table`、`clean_lemma`、`derive_pos`） | 改词表导入/清洗 |
| `store.py` | SQLite 封装：`get_conn`、导入词、`get_attempts_for_words`(返回 `(ok,ts,skill)`)、轮次存档 | 改 DB 查询 |
| `mastery.py` | 掌握度算法：`mastery_score`(按天聚合+半衰期+Wilson)、`skill_scores`、`overall`(取最弱)、`mastery_color` | 改染色/掌握度 |
| `matcher.py` | 判对错：`check_fr`(重音严格)、`check_zh`(分层,返回 True/None)、`check_speech`(口述,容错) | 改判分规则 |
| `roundlogic.py` | 一批一批复习的推进逻辑：`next_action(index,total,batch)` → done/rest/go | 改批次/复习节奏 |
| `asr.py` | 念法语转写的**文件信道**：read/write/clear `/tmp/dictation_asr.json` | 改 ASR 对接 |
| `anki.py` | AnkiConnect **只读**取词卡释义/例句；`enrich()` 无把握返回 None | 改 Anki 集成 |
| `macdict.py` | macOS 词典服务取法语释义（French-only 启发式） | 改本地词典 |
| `manifest.py` | 每课 manifest 的校验/读取/抽取（checkpoints/vocab_items）| 改 manifest 格式 |
| `srs.py` | 间隔复习排期 `next_schedule`（词与知识点卡共用）| 改 SRS 间隔 |
| `scripts/coverage_report.py` | `<manifest.json>` → 覆盖报告（每 chunk→桶 + 缺口）| 清点某课覆盖 |
| `scripts/backfill_fem.py` | 给现有 `../L*/vocab.json` 回填 `fem`/`fem_raw`（一次性，已跑过）| 加新课/改重建规则后 |
| `scripts/run_asr_worker.sh` | **念法语 worker 一键启动**：自动用 .venv-qwen + 缺 sounddevice 就补装 | 用户启动 ASR |
| `scripts/asr_worker.py` | 后台麦克风→Qwen3-ASR→写转写文件。**别直接 `python3` 跑**（会缺 qwen_asr），用上面的 .sh | — |
| `scripts/asr_stub.py` | 不用麦克风、手动写一句转写，用于测念法语流程 | 测念法语 |
| `scripts/build_vocab.py` | 从 source TSV 批量生成 vocab.json（L17/L18 专用，新课用上传控件即可） | 罕见 |
| `tests/` | pytest，**34 个，全绿**。`app.py` 不被测（Streamlit 入口） | 每次改完跑 |

---

## 3. 现状（已验证 ✅ / 未验证 ⚠️）

- ✅ **5 个打字模式 + 一批一批复习 + 轮次存档**：可用。
- ✅ **三技能掌握度（形/义/音）**：每条 attempt 带 `skill`；掌握度分维度算；词「总掌握」= `overall` = 三维取最弱（没练的维度=0）。**左侧原生边栏**（`st.sidebar`，像 GPT/Claude 主页可折叠）里是 形/义/音 三色热力图 + 词整体色；词前 ▶=当前词、✅/❌=本轮结果。点词可在主区开卷看 Anki 卡。
  - 实时刷新：打字提交后 `_finalize` 会 `st.rerun()`（边栏在 `render_practice` 之前渲染，不重跑就慢一步）。掌握度颜色按「当天第一次」算，故同日重复练同词颜色不跳（防刷分设计），但 ✅/❌ 与当日首练词的颜色会实时变。
  - **预期副作用**：用户历史 attempts 全是「形」（旧记录 `skill=NULL` 视作 form）→ 义/音=0 → 每个词「总掌握」显示灰，**这是设计如此**（矩阵全练全高才算掌握），不是 bug。
- ✅ **防刷分**：`mastery_score` 按「当天第一次」聚合（先错后对刷答案=记当天那次错）；点「显示答案」=记错；首次作答才计分（`graded` flag，`goto` 时重置）。
- ✅ **判分**：打字法语重音严格（`épicier`≠`epicier`）；中文分层（精确→义项拆分→占位符骨架，拿不准返回 None 让用户自判）；口述容错（去重音/标点/冠词，Levenshtein≤len//6）。
- ✅ **学习/复习统一模型（无独立考试模式）**：选课（**会记住上次**，存 `setting:last_lesson`）→ 三个**按当前课作用域**的入口「开始这一课 / 错词(N) / 到期(N)」；做完/歇一下那屏有「再练一遍这一课 / 复习错词 / ↩︎回听刚才这一批」；主区顶部「📅今天 K 词到期复习」一键开练。遗忘曲线 = `words.due_at/interval_days`（答对延长间隔），就是「到期」。关键函数：`_lesson_ids`、`start_lesson_round`、`start_lesson_review(lesson,…,due_only)`、`start_review_round`（全局到期，banner 用）；`get_due_wrong_words(due_only, only_ids=<本课ids>)`；当前轮属于哪课存 `round_lesson`（在 `_ROUND_KEYS` 里、会持久化）。
- ✅ **软删除/隐藏词（不用背的，如地名）**：`words.hidden` 列（迁移加，默认 0）。练习时「🙈 这个词不用背」→ `set_word_hidden` 置 1 + 跳下一题；所有取词都排除 hidden（`get_all_words`、`_lesson_ids`、`get_due_wrong_words`、`get_stats` 都带 `hidden=0`）。侧栏「🙈 已隐藏的词(N)」可逐个「恢复」。
- ✅ **重新扫描词表按钮**：侧栏「🔄 重新扫描词表」= `load_vocab.clear()`+`load_checkpoints.clear()`+rerun，应对 out-of-band 加课（见 §6 陷阱⑥）。
- ✅ **知识点 checkpoint 复习 + lesson manifest**：每课一份 `../L*/manifest.json`（机器合同，每 chunk 强制归桶 vocab|drill|checkpoint|skip → 覆盖率可清点）。`manifest.py`(validate/load/checkpoints/vocab_items)、`srs.py`(next_schedule，词与卡共用的间隔 [1,2,4,7,15,30])、`scripts/coverage_report.py`、`scripts/build_checkpoints_from_species.py`。8501 侧栏「📝 知识点(N)」→ `render_checkpoint`：有 answer 机判(check_fr)、无则揭示背面自评；SRS 状态存 DB `checkpoints` 表(card_id 主键)，复用 `srs.next_schedule`。**checkpoint 是独立流程**：`cp_active/cp_cards/cp_index/cp_show_back/cp_feedback`，**绝不碰** `pool/current_word/render_practice`（主区 `if cp_active: render_checkpoint() else: …`）。L21 已升级为正式 species deck：94 vocab + **73 张 reviewed species checkpoint 卡**，`coverage.expected_species_count=73`，`coverage_report.py` 显示 `species 覆盖: 73/73`。**卡片精修**走 `../L21/L21.card_overrides.json`（按 `species_label` 覆盖 front/back/answer），`build_checkpoints_from_species.py --overrides` 合并；卡 `id` 稳定 → 重建不丢精修也不丢 SRS 进度。**已精修 22 张：18 机判（answer→check_fr 填空）+ 4 自评（中文讲解）**，其余 51 张仍是通用自评模板（待续精修）。`drill` 桶留位未实现；`record_attempt` 暂未改用 srs（DRY 重构故意推迟，行为不变）。设计/计划见 `docs/specs|plans/2026-06-17-*`、`docs/MEMO-2026-06-17-*`。
- ✅ **阴阳性「变形」维度（morph/变）**：第 4 个掌握维度。词条带 `fem`/`fem_raw`（解析时由 `vocab.feminine_form` 从 `court, e`/`occidental, occidentale` 重建；`scripts/backfill_fem.py` 已回填 L17–L20）。新模式「看阳性 → 写阴性」+ 侧栏「变形(N)」入口（只练有阴性的词，自动切模式）。词表第 4 列「变」，无阴性的词该格留灰且不计入「总掌握」。`mastery.overall(scores, skills=…)` 默认仍只看 形/义/音，`render_word_panel` 对有 fem 的词才加 `morph`。设计/计划见 `docs/specs/` 与 `docs/plans/` 的 2026-06-15 两份。
- ⚠️ **念法语 ASR**：文件信道（worker 写 `/tmp/dictation_asr.json`，app 轮询读）。手动+自动模式逻辑通、可用桩测；**真转写需用户启动 `./scripts/run_asr_worker.sh`**（首次下载 Qwen3-ASR-1.7B 几 GB + 给麦克风权限）。
- ⚠️ **v2 念法语自动模式**（opt-in 勾选框）：`st.fragment(run_every=0.6)` 轮询→收到就自动判→对了倒计时~1.3s 自动下一题→自动备妥下一词。`st.fragment`/`st.rerun(scope=)` API 确认可用、编译/boot 干净，但**实时手感无法 headless 测**，需用户机或桩验证、可能要调（间隔、倒计时时长）。

---

## 4. 待办（backlog）—— 注意**归属**

| # | 事项 | 归属 | 备注 |
|---|---|---|---|
| 0 | ✅ **#8 多字段录入体验**（已做）| — | ①`wire_form_enter_submit` 改成通用：回车非最后一个框→跳下一个框（法语→中文），最后一个框→提交（JS 改动，**真浏览器里待用户确认手感**）；②`render_answer_table` 渲染 2×2 无边框对照表（你敲的/标准答案 × 法语/中文，✅❌❔），用在判定屏和最终反馈（≥2 字段时）。AppTest 已验渲染不挂 |
| 1 | 启动 `./scripts/run_asr_worker.sh` 实测调参 | **只能用户**（他的麦克风/模型） | 脚本会自动补 sounddevice；改 `SILENCE_RMS`/`SILENCE_HOLD` 现场调 |
| 2 | v2 自动模式实时手感调优 | agent+用户 | 等 #1 通了再调；或先用 `scripts/asr_stub.py` 测推进逻辑 |
| 3 | L21 species deck 精修 | agent | 73/73 可复习；**已精修 22 张**(18 机判+4 中文自评，见 `L21.card_overrides.json`)；**剩 51 张**仍通用自评模板，可继续往 overrides 里加（高频语法/介词/冠词优先做成机判） |
| 4 | 用户反馈后微调 | agent | 等用户用过：打字模式 / 左侧边栏视觉 / 形义音热力图 / 防刷分 / 自动模式 / 知识点卡 |
| — | (搁置) anki-wordsmith `or`/`enfin` 校验器误报 | — | 用户说「以后再说」 |
| — | (搁置) 色板 HSL 化 | — | 当前灰→黄→绿 RGB 线性插值够用 |

**agent 可独立推进的纯编码项基本见底**——剩下要么是用户机上跑 worker(#1)，要么是等用户反馈(#3)。
接手时若用户没给新需求，先确认 §0 跑通、再问他要 #1 的 worker 结果或 #3 的反馈，**不要盲目造新功能**。

---

## 5. 关键决策 / 数据约定（别推翻、别重推导）

- **模式矩阵** `MODES`（app.py:30）：`名称 → (prompt_type, answer_fields, skill)`。
  - prompt_type ∈ {fr_audio, zh_audio, zh_text, fr_text}；answer ∈ {("fr",),("zh",),("fr","zh"),("speak_fr",)}；skill ∈ {form, meaning, pron, both}。
  - `both`（听法语→敲法语+中文）一次记 form+meaning 两条 attempt。
  - **哪个模式练哪个技能**：form←听写类3个；meaning←敲中文；pron←念法语3个。要让一个词变绿，三类都得练。
- **DB 迁移**：在 `init_db`（app.py 顶部）用 `ALTER TABLE ... ADD COLUMN` + `try/except sqlite3.OperationalError` 幂等加列。`attempts.skill` 就是这么加的。**新加列照此办**，不要建迁移框架。
- **掌握度**：`mastery_score` = 按天取当天第一次 → 半衰期(14天)加权 → Wilson 下界(Z=1.28)。`overall`=min(form,meaning,pron)。颜色：0灰`#e6e6e6`→中黄`#ffd54f`→1绿`#66bb6a`。
- **判分返回值约定**：`check_zh`/`check_speech` 返回 `True`(对)/`None`(拿不准→让用户自判)，**从不返回 False**（错也走自判，避免误杀近义/口音）。`check_fr` 返回 bool。
- **语音名**：法语 `Thomas`、中文 `Tingting`（**不是** `Ting-Ting`，写错会静默退回英文）。常量在 app.py 顶部（`ZH_VOICE`）。
- **vocab.json 生产**：日常用 app 侧栏「➕ 添加/自定义词表」上传 TSV/CSV（走 `vocab.parse_uploaded` 自动清洗）。不要让 agent 手抄格式（清洗规则易错）。详见 README。
- **Anki 只读**：`anki.py` 经 AnkiConnect(localhost:8765) 读「Français」牌组；`enrich()` 匹配不确定时**返回 None**（曾因 fallback `infos[0]` 返回错词卡，已删）。
- **念法语状态机**（`render_speak`，app.py ~838）：idle→armed→(judge)→done。armed 时读 `asr.read_latest()` 且要求 `ts > armed_at`（防读到上一句的旧转写）。

---

## 6. 陷阱（踩过的坑，别再踩）

1. **改了被 import 的模块（mastery/store/matcher/...）必须全量重启**，点页面「Rerun」不会重载它们 → 会看到「旧函数不存在」之类 AttributeError。`pkill -f "streamlit run app.py"` 再 `./run.sh`。
2. **改完务必 `python3 -m pytest -q`**（34 绿）+ boot 自检；`app.py` 无单测，靠 boot 抓 import/语法。boot 自检模板见下。
3. **`say` 语音名拼错会静默失败**（退回英文且不报错）。改语音先 `say -v '?'` 核对。
4. **ASR 转写文件有时效**：永远用 `ts > armed_at` 过滤，否则会把上一题/陈旧转写当本题答案。
6. **`load_vocab` 是 `@st.cache_data`，加了新课/改了 vocab.json 不会自动出现**：UI 上传那条会 `load_vocab.clear()`，但 build_vocab.py、手动建文件、别的 session 加的课，当前进程看不到，直到点侧栏「🔄 重新扫描词表」或重启。（曾因此 L20 在盘上却不显示。）
7. **不能在 widget 实例化后改它的 `st.session_state[key]`**（会抛 StreamlitAPIException）。「变形」入口要切 `mode` selectbox 的值，故存 `pending_mode`，在 selectbox **创建前**（app.py 模式 selectbox 上一行）才 `st.session_state["mode"]=pop("pending_mode")`。同类需求照此办。
5. **这台机器的 shell 开了 `set -e`**（来自用户 profile）：脚本里**任何**命令返回非零都会**整条中止**。`grep` 无匹配返回 1（`grep -c` 打印 0 但**仍返回 1**），会把后面的命令全砍掉。**对策**：多行脚本开头加 `set +e`，或给可能失败的命令补 `|| true`。

**boot 自检模板**（改完 app.py 验证用，免占端口）：
```bash
streamlit run app.py --server.headless true --server.port 8599 >/tmp/st.log 2>&1 &
PID=$!; curl --retry 25 --retry-delay 1 --retry-connrefused -s -o /dev/null -w "health %{http_code}\n" localhost:8599/_stcore/health
grep -icE 'error|traceback|exception' /tmp/st.log; kill $PID 2>/dev/null
```

---

## 7. 数据现状（参考）

- `dictation.db`：words 195、attempts 841（绝大多数 skill=NULL→视作 form）。
- 课表：`../L0..L19/vocab.json`；用户已能自助加课（L19 是新加的）。
- 历史研究记录在本地 mem（claude-mem）：anki-wordsmith 制卡、批次诊断等，按需用 mem-search，不必重查。
