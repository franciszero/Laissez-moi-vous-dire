# 设计：lesson manifest + 8501 知识点 checkpoint 复习

日期：2026-06-17　状态：用户已同意设计，待写 plan。非 git 仓库（不提交）。
关联：`docs/MEMO-2026-06-17-manifest-checkpoint.md`（背景/续命）。

## 目标
1. 定一份**每课机器合同 manifest（JSON）**：把 doc 讲的每个 chunk 强制归桶（vocab/drill/checkpoint/skip），从而**覆盖率可清点**。
2. 8501 新增**「📝 知识点」checkpoint 复习**（卡片：能机判就机判，否则自评），复用现有遗忘曲线 SRS——给长尾知识兜底，消除“两天忘光”。
3. 一份 manifest → 机械派生多产物 + 一张覆盖报告。

## 不做（YAGNI）
- `drill` 桶只在 schema 留位，**不实现**渲染（冠词/变位/配合以后各自小项目）。
- 8501 里的“覆盖率页面”不做（先脚本报告）。
- checkpoint 掌握度**不**强并入词表色卡（卡片走自己的 due/interval）。
- 不动现有 vocab.json 听写链路（manifest 可派生 vocab.json，但 L21 已有，不强制覆盖）。

## 一、manifest 格式（`../L<n>/manifest.json`）
```json
{
  "lesson": "L21",
  "source": "L21_final_working.md",
  "chunks": [
    {"id": "c08", "title": "简单将来时：别老依赖 aller+inf", "bucket": "checkpoint",
     "items": [
       {"type": "checkpoint", "id": "L21:c08:0",
        "front": "把『我明天走』改成简单将来时", "back": "Demain, je partirai.（-ai/-as/-a…）",
        "answer": null, "tags": ["futur-simple"]}
     ]},
    {"id": "c12", "bucket": "vocab",
     "items": [{"type": "vocab", "fr": "le quartier", "pos": "nom", "zh": "社区，街区", "example": "J'habite dans un quartier calme."}]},
    {"id": "c01", "bucket": "skip"}
  ]
}
```
**字段规则（校验器强制）：**
- 顶层：`lesson`(str), `source`(str), `chunks`(list) 必填。
- 每个 chunk：`id`(str,课内唯一)、`bucket` ∈ {vocab,drill,checkpoint,skip} 必填。`bucket!="skip"` 时 `items` 非空。
- `type=="checkpoint"`：`id`(全局稳定，规则 `"{lesson}:{chunk_id}:{idx}"`)、`front`、`back` 必填；`answer`(str|null，有则机判)、`tags`(list,可选)。
- `type=="vocab"`：`fr`、`pos`、`zh` 必填；`example`(可选)。`fem`/`fem_raw` 由 `vocab.feminine_form` 在派生时补。
- `type=="drill"`：本期只校验 `pattern`(str) 存在即可，不消费。
- **稳定 id**：checkpoint 的 `id` 重建 manifest 不变 → SRS 进度不丢。

校验器 `manifest.validate(data) -> list[str]`（返回问题列表，空=通过）：缺字段、bucket 非法、非 skip 但 items 空、checkpoint 缺 front/back、id 重复 → 各报一条。

## 二、派生脚本
- `scripts/manifest_build.py <manifest.json>`：
  - 校验（不过就报错退出）。
  - vocab 条目 → 重新生成同目录 `vocab.json`（复用 `vocab.parse_uploaded` 等价逻辑 + `feminine_form`）+ `anki_batch_<lesson>.txt`。
  - checkpoint 条目 → 不单独落文件（8501 直接读 manifest）；仅打印计数。
- `scripts/coverage_report.py <manifest.json>`：输出 markdown 表——每 chunk: id/title/bucket/条目数；末尾各桶合计 + **缺口清单**（校验器返回的问题）。证明“没漏”。

