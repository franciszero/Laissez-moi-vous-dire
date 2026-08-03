# writing/tests/fakes.py
"""测试用内存端口实现，与 SQLite/Streamlit 无关。"""
from __future__ import annotations

from datetime import datetime

from writing.contracts import WritingDraft, WritingTask, WritingTaskSummary, WritingVersion


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class InMemoryContent:
    def __init__(self, tasks: list[WritingTask]) -> None:
        self._tasks = list(tasks)

    def list_tasks(self, lesson: str) -> tuple[WritingTaskSummary, ...]:
        return tuple(
            WritingTaskSummary(t.task_id, t.lesson, t.title, t.tcf_task_type)
            for t in self._tasks
            if t.lesson == lesson and t.status == "teacher_reviewed"
        )

    def load_task(self, lesson: str, task_id: str) -> WritingTask:
        for t in self._tasks:
            if t.lesson == lesson and t.task_id == task_id:
                return t
        raise KeyError(f"{lesson}/{task_id}")


class InMemoryHistory:
    def __init__(self) -> None:
        self._drafts: dict[str, WritingDraft] = {}
        self._versions: list[WritingVersion] = []
        self._n = 0

    def load_draft(self, task_id: str) -> WritingDraft | None:
        return self._drafts.get(task_id)

    def save_draft(self, task_id: str, text: str) -> WritingDraft:
        draft = WritingDraft(task_id, text, _now())
        self._drafts[task_id] = draft
        return draft

    def submit_version(self, task_id, text, parent_version_id=None) -> WritingVersion:
        self._n += 1
        v = WritingVersion(f"v{self._n}", task_id, text, _now(), parent_version_id)
        self._versions.append(v)
        return v

    def list_versions(self, task_id: str) -> tuple[WritingVersion, ...]:
        return tuple(v for v in self._versions if v.task_id == task_id)
