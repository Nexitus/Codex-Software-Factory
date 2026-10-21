# Consumable Factory CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for the approved maintenance workflow, or superpowers:subagent-driven-development if the user selects delegated maintenance execution. Steps use checkbox syntax for tracking. Only the low-tier Builder may implement code/tests.

**Goal:** Install the factory once and invoke it safely from terminals and all four requested harness surfaces, then publish the verified source.

**Architecture:** Add one Python CLI around the existing supervisor. Package the existing runtime under a unique namespace without moving its source files; keep resource reads separate from project-local configuration/state. Initialize only config and native skills; leave the dashboard as an optional source-checkout feature for this release.

**Tech Stack:** Python 3.10+, standard-library argparse/pathlib/importlib.metadata, setuptools build backend, existing unittest/pytest and React/Vite test tools. No new core runtime dependency.

**Spec:** `specs/consumable-factory-cli.md` (approved 2026-10-21).

## Global constraints

- Distribution: `codex-software-factory`; executable: `software-factory`.
- Support Windows PowerShell 7 and Linux. No macOS verification claim.
- Preserve Codex-only defaults: `gpt-6-sol` for planner/build_orchestrator; `gpt-6-luna` for Builder and specialists. Use xhigh for Codex implementation when supported; never silently substitute a model/effort.
- Prefer `uv tool install`; document `pipx install`. No PyPI publication.
- Preserve `python factory.py ...`, `python install.py <repo>`, application gate protection, locks/quarantine, review separation, and dashboard behavior.
- Use Ponytail full for every code task and Graphify during planning; workers must read Ponytail before editing. Keep the project Impeccable hook enabled in the execution checkout.
- Framework publication is a normal push to the existing requested remote after CLI-01 through CLI-13 pass. No force-push, merge, deployment, or fabricated factory delivery report.
- Task tracking is `tasks/todo.md`. Do not advance unchecked readiness gates on narrative claims.

## Review focus

1. Installing into a shared environment must not expose a generic top-level `app` or `factory` package: inspect the wheel and import from an unrelated directory (Task 2).
2. A target `.factory` or integration parent that is a symlink/junction must not redirect writes outside the checkout: test path containment before mutation (Tasks 3 and 4).
3. A worktree's `.git` is a file, and two worktrees of one repository are separate checkouts: test initialization, config selection, and lock identity (Tasks 3 and 4).
4. Newer partial runs must not let an older successful delivery masquerade as latest success: test ordering and malformed/missing evidence (Task 5).
5. Installed CLI runs must not break explicit dashboard queue/event-DB handoffs or PID identity checks: preserve and regression-test these flows (Task 4).

## Scope map and dependency order

| Files | Responsibility |
| --- | --- |
| `pyproject.toml`, root `__init__.py`, `MANIFEST.in` | Explicit namespaced packaging, version and installed resources. |
| `cli.py` | Parse public subcommands, dispatch init/doctor/run/status; no duplicate orchestration. |
| `project_setup.py`, `templates/project-config.json`, `templates/software-factory/SKILL.md`, `templates/claude-software-factory/SKILL.md` | Safe minimal initialization and host adapters. |
| `factory.py`, `skillctl.py` | Installed/source import compatibility, writable path ownership, project skill locks. |
| `tests/test_distribution.py`, `tests/test_cli.py`, `tests/test_project_setup.py` | Artifact integration and new command contracts. |
| Existing `tests/test_factory.py`, `tests/test_skills.py`, `tests/test_backend.py` | Compatibility and governance regressions. |
| `.github/workflows/ci.yml` | Windows/Linux artifact checks, retaining existing gates. |
| `README.md`, `FACTORY_SETUP.md`, `docs/ARCHITECTURE.md`, `docs/PUBLISH.md`, `docs/consumable-factory-cli-verification.md` | Operator instructions and evidence matrix. |

Order: Task 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8. Tasks are sequential because resource paths, initialization, and run forwarding share a contract. No parallel implementation is needed.

## Task 1: Establish a safe maintenance baseline and execution contract