## 三、DB：checkpoint 的 SRS 状态（内容在 JSON，状态在 DB，按稳定 id 关联）
新表（`init_db` 加，迁移式 CREATE IF NOT EXISTS）：
```sql
CREATE TABLE IF NOT EXISTS checkpoints (
  card_id TEXT PRIMARY KEY,      -- = manifest 里 checkpoint.id
  lesson TEXT NOT NULL,
  correct_streak INTEGER NOT NULL DEFAULT 0,
  interval_days INTEGER NOT NULL DEFAULT 0,
  due_at TEXT,
  last_seen_at TEXT,
  created_at TEXT NOT NULL
)
```
- 排期复用现有词的间隔逻辑：把 `record_attempt` 里那段 `intervals[min(streak-1,len-1)]` 抽成 `srs.next_schedule(correct_streak, ok, now) -> (correct_streak, interval_days, due_at)`，词与卡共用。
- 内容（front/back/answer/tags）来自 manifest，不入库（改 manifest 不需迁移）。

## 四、8501「📝 知识点」功能
- **加载**：`load_checkpoints()` 扫 `../L*/manifest.json`，取 `bucket==checkpoint` 的 items → `{lesson: [card,...]}`（card 含 id/front/back/answer/tags）。`@st.cache_data`，「🔄 重新扫描」一并清。
- **同步状态**：`ensure_checkpoint_rows(cards)` 对新 card_id 插 checkpoints 行（due_at=now，立即可练）。
- **侧栏入口**：「学习」块加 `📝 知识点（N）`，N=当前选课的卡数（或到期数）。点了 → `start_checkpoint_round(lesson)`。
- **独立状态（不复用词的引擎）**：checkpoint 走**自己的一套 session 状态** `cp_active`(bool)、`cp_pool`(card_id 列表)、`cp_index`、`cp_show_back`(bool)，**绝不碰** `pool/index/current_word/render_practice`（那是听写词引擎，current_word 是词，混用会崩）。主区渲染处：`if st.session_state.get("cp_active"): render_checkpoint() else: (现有 _show_card / render_practice 分支)`。`start_checkpoint_round` 只设 cp_* 并 `cp_active=True`；卡内「退出知识点」按钮置 `cp_active=False`。round 存档(`save_round`)本期不含 cp_*（退出即清，简单优先）。
- **渲染（新 `render_checkpoint(card)`）**：
  - 显示 `front`。
  - `card["answer"]` 非空 → 文本框 + 提交 → `matcher.check_fr(ans, answer)` 机判（对/错）→ 显示 back → 更新排期。
  - `answer` 为空 → 「揭示答案」按钮 → 显示 `back` → 「✅ 我对 / ❌ 我错」自评 → 更新排期。
  - 排期：`srs.next_schedule` 写回 checkpoints 行。
- **到期提醒**：顶部 banner 现有“今天到期 K 词”旁，加“知识点到期 M 张”（或合并）。
- **复用**：自评 UI 照 `render_speak` 的「算我对/算我错」；机判照打字提交。掌握度/着色本期不做，先纯 due/interval。

## 五、L21 交付
- 写 `../L21/manifest.json`：vocab 桶=现成 94 词（按 chunk 归并，或先放一个 vocab chunk）；checkpoint 桶=从 `L21.docx` 各 Chunk 抽（用法提点、辨析、规则、造句要求）；skip=寒暄/重复/纯听写复盘旁白。
- 跑 `coverage_report.py` 出报告给用户看。

## 六、验证
- 单测：`manifest.validate`（好/各种坏样例）；`srs.next_schedule`（连对间隔递增、答错重置）。
- AppTest（备份真实 DB 后）：进「📝 知识点」→ 机判卡 提交对/错；自评卡 揭示→我对；确认 checkpoints 行 due_at 更新、无异常。
- 全量 pytest 绿；重启 health 200/0 报错。

## 七、改动清单
- 新增：`manifest.py`(schema+validate)、`srs.py`(next_schedule，词与卡共用)、`scripts/manifest_build.py`、`scripts/coverage_report.py`、`../L21/manifest.json`。
- 改：`app.py`(init_db 加 checkpoints 表；load_checkpoints/ensure_rows；侧栏入口；render_checkpoint 分支；banner)；`store.py`(可放 checkpoint DB 读写)；`record_attempt` 改用 `srs.next_schedule`。
