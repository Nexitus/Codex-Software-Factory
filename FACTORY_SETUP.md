# Factory setup

Use the installed CLI to initialize an existing Git checkout. The CLI does not copy the factory application, dashboard, or gate scripts into a consumer project.

## Prerequisites

- Python 3.10 or newer and Git.
- All first-release worker roles use the `codex` executable on `PATH` and Codex authentication, even when the interactive host is Codex Desktop. Install and authenticate Codex CLI separately; the factory installer does not set this up.
- Real, project-specific gate commands and their tools.
- Windows PowerShell 7 or Linux for the initial support target. macOS has not been verified.

For unattended runs, use an ephemeral VM or container without production credentials and with restricted network access. The supervisor runs local processes; it does not provide OS isolation.

## Install a pinned source revision

Install from the existing [Nexitus/Codex-Software-Factory](https://github.com/Nexitus/Codex-Software-Factory) repository using the exact commit selected by the maintainer after qualification:

See the official [uv tool guide](https://docs.astral.sh/uv/guides/tools/) and [pipx guide](https://pipx.pypa.io/stable/) for their supported Git-source install options.

```sh
uv tool install "git+https://github.com/Nexitus/Codex-Software-Factory.git@<verified-commit>"
```

Or use pipx:

```sh
pipx install "git+https://github.com/Nexitus/Codex-Software-Factory.git@<verified-commit>"
```

The placeholder is not a usable revision and these commands do not claim that the remote commit has been published. For pre-publication checks, build and install the local wheel in an isolated environment. Installation does not add or modify files in a project checkout.

## Initialize a project

The target must already be a Git checkout. Select the adapter you will use:

```powershell
software-factory init --project "C:\work\my-project" --harness codex
```

On Linux, pass the corresponding absolute or relative checkout path. Omit `--harness` to initialize all supported templates, or repeat it to select multiple templates. Codex Desktop and Codex CLI discover the same `.agents/skills/software-factory/SKILL.md`. The other retained templates are `.claude/skills/software-factory/SKILL.md` for Claude Code and the agent-compatible `.agents/skills/software-factory/SKILL.md` path for OpenCode. Template inclusion is not live host qualification; only Codex is in scope for the first release, while Claude Code and OpenCode remain unverified.

Initialization writes `factory.config.json`, selected skill instructions, and a narrow marked `.factory/` ignore entry when needed. It does not create the `.factory/` state directory or copy the factory/dashboard into the target. Existing project files and a differing config are preserved; review the result before using it. Do not paste user request text into shell code. Pass it as a CLI argument or use a committed spec file for multiline requirements.

## Existing scaffold installations

Existing projects that already received the legacy scaffold remain usable. `python install.py <repo>` retains that older installation workflow; the installed CLI's `init` does not migrate, replace, or delete scaffold files. Review the project before combining the two layouts, and do not treat legacy scaffold installation as installed-package qualification.

## Recover from setup problems

- **Missing gate commands or an unready config:** `init` creates empty command lists for all required gates. Edit `factory.config.json` with real argv commands for every required gate, install the project tools, commit the config, and run `software-factory doctor --project "/path/to/my-project"` to check local readiness. Do not add no-op commands.
- **Invalid or conflicting project files:** preserve existing project files, review the reported paths, and correct the project config or integration file deliberately. Re-run `init` only after conflicts are resolved; it is not an upgrade command.
- **Missing Codex CLI or host authentication:** install and authenticate the host using its own documented setup. The factory installer does not install the host, read credential files, or authenticate it. `doctor` checks local readiness only and does not prove provider access.
### Windows uv permission workaround

On the tested Windows host, uv's managed-Python launcher could not start in the normal Codex CLI workspace, and installing from a `.codex` worktree failed with `Permission denied`. Using an accessible installed system Python, copy mode, and uv tool directories outside `.codex` worked. For example, in PowerShell (replace the Python path with one installed and accessible to your host):

```powershell
$env:UV_TOOL_DIR = Join-Path $env:LOCALAPPDATA 'uv-tools'
$env:UV_TOOL_BIN_DIR = Join-Path $env:LOCALAPPDATA 'uv-bin'
uv tool install --python "C:\Program Files\Python314\python.exe" --link-mode copy "git+https://github.com/Nexitus/Codex-Software-Factory.git@<verified-commit>"
$env:PATH = "$env:UV_TOOL_BIN_DIR;$env:PATH"
```

The command uses only the current PowerShell session's environment. The tested setup used a tool environment outside `.codex`; the example is specific to this failure mode and is not required on every Windows installation. It does not change global ACLs or bypass sandbox permissions. `uv tool dir` and `uv tool dir --bin` show the selected locations; see uv's [storage reference](https://docs.astral.sh/uv/reference/storage/) for `UV_TOOL_DIR` and `UV_TOOL_BIN_DIR`.

- **CLI not found after `uv tool install`:** run `uv tool update-shell`, then open a new terminal or restart Codex Desktop so it sees the updated `PATH`. This changes the user shell configuration only when the operator runs it.
- **Skill not visible in Codex:** Codex detects skill changes automatically. If `.agents/skills/software-factory/SKILL.md` is still missing from the selector after project initialization, restart Codex and verify the checkout is open.
- **Generated files:** `init` writes `factory.config.json`, the selected host skill file(s), and a marked `.factory/` ignore block only when that state directory is not already ignored. Run state is created later under `.factory/`; generated configuration and skills remain in the consumer checkout.

## Configure gates and run

The generated config has empty commands and keeps the four required gates: tests, lint, security, and build. Merge only the `commands` entries below into the generated `factory.config.json`; preserve its existing provider/model routing, limits, required gate list, and other fields. Install Ruff as a development tool for the project.

```text
"commands": {
  "tests": [["python", "-m", "unittest", "discover", "-s", "tests"]],
  "lint": [["ruff", "check", "src", "tests"]],
  "security": [["ruff", "check", "--select", "S", "src", "tests"]],
  "build": [["python", "-m", "compileall", "-q", "src"]]
}
```

Adapt the command paths and tools to the project, but keep each required gate meaningful; do not remove a gate just to make readiness pass. The Ruff security rules are a source-code check, not a dependency audit. Configure a real UI end-to-end gate when the project requires UI verification. Commit the configuration and initial project files so the checkout is clean before starting a run.
The intended sequence is:

```sh
software-factory doctor --project "/path/to/my-project"
software-factory run --idea "Implement the requested change" --project "/path/to/my-project" --dry-run
software-factory run specs/my-feature.md --project "/path/to/my-project"
software-factory status --project "/path/to/my-project"
```

`doctor` and `status` are implemented. The Windows artifact suite exercises unready and ready doctor results, empty status, and status after a consumer dry run from both the direct wheel and sdist-derived wheel. The verification matrix records current Windows Codex CLI and Desktop smoke checks plus the separate live-pipeline state. The native smoke commands stopped at preflight; they do not prove provider access or a verified candidate. A dry run checks local preflight and writes run/event state but does not invoke models or project gates. A normal run uses the existing supervisor, configured routing and gates, and independent review flow. Run reports and CLI state are stored beneath the target checkout's ignored `.factory/` directory.

A `verified_candidate` result is evidence that configured gates and required reviews passed. It does not mean the work is approved, merged, deployed, or guaranteed defect-free. The run does not update consumer projects automatically.

## Host invocation instructions

Initialization creates instructions for the selected hosts. Windows smoke checks confirmed automatic skill discovery and CLI invocation in Codex CLI, and invocation in Codex Desktop after an explicit skill-read prompt; `doctor`, dry-run, and `status` returned exit 0 on both. These commands remained at preflight and do not prove provider access or a completed run. Desktop automatic picker/discovery UI behavior remains unverified. Claude Code and OpenCode templates are retained but explicitly unverified; their presence does not make them supported live hosts for the Codex-only release.

| Host | Project setup and invocation |
| --- | --- |
| Codex Desktop | Open the initialized checkout in Codex Desktop. In the prompt, ask it to read `.agents/skills/software-factory/SKILL.md`, then describe the request. |
| Codex CLI | Start `codex` from the initialized checkout, then invoke `$software-factory` with the request in the prompt. |
| Claude Code | Start `claude` from the initialized checkout. The retained `.claude/skills/software-factory/SKILL.md` describes the intended `/software-factory` invocation; host discovery and execution remain unverified. |
| OpenCode | Start `opencode` from the initialized checkout and ask it in natural language to use the `software-factory` skill for the request. This is an unverified prompting example, not a confirmed native command or live integration. |

Use a spec file for a long or multiline request rather than placing request text in executable shell code. Confirm the host loaded `.agents/skills/software-factory/SKILL.md` or `.claude/skills/software-factory/SKILL.md` before requesting a run. After a Codex invocation, verify the CLI's exit code and actual run evidence; the host's narrative is not proof of a candidate. The interactive host loads a skill and invokes the CLI; the supervisor then uses the separate provider/model routing in `factory.config.json`. For this first release, both sides use Codex. Host discovery does not certify the worker routing or a run result. For Codex, see the current [official skills documentation](https://learn.chatgpt.com/docs/build-skills). Claude Code and OpenCode references are included for their retained templates only; neither host is live-qualified for this release. The verification matrix records which invocations have actually been tested.

## Optional dashboard from source

The dashboard remains optional and is not a runtime dependency of the installed CLI. From a source checkout, use the project's Python requirements and frontend lockfile. Node.js 20.19+ or 22.12+ is required by the pinned Vite 8 toolchain:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm ci
npm run build
.\start-dashboard.ps1 -Demo
```

For Linux, substitute `.venv/bin/python` and start with `sh start-dashboard.sh --demo`. Demo mode uses synthetic events and never calls a provider. Live dashboard runs require an operator-managed `dashboard.projects.json` and use the same supervisor as the CLI. See [architecture](docs/ARCHITECTURE.md) for local security boundaries and limits.
