#!/usr/bin/env python3
"""Build a lesson manifest checkpoint deck from reviewed species JSON.

This is the bridge from the VibeVoice ecological census to the local 8501
dictation app. It turns each reviewed within-region species into one SRS
checkpoint card, preserving the species label as the coverage key.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import manifest  # noqa: E402


def slugify(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-") or "species"


def _read_vocab_items(path: Path) -> list[dict]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    return [
        {
            "type": "vocab",
            "fr": row.get("lemma"),
            "pos": row.get("pos") or "expr",
            "zh": row.get("zh") or "",
        }
        for row in rows
        if row.get("lemma")
    ]


def _occurrence_summary(row: dict, limit: int = 4) -> str:
    parts: list[str] = []
    for occ in row.get("occurrences", [])[:limit]:
        time = occ.get("time_start") or "?"
        end = occ.get("time_end")
        if end and end != time:
            time = f"{time}-{end}"
        ref = occ.get("ref") or occ.get("raw_file") or ""
        parts.append(f"{time} · {ref}".strip(" ·"))
    more = len(row.get("occurrences", [])) - limit
    if more > 0:
        parts.append(f"+{more} more")
    return "；".join(parts)


def _front(row: dict) -> str:
    items = " / ".join(row.get("french_items") or []) or row.get("species_label", "")
    task = row.get("learner_task") or "回忆这个课堂知识点的规则和用法"
    return (
        f"【{items}】\n"
        f"先不看答案：这个点要解决什么学习任务？请说出规则/用法，并给一个例子。\n\n"
        f"提示：{task}"
    )


def _back(row: dict) -> str:
    items = " / ".join(row.get("french_items") or [])
    evidence = _occurrence_summary(row)
    tags = ", ".join(row.get("tags") or [])
    lines = [
        f"知识点：{row.get('species_label')}",
        f"类别：{row.get('primary_class') or 'unknown'}",
    ]
    if items:
        lines.append(f"法语项目：{items}")
    if row.get("learner_task"):
        lines.append(f"学习任务：{row['learner_task']}")
    if row.get("rule_or_usage"):
        lines.append(f"规则/用法：{row['rule_or_usage']}")
    if evidence:
        lines.append(f"课堂证据：{evidence}")
    if tags:
        lines.append(f"标签：{tags}")
    return "\n\n".join(lines)


def _checkpoint(row: dict, lesson: str, seen: set[str], overrides: dict) -> dict:
    label = row.get("species_label") or row.get("learner_task") or "species"
    base = f"{lesson}:species:{slugify(label)}"
    cid = base
    i = 2
    while cid in seen:
        cid = f"{base}-{i}"
        i += 1
    seen.add(cid)
    card = {
        "type": "checkpoint",
        "id": cid,
        "front": _front(row),
        "back": _back(row),
        "answer": None,
        "source_species": label,
        "primary_class": row.get("primary_class"),
        "tags": row.get("tags") or [],
        "french_items": row.get("french_items") or [],
        "evidence_refs": [occ.get("ref") for occ in row.get("occurrences", []) if occ.get("ref")],
    }
    ov = overrides.get(label)          # 人工精修卡：按 species_label 覆盖 front/back/answer
    if ov:
        if ov.get("front"):
            card["front"] = ov["front"]
        if ov.get("back"):
            card["back"] = ov["back"]
        if "answer" in ov:
            card["answer"] = ov["answer"]
        card["curated"] = True
    return card


def _apply_checkpoint_groups(
    cards: list[dict], lesson: str, groups_path: Path, seen_ids: set[str]
) -> list[dict]:
    config = json.loads(groups_path.read_text(encoding="utf-8"))
    groups = config.get("groups") or []
    by_species = {card["source_species"]: card for card in cards}
    original_order = {card["id"]: i for i, card in enumerate(cards)}
    assigned_species: set[str] = set()
    group_ids: set[str] = set()
    practice_ids: set[str] = set()

    for group in groups:
        group_id = str(group.get("id") or "").strip()
        label = str(group.get("label") or "").strip()
        if not group_id or not label:
            raise SystemExit("Checkpoint groups invalid: every group needs id and label")
        if group_id in group_ids:
            raise SystemExit(f"Checkpoint groups invalid: duplicate group id '{group_id}'")
        group_ids.add(group_id)
        group_order = int(group.get("order", 0))

        for member in group.get("species") or []:
            species_label = str(member.get("source_species") or "").strip()
            if species_label not in by_species:
                raise SystemExit(
                    f"Checkpoint groups invalid: unknown species '{species_label}'"
                )
            if species_label in assigned_species:
                raise SystemExit(
                    f"Checkpoint groups invalid: duplicate species member '{species_label}'"
                )
            assigned_species.add(species_label)
            by_species[species_label].update(
                {
                    "study_group": group_id,
                    "study_group_label": label,
                    "study_group_order": group_order,
                    "study_order": int(member.get("order", 0)),
                }
            )

        for practice in group.get("practice_cards") or []:
            short_id = str(practice.get("id") or "").strip()
            if short_id in practice_ids:
                raise SystemExit(
                    f"Checkpoint groups invalid: duplicate practice card id '{short_id}'"
                )
            practice_ids.add(short_id)
            if not short_id or not practice.get("front") or not practice.get("back"):
                raise SystemExit(
                    f"Checkpoint groups invalid: practice card '{short_id}' needs id/front/back"
                )
            answer = practice.get("answer")
            if "answer" not in practice or (
                answer is not None
                and (not isinstance(answer, str) or not answer.strip())
            ):
                raise SystemExit(
                    f"Checkpoint groups invalid: practice card '{short_id}' needs "
                    "answer=null for self-review or one non-empty machine answer"
                )
            card_id = f"{lesson}:practice:{slugify(short_id)}"
            if card_id in seen_ids:
                raise SystemExit(f"Checkpoint groups invalid: duplicate checkpoint id '{card_id}'")
            seen_ids.add(card_id)
            cards.append(
                {
                    "type": "checkpoint",
                    "id": card_id,
                    "front": practice["front"],
                    "back": practice["back"],
                    "answer": answer,
                    "primary_class": practice.get("primary_class") or "grammar_rule",
                    "tags": practice.get("tags") or ["conjugation", "teacher_corrected_error"],
                    "french_items": practice.get("french_items") or [],
                    "evidence_refs": practice.get("evidence_refs") or [],
                    "parent_group": group_id,
                    "study_group": group_id,
                    "study_group_label": label,
                    "study_group_order": group_order,
                    "study_order": int(practice.get("order", 0)),
                    "curated": True,
                }
            )

    return sorted(
        cards,
        key=lambda card: (
            card.get("study_group_order", 1_000_000),
            card.get("study_order", original_order.get(card["id"], 0)),
            original_order.get(card["id"], len(original_order)),
        ),
    )


def build_manifest(lesson: str, source: str, species_path: Path, vocab_path: Path,
                   overrides_path: Path | None = None,
                   checkpoint_groups_path: Path | None = None) -> dict:
    species = json.loads(species_path.read_text(encoding="utf-8"))
    reviewed = [row for row in species if row.get("adjudication_status") == "reviewed"]
    overrides: dict = {}
    if overrides_path and overrides_path.exists():
        overrides = json.loads(overrides_path.read_text(encoding="utf-8"))
    seen_ids: set[str] = set()
    cards = [_checkpoint(row, lesson, seen_ids, overrides) for row in reviewed]
    if checkpoint_groups_path:
        cards = _apply_checkpoint_groups(cards, lesson, checkpoint_groups_path, seen_ids)
    data = {
        "lesson": lesson,
        "source": source,
        "coverage": {
            "source_type": "within_region_species",
            "source_path": str(species_path),
            "expected_species_count": len(reviewed),
        },
        "chunks": [
            {
                "id": "vocab",
                "title": f"{lesson} 词汇",
                "bucket": "vocab",
                "items": _read_vocab_items(vocab_path),
            },
            {
                "id": "species-checkpoints",
                "title": f"{lesson} reviewed species checkpoints",
                "bucket": "checkpoint",
                "items": cards,
            },
        ],
    }
    problems = manifest.validate(data)
    if problems:
        raise SystemExit("Manifest validation failed:\n" + "\n".join(f"- {p}" for p in problems))
    return data


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lesson", required=True)
    ap.add_argument("--source", default=None)
    ap.add_argument("--species-json", required=True)
    ap.add_argument("--vocab-json", required=True)
    ap.add_argument("--overrides", default=None, help="人工精修卡 JSON（按 species_label 覆盖 front/back/answer）")
    ap.add_argument("--checkpoint-groups", default=None, help="可选学习组与补充机判/自评卡 JSON")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    source = args.source or f"{args.lesson}_final_working.md"
    data = build_manifest(
        args.lesson,
        source,
        Path(args.species_json).expanduser().resolve(),
        Path(args.vocab_json).expanduser().resolve(),
        Path(args.overrides).expanduser().resolve() if args.overrides else None,
        Path(args.checkpoint_groups).expanduser().resolve() if args.checkpoint_groups else None,
    )
    out = Path(args.out).expanduser()
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    print(f"vocab={len(data['chunks'][0]['items'])} checkpoints={len(data['chunks'][1]['items'])}")


if __name__ == "__main__":
    main()
