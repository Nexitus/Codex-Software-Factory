# Codex Environment and Development Workflow Audit

**Audit date:** 2026-10-20  
**Scope:** User-level Codex, Claude Code, OpenCode, and OMP configuration; current projectless audit workspace.  
**Method:** Read-only static inspection and harmless CLI version probes. No agent workflow or tests were run, and no configuration or source files were changed. The current workspace contains only outputs/ and work/; it has no project-level AGENTS.md, CLAUDE.md, DESIGN.md, CI config, or source tree.

## 1. Executive summary

The machine has several capable but mostly separate agent environments. It does **not** have one integrated, enforced software factory that reliably moves every requirement through planning, build, tests, independent review, repair, and verified delivery.

The active Codex configuration has one general assistant default, **gpt-6-luna** with **xhigh** reasoning. No role-specific Codex Planner, Builder, Test, or Reviewer definitions were found. Codex can use transient subagents, but that capability has no persistent phase graph or role-to-model mapping.

The strongest *documented* implementation contract is the installed OMP delegation skill: Codex plans, OMP implements, Codex independently inspects the diff and verification, and at most one correction pass is allowed before reassessment. OMP is not usable from this audit context: the omp --version probe failed with a module-not-found error. Its nested config contains model roles, but the default and plan routes do not meet the target routing policy.

Claude Code has 16 user-level specialist prompts and enabled review plugins. Its CLI responds to --version, but no model request or agent invocation was made. The custom prompts encourage automatic delegation, but they do not define a bounded, fail-closed development state machine. All 16 use the sonnet alias, omit tool/permission restrictions, and omit skill preloads. Claude is configured to use a custom Fuelix endpoint; actual backend identity and returned model are unverified.

OpenCode has primary Plan and Build agents plus Explore and General subagents. Its configured Plan model is GLM 5.3 and Build model is DeepSeek V4.1 Flash. These are separate from Codex and OMP, and no handoff from Plan to Build or mandatory review/test loop is configured. The OpenCode executable could not start in this sandbox because it could not open its user-profile log file.

**Critical credential finding:** Two inline MCP credentials in Codex's config were emitted in an initial raw tool output during this audit. They are not reproduced here. Treat those two credentials as exposed and rotate them. I did not modify credentials under the read-only scope.

### Maturity assessment

| Capability | Current state |
|---|---|
| Requirement intake | Present through an interactive Codex, Claude, or OpenCode session |
| Planning | Prompted by instructions or selected Plan agents; no single enforced planner route |
| Architecture | Optional specialist prompts; no required architecture gate |
| Implementation | Direct Codex available; OMP delegation specified but preflight fails; OpenCode Build is separate |
| Testing | Skills and prompts exist; no universal required test runner or CI gate was found in this workspace |
| UI/accessibility review | Instructions and tools exist, but invocation and project hook activation are conditional |
| Security review | Specialist prompts and Codex Security plugin exist; no automatic scan gate was found |
| Repair loop | OMP contract caps correction at one pass; no working automatic loop in the active path |
| Delivery | Final response and user-directed actions; no immutable proof-of-quality gate |

## 2. Scope and evidence definitions

- **Operational:** exercised successfully in this audit context.
- **Configured, inactive:** files/settings are present, but the agent was not invoked in this Codex session.
- **Blocked here:** executable is present, but a harmless startup/version probe failed in this sandbox.
- **Unknown:** static files do not prove the live provider, effective merged config, or runtime behavior.

Inspected: C:\Users\brlam\.codex\AGENTS.md, config.toml, hooks.json, and rules\default.rules; C:\Users\brlam\.claude\CLAUDE.md, settings.json, config.json, user agents, and installed plugin metadata; C:\Users\brlam\.config\opencode agents/configs; C:\Users\brlam\.omp\agent\config.yml; and the user skill roots.

