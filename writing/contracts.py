# writing/contracts.py
"""写作练习的数据合同与端口协议。禁止 import streamlit/sqlite3/app/llm。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

SourceKind = Literal["transcript", "pdf", "screenshot", "prompt", "learner_draft", "teacher_markup"]
VerifyState = Literal["verified", "needs_review"]
SlotKind = Literal["must", "bonus", "risk"]          # 漏答必失分 / 加分项 / 扣分风险
SlotOrigin = Literal["official", "teacher", "ai_inferred"]
SupportScope = Literal["task", "task_type", "general"]  # 本题 / 本类题 / 通用写作
SupportCategory = Literal["outline", "logic", "content_ammo", "language_ammo", "teacher_tip"]
ReviewStatus = Literal["teacher_reviewed", "ai_draft", "needs_review"]
Modality = Literal["writing", "speaking", "both"]
TaskStatus = Literal["draft", "teacher_reviewed"]
StepKind = Literal["fixed", "slots", "flow"]
# fixed=文章结构的一格，素材按 function 挂上来
# slots=文章结构的一格，子格由题目的 must/bonus 槽位在运行时展开
# flow =练习流程动作（选情境、交卷检查），不产出文章内容


@dataclass(frozen=True)
class SourceRef:
    lesson: str
    kind: SourceKind
    path: str
    locator: str = ""                    # 页码/行号/时间点，如 "L33_final_working.md:280"
    verify: VerifyState = "needs_review"
    note: str = ""


@dataclass(frozen=True)
class SkeletonStep:
    """体裁骨架的一格。属于 tcf_task_type，不属于任何一道题。"""

    step_id: str
    name: str
    kind: StepKind
    optional: bool = False


@dataclass(frozen=True)
class ScoreSlot:
    slot_id: str
    label: str                           # 如 "type de logement"
    kind: SlotKind
    origin: SlotOrigin
    note: str = ""


@dataclass(frozen=True)
class WritingSupport:
    support_id: str
    scope: SupportScope
    category: SupportCategory
    title: str
    body: str
    review: ReviewStatus
    order: int
    modality: Modality = "writing"
    conditions: str = ""
    source: SourceRef | None = None
    step: str = ""                       # ⚠️ 过渡字段，J2 卡移除；请改用 function
    function: str = ""                   # 对应 SkeletonStep.step_id；空串=不进骨架，只进详解
    slot_id: str = ""                    # 仅当所属格 kind="slots"：这条素材填哪个槽位


@dataclass(frozen=True)
class WritingTask:
    task_id: str
    lesson: str
    tcf_task_type: str                   # 如 "tache_1"
    title: str
    prompt_text: str
    audience: str
    register: str
    purpose: str
    word_min: int
    word_max: int
    status: TaskStatus
    slots: tuple[ScoreSlot, ...] = ()
    supports: tuple[WritingSupport, ...] = ()
    sources: tuple[SourceRef, ...] = ()
    reference_text: str = ""             # 老师核验过的参考全文；空串=暂无
    time_limit_minutes: int = 0          # 0=不限时
    skeleton: tuple[SkeletonStep, ...] = ()   # 按 tcf_task_type 装配，非本题私有


@dataclass(frozen=True)
class WritingTaskSummary:
    task_id: str
    lesson: str
    title: str
    tcf_task_type: str


@dataclass(frozen=True)
class WritingDraft:
    task_id: str
    text: str
    updated_at: str                      # ISO 时间串


@dataclass(frozen=True)
class WritingVersion:
    version_id: str
    task_id: str
    text: str
    created_at: str
    parent_version_id: str | None = None


class WritingContentPort(Protocol):
    def list_tasks(self, lesson: str) -> tuple[WritingTaskSummary, ...]: ...
    def load_task(self, lesson: str, task_id: str) -> WritingTask: ...


class WritingHistoryPort(Protocol):
    def load_draft(self, task_id: str) -> WritingDraft | None: ...
    def save_draft(self, task_id: str, text: str) -> WritingDraft: ...
    def submit_version(
        self, task_id: str, text: str, parent_version_id: str | None = None
    ) -> WritingVersion: ...
    def list_versions(self, task_id: str) -> tuple[WritingVersion, ...]: ...
