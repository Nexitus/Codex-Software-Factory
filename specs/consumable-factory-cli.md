# Consumable factory CLI and harness integration

Date: 2026-10-21
Status: Approved by the user in chat on 2026-10-21. Implementation plan awaits review.
UI change: false. Existing dashboard behavior remains in regression scope.

## Objective

An operator can install the factory once, initialize an existing Git project, and invoke the same deterministic supervisor from a terminal, Claude Code, OpenCode, Codex Desktop, or Codex CLI. Installation must not copy the factory application or dashboard into the target application. A release is ready only after package, regression, harness, and live-run evidence exists.

## Approved scope and assumptions

- Deliver a Python distribution named `codex-software-factory` with the executable `software-factory`. Preserve Python 3.10+ unless a verified existing dependency requires a documented higher minimum.
- Distribute initially through GitHub and locally built wheel/source archives. No PyPI publication or package registry account is required.
- Prefer `uv tool install`; document `pipx install` as an alternative. The installer does not install or authenticate model CLIs.
- Support Windows PowerShell 7 and Linux for this release. Do not claim macOS verification without evidence.
- Preserve the current Codex-only defaults: Sol for planner/build orchestration; Luna for Builder and specialist roles. Invocation from Claude Code or OpenCode does not select a different worker provider.
- Native harness integrations invoke the CLI; they do not replace supervision, perform stages themselves, waive gates, or approve outputs.
- Include the current dashboard build in the reviewed source release. Dashboard installation/startup is optional and must not be required to use the CLI.
- Keep existing scaffold installations usable; no automatic migration or deletion of copied files.

### Maintainer exception

The user's approval authorizes preparing changes to factory packaging, CLI entry points, installer, harness skills, their tests, and documentation. Necessary resource/configuration/state-path changes in `factory.py` and `skillctl.py` are within that scope. Necessary CI packaging checks may be proposed in the implementation plan. This is maintenance of the factory itself, not permission for generated application runs to edit their supervisor.

Only the configured low-tier Builder implements code/tests. Coordination and independent review remain read-only. Do not remove protected-file checks, weaken model routing, lower gates, edit reviewer findings, or alter application-run publication controls. If the supervisor cannot express this scoped maintenance exception safely, report the precise conflict before implementation rather than disabling protection.

The user has authorized a normal push of the verified factory source to `https://github.com/Nexitus/Codex-Software-Factory`. This does not authorize force-push, merging, deployment, registry publication, or changing repository visibility/settings. Framework publication is distinct from application `--publish-pr`.

## Public command contract

These are required future commands, not claims that the current checkout implements them.

| Command | Required behavior |
| --- | --- |
| `software-factory --help` / `--version` | Work without a Git checkout, project config, dashboard dependencies, or provider authentication. |
| `software-factory init --project <repo>` | Create minimal project config and selected harness instructions in an existing checkout; default project is the current checkout root. |
| `software-factory init --harness codex --harness claude --harness opencode` | Select integrations explicitly; without selection initialize all three. Codex covers Desktop and CLI. |
| `software-factory doctor --project <repo>` | Report project/config/gate readiness, executable availability, writable state paths, and actionable failures without invoking a model, running project gates, or exposing credentials. |
| `software-factory run <spec> --project <repo>` | Execute the existing supervised workflow using project-local configuration and evidence storage. |
| `software-factory run --idea "<request>" --project <repo>` | Preserve the existing one-line request flow; exactly one input form is required. |
| `software-factory run <spec> --dry-run` | Preserve existing preflight semantics and document any local evidence/state writes. No provider call or gate execution. |
| `software-factory status --project <repo>` | Read and summarize the latest run and evidence location. An empty project reports no runs, not success or failure. |

`run` retains explicit configuration override and application publication options supported by the supervisor. Resolve user-supplied relative paths against the caller's working directory; resolve project configuration and default state against the selected checkout, never the package installation directory. Paths containing spaces and Unicode must work.

