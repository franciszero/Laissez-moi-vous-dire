"""真实课程 JSON 的内容体检：markdown 里不能混裸 HTML。

Streamlit 的 st.markdown 默认不解析 HTML，表格单元格里的 <br> 会原样打印成
字面量（L34-W2 的连接词表就这么翻过一次车，浏览器里能看到 "<br>" 三个字符）。
这条测试盯真实数据，不盯 fake——渲染代码没问题，是内容会带进来。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

LESSON_DIRS = sorted(
    p.parent for p in Path("..").glob("L*/writing_tasks.json")
)
_HTML = re.compile(r"</?[a-zA-Z][^>]*>")
_TEXT_FIELDS = ("body", "extended")


def _rows():
    for d in LESSON_DIRS:
        doc = json.loads((d / "writing_tasks.json").read_text("utf-8"))
        for task in doc["tasks"]:
            if task.get("reference_text"):
                yield d.name, task["task_id"], "reference_text", task["reference_text"]
            for sup in task.get("supports", []):
                for f in _TEXT_FIELDS:
                    if sup.get(f):
                        yield d.name, task["task_id"], f"{sup['support_id']}.{f}", sup[f]


def test_lesson_dirs_are_discovered():
    assert LESSON_DIRS, "没找到任何 writing_tasks.json，测试等于没跑"


def test_no_raw_html_in_rendered_markdown():
    bad = [
        (lesson, task, field, sorted(set(_HTML.findall(text))))
        for lesson, task, field, text in _rows()
        if _HTML.search(text)
    ]
    assert not bad, f"markdown 里有裸 HTML，会原样显示：{bad}"


@pytest.mark.parametrize("field", _TEXT_FIELDS)
def test_markdown_tables_have_no_cell_line_breaks(field):
    """表格单元格里不能塞换行——markdown 表格一行就是一行，
    想并列多个选项用 ・ 分隔，或者拆成多行。"""
    bad = [
        (lesson, task, name)
        for lesson, task, name, text in _rows()
        if name.endswith(f".{field}")
        for line in text.splitlines()
        if line.strip().startswith("|") and ("<br" in line or "\\n" in line)
    ]
    assert not bad, f"表格单元格里有换行标记：{bad}"
