# 备忘录 · L23 转录后知识点落卡工作流（2026-06-25）

这份文档回答一个具体问题：`bash scripts/run-lesson-full-pipeline.sh L23` 之后，到底还要做什么，入口是什么，靠哪些 skill / 工具 / 记忆 / 指令保证不同课程一致，以及这套架构哪里合理、哪里不合理。

## 0. 先解决的线上可见性问题

症状：L23 的 `manifest.json` 和 `vocab.json` 已经写到磁盘，但 8501 网站侧栏选课里看不到 L23。

根因：8501 的课程列表来自 `vocab.load_all_vocab(BASE_DIR)`，而 `load_vocab()`、`load_checkpoints()`、`load_conjugations()` 都被 `@st.cache_data` 缓存。pipeline 或另一个 session 在 app 运行期间写入新课文件时，旧进程不会自动感知，除非点侧栏「🔄 重新扫描词表」或重启。

本次修复：

- `app.py` 增加 `_file_signature(pattern)`，把匹配文件的相对路径、mtime、size 作为 Streamlit cache key。
- `load_vocab(...)` 监听 `*/vocab.json`。
- `load_checkpoints(...)` 监听 `L*/manifest.json`。
- `load_conjugations(...)` 监听 `L*/conjugation.json`。
- 手动「🔄 重新扫描词表」按钮保留，作为强制清 cache 的兜底。
- 新增 AppTest：`test_l23_lesson_is_visible_and_checkpoint_deck_starts`，验证 L23 可选、知识点按钮数量正确、deck 能进入。

验证：

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=. pytest -q tests/test_checkpoint_ui.py::test_l23_lesson_is_visible_and_checkpoint_deck_starts
streamlit run app.py --server.port 8501 --server.headless true
curl localhost:8501/_stcore/health
```

本次实测 8501 重启后 health 200，日志中 traceback/exception/error 为 0。刷新页面后，L23 应出现在选课里，知识点按钮应显示 48。

## 1. pipeline 之后实际做了什么

`run-lesson-full-pipeline.sh` 的职责到“ASR/合并/初步 detector 输出”为止。L23 这次 pipeline 后的关键事实是：final transcript 与 evidence 生成了，但自动 detector 对 L23 没有 lesson-specific 规则，所以 `L23_knowledge_units.json` 一开始是空数组。

因此 pipeline 后做的是一整套“转录 → 可复习知识卡”的人工审核/结构化/上线流程：

1. 确认合并产物
   - `docker-data/outputs/L23/L23_final_working.md`
   - `docker-data/outputs/L23/L23_final_working_evidence.json`
   - `docker-data/outputs/L23/L23_knowledge_units.json`

2. 做 bounded 的知识点盘点
   - 只做一轮结构化审核，不做无限 census / saturation。
   - 从 transcript 中提取 teacher rules、examples、corrections、student errors、practice-worthy points。
   - 裸词/拼写不进知识卡；放回 vocab / dictation 系统。

3. 写 VibeVoice 侧结构化来源
   - `docs/french-wiki/census/recapture/reconciled/L23.species.json`
   - `docker-data/outputs/L23/L23_knowledge_units.json`

4. 写 8501 数据侧卡片配置
   - `../L23/vocab.json`
   - `../L23/L23.card_overrides.json`
   - `../L23/L23.checkpoint_groups.json`
   - `../L23/L23.knowledge_inventory.md`

5. 生成 8501 manifest
   - `../L23/manifest.json`
   - 构建结果：13 vocab + 48 checkpoints。

6. 验证
   - JSON 格式检查。
   - `scripts/build_checkpoints_from_species.py` manifest validation。
   - `scripts/coverage_report.py ../L23/manifest.json`。
   - app 全量测试。
   - 8501 health check。

## 2. 指令入口

### 2.1 转录合并入口（VibeVoice）

当原始转录已经跑完，只需要重新合并/重建下游文本产物时：

```bash
cd /Users/francis/Documents/Georgian_College/GitHub/VibeVoice
bash scripts/run-lesson-full-pipeline.sh L23 --skip-vibe --skip-qwen --skip-whisper
```

这一步会重建 final transcript/evidence，并尝试跑已有 detector。注意：detector 没有某课规则时，`*_knowledge_units.json` 可能为空；这不是“没有知识点”，只是“自动规则没有覆盖这课”。

### 2.2 知识点 species → 8501 manifest 入口（听写 app）

```bash
cd /Users/francis/Documents/法语/本地录屏课/听写
python3 scripts/build_checkpoints_from_species.py \
  --lesson L23 \
  --source L23_final_working.md \
  --species-json /Users/francis/Documents/Georgian_College/GitHub/VibeVoice/docs/french-wiki/census/recapture/reconciled/L23.species.json \
  --vocab-json ../L23/vocab.json \
  --overrides ../L23/L23.card_overrides.json \
  --checkpoint-groups ../L23/L23.checkpoint_groups.json \
  --out ../L23/manifest.json
