# writing/tests/test_service.py
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from writing.service import WritingService
from writing.tests.fakes import InMemoryContent, InMemoryHistory
from writing.tests.test_contracts import make_task


def make_service(tasks=None):
    tasks = tasks if tasks is not None else [make_task()]
    return WritingService(InMemoryContent(tasks), InMemoryHistory())


def test_list_tasks_excludes_draft_status():
    svc = make_service([make_task(), make_task(task_id="L33-W2", status="draft")])
    assert [s.task_id for s in svc.list_tasks("L33")] == ["L33-W1"]


def test_open_task_returns_task_draft_versions():
    svc = make_service()
    task, draft, versions = svc.open_task("L33", "L33-W1")
    assert task.task_id == "L33-W1" and draft is None and versions == ()


def test_draft_overwrites_not_appends():
    svc = make_service()
    svc.save_draft("L33-W1", "premier")
    svc.save_draft("L33-W1", "deuxième")
    _, draft, versions = svc.open_task("L33", "L33-W1")
    assert draft.text == "deuxième" and versions == ()


def test_versions_append_only_and_ordered():
    svc = make_service()
    v1 = svc.submit_version("L33-W1", "un")
    v2 = svc.submit_version("L33-W1", "deux", parent_version_id=v1.version_id)
    got = svc.list_versions("L33-W1")
    assert [v.text for v in got] == ["un", "deux"]
    assert got[1].parent_version_id == v1.version_id
    assert v1.version_id != v2.version_id


def test_empty_or_blank_text_cannot_submit():
    svc = make_service()
    with pytest.raises(ValueError):
        svc.submit_version("L33-W1", "")
    with pytest.raises(ValueError):
        svc.submit_version("L33-W1", "   \n ")


def test_core_modules_have_no_ui_or_db_imports():
    banned = {"streamlit", "sqlite3", "app", "llm"}
    pkg = Path(__file__).parents[1]
    for name in ("contracts.py", "service.py"):
        tree = ast.parse((pkg / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods = {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                mods = {(node.module or "").split(".")[0]}
            else:
                continue
            assert not (mods & banned), f"{name} 引入被禁模块: {mods & banned}"
