from pathlib import Path
import shutil

import llm
import store
from streamlit.testing.v1 import AppTest


def test_ai_view_loads_on_entry_and_unloads_on_exit(tmp_path, monkeypatch):
    db_path = Path("dictation.db")
    backup = tmp_path / "dictation.db.bak"
    if db_path.exists():
        shutil.copy2(db_path, backup)
    unloaded = []
    monkeypatch.setattr(llm, "load", lambda: 1.25)
    monkeypatch.setattr(llm, "is_loaded", lambda: True)
    monkeypatch.setattr(llm, "unload", lambda: unloaded.append(True))

    try:
        at = AppTest.from_file("app.py", default_timeout=10).run()
        assert not at.exception

        next(b for b in at.button if b.label == "🤖 AI 精练（加载本地模型）").click().run()
        assert not at.exception
        assert "🤖 AI 精练" in [s.value for s in at.subheader]
        assert any("本地模型已加载" in s.value for s in at.success)

        next(b for b in at.button if b.label == "↩︎ 退出并释放模型").click().run()
        assert not at.exception
        assert unloaded == [True]
        assert "🤖 AI 精练" not in [s.value for s in at.subheader]

        at.selectbox(key="sel_lesson").set_value("L22").run()
        next(b for b in at.button if b.label == "🤖 AI 精练（加载本地模型）").click().run()
        next(b for b in at.button if b.label.startswith("📝 知识点（")).click().run()
        assert not at.exception
        assert unloaded == [True, True]
        assert any(s.value.startswith("📝 知识点") for s in at.subheader)
    finally:
        if backup.exists():
            shutil.copy2(backup, db_path)
        elif db_path.exists():
            db_path.unlink()


def test_ai_view_unloads_after_idle_timeout(monkeypatch):
    unloaded = []
    monkeypatch.setattr(llm, "load", lambda: 0.1)
    monkeypatch.setattr(llm, "is_loaded", lambda: True)
    monkeypatch.setattr(llm, "unload", lambda: unloaded.append(True))

    at = AppTest.from_file("app.py", default_timeout=10).run()
    next(b for b in at.button if b.label == "🤖 AI 精练（加载本地模型）").click().run()
    at.session_state.llm_last_active = 0
    at.run()

    assert not at.exception
    assert unloaded == [True]
    assert any("闲置超过 5 分钟" in e.value for e in at.error)


def test_ai_feedback_requires_user_final_judgment_before_srs(tmp_path, monkeypatch):
    db_path = Path("dictation.db")
    backup = tmp_path / "dictation.db.bak"
    if db_path.exists():
        shutil.copy2(db_path, backup)
    calls = []
    monkeypatch.setattr(llm, "load", lambda: 0.1)
    monkeypatch.setattr(llm, "is_loaded", lambda: True)
    monkeypatch.setattr(llm, "unload", lambda: None)
    monkeypatch.setattr(llm, "grade", lambda *args: calls.append(args) or {
        "判定": "对", "错在哪": "无", "改进建议": "保持", "更好的版本": "Ils s'installeront à Paris."
    })

    try:
        at = AppTest.from_file("app.py", default_timeout=10).run()
        next(b for b in at.button if b.label == "🤖 AI 精练（加载本地模型）").click().run()
        at.text_area[0].set_value("Ils s'installeront à Paris.")
        next(b for b in at.button if b.label == "交给本地 AI 批改").click().run()

        assert not at.exception
        assert len(calls) == 1
        before = store.get_checkpoint_state(["L22:ai:sentence-core-after-work"])
        assert before["L22:ai:sentence-core-after-work"]["correct_streak"] == 0

        next(b for b in at.button if b.key == "llm_self_right").click().run()
        after = store.get_checkpoint_state(["L22:ai:sentence-core-after-work"])
        assert after["L22:ai:sentence-core-after-work"]["correct_streak"] == 1
        assert any("造句流程 2/2 · 再升级完整句" in m.value for m in at.markdown)
    finally:
        if backup.exists():
            shutil.copy2(backup, db_path)
        elif db_path.exists():
            db_path.unlink()
