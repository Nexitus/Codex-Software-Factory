# Adversarial audit: software factory v0.4

**Date:** 2026-10-20. **Scope:** v0.3 ZIP, Python supervisor, prompts, configuration, installation, skill loading, tests, native Claude agents. **Approach:** static inspection → attack hypotheses → harness changes → mocked execution/regression tests. Live Codex/Claude were not invoked. Not a penetration test or an independently audited security boundary.

## Intended operating invariant

Only two **read-only** orchestration invocations are allowed premium models: `planner` and `build_orchestrator` (Claude Opus or GPT Sol). Every task execution or specialized role (the write-capable `builder`, `testing`, `architecture`, `ui`, `ux`, `security`) must use Claude Haiku or GPT Luna. Every provider invocation sends `--model` explicitly. Model unavailability terminates the run; no implicit default and no cross-tier fallback.

| Finding | Risk | Disposition / evidence |
|---|---|---|
| Original Builder was simultaneously premium orchestrator and implementation worker | High: unrestricted expensive implementation loops | **Fixed**: new read-only `build_orchestrator` with `dispatch`/`triage`; low-tier `builder` receives its plan. Verified mocked two-round repair. |
| Existing `sonnet` specialist model assignments, null Codex models | High: allowed costly/unknown model selection | **Fixed**: explicit Sol/Opus vs Luna/Haiku role matrix, fail-closed allowlists; adversarial downgrade/upgrade/missing/default tests. |
| Native `.claude/agents` still declared Sonnet despite runner policy | Medium: interactive drift | **Fixed**: new Opus `build_orchestrator`, Haiku builder and all specialist agents; Opus planner. |
| Plan/review output could carry unexpected fields, some required values untyped | Medium: schema ambiguity and fabricated approvals | **Fixed**: strict recursive schema validation, no additional fields, required type checks, dispatch/triage schema. |
| Read-only phases and gate subprocesses could silently alter application code after verification | High: stale evidence, compromised source | **Mitigated**: fingerprints tracked + untracked nonignored source around planning, design, orchestration, gate execution, and reviewer execution. Unit tests cover fingerprint drift. |
| Worker could rewrite pre-existing package.json `test` command to `echo PASS` | High: executable gate reports green with no real check | **Mitigated**: lock existing npm/pnpm/yarn/bun gate scripts and named local script entrypoints against pre-build values. Test verifies bypass blocks. |
| Unconfigured/fake gates could be treated as sufficient for a new project | High: unearned delivery certification | **Residual**: nonempty argv is required, but meaning and completeness of arbitrary test commands cannot be inferred by this supervisor. Configure trusted verification independent from worker-editable code and CI. |
| Agent may spawn nested CLIs outside supervisor with higher-tier models via shell | High: model spend and policy evasion | **Residual**: direct supervisor invocations are strictly routed. Shell and other local executables are **not** OS-confined here. Use sandboxing, scoped provider credentials, spend ceilings, and deny nested model endpoints in production. |
| Hostile gate scripts may exfiltrate credentials or damage host | High: untrusted repository execution | **Residual**: no OS-level containerization; user must run in disposable VM/container, with no production credentials and controlled egress. |
| Provider/model availability and CLI-specific flags | Medium: runtime incompatibility | **Residual**: local tests use fake CLIs. Live CLI auth, account entitlements, plugin tool behavior, and platform-specific availability unverified. |
| Generated tests may be removed or assertions weakened | High: false assurance | **Residual**: gate scripts' entrypoints are protected where pre-existing, but test content and new projects still require independent regression/coverage reviews and immutable CI. |

## Test loop

- Baseline v0.3: 18 tests, 1 mocked end-to-end repair loop.
- Cycle 1: introduce separate premium dispatch/triage and low-cost worker; correct fixtures to require explicit routing. 18/18 passed.
- Cycle 2: add model escalation/downgrade/missing/default injection, strict handoff shape, content fingerprint tests; 26/26 passed.
- Cycle 3: try rewriting npm test script and a referenced Python security script, plus a direct Claude model flag test; 30/30 passed.
- Mandatory checks: `python -m py_compile factory.py skillctl.py install.py`; `python -m unittest discover -s tests -v`.

## Operating requirements

1. Set actual executable gates and configure account-supported model IDs. A `--dry-run` checks routing and gate configuration, **not** model access.
2. Use isolated Git working trees / ephemeral containers. Never place production secrets in worker environments.
3. Treat `verified_candidate` as a locally verified proposal, not an attested production release.
4. Keep CI verification and branch protection outside the model-editable workspace; inspect the PR before merge.
5. Enable opt-in third-party skills only after source/license and security review; skill text cannot grant tools.
6. For stronger model-cost enforcement, put model calls behind a provider-aware proxy with per-role credentials and hard spending budgets. `--model` alone is not proof of actual billing or nested-agent isolation.

## Sources for CLI model nomenclature

- OpenAI: <https://openai.com/index/introducing-gpt-6-sol-and-luna/>, <https://learn.chatgpt.com/docs/cli/reference>
- Claude Code: <https://support.claude.com/en/articles/11940350-claude-code-model-configuration>