Preserve existing run exit codes: 0 for successful completion/preflight, 2 for blocked or invalid execution, and 130 for interruption. `doctor` returns nonzero when required readiness checks fail. `status` must distinguish preflight, running, interrupted, blocked, verified candidate, missing evidence, and malformed evidence; no directory or partial report alone proves success.

## Installation and project ownership

- Build a wheel and source archive containing every required runtime module, role prompt, policy/schema resource, and approved integration template. Both installed artifacts must work outside the source checkout.
- Use standard packaging and existing helpers; avoid a parallel orchestration implementation or new runtime dependency for argument parsing/path resolution.
- Core CLI execution must not require FastAPI, Uvicorn, Node, or a frontend build. Package any needed standard-library event/lock/process modules with the runtime. Keep web dependencies and dashboard assets optional with documented setup.
- Installed resources are read-only. Write run artifacts, locks, and CLI event storage beneath the target project's ignored `.factory/` directory. Preserve explicit dashboard event-database handoffs, checkout identity, and quarantine behavior.
- Default project config is `<project>/factory.config.json`; an installed package must never accidentally use this factory repository's dashboard gate commands for a consumer project.
- `init` creates configuration that clearly requires project-specific gate setup. It must not guess passing commands or install no-op gates. An unconfigured project is blocked by `doctor` and `run` with remediation.
- `init` never overwrites existing configuration, instructions, application directories, or user edits. Preflight conflicts before writing. Identical managed output is a no-op on repeat; conflicting output produces a nonzero result identifying the paths without partial changes.
- Keep `README.md`, `AGENTS.md`, and `CLAUDE.md` owned by the target project; avoid wholesale concatenation of factory repository instructions. Any needed ignore rule is a narrowly marked, repeat-safe addition.
- Installation and upgrade do not modify consumer repositories automatically. Reinitialization must not silently replace modified integration instructions.

## Harness behavior

Use one maintained workflow body with only the discovery/invocation adaptation each harness needs. Generate project-local skills in documented locations: `.agents/skills/software-factory/` for Codex and `.claude/skills/software-factory/` for Claude Code; OpenCode may reuse its supported agent-compatible location without duplicate definitions.

The skill tells the host to locate the selected checkout, use `doctor` for setup problems, pass the user's request/spec to `software-factory run`, and report actual evidence/status. It must not claim verification from process launch or a model's narrative. Preserve shell-safe argument boundaries; never interpolate request text into an executable shell command. A long or multiline request can be passed through an existing supported spec-file input.

Document exact user invocation for each harness after validating it in the installed version. Discovery paths alone are not evidence that the host can launch the process. Explicitly report permission, authentication, nested-session, or sandbox limitations encountered in real tests. Do not use permission bypass flags to obtain a passing result.

## Affected structure and compatibility

Expected maintenance reaches packaging metadata, a small CLI entry module, runtime/resource lookup in `factory.py` and `skillctl.py`, `install.py`, project templates, harness skill templates, tests, README/setup/architecture/publication documentation, and relevant CI checks. Final file layout belongs in the implementation plan; do not rename unrelated dashboard modules for packaging convenience.

Reuse Python's `argparse`, `pathlib`, existing error handling, and explicit argv process execution. Follow the repository's existing style, for example `project = args.project.resolve()` and `raise SystemExit(main())`. Keep backwards-compatible `python factory.py ...` and `python install.py <repo>` behavior documented and tested. Old scaffold setup can retain its existing layout; new CLI initialization uses the minimal layout above.

`DESIGN.md` already exists at the root. No new visual reference or UI redesign is required for this command-line change.

## Verification and acceptance criteria

