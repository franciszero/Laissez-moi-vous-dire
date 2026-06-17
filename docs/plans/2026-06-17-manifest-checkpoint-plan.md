# manifest + checkpoint 实施计划（2026-06-17）

> 用 superpowers:executing-plans 逐任务做。**非 git**：「commit」=跑 pytest/AppTest 验证。多行 bash 开头 `set +e`。改 app.py 后**全量重启**。碰真实 DB 先 `cp dictation.db /tmp/dictation.db.bak`、测完还原。
> 设计见 `docs/specs/2026-06-17-manifest-checkpoint-design.md`；背景见 `docs/MEMO-2026-06-17-manifest-checkpoint.md`。
> 验证基线：当前 `python3 -m pytest -q` = 39 passed。

**Goal:** 落地 lesson manifest（JSON 合同+校验+覆盖报告）+ 8501「📝 知识点」checkpoint 复习（机判/自评，复用 SRS）。

---

### Task 1: `srs.py` 统一排期（词与卡共用）
**Files:** Create `srs.py`; Test `tests/test_srs.py`; 之后 Task 4 让 `record_attempt` 复用。

- [ ] **Step 1 失败测试** `tests/test_srs.py`：
```python
from datetime import datetime
import srs

def test_next_schedule_correct_grows():
    now = datetime(2026,6,17,12,0,0)
    s1,i1,d1 = srs.next_schedule(0, True, now)     # 第一次答对
    s2,i2,d2 = srs.next_schedule(s1, True, now)    # 再答对
    assert s1 == 1 and s2 == 2
    assert i2 >= i1 >= 1                            # 间隔不减
    assert d1 > now                                 # due 在未来

def test_next_schedule_wrong_resets():
    now = datetime(2026,6,17,12,0,0)
    s,i,d = srs.next_schedule(5, False, now)
    assert s == 0 and i == 0                        # 答错重置
```
- [ ] **Step 2** `python3 -m pytest tests/test_srs.py -q` → FAIL（no module srs）
- [ ] **Step 3 实现** `srs.py`（间隔表对齐现有 `record_attempt`，先看 app.py 里 `intervals = [...]` 的值照搬）：
```python
from datetime import datetime, timedelta

INTERVALS = [1, 2, 4, 7, 15, 30, 60]   # 与 app.record_attempt 现用值一致；若不同，以 app 为准改这里

def next_schedule(correct_streak: int, ok: bool, now: datetime | None = None):
    """返回 (correct_streak, interval_days, due_at_iso)。答对涨间隔，答错重置。"""
    now = now or datetime.now()
    if ok:
        streak = correct_streak + 1
        interval = INTERVALS[min(streak - 1, len(INTERVALS) - 1)]
    else:
        streak = 0
        interval = 0
    due = now + timedelta(days=interval)
    return streak, interval, due.isoformat(timespec="seconds")
```
- [ ] **Step 4** pytest tests/test_srs.py → PASS
- [ ] **Step 5** 全量 pytest → 绿（先确认 app.py 的 intervals 与 INTERVALS 一致，不一致则改 srs 对齐，**别动 app 行为**）

---

### Task 2: `manifest.py` 校验
**Files:** Create `manifest.py`; Test `tests/test_manifest.py`

- [ ] **Step 1 失败测试**（覆盖：合法、缺 bucket、bucket 非法、非 skip 但 items 空、checkpoint 缺 back、id 重复）：
```python
import manifest

GOOD = {"lesson":"L21","source":"x.md","chunks":[
  {"id":"c1","bucket":"vocab","items":[{"type":"vocab","fr":"le quartier","pos":"nom","zh":"社区"}]},
  {"id":"c2","bucket":"checkpoint","items":[{"type":"checkpoint","id":"L21:c2:0","front":"f","back":"b","answer":None}]},
  {"id":"c3","bucket":"skip"}]}

def test_validate_good():
    assert manifest.validate(GOOD) == []

def test_validate_catches():
    bad = {"lesson":"L21","source":"x","chunks":[
      {"id":"c1"},                                            # 缺 bucket
      {"id":"c2","bucket":"zzz","items":[]},                  # bucket 非法
      {"id":"c3","bucket":"vocab","items":[]},                # 非 skip 但空
      {"id":"c4","bucket":"checkpoint","items":[{"type":"checkpoint","id":"a","front":"f"}]}, # 缺 back
    ]}
    probs = manifest.validate(bad)
    assert len(probs) >= 4
```
- [ ] **Step 2** pytest → FAIL
- [ ] **Step 3 实现** `manifest.py`：
```python
import json

BUCKETS = {"vocab", "drill", "checkpoint", "skip"}

def validate(data: dict) -> list[str]:
    probs = []
    for k in ("lesson", "source", "chunks"):
        if k not in data:
            probs.append(f"顶层缺字段 {k}")
    seen_ids = set()
    for i, ch in enumerate(data.get("chunks", [])):
        tag = ch.get("id", f"#{i}")
        if "id" not in ch: probs.append(f"chunk {tag} 缺 id")
        b = ch.get("bucket")
        if b not in BUCKETS:
            probs.append(f"chunk {tag} bucket 非法/缺失: {b!r}")
        items = ch.get("items") or []
        if b != "skip" and not items:
            probs.append(f"chunk {tag} 非 skip 但 items 为空")
        for it in items:
            t = it.get("type")
            if t == "checkpoint":
                for f in ("id", "front", "back"):
                    if not it.get(f): probs.append(f"chunk {tag} checkpoint 缺 {f}")
                cid = it.get("id")
                if cid in seen_ids: probs.append(f"checkpoint id 重复: {cid}")
                seen_ids.add(cid)
            elif t == "vocab":
                for f in ("fr", "pos", "zh"):
                    if not it.get(f): probs.append(f"chunk {tag} vocab 缺 {f}")
            elif t == "drill":
                if not it.get("pattern"): probs.append(f"chunk {tag} drill 缺 pattern")
            else:
                probs.append(f"chunk {tag} item type 非法: {t!r}")
    return probs

def load(path: str) -> dict:
    return json.loads(open(path, encoding="utf-8").read())

def checkpoints(data: dict) -> list[dict]:
    out = []
    for ch in data.get("chunks", []):
        if ch.get("bucket") == "checkpoint":
            out += [it for it in ch.get("items", []) if it.get("type") == "checkpoint"]
    return out

def vocab_items(data: dict) -> list[dict]:
    out = []
    for ch in data.get("chunks", []):
        if ch.get("bucket") == "vocab":
            out += [it for it in ch.get("items", []) if it.get("type") == "vocab"]
    return out
```
- [ ] **Step 4/5** pytest tests/test_manifest.py → PASS；全量 → 绿

