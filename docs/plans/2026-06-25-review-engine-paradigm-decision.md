# 决策记录：复习引擎四层范式 —— 评估后推迟（只做 R0 + R3）

最后更新：2026-06-25。状态：**已定（采纳降级版）**。
配套：[`2026-06-23-unified-review-engine.md`](2026-06-23-unified-review-engine.md)（本记录**更新**它的 "P2/P3 next" → 推迟）、
[`2026-06-22-knowledge-unification.md`](2026-06-22-knowledge-unification.md)、[`2026-06-24-handoff.md`](2026-06-24-handoff.md)、`HANDOFF.md §5`。
基线：HEAD=`5fa3005`，`101 passed`，工作树干净。

## 0. 一句话

评估过把词/卡两套循环合进一个四层 hexagonal 架构（`ReviewSession` over `ReviewItem`）。**Gap 属实，但处方 over-scoped**。
决定：只做**安全网（R0）** + **LLM 生命周期收口（R3，小独立模块）**；把会话/协议合并（R1/R2）和表现层拆分（R4）**推迟**，记下重访触发条件。

## 1. 背景

- 个人单用户 French 听写/复习 Streamlit 工具（~2357 行 `app.py` + 一组纯小模块 + 薄 adapters）。两个核心：
  - **听写 = 背单词**：5 维 Wilson 掌握度、Anki 联动、`words.due_at` 遗忘曲线，效果可量；
  - **知识点复习**：checkpoint / conj / production 三种卡，单 streak SRS。
- [`2026-06-23-unified-review-engine.md`](2026-06-23-unified-review-engine.md) 提出 P2/P3：合并 `attempts`/`srs` 表 + 一个 `ReviewSession` over `ReviewItem`，标为 "next"。
- 本轮：先提出"四层范式 + 协议 + 适配器"的完整迁移方案，经独立审核 + 逐条核对仓库后**降级**。

## 2. 评过的范式（保留供参考，**非待办**）

四层、依赖单向（外→内）：

| 层 | 内容 | 现状 |
|---|---|---|
| Presentation | 薄 Streamlit 壳 + 按 `kind` 渲染 | ❌ 与下层糊在一起 |
| Application | `review/`：`ReviewSession`、`ReviewItem` 协议、`due_today`、生命周期 | ❌ 整层缺失，糊在 `app.py` |
| Domain | matcher/mastery/srs/conjugate/aigrade/roundlogic/vocab | ✅ 已是纯小模块 |
| Ports & Adapters | store/anki/asr/llm/macdict/say | ✅ 已薄、已隔离 |

## 3. Gap（核对属实，作现状记录）

- **Domain ✅、Adapters ✅** 已是最佳实践，风险最高的内核已干净。
- 缺一整层 **Application**，糊在 `app.py`：循环写了两遍（词 `pool/index/roundlogic/start_*` vs 卡 `cp_cards/cp_index/_start_cards`）、到期手拼（banner）、LLM 生命周期散在 3 处。
- 表现层与 application/持久化糊在一起；卡侧 `render_checkpoint` 按 `kind` 分派**已是多态的种子**（3 种 kind，含 P4 的 production），词在它之外。
- 量化（HEAD `5fa3005`）：词路径 `render_practice` **244** + 念法语子系统 **~129** + `render_word_panel` 86 ≈ **370+ 有状态行**；任一卡 kind `_render_production_card` **79** / `_render_conj_card` **68**。

## 4. 决定

**做：**

- **R0 窄安全网（按 R3 实际爆炸半径裁，非按推迟的 R1/R2 裁）**：R3 只动 LLM 生命周期，故 R0 只需把 load-on-submit / idle-unload / leave-unload / **绝不写 config** 这四条行为用测试钉死（`test_llm*.py` 已有部分，补全缺口）。**「词 + 卡全流程特征测试」是一般卫生、随 R1 一起推迟，不作 R3 的 gating**——否则就和本文档自己的 YAGNI 论证相左。（当前基线 101 绿。）
- **R3 生命周期收口**：把 LLM load/unload 的 *policy*（提交首次加载 + 闲置卸载 + 离开卸载 + **绝不写 `~/.hermes/config.yaml`** 不变量）收进**一个小独立模块**（与 `llm.py` 这个 *mechanism* adapter 分开）。**不**顺手立 `review/` 包。
  - 验收必须含：在真实会话确认 P4 AI 卡仍"提交首次加载 / 闲置卸载"（内存 47→23GB）——此项**不可纯代码验**，需在场跑。
- **扩展 `llm-graded-practice` skill**（不新建）：~~写入"确定性信任边界"不变量~~ —— **更正（2026-06-25）：该不变量已在 skill 第 1/2/7/8 点，无需重写**；Task 4 缩为只补"生命周期独立模块"这一新学习。详见 [`2026-06-25-llm-lifecycle-r0-r3-plan.md`](2026-06-25-llm-lifecycle-r0-r3-plan.md)。

**不做（推迟）：**

- R1（把 `ReviewSession` 抽到词循环）、R2（`ReviewItem` 协议 + 4 适配器）、R4（拆 `ui/render_<kind>`）。
- 新建 `add-review-item-kind` skill（为还没验证的协议写可复用方法论 = 固化投机抽象）。

**明确永不做（除非另起目标）：**

- A：合并 `attempts`/`srs` 表（词 `attempts` 带 skill 维、驱动热力图，是**本质多态非重复**）。
- 跨课共享 mastery / registry。

## 5. 为什么推迟（三条，核对过仓库）

1. **协议不对称 → 错误抽象风险。** 词 370+ 行 vs 卡 ~70 行；硬塞进一个 `ReviewItem.render()/mastery()/history()` → 一个肥词适配器 + 协议被迫长出只服务词的特例方法（泄漏）。
2. **YAGNI。** 抽象门槛 = 出现**具体的第三个跨切面需求**逼着写第三套。现无。第二套（卡）已写完在跑、痛感有限；真正咬过的那处重复（到期 banner）已用普通 helper 修好（`_start_cards`，`8f8b51e`），**没用上协议**。
3. **风险排序。** 词循环是每天早上要用、耦合最深的主驱动，且真实 `say()`/ASR/计时/5 模式交互 AppTest 测不了。不为投机收益重构它。

## 6. 重访触发条件

出现**一个具体的第三种跨切面复习类型**，不抽象就得把"队列 / 到期 / 历史"再抄第三遍 —— 那时再考虑 `ReviewSession`/`ReviewItem`：
**卡侧先做、证明划算，词循环当决策闸**（塞不进而别扭 = 停手信号，不是硬塞信号），且仍不做 A。

## 7. 两条值得记成 doctrine 的不变量

- **多态非重复**：词 5 维 Wilson 掌握度 + Anki 联动，**永不**并进卡的单 streak。
- **确定性信任边界**：答案键**恒确定性**（`conjugate`/`matcher`）；LLM 是建议性 adapter，其输出在 domain 内逐字复核（`aigrade.anchor_and_segment`）。"LLM 是陪练不是教科书" = 架构规则。

## 8. 相关工作现状（以仓库为准）

- P0/P1/P4 已落：`8f8b51e`(P0+P1：删死 `conj_active` / 抽 `_start_cards` / 到期合一 banner) → `4ea0f15`·`810d113`(P4a) → `b745cc5`(P4b：AI 成 card kind)。到期现为**唯一入口**。
- HEAD=`5fa3005`，`101 passed`，工作树干净。**对话里曾有 D1/D2/D4 与 P0/P1/P4 两套叙事——以仓库 P 系为准。**
