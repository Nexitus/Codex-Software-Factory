# Foundational Loop Skill Scan — alirezarezvani/claude-skills

Date: 2026-10-20. Reviewed [upstream repo](https://github.com/alirezarezvani/claude-skills) at commit `19392f7a08264ed00486a251f5b2098321771f94` (repository MIT). The `engineering`, `engineering-team`, `loop-library`, `orchestration`, and `project-management` directories were catalogued; the named SKILL.md documents below were inspected. Author's claims of “production-ready”, security effectiveness and benchmark outcomes were not independently verified. **The repository is a large collection of skills, not an alternate software-factory supervisor to install wholesale.**

## Recommended for core architecture

| Skill/component | Path | Factory responsibility | Policy | Priority |
|---|---|---|---|---|
| Loop Library | `loop-library/SKILL.md` | Design bounded Plan → Build → Verify → Repair loops with trigger, state, stop condition and escalation | Supervisor design reference; not a runtime LLM controlling state | P0 |
| Agent Harness | `engineering/agent-harness/skills/agent-harness/SKILL.md` and `engineering/agent-harness/README.md` | Explicit goal compiler, deterministic verification, retry-cap and hard STOP semantics | Use design patterns; do not nest its controller inside `factory.py` | P0 |
| Skill Security Auditor | `engineering/skills/skill-security-auditor/SKILL.md` | Review third-party skill contents before staging and check prompt-injection/script/exfiltration risks | Upstream script is **not executed automatically**; human approves source and pin | P0 |
| Agent Workflow Designer | `engineering/skills/agent-workflow-designer/SKILL.md` | Architecture of agent-based products or revisions to this factory | Only when user request explicitly touches multi-agent workflow | P1 |
| PR Review Expert | `engineering/skills/pr-review-expert/SKILL.md` | API/contract blast radius and coverage delta | Read-only architecture/testing review on large diffs | P1 |
| Focused Fix | `engineering/skills/focused-fix/SKILL.md` | Multi-file, multi-cause defects that survive review | Build Agent repair round only; bounded by max rounds | P1 |
| Ship Gate | `engineering/skills/ship-gate/SKILL.md` | Check completeness, security, deployment readiness | Advisory on pre-release Security review; **machine-enforced gates remain authoritative** | P1 |

## Consider later / intentionally excluded from default

| Skill | Assessment |
|---|---|
| `engineering-team/skills/adversarial-reviewer` | Useful independent perspectives, but **requires every persona to find an issue**, risking fabricated problems and infinite repair loops. Keep opt-in only after adapting it to allow evidence-backed zero findings. |
| `engineering/skills/spec-driven-workflow` | Useful acceptance traceability, but the upstream rule “approved spec required” conflicts with the stated one-input, no-interrupt pipeline. Reuse acceptance criteria methodology only; do not install unchanged. |
| `engineering/skills/self-eval` | Self-grading is not a valid quality gate. Use only for non-authoritative telemetry and calibration studies. |
| `engineering/skills/git-worktree-manager` | Correct architectural direction for parallel builds, but upstream tool copies `.env*` into worktrees and may run package installers. Implement worktree creation under the supervisor with restrictive credential handling before adopting it. |
| `engineering-team/skills/senior-qa` | React/Next-specific test scaffolding; consider as an optional Builder test-authoring skill, not a read-only reviewer that edits files. |
| `engineering/skills/skill-tester` | Useful quality grading for imported skills. Gradually adopt its structural/checking criteria, not arbitrary auto-execution of every third-party script. |

## Invariants preserved

1. **One supervisor** owns state; no agent may override max repair rounds or gate policy.
2. **One mutating role** (Builder) writes implementation. Every reviewing specialist must remain read-only.
3. Rejected, missing or contradictory review evidence blocks delivery.
4. No “mandatory issues” review patterns that invent findings to satisfy a quota.
5. Reference skills and prompt content are lower-trust than the supervisor and `POLICY.md`.
6. A third-party skill can enrich reasoning but **never** grant itself network, filesystem, credential or deployment permissions.
7. Successful local checks return a verified *candidate*, not proof of bug-free code or authorization to deploy.

## Future evaluation matrix

For each newly adopted skill, compare identical task sets with and without it: task completion; seeded-defect recall and false positives; gate success; escaped regressions; number of repair cycles; tokens, runtime and CAD/API cost. Prefer no additional skill when it adds cost and complexity without meaningful improvement.