---

### Task 3: 覆盖报告脚本
**Files:** Create `scripts/coverage_report.py`
- [ ] **Step 1 实现**：
```python
#!/usr/bin/env python3
"""coverage_report.py <manifest.json>：打印 每chunk→桶 表 + 各桶合计 + 缺口清单。"""
import sys, pathlib, collections
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import manifest

def main(p):
    d = manifest.load(p)
    print(f"# 覆盖报告 {d.get('lesson')}  source={d.get('source')}")
    cnt = collections.Counter()
    print("\n| chunk | bucket | 条目 | 标题 |\n|---|---|---|---|")
    for ch in d.get("chunks", []):
        b = ch.get("bucket"); n = len(ch.get("items") or [])
        cnt[b] += 1
        print(f"| {ch.get('id')} | {b} | {n} | {ch.get('title','')[:40]} |")
    print("\n桶合计:", dict(cnt))
    probs = manifest.validate(d)
    print("\n缺口/问题:", "无 ✅" if not probs else "")
    for x in probs: print(" -", x)

if __name__ == "__main__":
    main(sys.argv[1])
```
- [ ] **Step 2 验证**（等 Task 6 有 L21 manifest 后跑）：`python3 scripts/coverage_report.py ../L21/manifest.json`

---

### Task 4: DB checkpoints 表 + store 读写 + record_attempt 复用 srs
**Files:** Modify `app.py`(init_db, record_attempt), `store.py`(加 checkpoint 读写)
- [ ] **Step 1** `app.py` `init_db` 加（紧挨 words.hidden 迁移后）：
```python
    cur.execute("""
    CREATE TABLE IF NOT EXISTS checkpoints (
        card_id TEXT PRIMARY KEY, lesson TEXT NOT NULL,
        correct_streak INTEGER NOT NULL DEFAULT 0,
        interval_days INTEGER NOT NULL DEFAULT 0,
        due_at TEXT, last_seen_at TEXT, created_at TEXT NOT NULL)
    """)
```
- [ ] **Step 2** `store.py` 加（用 srs 排期；内容不入库）：
```python
def ensure_checkpoint(card_id: str, lesson: str) -> None:
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO checkpoints (card_id,lesson,due_at,created_at) VALUES (?,?,?,?)",
                 (card_id, lesson, _now(), _now()))
    conn.commit(); conn.close()

def get_checkpoint_state(card_ids):
    card_ids = list(card_ids)
    if not card_ids: return {}
    conn = get_conn(); ph = ",".join(["?"]*len(card_ids))
    rows = conn.execute(f"SELECT card_id,correct_streak,interval_days,due_at FROM checkpoints WHERE card_id IN ({ph})", card_ids).fetchall()
    conn.close()
    return {r[0]: {"correct_streak":r[1],"interval_days":r[2],"due_at":r[3]} for r in rows}

def update_checkpoint(card_id: str, ok: bool) -> None:
    import srs
    conn = get_conn()
    row = conn.execute("SELECT correct_streak FROM checkpoints WHERE card_id=?", (card_id,)).fetchone()
    streak = row[0] if row else 0
    ns, ni, due = srs.next_schedule(streak, ok)
    conn.execute("UPDATE checkpoints SET correct_streak=?,interval_days=?,due_at=?,last_seen_at=? WHERE card_id=?",
                 (ns, ni, due, _now(), card_id)); conn.commit(); conn.close()
```
- [ ] **Step 3** `record_attempt`（app.py）把那段算 interval/due 的逻辑换成 `srs.next_schedule(...)`（**保持行为等价**；先读现有代码确认 streak/字段名）。`import srs`。
- [ ] **Step 4 验证** 全量 pytest 绿 + py_compile app.py store.py。

