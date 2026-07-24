# Vocabulary provenance implementation plan

## Goal

Make every newly selected lesson vocabulary item explainable in learner-facing
Chinese without polluting its core translation. Preserve lemma identity,
existing learning progress, and the current lesson-launch workflow.

## Proven root cause

- `scripts/merge_vocab.py` previously skipped an existing lemma completely, so
  a later screenshot or transcript pass could not attach new classroom
  evidence.
- Unknown input fields were discarded when a new row was built, so structured
  provenance could not survive ingestion.
- `vocab.load_all_vocab()` discarded provenance, leaving the 8501 app no data
  to render.
- Launch verification checked file/count consistency but did not require an
  admission reason for newly selected vocabulary.

## Data contract

Each `vocab.json` row may contain a `provenance` array. Legacy rows may omit it.
Every new launch/ingest row must supply at least one item:

```json
{
  "source_kind": "teacher_extension",
  "source_ref": "L31:T5Q10:option-B",
  "teacher_action": "synonym",
  "selection_reason": "讲 Q10 选项 B 的关键词时补充的近义词",
  "evidence": {
    "file": "docker-data/outputs/L31/L31_final_working.md",
    "time": "01:12:00-01:13:00",
    "lines": "1040-1054"
  },
  "learning_note": "与题目词一起理解，不等于它是选项原文"
}
```

Required fields are `source_kind`, `source_ref`, `teacher_action`,
`selection_reason`, and `evidence.file`. Evidence time/lines and
`learning_note` are optional. Merge identity is the normalized complete
provenance object, so rerunning the same ingest is idempotent while genuinely
different classroom occurrences append.

## Implementation

- [x] Validate, preserve, and append provenance in `merge_vocab.py`.
- [x] Aggregate provenance per lesson in `vocab.load_all_vocab()`.
- [x] Render a native Streamlit expander after the answer is visible.
- [x] Add behavior-focused merge, loader, and learner-surface tests.
- [x] Update lifecycle, launch, and screenshot-ingest skills to require the
      contract for newly selected vocabulary.
- [x] Backfill the 48 previously unprefixed L31 rows from the existing
      provenance audit.
- [x] Verify L31 remains 117 lemmas and existing word IDs/progress are stable.
- [x] Run the full app suite, restart 8501, and perform a health/UI check.

## Safety and compatibility

- Do not rewrite `lemma`; it is the existing storage identity.
- Do not overwrite `pos`, `zh`, `example`, gender, or lesson fields when adding
  provenance to an existing lemma.
- Do not require provenance retroactively for unrelated legacy lessons.
- Keep `[T…Q…]` prefixes readable for backward compatibility, but treat the
  structured array as the canonical provenance.
- Use Streamlit's existing `st.expander` affordance and keep provenance hidden
  until an answer/learning panel is shown.

## Verification

- Regression tests prove existing row preservation, provenance append, duplicate
  suppression, and invalid-input rejection.
- Loader tests prove the same lemma can retain different provenance by lesson.
- App test proves the explanation is not leaked before answer reveal and is
  visible afterward.
- Course-data checks compare pre/post L31 lemma count and word-store IDs.
- Full `pytest`, Streamlit boot, and HTTP health checks complete the release.
