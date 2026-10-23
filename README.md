# Codex Software Factory

A local Python CLI and optional event-backed dashboard for a supervised software-development workflow. The deterministic supervisor routes planning, design, implementation, configured gates, and independent reviews, then reports a verified candidate or a blocked run. A passing result means only that configured checks and reviews passed.

> **Qualification status:** Installed-wheel run `20261023T000421478604Z` qualified runtime source `20e13a85348578b7aa35f5cc4862be2e2b0b2595` with wheel SHA-256 `4c29dcd3bff208e6c48fb7eaa02686b4f4a3ba401bc843efd0d19a6ba582cc90`. It produced `verified_candidate` after one review round: all four configured gates exited 0, all three independent reviews passed with zero findings, and the final blocker list was empty. Installed `status` exited 0 for run `488ea0ad-450e-439a-b0ce-92b123c033e1` and matched the delivery path. This disposable Windows fixture used the one-time user-approved host exception; it does not establish OS/network isolation or unattended security. The earlier source-475 candidate and two blocked attempts remain historical evidence. Native Codex execution on Linux, Claude Code, and OpenCode remain unqualified.
>
> Hosted CI run `39875562260` passed on Windows and Ubuntu for test-only commit `379ab47125a7ba15b0c006c3c5b94e300f9dfc5c`. The role-qualified source `20e13a85348578b7aa35f5cc4862be2e2b0b2595` passed its 111-test Windows and Linux suites and the installed fixture pipeline. The source/docs commit is not yet pushed; final documentation review, CI for the final pushed revision, and a fresh commit-pinned remote install remain pending.
>
> The copy-ready install commands below are pinned to the exact runtime-qualified commit `20e13a85348578b7aa35f5cc4862be2e2b0b2595`. The one-time fixture host exception remains limited to that disposable qualification, and the final remote install has not yet been verified. No tagged GitHub or package-registry release has been published. See the [revision-bound verification matrix](docs/consumable-factory-cli-verification.md) for evidence and limits.

## Install

