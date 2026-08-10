# writing/tests/test_content.py
from __future__ import annotations

import json
from pathlib import Path

import pytest

from writing.content import ContentError, JsonWritingContent


def _doc(**task_over):
    task = {
        "task_id": "L33-W1", "lesson": "L33", "tcf_task_type": "tache_1",
        "title": "给朋友写邮件找房", "prompt_text": "écrire un mail",
        "audience": "ami", "register": "informel", "purpose": "demander",
        "word_min": 60, "word_max": 120, "status": "teacher_reviewed",
        "time_limit_minutes": 0, "reference_text": "",
        "slots": [{"slot_id": "s1", "label": "budget", "kind": "must",
                   "origin": "teacher", "note": ""}],
        "supports": [
            {"support_id": "b", "scope": "task", "category": "logic",
             "title": "转折", "body": "mais / pourtant", "review": "ai_draft",
             "order": 2, "modality": "writing", "conditions": "", "source": None},
            {"support_id": "a", "scope": "task", "category": "outline",
             "title": "骨架", "body": "称呼→目的→请求", "review": "teacher_reviewed",
             "order": 1, "modality": "writing", "conditions": "",
             "source": {"lesson": "L33", "kind": "transcript", "path": "t.md",
                        "locator": "280", "verify": "needs_review", "note": ""}},
        ],
        "sources": [],
    }
    task.update(task_over)
    return {"schema": 1, "tasks": [task]}


def _write(root: Path, doc, lesson="L33"):
    (root / lesson).mkdir(parents=True, exist_ok=True)
    (root / lesson / "writing_tasks.json").write_text(
        json.dumps(doc, ensure_ascii=False), encoding="utf-8")


def test_missing_file_means_empty_list(tmp_path):
    assert JsonWritingContent(tmp_path).list_tasks("L33") == ()


def test_load_task_parses_and_sorts_supports(tmp_path):
    _write(tmp_path, _doc())
    c = JsonWritingContent(tmp_path)
    t = c.load_task("L33-W1")
    assert [s.support_id for s in t.supports] == ["a", "b"]  # 按 order 稳定排序
    assert t.supports[0].source is not None and t.supports[0].source.locator == "280"
    assert t.slots[0].kind == "must"


def test_list_excludes_draft_but_load_still_works(tmp_path):
    doc = _doc(status="draft")
    _write(tmp_path, doc)
    c = JsonWritingContent(tmp_path)
    assert c.list_tasks("L33") == ()
    assert c.load_task("L33-W1").status == "draft"


def test_missing_required_field_raises_with_field_name(tmp_path):
    doc = _doc()
    del doc["tasks"][0]["prompt_text"]
    _write(tmp_path, doc)
    with pytest.raises(ContentError, match="prompt_text"):
        JsonWritingContent(tmp_path).load_task("L33-W1")


def test_duplicate_task_id_raises(tmp_path):
    doc = _doc()
    doc["tasks"].append(dict(doc["tasks"][0]))
    _write(tmp_path, doc)
    with pytest.raises(ContentError, match="task_id"):
        JsonWritingContent(tmp_path).list_tasks("L33")


def test_unknown_task_raises_keyerror(tmp_path):
    _write(tmp_path, _doc())
    with pytest.raises(KeyError):
        JsonWritingContent(tmp_path).load_task("nope")


def _write_skeletons(root: Path):
    (root / "writing_skeletons.json").write_text(json.dumps({
        "schema": 1,
        "skeletons": {"tache_1": {"name": "TCF Tâche 1", "flow": [
            {"step_id": "pick_scenario", "name": "选一个情境", "kind": "flow"},
            {"step_id": "subject", "name": "邮件主题", "kind": "fixed", "optional": True},
            {"step_id": "slot_fill", "name": "展开必答信息", "kind": "slots"},
        ]}},
    }, ensure_ascii=False), encoding="utf-8")


def test_function_and_slot_id_are_parsed(tmp_path):
    doc = _doc()
    doc["tasks"][0]["supports"][1]["function"] = "slot_fill"
    doc["tasks"][0]["supports"][1]["slot_id"] = "s1"
    _write(tmp_path, doc)
    t = JsonWritingContent(tmp_path).load_task("L33-W1")
    by_id = {s.support_id: s for s in t.supports}
    assert by_id["a"].function == "slot_fill" and by_id["a"].slot_id == "s1"
    assert by_id["b"].function == "" and by_id["b"].slot_id == ""


def test_skeleton_is_attached_by_task_type(tmp_path):
    """骨架按 tcf_task_type 装配——它跨课共用，不住在每课的 writing_tasks.json 里。"""
    _write(tmp_path, _doc())
    _write_skeletons(tmp_path)
    t = JsonWritingContent(tmp_path).load_task("L33-W1")
    assert [s.step_id for s in t.skeleton] == ["pick_scenario", "subject", "slot_fill"]
    assert [s.kind for s in t.skeleton] == ["flow", "fixed", "slots"]
    assert t.skeleton[1].optional is True


