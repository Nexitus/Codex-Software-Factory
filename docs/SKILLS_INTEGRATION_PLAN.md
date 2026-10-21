# Update (v0.3): requested skills catalogued and opt-in prompt activation implemented

See [Requested Skills](REQUESTED_SKILLS.md), [Foundational Loop Skill Scan](FOUNDATIONAL_LOOP_SKILL_SCAN.md), and `skills/registry.json`. **The original v0.2 plan follows for longer-term hardening; some planned items are still incomplete.**

---

# Role-aware skills integration plan (v0.2 proposal)

**Status:** Proposed; **not implemented in the v0.1 runtime**.  
**Prepared:** 2026-10-20.  
**Target:** Software Factory running Codex CLI and Claude Code CLI.  
**Operating contract:** human enters one requirement; supervisor returns a verified candidate or a blocked delivery report. No intermediate interactive approval, no auto-merge, no autonomous production deployment.

## 1. Decision

Ship a **version-locked, reviewed skill registry** with per-role activation. Do not globally install all of Superpowers, BMAD, Anthropic Skills, Codex plugins, Vercel skills, and security plugins into every worker. Skill adoption is an optimization to be independently evaluated, not proof of correctness.

- One canonical `SKILL.md`-based source format, with assets and references intact.
- Codex adapter to `.agents/skills/` or explicit role-specific skill invocation.
- Claude Code adapter to an **explicit vetted plugin directory / prompt bundle** because current `claude --bare` runs intentionally skip ambient `.claude/skills/` discovery.
- Human/configured supervisor policy overrides instructions in any imported skill. Imported skills **never** authorize themselves to acquire broader tools, alter quality gates, change approval policy, install additional skills, push, merge, or deploy.
- Planner, architecture, security, testing, UI and UX reviewers remain read-only. Only Builder may edit implementation/test files. Executable gates and browser automation run in an independently controlled test worker and deliver artifacts to reviewers.
- Retain reproducibility with SHA-pinned upstream sources, hashes, license notices, signed/auditable approvals and exact per-run skill IDs in the run manifest.

## 2. Curated shortlist, by role

The selections below balance ecosystem popularity, publisher credibility, direct role fit and compatibility. They are **candidates**, not automatic approvals; each must pass the audit and evaluations in sections 5 and 8.

| Factory agent | Default candidates | Conditional candidates | Adaptation / exclusion |
|---|---|---|---|
| **Planner** | `obra/superpowers:brainstorming`, `obra/superpowers:writing-plans` | BMAD Method spec/acceptance-criteria *patterns* (do not import the entire agent runtime) | Existing skill instructions may ask a human to approve a plan or write files. Override with unattended, structured output and explicit conservative assumptions. |
| **Architecture design/review** | `mattpocock/skills:codebase-design` | `mattpocock/skills:domain-modeling`, `improve-codebase-architecture` only after adaptation | Some skills write glossaries, require extra sub-skills, create HTML, or ask users to choose options; the reviewer may **only report** architecture findings. |
| **Builder** | `obra/superpowers:test-driven-development`, `obra/superpowers:systematic-debugging` | `vercel-labs/agent-skills:vercel-react-best-practices` for React/Next.js; relevant first-party platform/framework skill for detected stack | Avoid duplicate TDD methodologies. Preserve test-first behavior without unbounded loops or user prompts. |
| **Testing design/review** | `obra/superpowers:verification-before-completion`; `trailofbits/skills:property-based-testing` where invariant testing fits | `anthropics/skills:webapp-testing` for web apps; `openai/skills:playwright` for browser exploration if legacy skill is approved | Review-only agents cannot write tests or execute shell commands. Builder writes tests; external gate executes them; Test reviewer inspects logs, coverage, traces and the diff. |
| **UI design/review** | `anthropics/skills:frontend-design` | **Choose one**: `pbakaus/impeccable` or `nextlevelbuilder/ui-ux-pro-max-skill`; optional stack-specific component skill | UI reviewer receives viewport screenshots, DOM/snapshots and design targets. Do not run multiple competing visual-style frameworks by default. |
| **UX design/review** | `vercel-labs/agent-skills:web-design-guidelines`, `wshobson/agents:wcag-audit-patterns` | `openai/plugins:product-design/audit` *only if* plugin prerequisites are met | Pin Vercel's remotely fetched guideline content for reproducible review. Accessibility claims require browser/assistive-tech evidence, not source alone. |
| **Security design/review** | `trailofbits/skills:differential-review`, first-party Codex Security `threat-model` **methodology** | Codex Security `security-diff-scan` when the plugin and required tools are available; Trail of Bits `semgrep` and `supply-chain-risk-auditor` as tooling/gate guidance | The official Codex Security skill depends on plugin references and optional MCP actions. Do not copy the standalone `SKILL.md` and assume full functionality. Run Semgrep/dependency/secrets scanners as **deterministic gates**, not a reviewer's self-report. |

