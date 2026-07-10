#!/usr/bin/env python3
"""Project an anki-wordsmith French batch into merge_vocab-ready source rows.

The projection deliberately takes ``zh`` only from the card's Core Meaning
field. Examples, collocations, comparisons, and dialogues remain context and
must never become meanings of the bare lemma.
"""
from __future__ import annotations

import argparse
import csv
from html.parser import HTMLParser
from io import BytesIO, StringIO
import json
from pathlib import Path
import sys
from urllib.request import urlopen
from zipfile import ZipFile


ANKI_FIELD_ORDER = (
    "Lemma",
    "QA Summary",
    "POS + Core Grammar Tag",
    "Article / Number / Basic Form",
    "IPA + Pronunciation Notes",
    "Core Meaning",
    "Définition FR",
    "Grammar Frame",
    "Register / Politeness",
    "Usage Comparison",
    "Collocations",
    "Example Sentences",
    "Faux Amis / Pitfalls",
    "Mini Dialogues",
    "My Output",
)
CORE_MEANING_INDEX = ANKI_FIELD_ORDER.index("Core Meaning")

_POS_BY_WORD_CLASS = {
    "noun": "noun",
    "verb": "verb",
    "adjective": "adj",
    "adverb": "adverb",
    "preposition": "prep",
    "conjunction": "conj",
    "expression": "expr",
    "interjection": "expr",
    "determiner": "expr",
    "pronoun": "expr",
}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "br":
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "div", "li", "span"}:
            self.parts.append(" ")


def _plain_text(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(value or "")
    parser.close()
    return " ".join("".join(parser.parts).split())


def _api_items_by_lemma(payload: dict) -> dict[str, dict]:
    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("french_results response requires an items array")
    out: dict[str, dict] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        audit = item.get("accepted_unit_audit") or {}
        meta = item.get("meta") or {}
        lemma = str(
            audit.get("accepted_target_text")
            or audit.get("parsed_word")
            or meta.get("word")
            or ""
        ).strip()
        if lemma:
            out[lemma] = item
    return out


def project_rows(lines: list[str], api_payload: dict) -> list[dict]:
    """Return merge-ready rows while preserving Core Meaning provenance."""
    batch_id = str(api_payload.get("batch_id") or "").strip()
    if not batch_id:
        raise ValueError("french_results response requires batch_id")
    api_items = _api_items_by_lemma(api_payload)
    projected: list[dict] = []
    seen: set[str] = set()

    for index, fields in enumerate(csv.reader(lines, delimiter="|"), start=1):
        if len(fields) != len(ANKI_FIELD_ORDER):
            raise ValueError(
                f"row {index}: expected {len(ANKI_FIELD_ORDER)} Anki fields, got {len(fields)}"
            )
        lemma = _plain_text(fields[0])
        core_meaning = _plain_text(fields[CORE_MEANING_INDEX])
        if not lemma or lemma == "N/A":
            raise ValueError(f"row {index}: missing lemma")
        if not core_meaning or core_meaning == "N/A":
            raise ValueError(f"row {index} ({lemma}): missing Core Meaning")
        if lemma in seen:
            raise ValueError(f"duplicate lemma in Anki export: {lemma}")
        seen.add(lemma)

        item = api_items.get(lemma, {})
        audit = item.get("accepted_unit_audit") or {}
        meta = item.get("meta") or {}
        word_class = str(meta.get("word_class") or "").strip().lower()
        pos = _POS_BY_WORD_CLASS.get(word_class, "expr")
        example = str(audit.get("source_sentence_or_context") or "").strip() or None
        projected.append(
            {
                "lemma": lemma,
                "pos": pos,
                "zh": core_meaning,
                "example": example,
                "raw": lemma,
                "source_batch": batch_id,
                "source_decision": str(item.get("decision") or "").strip(),
                "zh_source": "anki_core_meaning",
            }
        )
    return projected


def _fetch_json(url: str) -> dict:
    with urlopen(url, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object from {url}")
    return payload


def _fetch_export_lines(base_url: str, batch_id: str) -> list[str]:
    url = f"{base_url.rstrip('/')}/download/{batch_id}"
    with urlopen(url, timeout=30) as response:
        archive = response.read()
    expected_name = f"{batch_id}.csv"
    with ZipFile(BytesIO(archive)) as zf:
        if expected_name not in zf.namelist():
            raise ValueError(f"batch download is missing {expected_name}")
        text = zf.read(expected_name).decode("utf-8-sig")
    return list(StringIO(text))


def fetch_projection(base_url: str, batch_id: str) -> list[dict]:
    api_url = f"{base_url.rstrip('/')}/api/batches/{batch_id}/french_results"
    payload = _fetch_json(api_url)
    return project_rows(_fetch_export_lines(base_url, batch_id), payload)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--out", required=True, help="JSON output path, or - for stdout")
    args = parser.parse_args()

    rows = fetch_projection(args.base_url, args.batch_id)
    text = json.dumps(rows, ensure_ascii=False, indent=2) + "\n"
    if args.out == "-":
        sys.stdout.write(text)
    else:
        Path(args.out).write_text(text, "utf-8")


if __name__ == "__main__":
    main()
