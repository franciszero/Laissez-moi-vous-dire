# 搁置项与产品反馈

**给 agent**：动这个仓库之前先读这份。里面全是**已经确认存在、但当时决定不做**的问题——
不是猜想，每条都附了复现方式或实测数字。看到相关代码时先查这里，别当成新发现重新调研一遍，
也别顺手"修"掉一个其实是刻意保留的行为。

改完某条就从这里删掉，并在提交说明里写清楚。新增条目要带**证据**（命令、数字、文件行号），
只写"感觉不好"的条目会被后来人忽略。

最后更新：2026-08-13

---

## 1. ~~导航方向反了~~ ✅ 已完成 2026-08-07

写作已经是独立入口：不选课也能列出全库的题，下拉标出每道题属于哪一课，
当前选课的题排前面。`scope` 也认了（原第 2 条一并解决）——两件事同一个根：
内容层把 lesson 当成了找文件的路径，`_load_all()` 改成 glob 全库之后都通了。

**留下的**：背单词那边只欠「从搜到的某个词直接开练」，是加个按钮的量，
不是架构问题（`"全部"` 入口一直能用，一词多课数据层也一直支持）。

---

## 2. 组装线有三格是空的，两条素材只在「详解」里可见

**状态**：已确认，等用户体验后决定。

`writing_skeletons.json` 的 `tache_2` 有 7 步，但 L34-W2 的素材只填了 4 步：

```
pick_scenario   0 条        use_template   0 条        final_check   0 条
```

而 `L34-W2-traps`（本题最容易错的几处）和 `L34-W2-length`（字数分配与增删顺序）
因为没标 `function`，在「组装线」视图里根本不出现，只能切到「详解」才看得到。

`traps` 尤其别扭——「最容易错的几处」正是交卷前要扫的东西，而骨架里 `final_check`
那格空着，两边正好能对上。

**改法**：给 `traps` 标 `function: "final_check"`、`length` 标 `function: "use_template"`。
改的是数据不是代码。但「交卷前检查」那格该放什么，用户自己写作时才知道顺不顺手，
所以没有自作主张。

---

## 3. 敲法语和念法语是两套相反的判分口径

**状态**：已确认，用户决定**保持现状**（TCF 写作确实扣重音）。记录以备将来改主意。

同一个字符串 `la securité`（漏重音）：

| 判分函数 | 用在 | 返回 | 容错 | 有申诉吗 |
|---|---|---|---|---|
| `check_fr` | 敲法语 | 硬 `bool` | 零容错、重音严格 | ❌ 没有 |
| `check_zh` | 敲中文 | `True/None` | 义项切分、占位符骨架 | ✅ 算我对/算我错 |
| `check_speech` | 念法语 | `True/None` | 去重音 + 编辑距离 + 可省冠词 | ✅ 有 |

`check_speech` 宽到连 `la sekurite` 都判对。同一门语言的两个技能，一个零容错无申诉，
一个宽到几乎判不错。

用户的选择是保持 `check_fr` 硬判错，只把自判按钮改名为「中文算我对／中文算我错」
并写明法语不受其影响。**不要**擅自给 `check_fr` 加容错。

---

## 4. 主区还有两处可以按「设一次 vs 每次用」收起来

**状态**：已提出，用户说先用几天再定。

侧栏已经按这个原则分层了（见 `tests/test_sidebar_layout.py`）。主区还剩：

- 顶部四个指标（词库／错词／提交次数／正确率）——是不是每次打开都要盯着？
- 「查看这个词的最近记录」「这张卡你以前怎么答的」这类**回顾用**的折叠区，
  现在混在答题流里

---

## 5. L34 的阅读证据文件格式该向 L31/L32 看齐

**状态**：已确认，不急。

`L31.T5.reading-evidence.md` 和 `L32.T6.reading-evidence.md` 有明确分节：

```
### Printed source text
### Question and options
### Visible markings
### Handwritten annotations
### Evidence notes
```

这让"这个词到底出现在试卷原文里，还是出现在我自己的分析文字里"**可以机器判定**。
`L34.T8.reading-evidence.md` 没有分节，做同样的交叉核对时只能逐条人工看上下文，
慢且容易漏。写 ingest skill 的下一版时应把分节定成规范。