def test_missing_skeleton_file_means_empty(tmp_path):
    _write(tmp_path, _doc())
    assert JsonWritingContent(tmp_path).load_task("L33-W1").skeleton == ()


def test_unknown_task_type_gets_no_skeleton(tmp_path):
    _write(tmp_path, _doc(tcf_task_type="tache_3"))
    _write_skeletons(tmp_path)
    assert JsonWritingContent(tmp_path).load_task("L33-W1").skeleton == ()


def test_tasks_are_reachable_without_naming_a_lesson(tmp_path):
    """写作题是独立实体，课只是它的一个属性。不选课也要能列全。"""
    _write(tmp_path, _doc(), lesson="L33")
    _write(tmp_path, _doc(task_id="L34-W1", lesson="L34"), lesson="L34")
    c = JsonWritingContent(tmp_path)
    assert {s.task_id for s in c.list_tasks()} == {"L33-W1", "L34-W1"}
    assert {s.task_id for s in c.list_tasks("L34")} == {"L34-W1"}
    assert {s.task_id for s in c.list_tasks("全部")} == {"L33-W1", "L34-W1"}
    assert c.load_task("L34-W1").lesson == "L34"      # 不用告诉它是哪一课


def test_task_id_must_be_unique_across_lessons(tmp_path):
    """task_id 现在是全库唯一键——load_task 只凭它找题。"""
    _write(tmp_path, _doc(task_id="W1", lesson="L33"), lesson="L33")
    _write(tmp_path, _doc(task_id="W1", lesson="L34"), lesson="L34")   # 同 id 不同课
    with pytest.raises(ContentError, match="跨课重复"):
        JsonWritingContent(tmp_path).list_tasks()


def test_shared_supports_cross_task_by_scope(tmp_path):
    """scope=task_type/general 的素材本就该被同体裁的题共用。

    这个字段一直有人填、却从没人读，25 条通用弹药因此锁死在 L33-W1 里。
    """
    donor = _doc()
    donor["tasks"][0]["supports"] = [
        {"support_id": "own", "scope": "task", "category": "outline", "title": "本题专用",
         "body": "x", "review": "ai_draft", "order": 1},
        {"support_id": "shared_tt", "scope": "task_type", "category": "outline",
         "title": "本类题通用", "body": "y", "review": "ai_draft", "order": 2},
        {"support_id": "shared_g", "scope": "general", "category": "language_ammo",
         "title": "通用写作", "body": "z", "review": "ai_draft", "order": 3},
    ]
    _write(tmp_path, donor, lesson="L33")
    _write(tmp_path, _doc(task_id="L34-W1", lesson="L34"), lesson="L34")

    c = JsonWritingContent(tmp_path)
    got = c.shared_supports(c.load_task("L34-W1"))
    assert {s.support_id for _, s in got} == {"shared_tt", "shared_g"}, "只取跨题档，不取本题专用"
    assert {les for les, _ in got} == {"L33"}, "要带来源课号，学习者得知道它从哪来"


def test_shared_supports_ignore_other_task_types(tmp_path):
    _write(tmp_path, _doc(), lesson="L33")
    other = _doc(task_id="L34-W2", lesson="L34")
    other["tasks"][0]["tcf_task_type"] = "tache_2"
    other["tasks"][0]["supports"] = [
        {"support_id": "t2", "scope": "general", "category": "outline", "title": "t2",
         "body": "x", "review": "ai_draft", "order": 1}]
    _write(tmp_path, other, lesson="L34")
    c = JsonWritingContent(tmp_path)
    assert c.shared_supports(c.load_task("L33-W1")) == (), "tache_2 的素材不该流进 tache_1"


def test_shared_supports_skip_draft_tasks(tmp_path):
    """draft 还没核验，它的「通用」素材不该悄悄流进别的题。"""
    draft = _doc(status="draft")
    draft["tasks"][0]["supports"] = [
        {"support_id": "g", "scope": "general", "category": "outline", "title": "g",
         "body": "x", "review": "ai_draft", "order": 1}]
    _write(tmp_path, draft, lesson="L33")
    _write(tmp_path, _doc(task_id="L34-W1", lesson="L34"), lesson="L34")
    c = JsonWritingContent(tmp_path)
    assert c.shared_supports(c.load_task("L34-W1")) == ()


def test_lesson_field_must_match_its_directory(tmp_path):
    """跨课加载之后 lesson 字段是归属的唯一依据，写错会悄悄归到别的课。"""
    _write(tmp_path, _doc(), lesson="L34")     # 字段写 L33，却放在 L34/
    with pytest.raises(ContentError, match="与目录名"):
        JsonWritingContent(tmp_path).list_tasks()
