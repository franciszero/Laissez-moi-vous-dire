"""AI 精练批改的「确定性」部分：构造批改 prompt、归一化模型 JSON、
把模型给的「锚定片段」在学生原句里逐字验证并染色。

设计要点（见 HANDOFF §5）：
- 1-4（候选词/变位/句式/参考句）是出题时固化的人工规范，不在运行时让模型现编。
- 5-7 由本地模型按规范判，状态是开放集（不是白名单）。
- 第 8 步染色：模型只给「片段+状态」，**位置由代码用子串重新定位验证**，模型给的
  数字偏移一律忽略；定位不到的片段（模型幻觉）丢弃。颜色 = 模型判断，标「需核验」。
"""
from __future__ import annotations

import html
import json

# 开放状态集（codex 评审 #2）：规范是参照不是词汇监狱。
VALID_STATUS = ("正确", "可接受变体", "正确但不自然", "错误", "多余", "拿不准")

# 四色语义（codex 评审 #5）：把「错误」与「不自然」分开，别把可接受写法教成错。
STATUS_STYLE = {
    "正确": "background:#c8e6c9;",
    "可接受变体": "background:#dcedc8;",
    "正确但不自然": "background:#fff9c4;",                       # 黄：可接受但不自然/偏题
    "错误": "background:#ffcdd2;",                               # 红：真正错误
    "多余": "background:#eeeeee;color:#9e9e9e;text-decoration:line-through;",  # 灰删除线：应删除
    "拿不准": "background:#f5f5f5;color:#757575;",
    "未标注": "",
}


def _norm_apos(s: str) -> str:
    """只把弯撇号统一成直撇号；1:1 字符替换，长度与位置不变（用于子串定位）。"""
    return (s or "").replace("’", "'").replace("‘", "'").replace("ʼ", "'")


def build_prompt(spec: dict, answer: str) -> str:
    """依据固化规范(spec)批改学生句。模型只判分，不重新发明标准答案。"""
    cand = "；".join(
        f"{c.get('zh','')}→{'/'.join(c.get('fr', []))}" for c in spec.get("candidates", [])
    ) or "（无）"
    conj = "；".join(
        f"{c.get('verb','')} {c.get('form','')}: {c.get('value','')}" for c in spec.get("conjugations", [])
    ) or "（无）"
    structs = "；".join(spec.get("structures", [])) or "（无）"
    refs = " | ".join(spec.get("references", [])) or "（无）"
    req = "；".join(spec.get("required", [])) or "（无）"
    ignore = spec.get("ignore") or "无"
    target = spec.get("target") or spec.get("cue", "")
    return f"""你是严谨的法语老师。依据这道题的「标准规范」批改学生句子，只输出一个 JSON 对象，不要 Markdown 代码块。

【本轮要表达】{target}
【可接受候选词·开放】{cand}
【本句相关变位】{conj}
【可接受句式】{structs}
【参考句·可有多种正确写法】{refs}
【必须表达的要点】{req}
【本轮忽略】{ignore}

学生写的句子（逐字）：{answer}

要求：
1. 把学生句子切成若干片段逐个判定、覆盖整句。每个 "片段" 字段必须是学生句子里**逐字出现的子串**，绝不要写你改正后的形式。
2. "状态" 只能取：正确 / 可接受变体 / 正确但不自然 / 错误 / 多余 / 拿不准。
   - 候选表没列出但确实正确的表达 → 可接受变体（**不要因为不在候选表里就判错**）。
   - 语法对但不地道或偏离本轮目标 → 正确但不自然。
   - 多写、应删除的 → 多余。
3. "最小修正"：在学生原句上**只改真正错误处**，保留学生写对的个人表达，不要整句重写成参考句。
4. "更自然版"：另给一个更地道的参考写法。
5. 不要评判【本轮忽略】里的内容。
6. 判定必须基于「学生写的句子」的实际字符，不要把你改正后的形式当成学生原答案。

JSON 格式：
{{"片段":[{{"片段":"学生原句子串","维度":"用词/语法/句式","状态":"...","依据":"简短","替换":"可选"}}],"最小修正":"...","更自然版":"...","总判定":"对/部分/错"}}"""


def _loads(raw: str):
    clean = (raw or "").strip()
    clean = clean.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(clean)
    except (json.JSONDecodeError, TypeError):
        return None


def normalize_result(raw: str) -> dict:
    """把模型返回归一成稳定结构；解析失败给 parse_error 让 UI 退回原文。"""
    data = _loads(raw)
    if not isinstance(data, dict):
        return {"parse_error": True, "raw": raw}
    spans = data.get("片段") or data.get("spans") or []
    if not isinstance(spans, list):
        spans = []
    clean_spans = []
    for sp in spans:
        if not isinstance(sp, dict):
            continue
        frag = str(sp.get("片段") or sp.get("text") or "")
        if not frag:
            continue
        status = str(sp.get("状态") or sp.get("status") or "拿不准")
        if status not in VALID_STATUS:
            status = "拿不准"
        clean_spans.append({
            "片段": frag,
            "维度": str(sp.get("维度") or sp.get("dim") or ""),
            "状态": status,
            "依据": str(sp.get("依据") or sp.get("reason") or ""),
            "替换": str(sp.get("替换") or sp.get("replace") or ""),
        })
    return {
        "parse_error": False,
        "spans": clean_spans,
        "最小修正": str(data.get("最小修正") or data.get("minimal_correction") or "").strip(),
        "更自然版": str(data.get("更自然版") or data.get("natural_version") or "").strip(),
        "总判定": str(data.get("总判定") or data.get("overall") or "").strip(),
    }


def anchor_and_segment(answer: str, spans: list[dict]) -> list[dict]:
    """把模型片段在学生原句里逐字定位（忽略模型给的偏移、丢弃定位不到的），
    返回覆盖整句的有序片段列表，每段带状态；未被任何片段覆盖的部分标「未标注」。"""
    na = _norm_apos(answer)
    used = [False] * len(answer)
    placed: list[tuple] = []
    for sp in spans:
        frag = sp.get("片段", "")
        if not frag:
            continue
        nf = _norm_apos(frag)
        idx = na.find(nf)
        while idx != -1:
            if not any(used[idx:idx + len(nf)]):
                break
            idx = na.find(nf, idx + 1)
        if idx == -1:                      # 幻觉片段或与已放置片段重叠 → 丢弃
            continue
        for k in range(idx, idx + len(nf)):
            used[k] = True
        placed.append((idx, idx + len(nf), sp))
    placed.sort(key=lambda t: t[0])
    segs: list[dict] = []
    pos = 0
    for start, end, sp in placed:
        if start > pos:
            segs.append({"text": answer[pos:start], "状态": "未标注"})
        segs.append({
            "text": answer[start:end], "状态": sp["状态"],
            "维度": sp.get("维度", ""), "依据": sp.get("依据", ""), "替换": sp.get("替换", ""),
        })
        pos = end
    if pos < len(answer):
        segs.append({"text": answer[pos:], "状态": "未标注"})
    return segs


def to_html(segments: list[dict]) -> str:
    """把染色片段渲染成转义后的 HTML（颜色=模型判断，调用方须标「需核验」）。"""
    out = []
    for seg in segments:
        style = STATUS_STYLE.get(seg.get("状态", "未标注"), "")
        text = html.escape(seg.get("text", "")).replace("\n", "<br>")
        out.append(f'<span style="{style}padding:1px 0;">{text}</span>' if style else text)
    return "".join(out)
