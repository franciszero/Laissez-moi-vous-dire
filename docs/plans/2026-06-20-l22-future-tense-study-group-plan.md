# L22 Future Tense Study Group Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Group the L22 future-tense checkpoints into one stable learning sequence and add six machine-graded production cards without changing species coverage or existing SRS IDs.

**Architecture:** Add an optional checkpoint-group data file consumed by the existing species-to-manifest builder. The builder annotates and sorts existing checkpoint cards, appends supplemental practice cards without `source_species`, and leaves the current output byte-for-byte behavior unchanged when the option is absent. Streamlit continues to render the native checkpoint dataframe and existing SRS flow.

**Tech Stack:** Python, JSON, pytest, Streamlit AppTest, existing manifest/checkpoint/SRS modules.

---

### Task 1: Lock the checkpoint-group build contract

**Files:**
- Modify: `tests/test_build_checkpoints_from_species.py`
- Modify: `scripts/build_checkpoints_from_species.py`

- [x] Add a failing test with two reviewed species, one study group, and one practice card. Assert grouped cards sort first, ungrouped cards retain relative order, the practice card has a stable `Lx:practice:*` ID, and `coverage.expected_species_count` remains the reviewed-species count.
- [x] Add failing validation tests for an unknown species member and a duplicate practice-card ID.
- [x] Run `python3 -m pytest -q tests/test_build_checkpoints_from_species.py` and confirm the new tests fail because checkpoint groups are unsupported.
- [x] Implement optional checkpoint-group loading, validation, annotation, practice-card creation, and stable sorting in the existing builder seam.
- [x] Add `--checkpoint-groups` to the CLI and keep behavior unchanged when omitted.
- [x] Re-run the focused tests and confirm they pass.

### Task 2: Make the native knowledge table show the learning group

**Files:**
- Modify: `app.py`
- Modify: `tests/test_checkpoint_ui.py`

- [x] Add a failing behavior test that loads L22 and asserts the native dataframe starts with contiguous “将来时系统” rows and exposes 109 checkpoints.
- [x] Update `_checkpoint_category` to prefer `study_group_label` before tag-derived categories.
- [x] Run `python3 -m pytest -q tests/test_checkpoint_ui.py` and confirm the behavior passes without adding widgets, CSS, or state.

### Task 3: Author and build the L22 pilot

**Files:**
- Create: `../L22/L22.checkpoint_groups.json`
- Regenerate: `../L22/manifest.json`

- [x] Define one `future-tense-system` group containing the 19 approved species cards in pedagogical order.
- [x] Add six deterministic production cards for `voudrai`, `voudrais`, `finirons`, `finirions`, `aura fini`, and `auront trouvé`.
- [x] Run the builder with `--checkpoint-groups ../L22/L22.checkpoint_groups.json`.
- [x] Run `python3 scripts/coverage_report.py ../L22/manifest.json` and verify species coverage remains 103/103 while checkpoint count becomes 109.

### Task 4: Verify behavior and preserve unrelated work

**Files:**
- Modify only if verification exposes a defect in files owned by Tasks 1–3.

- [x] Run `python3 -m pytest -q` in the app repo; distinguish any pre-existing failure in the user's dirty `matcher.py` work from this feature.
- [x] Use AppTest to select L22, enter `📝 知识点（109）`, inspect the native dataframe order, and submit one new machine-graded card.
- [x] Restart Streamlit in the existing `laissez-8501` tmux session and verify `/_stcore/health` returns `ok`.
- [x] Confirm `matcher.py`, `tests/test_matcher.py`, and the four untracked wordsmith files remain untouched.
- [x] Commit and push only the app files owned by this plan and the L22 data files owned by this plan.