**Supervisor:** intentionally has no imported swarm/orchestration skill. The Python state machine remains authoritative. Agent libraries such as Oh My Claude Code, Ralph and BMAD are architectural references, not nested supervisors.

### Provenance and compatibility notes

- Superpowers: https://github.com/obra/superpowers/tree/main/skills
- Anthropic Skills: https://github.com/anthropics/skills/tree/main/skills
- Vercel Agent Skills: https://github.com/vercel-labs/agent-skills/tree/main/skills
- Matt Pocock engineering skills: https://github.com/mattpocock/skills/tree/main/skills/engineering
- Impeccable: https://github.com/pbakaus/impeccable
- UI UX Pro Max: https://github.com/nextlevelbuilder/ui-ux-pro-max-skill
- Trail of Bits Skills: https://github.com/trailofbits/skills
- Codex Security plugin: https://github.com/openai/plugins/tree/main/plugins/codex-security
- Wshobson WCAG audit patterns: https://github.com/wshobson/agents/tree/main/plugins/accessibility-compliance
- skills.sh installation popularity (not a quality measure): https://skills.sh/
- OpenAI older `openai/skills` catalog is explicitly deprecated in favor of `openai/plugins`; treat any use of legacy `playwright` or security skills as a conscious exception, and evaluate maintained alternatives.

## 3. Planned repository changes

```text
agentic-software-factory/
├── skills/
│   ├── registry.json              # Approved skills, source paths, pinned SHAs, phases and tool grants
│   ├── lock.json                  # Exact source commit + vendored-content hashes
│   ├── sources/                   # Approved, vendored upstream skill packages (licenses intact)
│   └── adapters/                  # Small local wrappers; never re-write upstream on fetch
├── factory/
│   ├── skill_registry.py          # Manifest validation; rejects unknown/unsigned/unpinned skills
│   ├── skill_selector.py          # Deterministic role/phase/stack/risk selection
│   ├── skill_loader.py            # Provider adapters; per-invocation capability isolation
│   └── skill_audit.py             # Integrity, permission, instruction-injection and license review
├── .agents/skills/                # Generated Codex-facing approved project skills
├── .claude/skills/                # Generated Claude-facing approved project skills (interactive mode)
├── tests/skills/                  # Fixtures, adapter tests, security tests and role evals
└── docs/SKILLS_INTEGRATION_PLAN.md
```

**Do not create dynamic skill directories inside an untrusted code checkout and let a model execute them.** Stage vendor assets outside the target tree or in a supervisor-owned read-only area, publish approved material atomically, and verify its hash again immediately before execution.

### Existing scaffold changes required

