# Instructions for Codex in this repository

Follow `POLICY.md` for all factory workflows. The external supervisor `factory.py` determines the next stage; do not bypass it. Human requirements live in `specs/`, and results in ignored `.factory/runs/`.

Roles are in `roles/`. Codex may be Planner or a read-only specialist reviewer, or Builder if configured in `factory.config.json`. Only the low-tier Build Worker (builder) is allowed to modify application code/tests. Do not touch factory infrastructure, alter review findings, waive gates, push, merge, or deploy.

For interactive use, apply the `.agents/skills/software-factory/SKILL.md` workflow. Read the relevant role file before performing the assigned task. Prefer evidence-based outputs over unsupported completion claims.

## Model routing
Planner and build_orchestrator are premium coordination roles (Codex Sol / Claude Opus). All other roles, including builder, must run on Luna / Haiku. Configuration is validated fail-closed; never silently upgrade workers.