---

## 6. 等用户就绪的事（不是缺陷）

- **Anki 制卡**：Docker 里跑着别的东西。开了之后查 L34 那 77 个老师层 lemma
  缺哪些卡、只补缺的（不生成带《补》的，省 quota）。
- ~~**阅读9 预抽词**~~ ✅ 已完成 2026-08-12：L35 上线时按约定抽了，60 条全走《补》层
  （`[T9Qn 补]`），老师课上讲到的 8 条走老师要求档。**老师那份阅读9 笔记仍未到**，
  到了要重跑一次归属：高亮的词从《补》升档时，老师证据**并进原有那条 provenance**，
  不追加第二条（追加会让 `merge_vocab.py` 的等值去重失效，App 里「为什么收录这个词」
  会重复渲染两次）。
- **L33 的开课词 ∩ 阅读交叉核对**：做不了，L33 没有阅读证据文件。
  （L35 补了 11 条 + 2 条 word_family、L34 补了 12 条、L31 补了 4 条、L32 补了 2 条，
  都已完成。）

---

## 7. 测试里禁止裸 `import app`

`app.py` 是 Streamlit 脚本，**import 的瞬间就整个执行一遍**——包括 1144–1148 行按
文件签名往 `dictation.db` 导词。在 pytest 进程里裸 import 之后，后面用
`AppTest.from_file("app.py")` 起的用例会连环失败：

```bash
# 实测（2026-08-12，HEAD=a770398）：测试里加一句 `from app import ...` 之后
python3 -m pytest -q          # 21 failed, 232 passed, 4 errors
python3 -m pytest -q tests/test_writing_ui.py::test_layout_has_editor_and_word_count  # 1 passed
```

单独跑全过、全量跑就炸，典型的共享状态污染。挂掉的全在
`test_writing_app_entry.py` / `test_writing_ui.py` / `test_writing_entry_independent.py`。

**要在测试里读 `app.py` 的模块级常量，用 `ast` 静态解析，别 import。**
现成例子：`tests/test_vocab_provenance_ui.py::test_every_real_teacher_action_has_a_chinese_label`。

## 8. `@st.cache_data` 的文件签名不保证失效

`app.py:169` 的 `_file_signature()` 按 `st_mtime_ns + st_size` 做缓存键，理论上课程
数据一改就失效。实测不可靠：2026-08-12 改完 `L35/vocab.json`（152→155 行）和
`manifest.json`（45→50 张卡）之后，浏览器整页重载两次，侧栏仍显示旧的
`开始这一课（152 词）` / `📝 知识点（45）`；**重启 streamlit 进程后立刻正确**。

同一天早些时候新建 L35 时也一样：选课下拉框里根本搜不到 L35，重启才出现——
说明课程**列表**也吃这个缓存。

没定位到根因（可能是 session_state 里存着的轮次快照，也可能是 cache_data 本身）。
在此之前：**改完课程数据要验证真实 8501 时，默认重启 streamlit**，别指望热更新。
注意重启会打断正在用 8501 的人。

---

## 9. 从 `vocab.json` 撤掉的词不会从 `dictation.db` 消失

**状态**：已确认，等决定怎么处理。

`store.py:20` 的 `import_vocab_into_db()` 是**只插不删**：

```python
for lemma in vocab:
    try:
        cur.execute("INSERT INTO words (text, created_at) VALUES (?, ?)", (lemma, _now()))
    except sqlite3.IntegrityError:
        pass          # 已存在就跳过——但「已删除」没人管
```

它在 `app.py:1148`（按文件签名全量导入）和 `app.py:1413`（自定义词表）两处被调用。
结果是：**一个词只要进过一次库，就永远留在库里**，哪怕它后来被证明是听错的。
课程数据是 append-only 的语义，学习库却不是。

实测（2026-08-13，HEAD=5b631a8）：

