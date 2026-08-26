#!/usr/bin/env python3
"""词条前缀两层拆分的**迁移预演**。只读，不写任何 vocab.json。

现状：`zh` 的方括号前缀既要标技能、又要标具体题号（`[T11Q9]`、`[L38写作T3]`），
而它是单值的。课程从阅读转向口语写作之后，题号锚点没有了，
而且一个词经常同时属于写作和口语——单值前缀装不下。

方案：前缀降级为粗粒度技能标签（听写/阅读/写作/口语/课外），
细粒度来源全部挪进 `provenance[].source_ref`（本来就是数组、本来就在 App 里渲染）。

本脚本回答迁移前必须先知道的一件事：
**哪些行的题号信息只存在于前缀里，provenance 里没有对应锚点？**
这些行迁移会丢信息，必须先补 provenance 才能动。
"""
from __future__ import annotations

import argparse
import collections
import glob as globlib
import json
import pathlib
import re
import sys

DEFAULT_GLOB = "/Users/francis/Documents/法语/本地录屏课/L*/vocab.json"

_PREFIX = re.compile(r"^\[([^\]]+)\]")
_SUPP = re.compile(r"\s*补\s*$")

_SKILLS = ("听写", "阅读", "听力", "写作", "口语", "课外")

_RULES = [
    # 已经是新形状的：识别为「已迁移」，不算改动也不算无法映射。
    (re.compile(r"^L\d+(?:" + "|".join(_SKILLS) + r")$"), None),
    # (识别旧前缀, 新技能标签)
    (re.compile(r"^L\d+课前复习$"), "听写"),
    (re.compile(r"^L\d+写作T\d+\w*$"), "写作"),
    (re.compile(r"^L\d+口语T\d+\w*$"), "口语"),
    # 听力：预演跑出来才发现的第六个技能（[L36听力] 43 行、[L35听力T2] 33 行）。
    # 原设计只列了五个，是照 L38 一课想当然的。
    (re.compile(r"^L\d+听力(?:T\d+\w*)?$"), "听力"),
    (re.compile(r"^L\d+课外题$"), "课外"),
    # 2026-08-25 用户裁定：动词变位紧接开课听写做，同一个环节 → 听写；
    # 课后补注不属于任何技能环节 → 课外。
    (re.compile(r"^L\d+动词变位$"), "听写"),
    (re.compile(r"^L\d+课后补注$"), "课外"),
    (re.compile(r"^T\d+Q[\w/]+(?:\s*[;；]\s*T\d+Q[\w/]+)*$"), "阅读"),
]

_TQ = re.compile(r"T(\d+)Q([\w/]+)")


def classify(prefix_body: str) -> tuple[str | None, bool]:
    """返回 (新技能标签, 是否补充档)。认不出来返回 (None, ...)。"""
    is_supp = bool(_SUPP.search(prefix_body))
    core = _SUPP.sub("", prefix_body).strip()
    for pattern, skill in _RULES:
        if pattern.match(core):
            if skill is None:                      # 已经是新形状，原样保留
                return core[len(re.match(r"L\d+", core).group(0)):], is_supp
            return skill, is_supp
    return None, is_supp


def anchors_in_prefix(prefix_body: str) -> set[str]:
    """前缀里携带的题号锚点，例如 {'T11Q9'}。"""
    return {f"T{t}Q{q}" for t, q in _TQ.findall(prefix_body)}


def anchors_in_provenance(row: dict) -> str:
    """把该行所有 source_ref 拼起来，用于判断题号是否已被 provenance 保留。"""
    return " ".join(
        str(p.get("source_ref", "")) for p in (row.get("provenance") or [])
    )


def analyse(paths: list[pathlib.Path]) -> dict:
    per_lesson: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    unmapped: list[tuple[str, str, str]] = []      # (lesson, lemma, prefix)
    would_lose: list[tuple[str, str, str]] = []    # (lesson, lemma, 丢失的锚点)
    no_prefix: list[tuple[str, str]] = []
    total = changed = 0

    for path in paths:
        rows = json.loads(path.read_text(encoding="utf-8"))
        for row in rows:
            total += 1
            lesson = row.get("lesson") or path.parent.name
            zh = row.get("zh") or ""
            m = _PREFIX.match(zh)
            if not m:
                no_prefix.append((lesson, row.get("lemma", "")))
                continue
            body = m.group(1)
            skill, is_supp = classify(body)
            if skill is None:
                unmapped.append((lesson, row.get("lemma", ""), body))
                per_lesson[lesson]["无法映射"] += 1
                continue

            new_prefix = f"[{lesson}{skill}{' 补' if is_supp else ''}]"
            per_lesson[lesson][f"{skill}{' 补' if is_supp else ''}"] += 1
            if not zh.startswith(new_prefix):
                changed += 1

            lost = anchors_in_prefix(body)
            if lost:
                prov = anchors_in_provenance(row)
                missing = sorted(a for a in lost if a not in prov)
                if missing:
                    would_lose.append((lesson, row.get("lemma", ""), "/".join(missing)))

    return {
        "per_lesson": per_lesson,
        "unmapped": unmapped,
        "would_lose": would_lose,
        "no_prefix": no_prefix,
        "total": total,
        "changed": changed,
    }


