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


_RIGHT_PANEL_HEIGHT = 620   # px；与左栏「正文框 + 字数 + 按钮」大致齐平，资料区在框内滚动
_SLOT_ICON = {"must": "⭕", "bonus": "➕", "risk": "⚠️"}
_REVIEW_BADGE = {"teacher_reviewed": "老师核验", "ai_draft": "AI 起草", "needs_review": "待核对"}


def _support_line(sup) -> str:
    badge = _REVIEW_BADGE.get(sup.review, sup.review)
    src = f" ｜出处 {sup.source.path}:{sup.source.locator}" if sup.source else ""
    return f"**{sup.title}**（{badge}{src}）\n\n{sup.body}"


def _render_supports(task: WritingTask, categories: tuple[str, ...]) -> None:
    sups = [s for s in task.supports if s.category in categories]
    if not sups:
        st.caption("（暂无内容）")
        return
    for sup in sups:
        with st.expander(sup.title, expanded=False):
            st.markdown(_support_line(sup))


def _render_right(task: WritingTask, versions: tuple[WritingVersion, ...]) -> None:
    with st.container(height=_RIGHT_PANEL_HEIGHT):   # 资料区内部滚动，编辑器不被顶出视野
        _render_right_body(task, versions)


def _render_right_body(task: WritingTask, versions: tuple[WritingVersion, ...]) -> None:
    tabs = st.tabs(["题目拆解", "骨架/逻辑", "弹药库", "老师讲解", "历史"])

    with tabs[0]:
        st.markdown(f"**任务类型** {task.tcf_task_type} ｜ **受众** {task.audience} "
                    f"｜ **语域** {task.register}")
        st.markdown(f"**交际目的** {task.purpose}")
        st.markdown(f"**字数** {task.word_min}–{task.word_max} 词")
        st.markdown("**得分槽位**（⭕漏答必失分 ➕加分 ⚠️扣分风险）")
        for slot in task.slots:
            icon = _SLOT_ICON.get(slot.kind, "•")
            note = f" — {slot.note}" if slot.note else ""
            st.markdown(f"- {icon} {slot.label}（{slot.origin}）{note}")

    with tabs[1]:
        _render_supports(task, ("outline", "logic"))

    with tabs[2]:
        _render_supports(task, ("content_ammo", "language_ammo"))
        if task.reference_text:
            with st.expander("📄 参考全文（展开即照抄模式）", expanded=False):
                st.markdown(task.reference_text)

    with tabs[3]:
        _render_supports(task, ("teacher_tip",))

    with tabs[4]:
        if not versions:
            st.caption("还没有提交过版本。")
        else:
            labels = {f"第 {i + 1} 版 · {v.created_at}": v
                      for i, v in enumerate(versions)}
            chosen = st.selectbox("查看版本", list(reversed(list(labels))),
                                  key="wr_hist_sel")
            st.code(labels[chosen].text)