**Files:** Read `POLICY.md`, `AGENTS.md`, `roles/builder.md`, all current tracked changes/untracked source; create an ignored baseline inventory under `.factory/maintenance/`. No code change.

**Interfaces:** Produces the reviewed baseline commit, execution checkout, exact allowlist, and explicit maintenance execution decision for subsequent tasks.

- [ ] Inventory tracked diffs and untracked files individually. Include the existing dashboard work required by the spec; exclude generated output, credentials and unrelated files. Record baseline HEAD and hashes before any transfer.
- [ ] Resolve the known governance conflict before dispatch: `factory.py:PROTECTED`, `protected_snapshot`, and `assert_protected` reject every change to `factory.py`, `skillctl.py`, `.agents`, and `.claude`. There is no maintenance-mode argument. An application factory run cannot implement this plan honestly.
- [ ] Obtain approval of a separate maintenance workflow: a scoped `gpt-6-luna` Builder in an isolated checkout implements this plan under Codex coordination, with independent low-tier review and deterministic checks. Keep the application supervisor unchanged except for the approved product changes. This execution exception does not create or claim an application `verified_candidate` for the maintenance work.
- [ ] Use `superpowers:using-git-worktrees` at execution time. Stage only the individually reviewed baseline paths; commit the baseline before creating the isolated checkout, preserving all other changes in the original workspace. Do not use `git add .`, stash/reset, or change existing HEAD during a live factory run.
- [ ] Run `C:\Users\brlam\.agents\skills\impeccable\scripts\impeccable.cmd hooks on`, then `hooks status`, from the execution checkout, as required by the user's project instructions.
- [ ] Record baseline Python/frontend/build/security test results using the configured commands. Failures are blockers to qualification; do not change gates to pass them. Confirm Codex/Claude/OpenCode CLI versions and remote access without exposing credentials.

**Exit condition:** Approved, reproducible baseline and maintenance execution path. If the exception is not approved, stop code work and report this specific conflict; remaining tasks describe the implementation once resolved.

## Task 2: Ship an installable command with isolated imports

**Files:** Create `pyproject.toml`, `__init__.py`, `MANIFEST.in`, `cli.py`, `tests/test_distribution.py`; modify only imports in `factory.py` if necessary for package execution.

**Interfaces:** `cli.main(argv: list[str] | None = None) -> int`; console entry point `codex_software_factory.cli:main`. Map package `codex_software_factory` to the repository root and `codex_software_factory.app` to `app/` explicitly in setuptools; do not use automatic package discovery. Define version `0.6.0` in metadata. `--version` reads distribution metadata; root source use has a documented fallback.

- [ ] Add artifact tests `test_wheel_runs_outside_source_tree`, `test_sdist_builds_self_contained_wheel`, `test_install_has_no_generic_top_level_modules`, and `test_help_without_optional_dependencies`. Assert exit 0 for help/version, package resource presence, and absence of source-tree `PYTHONPATH` dependency. Assert the installed version is `0.6.0`.
- [ ] Run `python -m pytest -q tests/test_distribution.py` and confirm the tests expose missing packaging/entry-point behavior before implementation.
- [ ] Add minimal metadata and CLI help/version. Explicitly package runtime Python modules, `roles/*.md`, `POLICY.md`, `skills/registry.json`, `templates/**`, and license metadata. Exclude `.factory`, private/local config, tests, caches, and frontend dependencies from the wheel. Include dashboard source and its manifests in the source archive, without Node or compiled/generated output.
- [ ] Support relative imports when `factory.py` is installed as a package and the existing absolute imports when run as a source script. Do not duplicate the runtime or import FastAPI/Uvicorn through package initialization. Keep dashboard startup documented from the source checkout; a dashboard console command is outside this release.
- [ ] Build with `uv build --out-dir .factory/dist`; install each wheel into a fresh `uv venv` with `uv pip install --python <venv-python> <wheel>`. Build another wheel from the source archive in a separate temp directory and test it the same way. Use platform-appropriate venv executable paths.
- [ ] Run focused tests, inspect archive members, and commit only this task's changes after review.