No existing Graphify graph was present at the audit workspace or Codex root. Building one would create files and may call semantic extraction, so it was not run under the read-only and no-paid-agent constraints. Direct file inspection was used instead.

## 3. Agent matrix

### Codex

| Agent/capability | Purpose and model | Tools, skills, permissions | Invocation and status |
|---|---|---|---|
| Codex main assistant | Requirement intake, planning, coding, and final response in one conversation. On-disk default is gpt-6-luna, xhigh; exact model serving this turn is **Unknown**. Provider: Codex/OpenAI. | Current session exposes shell/file tools, web, MCP/app connectors, browser/computer-use tools, and transient collaboration. Global instructions route skills by task. Config has approval_policy=on-request and sandbox_mode=workspace-write. Current app context reports auto_review for approval escalation, while config.toml says guardian_subagent; effective approval reviewer differs from disk. | User chat; operational now. No separate Planner or Build role config found. |
| Transient Codex subagent | Ad hoc independent task. No persistent model assignment found. | Current collaboration tools can spawn/message/wait/interrupt. Subagents share the current filesystem/tool environment; no default worktree isolation or per-role skill preload is configured. | Selected by the main assistant; capability available, but no subagent was used in this audit. |
| Codex plugin agents | No agent prompt files found in the Codex plugin cache. Enabled Code Review and Codex Security plugins provide capabilities, not a configured stage graph. | Plugin/tool access is available from the main session; no dedicated reviewer permission profile found. | User/assistant invoked; configured capabilities, not automatic gates. |

Evidence: C:\Users\brlam\.codex\config.toml lines 1–5 and plugin declarations around lines 23–86; global instructions in C:\Users\brlam\.codex\AGENTS.md.

### OMP

| Agent/capability | Purpose and configured route | Tools, skills, permissions | Invocation and status |
|---|---|---|---|
| OMP implementation worker | The installed omp-delegate skill assigns implementation/refactor/test work to OMP while Codex plans, independently reviews, and verifies. Nested config defaults to opencode-go/deepseek-v4.1-flash; there is no explicit build role. | OMP skill requires a bounded prompt, Ponytail, no unsafe auto-approve flags, independent diff/test verification, and at most one correction pass before reassessment. Provider/permissions must be resolved by OMP CLI before a run. | Intended delegated path, but **blocked here**. omp --version failed with a module-not-found error for its Pi CLI entry point. A later file-existence check returned true for that path, so the exact cause is Unknown. The mandatory preflight did not pass; no OMP run was attempted. |

Nested global routing file: C:\Users\brlam\.omp\agent\config.yml

| Role key | Declared model | Configured fallback |
|---|---|---|
| plan | opencode-go/grok-4.7 | opencode-go/grok-4.7:xhigh |
| default | opencode-go/deepseek-v4.1-flash | opencode-go/gpt-6-luna:xhigh |
| task | opencode-go/gpt-6-luna:xhigh | opencode-go/glm-5.3:high |
| slow, advisor | openai-codex/gpt-6-sol | GLM 5.3 max / Grok 4.7 xhigh |
| smol | openai-codex/gpt-6-sol:auto | GLM 5.3 max, then GPT-6 Luna xhigh |
| tiny, commit | openai-codex/gpt-6-luna:low | GLM 5.3 Flash low |
| memory | opencode-go/glm-5.3-flash:low | None listed |

defaultThinkingLevel is auto. The role table does not identify which role corresponds to “Build Orchestrator”; default is DeepSeek Flash and plan is Grok. Listed fallbacks include GLM and Grok. Those declared routes do not consistently match the target policy. Runtime resolution remains unverified because OMP preflight failed.

Evidence: C:\Users\brlam\.agents\skills\omp-delegate\SKILL.md (preconditions, procedure, one-correction-pass rule); C:\Users\brlam\.omp\agent\config.yml lines 2–39; omp.exe at C:\Users\brlam\.bun\bin\omp.exe.

### Claude Code

