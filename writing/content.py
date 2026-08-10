# writing/content.py
"""lesson-owned writing_tasks.json 的加载与校验。只读内容，不碰学习历史。"""
from __future__ import annotations

import json
from pathlib import Path

from writing.contracts import (
    ScoreSlot,
    SkeletonStep,
    SourceRef,
    WritingSupport,
    WritingTask,
    WritingTaskSummary,
)

_REQUIRED_TASK_FIELDS = (
    "task_id", "lesson", "tcf_task_type", "title", "prompt_text",
    "audience", "register", "purpose", "word_min", "word_max", "status",
)


class ContentError(ValueError):
    """内容文件不合法（缺字段、重复 ID 等）。"""


def _require(d: dict, fields, where: str) -> None:
    missing = [f for f in fields if f not in d]
    if missing:
        raise ContentError(f"{where} 缺少字段: {', '.join(missing)}")


def _parse_source(d: dict | None) -> SourceRef | None:
    if d is None:
        return None
    _require(d, ("lesson", "kind", "path"), "source")
    return SourceRef(
        lesson=d["lesson"], kind=d["kind"], path=d["path"],
        locator=d.get("locator", ""), verify=d.get("verify", "needs_review"),
        note=d.get("note", ""),
    )


def _parse_slot(d: dict) -> ScoreSlot:
    _require(d, ("slot_id", "label", "kind", "origin"), "slot")
    return ScoreSlot(
        slot_id=d["slot_id"], label=d["label"], kind=d["kind"],
        origin=d["origin"], note=d.get("note", ""),
    )


def _parse_support(d: dict) -> WritingSupport:
    _require(d, ("support_id", "scope", "category", "title", "body", "review", "order"),
             "support")
    return WritingSupport(
        support_id=d["support_id"], scope=d["scope"], category=d["category"],
        title=d["title"], body=d["body"], review=d["review"], order=d["order"],
        modality=d.get("modality", "writing"), conditions=d.get("conditions", ""),
        source=_parse_source(d.get("source")),
        function=str(d.get("function", "")), slot_id=str(d.get("slot_id", "")),
        extended=str(d.get("extended", "")),
    )


def _parse_skeleton_step(d: dict) -> SkeletonStep:
    _require(d, ("step_id", "name", "kind"), "skeleton step")
    return SkeletonStep(
        step_id=d["step_id"], name=d["name"], kind=d["kind"],
        optional=bool(d.get("optional", False)),
    )


def _parse_task(d: dict, skeleton: tuple[SkeletonStep, ...] = ()) -> WritingTask:
    _require(d, _REQUIRED_TASK_FIELDS, f"task {d.get('task_id', '?')}")
    supports = tuple(sorted((_parse_support(s) for s in d.get("supports", [])),
                            key=lambda s: (s.order, s.support_id)))
    sup_ids = [s.support_id for s in supports]
    if len(sup_ids) != len(set(sup_ids)):
        raise ContentError(f"task {d['task_id']} support_id 重复")
    return WritingTask(
        task_id=d["task_id"], lesson=d["lesson"], tcf_task_type=d["tcf_task_type"],
        title=d["title"], prompt_text=d["prompt_text"], audience=d["audience"],
        register=d["register"], purpose=d["purpose"],
        word_min=d["word_min"], word_max=d["word_max"], status=d["status"],
        slots=tuple(_parse_slot(s) for s in d.get("slots", [])),
        supports=supports,
        sources=tuple(s for s in (_parse_source(x) for x in d.get("sources", [])) if s),
        reference_text=d.get("reference_text", ""),
        time_limit_minutes=d.get("time_limit_minutes", 0),
        skeleton=skeleton,
    )


class JsonWritingContent:
    """WritingContentPort 的真适配器：读 {root}/{lesson}/writing_tasks.json。"""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def _load_skeletons(self) -> dict[str, tuple[SkeletonStep, ...]]:
        """体裁骨架属于 tcf_task_type，跨课共用，所以放在内容根而非每课目录下。"""
        path = self._root / "writing_skeletons.json"
        if not path.exists():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        return {
            k: tuple(_parse_skeleton_step(x) for x in v.get("flow", []))
            for k, v in data.get("skeletons", {}).items()
        }

    def _load_all(self) -> tuple[WritingTask, ...]:
        """扫全库的 L*/writing_tasks.json。

        lesson 不再是「找文件的路径」，只是题目的一个属性——加载出来的
        WritingTask 自带 .lesson。这样才能不选课就列题，也才能在渲染 A 题时
        取到 B 题里标了「本类题/通用」的素材。
        """
        sk = self._load_skeletons()
        out: list[WritingTask] = []
        for path in sorted(self._root.glob("L*/writing_tasks.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            tasks = [
                _parse_task(t, sk.get(t.get("tcf_task_type", ""), ()))
                for t in data.get("tasks", [])
            ]
            ids = [t.task_id for t in tasks]
            if len(ids) != len(set(ids)):
                raise ContentError(f"{path} task_id 重复")
            # 目录名和 lesson 字段必须一致。跨课加载之后 lesson 字段成了归属的
            # 唯一依据，写错就会把题悄悄归到别的课去，且不报任何错。
            wrong = [t.task_id for t in tasks if t.lesson != path.parent.name]
            if wrong:
                raise ContentError(
                    f"{path}：lesson 字段与目录名 {path.parent.name} 不符 → {wrong}")
            out += tasks
        ids = [t.task_id for t in out]
        dup = {i for i in ids if ids.count(i) > 1}
        if dup:
            raise ContentError(f"task_id 跨课重复：{sorted(dup)}——它现在是全库唯一键")
        return tuple(out)

    def list_tasks(self, lesson: str | None = None) -> tuple[WritingTaskSummary, ...]:
        return tuple(
            WritingTaskSummary(t.task_id, t.lesson, t.title, t.tcf_task_type)
            for t in self._load_all()
            if t.status == "teacher_reviewed" and lesson in (None, "全部", t.lesson)
        )

    def load_task(self, task_id: str) -> WritingTask:
        for t in self._load_all():
            if t.task_id == task_id:
                return t
        raise KeyError(task_id)

    def shared_supports(self, task: WritingTask):
        """同体裁其他题里标了 task_type/general 的素材，带来源课号。

        只从 teacher_reviewed 的题里取：draft 状态的题还没核验过，它的「通用」
        素材不该悄悄流进别的题。
        """
        return tuple(
            (other.lesson, sup)
            for other in self._load_all()
            if other.task_id != task.task_id
            and other.tcf_task_type == task.tcf_task_type
            and other.status == "teacher_reviewed"
            for sup in other.supports
            if sup.scope in ("task_type", "general")
        )
