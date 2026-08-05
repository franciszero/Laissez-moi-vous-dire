from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

HARNESS = str(Path(__file__).parents[1] / "writing" / "tests" / "harness_app.py")


def _app() -> AppTest:
    at = AppTest.from_file(HARNESS, default_timeout=10)
    at.run()
    assert not at.exception
    return at


def _btn(at: AppTest, label: str):
    b = next((b for b in at.button if b.label == label), None)
    assert b is not None, f"找不到按钮: {label}"
    return b


def test_layout_has_editor_and_word_count():
    at = _app()
    assert at.text_area(key="wr_text_T1") is not None
    assert any("字数" in c.value for c in at.caption)


def test_draft_save_then_restore_caption():
    at = _app()
    at.text_area(key="wr_text_T1").set_value("Salut, je cherche un studio.").run()
    _btn(at, "💾 保存草稿").click().run()
    assert not at.exception
    assert any(c.value.startswith("草稿已存") for c in at.caption)


def test_exit_calls_on_exit():
    at = _app()
    _btn(at, "↩︎ 退出写作").click().run()
    assert at.session_state["harness_exited"] is True


def test_right_column_has_five_tabs():
    at = _app()
    tab_labels = [t.label for t in at.tabs]
    for want in ("题目拆解", "骨架/逻辑", "弹药库", "老师讲解", "历史"):
        assert want in tab_labels, tab_labels


def test_slots_show_kind_icons():
    at = _app()
    joined = " ".join(m.value for m in at.markdown)
    assert "budget" in joined and "⭕" in joined      # must 槽位
    assert "formule de politesse" in joined and "➕" in joined  # bonus 槽位


def test_submit_version_appears_in_history():
    at = _app()
    at.text_area(key="wr_text_T1").set_value("Salut Marie, je cherche un studio.").run()
    _btn(at, "📌 保存这一版").click().run()
    assert not at.exception
    sel = at.selectbox(key="wr_hist_sel")
    assert sel is not None and len(sel.options) == 1


def test_submit_empty_shows_warning_no_version():
    at = _app()
    at.text_area(key="wr_text_T1").set_value("   ").run()
    _btn(at, "📌 保存这一版").click().run()
    assert len(at.warning) >= 1
    # 无版本时历史里没有选择框。注意 AppTest 的 at.selectbox(key=...) 找不到 key 时
    # 抛 KeyError（不返回 None），所以断言 key 不在 widget 列表里，而不是断言返回值为 None。
    assert all(s.key != "wr_hist_sel" for s in at.selectbox)


def test_right_panel_is_height_bounded():
    """右栏必须封在固定高度容器里，否则资料区会把编辑器顶出视野。"""
    src = Path(__file__).parents[1] / "writing" / "ui.py"
    text = src.read_text(encoding="utf-8")
    assert "_RIGHT_PANEL_HEIGHT = 620" in text, "缺少固定高度常量"
    assert "st.container(height=_RIGHT_PANEL_HEIGHT)" in text, "右栏未使用固定高度容器"
    assert "def _render_right_body(" in text, "内容渲染未拆出 _render_right_body"


def test_info_column_is_wider_than_editor():
    """写作文不需要宽度，资料区多行阅读需要宽度。"""
    src = Path(__file__).parents[1] / "writing" / "ui.py"
    text = src.read_text(encoding="utf-8")
    assert "st.columns([2, 3])" in text, "资料区应比编辑区宽"
    assert "st.columns([3, 2])" not in text, "旧的 3:2 比例应已移除"


def test_task_breakdown_is_one_markdown_block():
    """题目拆解整段必须合并成一次 st.markdown，否则每条槽位之间被塞 16px 块间距。"""
    at = _app()
    merged = [m.value for m in at.markdown if "必答清单" in m.value]
    assert merged, "找不到必答清单块"
    assert "扣分风险" in merged[0], "必答清单与扣分风险应在同一个 markdown 块内"
    assert "budget" in merged[0] and "formule de politesse" in merged[0], \
        "全部槽位应与标题同在一个 markdown 块内"


def test_legend_row_is_shown():
    """图例常驻。必须走 markdown——caption 的 opacity:.6 会把 10% 底色乘成 6%，等于没有。"""
    at = _app()
    assert any("老师核验" in m.value and "转录重构" in m.value for m in at.markdown), \
        "找不到图例行"
    assert not any("老师核验" in c.value for c in at.caption), \
        "图例不能放 caption 里，底色会被 opacity 吃掉"


def test_breakdown_renders_as_tables():
    """槽位是二维数据，用表格而不是 bullet。"""
    at = _app()
    merged = [m.value for m in at.markdown if "必答清单" in m.value][0]
    assert "|---|" in merged, "必答清单应是 markdown 表格"
    assert merged.count("|---|") >= 2, "必答清单与扣分风险应各有一张表"


def test_ammo_defaults_to_assembly_view():
    at = _app()
    w = at.segmented_control(key="wr_ammo_view")
    assert w is not None and w.value == "🔧 组装线"


