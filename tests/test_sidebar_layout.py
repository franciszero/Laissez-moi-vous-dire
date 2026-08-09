"""侧栏分层：设一次的收进折叠区，每次要点的留在外面。

侧栏顶部是最值钱的位置。语音、语速、每批词数、答对自动下一题都是装好之后
几个月不碰的，占着顶部就把「选课/模式/搜词」挤下去了。这条测试盯住这个分界——
新加控件时很容易顺手往顶层塞。
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

SET_ONCE = {"语音", "语速", "答对后自动下一题",
            "每批词数（做完一批会停下来喘口气）",
            "🔄 重新扫描词表（加了课/改了文件后点）"}
EVERY_TIME = {"选课", "模式"}


@pytest.fixture
def at(tmp_path):
    db, bak = Path("dictation.db"), tmp_path / "dictation.db.bak"
    if db.exists():
        shutil.copy2(db, bak)
    app = AppTest.from_file("app.py", default_timeout=25).run()
    assert not app.exception
    yield app
    if bak.exists():
        shutil.copy2(bak, db)


def _settings(at: AppTest):
    return next(e for e in at.sidebar.expander if e.label == "⚙️ 设置")


def _labels(container) -> set[str]:
    out: set[str] = set()
    for kind in ("selectbox", "slider", "checkbox", "number_input", "button", "text_input"):
        out |= {w.label for w in getattr(container, kind)}
    return out


def test_settings_expander_exists_and_starts_collapsed(at):
    assert _settings(at).proto.expanded is False, "设置默认要折起来，否则等于没收"


def test_set_once_controls_live_inside_settings(at):
    inside = _labels(_settings(at))
    missing = SET_ONCE - inside
    assert not missing, f"这些「设一次」的控件跑到侧栏顶层去了：{missing}"


def test_every_session_controls_stay_outside_settings(at):
    inside = _labels(_settings(at))
    leaked = EVERY_TIME & inside
    assert not leaked, f"每次都要用的控件被折起来了：{leaked}"
    top = _labels(at.sidebar) - inside
    assert EVERY_TIME <= top, f"选课/模式必须在侧栏外面，实际顶层有：{sorted(top)[:12]}"


def test_lesson_entry_buttons_stay_outside_settings(at):
    inside = _labels(_settings(at))
    for label in ("开始这一课", "错词", "变形", "📝 知识点", "✍️ 写作练习"):
        assert not any(b.startswith(label) for b in inside), f"{label} 不该被折进设置"