**Acceptance:** CLI-01 and CLI-02 packaging/help portions. Setuptools is a build dependency, not a runtime dependency.

## Task 3: Initialize projects safely with native integrations

**Files:** Create `project_setup.py`, both integration templates, `templates/project-config.json`, `tests/test_project_setup.py`; modify `cli.py`. Preserve `install.py` as the legacy scaffold installer.

**Interfaces:** `project_setup.initialize(project: Path, harnesses: list[str]) -> list[Path]` returns written paths; raises `ValueError` for invalid targets/conflicts. `--harness` is repeatable with choices `codex`, `claude`, `opencode`; default is all three.

- [ ] Add `test_init_minimal_checkout`, `test_init_repeat_is_noop`, `test_conflict_is_atomic`, `test_init_worktree_unicode_space_path`, `test_reject_symlink_parent`, and `test_select_harnesses`. Assert original contents remain byte-identical on any preflight failure and that no application/dashboard source is copied.
- [ ] Run `python -m pytest -q tests/test_project_setup.py`; confirm failures represent missing behavior.
- [ ] Use Git to find the checkout, precompute desired output, reject conflicting contents and escaping symlinks/junctions before writes, and apply only missing files. Preserve existing config verbatim; validate/report it through doctor. Write a narrowly marked ignore addition only when required, without replacing the user's ignore content. Stage all new output before replacement and clean up files created by this invocation if an I/O failure prevents completing it; preserve pre-existing files.
- [ ] Generate `factory.config.json` from a dedicated template with all eight approved model/provider defaults, existing limits, and required gate names with empty command lists. That is deliberately unready; doctor must report missing commands. Do not copy the factory/dashboard gate configuration into a consumer project.
- [ ] Codex and OpenCode share `.agents/skills/software-factory/SKILL.md`; install the Claude adapter in `.claude/skills/software-factory/SKILL.md`. Deduplicate output when both compatible hosts are selected. Skills pass requests as argument arrays or spec-file inputs and defer all stage decisions to the supervisor.
- [ ] Re-run focused tests and legacy installer tests; commit the complete initialization slice after review.

**Acceptance:** CLI-03, CLI-04, and integration files for CLI-09. Legacy installers retain existing behavior, not minimal-init behavior.

## Task 4: Run the installed supervisor with project-owned state

**Files:** Modify `cli.py`, `factory.py`, `skillctl.py`; extend `tests/test_cli.py`, `tests/test_factory.py`, `tests/test_skills.py`, and relevant backend regression cases.

**Interfaces:** `factory.main(argv: list[str] | None = None) -> int` retains zero-argument source-script behavior. `cli.main` forwards parsed run options to that function as an argv list. `skillctl` keeps `load_registry()` for packaged read-only catalog data and resolves staged skill trees/lock against the selected project.

- [ ] Add `test_run_argument_boundaries`, `test_run_exit_codes`, `test_project_config_default`, `test_readonly_package_installation`, `test_two_projects_do_not_share_cli_state`, `test_dashboard_handoff_preserved`, and `test_protected_runtime_unchanged`. Assert literal multiline/quote/shell-marker input arrives unchanged, 0/2/130 are preserved, target-local config/state wins, and invalid config fails cleanly.
- [ ] Confirm focused tests fail, then add argv injection and minimal package/source path corrections. Default config becomes `<project>/factory.config.json`; default CLI event DB becomes `<project>/.factory/dashboard.sqlite3`. Explicit dashboard DB/queue arguments retain their existing semantics.
- [ ] Keep role/policy/catalog reads package-relative. Keep stage outputs, locks, staged skill trees, and skill lock writes project-relative. Update tests that currently patch global lock paths to exercise project-local lock selection. Do not auto-fetch or activate third-party skills.
- [ ] Preserve target protected-file checks. Also fingerprint the installed supervisor/roles/policy/catalog used for this run before and after stages so relocating the runtime cannot remove its integrity guarantee. Include a deliberate mutation test that fails closed; no write permission or extra CLI bypass is introduced.
- [ ] Run `python -m pytest -q tests/test_cli.py tests/test_factory.py tests/test_skills.py tests/test_backend.py`. Rebuild/install the wheel and exercise a committed, configured fixture application's dry-run from outside the source tree. Confirm no writes under the installation directory.
- [ ] Commit reviewed changes. Keep commits outside active application supervisor runs, which intentionally reject HEAD changes.

