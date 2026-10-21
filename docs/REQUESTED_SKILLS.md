# Requested Skill Integration — v0.3

Date: 2026-10-20. Source refs, license metadata, roles, activation conditions and pinned blob IDs: [`skills/registry.json`](../skills/registry.json). **No third-party scripts are executed automatically.**

## User-specified role assignments

| Source | Role/phase | Mode | Activation | Capability provided |
|---|---|---|---|---|
| [UI UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | UI: design/review; UX: design/review | Native SKILL.md | Each UI-affecting task | Design-system decisions; UX guidance; accessibility and responsiveness |
| [Emil Kowalski Skills](https://github.com/emilkowalski/skills) | UI: design/review | Native SKILL.md | Each UI-affecting task | Design engineering and interaction quality (`emil-design-eng`) |
| Same | UI: design/review | Native SKILL.md | Only requests concerning motion | `animate` / `review-animations` |
| Same | Testing, UX: design/review | Native SKILL.md | UI-affecting work | `break-ui`: realistic overflow/empty/edge data test patterns |
| [Screenshot-to-Code](https://github.com/abi/screenshot-to-code) | UI: design; Testing: review | **External app**, not SKILL.md | Reference image supplied and separately provisioned | Screenshot → UI code candidate; screenshots used as comparison artifacts, not as an oracle |
| [Graphify](https://github.com/Graphify-Labs/graphify) | Planner: plan | SKILL.md + **optional external `graphifyy` CLI** | Existing-codebase task | Component relationships, references, impact analysis |
| [Ponytail](https://github.com/dietrichgebert/ponytail) | Planner: plan | Native SKILL.md | All planning tasks | Minimal complete scope, avoid unnecessary code/dependencies |

**Screenshot-to-Code** has a React/Vite frontend and FastAPI backend, and requires at least one model-provider credential to run. It is not activated by copying a `SKILL.md`. Future support requires a configured isolated service, an API/WebSocket adapter and test coverage. Until the adapter exists, the factory uses standard browser screenshots and Playwright/visual-test tooling for independent visual quality checks. Do not claim Screenshot-to-Code executed when it did not.

**Graphify** ships `graphify/skill.md` and a Python CLI. Its guidance can be read by Planner once pinned and staged. Creating a fresh AST graph requires separately installing and running `graphifyy` in a supervised preflight worker, placing its output under `.factory/runs/<id>/evidence/graphify/` and passing paths to Planner. The current runtime does **not** run Graphify automatically. The package's claimed improvements in token use are not treated as verified benchmarks.

**Ponytail** optimizes code scope, not output coverage. Acceptance criteria, security, accessibility, deterministic gates and functionality outrank brevity. If its upstream instructions ask for a different output format, JSON-schema review contracts win.

## Current implementation and limitations

- `skillctl.py` stages the pinned prompt skills into `.factory/skills/<id>` using Git and writes a content-digest lock under `skills/lock.json`. No dependency installers or upstream scripts are executed.
- `factory.py` chooses prompt skills deterministically by role/phase and limited scope signals, validates installed content and injects a bounded excerpt into **Codex and Claude Code** prompts. Referenced assets are staged with their parent skill trees.
- Default `skills.enabled=false`: user explicitly stages and audits sources, commits generated `skills/lock.json` and opts in. When enabled, a missing/tampered selected skill blocks the run.
- `claude --bare` project skill discovery is not relied upon; role skills are carried in the structured prompt.
- The supervisor's read-only vs writable permissions remain defined by the CLI execution adapter. The local runtime is **not** an OS isolation sandbox.
- Optional external tools (Screenshot-to-Code, Graphify graph-building) are **declared, not operationally wired**. A Python registration is not the same as running the tool.
- Skill trees may include relative scripts and other assets. They remain inert unless a human separately audits and permits specific tools.

## Setup

After installing the factory scaffold into an application Git checkout and reviewing the upstream source/license/behavior:

```bash
python skillctl.py list
python skillctl.py install
python skillctl.py validate
# Review generated skills/lock.json and staged .factory/skills/* assets.
# Edit factory.config.json: set skills.enabled = true.
git add skillctl.py skills factory.py factory.config.json
git commit -m "Configure pinned role skills"
```

Then configure real project test/lint/security/build (and, for UI work, E2E) commands before launching the factory. Installing skills does **not** make empty gate configurations acceptable.

To upgrade: review upstream diff and new source commit/blob hashes; edit the registry pins; run `python skillctl.py install --refresh`, validate and commit the new lock. Never follow unpinned `main` at runtime.

## Next steps

1. Implement external Screenshot-to-Code service adapter and separate source/screenshot capture worker.
2. Implement supervised Graphify AST preflight that executes only on an isolated filesystem snapshot and has no write access to source.
3. Add explicit skill-selection audit to the top-level run manifest, not just each per-agent `skills.json`.
4. Benchmark variants with and without optional motion, review and adversarial skills.
5. Add OS-level sandbox controls, including egress policy and access to untrusted skill scripts.

See [Foundational Loop Skill Scan](FOUNDATIONAL_LOOP_SKILL_SCAN.md) for additional high-value selections from alirezarezvani/claude-skills.