The CLI is installed and claude --version returned 2.1.169. No model request was made, so authentication, actual provider, and runtime agent availability are unconfirmed. ~/.claude/settings.json declares ANTHROPIC_MODEL=claude-sonnet-4-6 and ANTHROPIC_BASE_URL=https://api.fuelix.ai. This is a custom endpoint route, not evidence of direct Anthropic service or of the model returned by that endpoint.

All 16 files in C:\Users\brlam\.claude\agents\ declare model: sonnet and no effort setting. None declares tools, disallowedTools, permissionMode, skills, mcpServers, or worktree isolation. Claude Code documentation says omitted tool limits inherit the parent’s available tools and omitted permission mode inherits the parent. The global allow list includes file write/update tools, shell permissions for commands including curl, docker, python, npm, and git, plus Melty MCP; deny is empty. A reviewer prompt is not a tool-isolation boundary by its name alone.

| Agent file/name | Purpose |
|---|---|
| accessibility-auditor.md | Accessibility, ARIA, keyboard, and screen-reader review |
| ai-integration-specialist.md | LLM/RAG/agent and tool-orchestration design |
| api-designer.md | API contracts, endpoints, OpenAPI, versioning |
| code-refactorer.md | Refactor complex or duplicated code |
| code-reviewer.md | Quality, security, and maintainability review |
| coordinator.md | Decompose multi-domain work and delegate specialists |
| css-architect.md | CSS systems, tokens, responsive layouts |
| debugger.md | Diagnose runtime errors, failed tests, and integrations |
| e2e-tester.md | End-to-end user-flow coverage |
| performance-optimizer.md | Frontend performance analysis/optimization |
| product-strategist.md | Product requirements, idea evaluation, prioritization |
| security-auditor.md | Security review of code, APIs, and data flows |
| state-manager.md | Frontend state architecture and data flow |
| system-architect.md | Technical architecture and service interactions |
| test-generator.md | Unit/integration test coverage generation |
| ui-engineer.md | UI implementation and design-system work |

Descriptions encourage proactive use for matching tasks. Current Claude Code documentation describes automatic delegation based on request/descriptions and explicit named invocation. That is model-selected delegation, not a guaranteed sequence. These files do not preload skills. Claude Code built-ins such as Explore, Plan, and General-purpose may also be available in interactive sessions; exact built-in inventory for installed version 2.1.169 was not verified.

Enabled plugin agent prompts found:

| Plugin agent | Declared model | Purpose/status |
|---|---|---|
| superpowers:code-reviewer | inherit | Review; plugin enabled, not invoked |
| pr-review-toolkit:type-design-analyzer | inherit | Type/design review; enabled, not invoked |
| pr-review-toolkit:silent-failure-hunter | inherit | Silent failure review; enabled, not invoked |
| pr-review-toolkit:pr-test-analyzer | inherit | Test adequacy review; enabled, not invoked |
| pr-review-toolkit:comment-analyzer | inherit | Review comment quality; enabled, not invoked |
| pr-review-toolkit:code-simplifier | opus | Simplification; enabled, not invoked |
| pr-review-toolkit:code-reviewer | opus | Code review; enabled, not invoked |

The code-reviewer name exists in three Claude scopes/variants (user-level, Superpowers, PR Review Toolkit). Plugin scoping may distinguish them, but it is a duplication that can make manual selection ambiguous. Two PR Toolkit agents pinned to Opus also conflict with the requested specialist-reviewer model policy.

Evidence: C:\Users\brlam\.claude\settings.json lines 3–67; C:\Users\brlam\.claude\CLAUDE.md lines 1–3; C:\Users\brlam\.claude\agents\*.md front matter; C:\Users\brlam\.claude\plugins\installed_plugins.json.

### OpenCode

The opencode executable exists, but opencode --version failed in this sandbox with EPERM while opening C:\Users\brlam\.local\share\opencode\log\opencode.log. Its ability to start outside this sandbox is Unknown.

