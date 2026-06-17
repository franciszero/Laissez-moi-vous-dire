"""每课的机器合同 manifest（JSON）：把 doc 每个 chunk 强制归桶，覆盖率可清点。
内容是 LLM 产、机器吃；Word 文档只是它的渲染产物。"""
from __future__ import annotations

import json

BUCKETS = {"vocab", "drill", "checkpoint", "skip"}


def validate(data: dict) -> list[str]:
    """返回问题清单（空=通过）。校验：归桶强制、字段完整、checkpoint id 唯一。"""
    probs: list[str] = []
    for k in ("lesson", "source", "chunks"):
        if k not in data:
            probs.append(f"顶层缺字段 {k}")
    seen_ids: set = set()
    species_refs: list[str] = []
    for i, ch in enumerate(data.get("chunks", [])):
        tag = ch.get("id", f"#{i}")
        if "id" not in ch:
            probs.append(f"chunk {tag} 缺 id")
        b = ch.get("bucket")
        if b not in BUCKETS:
            probs.append(f"chunk {tag} bucket 非法/缺失: {b!r}")
        items = ch.get("items") or []
        if b != "skip" and not items:
            probs.append(f"chunk {tag} 非 skip 但 items 为空")
        for it in items:
            t = it.get("type")
            if t == "checkpoint":
                for f in ("id", "front", "back"):
                    if not it.get(f):
                        probs.append(f"chunk {tag} checkpoint 缺 {f}")
                cid = it.get("id")
                if cid in seen_ids:
                    probs.append(f"checkpoint id 重复: {cid}")
                seen_ids.add(cid)
                if it.get("source_species"):
                    species_refs.append(it["source_species"])
            elif t == "vocab":
                for f in ("fr", "pos", "zh"):
                    if not it.get(f):
                        probs.append(f"chunk {tag} vocab 缺 {f}")
            elif t == "drill":
                if not it.get("pattern"):
                    probs.append(f"chunk {tag} drill 缺 pattern")
            else:
                probs.append(f"chunk {tag} item type 非法: {t!r}")
    cov = data.get("coverage") or {}
    if cov.get("source_type") == "within_region_species":
        expected = cov.get("expected_species_count")
        if not isinstance(expected, int) or expected <= 0:
            probs.append("coverage.expected_species_count 缺失/非法")
        else:
            unique_species = set(species_refs)
            if len(unique_species) != expected:
                probs.append(f"species 覆盖数 {len(unique_species)} != expected {expected}")
        dupes = sorted({x for x in species_refs if species_refs.count(x) > 1})
        for sp in dupes:
            probs.append(f"source_species 重复: {sp}")
    return probs


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def checkpoints(data: dict) -> list[dict]:
    out: list[dict] = []
    for ch in data.get("chunks", []):
        if ch.get("bucket") == "checkpoint":
            out += [it for it in ch.get("items", []) if it.get("type") == "checkpoint"]
    return out


def vocab_items(data: dict) -> list[dict]:
    out: list[dict] = []
    for ch in data.get("chunks", []):
        if ch.get("bucket") == "vocab":
            out += [it for it in ch.get("items", []) if it.get("type") == "vocab"]
    return out
