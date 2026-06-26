# R0 + R3：LLM 生命周期收口 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把散在 `app.py` 三处的 LLM load/unload *policy* 收进一个小独立模块 `llm_lifecycle.py`，并用窄安全网钉住四条生命周期行为——行为不变、零 DB 改动、不碰词流程。

**Architecture:** 新建纯模块 `llm_lifecycle.py`（policy：何时卸载 + caption 数学），`app.py` 的 `_llm_idle_watch` 改为调用它；`llm.py`（mechanism：起停 rapid-mlx 进程）不动。词练习、卡渲染、DB、SRS 一律不碰。这是 [`2026-06-25-review-engine-paradigm-decision.md`](2026-06-25-review-engine-paradigm-decision.md) 里决定要做的 **R0+R3**，R1/R2/R4 已推迟。

**Tech Stack:** Python 3 · Streamlit 1.58（AppTest）· pytest · SQLite（本计划不触及）。

## Global Constraints

- 分支 `review-engine-r0-r3`（已建，决策记录已提交于 `821b056`，基线 `5fa3005`，101 绿）。每个 Task 独立 commit = 回滚点。
- 跑测试：`python3 -m pytest -q`。**本 sandbox 需关闭沙箱跑**（`numcodecs` native lib 的 code-signature 在沙箱里被拒，是假阴性）；基线 **101 passed**。
- **绝不读写 `~/.hermes/config.yaml`**：生命周期只管 rapid-mlx 子进程（`llm.load`/`llm.unload`），配置仅由 `llm.configured_model()` 只读。
- **答案键恒确定性，LLM 仅建议**——本计划不改判分，仅动资源生命周期。
- 改了被 import 的模块需全量重启 :8501 才在真实 app 生效；CI/验证用 boot 自检模板（见 Task 3）。
- **R3 只动 LLM 生命周期**：`render_practice`/`pool`/`words.due_at`/`attempts`/mastery **一行都不能动**。
- 行为必须**逐字等价**：现有 `tests/test_llm_ui.py::test_idle_watch_unloads_when_model_loaded_and_idle` 是 R3 的集成安全网，重写后必须仍绿。

---

## File Structure

| 文件 | 责任 | 本计划动作 |
|---|---|---|
| `llm_lifecycle.py` | LLM 生命周期 **policy**（何时卸载 + caption 数学 + 不变量的家） | **Create** (Task 2) |
| `llm.py` | rapid-mlx **mechanism**（起停进程、chat、只读配置） | 不动 |
| `app.py` | `_llm_idle_watch` 改用 `llm_lifecycle`；删死常量 `LLM_IDLE_SECONDS` | **Modify** (Task 3) |
| `tests/test_llm_lifecycle.py` | policy 纯函数单测 | **Create** (Task 2) |
| `tests/test_llm.py` | 加「绝不写配置」守卫测试 | **Modify** (Task 1) |
| `tests/test_llm_ui.py` | 加 leave-unload AppTest（补未覆盖行为） | **Modify** (Task 1) |
| `/Users/francis/.codex/skills/llm-graded-practice/SKILL.md` | 记下 R3 的「生命周期独立模块」模式 | **Modify** (Task 4) |

**已有覆盖（不重复）：** `test_llm_ui.py` 已钉 **load-on-submit**（`test_production_card_loads_model_on_submit_and_grades`）和 **idle-unload**（`test_idle_watch_unloads_when_model_loaded_and_idle`）。故 R0 只补**两处缺口**：leave-unload、never-write-config，外加 R3 抽出的纯函数。

---

## Task 1: R0 窄安全网 —— 补未覆盖的两条生命周期行为

钉住「离开覆盖视图卸载」和「卸载绝不写配置」**之前**再动代码。这两条是 characterization/守卫测试：对**当前**代码即应通过，价值在于挡未来回归。

**Files:**
- Modify/Test: `tests/test_llm.py`（追加一个函数）
- Modify/Test: `tests/test_llm_ui.py`（追加 `import time` + 一个函数）

**Interfaces:**
- Consumes: `llm.unload`、`llm.CONFIG`、`llm._process`（既有）；`app.py` 的「开始这一课」按钮（label 以 `开始这一课` 开头，调用 `_leave_overlays()`，见 `app.py:1123-1124`）。
- Produces: 无新生产接口。

- [ ] **Step 1: 写「绝不写配置」守卫测试** —— 追加到 `tests/test_llm.py` 末尾：