| Agent file | Purpose | Model/effort | Tools, skills, invocation |
|---|---|---|---|
| agents/plan.md | Planning and analysis; prompt says edits are disallowed | opencode-go/glm-5.3; effort unspecified | Primary. No explicit permission/tool allowlist, so read-only enforcement is unverified. Selectable primary, not chained automatically to Build. |
| agents/build.md | Default implementation agent; prompt asks for narrow verification and diff inspection | opencode-go/deepseek-v4.1-flash; effort unspecified | Primary. No agent-specific permission allowlist. |
| agents/explore.md | Read-only file/codebase exploration by prompt | opencode-go/deepseek-v4.1-flash, temperature 0.1 | Subagent. Prompt says not to modify, but no explicit tool restriction is declared. |
| agents/general.md | General research/multi-step work; prompt says parallel units may be executed | opencode-go/deepseek-v4.1-flash, temperature 0.2 | Subagent; no explicit tool/permission restriction or fixed skills. |

Global files opencode.json and opencode.jsonc coexist and declare different MCP servers/plugins. The jsonc file includes a filesystem MCP root of C:\Users\brlam and an allow rule for all melty_* tools. The json file declares other MCP servers, including Docker and PowerShell. Effective merged config was not resolved because the binary could not start; do not treat either file alone as the confirmed runtime set. No OpenCode plan/build handoff, review stage, or retry loop appears in the four agent prompts.

Evidence: C:\Users\brlam\.config\opencode\agents\{plan,build,explore,general}.md; C:\Users\brlam\.config\opencode\opencode.json; C:\Users\brlam\.config\opencode\opencode.jsonc.

### Project-level agents

None were found in the current audit workspace or its immediate dated parent. This is a projectless generated Codex directory, not a source repository. No project agent configuration can be attributed to a separate application repo without a repo path.

## 4. Actual workflow and orchestration

The configuration supports several separate workflows but does not wire them into one chain. Solid boxes are the current Codex path; dashed boxes are separate runtimes not connected to it.

~~~mermaid
flowchart TD
    U[Requirement from user] --> C[Codex main conversation]
    C --> P[Planning in same conversation<br/>AGENTS rules and task-selected skills]
    P --> D{Assistant/user chooses execution path}
    D -->|Direct| B[Codex main edits or runs tools]
    D -->|OMP delegation| O[OMP preflight]
    O -->|Current observed result| X[Blocked: omp --version fails]
    B --> H[Configured global hooks on matching tool events]
    H --> T[Selected verification, if chosen by task/agent]
    T --> R{Review requested or selected?}
    R -->|No| F[Final response / user-directed delivery]
    R -->|Yes| V[Optional code/UI/security reviewer]
    V -->|Findings| M[Main assistant or user decides whether to repair]
    M --> B
    T -->|Failure| M
    subgraph Separate runtimes, not connected to Codex workflow
      CL[Claude Code session<br/>descriptions can prompt auto-delegation]
      OC[OpenCode session<br/>Plan/Build primary; Explore/General subagents]
    end
    C -. manual launch, no automatic handoff .-> CL
    C -. manual launch, no automatic handoff .-> OC
~~~

### Stage-by-stage findings