1. `factory.config.json`: define `skills.enabled`, per-role skill IDs, per-phase activation, stack auto-detection, optional paths, maximum skill bytes/tokens, tool capabilities and total run budget. No unrestricted per-role imports.
2. `factory.py/get_prompt(...)`: provide **the selected skill manifest** plus explicit invocation instructions. Build a per-invocation session; do not hope that skills self-select from a global inventory.
3. `factory.py/execute_agent(...)`: for Codex, present only selected trusted `.agents/skills` (prefer disposable job workspace/home with a controlled skill root). For Claude `--bare`, use a **trusted per-run `--plugin-dir`** or explicit skill instructions with all required references. Test this with the actual installed Claude CLI version; do not silently switch off `--bare`.
4. `PROTECTED`/`protected_snapshot`: cover `skills/`, generated skill indexes, skill manifests, policy, and adapters; verify *all* governed files including new files and symlinks cannot change during a run.
5. `do_work(...)`: select at each phase, re-evaluate selection for repair rounds when changed stack/risk warrants, but never expand capability permissions mid-run. Record skill selection, versions, hashes, token budgets and invoked checks in `.factory/runs/<id>/manifest.json`.
6. Quality gates: browser worker captures real screenshot/trace/console/network/a11y evidence for UI/UX, SAST/dependency/secret scanning for security, test/coverage/mutation artifacts for Testing. Model reviewers inspect **evidence**; they do not certify checks that did not run.
7. Structured outputs remain unchanged at first. Add optional `skill_evidence: [{id, version, evidence_paths}]` in a future schema migration, validated separately by the supervisor.
8. Ensure paths work on Windows/macOS/Linux: do not depend exclusively on symlinks; prefer staged copies or generated manifests with checksum tests.

## 4. Example activation policy (illustrative, not an executable current config)

```json
{
  "skills": {
    "enabled": true,
    "mode": "pinned-and-allowlisted",
    "max_per_invocation": 3,
    "roles": {
      "planner": {"plan": ["superpowers-brainstorming", "superpowers-writing-plans"]},
      "architecture": {"design": ["codebase-design"], "review": ["codebase-design"]},
      "builder": {"build": ["superpowers-tdd", "superpowers-systematic-debugging"], "repair": ["superpowers-systematic-debugging", "superpowers-tdd"]},
      "testing": {"design": ["property-based-testing"], "review": ["verification-before-completion"]},
      "ui": {"design": ["frontend-design"], "review": ["impeccable"]},
      "ux": {"design": ["web-design-guidelines"], "review": ["web-design-guidelines", "wcag-audit-patterns"]},
      "security": {"design": ["threat-model-methodology"], "review": ["differential-review"]}
    },
    "conditionals": [
      {"when": {"framework_any": ["react", "nextjs"], "roles": ["builder"]}, "add": ["vercel-react-best-practices"]},
      {"when": {"ui_change": true, "roles": ["testing"]}, "add": ["webapp-testing"]},
      {"when": {"has_browser_evidence": false, "roles": ["ui", "ux"]}, "action": "block_visual_signoff"}
    ]
  }
}
```

Actual `registry.json` entries must include: `id`, `canonical_name`, `upstream_url`, `source_path`, `commit_sha`, `content_sha256`, `license`, `approved_by`, `approved_at`, `applicable_roles`, `phases`, `stack_triggers`, `required_tools`, `required_files`, `prompt_size_budget`, `network_access`, `script_execution`, `adaptor`, `eval_suite`, `status`.

**No auto-discovery from skills.sh at runtime.** Popularity lists are a discovery input to the human-reviewed update pipeline, not a way to grant execution to arbitrary GitHub source.

## 5. Skill intake, approval and update process