**Acceptance:** CLI-05 config selection, CLI-06, CLI-07, and read-only optional-dependency execution for CLI-02.

## Task 5: Make readiness and status useful without model calls

**Files:** Modify `cli.py`; extend `tests/test_cli.py`. Reuse `app.projector.project_run`, event storage, `ensure_config`, and gate validation rather than creating another state machine.

**Interfaces:** `doctor(project: Path, config: Path | None = None) -> int` and `status(project: Path) -> int`, called by `cli.main`. Doctor returns 2 on missing readiness prerequisites and 0 on readiness. Status returns 0 for well-formed reports, including a blocked outcome/no runs, and 2 for unreadable or inconsistent evidence; it displays delivery state explicitly.

- [ ] Add `test_doctor_missing_gate_commands`, `test_doctor_missing_cli`, `test_doctor_never_invokes_agents_or_gates`, `test_status_empty`, `test_status_latest_partial_not_old_success`, and parameterized fixtures for preflight/running/interrupted/blocked/verified/malformed evidence.
- [ ] Confirm focused failures. Implement read-only status using the existing event DB/projector and delivery paths; open SQLite in read-only mode. Display source run ID, actual state, and evidence location. Missing event DB is allowed for legacy file-based runs; conflicting evidence is reported, not guessed.
- [ ] Doctor checks canonical checkout, config/gate shape and declared executable availability. Determine state-path writability with a transient probe confined to the selected checkout, remove the probe, and disclose that local probe. Do not read credential files, dump environment variables, run provider authentication flows, create a run, or execute project code to diagnose readiness.
- [ ] Run `python -m pytest -q tests/test_cli.py`, then repeat clean installed-wheel doctor/status smoke checks. Commit after review.

**Acceptance:** CLI-05 and CLI-08. Readiness does not assert provider authentication, executable gates passing, or a verified build.

## Task 6: Document installation and automate artifact checks

**Files:** Modify `.github/workflows/ci.yml`, `README.md`, `FACTORY_SETUP.md`, `docs/ARCHITECTURE.md`, `docs/PUBLISH.md`; create `docs/consumable-factory-cli-verification.md`.

- [ ] Add artifact tests to a Windows/Linux CI matrix without replacing/removing existing checks. Install approved build/test dependencies explicitly. Test the sdist-derived wheel and direct wheel from a foreign directory; use the installed interpreter with no source-tree import fallback.
- [ ] Document `uv tool install "git+https://github.com/Nexitus/Codex-Software-Factory.git@<verified-commit>"` and the equivalent `pipx install` command, substituting the actual verified commit in the release evidence. Before publication, use local artifact installation; do not claim the remote install is available yet.
- [ ] Document init → project gate setup → doctor → run → status, all four host invocation instructions, legacy scaffold behavior, upgrades/rollback, optional source-dashboard setup, and the difference between an invoking host and worker provider.
- [ ] Document missing-provider/gate/config recovery and generated files. Verify every command against installed help and actual host behavior. Update outdated publication URLs; do not create another repository or require changing visibility/settings.
- [ ] Run artifact tests on both platforms and inspect the workflow diff. Record exact commands/results in the verification report. Commit only reviewed docs/CI changes.

**Acceptance:** CLI-01 through CLI-08 documented, CLI-12 automated. A local Windows run does not count as Linux evidence.

## Task 7: Qualify the complete build and Codex surfaces

**Files:** Evidence under ignored `.factory/maintenance/`; summarize in `docs/consumable-factory-cli-verification.md`. Repair code only through the low-tier Builder, followed by fresh independent review.

