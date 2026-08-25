#!/usr/bin/env python3
"""跨课知识点重复检测。

每一课的知识点以 species 形式存在 VibeVoice 的
`docs/french-wiki/census/recapture/reconciled/L*.species.json`，
`build_checkpoints_from_species.py` 把每个 species 变成一张 SRS 卡。

问题：同一个知识点在两课各出一张卡，两张卡会各自积累 SRS 进度，
事后合并必然丢一份。L38 的开课听写就是 L37 阅读卷词表的重报，
当时靠人工比对才发现 L37 已经出过 entretien / épreuve / consister en 等卡。

本脚本只出报告，**不合并、不删除、不修改任何文件**。
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sys

# 只去掉开头一个冠词；casefold 之后比较
# 顺序要害：正则交替取第一个匹配，une 必须排在 un 前面，
# 否则 "une boutique" 会被切成 "e boutique"。长的在前。
_LEADING_ARTICLE = re.compile(
    r"^(?:de\s+la|les|une|le|la|l'|un|des|du)\s*", re.IGNORECASE
)


def normalize_item(value: str) -> str:
    """归一化一个 french_item：去空白 → casefold → 去首尾标点 → 去开头冠词。"""
    if not isinstance(value, str):
        return ""
    text = value.strip().replace("’", "'")
    text = text.casefold()
    text = text.strip(" \t\r\n.,;:!?…«»\"'()[]")
    text = _LEADING_ARTICLE.sub("", text, count=1)
    return text.strip()


def load_species(species_dir: pathlib.Path) -> list[dict]:
    """读取目录下所有 L*.species.json 里 adjudication_status == reviewed 的条目。"""
    rows: list[dict] = []
    for path in sorted(species_dir.glob("L*.species.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"跳过 {path.name}：{exc}", file=sys.stderr)
            continue
        if not isinstance(data, list):
            continue
        for entry in data:
            if not isinstance(entry, dict):
                continue
            if entry.get("adjudication_status") != "reviewed":
                continue
            lesson = entry.get("lesson")
            label = entry.get("species_label")
            if not lesson or not label:
                continue
            items = {
                norm
                for raw in (entry.get("french_items") or [])
                if (norm := normalize_item(raw))
            }
            if not items:
                continue
            rows.append(
                {
                    "lesson": lesson,
                    "species_label": label,
                    "primary_class": entry.get("primary_class") or "unknown",
                    "items": items,
                }
            )
    return rows


def find_overlaps(rows: list[dict], lesson: str | None = None) -> list[dict]:
    """两两比对，返回跨课且 french_items 有交集的候选。同课内部不报告。"""
    hits: list[dict] = []
    for i, left in enumerate(rows):
        for right in rows[i + 1 :]:
            if left["lesson"] == right["lesson"]:
                continue
            if lesson and lesson not in (left["lesson"], right["lesson"]):
                continue
            shared = left["items"] & right["items"]
            if not shared:
                continue
            a, b = sorted((left, right), key=lambda r: _lesson_key(r["lesson"]))
            hits.append({"a": a, "b": b, "shared": sorted(shared)})
    return hits


def _lesson_key(name: str) -> tuple[int, str]:
    m = re.match(r"L(\d+)", name or "")
    return (int(m.group(1)) if m else 10**6, name or "")


def render(rows: list[dict], hits: list[dict], lesson: str | None) -> str:
    lessons = sorted({r["lesson"] for r in rows}, key=_lesson_key)
    out = ["# 跨课知识点重复报告", ""]
    scope = f"（只看 {lesson} 与其它课）" if lesson else "（全部两两组合）"
    out.append(
        f"扫描 {len(lessons)} 课、{len(rows)} 个 reviewed species{scope}，"
        f"发现 **{len(hits)}** 组跨课重复。"
    )
    out.append("")
    if not hits:
        out.append("未发现跨课重复 ✅")
        out.append("")
        return "\n".join(out)

    by_pair: dict[tuple[str, str], list[dict]] = collections.defaultdict(list)
    for hit in hits:
        by_pair[(hit["a"]["lesson"], hit["b"]["lesson"])].append(hit)

    for pair in sorted(by_pair, key=lambda p: (_lesson_key(p[0]), _lesson_key(p[1]))):
        group = sorted(by_pair[pair], key=lambda h: (-len(h["shared"]), h["a"]["species_label"]))
        left_lesson, right_lesson = pair
        out.append(f"## {left_lesson} ↔ {right_lesson}（{len(group)} 组）")
        out.append("")
        out.append(f"| 共同法语项 | {left_lesson} species | {right_lesson} species | primary_class |")
        out.append("|---|---|---|---|")
        for hit in group:
            shared = " / ".join(f"`{s}`" for s in hit["shared"])
            klass = hit["a"]["primary_class"]
            if hit["b"]["primary_class"] != klass:
                klass = f'{klass} / {hit["b"]["primary_class"]}'
            out.append(
                f'| {shared} | {hit["a"]["species_label"]} '
                f'| {hit["b"]["species_label"]} | {klass} |'
            )
        out.append("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--species-dir", required=True, type=pathlib.Path)
    ap.add_argument("--lesson", default=None, help="只报告这一课与其它课的重复，如 L38")
    ap.add_argument("--out", default=None, type=pathlib.Path)
    args = ap.parse_args(argv)

    rows = load_species(args.species_dir)
    hits = find_overlaps(rows, args.lesson)
    text = render(rows, hits, args.lesson)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0  # 报告工具，不是门禁：永远 0


if __name__ == "__main__":
    raise SystemExit(main())
