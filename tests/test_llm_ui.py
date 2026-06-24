import shutil
from pathlib import Path

import llm
import store
from streamlit.testing.v1 import AppTest

_GRADE_JSON = (
    '{"片段":[{"片段":"Ils s\'installeront à Paris.","维度":"句式","状态":"正确","依据":"ok"}],'
    '"最小修正":"Ils s\'installeront à Paris.","更自然版":"Ils s\'installeront à Paris.","总判定":"对"}'
)


def _enter_first_production_card(at):
    """进入 L22「知识点」deck，跳到第一张 AI 产出卡（kind=production）。"""
    at.selectbox(key="sel_lesson").set_value("L22").run()
    next(b for b in at.button if b.label.startswith("📝 知识点（")).click().run()
    cards = at.session_state.cp_cards
    idx = next(i for i, c in enumerate(cards) if c.get("kind") == "production")
    at.session_state.cp_index = idx
    at.run()
    return cards[idx]


def test_production_card_loads_model_on_submit_and_grades(tmp_path, monkeypatch):
    db = Path("dictation.db"); bak = tmp_path / "db.bak"
    if db.exists():
        shutil.copy2(db, bak)
    loaded = []
    monkeypatch.setattr(llm, "load", lambda: (loaded.append(True), 0.1)[1])
    monkeypatch.setattr(llm, "is_loaded", lambda: bool(loaded))
    monkeypatch.setattr(llm, "unload", lambda: None)
    monkeypatch.setattr(llm, "chat", lambda *a, **k: _GRADE_JSON)
    try:
        at = AppTest.from_file("app.py", default_timeout=10).run()
        _enter_first_production_card(at)
        assert not at.exception
        assert at.session_state.llm_loaded is False             # 进入产出卡时不加载
        ta = next(t for t in at.text_area if t.key.startswith("prod_ans_"))
        ta.set_value("Ils s'installeront à Paris.")
        next(b for b in at.button if b.label.startswith("交给本地 AI 批改")).click().run()
        assert not at.exception
        assert loaded == [True]                                 # 提交时才加载（一次）
        assert at.session_state.llm_loaded is True
        assert at.session_state.llm_result and not at.session_state.llm_result.get("parse_error")
    finally:
        if bak.exists():
            shutil.copy2(bak, db)
        elif db.exists():
            db.unlink()


def test_idle_watch_unloads_when_model_loaded_and_idle(monkeypatch):
    unloaded = []
    monkeypatch.setattr(llm, "unload", lambda: unloaded.append(True))
    at = AppTest.from_file("app.py", default_timeout=10).run()
    at.session_state.llm_loaded = True          # 引擎级兜底：加载着 + 闲置 → 卸载（不论哪个视图）
    at.session_state.llm_last_active = 0
    at.run()
    assert not at.exception
    assert unloaded == [True]
    assert at.session_state.llm_loaded is False


def test_production_ai_requires_user_verdict_before_srs(tmp_path, monkeypatch):
    db = Path("dictation.db"); bak = tmp_path / "db.bak"
    if db.exists():
        shutil.copy2(db, bak)
    monkeypatch.setattr(llm, "load", lambda: 0.1)
    monkeypatch.setattr(llm, "is_loaded", lambda: True)
    monkeypatch.setattr(llm, "unload", lambda: None)
    monkeypatch.setattr(llm, "chat", lambda *a, **k: _GRADE_JSON)
    try:
        at = AppTest.from_file("app.py", default_timeout=10).run()
        card = _enter_first_production_card(at)
        ta = next(t for t in at.text_area if t.key.startswith("prod_ans_"))
        ta.set_value("Ils s'installeront à Paris.")
        next(b for b in at.button if b.label.startswith("交给本地 AI 批改")).click().run()
        before = store.get_checkpoint_state([card["id"]]).get(card["id"], {}).get("correct_streak", 0)
        # 批改完，但未终判 → SRS 未变；点「我对」才写
        next(b for b in at.button if b.key == "prod_right").click().run()
        after = store.get_checkpoint_state([card["id"]])[card["id"]]["correct_streak"]
        assert after == before + 1
    finally:
        if bak.exists():
            shutil.copy2(bak, db)
        elif db.exists():
            db.unlink()