| Stage | Implemented behavior | Owner and enforcement |
|---|---|---|
| Requirement | User enters a request in the current Codex session. | Codex main assistant. No intake schema or acceptance-record artifact is mandatory. |
| Planning | Global instructions require Ponytail and Graphify during planning; task-specific skills are routed conditionally. | Same Codex assistant. No persistent Planner agent; no pre-existing Graphify graph here. Full Graphify build was skipped because it would write artifacts and could use semantic extraction. |
| Architecture | Codex can reason directly; Claude system-architect/coordinator and OpenCode Plan are available in separate sessions. | Optional prompts. No architecture signoff before Build. |
| Build | Codex can edit directly. OMP is the documented implementation delegate; OpenCode Build is another separate option. | Direct Codex is available. OMP preflight fails. OpenCode startup is blocked in this sandbox. |
| Testing | TDD, browser, E2E, and test-generation skills/prompts are installed. OpenCode Build and OMP skill ask for verification. | No universal command, test matrix, CI job, or success gate in current workspace/global config. |
| UI/UX/accessibility | Global Codex instructions require design workflows for UI tasks; an Impeccable PostToolUse/Stop hook is configured. Claude has accessibility/UI specialists. | Conditional on task and hook activation. Current workspace has no .impeccable/config.json; project activation is absent here. No rendered UI or accessibility check was run. |
| Security review | Codex Security plugin and security skills are available; Claude security-auditor and PR review agents exist. | Optional invocation. No mandatory, independent, read-only security stage or scanner gate was found. |
| Repair | OMP contract permits one correction pass. Otherwise the main assistant/debugger can repair if failure is noticed. | No active automatic route back from review to Build. No fixed global retry count or escalation contract. |
| Delivery | Codex can produce a final response and tools can perform commits/external changes when asked and allowed. | No signed artifact, required CI status, protected-branch gate, or evidence bundle defines “verified complete.” Global shell rules include explicit allowances for some commit/push commands. |

The OMP skill describes a sequential path (Codex plan → OMP implementation → Codex diff/tests → at most one correction pass), and says to isolate a worktree if multiple agents may edit. That is a skill contract, not an active workflow: the CLI preflight failed. Claude and OpenCode each have conditional delegation; no context/artifact handoff connects them to this Codex chat.

## 5. Skills and instructions

### Installed and exposed skill roots

| Root/registry | Inventory | Runtime meaning |
|---|---|---|
| C:\Users\brlam\.agents\skills | 73 skill directories. .skill-lock.json tracks 60; 13 present directories are absent from the lock. | User-level skill library. Global Codex instructions route relevant skills; directory presence alone does not mean every session or agent loads one. |
| C:\Users\brlam\.codex\skills | 9 user skill directories (excluding .system). | Codex-scoped skills, including Graphify and awesome-design-md. |
| C:\Users\brlam\.claude\skills | 10 names: 9 junctions into .agents/skills and one separate Graphify copy. | Claude-visible skills; 16 user agent files do not preload skills. |
| Codex plugin cache | 153 SKILL.md files across 126 distinct names; 26 names occur in multiple cached copies/versions. | Plugin skills may be exposed when a corresponding plugin is enabled. Cache presence does not prove invocation. |
| OpenCode | Local Graphify copy and configured Ponytail/Superpowers plugins across two config files. | Effective skill set Unknown while OpenCode cannot start and two config files remain unresolved. |

### Relevant skills and actual use

| Capability | Installed examples | Assignment/use evidence |
|---|---|---|
| Required planning/code scope | Ponytail, Graphify | Global Codex AGENTS requires both during planning; Ponytail is required before code work. This audit followed Ponytail instructions and read Graphify’s skill. Graphify generation was intentionally not run under read-only constraints. |
| Planning/specification | planning-and-task-breakdown, spec-driven-development, brainstorming | Available; no fixed Planner agent loads these. |
| Architecture/API | api-and-interface-design, design-system, source-driven-development | Available; no mandatory architecture stage. |
| Build | incremental-implementation, frontend-ui-engineering, omp-delegate | Available; OMP skill specifies delegation requirements, but OMP did not run. |
| Test/debug | test-driven-development, browser-testing-with-devtools, break-ui, debugging-and-error-recovery | Available; not universal gates. |
| Review/security | code-review-and-quality, ponytail-review, security-and-hardening, Codex Security plugin skills | Available/enabled in places; no enforced review gate. |
| UI/UX/a11y | awesome-design-md, design-taste-frontend, emil-design-eng, ui-ux-pro-max, impeccable | Codex instructions make these conditional requirements for UI work. Impeccable hooks are global, but current workspace lacks project-level activation. |
| Completion/parallelism | verification-before-completion, requesting-code-review, dispatching-parallel-agents, using-git-worktrees | Installed through plugin cache; not encoded as a global deterministic workflow. |

