# Vocabulary provenance schema

Vocabulary provenance answers a learner's question: “Why was this word admitted
to this lesson, and where can I reconnect it to the original material?”

The canonical field is a per-entry `provenance` array:

```json
[
  {
    "source_kind": "reading_question",
    "source_ref": "L31:T5Q10:option-B",
    "teacher_action": "synonym",
    "selection_reason": "讲 Q10 选项 B 的关键词时补充的近义词",
    "evidence": {
      "file": "docker-data/outputs/L31/L31_final_working.md",
      "time": "01:12:00-01:13:00",
      "lines": "1040-1054"
    },
    "learning_note": "与选项 B 一起讲解，但不属于题目原文"
  }
]
```

## Required fields

- `source_kind`: stable source class, normally `opening_review`,
  `reading_question`, `teacher_extension`, or `user_supplied`.
- `source_ref`: compact lesson-local anchor such as
  `L31:T5Q10:option-B`, `L31:opening-review`, or `L31:transcript`.
- `teacher_action`: pedagogical relationship, normally `memorize`, `explain`,
  `correction`, `contrast`, `synonym`, `word_family`, `review`, or
  `user_supplied`.
- `selection_reason`: one concise learner-facing Chinese sentence explaining
  why this item is useful enough to keep.
- `evidence.file`: repository/workspace-relative source file that supports the
  claim.

## Optional fields

- `evidence.time`: transcript/audio timestamp or range.
- `evidence.lines`: source line or range.
- `learning_note`: boundary or study guidance, especially when the teacher says
  a term is only explanatory and does not need memorization.

## Invariants

1. `zh` remains the concise answer used for recall and grading.
2. Provenance is append-only for an existing lemma; ingestion must not overwrite
   its learning fields.
3. Exact provenance re-ingestion is idempotent.
4. Multiple genuine classroom relationships may coexist for one lemma.
5. Evidence must support the stated relationship. Do not invent a precise
   question, option, time, or teacher action when the source only supports a
   broader lesson/transcript association.
6. Legacy rows may omit provenance. New launch and screenshot-ingest selections
   may not.
7. When `evidence.file` points directly to a timestamped transcript, every
   disjoint `evidence.time` interval must have a same-position line range in
   `evidence.lines`, and that range must contain an overlapping transcript
   timestamp header. For example:
   `"time": "05:30-06:00; 17:30-18:00"` pairs with
   `"lines": "111-114; 270-275"`. Never reuse one coarse line range for two
   disconnected transcript intervals. A review ledger may summarize several
   intervals at one line only when that ledger line is the cited evidence.