---

### Task 5: 8501「📝 知识点」功能（独立状态，不碰词引擎）
**Files:** Modify `app.py`
- [ ] **Step 1** loader（放在 load_vocab 附近，带 `@st.cache_data`）：
```python
@st.cache_data(show_spinner=False)
def load_checkpoints():
    import manifest as mf
    out = {}
    for vj in sorted(BASE_DIR.glob("L*/manifest.json")):
        try: d = mf.load(str(vj))
        except Exception: continue
        cards = mf.checkpoints(d)
        if cards: out[d.get("lesson", vj.parent.name)] = cards
    return out
```
  「🔄 重新扫描词表」里一并 `load_checkpoints.clear()`。
- [ ] **Step 2** session 默认：`cp_active=False, cp_pool=[], cp_index=0, cp_show_back=False`。
- [ ] **Step 3** 侧栏「学习」块（变形按钮后）加：
```python
    _cards = load_checkpoints().get(chosen_lesson, [])
    if st.button(f"📝 知识点（{len(_cards)}）", disabled=not _cards):
        for c in _cards: store.ensure_checkpoint(c["id"], chosen_lesson)
        st.session_state.cp_active = True
        st.session_state.cp_pool = [c["id"] for c in _cards]
        st.session_state.cp_index = 0
        st.session_state.cp_show_back = False
        st.rerun()
```
- [ ] **Step 4** `render_checkpoint()`：按 cp_index 取 card（从 `load_checkpoints()` 按 lesson 找 id），显示 front；有 answer→表单 check_fr 机判；无→揭示 back→我对/我错；判完 `store.update_checkpoint(id, ok)`、`cp_index+=1`、超界提示“这组复习完”+退出。含「退出知识点」按钮(`cp_active=False`)。卡内容按 id 在当前课卡里查。
- [ ] **Step 5** 主渲染分叉（在现有 `if _show_card... else render_practice()` 外层）：
```python
if st.session_state.get("cp_active"):
    render_checkpoint()
else:
    # 现有 banner + _show_card/render_practice 原样
```
- [ ] **Step 6 验证** AppTest（备份 DB）：选 L21 →「📝 知识点」点开 → 渲染无异常；机判卡提交、自评卡揭示+我对，确认 checkpoints 行 due_at 变化。

---

### Task 6: L21 manifest 创作 + 覆盖报告
**Files:** Create `../L21/manifest.json`
- [ ] **Step 1** 写 manifest：
  - vocab 桶：现成 94 词（可放一个 `{"id":"vocab","bucket":"vocab","items":[...94...]}`，items 用 `../L21/vocab.json` 的 fr/pos/zh/example 回灌；pos 转 nom/verbe/adj/adv/expression 或保留——本期 8501 不消费 vocab item，宽松）。
  - checkpoint 桶：从 `L21.docx` 各 Chunk（用 §6/MEMO 的解析法）抽：用法提点（aller+inf→简单将来时）、辨析（gare/guerre、remplir≠compléter）、规则（-té 多阴性、复合过去时性数配合三情况、国家阴阳性 en/au）、造句要求等。每张给 front/back，能定答案的填 answer。**id 用 `L21:<chunkid>:<idx>`**。
  - skip 桶：寒暄/重复/纯听写旁白。
- [ ] **Step 2** `python3 manifest.py` 不可直接跑——用 `python3 -c "import manifest;print(manifest.validate(manifest.load('../L21/manifest.json')))"` 校验=`[]`。
- [ ] **Step 3** `python3 scripts/coverage_report.py ../L21/manifest.json` 出报告给用户。

---

### Task 7: 全量验证 + 重启 + 文档同步
- [ ] 全量 pytest 绿（39 + 新增 srs/manifest 用例）。
- [ ] 重启 server，health 200/0 报错；选 L21 点「📝 知识点」实测一张机判+一张自评。
- [ ] 更新 `HANDOFF.md`(§3 加 checkpoint+manifest；文件地图加 manifest.py/srs.py/scripts) 与 `MEMO-...md`(标本项目完成度)。

## 自检
- Spec 覆盖：manifest(T2)+派生/覆盖(T3,T6)+SRS(T1,T4)+checkpoint功能(T5)+L21(T6)+验证(T7) ✅。
- 命名一致：`srs.next_schedule`、`manifest.validate/load/checkpoints/vocab_items`、表 `checkpoints.card_id`、session `cp_active/cp_pool/cp_index/cp_show_back`、card `id/front/back/answer/tags` 全程一致。
- 风险：①record_attempt 改用 srs 要保证行为等价（先核对现有 intervals 值再写 srs.INTERVALS）；②checkpoint 独立状态绝不碰 pool/current_word（已在 spec §四 钉死）；③load_checkpoints 缓存——加课/改 manifest 要点「重新扫描」。
