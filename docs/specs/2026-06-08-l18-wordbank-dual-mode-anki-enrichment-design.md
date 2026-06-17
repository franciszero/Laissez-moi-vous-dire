# L18 词库 + 听写双模式 + Anki 只读富化 — 设计（Phase 1）

- Date: 2026-06-08
- Status: 设计已获用户同意，待 spec 评审
- Scope: 听写 app（`法语/本地录屏课/听写`）Phase 1；Phase 2/3 仅作路线图勾画

## 1. 背景与问题

- 现状：听写 app（Streamlit + SQLite + macOS `say`）只校验拼写对错。答完看不到词义，想看意思得去 Collins → "学不到东西"。
- 新需求：L18 是**复习课**，词表覆盖 Leçon 23/24/25（= 录屏课文件夹 L12 / L13 / L17）。要把它整理成程序可用的结构化词表，并升级听写以"边听写边学词义"。
- 已盘点的资产：
  - **anki-wordsmith**（`Georgian_College/GitHub/anki-wordsmith`）：法语制卡流水线。词条格式（`src/french/input_parser.py`）：一行 `lemma`、`lemma (词性)`、`lemma (词性; 课文例句)` 或 `lemma (课文例句)`；括号非词性时整体作 `USAGE_CONTEXT`（消歧/对齐）。**名词必须带冠词**。流水线自身会生成卡内例句，所以"课文例句"是消歧上下文，不是最终例句。
  - **AnkiConnect v6** 在线。个人牌组 `Français`（234 卡）。note type `Francis 的 法语单词卡`，字段含 `Lemma / Core Meaning(中文) / Définition FR / IPA + Pronunciation Notes / Example Sentences / Collocations / Mini Dialogues / …`。卡片**暂无课程标签**。
  - 覆盖率抽样：**Leçon 25（=L17，旧词表）基本已制卡；Leçon 23/24（=L12/L13）基本未制卡。**

## 2. 路线图（三阶段）

- **Phase 1（本文档）**：结构化词表 + 听写双模式 + 答后显示词义 + Anki 只读富化。纯本地交付，不依赖 Anki/Docker。
- **Phase 2**：anki-wordsmith 制卡（Leçon 23/24；从 L12/L13 课文 PDF 抽例句填进词条括号；L17 缺课文单独处理）；生成 `Francis 的 法语单词卡` 推进 `Français` 并打 `L18` 标签。
- **Phase 3**：Anki 当 SRS 大脑（学习模式按标签拉卡、考试模式拉到期卡并把复习结果回写 Anki 调度器）；本地 SRS 退为离线缓存。

## 3. Phase 1 详细设计

### 3.1 数据：结构化词表

- 位置：`本地录屏课/L18/vocab.json`（用户要求"放 L18 文件夹"）；同时迁移 `本地录屏课/L17/vocab.json`，让"按课选"至少有两课可选。
- 文件 = 词条数组，每条：

```json
{
  "lemma": "augmenter",
  "pos": "verb",
  "zh": "增长，提高",
  "lesson": "L18",
  "source_lesson": "Leçon25",
  "category": "VERBES",
  "example": null,
  "raw": "augmenter v. i. ou v. t."
}
```

- 字段：`lemma` 朗读&听写目标（清洗后）；`pos` ∈ {noun,verb,adj,adverb,conj,prep,expr}（由 `category` + 内嵌缩写推导，供显示与 Phase 2 词性提示）；`zh` 中文；`source_lesson` ∈ {Leçon23,Leçon24,Leçon25}；`example` 留到 Phase 2；`raw` 原始留档。
- **清洗规则**（从用户贴的三张表生成 `lemma`）：
  - 去尾部语法缩写：`n. f. / n. m. / v. t. / v. i. / v. t. ind / v. i. ou v. t. / adv. / conj. / prép. / loc. adv. / loc. prép. / adj.` 等。
  - 去 `[...]`（IPA），如 `un sandwich [sãdwitʃ]` → `un sandwich`。
  - 去 `（…）` / `(...)` 中文注释，如 `prévoir v. t.（变位同 voir）` → `prévoir`。
  - 名词保留冠词：`la confiture`、`le légume`。
  - 阴阳性/词形对 `Parisien, ne` / `client, e` / `délicieux, se` / `conducteur, trice` / `premier, ère` → 取**基本形/阳性**（`Parisien`）。【锁定决策】
