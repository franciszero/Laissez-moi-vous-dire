# 架构：统一复习引擎（消除词/卡两套平行引擎）

> **⚠️ P2/P3 已推迟（2026-06-25）**：经独立审核，词↔卡合并被判 over-scoped（不对称协议 + YAGNI + 风险排序）。本文档的 **P2/P3「next」不再是既定待办**；现状只做 R0（窄安全网）+ R3（生命周期收口）。决定、理由与重访触发条件见 [`2026-06-25-review-engine-paradigm-decision.md`](2026-06-25-review-engine-paradigm-decision.md)。**P0/P1/P4 仍有效。**

最后更新：2026-06-23。背景：product-story-critique 评审 + 用户决定**作废 HANDOFF §5 的"等 3+ 处再抽象"**——架构上不允许同一概念重复开发。

## 关键判断框架：区分「重复」与「本质差异」
不是所有"两套实现"都是重复。消重时必须分清，否则会把好东西也合掉：
- **真·重复（必须合成一套）**：同一概念写了两遍——队列(`pool`/`cp_cards`)、当前位(`current_word`+`index`/`cp_index`)、到期(`get_due_wrong_words`/`get_due_checkpoints`)、开轮、历史(`attempts`/`checkpoint_attempts`)、排期(`words.due_at`/`checkpoints`表)、底部 router、D1 那个拼出来的到期 banner。
- **本质差异（保留，是多态不是重复）**：词有 5 维技能 + Wilson/半衰期热力图；卡是单一 streak/interval。硬合会给卡塞无用维度或砍掉词的热力图。
- **一句话：机制统一，内容多态。**

## 目标架构
`ReviewItem`（统一接口）：`id / kind / due_at / render() / grade(answer) / on_result(ok) / mastery()`。
kind ∈ `word:听写/产出/理解/音/变 | checkpoint | conj | production`。

| 引擎部件 | 现状（重复） | 统一后（一份） |
|---|---|---|
| 队列/一轮/批次/导航 | pool+cp_cards+roundlogic+cp_index | 一个 `ReviewSession(items, batch)` |
| 到期 | get_due_wrong_words + _due_checkpoint_cards | 一个 `due_today()` 跨所有 kind |
| 历史 | attempts + checkpoint_attempts | 一张 `attempts(item_id, kind, ok, ts, answer)` |
| 排期 | words.due_at + checkpoints 表 | 一张 `srs_state(item_id, kind, streak, interval, due_at)` |
| 渲染分派 | if llm/cp/else + kind 分支 | 一个 `render(item)` 多态 |

**保留多态（非重复）**：词的 5 维 Wilson 掌握度 + 热力图（词 item 专有）；各 kind 的 render/grade。

## 迁移分期（每期可上线、测试绿、绝不弄坏每天用的词流程）
- **P0 ✅（零风险清理）**：删死状态 `conj_active`（init+6 处）；抽 `_start_cards(cards,label,lesson)` 消三处复制。
- **P1 ✅（到期合并）**：banner 当**唯一**到期入口（按选课作用域，词+卡）；撤掉侧栏「到期」「🔁知识点·到期」两个按钮。注：词/卡仍是 banner 里两个按钮（动作真合并 = P3 的共同队列）。
- **P2（历史统一，需在场）**：一张 attempts 表收所有 kind。**触及 word `attempts`（驱动热力图）**——要迁移、别丢历史、别动 mastery 计算。风险中。
- **P3（核心引擎合并，需在场）**：`render_practice`+`render_checkpoint` → 一个 `ReviewSession` over `ReviewItem`。**改写每天用的词流程**——最高风险，测试驱动+增量+逐步回滚。先让词流程跑新引擎而行为不变。
- **P4 ✅（提前到 P2/P3 之前做，因为只需卡侧 + 用户在场验模型）**：AI 精练退化成 deck 里的 `kind=production` 卡（`_render_production_card`，提交时按需加载模型）；删除独立 `render_llm_practice`/`_render_llm_exercise`/🤖 按钮/`llm_active`/router 分支。闲置卸载提到顶层兜底。**实测**(用户)：提交加载、批改、内存 47→23GB 卸载。**卡侧三类(checkpoint/变位/产出)已统一在一个 deck + 一套 render_checkpoint 分派。**

### 仍剩（词↔卡引擎合并，最深的一层，最大风险）
卡侧已统一；**词引擎(render_practice/pool/roundlogic/attempts/words.due_at)仍与卡引擎平行**。
- **P2（历史统一）**：一张 attempts 表收词+卡；触及驱动热力图的 word `attempts` + DB 迁移。
- **P3（会话/渲染合并）**：`render_practice`+`render_checkpoint` → 一个 `ReviewSession` over `ReviewItem`；**改写每天用的词流程**。
这两步是真正把"两套引擎"合一的核心，但都重写成熟的词流程 + 动 DB，建议作为**独立专注的一轮**做（测试驱动、增量、逐步回滚），别在长 session 尾部赶。

## 风险与边界
- P2/P3 触及成熟的词流程 + 现有 DB（attempts / words.due_at / checkpoints）→ 必须用户在场、写迁移、AppTest 全覆盖、每步可回滚。
- 词 due 是"词级"、掌握度是"技能级"——统一排期表时保持这个粒度。
- 仍**不做**跨课共享 mastery/registry（那是另一回事，不是本次消重目标）。

## 待用户拍（P1 已按"banner 唯一"落地，可回滚）
- 到期入口=banner（已做）。如想反过来（侧栏当家），git revert 本期即可。
- P2/P3 节奏：建议在场 + smoke test 真词流程后再推。