```python
def test_unload_never_writes_hermes_config(tmp_path, monkeypatch):
    """生命周期不变量：卸载只停进程，绝不改 Hermes 配置（曾被 benchmark 覆盖过）。"""
    config = tmp_path / "config.yaml"
    config.write_text("model:\n  default: keep-me\n", encoding="utf-8")
    before = config.read_text(encoding="utf-8")
    monkeypatch.setattr(llm, "CONFIG", config)
    # 无进程分支：unload 空转，配置不变
    llm._process = None
    llm.unload()
    assert config.read_text(encoding="utf-8") == before

    # 有进程分支：走真实 terminate/wait 卸载路径，仍绝不碰配置
    class _FakeProc:
        def poll(self): return None          # 活着 → 进入 terminate 分支
        def terminate(self): self.killed = True
        def wait(self, timeout=None): return 0
    llm._process = _FakeProc()
    llm.unload()
    assert config.read_text(encoding="utf-8") == before
    assert llm._process is None              # 卸载后进程句柄清空
```

> 注（审核②）：此守卫覆盖**本模块代码**的两条 unload 分支，证明我们的代码绝不碰配置。真正的历史风险是 **rapid-mlx `serve` 子进程**（外部）覆盖配置——那不在我们代码可控范围，由「本模块绝不写配置」的不变量 + `test_load_failure_is_clear_and_stops_process`（已 mock `Popen`）共同约束，不在本测试内。

- [ ] **Step 2: 跑它，确认通过（守卫对当前代码即绿）**

Run: `python3 -m pytest tests/test_llm.py::test_unload_never_writes_hermes_config -v`
Expected: PASS（这是回归守卫，不是 red-first 新行为）

- [ ] **Step 3: 写 leave-unload AppTest** —— 在 `tests/test_llm_ui.py` 顶部 import 区加 `import time`，并追加函数：

```python
def test_leave_overlays_unloads_when_model_loaded(tmp_path, monkeypatch):
    """离开覆盖视图（点「开始这一课」回词练习）时，已加载的模型被卸载。"""
    db = Path("dictation.db"); bak = tmp_path / "db.bak"
    if db.exists():
        shutil.copy2(db, bak)
    unloaded = []
    monkeypatch.setattr(llm, "unload", lambda: unloaded.append(True))
    try:
        at = AppTest.from_file("app.py", default_timeout=10).run()
        at.session_state.llm_loaded = True
        at.session_state.llm_last_active = time.time()   # 刚活动过 → 闲置兜底先不卸，隔离 leave 路径
        at.run()
        assert not at.exception
        assert unloaded == []                            # 还没离开，未卸载
        next(b for b in at.button if b.label.startswith("开始这一课")).click().run()
        assert not at.exception
        assert unloaded == [True]                        # 离开覆盖视图 → 卸载一次
        assert at.session_state.llm_loaded is False
    finally:
        if bak.exists():
            shutil.copy2(bak, db)
        elif db.exists():
            db.unlink()
```

- [ ] **Step 4: 跑它，确认通过**

Run: `python3 -m pytest tests/test_llm_ui.py::test_leave_overlays_unloads_when_model_loaded -v`
Expected: PASS

- [ ] **Step 5: 跑全套，确认无回归**

Run: `python3 -m pytest -q`
Expected: `103 passed`（101 基线 + 本 Task 2 个新测试）

- [ ] **Step 6: Commit**

```bash
git add tests/test_llm.py tests/test_llm_ui.py
git commit -m "R0: pin leave-unload + never-write-config lifecycle invariants

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: 创建 `llm_lifecycle.py`（policy 纯函数，TDD）

**Files:**
- Create: `llm_lifecycle.py`
- Create: `tests/test_llm_lifecycle.py`

**Interfaces:**
- Produces:
  - `llm_lifecycle.IDLE_SECONDS: int`（= `5 * 60`）
  - `should_idle_unload(loaded: bool, last_active: float, now: float, idle_seconds: int = IDLE_SECONDS) -> bool`
  - `idle_minutes_left(last_active: float, now: float, idle_seconds: int = IDLE_SECONDS) -> int`

- [ ] **Step 1: 写失败测试** —— Create `tests/test_llm_lifecycle.py`：

```python
import llm_lifecycle as lc


def test_should_idle_unload_truth_table():
    assert lc.should_idle_unload(False, last_active=0, now=10_000) is False                       # 未加载永不卸
    assert lc.should_idle_unload(True, last_active=100, now=100 + lc.IDLE_SECONDS - 1) is False    # 未到阈值
    assert lc.should_idle_unload(True, last_active=100, now=100 + lc.IDLE_SECONDS) is True         # 边界含等号
    assert lc.should_idle_unload(True, last_active=0, now=10_000) is True                          # 远超阈值