| ID | Required outcome | Evidence |
| --- | --- | --- |
| CLI-01 | Wheel and source archive install into clean isolated environments and run from outside the source tree. | Build/install logs, version/help output, packaged-resource checks for both artifacts. |
| CLI-02 | Core CLI works without optional dashboard dependencies. | Clean installation, help/doctor/preflight execution with web packages and Node absent. |
| CLI-03 | Initialization succeeds in an existing checkout, including linked worktrees and paths with spaces/Unicode. | Focused integration tests inspecting generated config and selected skill locations. |
| CLI-04 | Reinitialization is safe, conflicts preserve all existing contents, and invalid targets fail before writes. | Repeat/conflict/invalid-target tests comparing file contents before and after. |
| CLI-05 | Project configuration is selected correctly; missing gates/config/tools block with useful remediation. | Positive and negative doctor/run tests from a foreign working directory and two different target projects. |
| CLI-06 | Installed runtime resolves all prompts, policies, schemas, and skills; no state is written into the installed distribution. | Integration run with read-only installation resources and target-local artifacts/event DB. |
| CLI-07 | Wrapper preserves supervisor arguments, exit codes, model tiers, gates, locks, and quarantine behavior. | Focused forwarding tests plus existing supervisor/backend regression suite. |
| CLI-08 | Status is evidence-based for no runs, preflight, running, interrupted, blocked, valid delivery, and malformed/missing reports. | Fixture-driven status tests. |
| CLI-09 | Claude Code, OpenCode, Codex Desktop, and Codex CLI discover their integration and invoke the installed command. | Actual per-surface invocation transcripts, installed versions, selected project, exit/status, and evidence paths. Mock tests alone do not satisfy this item. |
| CLI-10 | At least one installed-package factory run completes planning, design, build, gates, independent review, and delivery using default Codex routing. | `DELIVERY.json` with `verified_candidate`, matching source revision, green gates and required reviews, and no unresolved blocking findings. |
| CLI-11 | Existing factory/dashboard behavior remains functional. | Python tests, frontend tests, typecheck/build, applicable security checks, and dashboard browser regression evidence. |
| CLI-12 | Windows and Linux package/setup contracts pass. | Platform-specific test/install logs; clearly identify which platforms received live-provider/harness checks. |
| CLI-13 | Current source release is reviewable and safe to publish. | Explicit tracked/untracked file inventory, diff review, credential/generated-artifact exclusion, exact commit ID, and documented remaining limitations. |
| CLI-14 | Verified source is pushed normally to the requested repository and the documented Git-based install works. | Successful push and remote commit check, followed by fresh installation pinned to that commit and help/doctor smoke output. |

Use the existing Python test framework for targeted logic and installed-package integration tests. Record exact command, exit code, platform, source revision, and evidence path; do not treat configured gates as executed gates. Existing failures must be diagnosed and resolved within scope or recorded as release blockers, not skipped or recast as passing.

Expected existing checks include `python -m pytest -q tests`, `npm test -- --run`, `npm run lint`, `npm run build`, `npx playwright test`, and the configured dependency/security checks. The implementation plan must verify their actual availability and define exact artifact build/install commands. Run appropriate checks once per relevant revision; repeat only after changes or unresolved failures justify it.

All CLI-01 through CLI-13 criteria are prerequisites for the push. CLI-14 includes the necessary post-push remote-install smoke check; if it fails, the release remains unqualified until repaired and reverified. No PyPI or GitHub release publication is implied.

## Execution, rollback, and outstanding conditions

Preserve the dirty working tree and review its existing dashboard work before choosing a baseline. Do not stash, reset, discard, or sweep all files into a commit. Use an isolated checkout for Builder work once the intended baseline is established, with no unrelated edits included. Keep the project Impeccable hook enabled and verify its status in that checkout.

Before publication, local rollback is limited to this task's changes. Consumer rollback uses the previous installed version/commit; project initialization does not delete old scaffold files or application data. Do not rewrite published history or remove evidence/state to recover from a failure.

No additional product decision blocks the written spec. Execution conditions still requiring evidence are remote/network access, safe transfer of the existing uncommitted baseline, live Codex authentication/profile access, permission to invoke each harness, and a supervisor-compatible path for the maintainer exception. Treat unavailable checks as blockers to the corresponding readiness claims.

## Documentation references

- Codex skill discovery: https://developers.openai.com/codex/skills
- Claude Code skills: https://code.claude.com/docs/en/skills
- OpenCode skills and compatibility paths: https://opencode.ai/docs/skills/

These sources were inspected during initial design. Verify the installed harness behavior during implementation; documentation is not execution evidence.
