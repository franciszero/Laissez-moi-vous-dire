# tests/test_writing_app_entry.py
from __future__ import annotations

import json
import shutil
from pathlib import Path

from streamlit.testing.v1 import AppTest


def _make_content_root(tmp_path: Path) -> Path:
    root = tmp_path / "lessons"
    (root / "L33").mkdir(parents=True)
    doc = {"schema": 1, "tasks": [{
        "task_id": "L33-W1", "lesson": "L33", "tcf_task_type": "tache_1",
        "title": "测试题", "prompt_text": "Écrire un mail.", "audience": "ami",
        "register": "informel", "purpose": "demander", "word_min": 60,
        "word_max": 120, "status": "teacher_reviewed",
        "slots": [], "supports": [], "sources": []}]}
    (root / "L33" / "writing_tasks.json").write_text(
        json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return root


def test_writing_entry_roundtrip(tmp_path, monkeypatch):
    db_path = Path("dictation.db")           # 与 test_checkpoint_ui.py 相同的备份模式
    backup = tmp_path / "dictation.db.bak"
    if db_path.exists():
        shutil.copy2(db_path, backup)
    monkeypatch.setenv("WRITING_CONTENT_ROOT", str(_make_content_root(tmp_path)))
    try:
        at = AppTest.from_file("app.py", default_timeout=10)
        at.run()
        assert not at.exception

        at.selectbox(key="sel_lesson").set_value("L33").run()
        entry = next((b for b in at.button if b.label.startswith("✍️ 写作练习")), None)
        assert entry is not None and not entry.disabled

        entry.click().run()
        assert not at.exception
        assert at.text_area(key="wr_text_L33-W1") is not None   # 进入写作视图

        # 提交一版走通 store 适配器
        at.text_area(key="wr_text_L33-W1").set_value("Salut, je cherche un studio.").run()
        submit = next(b for b in at.button if b.label == "📌 保存这一版")
        submit.click().run()
        assert not at.exception

        # 退出：写作视图消失，词/卡入口还在
        exit_btn = next(b for b in at.button if b.label == "↩︎ 退出写作")
        exit_btn.click().run()
        assert not at.exception
        assert not any(b.label == "↩︎ 退出写作" for b in at.button)
        assert any(b.label.startswith("📝 知识点") for b in at.button)
    finally:
        if backup.exists():
            shutil.copy2(backup, db_path)


def test_no_content_means_disabled_button(tmp_path, monkeypatch):
    monkeypatch.setenv("WRITING_CONTENT_ROOT", str(tmp_path))  # 空目录
    at = AppTest.from_file("app.py", default_timeout=10)
    at.run()
    assert not at.exception
    at.selectbox(key="sel_lesson").set_value("L33").run()
    entry = next((b for b in at.button if b.label.startswith("✍️ 写作练习")), None)
    assert entry is not None and entry.disabled
