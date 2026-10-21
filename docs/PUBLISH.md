# Publish a verified source revision

The framework repository already exists at [Nexitus/Codex-Software-Factory](https://github.com/Nexitus/Codex-Software-Factory). This guide covers a normal source push of the verified checkout. It does not create a repository, change visibility or settings, reinitialize Git, force-push, merge a pull request, deploy software, or publish to a package registry.

## Before pushing

1. Complete the [CLI verification matrix](consumable-factory-cli-verification.md) with exact commands, exit codes, platform, and source revision. Do not mark a pending contract complete from a specification, template, or local mock alone.
2. Rebuild and install the wheel and sdist-derived wheel from the final source revision in clean environments. Run tests from a foreign working directory with `PYTHONPATH` unset. Verify consumer state is written only under the target checkout.
3. Run the Windows and Linux CI suite. Record any provider or native-host checks separately; source tests do not prove that an installed host can launch the CLI.
4. Review the final tracked and untracked file inventory, the complete diff, generated artifacts, ignored state, and credential exclusions. Confirm only approved source/docs/tests are included.
5. Confirm the target is the existing checkout and its configured remote is the intended repository. Preserve its existing Git history and branch.

Build local artifacts before relying on a source installation:

```powershell
uv build --out-dir .factory/release-artifacts
python -m unittest discover -s tests -p test_distribution.py -v
```

Use a clean environment and foreign working directory for the artifact test. The test builds the wheel and sdist, rebuilds a wheel from the sdist, installs each wheel, and exercises the packaged CLI. Local artifact success is not remote publication evidence.

## Normal source push

After the maintainer has reviewed the concrete final diff and the source commit, push that existing commit to the intended branch of the configured origin using the normal Git workflow. Do not create or replace the repository, rewrite history, or push an unverified working tree. Record the pushed commit SHA and verify the remote branch points to it. Do not stage generated or ignored run state.

This source push does not merge a PR, change repository visibility/settings, publish a Python package, or deploy an application. A later maintainer release step should select an exact commit SHA only after the remote source and its evidence are verified.

## Install from an exact commit

After the normal push, install only from its verified commit:

```sh
uv tool install "git+https://github.com/Nexitus/Codex-Software-Factory.git@<verified-commit>"
```

Or use pipx:

```sh
pipx install "git+https://github.com/Nexitus/Codex-Software-Factory.git@<verified-commit>"
```

Replace the placeholder with the verified SHA; never publish it literally. Confirm `software-factory --version` and `software-factory --help` from a foreign directory. Then initialize a disposable Git project, configure real gates, run `software-factory doctor` and a dry run, and inspect `software-factory status`. The current Windows artifact suite exercises this lifecycle from the direct wheel and sdist-derived wheel. Installation must not change the target checkout until the operator explicitly runs `init`.

## Upgrade and rollback

The CLI does not update itself or consumer projects. Move to a new release by explicitly uninstalling and reinstalling from the new verified commit. For uv:

```sh
uv tool uninstall codex-software-factory
uv tool install "git+https://github.com/Nexitus/Codex-Software-Factory.git@<new-verified-commit>"
```

For pipx:

```sh
pipx uninstall codex-software-factory
pipx install "git+https://github.com/Nexitus/Codex-Software-Factory.git@<new-verified-commit>"
```

To roll back, repeat the install using the prior verified commit SHA. Existing consumer config, skills, source, and run evidence remain under their project checkouts. Review upgrade compatibility and do not reinitialize a project as an upgrade mechanism.

## Release limits

The first-release routing is Codex-only: GPT Sol for planner/build orchestration and GPT Luna for Builder/specialists. The CLI does not install or authenticate the host. Claude Code and OpenCode templates remain present but explicitly unverified; do not describe them as supported live integrations until separate host evidence exists.

Only Windows PowerShell 7 and Linux are in the release target. Do not claim macOS support without evidence. The package CLI does not require the optional FastAPI dashboard or Node build. Dashboard qualification is recorded separately from CLI package qualification.
