#!/usr/bin/env python3
"""coverage_report.py <manifest.json>：打印 每chunk→桶 表 + 各桶合计 + 缺口清单。
证明 doc 里每个 chunk 都归了桶（覆盖率可清点）。"""
import collections
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import manifest  # noqa: E402


def main(p: str) -> None:
    d = manifest.load(p)
    print(f"# 覆盖报告 {d.get('lesson')}  source={d.get('source')}")
    cnt: collections.Counter = collections.Counter()
    print("\n| chunk | bucket | 条目 | 标题 |")
    print("|---|---|---|---|")
    for ch in d.get("chunks", []):
        b = ch.get("bucket")
        n = len(ch.get("items") or [])
        cnt[b] += 1
        print(f"| {ch.get('id')} | {b} | {n} | {(ch.get('title') or '')[:40]} |")
    print("\n桶合计:", dict(cnt))
    probs = manifest.validate(d)
    cov = d.get("coverage") or {}
    if cov.get("source_type") == "within_region_species":
        cards = manifest.checkpoints(d)
        covered = {c.get("source_species") for c in cards if c.get("source_species")}
        expected = cov.get("expected_species_count")
        print(f"species 覆盖: {len(covered)}/{expected} ({cov.get('source_path', 'unknown source')})")
    print("缺口/问题:", "无 ✅" if not probs else f"{len(probs)} 条")
    for x in probs:
        print(" -", x)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 scripts/coverage_report.py <manifest.json>")
        sys.exit(1)
    main(sys.argv[1])
