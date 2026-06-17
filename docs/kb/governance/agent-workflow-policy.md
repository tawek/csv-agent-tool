# Agent Workflow Policy

## Purpose

Capture the durable project governance rules that should guide leader and specialist work.

## Policies

- Follow spec-first execution for every feature, bug fix, or behavior change.
- Prefer artifact-driven delegation: input artifact in, output artifact out.
- Capture user intent in a feature workspace before downstream work starts.
- Keep review findings in an action register until every finding has a disposition.
- Require architect review for architecturally significant source changes.
- Prefer one feature workspace per workstream instead of one global scratch TODO file.

## Feature workspace pattern

Use `project/<feature>/` for task-scoped durable artifacts such as:

- `implementation-notes.md`
- `status.md`
- `action-register.md`
- `reviews.md`
- `mockups/`

## Leader responsibilities

- choose the right specialist,
- serialize overlapping source edits,
- reject incomplete artifact outputs,
- maintain cross-agent coherence,
- report open and deferred findings honestly.