1. **Discover:** record repo, exact subdirectory, popularity, maintainers, recent changes and alternative implementations.
2. **Acquire:** check out **an immutable commit SHA**; verify file hashes; collect licenses for every skill and bundled asset (repo-wide license alone may be insufficient).
3. **Audit instructions:** flag user prompt/approval requirements, attempts to edit governance, network access, shell execution, secrets handling, arbitrary downloads, privilege escalation, Git push/deploy steps, and instruction conflicts.
4. **Classify:** (a) portable prompt-only, (b) portable with references/scripts, (c) plugin/tool-dependent. Third-party executables are denied by default.
5. **Adapt:** use a supervisor-maintained wrapper; preserve upstream text and license notices. Avoid claiming an adapted skill is the exact upstream behavior.
6. **Evaluate:** compare with the current role baseline using a held-out benchmark: quality, regression rate, unresolved findings, tokens, runtime and dollar cost.
7. **Approve:** add immutable source/hash and owner approval to registry; run the suite and archive evidence.
8. **Update:** scheduled proposal opens a review PR with changelog/diff/SBOM and evaluation comparison. Never auto-install latest main in a factory run.

For `web-design-guidelines`, the upstream instruction fetches a remote guideline file on every use. Replace this with a pinned, previously reviewed snapshot in the adapter to prevent non-reproducible remote instructions.

For Claude `--bare`, plugin directories can intentionally restore selected skill capability. However, some upstream skills depend on ambient plugin commands, MCP servers or user preferences. The adapter should reject such a skill unless those dependencies are explicitly provisioned and permitted. Source: https://github.com/anthropics/claude-code/issues/52283

## 6. Permissions and evidence model

| Actor | Repository writes | Shell / browser | Outbound network | Can approve release? |
|---|---|---|---|---|
| Supervisor | Controlled manifest/report writes | Runs fixed tool/gate commands | Limited to configured provider/GitHub APIs | Yes, **only** when gates/reviews pass |
| Planner / Architecture | None | Read only | No arbitrary browsing | No |
| Builder | Implementation and tests in isolated worktree | Restricted sandbox | Package registry/provider allowlist only | No |
| Test / UI / UX / Security reviewers | None | Read artifacts, no shell mutation | None by default | No, each submits evidence-based verdict |
| Independent gate worker | Outputs only to evidence directory | Test runner, browser, scanners | Explicitly scoped network when necessary | Can generate evidence, not override decisions |

Any missing or stale mandatory evidence blocks release. UI review must check actual rendered states at defined viewports, with a11y outcomes and visible screenshots. Security's Semgrep/dependency/secrets gates must report tool version, command, exit code, artifact hash and findings. Skills cannot replace gate execution or alter the severity threshold.

## 7. Implementation backlog

### P0 — Registry, security and observability (must ship first)
- [ ] Define versioned `skills/registry.json` schema and lockfile.
- [ ] Add `factory skill audit`, `factory skill list`, `factory skill sync --dry-run` commands.
- [ ] Add protected-path and no-symlink/no-manifest-tamper tests.
- [ ] Add per-invocation skill selection, immutable manifest logging, fail-closed fallback.
- [ ] Validate cross-provider skill loading in test fixtures; verify Claude `--bare` behavior.

**Acceptance:** inactive skill cannot be loaded; hash change blocks run; only allowed skill IDs available to role; missing skill fails closed; no model can edit registry or artifact hashes.

### P1 — Planner, Architecture, Builder
- [ ] Add approved Superpowers planning and TDD/debugging wrappers.
- [ ] Add architecture vocabulary skill wrapper.
- [ ] Route React/Next.js best-practices conditionally.
- [ ] Make each active skill produce structured evidence; retain current output contracts.

**Acceptance:** held-out planning tasks trace acceptance criteria to tests; Builder cannot disable tests; project without React never gets a React-specific skill.

### P2 — Testing, UI and UX
- [ ] Add Property-based Testing; select only when domain invariants exist.
- [ ] Use Playwright/browser worker for dynamic UI, screenshot matrix, trace and console capture.
- [ ] Evaluate `frontend-design` versus `impeccable` versus `ui-ux-pro-max` separately; promote one default style-review framework based on visual defect detection and cost.
- [ ] Pin Vercel guideline snapshot and add WCAG patterns.
- [ ] Feed browser artifacts to read-only reviewers; iterate findings to Builder.