The installed .agents inventory includes: adversarial-review, animate-expo, animation-vocabulary, api-and-interface-design, apple-design, ask-sonner, banner-design, brand, brandkit, break-ui, browser-testing-with-devtools, ci-cd-and-automation, code-review-and-quality, code-simplification, constraint-driven-development, context-engineering, debugging-and-error-recovery, deprecation-and-migration, design, design-director, design-system, design-taste-frontend, documentation-and-adrs, doubt-driven-development, emil-design-eng, find-animation-opportunities, find-skills, frontend-ui-engineering, full-output-enforcement, git-workflow-and-versioning, gpt-taste, hasdata, hasdata-cli, high-end-visual-design, humanizer, idea-refine, image-to-code, imagegen-frontend-mobile, imagegen-frontend-web, impeccable, improve-animations, incremental-implementation, industrial-brutalist-ui, install-moomoo-opend, interview-me, minimalist-ui, mobile-native, moomooapi, observability-and-instrumentation, omp-delegate, pacific-signal-writing, performance-optimization, pick-ui-library, planning-and-task-breakdown, ponytail, ponytail-audit, ponytail-debt, ponytail-gain, ponytail-help, ponytail-review, prototype, redesign-existing-projects, review-animations, security-and-hardening, shipping-and-launch, slides, source-driven-development, spec-driven-development, test-driven-development, stitch-design-taste, ui-styling, ui-ux-pro-max, write-swift.

### Duplication and drift

- .agents and .codex contain duplicate copies of adversarial-review, design-director, humanizer, and ui-ux-pro-max. SHA-256 checks found the first three copies identical and ui-ux-pro-max different.
- Nine Claude skill entries are junctions to .agents; Claude Graphify is a separate copy and differs from Codex Graphify.
- Plugin caches contain duplicate skill names in multiple versioned packages, including Superpowers, Ponytail, Google Drive, and browser-control skills. Effective collision/precedence was not tested.
- Thirteen .agents/skills directories have no .skill-lock.json entry. Their update/provenance state is not tracked by that registry.
- Skills not declared in an agent’s frontmatter are not guaranteed to load. Claude docs say skills can still be invoked during a run if the Skill tool is available; no such invocation was observed in the separate agents.

## 6. Model routing and cost controls

The target policy in the request is:
1. Planning Orchestrator: GPT Sol or Claude Opus.
2. Build Orchestrator: GPT Sol or Claude Opus.
3. Implementation workers and specialist reviewers: GPT Luna or Claude Haiku.

It is **not implemented consistently**:

| Role/system | Current declaration | Result against target |
|---|---|---|
| Codex main | gpt-6-luna, xhigh default | Not GPT Sol/Opus for planning/build. Exact current served model Unknown. |
| OMP plan | opencode-go/grok-4.7 | Not GPT Sol/Opus. |
| OMP default worker | opencode-go/deepseek-v4.1-flash; fallback GPT-6 Luna xhigh | Default is outside target specialist models; fallback is Luna. No explicit Build role. |
| OMP task, tiny, commit | GPT-6 Luna routes at varied effort | Luna fits worker family, but role use is not fully mapped and runtime is blocked. |
| OMP slow, advisor, smol | GPT-6 Sol routes | Sol is in target, but aliases are not clearly mapped to Planner/Builder roles. |
| OpenCode Plan | opencode-go/glm-5.3 | Not target. |
| OpenCode Build/Explore/General | opencode-go/deepseek-v4.1-flash | Not target. |
| Claude user agents | sonnet alias; user config declares Sonnet 4.6 through Fuelix | Not Opus for planning/build or Haiku for specialists. Actual endpoint response Unknown. |
| Claude PR Toolkit reviewers | Four inherit, two explicit opus | Inherited likely follows configured main model; explicit Opus does not match worker/reviewer target. No Haiku route found. |