- [ ] Run `python -m pytest -q tests`, `npm test -- --run`, `npm run lint`, `npm run build`, `ruff check app`, `pip-audit -r requirements.txt -r requirements-dev.txt`, and `npm audit --audit-level=high` in the reviewed baseline environment. Add new Python files to lint/security scope where applicable; never reduce existing checks.
- [ ] Run `npx playwright test` with the existing browser evidence setup; inspect actual dashboard rendering and console/network failures. Use browser-testing-with-devtools for requested rendered inspection. Record any unavailable browser/platform capability as a release blocker.
- [ ] On Codex Desktop and Codex CLI, verify skill discovery, then invoke installed doctor and a real supervisor dry-run in a dedicated fixture checkout. Capture host version, command/action, target path, output, exit/status, and evidence. Do not pass sandbox/permission bypass flags or confuse a transcript from one surface with another.
- [ ] Run one small, committed fixture application through the installed command with all stages, real default Codex workers, genuine configured gates, and independent review. Require its `DELIVERY.json` to say `verified_candidate` and inspect the matching gate/review evidence. This verifies the packaged product; it does not certify the factory maintenance diff.
- [ ] Obtain independent read-only architecture/testing/security review of the complete maintenance diff, using Luna specialists, plus UI/UX review of any pre-existing dashboard changes being published. Resolve all blocking findings through Builder repairs. Re-run affected checks after each repair; bind final evidence to the exact source revision/diff.
- [ ] Fill the CLI-01 through CLI-13 matrix with actual artifact paths, commands, exit codes, platforms, and limitations. No unresolved required check is compatible with publication readiness.

**Acceptance:** CLI-09 through CLI-13, plus final regression coverage for all previous tasks.

## Task 8: Publish the verified source and check remote installation

**Files:** Final verification report; Git metadata only for the approved repository.

- [ ] Review the exact final file inventory and staged diff. Exclude credentials, `.factory`, local configs, caches, node_modules, generated artifacts, and unrelated work. Confirm normal push will not overwrite remote history and record remote state.
- [ ] Commit the verified source locally. If the remote is empty, push the approved release branch as `main`; otherwise push a `codex/consumable-factory-cli` branch without merging. Never force-push or infer that a PR merge is authorized.
- [ ] Push normally to the verified origin `https://github.com/Nexitus/Codex-Software-Factory.git` and verify the remote ref resolves to the exact source commit.
- [ ] Install from the commit-pinned Git URL into a fresh isolated tool environment. Run version/help and init/doctor on a disposable checkout. A project without configured gates should report the expected actionable unready status, not false success.
- [ ] Record CLI-14 output. If remote installation fails, leave release readiness unqualified, diagnose/repair locally, and repeat relevant checks before a normal follow-up push. Do not rewrite history or discard failed-run evidence.

**Acceptance:** CLI-14. Report the pushed branch, commit, install command, verified surfaces/platforms, and any remaining advisory findings.

## Rollback and review handoff

Rollback only task-owned local changes or select the preceding installed version/commit. Never delete consumer source, old scaffold files, evidence, or state. Existing production/deployment state is outside scope.

Self-review coverage: CLI-01/02 → Task 2; CLI-03/04 → Task 3; CLI-05/06/07 → Task 4; CLI-05/08 → Task 5; CLI-12 → Task 6; CLI-09/10/11/13 → Task 7; CLI-14 → Task 8. Review-focus cases are assigned to named tests above.

**Decision needed before code:** approve this plan and the Task 1 maintenance execution exception. Recommended execution is one scoped low-tier Builder with sequential tasks and independent read-only review, coordinated here. Native implementation by the coordinating model is not permitted by the approved role policy. No application-run safeguards are disabled.

Execution approval recorded 2026-10-21: user approved this plan, the separate maintenance workflow, and GPT-6 Luna xhigh subagent implementation. The decision described above is resolved. Task completion evidence lives in tasks/todo.md and the ignored per-plan ledger.

Scope amendment 2026-10-21: user requested only Codex live qualification. Task7 and CLI-09 require Desktop/CLI Codex evidence; Claude/OpenCode adapters remain included but explicitly unverified, with no further authentication or provider calls. Their recorded external failures do not block publication. This user direction supersedes earlier all-four-host live wording.
