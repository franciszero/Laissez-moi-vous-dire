# 备忘录 · manifest + checkpoint 项目（2026-06-17）

> 给被打断后续命的 agent：读这一份就能接着干。通用项目信息在 `HANDOFF.md`，这份只记**这个新项目**的来龙去脉 + 当前进度 + 下一步。

## 0. 现在进行到哪 / 下一步

### ✅ 项目完成（2026-06-17）—— Task 1–7 全做完并验证
- 新模块：`srs.py`、`manifest.py`、`scripts/coverage_report.py`（各带测试/烟测）。
- DB：`checkpoints` 表 + `store.ensure_checkpoint/get_checkpoint_state/update_checkpoint`。
- 8501：`load_checkpoints`、侧栏「📝 知识点(N)」、`render_checkpoint`（机判/自评）、主区 `cp_active` 分叉（独立状态，不碰词引擎）。
- L21：`../L21/manifest.json` 已升级为正式复习 deck（94 vocab + **85 张知识点卡**：73 张 reviewed species checkpoint 卡 + 12 张混合代词作业复习卡；来源为 VibeVoice 的 `docs/french-wiki/census/recapture/reconciled/L21.species.json`；`coverage_report.py` 显示 `species 覆盖: 73/73`）。
- 验证：全量 **50 passed**（含 L21 manifest 73/73 species 覆盖测试 + 12 张代词复习卡不泄露原题答案测试）；AppTest 知识点流程渲染无异常；重启 health 200/0 报错。
- **故意没做（YAGNI/降risk）**：`drill` 桶渲染；`record_attempt`→srs 的 DRY 重构（行为不变，留着）；8501 覆盖率页面（先用脚本）；`scripts/manifest_build.py`（vocab/anki 派生器，计划里有，本期没做——L21 的 vocab.json/anki 已手工产出）。
- **卡片精修机制（2026-06-17 续）**：`../L21/L21.card_overrides.json`（按 `species_label` 覆盖 front/back/answer）+ `build_checkpoints_from_species.py --overrides` 合并。卡 id 稳定 → 重建不丢精修/SRS。**L21 73/73 全部精修完成（49 机判 check_fr 填空 + 24 中文自评，0 通用模板）**。
- **混合代词作业复习卡（2026-06-17 续）**：L21 末尾老师明确说“这个代词的题没有讲……重新做这个题”，所以 `../L21/manifest.json` 里追加 `pronoun-review-assignment` chunk：12 张 `mixed-pronoun-review` 自评卡，复习 COD/COI/y/en/位置/顺序/做题流程，**不使用截图原题句子、不提供 30 题逐题答案、不计入 species 分母**。
- **两个 git 仓库**：app=`Laissez-moi-vous-dire`(听写/)；数据=`Laissez-moi-me-detendre`(本地录屏课/，忽略听写/与媒体)。
- **后续可做**：新课同法 species→overrides 精修；把自评卡进一步拆成 drill 题型；到期 banner 纳入知识点；drill 桶实现。
- **重建命令**：`python3 scripts/build_checkpoints_from_species.py --lesson L21 --species-json <VibeVoice/.../reconciled/L21.species.json> --vocab-json ../L21/vocab.json --overrides ../L21/L21.card_overrides.json --out ../L21/manifest.json`

### （历史）原始计划与决策见下 ↓
- ✅ brainstorm 完（决策见 §4）、✅ spec 写完（`docs/specs/2026-06-17-manifest-checkpoint-design.md`，含 schema/校验/checkpoints表/独立cp状态）、✅ plan 写完（`docs/plans/2026-06-17-manifest-checkpoint-plan.md`，7 任务 TDD）。
- ✅ **Task 1-3 完成**（都是独立新模块，已验证）：
  - `srs.py`+`tests/test_srs.py`（next_schedule，INTERVALS=[1,2,4,7,15,30] 与 app 一致）
  - `manifest.py`+`tests/test_manifest.py`（validate/load/checkpoints/vocab_items）
  - `scripts/coverage_report.py`（烟测通过）
  - 全量 **50 passed**。
- **下一步：Task 4**（改 app.py/store.py：init_db 加 `checkpoints` 表；store 加 ensure_checkpoint/get_checkpoint_state/update_checkpoint；`record_attempt` 改用 `srs.next_schedule` 保持行为等价）→ T5 8501 知识点 UI（独立 cp_* 状态，**别碰 pool/current_word**）→ T6 写 `../L21/manifest.json` → T7 验证+文档。
- ⚠️ T4-T5 要改 app.py，改完**全量重启**再验。用 executing-plans 逐个做。
- 续命：直接打开 plan 从 Task 2 往下；环境/重启/验证看本文件 §7 与 HANDOFF。

## 1. 用户的真问题（为什么做这个）
用户怕：“**以 8501 为主，老师教的东西只要没纳入 8501，过一两天就忘光**”。
所以目标**不是**“给每类知识点造一个题型”（无底洞），而是：**老师讲的每个点都必须落进‘某种’可复习形态，且覆盖率可清点**（拿 doc/转录当分母）。

