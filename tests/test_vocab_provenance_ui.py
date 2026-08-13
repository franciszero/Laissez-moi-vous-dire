from pathlib import Path
import json
import shutil

import store
from streamlit.testing.v1 import AppTest


def test_l31_provenance_is_available_before_answer_without_revealing_answer_panel(tmp_path):
    db_path = Path("dictation.db")
    backup_path = tmp_path / "dictation.db.bak"
    if db_path.exists():
        shutil.copy2(db_path, backup_path)

    try:
        at = AppTest.from_file("app.py", default_timeout=10).run()
        assert not at.exception
        at.selectbox(key="mode").set_value("听法语 → 敲法语").run()

        word_id = store.get_ids_for_lemmas(["une assiette"])[0]
        word = {"id": word_id, "text": "une assiette"}
        at.session_state.pool = [word_id]
        at.session_state.index = 1
        at.session_state.current_word = word
        at.session_state.round_total = 1
        at.session_state.round_lesson = "L31"
        at.session_state.round_label = "学习 · L31"
        at.session_state.show_answer = False
        at.session_state.feedback = None
        at.session_state.graded = False
        at.run()

        assert not at.exception
        provenance_expander = next(
            item for item in at.expander if item.label == "📚 为什么收录这个词"
        )
        assert provenance_expander.proto.expanded is True
        rendered = "\n".join(item.value for item in at.markdown)
        assert "L31 · 阅读 Test 5 · 第 8 题" in rendered
        assert "纠正把 `plat` 理解成盘子的错误" in rendered
        assert "对比辨析" in rendered
        assert "32:30-35:30 · 50" in rendered
        assert not any(item.value.startswith("答案：") for item in at.info)

        next(button for button in at.button if button.label == "显示答案").click().run()

        assert not at.exception
        assert [item.label for item in at.expander].count("📚 为什么收录这个词") == 1
        assert any(item.value.startswith("答案：") for item in at.info)
    finally:
        if backup_path.exists():
            shutil.copy2(backup_path, db_path)
        elif db_path.exists():
            db_path.unlink()


def test_every_l31_word_has_structured_provenance():
    rows = json.loads(Path("../L31/vocab.json").read_text("utf-8"))

    assert len(rows) == 117
    assert all(row.get("provenance") for row in rows)


def test_every_real_teacher_action_has_a_chinese_label():
    """真实词表体检：每种 teacher_action 都得有中文标签。

    没有映射时 app 会原样显示英文键名（`agent_supplement` 曾经这样露了 106 次），
    「教学关系」那一行就从人话退化成内部字段名——不报错、不崩，只是难看且看不懂。
    单测盯不住这个，因为新的 teacher_action 是数据带进来的，不是代码写出来的。

    这里用 ast 静态读 app.py 的字面量，**不 import app**：裸 import 会在 pytest 进程里
    把 app.py 整个跑一遍（含写库），后面 AppTest 起的写作用例会连环失败。
    """
    import ast
    import glob

    tree = ast.parse(Path("app.py").read_text("utf-8"))
    labels = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(t, ast.Name) and t.id == "_PROVENANCE_ACTION_LABELS"
            for t in node.targets
        )
    )

    files = sorted(glob.glob(str(Path("..") / "L*" / "vocab.json")))
    assert files, "没扫到任何 vocab.json，测试等于没跑"

    used = {
        record.get("teacher_action")
        for f in files
        for row in json.loads(Path(f).read_text("utf-8"))
        for record in row.get("provenance", [])
    }
    missing = sorted(used - set(labels))
    assert not missing, (
        f"这些 teacher_action 没有中文标签，会在「教学关系」里露出英文键名：{missing}。"
        f"把它们加进 app._PROVENANCE_ACTION_LABELS。"
    )