**Acceptance:** a seeded keyboard trap, small-screen overflow, missing empty state and a JavaScript console error are detected and block sign-off.

### P3 — Security and supply chain
- [ ] Add threat modeling to design, differential review to review.
- [ ] Add pinned Semgrep rules, dependency advisories, Gitleaks, optional CodeQL/Trivy as independent gates.
- [ ] Validate vulnerable fixtures (auth bypass, SSRF, secret, injection, dependency risk).
- [ ] Make findings include file/line, exploit path, severity, remediation, re-test evidence.

**Acceptance:** seeded critical/high vulnerabilities block delivery; zero SAST output is never treated as scan success if scanner did not run.

### P4 — Automated selection and evaluation
- [ ] Add metrics: escaped-defect rate, false-positive findings, repair rounds, successful builds, token usage, USD cost, wall time and skill usage.
- [ ] Create at least 10-20 held-out cases per specialized role (can share fixtures) and adversarial/injected-skill tests.
- [ ] Canary individual new versions; require material quality lift or comparable quality at lower cost.
- [ ] Propose updates via PR; keep rollback to last-approved SHA.

**Acceptance:** each skill shows before/after evidence relative to no-skill baseline; failed canary rolls back without touching production run configuration.

## 8. Evaluation and release criteria

- **Safety:** zero skill-authorized governance edits, unapproved actions, secret leaks, or bypassed mandatory gates. Any such event is a hard stop.
- **Quality:** no decrease in required-gate pass rate on the held-out suite; higher detection rate of seeded defects without unacceptable new false positives.
- **Autonomy:** no unexpected questions or user-interaction prompts; unresolved ambiguity results in conservative assumptions or a blocked report.
- **Cost:** show p50/p95 tokens, API dollars, wall time and total attempts for baseline vs skill-enabled tasks; avoid default skill bundles whose additional cost is unproven.
- **Reproducibility:** identical source SHAs and gate versions are recoverable from every run; all loaded skill paths and content hashes match lockfile.
- **Portability:** cross-provider tests pass on supported Codex CLI and Claude Code CLI versions; protocol/flag changes break safely.

### Key known v0.1 limitations addressed by this plan

- `claude --bare` skips ambient project skill discovery; needs intentional provisioning.
- Reviewer `--tools Read,Glob,Grep` cannot run many upstream scripts and browser tools; execution must be delegated to fixed external gates.
- Existing protected paths do not include a future `skills/` tree; must be extended **before** installation.
- Existing CLI execution gives Codex its ambient skill discovery; an isolated controlled skill root is needed for strict per-role allowlisting.
- No real-browser evidence collector currently exists for UI/UX reviews.
- No real skill-registry versioning, skill attribution, or comparative quality evaluation exists yet.

## 9. What not to do

- Don't install every skill from a high-star repository.
- Don't layer two incompatible software-factory state machines (BMAD + Ralph + Superpowers orchestration) inside this supervisor.
- Don't automatically update instructions from `main`, fetch live security rules in a reviewer prompt, or allow a model to install its own skills.
- Don't conflate agent review verdicts with actual scanner/test evidence.
- Don't grant read-only reviewers shell, GitHub mutation, secrets or browser-login capabilities merely because a skill asks for them.
- Don't let a visual-style skill override a product requirement, design system, accessibility standards or acceptance tests.

## Sources used for discovery (2026-10-20)

- https://skills.sh/ (aggregate installs; popularity only)
- https://github.com/obra/superpowers
- https://github.com/anthropics/skills
- https://github.com/vercel-labs/agent-skills
- https://github.com/mattpocock/skills
- https://github.com/openai/plugins
- https://github.com/pbakaus/impeccable
- https://github.com/nextlevelbuilder/ui-ux-pro-max-skill
- https://github.com/trailofbits/skills
- https://github.com/wshobson/agents
- https://developers.openai.com/api/docs/guides/tools-skills
- https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
