#!/usr/bin/env python3
"""把跨课重复的知识点压成「知识点簇」，并按复现次数排序。

`species_overlap_report.py` 报告的是**两两重复**；这个脚本对同一张图做
连通分量，得到「同一个点在全课程一共出现过几次、分别在哪几课」。

只读。不合并、不删除、不修改任何文件。
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from species_overlap_report import load_species, normalize_item, _lesson_key  # noqa: E402

# 只有含拉丁字母的项才算「法语项」——否则中文的 learner_task 片段
# （例如「自己造句」）会把不相干的点连起来。
_LATIN = re.compile(r"[a-zà-ÿœæ]", re.IGNORECASE)


def french_items(row: dict) -> set[str]:
    return {i for i in row["items"] if _LATIN.search(i)}


# 一个法语项在全库出现多少次以内才算「有辨识度」。
# `de` / `en` / `qui` 这种到处都是，共享它们说明不了两个知识点讲的是同一件事。
RARE_MAX = 4


def build_clusters(rows: list[dict], rare_max: int = RARE_MAX) -> list[dict]:
    by_item: dict[str, list[int]] = collections.defaultdict(list)
    for idx, r in enumerate(rows):
        for it in french_items(r):
            by_item[it].append(idx)

    parent = list(range(len(rows)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    # 先数每一对跨课知识点共享了几项、其中有没有罕见项。
    # 只共享一个高频词（de/en/qui…）不足以连边——否则传递闭包会把
    # 十节课并成一个巨簇。
    shared_pairs: dict[tuple[int, int], list[str]] = collections.defaultdict(list)
    for item, idxs in by_item.items():
        if len({rows[i]["lesson"] for i in idxs}) < 2:
            continue
        for a_pos in range(len(idxs)):
            for b_pos in range(a_pos + 1, len(idxs)):
                a, b = idxs[a_pos], idxs[b_pos]
                if rows[a]["lesson"] == rows[b]["lesson"]:
                    continue
                shared_pairs[(min(a, b), max(a, b))].append(item)

    for (a, b), items in shared_pairs.items():
        rare = [it for it in items if len(by_item[it]) <= rare_max]
        if len(items) >= 2 or rare:
            union(a, b)

    groups: dict[int, list[int]] = collections.defaultdict(list)
    for i in range(len(rows)):
        groups[find(i)].append(i)

    out = []
    for members in groups.values():
        lessons = sorted({rows[i]["lesson"] for i in members}, key=_lesson_key)
        if len(lessons) < 2:
            continue
        shared = collections.Counter()
        for i in members:
            for it in french_items(rows[i]):
                shared[it] += 1
        out.append({
            "lessons": lessons,
            "n_lessons": len(lessons),
            "members": [(rows[i]["lesson"], rows[i]["species_label"],
                         rows[i]["primary_class"], rows[i].get("tags", []))
                        for i in sorted(members, key=lambda k: _lesson_key(rows[k]["lesson"]))],
            "shared": [it for it, c in shared.most_common() if c > 1][:6],
            "corrected": any("teacher_corrected_error" in rows[i].get("tags", []) for i in members),
        })
    out.sort(key=lambda c: (-c["n_lessons"], -len(c["members"])))
    return out


def render(rows: list[dict], clusters: list[dict]) -> str:
    total_members = sum(len(c["members"]) for c in clusters)
    corrected = [c for c in clusters if c["corrected"]]
    o = ["# 知识点簇（跨课复现）", ""]
    o.append(f"全库 **{len(rows)}** 个 reviewed 知识点，压成 **{len(clusters)}** 个跨课簇，"
             f"覆盖 **{total_members}** 个知识点。其中 **{len(corrected)}** 个簇含老师当堂纠错。")
    o.append("")
    o.append("> 只统计**跨课**复现；同一课内部共享法语项不算。"
             "只有含拉丁字母的项才算法语项（否则中文任务描述会误连）。")
    o.append("")

    o.append("## 复现次数排行")
    o.append("")
    o.append("| 课数 | 出现在 | 共同法语项 | 纠错 |")
    o.append("|---:|---|---|:-:|")
    for c in clusters[:30]:
        items = " / ".join(f"`{s}`" for s in c["shared"][:3]) or "—"
        o.append(f'| **{c["n_lessons"]}** | {" · ".join(c["lessons"])} | {items} '
                 f'| {"✱" if c["corrected"] else ""} |')
    if len(clusters) > 30:
        o.append(f'| | …另有 {len(clusters)-30} 个簇 | | |')
    o.append("")

    o.append("## 逐簇明细")
    o.append("")
    for n, c in enumerate(clusters, 1):
        head = " · ".join(c["lessons"])
        o.append(f'### {n}. {head}　（{len(c["members"])} 个点）'
                 + ("　✱含纠错" if c["corrected"] else ""))
        if c["shared"]:
            o.append("共同项：" + " / ".join(f"`{s}`" for s in c["shared"]))
        o.append("")
        for les, label, klass, tags in c["members"]:
            mark = " ✱" if "teacher_corrected_error" in tags else ""
            o.append(f"- **{les}** · `{klass}` — {label}{mark}")
        o.append("")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--species-dir", required=True, type=pathlib.Path)
    ap.add_argument("--out", default=None, type=pathlib.Path)
    a = ap.parse_args(argv)
    rows = load_species(a.species_dir)
    for r, raw in zip(rows, rows):
        raw.setdefault("tags", [])
    # load_species 不带 tags，补读一次
    tagmap = {}
    for p in sorted(a.species_dir.glob("L*.species.json")):
        for e in json.loads(p.read_text(encoding="utf-8")):
            if isinstance(e, dict):
                tagmap[(e.get("lesson"), e.get("species_label"))] = e.get("tags") or []
    for r in rows:
        r["tags"] = tagmap.get((r["lesson"], r["species_label"]), [])
    clusters = build_clusters(rows)
    text = render(rows, clusters)
    if a.out:
        a.out.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {a.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
