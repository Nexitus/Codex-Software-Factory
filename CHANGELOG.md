## v0.4 — Adversarial model tier & verification review

- Split premium read-only Build Orchestrator from low-cost code-writing Build Worker; premium Planning Orchestrator retained.
- All six specialist/worker roles switched to explicit Haiku/Luna IDs; Opus/Sol restricted to two orchestrators.
- Block missing or unapproved model/provider pairings; no unspecified model defaults or silent privilege escalation.
- Additional verification source fingerprints before and after read-only phases and executable gates.
- Existing npm/yarn/pnpm gate script definitions and referenced local gate scripts are integrity-checked against their pre-build versions.
- Strict structured output validation, including new dispatch/triage schema.
- Adversarial regression tests and documented residual operational risks.

# Changelog

## v0.3 — 2026-10-20

- Catalogued six requested GitHub repositories with pinned commits and corresponding role/phase assignments.
- Added `skillctl.py` to stage and verify instruction skills without executing third-party scripts.
- Added deterministic role-based prompt activation for Codex and Claude Code (including `--bare` sessions); disabled by default until explicit installation, license/security review and config opt-in.
- Added UI UX Pro Max (UI/UX), Emil Kowalski (UI/UX/Testing edge cases), Graphify guidance (planning existing codebase) and Ponytail (planning simplicity).
- Registered Screenshot-to-Code as an **external app** requiring a future service adapter, not a fake native skill. Graphify AST scan also requires a separate controlled tool worker.
- Audited `alirezarezvani/claude-skills` for foundational-loop patterns: Loop Library, Agent Harness, Agent Workflow Designer, Focused Fix, Ship Gate, Skill Security Auditor, PR Review Expert; adversarial reviewer excluded from automatic activation.
- Updated policy protection to cover skill registry and lock files; added 7 skill-focused tests on top of the original 11 supervisor tests.

### Limitations

- Live Codex/Claude sessions, GitHub network installations and the Screenshot-to-Code/Graphify command integration have not been end-to-end tested here.
- The local supervisor is not an OS security sandbox. Run untrusted code only in a restricted ephemeral runtime.
- `skills.enabled` defaults to `false`. Third-party skill text is not shipped in the ZIP; a deliberate pinned-source install is required.