def test_idle_minutes_left_preserves_legacy_caption_formula():
    # 刚活动过：剩满阈值（沿用原 app.py 的 +1 取整公式，不改观感）
    assert lc.idle_minutes_left(last_active=1000, now=1000) == int(lc.IDLE_SECONDS / 60) + 1
    # 已超时：不显示负数
    assert lc.idle_minutes_left(last_active=0, now=10_000) == 0
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `python3 -m pytest tests/test_llm_lifecycle.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'llm_lifecycle'`

- [ ] **Step 3: 写最小实现** —— Create `llm_lifecycle.py`：

```python
"""LLM 资源生命周期 policy —— 与 llm.py（mechanism）分开。

不变量（单一的家）：本模块只决定「何时 load / unload」，委托 llm.load()/llm.unload()
管理 rapid-mlx 子进程；**绝不读写 Hermes 配置 ~/.hermes/config.yaml**
（配置仅由 llm.configured_model() 只读取用）。rapid-mlx benchmark 曾覆盖过它一次，故立此规。
"""
from __future__ import annotations

IDLE_SECONDS = 5 * 60  # 模型闲置多久后自动卸载（兜底，最大泄漏 = 此阈值）


def should_idle_unload(loaded: bool, last_active: float, now: float,
                       idle_seconds: int = IDLE_SECONDS) -> bool:
    """已加载且闲置 ≥ 阈值 → 该卸载。"""
    return loaded and (now - last_active) >= idle_seconds


def idle_minutes_left(last_active: float, now: float,
                      idle_seconds: int = IDLE_SECONDS) -> int:
    """距自动卸载还剩几分钟（给 UI caption；保持原 app.py 公式不变）。"""
    idle = now - last_active
    return max(0, int((idle_seconds - idle) / 60) + 1)
```

- [ ] **Step 4: 跑测试，确认通过**

Run: `python3 -m pytest tests/test_llm_lifecycle.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: Commit**

```bash
git add llm_lifecycle.py tests/test_llm_lifecycle.py
git commit -m "R3: extract LLM lifecycle policy into llm_lifecycle.py (pure, tested)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: 把 `_llm_idle_watch` 改用 `llm_lifecycle`（行为逐字等价）

纯重构：把内联的闲置判定 + caption 数学换成 Task 2 的纯函数，删掉因此变死的常量。靠现有集成 AppTest + 新纯函数测试 + boot 自检证明等价。

**Files:**
- Modify: `app.py`（import；删 `LLM_IDLE_SECONDS`@`45`；重写 `_llm_idle_watch`@`2086-2096`）

**Interfaces:**
- Consumes: `llm_lifecycle.IDLE_SECONDS` / `should_idle_unload` / `idle_minutes_left`（Task 2）。

- [ ] **Step 1: 加 import** —— 在 `app.py` 顶部 import 组里，紧挨 `import llm` 加一行 `import llm_lifecycle`。

定位：`grep -n '^import llm$' app.py`，在该行后插入 `import llm_lifecycle`。

- [ ] **Step 2: 删死常量** —— 删除 `app.py:45` 整行：

```python
LLM_IDLE_SECONDS = 5 * 60
```

（grep 确认仅 `_llm_idle_watch` 用过它，重写后即无引用。先 `grep -n 'LLM_IDLE_SECONDS' app.py` 复核只剩第 45 行与将被替换的函数体。）

- [ ] **Step 3: 重写 `_llm_idle_watch`** —— 把整个函数体（`app.py:2085-2096`）替换为：

```python
@st.fragment(run_every=15)
def _llm_idle_watch() -> None:
    # 引擎级兜底：只要模型加载着就盯（不论在哪个视图），闲置即卸载，最大泄漏=闲置阈值
    if not st.session_state.get("llm_loaded"):
        return
    now = time.time()
    last_active = st.session_state.get("llm_last_active", 0)
    if llm_lifecycle.should_idle_unload(True, last_active, now):
        llm.unload()
        st.session_state.llm_loaded = False
        st.session_state.llm_error = "闲置超过 5 分钟，模型已自动卸载并释放内存。"
        st.rerun(scope="app")
    st.caption(f"模型会在闲置 {llm_lifecycle.idle_minutes_left(last_active, now)} 分钟后自动卸载。")
```

逐字等价说明：原 `idle = time.time() - last_active; if idle >= LLM_IDLE_SECONDS` ≡ `should_idle_unload(True, last_active, now)`（已知 loaded）；caption 的 `max(0, int((LLM_IDLE_SECONDS - idle)/60)+1)` ≡ `idle_minutes_left(last_active, now)`。

- [ ] **Step 4: 跑 LLM 相关测试 + 全套**

