"""写作双栏工作台（Streamlit 原生组件）。不写 SQL、不读 JSON，只经注入的 service。"""
from __future__ import annotations

import streamlit as st

from writing.contracts import WritingTask, WritingVersion
from writing.service import WritingService


def render_writing(service: WritingService, lesson: str, on_exit) -> None:
    st.markdown(_STYLE, unsafe_allow_html=True)   # 纯装饰样式，每次 rerun 重发一遍
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

    left, right = st.columns([2, 3])   # 写作文不需要宽，资料区多行阅读需要宽
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


_STYLE = """
<style>
/* 写作资料区样式。挂载点是 st.container(key=...) 生成的 st-key-* class——
   那是 Streamlit 按我们给的 key 生成的受支持行为，不是 st-emotion-cache-* 那类
   会随版本变的编译产物。要换色/换密度只改这一段，不用碰渲染代码。 */
[class*="st-key-wr_step_"] {
    background: rgba(49, 51, 63, .045);
    border-radius: 8px;
    padding: 6px 12px !important;   /* Streamlit 自带 padding 优先级更高，必须 important */
    margin-bottom: 6px;
}
[class*="st-key-wr_flow_"] {
    background: transparent;
    border: 1px dashed rgba(49, 51, 63, .25);
    border-radius: 8px;
    padding: 6px 12px !important;
    margin-bottom: 6px;
}
[class*="st-key-wr_legend"] p {
    font-size: .85em;               /* 视觉上等同 caption，但不带 caption 的 opacity:.6
                                       —— 那个 opacity 会把 10% 的底色乘成 6%，等于没有 */
    margin-bottom: .25rem;
}
</style>
"""

_LEGEND = (
    ":green-background[绿底]:gray[＝老师核验·直接抄]　"
    ":orange-background[橙底]:gray[＝AI 起草·可抄]　"
    ":red-background[红底]:gray[＝转录重构·核了再抄]　"
    ":gray[⭕必答 ➕加分 ⚠️风险]"
)
_RIGHT_PANEL_HEIGHT = 620   # px；与左栏「正文框 + 字数 + 按钮」大致齐平，资料区在框内滚动
_SLOT_ICON = {"must": "⭕", "bonus": "➕", "risk": "⚠️"}
_REVIEW_BADGE = {"teacher_reviewed": "老师核验", "ai_draft": "AI 起草", "needs_review": "待核对"}


def _support_line(sup, with_evidence: bool = False) -> str:
    badge = _REVIEW_BADGE.get(sup.review, sup.review)
    src = f" ｜出处 {sup.source.path}:{sup.source.locator}" if sup.source else ""
    out = f"**{sup.title}**（{badge}{src}）\n\n{sup.body}"
    if with_evidence and sup.source and sup.source.note:
        note = sup.source.note.replace("\n", " ")
        out += f"\n\n> :gray[核验 {sup.source.verify}　{note}]"
    return out


def _render_supports(task: WritingTask, categories: tuple[str, ...]) -> None:
    sups = [s for s in task.supports if s.category in categories]
    if not sups:
        st.caption("（暂无内容）")
        return
    for sup in sups:
        with st.expander(sup.title, expanded=False):
            st.markdown(_support_line(sup, with_evidence=True))


def _render_breakdown(task: WritingTask) -> None:
    """题目拆解：两张窄表，槽位是二维数据，不该串成 bullet。"""
    def _cell(t: str) -> str:
        return t.replace("|", "｜").replace("\n", " ")

    lines = [
        f"`{task.tcf_task_type}`　:gray[受众] {task.audience}　"
        f":gray[语域] {task.register}　:gray[字数] {task.word_min}–{task.word_max} 词",
        "", f":gray[交际目的] {task.purpose}",
        "", "**⭕ 必答清单**　:gray[交卷前逐项点一遍]", "",
        "| | 槽位 | 来源 |", "|---|---|---|",
    ]
    for s in task.slots:
        if s.kind == "must":
            lines.append(f"| ⭕ | **{_cell(s.label)}** | :gray[{s.origin}] |")
    lines += ["", "**⚠️ 扣分风险**", "", "| 风险 | 一句话 |", "|---|---|"]
    for s in task.slots:
        if s.kind == "risk":
            one = _cell(s.note.split("。")[0].replace("⚠️ ", ""))
            lines.append(f"| ⚠️ **{_cell(s.label)}** | :gray[{one}] |")
    bonus = [s for s in task.slots if s.kind == "bonus"]
    if bonus:
        lines += ["", "**➕ 加分项**", ""]
        lines += [f"- ➕ {_cell(s.label)}　:gray[{_cell(s.note)}]" for s in bonus]
    st.markdown("\n".join(lines))


