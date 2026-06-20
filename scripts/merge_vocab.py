#!/usr/bin/env python3
"""Append missing entries to one lesson vocab.json without overwriting existing rows.

Input is a JSON array whose entries contain at least ``lemma``, ``pos``, and
``zh``. Re-running the same merge is idempotent.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import vocab  # noqa: E402


_CATEGORY_BY_POS = {
    "noun": "NOMS",
    "verb": "VERBES",
    "adj": "ADJECTIFS",
}


@dataclass(frozen=True)
class MergeResult:
    added: int
    skipped_existing: int
    skipped_duplicate: int


def _normalize_lemma(value: str) -> str:
    return " ".join(vocab.clean_lemma(value).replace("’", "'").split())


def _lemma_key(value: str) -> str:
    return _normalize_lemma(value).casefold()


def _require_text(row: dict, field: str, index: int) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"input row {index} requires non-empty {field}")
    return value.strip()


def _new_entry(row: dict, *, lesson: str, index: int) -> dict:
    lemma = _normalize_lemma(_require_text(row, "lemma", index))
    pos = _require_text(row, "pos", index)
    zh = _require_text(row, "zh", index)
    raw = row.get("raw") or lemma
    if not isinstance(raw, str):
        raise ValueError(f"input row {index} raw must be a string")
    raw = raw.strip().replace("’", "'")
    masc, marker = vocab.split_gender(raw)
    fem_raw = row.get("fem_raw", marker)
    fem = row.get("fem")
    if fem is None:
        fem = vocab.feminine_form(masc, fem_raw)
    category = row.get("category") or _CATEGORY_BY_POS.get(pos, "AUTRES")
    return {
        "lemma": lemma,
        "pos": pos,
        "zh": zh,
        "lesson": lesson,
        "source_lesson": row.get("source_lesson") or lesson,
        "category": str(category).upper(),
        "example": row.get("example"),
        "raw": raw,
        "fem": fem,
        "fem_raw": fem_raw,
    }


def merge_vocab(vocab_path: str | Path, incoming: Iterable[dict]) -> MergeResult:
    """Merge missing lemmas into ``vocab_path`` while preserving existing rows."""
    path = Path(vocab_path)
    rows = json.loads(path.read_text("utf-8"))
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("target vocab must be a JSON array of objects")

    existing_keys = {
        _lemma_key(row.get("lemma", ""))
        for row in rows
        if isinstance(row.get("lemma"), str) and row["lemma"].strip()
    }
    lesson = path.parent.name
    seen_batch: dict[str, tuple[str, str]] = {}
    additions: list[dict] = []
    skipped_existing = 0
    skipped_duplicate = 0

    for index, source in enumerate(incoming, 1):
        if not isinstance(source, dict):
            raise ValueError(f"input row {index} must be an object")
        entry = _new_entry(source, lesson=lesson, index=index)
        key = _lemma_key(entry["lemma"])
        signature = (entry["pos"], entry["zh"])
        previous = seen_batch.get(key)
        if previous is not None:
            if previous != signature:
                raise ValueError(f"conflicting duplicate lemma in input: {entry['lemma']}")
            skipped_duplicate += 1
            continue
        seen_batch[key] = signature
        if key in existing_keys:
            skipped_existing += 1
            continue
        existing_keys.add(key)
        additions.append(entry)

    if additions:
        path.write_text(
            json.dumps(rows + additions, ensure_ascii=False, indent=2) + "\n",
            "utf-8",
        )
    return MergeResult(
        added=len(additions),
        skipped_existing=skipped_existing,
        skipped_duplicate=skipped_duplicate,
    )


def _load_input(path: str) -> list[dict]:
    text = sys.stdin.read() if path == "-" else Path(path).read_text("utf-8")
    rows = json.loads(text)
    if not isinstance(rows, list):
        raise ValueError("input must be a JSON array")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vocab", required=True, help="target lesson vocab.json")
    parser.add_argument("--input", required=True, help="JSON array path, or - for stdin")
    args = parser.parse_args()

    incoming = _load_input(args.input)
    result = merge_vocab(args.vocab, incoming)
    print(
        f"input={len(incoming)} added={result.added} "
        f"skipped_existing={result.skipped_existing} "
        f"skipped_duplicate={result.skipped_duplicate}"
    )


if __name__ == "__main__":
    main()