def test_assembly_line_groups_by_step():
    """组装线按 step 分组，标出步号与步名。"""
    at = _app()
    joined = " ".join(m.value for m in at.markdown)
    assert "3. Objectif général" in joined, "组装线应按骨架段名分组，而不是步号"
    assert "请求句型" in joined, "带 function 的弹药应出现在对应格里"
    assert "（题目没要求就不写）" in joined, "optional 的格应标出可选"


def test_detail_view_restores_expanders():
    """切到详解，弹药回到折叠块（供吸收，不供边写边挑）。"""
    at = _app()
    before = len(at.expander)
    at.segmented_control(key="wr_ammo_view").set_value("📖 详解").run()
    assert not at.exception
    assert len(at.expander) > before, "详解视图应多出弹药折叠块"
    assert any(e.label == "请求句型" for e in at.expander)


def test_skeleton_tab_is_flat():
    """骨架/逻辑 平铺，不再逐条折叠。"""
    at = _app()
    assert not any(e.label == "段落骨架" for e in at.expander), "骨架条目不应再是折叠块"
    assert any("段落骨架" in m.value for m in at.markdown), "骨架条目应平铺进 markdown"


def test_assembly_step_is_boxed_and_counted():
    """每步一个边框容器（范围可见）+ 步头带条数（未读先知量）。"""
    src = (Path(__file__).parents[1] / "writing" / "ui.py").read_text(encoding="utf-8")
    assert 'f"{prefix}{step.step_id}"' in src, "每格应按 step_id 给 key 供 CSS 挂载"
    assert '[class*="st-key-wr_step_"]' in src, "文章格样式挂 st-key-wr_step_*"
    assert '[class*="st-key-wr_flow_"]' in src, "流程格样式挂 st-key-wr_flow_*（虚线，非文章结构）"
    at = _app()
    joined = " ".join(m.value for m in at.markdown)
    assert "1 条" in joined, "步头应显示该步条数"


def test_evidence_quote_is_opt_in():
    """source.note 一直不可见（标签失真的老病根）。详解显式要证据，组装线不塞。"""
    from writing import ui
    from writing.contracts import SourceRef, WritingSupport

    sup = WritingSupport(
        "x", "task", "logic", "标题", "正文", "teacher_reviewed", 1,
        source=SourceRef("L33", "transcript", "t.md", "280", "needs_review", "ASR 三路打架"),
    )
    plain = ui._support_line(sup)
    rich = ui._support_line(sup, with_evidence=True)
    assert "> :gray[核验" not in plain, "组装线用的默认形态不应带证据引用块"
    assert "> :gray[核验 needs_review" in rich and "ASR 三路打架" in rich, \
        "详解形态应把核验状态与来源备注显为引用块"


def test_stylesheet_hooks_only_supported_classes():
    """CSS 只许挂 st-key-*（Streamlit 按我们给的 key 生成，受支持）。
    禁止挂 st-emotion-cache-*（编译产物）或 data-testid（内部结构）——升级即碎。"""
    import re

    from writing import ui

    # 只查 CSS 正文并剥掉注释——注释里会写"为什么不用 st-emotion-cache"，别自己绊自己
    css = re.sub(r"/\*.*?\*/", "", ui._STYLE, flags=re.S)
    assert "st-key-" in css, "样式必须挂在 st-key-* 上"
    assert "st-emotion-cache" not in css, "禁止依赖 Streamlit 编译产物类名做样式挂载"
    assert "data-testid" not in css, "禁止依赖 Streamlit 内部 testid 做样式挂载"


def test_slot_step_expands_in_task_slot_order():
    """slots 格按【题目 slots 的原始顺序】展开，不能 sorted(slot_id)——
    那会把 s14 排到 s1 和 s2 之间。"""
    src = (Path(__file__).parents[1] / "writing" / "ui.py").read_text(encoding="utf-8")
    assert "for sl in task.slots:" in src, "应遍历 task.slots 保序，而不是对 slot_id 排序"
    at = _app()
    joined = " ".join(m.value for m in at.markdown)
    assert "4. Détails" in joined and "budget" in joined, "slots 格应展开出题目的槽位"
    assert "怎么展开" in joined, "无 slot_id 的通用素材应排在分组之前"


def test_flow_steps_are_visually_separate_from_article_steps():
    """选情境/交卷检查是练习流程，不是文章的一格——挂不同的 CSS 前缀。"""
    src = (Path(__file__).parents[1] / "writing" / "ui.py").read_text(encoding="utf-8")
    assert '"wr_flow_" if step.kind == "flow" else "wr_step_"' in src, \
        "flow 与 fixed/slots 必须挂不同前缀"


def test_step_field_is_gone():
    """step 曾经把三个抽象层压成一个字符串，本卡移除。"""
    from writing.contracts import WritingSupport
    assert not hasattr(WritingSupport("x", "task", "logic", "T", "B", "ai_draft", 1), "step"), \
        "WritingSupport.step 应已移除，改用 function"
    ui = (Path(__file__).parents[1] / "writing" / "ui.py").read_text(encoding="utf-8")
    assert "_STEP_NAME" not in ui, "步名应由内容层的骨架提供，不再硬编码在 UI 里"
