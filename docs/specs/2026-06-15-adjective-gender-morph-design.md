# 设计：形容词阴阳性「变形」练习

日期：2026-06-15　状态：待用户复核
（本项目非 git 仓库，故不提交，仅落盘本文件。）

## 目标
让用户**主动掌握阴阳性变形**：看到/给出阳性形式 → 敲出阴性形式。作为一个新的掌握维度跟踪、上色、计入"总掌握"。

适用对象：有独立阴性形式的词（形容词 + 阴阳成对的人称名词，如 client/cliente、épicier/épicière）。

## 不做（YAGNI）
- 复数形式（occidental/occidentaux 那种）。
- 听阳性→写阴性（先只做「看」）。
- mieux/meilleur 特殊处理——它们是**不同的词**（mieux=副词、meilleur=形容词），源表里本就是独立词条，各自正常听写，与本功能无关。
- 不规则词的"待确认"专门 UI——重建 + 保留原标记，错了手改 vocab.json。

## 一、数据：阴性从哪来（回填，不用重新导入）
现有 vocab.json 的 `raw` 字段保留了原始标记（`court, e` / `épicier, ère` / `occidental, occidentale`）。

**词条新增两个字段**：
- `fem`：重建出的阴性形式（字符串）；无独立阴性则为 `null`。
- `fem_raw`：逗号后的原始标记（兜底，便于核对/手改）。

**重建函数** `vocab.feminine_form(masc, marker)`（marker = 逗号后部分，去空格），按此**顺序**判断：
1. 无 marker → `None`（阴阳同形/不适用）。
2. `marker == "e"` → `masc + "e"`（étroite/courte/habitante/mondiale… 覆盖绝大多数，准）。
3. **已知后缀替换**（小规则表，marker 命中其一就用）：
   - masc 结尾 `er` + marker `ère` → `masc[:-2]+"ère"`（épicier→épicière）
   - masc 结尾 `eur` + marker `euse` → `masc[:-3]+"euse"`（chanteur→chanteuse）
   - masc 结尾 `teur` + marker `trice` → `masc[:-4]+"trice"`（conducteur→conductrice）
   - masc 结尾 `x` + marker `se` → `masc[:-1]+"se"`（délicieux→délicieuse）
   - masc 结尾 `f` + marker `ve` → `masc[:-1]+"ve"`（neuf→neuve）
   - marker `ne`/`nne` → `masc+"ne"`（Parisien→Parisienne）
   - marker `le`/`lle` → `masc+"le"`（naturel→naturelle）
4. 否则若 marker **长度 ≥4 且不在上面后缀集** → 视为**完整阴性词**，直接用（occidentale、principale、belle、vieille、blanche、longue）。
5. 其它（短、拿不准）→ `fem = None`，`fem_raw` 保留（手改）。

**落地方式**：
- `vocab.py` 加 `feminine_form`；`clean_lemma` 不变（仍产 masc lemma），在 `parse_lesson_table`/`parse_uploaded` 给每条加 `fem`/`fem_raw`（来源：french 单元格逗号后）。
- 一次性**回填脚本** `scripts/backfill_fem.py`：遍历 `../L*/vocab.json`，对每条用 `raw` 重算 `fem`/`fem_raw` 并写回。跑一次即可，无需用户重新上传。

## 二、掌握度：新增「变」维度
- `mastery.SKILLS` 增加 `"morph"`；attempts 用 `skill="morph"` 记录（attempts.skill 已是自由文本，无需 DB 迁移）。
- **关键修正**：`overall()` 不能再对全部技能取 min（否则没阴性的词 morph=0 → 永远不算掌握）。
  - `BASE_SKILLS = ("form","meaning","pron")`；`overall(scores, skills=BASE_SKILLS)` 默认仍是这三项（**现有测试不破**）。
  - `render_word_panel` 对**有 fem 的词**传 `skills=BASE_SKILLS+("morph",)`，无 fem 的词用默认三项。
- **词表热力图加第 4 列「变」**：有 fem 的词按 morph 掌握度上色；无 fem 的词显示「—」（不适用）。

## 三、练习：模式 +「变形」入口
- `MODES` 增加 `"看阳性 → 写阴性": ("fr_morph", ("fem",), "morph")`。
  - **新 prompt 类型 `fr_morph`**（不要复用 `fr_text`，否则会触发念法语那条"读出来"提示，也不能触发自动播音）。
  - 提示区（按 `ANSWER_FIELDS == ("fem",)` 分支）显示：`阳性：court — 短的，写出阴性形式`。
  - 单个输入框，回车提交；匹配 `matcher.check_fr(typed, VOCAB[text]["fem"])`（重音严格）。
  - `_finalize`/提交处理支持 `"fem"` 字段：记 `skill="morph"`，对错入 `round_results`。
- **侧栏新增「变形（N）」入口**（与"错词/到期"并列）：N = 当前选课里有 fem 的词数；点了 → 词池 = 这些词、并把模式自动切到「看阳性 → 写阴性」、开练。这样不用在混合词表里一个个跳过无变化的词。
- 兜底：若在「变形」模式遇到无 fem 的词（如手动切了课/模式），显示「（这个词无阴阳性变化）」+ 下一题，不自动 rerun（防循环）。

## 改动清单（文件 → 改什么）
- `vocab.py`：加 `feminine_form()`；解析时给词条加 `fem`/`fem_raw`。
- `scripts/backfill_fem.py`（新）：回填现有 vocab.json。
- `mastery.py`：`SKILLS` 加 morph；`BASE_SKILLS` + `overall(skills=…)`。
- `app.py`：MODES 加变形模式；submit/`_finalize` 支持 `fem` 字段+morph；render 提示区与"无变化"兜底；`render_word_panel` 加「变」列 + 传 applicable skills；侧栏「变形（N）」按钮（需要"本课有 fem 的词 id"helper）。

## 验证
- 单测：`feminine_form` 各分支（e / 完整词 / ère / euse / trice / se / 无）；`overall` 加 morph 后默认三项不变（旧测试绿）。
- `backfill_fem.py` 跑后抽查 L17–L20 的 `fem` 是否合理（court→courte、épicier→épicière、occidental→occidentale）。
- AppTest：切「看阳性→写阴性」→ 提交阴性 → 判定 + morph 入库；词表「变」列渲染不挂。
- 真实 DB 先备份再测、测完还原（同既往）。
