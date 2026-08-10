"""写作是独立入口：不选课也能到达，且能拿到同体裁跨题的通用弹药。

以前 `_writing_task_summaries` 里有一行 `if lesson == "全部": return []`，
写作被锁在「先选课」后面；而 scope=task_type/general 的素材（L33-W1 里有 25 条）
从来没被别的题读到过——两件事同一个根：内容层把 lesson 当成了找文件的路径。
"""
from pathlib import Path
import shutil

import pytest
from streamlit.testing.v1 import AppTest


@pytest.fixture
def at(tmp_path):
    db, bak = Path("dictation.db"), tmp_path / "dictation.db.bak"
    if db.exists():
        shutil.copy2(db, bak)
    app = AppTest.from_file("app.py", default_timeout=30).run()
    assert not app.exception
    yield app
    if bak.exists():
        shutil.copy2(bak, db)


def _enter_writing(at: AppTest):
    btn = next(b for b in at.button if b.label.startswith("✍️ 写作练习"))
    assert not btn.disabled
    btn.click().run()
    assert not at.exception
    return at


def test_writing_is_reachable_without_choosing_a_lesson(at):
    at.selectbox(key="sel_lesson").set_value("全部").run()
    btn = next((b for b in at.button if b.label.startswith("✍️ 写作练习")), None)
    assert btn is not None and not btn.disabled, "选课=全部 时写作入口不该消失"


def test_task_list_spans_lessons_and_shows_which_one(at):
    at.selectbox(key="sel_lesson").set_value("L34").run()
    _enter_writing(at)
    opts = at.selectbox(key="wr_task_sel").options
    assert any("L33-W1" in o for o in opts), f"够不到别课的题：{opts}"
    assert all(o.split(" · ")[0].startswith("L") for o in opts), "每道题要标出属于哪一课"
    assert opts[0].startswith("L34"), "当前选课的题排前面"


def test_current_task_gets_shared_ammo_from_the_same_task_type(at):
    at.selectbox(key="sel_lesson").set_value("L34").run()
    _enter_writing(at)
    opts = at.selectbox(key="wr_task_sel").options
    at.selectbox(key="wr_task_sel").set_value(next(o for o in opts if "L34-W1" in o)).run()
    assert not at.exception
    shared = [e for e in at.expander if e.label.startswith("📦 这类题通用")]
    assert shared, "L34-W1 应拿到 L33-W1 里标了 task_type/general 的素材"
    assert all("来自" in e.label for e in shared), "要写明来自哪一课"
    assert all(e.proto.expanded is False for e in shared), \
        "默认折起来：本题的弹药在上面，这些是写不动时才翻的储备"


def test_other_task_type_does_not_leak(at):
    """L34-W2 是 tache_2，不该收到 tache_1 的通用素材。"""
    at.selectbox(key="sel_lesson").set_value("L34").run()
    _enter_writing(at)
    opts = at.selectbox(key="wr_task_sel").options
    at.selectbox(key="wr_task_sel").set_value(next(o for o in opts if "L34-W2" in o)).run()
    assert not at.exception
    assert not [e for e in at.expander if e.label.startswith("📦 这类题通用")], \
        "全库只有 L34-W2 一道 tache_2，不该有跨题素材"
