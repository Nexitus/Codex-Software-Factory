---
name: software-factory
description: Run or support the repo's Plan → Design → Build → Independent Review → Repair software factory workflow, using the external factory.py supervisor.
---

For a user request to build or change software, prefer preparing an unambiguous Markdown spec in `specs/` and invoking `python factory.py specs/<file>.md` from a clean Git repository after `factory.config.json` is configured. Do not claim success based on agent self-reports; check `.factory/runs/<id>/DELIVERY.json` for `verified_candidate` and all required green gates. Do not circumvent factory controls or authorize release with missing evidence. For manual planning/review, read `POLICY.md` plus the appropriate `roles/*.md` file first. A run only pushes and opens a PR with the explicit `--publish-pr` option; it never merges or deploys.

Cost policy: orchestrator tasks (`planner`, `build_orchestrator`) may use GPT Sol or Claude Opus. All role-specific work (`builder`, reviewers, specialists) MUST run on GPT Luna or Claude Haiku. Never override supervisor routing.
