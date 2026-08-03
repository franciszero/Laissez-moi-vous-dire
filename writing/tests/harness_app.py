"""AppTest 最小宿主：内存 fakes 驱动 writing.ui，与 app.py、真实 DB 无关。"""
from __future__ import annotations

import streamlit as st

from writing.contracts import ScoreSlot, WritingSupport, WritingTask
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
                           "Pourrais-tu m'aider à …", "ai_draft", 2),
            WritingSupport("sup3", "task_type", "teacher_tip", "老师嘱咐",
                           "可以查词组，不要查整句", "teacher_reviewed", 3),
        ),
        reference_text="Salut Marie, je cherche un appartement …",
    )


if "_hist" not in st.session_state:      # 同一 AppTest 实例内跨 rerun 持久
    st.session_state["_hist"] = InMemoryHistory()

service = WritingService(InMemoryContent([_task()]), st.session_state["_hist"])


def _exit() -> None:
    st.session_state["harness_exited"] = True


ui.render_writing(service, "L33", _exit)