No global budget, token cap, provider spend cap, max-turn policy, or cost alert was found in inspected role settings. Codex service_tier=default and OMP defaultThinkingLevel=auto are not budget limits. OMP has fallback chains, but a fallback can change provider/model; no policy locks fallbacks to permitted role families.

## 7. Quality, security, and approval controls

### Tests and reviews

- Unit, integration, browser, and E2E skills/prompts are installed, but none is a universal required gate.
- Code-review, security-review, test-generator, and accessibility agents are optional prompt-driven delegates. No agent permission isolation or mandatory review receipt is configured.
- Codex has a global PostToolUse hook for UI checks and a Stop hook for Impeccable. The current projectless workspace has no .impeccable/config.json, so project-level activation is absent here. Hooks do not run tests or security scans.
- No automatic “review findings → Build” return route was found. Outside the OMP skill’s one-pass contract, repair is assistant/user-directed.
- No immutable CI/branch-protection quality gate or externally validated acceptance artifact was found in this workspace.

### Isolation and permissions

- Codex transient subagents share the same working tree/tool environment unless a worktree is explicitly arranged. No persistent default isolation policy was found.
- Claude custom agent files omit tools and permissionMode. Their review role is descriptive; it is not a read-only tool boundary. No worktree isolation setting was found.
- OpenCode Explore and Plan prompts say not to modify files, but there are no per-agent permission allowlists in their Markdown frontmatter. Plan read-only enforcement is unconfirmed.
- OMP’s skill calls for a separate worktree when agents may edit concurrently, but the skill does not cause isolation automatically.

### Approval and delivery

- Codex disk config says on-request, but C:\Users\brlam\.codex\rules\default.rules contains 49 persistent allow prefix rules. They include git commit, git push, merge/pull, build commands, npx, web requests, and config/install commands. A matching rule can reduce prompts; whether every historical prefix remains effective in the current app is Unknown. Reviewer setting also differs: guardian_subagent on disk versus auto_review in app context.
- Claude has broad global allow rules and an empty deny list. Per-agent permission mode is omitted and inherited from the parent session.
- OpenCode’s two global configs grant different MCP sets. One config includes a filesystem server rooted at the whole user profile; if effective, that is broader than a project-only boundary. Effective config is Unknown because startup failed.
- Credential values are stored inline in local TOML/JSON config files. File ACL/encryption was not assessed. Codex’s Magic and Melty inline values appeared in the initial raw tool output; they were withheld thereafter. Rotate those values.
- No credential scanner, secret redaction gate, or rule preventing credentials in config files was found.

### Evidence of completion

The OMP skill and OpenCode Build prompt ask for concrete checks and a diff inspection, but no central state machine enforces that request. The current system does not require test results, review signoff, security scan output, commit SHA, or deployment evidence before the assistant can report completion. “Verified complete” has no single implemented definition.

## 8. Gap analysis

| Intended Software Factory property | Current evidence | Gap |
|---|---|---|
| One Planner and one Build Orchestrator with controlled model tiers | Codex default Luna; OMP plan Grok and default DeepSeek; OpenCode Plan GLM and Build DeepSeek | Role/model policy is not enforced and differs across runtimes |
| Specialists on Luna/Haiku | Claude specialists use Sonnet; OpenCode specialists use DeepSeek; OMP has mixed aliases | Required worker routing absent |
| Sequential or parallel orchestration rules | Claude descriptions encourage delegation; OpenCode General mentions parallel units; Codex supports transient subagents | No central dependency graph, concurrency rules, or artifact contract |
| Tests always run | Skills/prompts only | No required commands, test matrix, or CI gate |
| Independent security and code review | Optional reviewer prompts/plugins | No read-only review tool profile, shared-worktree protection, or mandatory signoff |
| UI/UX and accessibility review | Instructions, Impeccable hook, Claude accessibility agent | Conditional invocation and project hook activation; not a verified gate |
| Bounded repair cycle | OMP skill allows one correction pass | OMP preflight fails; other paths have no bounded automated loop |
| Safe delivery | On-request approval setting plus stale allow rules | Command approvals are not a quality gate; some commit/push prefixes are allowed |
| Traceable proof | Per-task prompts ask for evidence | No required report/manifest with test and review evidence |
| Secret protection | Secret-bearing fields in local configs | Inline credentials and two values exposed in this audit’s tool output |

