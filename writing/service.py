# writing/service.py
"""无 UI、无 DB 的写作用例编排。禁止 import streamlit/sqlite3/app/llm。"""
from __future__ import annotations

from writing.contracts import (
    WritingContentPort,
    WritingDraft,
    WritingHistoryPort,
    WritingTask,
    WritingTaskSummary,
    WritingVersion,
)


class WritingService:
    def __init__(self, content: WritingContentPort, history: WritingHistoryPort) -> None:
        self._content = content
        self._history = history

    def list_tasks(self, lesson: str) -> tuple[WritingTaskSummary, ...]:
        return self._content.list_tasks(lesson)

    def open_task(
        self, lesson: str, task_id: str
    ) -> tuple[WritingTask, WritingDraft | None, tuple[WritingVersion, ...]]:
        task = self._content.load_task(lesson, task_id)
        return task, self._history.load_draft(task_id), self._history.list_versions(task_id)

    def save_draft(self, task_id: str, text: str) -> WritingDraft:
        return self._history.save_draft(task_id, text)

    def submit_version(
        self, task_id: str, text: str, parent_version_id: str | None = None
    ) -> WritingVersion:
        if not text.strip():
            raise ValueError("空文本不能提交为版本")
        return self._history.submit_version(task_id, text, parent_version_id)

    def list_versions(self, task_id: str) -> tuple[WritingVersion, ...]:
        return self._history.list_versions(task_id)
