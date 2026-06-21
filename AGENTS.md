# Existing Pattern First Gate

Before modifying any existing file, UI flow, data loader, test, SRS behavior, or
runtime behavior in this app, read and follow:

`/Users/francis/.codex/skills/existing-pattern-first/SKILL.md`

This gate is always-on for this repo. It applies to small follow-up edits, not
only large refactors. First find and read the closest local implementation with
`rg`; reuse existing Streamlit/app patterns and native framework capabilities by
default. Do not introduce fake substitutes such as button walls, fake tables,
ad hoc parsers, duplicate state, or global CSS/`!important` overrides unless the
user explicitly approves the deviation before edits.

Tests must prove user behavior and app invariants, not implementation trivia.
Final reports must name the existing pattern or native capability reused, the
affordance preserved, and the verification performed.

# Project Decisions & Data Conventions

Before any knowledge-card / manifest / SRS / vocab / data-model work in this app,
also read `HANDOFF.md` — especially **§5 关键决策/数据约定** and **§6 陷阱**.
Do not re-derive or overturn decisions recorded there. In particular: lessons own
their own cards (cross-lesson knowledge = duplicate + light pointer, NOT a shared
ID/registry/mastery layer), and apostrophes are normalized only at match time
(`matcher.norm_fr`), never in stored `lemma`/data.
