# Consumable factory CLI task list

Spec: `specs/consumable-factory-cli.md` (approved).
Plan: `tasks/plan.md` (approved; source 20e13a8 passed Windows/Linux 111-test suites and the installed fixture; reviewed docs were published as dd1eba4, remote SHA matched, Windows/Ubuntu CI passed, and fresh commit-pinned installs and consumer smoke checks passed).

- [x] 1. Establish reviewed baseline, isolated checkout, and approved maintenance execution path.
- [x] 2. Package the runtime and ship installed help/version with isolated imports.
- [x] 3. Implement safe minimal initialization and native harness skills.
- [x] 4. Forward runs to the supervisor with project-owned configuration/state.
- [x] Checkpoint: installed-package preflight, governance/lock tests, and initialization tests pass.
- [x] 5. Implement evidence-based doctor/status commands.
- [x] 6. Document the CLI and add Windows/Linux artifact checks.
- [x] Checkpoint: wheel/sdist contracts pass on both platforms; legacy behavior remains intact.
- [x] 7. Qualify the complete build, Codex Desktop/CLI, and one real factory candidate; resolve independent review findings.
- [x] Checkpoint: CLI-01–12 runtime evidence passed for source 20e13a8; CLI-13 review and CLI-14 publication checks passed for commit dd1eba4.
- [x] 8. Push the initial verified source normally to the approved GitHub repository and verify a fresh commit-pinned remote installation (commit 19939337).
- [x] 9. Push the role-qualified source with final docs, verify exact remote SHA and hosted CI, then run a fresh commit-pinned install and help/doctor/status smoke.

All scoped task items are complete. Application `verified_candidate` evidence for the fixture run and maintenance release verification are distinct.