## 9. Prioritized recommendations

### P0

1. **Rotate the two Codex MCP credentials printed in this audit’s tool output.** They belong to the Magic and Melty entries in C:\Users\brlam\.codex\config.toml. Then replace inline values with a protected environment/credential mechanism. Rotation was not performed because the task is read-only.
2. **Review the other inline credentials** in Claude and OpenCode config files and move them out of plaintext config. Keep values redacted in logs and audit output.
3. **Narrow OpenCode filesystem access** from the full user profile to explicit project roots before using that config with an agent.

### P1

1. **Choose one orchestrator/runtime and encode the role matrix.** Assign Plan and Build only to GPT Sol or Claude Opus; route implementation/review workers only to GPT Luna or Claude Haiku. Put explicit model IDs and allowed fallbacks in config, not inferred role names.
2. **Restore OMP’s CLI before relying on its route.** Its skill requires omp --version and omp --help to pass and the effective model to be resolved. Do not delegate until these checks work.
3. **Define a bounded pipeline.** Require a plan artifact, implementation diff, selected unit/integration/E2E checks, independent code/security review, and a final evidence summary. Set iteration limits and escalation behavior.
4. **Isolate Build from Review.** Use a separate worktree for implementation and a read-only reviewer tool profile. Prevent the reviewer from modifying the implementation tree.
5. **Add non-bypassable delivery gates.** Run required test and security/accessibility checks in CI with branch protection; require an external pass status before merge/release.

### P2

1. **Consolidate skill copies and tracking.** Resolve differing ui-ux-pro-max and Graphify copies, track or remove the 13 lock-missing skill directories, and pin one version of duplicate plugin skills.
2. **Consolidate OpenCode configuration.** Remove ambiguity between opencode.json and opencode.jsonc, set an explicit default agent, and define per-agent read/write/MCP allowlists.
3. **Add cost controls and observability.** Set per-role token/turn budgets, provider spend alerts, retry limits, and logs recording agent/model, delegated work, attempts, tests, and final review status.

## 10. If I provide one development requirement today

It enters the active Codex conversation. The same assistant receives it, applies global instructions, and can plan and implement directly with the configured Codex tools. The on-disk default is GPT-6 Luna at xhigh effort, but this audit cannot prove the exact model serving a particular turn. The assistant can select task-specific skills and can optionally use transient Codex subagents. OMP delegation is documented but currently stops at its failed CLI preflight. Claude Code and OpenCode are separate, manually launched environments; they do not receive this requirement automatically.

Automation stops before a guaranteed test/review/repair/delivery gate. A build might run whatever checks the assistant chooses for that request. UI hooks may run after matching edits only when the project is activated. Code/security/accessibility agents are optional. Failures do not automatically loop through a bounded repair cycle in the active Codex path, and no machine-enforced evidence bundle defines delivery.

What remains manual is choosing/approving scope where needed, ensuring required tests and independent reviews actually ran, deciding whether findings are acceptable, authorizing any external delivery, and checking that the final report contains verifiable evidence. For the current setup, also rotate the two credentials exposed in the audit tool output.

## References

- Claude Code: [custom subagents](https://code.claude.com/docs/en/sub-agents) and [settings](https://code.claude.com/docs/en/settings)
- OpenCode: [agents](https://opencode.ai/docs/agents) and [configuration](https://opencode.ai/docs/config)