```

### 2.3 覆盖报告入口

```bash
python3 scripts/coverage_report.py ../L23/manifest.json
```

L23 当前报告：

- vocab chunk：13
- checkpoint chunk：48
- species 覆盖：24/24
- 缺口/问题：无
- 唯一提醒：`homework-boundary` 组全自评。这是作业边界/流程确认，属于合理豁免。

### 2.4 8501 网站刷新/验证入口

正常情况下，新课文件变化会自动触发 cache key 改变。仍保留手动兜底：

- 页面侧栏点「🔄 重新扫描词表」；或
- 重启 Streamlit：

```bash
pkill -f "streamlit run app.py"
streamlit run app.py --server.port 8501 --server.headless true
```

## 3. 本次 L23 的实际产物

### 3.1 VibeVoice 侧

- `docker-data/outputs/L23/L23_final_working.md`
- `docker-data/outputs/L23/L23_final_working_evidence.json`
- `docker-data/outputs/L23/L23_knowledge_units.json`
- `docs/french-wiki/census/recapture/reconciled/L23.species.json`

未提交/不应随便提交：

- ASR segment wav 目录。
- 中间模型转录目录。
- 大媒体文件。

### 3.2 8501 数据侧

- `L23/vocab.json`
- `L23/L23.card_overrides.json`
- `L23/L23.checkpoint_groups.json`
- `L23/L23.knowledge_inventory.md`
- `L23/manifest.json`

当前 L23 知识点分组：

1. 过去视角与间接引语
2. ce que / ce qui / qui
3. 动词接口与文本表达块
4. 课后任务边界

当前 L23 规模：

- 24 reviewed species。
- 48 checkpoint cards。
- 26 machine-graded cards。
- 22 self-review cards。
- 13 vocab entries。

## 4. 保证不同课程一致性的支撑

### 4.1 skills / 指令

1. `existing-pattern-first`
   - 约束：修改现有系统前先找本地模式，不新建平行架构。
   - 本次落实：复用 `../L*/manifest.json`、`build_checkpoints_from_species.py`、`checkpoint_groups`、`card_overrides`，没有建全局 registry / global ID / 共享掌握度。

2. `bounded-extraction`
   - 约束：转录抽知识点时，不做无限普查，不用 saturation 当交付门槛；裸词不当知识点卡。
   - 本次落实：L23 只做一轮可上线盘点；词汇放 vocab，知识卡只承接规则、接口、句型、策略。

3. `lesson-learning-pipeline`
   - 约束：先从 final transcript 提炼 timestamped evidence，再建 knowledge units / site surfaces，不直接从 ASR 摘要跳到网站。
   - 本次落实：VibeVoice 侧留下 `knowledge_units` 与 `species`，8501 manifest 从 species 构建。

4. AGENTS / HANDOFF 约束
   - 每课拥有自己的卡；跨课重复 + 轻指针，不建共享层。
   - 课程内容走 per-lesson manifest。
   - `cp_active` 是独立知识点流程，不碰词练习的 `pool/current_word`。
   - commit 采用 lore protocol，记录约束、拒绝方案、测试。

### 4.2 工具

1. `scripts/run-lesson-full-pipeline.sh`
   - 合并 ASR 输出、生成 final working transcript 和 evidence。

2. `scripts/build_checkpoints_from_species.py`
   - 把 reviewed species 变成 checkpoint cards。
   - 支持 `card_overrides` 精修 front/back/answer。
   - 支持 `checkpoint_groups` 排序与追加 practice cards。
   - 保证 `source_species` 覆盖分母稳定。

3. `manifest.py`
   - 校验 lesson/source/chunks、bucket、checkpoint 必填字段、species 覆盖数、重复 source_species。

4. `scripts/coverage_report.py`
   - 打印 chunk/bucket、species 覆盖、缺口、全自评组提醒。

5. `streamlit.testing.v1.AppTest`
   - 验证网站真实入口，而不只验证 JSON。
   - 本次新增 L23 可见性回归测试。

### 4.3 记忆 / 文档

1. `HANDOFF.md`
   - 记录 app 的系统边界、陷阱、数据约定。

2. `docs/MEMO-2026-06-17-manifest-checkpoint.md`
   - 记录 manifest/checkpoint 系统为什么存在，以及 L21 先例。

3. `docs/plans/2026-06-22-knowledge-unification.md`
   - 记录知识点卡、练习卡、AI 产出卡统一的方向。

4. 本文档
   - 记录 L23 后 pipeline 的实际打法与架构复盘，作为 L24+ 的操作记忆。

## 5. 架构上合理的地方

1. per-lesson manifest 是正确边界
   - 每课有自己的学习上下文、老师纠错、作业边界。
   - 不建共享掌握度，避免过早抽象。
   - 跨课复现同一语法点时，允许重复卡片，因为复习语境不同。

2. species 作为 coverage key 合理
   - `source_species` 让“老师讲过的点是否进入 8501”可清点。
   - `coverage.expected_species_count` 能防止漏卡或重复卡。

3. `card_overrides` + `checkpoint_groups` 的两层设计合理
   - species 自动生成兜底卡，保证覆盖。
   - overrides 负责精修单张卡。
   - groups 负责学习顺序和补练习题。
   - 这避免把精修内容写死进构建脚本。

4. 词汇与知识卡分开合理
   - vocab/dictation 负责词、拼写、释义。
   - checkpoint 负责规则、接口、句型、策略。
   - 遵守 bounded-extraction rule 6，避免“知识卡 = 单词堆”。

5. 网站读取磁盘文件自动失效合理
   - 新课由 pipeline 或另一个 session 生成时，用户不必知道 Streamlit cache 的内部机制。
   - 仍保留手动 rescan，适合异常兜底。

## 6. 架构上不合理或脆弱的地方

1. post-pipeline 缺一个正式总入口
   - 现在从 final transcript 到 species、knowledge_units、overrides、groups、manifest，需要 agent 手动串联。
   - `run-lesson-full-pipeline.sh` 名字像“全流程”，但实际上没有完成“8501 可见卡组上线”。

2. detector 与人工 species 层割裂
   - L23 自动 detector 输出 0，但人工审核能得到 24 个 species。
   - 这会让“pipeline 绿了”产生误导：绿的是 ASR/合并，不是教学点覆盖。

3. vocab chunk 不能为空的约束有点隐性
   - `manifest.validate` 要求非 skip chunk items 非空，所以 L23 即使重点是知识卡，也必须给 vocab chunk 放内容。
   - 这合理地保持 manifest 合同完整，但对执行者不够显眼，容易先写 `[]` 后构建失败。

4. `checkpoint_groups` 没有显式 application/exempt 字段
   - coverage report 只能提示“全自评组待确认”，不能真正表达“这是合理豁免”。
   - 长远看，“陈述必配题”应该是 schema 级合同，而不是靠人工解释。

5. AppTest 能证明可见性，但不能证明用户浏览器已刷新
   - 本次已加文件签名自动失效并重启 8501。
   - 但如果用户浏览器 tab 持有旧前端状态，仍可能需要手动刷新页面。

6. 跨仓库产物容易漏提交或误提交
   - VibeVoice 产出、8501 数据产出、8501 app 代码在不同仓库/目录。
   - 大媒体和 ASR segment 很容易被 `git add L23/` 或 `git add docker-data/outputs/L23/` 误纳入。

## 7. 改进建议

### 7.1 近期、值得做

1. 增加一个 post-pipeline orchestration 脚本

建议入口：

```bash
scripts/ship-lesson-knowledge.sh L23
```

它不一定自动写人工 species，但至少做：

- 检查 final transcript/evidence 是否存在。
- 检查 `reconciled/<lesson>.species.json` 是否存在且 JSON 有效。
- 检查 `../<lesson>/vocab.json`、overrides、groups 是否存在。
- 调用 `build_checkpoints_from_species.py`。
- 调用 `coverage_report.py`。
- 跑 manifest/json 检查。
- 输出“是否可在 8501 看到”的 checklist。

2. 给 L23/L24+ 增加 lesson-specific manifest smoke test

现在已有 L23 AppTest。未来可以用一个参数化测试扫 `../L*/manifest.json`，至少保证：

- 每个有 manifest 的课都能被 `load_checkpoints` 发现。
- 每个有 vocab 的课都能出现在侧栏。
- checkpoint count 与 manifest 一致。

3. 扩展 coverage schema：application/exempt

建议每个 species 或其配套 practice 声明：

- `application.kind = machine|self|llm`
- 或 `exempt.reason = homework_boundary|pure_reference|not_practice_worthy`

这样 `coverage_report.py` 能区分“合理自评/流程卡”和“缺应用题”。

4. 文档化“vocab chunk 不能空”

把该约束写进 `docs/MEMO-2026-06-17-manifest-checkpoint.md` 或 `HANDOFF.md` manifest 部分，减少下次先写 `[]` 的摩擦。

### 7.2 中期、谨慎做

1. 半自动 species scaffold
   - 不让模型独断生成最终卡，但可以从 final transcript 产出候选 species scaffold。
   - 人工仍负责 reviewed status、priority、练习设计。

2. 让 `coverage_report.py` 能输出 lesson launch checklist
   - JSON valid
   - species coverage
   - machine/self ratio
   - full-self groups with reason
   - site-visible preflight

3. 建一个“不要 stage 大文件”的保护脚本
   - 检查 staged files 中是否有 `.mov/.mp4/.wav/.pdf/.jpg` 或大于某阈值的文件。
   - 对这个跨仓库 workflow 很有价值。

### 7.3 不建议现在做

1. 不建跨课 global species registry / shared mastery
   - 目前 L20/L21/L22/L23 还没有出现足够强的实际痛点。
   - 重复少量卡比维护共享层便宜。

2. 不把 post-pipeline 全自动化为“从转录直接生成最终知识卡”
   - 老师纠错、学生痛点、哪些词不做知识卡，这些需要 judgment。
   - 可以自动 scaffold，但 reviewed 卡片设计仍应保留人工/agent 审核闸。

3. 不把 vocab 变成知识卡来绕过 manifest 空 chunk
   - 这会破坏系统边界。
   - 正确做法是保留 vocab chunk，同时只把可教学的规则/接口/句型做 checkpoint。

## 8. L24+ 推荐标准流程

1. 跑或确认转录 pipeline。
2. 若只需重建下游：

```bash
bash scripts/run-lesson-full-pipeline.sh L24 --skip-vibe --skip-qwen --skip-whisper
```

3. 读 final transcript，做一次 bounded knowledge pass。
4. 写/审 `docs/french-wiki/census/recapture/reconciled/L24.species.json`。
5. 写 `docker-data/outputs/L24/L24_knowledge_units.json`。
6. 写数据仓库：

```text
L24/vocab.json
L24/L24.card_overrides.json
L24/L24.checkpoint_groups.json
L24/L24.knowledge_inventory.md
```

7. 构建 manifest：

```bash
python3 scripts/build_checkpoints_from_species.py --lesson L24 ...
```

8. 验证：

```bash
python3 -m json.tool ../L24/manifest.json
python3 scripts/coverage_report.py ../L24/manifest.json
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=. pytest -q
python3 -m compileall -q app.py scripts/build_checkpoints_from_species.py manifest.py
```

9. 网站确认：
   - L24 出现在选课。
   - 知识点按钮数量正确。
   - 可进入第一张卡。

10. 提交时只 stage 小文本产物，不 stage 原始媒体/segment wav/PDF/JPG。

## 9. 本次 commit 事实

L23 内容上线 commit：

- VibeVoice：`074c123 Capture L23 lesson knowledge for card generation`
- 数据仓库：`008166d Ship L23 knowledge checkpoints into 8501`

L23 可见性修复与本文档应作为后续 app commit 提交。
