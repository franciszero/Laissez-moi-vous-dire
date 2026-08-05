# writing/tests/test_contracts.py
from __future__ import annotations

import dataclasses

import pytest

from writing.contracts import (
    ScoreSlot,
    SkeletonStep,
    SourceRef,
    WritingDraft,
    WritingSupport,
    WritingTask,
    WritingTaskSummary,
    WritingVersion,
)


def make_task(**over):
    base = dict(
        task_id="L33-W1", lesson="L33", tcf_task_type="tache_1",
        title="给朋友写邮件找房", prompt_text="écrire un mail à un ami",
        audience="ami", register="informel", purpose="demander de l'aide",
        word_min=60, word_max=120, status="teacher_reviewed",
    )
    base.update(over)
    return WritingTask(**base)


def test_task_frozen_and_defaults():
    t = make_task()
    assert t.slots == () and t.supports == () and t.sources == ()
    assert t.reference_text == "" and t.time_limit_minutes == 0
    with pytest.raises(dataclasses.FrozenInstanceError):
        t.title = "x"


def test_support_and_slot_construction():
    src = SourceRef(lesson="L33", kind="transcript", path="a.md", locator="280")
    assert src.verify == "needs_review"
    sup = WritingSupport(
        support_id="s1", scope="task", category="outline",
        title="骨架", body="称呼→目的→请求", review="teacher_reviewed", order=1,
        source=src,
    )
    assert sup.modality == "writing" and sup.conditions == ""
    slot = ScoreSlot(slot_id="s1", label="budget", kind="must", origin="teacher")
    assert slot.note == ""


def test_draft_version_summary():
    d = WritingDraft(task_id="t", text="Bonjour", updated_at="2026-08-02T10:00:00")
    v = WritingVersion(version_id="v1", task_id="t", text="Bonjour",
                       created_at="2026-08-02T10:00:00")
    assert v.parent_version_id is None
    s = WritingTaskSummary(task_id="t", lesson="L33", title="题", tcf_task_type="tache_1")
    with pytest.raises(dataclasses.FrozenInstanceError):
        d.text = "x"
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.title = "x"


def test_skeleton_step_defaults():
    """体裁骨架的一格：属于 tcf_task_type，不属于任何一道题。"""
    st = SkeletonStep(step_id="greeting", name="称呼", kind="fixed")
    assert st.optional is False
    assert SkeletonStep("subject", "Objet", "fixed", optional=True).optional is True


def test_support_declares_function_not_position():
    """素材声明「干什么用」，位置由骨架决定——两者不同抽象层，不许压扁。"""
    base = dict(support_id="s1", scope="task", category="outline", title="骨架",
                body="称呼→目的→请求", review="teacher_reviewed", order=1)
    plain = WritingSupport(**base)
    assert plain.function == "" and plain.slot_id == ""
    tagged = WritingSupport(**{**base, "support_id": "s2",
                               "function": "slot_fill", "slot_id": "s3"})
    assert tagged.function == "slot_fill" and tagged.slot_id == "s3"


def test_task_carries_skeleton_but_defaults_empty():
    assert make_task().skeleton == ()
    sk = (SkeletonStep("greeting", "称呼", "fixed"),)
    assert make_task(skeleton=sk).skeleton == sk