Install the runtime-qualified source commit from the existing [Nexitus/Codex-Software-Factory](https://github.com/Nexitus/Codex-Software-Factory). Commit `20e13a85348578b7aa35f5cc4862be2e2b0b2595` is not pushed yet, so these Git commands become fetchable after the pending normal push:

```sh
uv tool install --python python --link-mode copy "git+https://github.com/Nexitus/Codex-Software-Factory.git@20e13a85348578b7aa35f5cc4862be2e2b0b2595"
```

On the tested Windows host, `python` resolved to the accessible system interpreter at `C:\Program Files\Python314\python.exe`; the uv managed-Python launcher failed, and installing under `.codex` worktrees returned `Permission denied`. Selecting the system interpreter and `--link-mode copy`, with uv's tool environment outside `.codex`, worked. This is a tested machine-specific workaround, not a requirement for every machine; it did not change global permissions or bypass the sandbox. See [Windows uv troubleshooting](FACTORY_SETUP.md#windows-uv-permission-workaround).

Linux can use uv with its installed Python on PATH:

```sh
uv tool install --python python3 --link-mode copy "git+https://github.com/Nexitus/Codex-Software-Factory.git@20e13a85348578b7aa35f5cc4862be2e2b0b2595"
```

The uv commands above pin the exact fixture-qualified runtime source `20e13a85348578b7aa35f5cc4862be2e2b0b2595`; a fresh remote install from this revision remains to be verified after the normal push.

`pipx` is an alternative, but it was not exercised by this runtime qualification. After the normal push, install the same exact source revision with:

```sh
pipx install "git+https://github.com/Nexitus/Codex-Software-Factory.git@20e13a85348578b7aa35f5cc4862be2e2b0b2595"
```

See the [publication checklist](docs/PUBLISH.md) for the remaining push and remote verification steps.

The role-qualified wheel and source archive were built from commit `20e13a85348578b7aa35f5cc4862be2e2b0b2595`; the wheel passed the full installed fixture pipeline, and Windows/Linux each passed 111 source tests. Their SHA-256 values and the exact run evidence are in the [revision-bound verification matrix](docs/consumable-factory-cli-verification.md). The older fresh remote install at 19939337 remains historical; the final push, hosted CI, and fresh remote install for this source are pending.

The CLI does not install or authenticate any coding CLI. Python 3.10+ and Git are required. The first release targets Windows PowerShell 7 and Linux; macOS is not qualified.

## Initialize and run an existing project

Start with an existing Git checkout and select Codex explicitly for the first release:

```powershell
software-factory init --project "C:\work\my-project" --harness codex
```

Without `--harness`, initialization selects all current adapters. Codex Desktop and Codex CLI use `.agents/skills/software-factory/SKILL.md`. Claude Code and OpenCode templates are included for future testing; those hosts are not live-qualified. Initialization writes minimal project configuration and selected skill files. It does not copy the factory or dashboard into the project or overwrite an existing config.

Merge real project commands into each required gate's empty command list in `factory.config.json`; keep the generated required-gate list and configure a meaningful command for every gate. If a project lacks a standard tool, select a real equivalent check; do not remove a gate or weaken it just to make readiness pass. Configure UI end-to-end checks for UI projects.

Commit the project configuration and other initial changes, then follow this intended operator sequence:

```sh
software-factory doctor --project "/path/to/my-project"
software-factory run --idea "Add an accessible settings page with validation and tests" --project "/path/to/my-project" --dry-run
software-factory run --idea "Add an accessible settings page with validation and tests" --project "/path/to/my-project"
software-factory status --project "/path/to/my-project"
```

`doctor` checks local readiness, and `status` reports saved run evidence. Both commands are implemented in the CLI. The Windows wheel and sdist-derived-wheel artifact tests exercise the installed lifecycle; consult the verification matrix for the exact evidence and remaining limits. Dry run performs local preflight and writes run/event evidence; it does not call a provider or run project gates. A normal run may invoke configured agents and project commands.

Runs and local state live under the selected checkout's ignored `.factory/` directory. Inspect reports, gate logs, the source diff, and delivery evidence. `verified_candidate` means configured gates and required reviews passed; it is not proof that the result is defect-free, approved for release, merged, or deployed. The CLI never updates consumer projects automatically.

Harness instructions pass requests as arguments or spec files through the CLI; they do not interpolate request text into executable shell code. Factory workers must not recursively launch the factory. Use a committed spec file for long or multiline requests.

## Use Codex Desktop or Codex CLI

After initializing a project with `--harness codex`, the generated skill is at `.agents/skills/software-factory/SKILL.md`. These prompts use only local readiness and dry-run commands; a dry run does not call a provider or execute project gates.

In Codex CLI, the smoke check confirmed automatic discovery and reading of the generated skill. From the initialized project checkout, enter a prompt such as:

```text
$software-factory
Run `software-factory doctor --project .`, then `software-factory run requirements.md --project . --dry-run`, then `software-factory status --project .`. Report each exit code and the run ID.
```

In Codex Desktop, the tested method asked the chat to read the generated skill explicitly before running the same commands:

```text
Read `.agents/skills/software-factory/SKILL.md` from this checkout. Then run `software-factory doctor --project .`, `software-factory run requirements.md --project . --dry-run`, and `software-factory status --project .`. Report each exit code and the run ID.
```

The Desktop smoke used an explicit skill-read prompt. Automatic skill-picker or discovery UI behavior has not been verified. See the [native qualification evidence](docs/consumable-factory-cli-verification.md#evidence-reports).

## Optional local dashboard

The dashboard is a source-checkout feature, not a CLI package requirement. A fresh checkout needs Python 3.10+ and Node.js 20.19+ or 22.12+ for the pinned Vite 8 build.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm ci
npm run build
.\start-dashboard.ps1 -Demo
```

On Linux, use `python3 -m venv .venv`, `.venv/bin/python -m pip install -r requirements.txt`, `npm ci`, `npm run build`, then `sh start-dashboard.sh --demo`. The dashboard binds to `127.0.0.1` on port 8765 by default. Demo mode is synthetic and never invokes a provider. Live use needs an operator-managed `dashboard.projects.json`; see [architecture and limits](docs/ARCHITECTURE.md).

## Safety and limits

The supervisor runs processes locally and is not an OS sandbox. Treat project code, dependencies, tests, and repository instructions as untrusted. Use an ephemeral VM or container with no production credentials and restricted network access for unattended work. A process launch or model narrative is not verification; require gate and review evidence in the run report. The optional `--publish-pr` path requires explicit invocation and does not merge or deploy.

See [setup details](FACTORY_SETUP.md), [architecture](docs/ARCHITECTURE.md), [publication and upgrade guidance](docs/PUBLISH.md), and [CLI verification evidence](docs/consumable-factory-cli-verification.md).

## Development checks

```sh
python -m py_compile factory.py install.py
python -m unittest discover -s tests -v
```

CI runs the suite on Windows and Linux and installs `uv` for wheel/sdist tests. The tests mock coding CLIs; they do not authenticate to providers or qualify live agent behavior.

## License

MIT. See [LICENSE](LICENSE).
