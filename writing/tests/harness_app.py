"""AppTest 最小宿主：内存 fakes 驱动 writing.ui，与 app.py、真实 DB 无关。"""
from __future__ import annotations

import streamlit as st

from writing.contracts import ScoreSlot, SkeletonStep, WritingSupport, WritingTask
from writing.service import WritingService
from writing.tests.fakes import InMemoryContent, InMemoryHistory
from writing import ui


def _task() -> WritingTask:
    return WritingTask(
        task_id="T1", lesson="L33", tcf_task_type="tache_1", title="测试题",
        prompt_text="Écrire un mail à un ami.", audience="ami", register="informel",
        purpose="demander de l'aide", word_min=60, word_max=120,
        status="teacher_reviewed",
        slots=(ScoreSlot("s1", "budget", "must", "teacher"),
               ScoreSlot("s2", "formule de politesse", "bonus", "teacher")),
        supports=(
            WritingSupport("sup1", "task", "outline", "段落骨架",
                           "称呼 → 目的 → 请求 → 结尾", "teacher_reviewed", 1),
            WritingSupport("sup2", "task", "language_ammo", "请求句型",
                           "Pourrais-tu m'aider à …", "ai_draft", 2,
                           function="objectif_general"),
            WritingSupport("sup4", "task", "content_ammo", "预算说法",
                           "Mon budget est de 800 dollars.", "ai_draft", 4,
                           function="details", slot_id="s1",
                           extended="| 档位 | 说法 |\n|---|---|\n| 低 | pas cher |"),
            WritingSupport("sup5", "task", "outline", "怎么展开",
                           "Qui ? Quoi ? Quand ?", "teacher_reviewed", 5,
                           function="details"),
            WritingSupport("sup6", "task", "language_ammo", "选情境",
                           "A / B / C", "ai_draft", 6, function="pick_scenario"),
            WritingSupport("sup7", "task", "language_ammo", "主题行",
                           "Objet : Recherche…", "teacher_reviewed", 7, function="en_tete"),
            WritingSupport("sup3", "task_type", "teacher_tip", "老师嘱咐",
                           "可以查词组，不要查整句", "teacher_reviewed", 3),
        ),
        reference_text="Salut Marie, je cherche un appartement …",
        skeleton=(
            SkeletonStep("pick_scenario", "选一个情境", "flow"),
            SkeletonStep("objectif_general", "3. Objectif général · 亮明目的", "fixed"),
            SkeletonStep("details", "4. Détails · 展开细节", "slots"),
            SkeletonStep("en_tete", "1. En-tête · 邮件头", "fixed", optional=True),
        ),
    )


if "_hist" not in st.session_state:      # 同一 AppTest 实例内跨 rerun 持久
    st.session_state["_hist"] = InMemoryHistory()

service = WritingService(InMemoryContent([_task()]), st.session_state["_hist"])


def _exit() -> None:
    st.session_state["harness_exited"] = True


ui.render_writing(service, "L33", _exit)
