# Architecture and operator contract

## States

`request → premium plan → low-cost specialist design → premium build dispatch → low-cost build worker → {gates + low-cost reviews → premium triage → low-cost repair}* → verified_candidate | blocked`

The state machine is implemented by the **Python supervisor**, not by language-model instructions. Each invocation receives a standalone prompt and must return the required structured JSON schema. Only the low-cost Build Worker runs with write-capable tools. Reviewer verdicts **do not** replace subprocess exit codes.

## Handoff contract

- **Plan**: summary, UI change flag, acceptance criteria (ID, description, verification), work items, assumptions, risks.
- **Design**: per-role guidance, proposed checks, risks, blocking questions. Any blocking question prevents Build.
- **Build orchestration**: compact task dispatch and evidence-driven triage, without source writes.
- **Build**: summary, changed files, new tests, unresolved work; unresolved work blocks verified completion.
- **Gate results**: argv, exit codes, timing, file path and bounded excerpt for failures. Gate `pass` requires all subprocesses in the gate to return zero.
- **Reviews**: `pass | fail | not_applicable`, cited findings (critical/high/medium/low), checks and limitations; missing reviewers and non-pass verdicts block release.

## Review/repair policy

Critical, high and medium findings must be fixed. Low severity can remain advisory. The default is three review cycles. After each repair, all configured deterministic gates and every required specialist review rerun; prior passes are **not** cached. The last report contains the actual final results.

## Isolation / threat model

A hostile repository can contain dangerous install scripts, tests, readmes and embedded instructions. Running the Builder or even a verification command on the host is not safe merely because the model is sandboxed. Use an ephemeral VM/container, non-production credentials, restrict network egress, and grant a fine-grained credential for PR-only write operations if publication is enabled. Logs may contain proprietary code and secrets; `.factory/` is Git-ignored but not encrypted.

The supervisor uses a clean working-tree prerequisite, SHA-256 snapshots of protected files, checks Git HEAD after agent stages, structured contracts, and subprocess timeouts. These are **integrity tripwires**, not a hard security boundary. There is no OS isolation in this version.

## Future roadmap

- v0.2: Docker/VM executor and worktree-per-feature; immutable verification image; policy as code.
- v0.3: durable SQLite run state, resume/retry, aggregated token/cost reporting, parallel independent worktrees, notifications.
- v0.4: staging environment, browser screenshot comparisons, a11y audit, security scans/attestation; PR CI coordination.
- v1.0: optional policy-gated release promotion and rollback, with mandatory human approvals for production or destructive operations.

## Tiered routing (v0.4)

Planner and Build Orchestrator have read-only access on explicit GPT Sol / Claude Opus. All task-specific roles, including the implementation worker, have explicit GPT Luna / Claude Haiku. No default models, silent escalation or implicit downgrades are permitted. CLI model availability is account-dependent and a provider failure blocks the run.

## Verification content isolation

The supervisor fingerprints tracked and untracked, nonignored source before and after planning, designing, orchestration, gates and review. That catches additional mutations that do not affect governance files. It is still not a security boundary against a hostile local subprocess. Execute untrusted builds in a VM/container.
