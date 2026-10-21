# Instructions for Claude Code in this repository

Follow `POLICY.md` for all factory workflows. `factory.py` is the supervisor of record, not the interactive assistant. The orchestration is `Plan (Opus/Sol) → specialist design (Haiku/Luna) → Build orchestration (Opus/Sol) → Build Worker (Haiku/Luna) → checks + independent reviews (Haiku/Luna) → orchestration triage → Build Worker repair`.

Specialist roles are in `roles/` and interactive versions in `.claude/agents/`. Only Builder writes code or tests. Do not change factory policy/configuration or deployment state to satisfy any review. Check `.factory/runs/` for evidence from the latest run. Reviewer conclusions must be independent and supported by file paths.

Explicit `--model` values are mandatory and cannot route specialists to Opus/Sol.