def _render_flat(task: WritingTask, categories: tuple[str, ...]) -> None:
    """平铺：正文一眼可扫，不再逐条折叠。"""
    sups = [s for s in task.supports if s.category in categories]
    if not sups:
        st.caption("（暂无内容）")
        return
    buf = []
    for sup in sups:
        buf += [_support_line(sup), ""]
    st.markdown("\n".join(buf))


def _render_ammo(task: WritingTask) -> None:
    """弹药库双视图：组装线按 step 分组供写作，详解按 category 折叠供吸收。"""
    view = st.segmented_control(
        "视图", ["🔧 组装线", "📖 详解"], default="🔧 组装线",
        key="wr_ammo_view", label_visibility="collapsed",
    )
    if view == "📖 详解":
        _render_supports(task, ("content_ammo", "language_ammo"))
        if task.reference_text:
            with st.expander("📄 参考全文（展开即照抄模式）", expanded=False):
                st.markdown(task.reference_text)
        return
    if not task.skeleton:
        st.caption("这道题所属的体裁还没有配置骨架，请切到「详解」。")
        return
    by_fn: dict[str, list] = {}
    for sup in task.supports:
        if sup.function:
            by_fn.setdefault(sup.function, []).append(sup)
    if not by_fn:
        st.caption("这道题的弹药还没标 function，请切到「详解」。")
        return
    slot_of = {sl.slot_id: sl for sl in task.slots}
    for step in task.skeleton:
        items = sorted(by_fn.get(step.step_id, []), key=lambda s: (s.order, s.support_id))
        if not items:
            continue
        prefix = "wr_flow_" if step.kind == "flow" else "wr_step_"
        with st.container(key=f"{prefix}{step.step_id}"):
            opt = "　:gray[（题目没要求就不写）]" if step.optional else ""
            buf = [f"**{step.name}**　:gray[{len(items)} 条]{opt}", ""]
            if step.kind == "slots":
                buf += _slot_groups(items, task, slot_of)
            else:
                for sup in items:
                    buf += [_support_line(sup), ""]
            st.markdown("\n".join(buf))


def _slot_groups(items, task: WritingTask, slot_of: dict) -> list[str]:
    """slots 格：先通用素材，再按【题目 slots 的原始顺序】分组——
    不能用 sorted(slot_id)，那会把 s14 排到 s1 和 s2 之间。"""
    buf: list[str] = []
    for sup in [x for x in items if not x.slot_id]:
        buf += [_support_line(sup), ""]
    present = {x.slot_id for x in items if x.slot_id}
    for sl in task.slots:
        if sl.slot_id not in present:
            continue
        icon = _SLOT_ICON.get(sl.kind, "•")
        group = [x for x in items if x.slot_id == sl.slot_id]
        buf += [f"{icon} **{sl.label}**　:gray[{len(group)} 条]", ""]
        for sup in group:
            buf += [_support_line(sup), ""]
    return buf


def _render_right(task: WritingTask, versions: tuple[WritingVersion, ...]) -> None:
    with st.container(height=_RIGHT_PANEL_HEIGHT):   # 资料区内部滚动，编辑器不被顶出视野
        _render_right_body(task, versions)


def _render_right_body(task: WritingTask, versions: tuple[WritingVersion, ...]) -> None:
    with st.container(key="wr_legend"):
        st.markdown(_LEGEND)
    tabs = st.tabs(["题目拆解", "骨架/逻辑", "弹药库", "老师讲解", "历史"])

    with tabs[0]:
        _render_breakdown(task)

    with tabs[1]:
        _render_flat(task, ("outline", "logic"))

    with tabs[2]:
        _render_ammo(task)

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