- **历史一致性（关键）**：`L17/vocab.json` 的 `lemma` 必须与现有 `words.txt`（即 DB `words.text` 已有值）**逐字一致**，以保住 290 条 attempts 历史。故 L17 以 `words.txt` 为 lemma 权威，再用 Leçon 25 表补 `zh/pos`。L18 以三表生成；其中 Leçon 25 子集与 `words.txt` 文本一致者自动续历史，不一致者按新词处理（复习集，可接受）。
- 生成器先产出**样本 / diff 给用户过目再定稿**（清洗易错，尤其 `un épicier`(words.txt) vs `épicier, ère`(表) 这类）。

### 3.2 听写改造（`app.py`）

- 启动时加载并合并所有 `../L*/vocab.json` → 内存字典 `lemma → {pos, zh, example, lessons}`（`st.cache_data`）。用于"按课选"成员关系 + 两模式的"显示词义"。可用课程 = 扫描到的 `../L*/vocab.json`。
- **双模式**：
  - **学习模式**：侧栏选课（L17 / L18 / …），从该课 vocab 取词，沿用现有分批随机不放回。
  - **考试模式**：跨课，沿用现有错题/到期复习（本地 SRS = 遗忘曲线雏形）。
  - 现有功能保留：分批、自动下一题、只练到期、上一题/重听/显示答案、本批完成页。
- **答完显示词义**：
  - 总是：✅/❌ + 正确拼写（现有）+ `zh`（来自词表）。
  - **只读富化**：若 `lemma` 命中 Anki `Français` → 额外显示 `Core Meaning / 一条 Example Sentences / IPA`（去 HTML 标签、截断）；Anki 没开或未命中 → 静默跳过。
- 朗读仍用 `say`（离线、简单）。

### 3.3 数据库（最小改动，保历史）

- **不改表结构**。词义内容来自 JSON 运行时读取，不进 DB。
- 导入：把 `import_words_from_txt` 改为读 `vocab.json`，仅对**新 lemma** `INSERT`（text + created_at），已存在的跳过 → 不动 `wrong_count / correct_streak / interval_days / due_at / attempts`。
- 迁移前自动再备份 `dictation.db`（带时间戳）。保留 `words.txt` 作为后备导入源。

### 3.4 AnkiConnect 只读客户端（新模块 `anki.py`）

- 端点 `http://127.0.0.1:8765`，仅用读 action：`findNotes`（`deck:"Français" "Lemma:re:<lemma>"`，名词去冠词再试一次）、`notesInfo`。
- 缓存：`lemma → 富化内容`（`st.cache_data`，进程内）。
- HTML→文本：去标签、解实体、压空白、截断。
- 降级：连接失败/超时/未命中 → 返回 `None`，UI 跳过富化。**绝不调用写类 action**（addNote / updateNoteFields / guiAddCards / sync / deleteNotes …）。

### 3.5 非目标（Phase 1）

- 不写 Anki、不抽课文例句、不接 Anki 音频、不做 Anki SRS 回写（均在 Phase 2/3）。

### 3.6 测试

- 清洗规则单测：覆盖 `un sandwich [sãdwitʃ]`、`l'eau n. f.`、`prévoir v. t.（变位同 voir）`、`Parisien, ne`、`les gens n. m. pl.`、`en dehors de loc. prép.`。
- 导入幂等：重复导入不增历史、不重复插入。
- L17 lemma 与 `words.txt` 逐字一致（防历史断裂）。
- Anki 客户端：HTML 去标签正确；Anki 不可用时降级；命中 / 未命中分支。

### 3.7 风险 / 回滚

- 主要风险：lemma 清洗错误导致听写目标错或历史断裂 → 样本评审 + L17 逐字一致校验 + 单测兜底。
- AnkiConnect 全程只读，无损 Anki 数据。
- 回滚：保留 `dictation.db` 备份；`vocab.json` 与新模块均为新增，移除即恢复旧行为（`words.txt` 仍在）。

## 4. 锁定决策

- 词表格式 **JSON**（不用 TSV）。
- **顺带迁移 L17** 到结构化词表。
- 阴阳性/词形对**取阳性/基本形**。

## 5. 留待 Phase 2/3

- 课文例句抽取（L12/L13 课文 PDF；L17 缺课文的缺口）。
- anki-wordsmith 制卡 + `L18` 标签回灌 `Français`。
- Anki 作为 SRS 大脑 + 复习结果回写。