def _lesson_key(name: str) -> tuple[int, str]:
    m = re.match(r"L(\d+)", name or "")
    return (int(m.group(1)) if m else 10**6, name or "")


def render(res: dict, paths: list[pathlib.Path]) -> str:
    out = ["# 词条前缀迁移预演", ""]
    out.append(f"扫描 {len(paths)} 个 vocab.json，共 **{res['total']}** 行，"
               f"其中 **{res['changed']}** 行的 `zh` 会变。")
    out.append("")
    out.append("> 本脚本**只读**，没有修改任何文件。")
    out.append("")

    out.append("## 按课分布（迁移后的新前缀）")
    out.append("")
    skills = ["听写", "阅读", "听力", "写作", "口语", "课外"]
    cols = skills + [f"{s} 补" for s in skills] + ["无法映射"]
    used = [c for c in cols if any(res["per_lesson"][l][c] for l in res["per_lesson"])]
    out.append("| 课 | " + " | ".join(used) + " | 合计 |")
    out.append("|---" * (len(used) + 2) + "|")
    for lesson in sorted(res["per_lesson"], key=_lesson_key):
        counts = res["per_lesson"][lesson]
        cells = [str(counts[c] or "") for c in used]
        out.append(f"| {lesson} | " + " | ".join(cells) + f" | {sum(counts.values())} |")
    out.append("")

    out.append("## ⚠️ 迁移会丢信息的行（必须先补 provenance）")
    out.append("")
    if res["would_lose"]:
        out.append(f"共 **{len(res['would_lose'])}** 行：前缀里带题号，"
                   f"但该行的 `provenance.source_ref` 里找不到这个锚点。"
                   f"**这些行在迁移前必须先把题号补进 provenance，否则信息只在前缀里、一改就没了。**")
        out.append("")
        out.append("| 课 | lemma | 会丢的锚点 |")
        out.append("|---|---|---|")
        for lesson, lemma, lost in sorted(res["would_lose"], key=lambda r: (_lesson_key(r[0]), r[1])):
            out.append(f"| {lesson} | `{lemma}` | {lost} |")
    else:
        out.append("无 ✅ —— 所有带题号的前缀，题号都已经在 provenance 里有对应锚点，迁移不丢信息。")
    out.append("")

    out.append("## 无法映射的前缀")
    out.append("")
    if res["unmapped"]:
        out.append(f"共 **{len(res['unmapped'])}** 行。**没有猜**，原样列出等人决定：")
        out.append("")
        out.append("| 课 | lemma | 现有前缀 |")
        out.append("|---|---|---|")
        for lesson, lemma, body in sorted(res["unmapped"], key=lambda r: (_lesson_key(r[0]), r[1])):
            out.append(f"| {lesson} | `{lemma}` | `[{body}]` |")
    else:
        out.append("无 ✅")
    out.append("")

    if res["no_prefix"]:
        out.append(f"## 没有前缀的行（{len(res['no_prefix'])} 行）")
        out.append("")
        out.append("这些行的 `zh` 不带方括号前缀，迁移不涉及它们。")
        out.append("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vocab-glob", default=DEFAULT_GLOB)
    ap.add_argument("--out", default=None, type=pathlib.Path)
    args = ap.parse_args(argv)

    paths = [pathlib.Path(p) for p in sorted(globlib.glob(args.vocab_glob))]
    if not paths:
        # 硬保护：worktree 里用相对路径会一个文件都匹配不到，
        # 空报告看起来像跑成功了。宁可报错。
        print(
            f"错误：--vocab-glob {args.vocab_glob!r} 一个文件都没匹配到。\n"
            f"（在 worktree 里跑时，'../L*/vocab.json' 会解析到 .claude/worktrees/，"
            f"请用绝对路径。）",
            file=sys.stderr,
        )
        return 2

    res = analyse(paths)
    text = render(res, paths)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
