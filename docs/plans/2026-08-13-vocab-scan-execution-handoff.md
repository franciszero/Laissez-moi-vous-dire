# 速过视图施工总管 Handoff（Opus 5 专用）

你是本仓库速过视图（⚡ 扫读 /「认」技能）的**施工总管**：只做派发与审核，不亲自写实现代码（唯一例外见「S0 卡」）。本文件是你的全部操作规程，严格执行，不要重新设计。

## 输入文件（按序读）

1. `docs/plans/2026-08-13-vocab-scan-sonnet-cards.md` —— 施工卡（法律文本，代码照抄，不得偏离）
2. `docs/specs/2026-08-13-vocab-scan-design.md` —— 设计文档（只在裁决争议时查阅，不要整篇喂给执行者）

## 开工前

```bash
git checkout -b vocab-scan-v1
python3 -m pytest -q   # 基线必须全绿，红了先停下报告用户
```

**两件必须先核实的事**（写计划的会话读不到 `tests/*.py`，被沙箱挡了）：

1. 打开 `tests/test_store.py`，看它怎么隔离 `dictation.db`。若它已有现成的临时库夹具，
   把 A2 卡里 `_fresh_db` 那段替换成复用既有夹具，并在派发时把改动一并交代给执行者。
   若没有（很可能——本仓库无 `conftest.py`），A2 卡照原样执行。
2. 确认 `tests/` 下没有已存在的 `test_scan*.py`。有的话停下报告用户，不要覆盖。

## 主循环：每张卡一个轮次（A1 → A2 → A3 → B1 → B2 → B3 → B4 → B5 → F）

**S0 已经做完了，结论是 `A`**（2026-08-13 在 Streamlit 1.58.0 上真机验证，页面显示
`Python 收到：'2,4'`，rerun 之后重挂也通）。你不用再跑它。

### 1. 派发

用 Agent 工具派一个**全新** subagent，`model: "sonnet"`，同步执行（等它做完再继续），每卡提示词模板：

> 你在仓库 /Users/francis/Documents/法语/本地录屏课/听写 施工。打开
> docs/plans/2026-08-13-vocab-scan-sonnet-cards.md，只执行 **Task {X}** 一张卡。
> 严格按卡内步骤：代码照抄，不做任何设计变更；改 app.py 时用卡内给的**锚点文本**定位，
> 不要用行号；每步跑卡内给定命令并核对期望输出；禁止改动本卡 Files 清单之外的文件；
> 全量 `python3 -m pytest -q` 全绿后，用卡内给定的 commit 信息提交。
> 完成后报告：改动文件清单 + 每个验收命令的真实输出摘要。

不复用旧 subagent 的上下文——卡片自包含，新开更便宜也更干净。

**B4 卡派发时必须在提示词里写明**：「S0 结论是 A，只做 Step 3（A 路），整段跳过
Step 3（B 路）」。不写清楚 Sonnet 会两路都做。

### 2. 审核（每卡必做，不信转述）

- [ ] `git show --stat HEAD`：改动只含本卡 Files 清单里的文件；
- [ ] `git show HEAD` 通读 diff：代码与卡内一致，尤其 `store.record_scan_page` 里
      **一行 UPDATE words 都不许有**；
- [ ] **亲自重跑**本卡验收命令和 `python3 -m pytest -q`，看真实输出，不采信 subagent 的复述；
- [ ] A2 之后每卡顺手确认 `tests/test_scan_store.py::test_never_touches_words_srs_state`
      仍绿（全量 pytest 已覆盖，红了即停——那是本设计的核心不变量塌了）。

全部通过 → 派下一张。任何一条不过 → 进入返工流程。

### 3. 返工

把具体失败项（命令 + 真实报错）发回给**同一张卡的新 subagent**重做，最多 2 次；仍失败则停止整个流水线，向用户报告卡号、失败输出和你的诊断。**不要自己动手改实现来救场**——那会绕过审核。

## 硬规则

- 施工卡是法律：session key、skill 名（`rec_meaning`/`rec_produce`/`rec_audio`）、
  SQL、锚点文本、commit 信息一律不得"优化"。执行者或你觉得计划有错时，停下报告用户，
  不要现场改设计。
- **不许给 `matcher.check_fr` 加容错**（`docs/BACKLOG.md` 第 3 条是用户的明确选择）。
- **不许新增数据库表或改既有列**。整个设计是零 schema 变更。
- 不并行：一次只在飞一张卡（B1 之后每张都碰 `app.py`）。
- 顺序固定，S0 必须最先做完——它的结论决定 B4 的形态。
- B5 通过后：跑一次 `python3 -m pytest -q` 终验，报告用户"代码卡全部完成"，**停**。

## S0（已完成，不用重跑）

结论 `A`：注入的 JS 用 native setter + `input` 事件写 `.st-key-scan_missed input`，
Streamlit 的 form 提交能读到，rerun 之后重挂也通。B4 走 A 路。

只有一种情况要重跑：Streamlit 升级后 B4 的真机验证（B4 Step 6）失败。那时按施工卡
Task S0 里保留的原始步骤重验一次，若确认打不通，改走 B 路（`st.pills` 序号条），
并先向用户报告再动手。

## 完成定义

A1–B5 全部通过审核并提交、全量 pytest 绿。
Task F（真实练一课的验收，含定页大小默认值）属于用户本人，你只提醒，不代做。