Run: `python3 -m pytest tests/test_llm_ui.py tests/test_llm_lifecycle.py -v && python3 -m pytest -q`
Expected: `test_idle_watch_unloads_when_model_loaded_and_idle` 等全部 PASS；全套 `105 passed`（101 基线 + R0 两个 + R3 模块两个）

- [ ] **Step 5: boot 自检（抓 import/语法，app.py 无单测）**

Run:
```bash
streamlit run app.py --server.headless true --server.port 8599 >/tmp/st.log 2>&1 &
PID=$!; curl --retry 25 --retry-delay 1 --retry-connrefused -s -o /dev/null -w "health %{http_code}\n" localhost:8599/_stcore/health
grep -icE 'error|traceback|exception' /tmp/st.log; kill $PID 2>/dev/null
```
Expected: `health 200`，错误计数 `0`

- [ ] **Step 6: Commit**

```bash
git add app.py
git commit -m "R3: route _llm_idle_watch through llm_lifecycle; drop dead LLM_IDLE_SECONDS

Behavior-identical refactor; existing idle-watch AppTest stays green.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: 在 `llm-graded-practice` 记下「生命周期独立模块」模式（最小改动）

**前提核对（已做）：** 该 skill 的「确定性信任边界」不变量**已存在**——第 1 点（authored reference）、第 2 点（code owns deterministic / drop hallucinated）、第 7 点（sparring partner not textbook）、第 8 点（never rewrite config）。**故不重复写入**；只补 R3 的新学习：policy 该独立成模块。

**Files:**
- Modify: `/Users/francis/.codex/skills/llm-graded-practice/SKILL.md`（第 8 点）

- [ ] **Step 1: 给第 8 点追加一句** —— 把这一行：

```
8. **Local-model resource lifecycle.** Load on demand, unload on exit / view-switch / idle; **never rewrite the model's external config file**. Model+thinking are a session/offline choice (env), not switched per call on a single exclusive process.
```

替换为（仅末尾加一句）：

```
8. **Local-model resource lifecycle.** Load on demand, unload on exit / view-switch / idle; **never rewrite the model's external config file**. Model+thinking are a session/offline choice (env), not switched per call on a single exclusive process. Keep the load/unload *policy* in one dedicated module, separate from the thin service *adapter*, so the "never rewrite config" invariant has a single home (听写: `llm_lifecycle.py` decides *when*, `llm.py` does the start/stop).
```

- [ ] **Step 2: 确认无重复 / 渲染正常**

Run: `grep -n "dedicated module" /Users/francis/.codex/skills/llm-graded-practice/SKILL.md`
Expected: 命中 1 行（仅新增句）

- [ ] **Step 3: Commit（codex skills 是独立的家，单独说明）**

> 注：该 SKILL.md 在 `~/.codex/skills/`，不在本仓库。若它自身是 git 仓，在那里单独 commit；否则向用户报告这是一处仓外改动（本仓 `git status` 不会显示它）。

```bash
# 若 ~/.codex/skills 是 git 仓：
cd /Users/francis/.codex/skills && git add llm-graded-practice/SKILL.md \
  && git commit -m "llm-graded-practice: lifecycle policy belongs in a dedicated module (听写 llm_lifecycle.py)"
```

---

## Self-Review

**1. Spec coverage（对照决策记录 §4）：**
- R0 窄安全网（按 R3 爆炸半径裁）→ Task 1（leave-unload + never-write-config）+ Task 2 的纯函数测试；load-on-submit/idle-unload 已被既有测试覆盖（File Structure 已注明）。✅
- R3 生命周期收口（小独立模块，不立 `review/` 包）→ Task 2 + Task 3。✅
- P4 内存验收（47→23GB，需你在场跑）→ **不是本计划的自动步骤**；列为执行后由用户在真实会话确认的验收项（见下「执行交接」）。✅ 诚实标注：agent 不可验运行时内存。
- 扩展 llm-graded-practice → Task 4（缩为一句，因不变量已在）。✅
- 推迟 R1/R2/R4 + `add-review-item-kind` skill → 本计划不含，符合决策。✅

**2. Placeholder scan：** 无 TBD/TODO；每个改码步骤都带完整代码或精确替换。✅

**3. Type consistency：** `should_idle_unload(loaded, last_active, now, idle_seconds=…) -> bool` 与 `idle_minutes_left(last_active, now, idle_seconds=…) -> int` 在 Task 2 定义、Task 3 按同名同参调用；`IDLE_SECONDS` 命名一致。✅

**已知执行注意：** Task 1 的 leave-unload 测试依赖「开始这一课」按钮（label 前缀稳定）与 `dictation.db` 备份/还原（沿用既有测试模式）；`_leave_overlays` 在 `start_lesson_round` **之前**调用，故即便该课无词也已卸载，测试稳健。