```bash
python3 - <<'PY'
import json, glob, sqlite3
lemmas = set()
for f in glob.glob('../L*/vocab.json'):
    lemmas |= {r['lemma'] for r in json.load(open(f, encoding='utf-8'))}
c = sqlite3.connect('dictation.db')
rows = list(c.execute('SELECT id,text,wrong_count,correct_streak,last_seen_at FROM words'))
print(len(lemmas), len(rows))
for r in rows:
    if r[1] not in lemmas:
        print(r)
PY
```

vocab.json 共 1462 个 lemma，`words` 表 1467 行，**5 行在任何 vocab.json 里都找不到**
（也都不在 `words.txt` 的 58 行里）：

| id | text | 错次 | 连对 | 最后练习 |
|---:|---|---:|---:|---|
| 153 | `l'Afghanistan` | 1 | 0 | 2026-06-11 |
| 158 | `la Mer du Nord` | 0 | 0 | — |
| 204 | `les medias` | 2 | 5 | 2026-06-16 |
| 842 | `la pilule` | 1 | 0 | 2026-07-18 |
| 1274 | `un essai` | 0 | 0 | — |

`un essai` 是最能说明问题的一条：L35 上线时两路 ASR 都听成 `essai`，后来老师自己的
听写词单上只有 `essayer`、没有 `essai`，词条据此撤掉了——**但库里这行还在**。
`les medias` 更糟，已经练了 7 次（错 2 连对 5），也就是说**学习者真的在背一个已经被撤回的词**。

危害不是崩溃，是安静地跑偏：孤儿词不属于任何一课，所以选课练习抽不到它，
但全库搜词、「全部」入口、词库统计都还带着它。撤词越多，库越脏。

**改法**（没动，因为要先定策略）：

- 保守：导入后报告一次「库里有 N 个词不在任何 vocab.json 里」，只提示不删；
- 彻底：给 `words` 加一列来源，导入时把「来自 vocab.json 但已消失」的标 `hidden=1`
  （**不能硬删**——`les medias` 那种有练习记录的，删了就丢 SRS 历史）。

短期人工处置：确认某行确实是撤回产物且 `wrong_count=0`、无 `attempts` 引用时，
可以直接 `DELETE`；有练习记录的建议标 `hidden=1` 而不是删。
2026-08-13 L36 撤 `la protection` 时就是这么处理的（0 次练习，直接删，删前备份 db）。

---

## 9. 整个测试套件的结果依赖 dictation.db 里持久化的轮次

**状态**：已确认，机制清楚，只堵住了当前的入口，没有根治。

`app.py` 每次渲染结束都会 `if st.session_state.get("pool"): persist_round()`。
任何用 `AppTest` 且把 `pool` 撑起来的用例，都会把**存档轮次**写进 `dictation.db`，
而后面新起的 `AppTest` 在启动时会 `load_round()` 把它「续上」——于是用例之间
通过磁盘互相传染。

**实测**（2026-08-13 加 `tests/test_word_panel.py` 时）：

```
第一次全量：2 failed, 313 passed
  FAILED tests/test_card_request_ui.py::test_requested_word_shows_in_sidebar_and_can_be_cancelled
  FAILED tests/test_llm_ui.py::test_production_ai_requires_user_verdict_before_srs
隔离重跑这两条：5 passed
再跑一次全量：315 passed
```

两条都不是被改坏的——是**存档在运行途中被改变**的那一次才翻车，等存档稳定下来
就又绿了。也就是说这个套件有一类只在「存档状态发生迁移」时出现的假红。

**已做的**：`tests/test_word_panel.py` 和 `tests/test_scan_handoff.py` 各加了一个
autouse fixture `_keep_the_saved_round()`，跑完还原（原来没有存档就 `clear_round()`）。

**没做的**（根治方案，等有空再定）：

- 最省事：加一个 `tests/conftest.py`，把还原做成全局 autouse，所有用例自动免疫；
- 更彻底：让 `AppTest` 系的用例跑在临时 `DB_PATH` 上，不碰真实的 `dictation.db`
  （现在 `test_scan_store.py` 已经是这么做的，但 UI 用例还在用真库）。

**给后来人**：新写的 UI 用例只要会让 `pool` 非空，就必须带上还原，否则会把用户
真正在练的那一轮存档冲掉——这不只是测试问题，是会丢用户状态的。
