# Changelog

## v0.6.0 — Consumable CLI work (qualification pending)

- Added the `software-factory` package entry point, minimal project initialization, and installed supervisor forwarding with consumer-owned configuration and state.
- Added direct-wheel and sdist-derived-wheel artifact checks plus Windows/Linux CI coverage. The docs and verification matrix describe remaining release and native-host checks; this work does not claim live qualification.
- The installed lifecycle covers `init`, `doctor`, `run`, and `status`; Windows wheel and sdist-derived-wheel tests exercise initialization, readiness, and dry-run status. Native-host, provider, Linux artifact, and final release qualification remain pending in the CLI matrix.

## v0.5 — Local dashboard and durable events

- Added the optional loopback dashboard, SQLite-backed run/event history, live/demo separation, event replay, and evidence-based run-state projection.

## v0.4 — Adversarial model tier & verification review

- Split premium read-only Build Orchestrator from low-cost code-writing Build Worker; premium Planning Orchestrator retained.
- All six specialist/worker roles switched to explicit Haiku/Luna IDs; Opus/Sol restricted to two orchestrators.
- Block missing or unapproved model/provider pairings; no unspecified model defaults or silent privilege escalation.
- Additional verification source fingerprints before and after read-only phases and executable gates.
- Existing npm/yarn/pnpm gate script definitions and referenced local gate scripts are integrity-checked against their pre-build versions.
- Strict structured output validation, including new dispatch/triage schema.
- Adversarial regression tests and documented residual operational risks.

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
