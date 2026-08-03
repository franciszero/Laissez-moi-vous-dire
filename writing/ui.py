"""写作双栏工作台（Streamlit 原生组件）。不写 SQL、不读 JSON，只经注入的 service。"""
from __future__ import annotations

import streamlit as st

from writing.contracts import WritingTask, WritingVersion
from writing.service import WritingService


def render_writing(service: WritingService, lesson: str, on_exit) -> None:
    tasks = service.list_tasks(lesson)
    if not tasks:
        st.info("这一课还没有写作题。")
        if st.button("↩︎ 退出写作", key="wr_exit"):
            on_exit()
            st.rerun()
        return

    labels = {f"{t.task_id} · {t.title}": t.task_id for t in tasks}
    chosen = st.selectbox("写作题", list(labels), key="wr_task_sel")
    task, draft, versions = service.open_task(lesson, labels[chosen])

    if st.button("↩︎ 退出写作", key="wr_exit"):
        on_exit()
        st.rerun()

    left, right = st.columns([3, 2])
    with left:
        _render_left(service, task, draft, versions)
    with right:
        _render_right(task, versions)


def _render_left(service: WritingService, task: WritingTask, draft, versions) -> None:
    st.subheader(task.title)
    st.markdown(task.prompt_text)
    text_key = f"wr_text_{task.task_id}"
    if text_key not in st.session_state:
        st.session_state[text_key] = draft.text if draft else ""
    text = st.text_area("正文", key=text_key, height=400)
    n_words = len(text.split())
    st.caption(f"字数：{n_words}（要求 {task.word_min}–{task.word_max} 词）")
    if draft:
        st.caption(f"草稿已存：{draft.updated_at}")

    c1, c2 = st.columns(2)
    if c1.button("💾 保存草稿", key="wr_save_draft"):
        service.save_draft(task.task_id, text)
        st.rerun()
    if c2.button("📌 保存这一版", key="wr_submit"):
        if not text.strip():
            st.warning("空文本不能提交为版本。")
        else:
            parent = versions[-1].version_id if versions else None
            service.submit_version(task.task_id, text, parent)
            st.rerun()


def _render_right(task: WritingTask, versions: tuple[WritingVersion, ...]) -> None:
    st.caption("资料区（D2 施工）")