## 2. 已拍板的架构（用户“完全同意”）
**两层 + 一个数据合同：**
- **第1层 结构化题（自动判分）**：听写 / 变形(已上线) / 冠词填空 / 动词变位 / 性数配合。给可重复、能机判的硬核。
- **第2层 通用 checkpoint 卡（自评，复用现成遗忘曲线 SRS）**：吃掉整条长尾（如“CHUNK 8：简单将来时别老用 aller+inf”、gare/guerre 辨析、用法提点、造句）。**这层是兜底网，是消除“两天忘光”的关键。**
- **数据合同 = 每课一份 manifest**：严格点放在**结构化 manifest（机器合同）**，**不是** Word 排版。Word 从“源头”降级为“产物”。
  - 两条硬规则：①每条目带类型(vocab|drill|checkpoint)、字段固定可校验；②**源文稿每个 chunk 必须声明归桶(vocab|drill|checkpoint|skip)，没归=校验报错=可见缺口** ← 这就是“覆盖率可清点”。
  - 一份 manifest → 机械派生：vocab.json + anki batch + checkpoint 卡组 + (将来)drill 题集 + 归档 Word。

## 3. 次序决定（关键：它们不独立）
tier-2 的“把 doc 灌成卡组 + 覆盖映射”**本身就是 manifest**（checkpoint 条目 + 归桶校验）。若先临时解析 docx 再做 manifest = docx 抽取写两遍，违背“省计算量”。
- **结构**：manifest=地基；checkpoint 功能=第一个房客（消费 manifest）；结构化题=后续房客（同一 manifest 加 `drill.pattern`）。
- **第一刀（合并项目）**：manifest schema + **L21 manifest**（先填 vocab/checkpoint/skip，drill 桶留位不实现 YAGNI）+ **8501 checkpoint 复习功能**（卡片 UI + 接遗忘曲线）+ 覆盖映射给用户看。
- **后续各自小项目**：冠词填空(白送数据) → 动词变位 → 性数配合。

## 4. brainstorm 决策（用户已答 2026-06-17）
1. ✅ manifest 载体 = **JSON**（和 vocab.json 同栈、可校验）。
2. ✅ checkpoint 判分 = **能填空就机判（卡带确定答案→check_fr），否则揭示背面自评**。
3. ✅ 覆盖映射 = **先生成报告表**（脚本输出 每chunk→桶 + 缺口清单），8501 页面以后再说。
4. （spec 阶段再定）卡组/manifest 存哪（倾向 `../L*/manifest.json`，8501 派生 checkpoint）；checkpoint 的 SRS 排期（倾向单独 `checkpoints` 表 + 复用 record_attempt 的间隔逻辑）。

## 5. 复用什么（checkpoint 功能几乎不用新工程）
8501 已有、直接复用：
- **SRS 排期**：`words.due_at`/`interval_days`、`get_due_wrong_words(due_only)`、`start_lesson_review`、顶部“今天到期 K 词”banner、`mastery.py`(Wilson+按天聚合)。
- **自评 UI 范式**：`render_speak` 的「✅算我对/❌算我错」、中文拿不准的 pending 判定屏。checkpoint 卡 = 揭示背面→自评，同一套。
- **持久化**：`store.py` 的 `app_state` 表 + `save_setting/load_setting` + `save_round`。
- **内容类型范式**：现有 vocab = `../L*/vocab.json` 经 `vocab.load_all_vocab` → `VOCAB`。新内容(checkpoint/drill)照此并列存 `../L*/<something>.json`，加各自 loader。
- **先例**：阴阳性「变形」就是“知识点→互动 pattern”的第一个实例，可参照其 mode/skill/掌握度接法（见 `docs/specs|plans/2026-06-15-*`）。

## 6. L21 素材现状（本轮已产出，可作 manifest 样本）
- 转录文稿（cross-check 源，三套 ASR 合并）：`/Users/francis/Documents/Georgian_College/GitHub/VibeVoice/docker-data/outputs/L21/L21_final_working.md`（1576 行）。
- AI 总结 docx：`../L21/L21.docx`。内含 5 个「核心词汇表」+ 多个 Chunk（每个 Chunk 标题本身常是一个 checkpoint）。
  - **解析坑**：docx 表格用 table-aware 正则；cell 文本正则必须用 `<w:t(?: [^>]*)?>`（别用 `<w:t[^>]*>`，会误吞 `<w:tcPr>`）。
  - **可信度结论**：是“规范化总结”非逐字转录——主题/词义可靠；个别法语词(remplir/fiche/chômage/parcourir)转录里 0 次但概念真实(失业/formulaire/过去完成 都在)，即 AI 把中文讲点补成了标准法语词。可信任，但 manifest 化时对“推断词”的拼写/性数瞄一眼。
- 已产出：`../L21/vocab.json`(94 词，8 个阴性已重建) + `../L21/anki_batch_L21.txt`(94 条，`词(词性;例句)`，与 vocab 一一对应)。⚠️`le Singapour` 通常不带冠词，待用户定。
- 这 94 词的 manifest 化：它们属 vocab 桶；checkpoint/skip 桶要从 docx 其余 chunk 抽。

## 7. 续命操作（环境）
- 跑/验证：`cd .../听写`；多行 bash 开头 `set +e`（本机 shell 开了 errexit）；`python3 -m pytest -q`（现 39 passed）。
- 改了 app.py/被 import 的模块要**全量重启**：`pkill -f "streamlit run app.py"; nohup streamlit run app.py --server.port 8501 --server.headless true >/tmp/dictation_app.log 2>&1 &`，再 `curl ... localhost:8501/_stcore/health`。
- 渲染期错误用 `streamlit.testing.v1.AppTest` 抓；碰真实 DB 先 `cp dictation.db /tmp/bak` 测完还原。
- 详见 `HANDOFF.md` §0/§6。
