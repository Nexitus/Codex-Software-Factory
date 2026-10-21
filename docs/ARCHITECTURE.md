# Architecture and operator contract

## Consumable CLI and consumer ownership

The distribution exposes `software-factory`. `--help` and `--version` work without a project checkout or optional dashboard dependencies. `init` initializes an existing Git checkout with project configuration and selected host instructions; it does not copy factory code, dashboard files, or gate commands into a consumer project. The legacy `python install.py <repo>` scaffold remains available and is not automatically migrated.

`software-factory run` forwards its argument vector to the same deterministic supervisor used by `python factory.py`. Installed policy, role prompts, schemas, and templates are read-only package resources. Project config and default run/event state belong beneath the selected consumer checkout; user-relative spec/config/event paths remain relative to the caller's working directory. A dry run writes local run/event evidence but does not invoke a provider or project gate.

The intended operator sequence is initialize, configure real project gates, commit the configuration and initial project files, check readiness, run, and inspect status. The CLI implements `doctor` for local readiness and `status` for saved run evidence. Windows wheel and sdist-derived-wheel lifecycle tests cover both commands; broader state fixtures and native-host qualification remain pending in the [CLI verification matrix](consumable-factory-cli-verification.md).

Codex is the only provider qualification target for the first release. Codex Desktop and Codex CLI use the Codex skill adapter; Claude Code and OpenCode templates remain explicitly unverified. The package does not install or authenticate any host/provider CLI. A harness invocation is not a substitute for supervisor gate and review evidence.

## States

`request → premium plan → low-cost specialist design → premium build dispatch → low-cost build worker → {gates + low-cost reviews → premium triage → low-cost repair}* → verified_candidate | blocked`

The state machine is implemented by the **Python supervisor**, not by language-model instructions. Each invocation receives a standalone prompt and must return the required structured JSON schema. Only the low-cost Build Worker runs with write-capable tools. Reviewer verdicts **do not** replace subprocess exit codes.

## Handoff contract

- **Plan**: summary, UI change flag, acceptance criteria (ID, description, verification), work items, assumptions, risks.
- **Design**: per-role guidance, proposed checks, risks, blocking questions. Any blocking question prevents Build.
- **Build orchestration**: compact task dispatch and evidence-driven triage, without source writes.
- **Build**: summary, changed files, new tests, unresolved work; unresolved work blocks verified completion.
- **Gate results**: argv, exit codes, timing, file path and bounded excerpt for failures. Gate `pass` requires all subprocesses in the gate to return zero.
- **Reviews**: `pass | fail | not_applicable`, cited findings (critical/high/medium/low), checks and limitations; missing reviewers and non-pass verdicts block release.

## Review/repair policy

Critical, high and medium findings must be fixed. Low severity can remain advisory. The default is three review cycles. After each repair, all configured deterministic gates and every required specialist review rerun; prior passes are **not** cached. The last report contains the actual final results.

## Isolation / threat model

A hostile repository can contain dangerous install scripts, tests, readmes and embedded instructions. Running the Builder or even a verification command on the host is not safe merely because the model is sandboxed. Use an ephemeral VM/container, non-production credentials, restrict network egress, and grant a fine-grained credential for PR-only write operations if publication is enabled. Logs may contain proprietary code and secrets; `.factory/` is Git-ignored but not encrypted.

The supervisor uses a clean working-tree prerequisite, SHA-256 snapshots of protected files, checks Git HEAD after agent stages, structured contracts, and subprocess timeouts. These are **integrity tripwires**, not a hard security boundary. There is no OS isolation in this version.

## Tiered routing for the first release

The first release config is Codex-only: planner and build_orchestrator use GPT Sol; Builder and every specialist use GPT Luna. No default models or silent tier changes are permitted. Provider availability is account-dependent and an invocation failure blocks the run. Claude Code and OpenCode adapters are retained but unverified.

## Verification content isolation

The supervisor fingerprints tracked and untracked, nonignored source before and after planning, designing, orchestration, gates and review. That catches additional mutations that do not affect governance files. It is still not a security boundary against a hostile local subprocess. Execute untrusted builds in a VM/container.

## Local run dashboard and durable events (v0.5)

The dashboard is a loopback-only FastAPI application started by `dashboard.py`. `app/server.py` owns the local HTTP API, project allowlist, browser bootstrap, and FIFO queue. `app/events.py` stores runs and append-only events in SQLite with WAL and a monotonically increasing event ID. The database records whether it is in `live` or `demo` mode and refuses to open under the other mode. Events are redacted before persistence and contain run identity plus stage, round, attempt, and timestamp context; logs and secret-bearing report text are not streamed as event payloads.

`factory.py` remains the only authority for planning, role/model routing, design, build, repair rounds, deterministic gates, reviews, report generation, and final delivery status. It emits lifecycle, stage, agent, gate, finding, repair, round, delivery, and completion events from the existing supervisor flow. The dashboard starts the existing CLI using a fixed argument vector and a validated project ID; it does not create a second implementation path or accept user-supplied shell commands. The protected support modules are `app/events.py`, `app/projector.py`, `app/checkout_lock.py`, and `app/process_guard.py`.

`app/projector.py` deterministically projects stored events into the eight board stages: Queue, Planning, Design, Build, Review, Repair, Ready, and Blocked. `Ready` requires a persisted supervisor `delivery_verified` event with `delivery_status` exactly `verified_candidate` and a matching bounded `DELIVERY.json` report for the same run. Conflicting or incomplete evidence cannot promote a run; a process exit, `run_completed`, event alone, or report alone is insufficient. A failed review verdict remains a failed stoplight even if its CLI process returned successfully. Restart recovery reattaches only to a matching live supervisor process identity. A report-only success claim is never synthesized into verification evidence.

The dashboard endpoints are `GET /api/health`, `/api/projects`, `/api/runs`, `/api/runs/{id}`, `/api/runs/{id}/events`, `/api/runs/{id}/artifacts`, and `GET /api/events` for global Server-Sent Events replay; `POST /api/runs` queues work. The run-list response includes a snapshot `last_event_id`, and SSE accepts `Last-Event-ID` or an `after` cursor so clients can replay events without a snapshot/subscription gap. `GET /api/runs` returns only the newest 200 runs and has no pagination, so older run history is not discoverable from the board list. Host validation and Origin checks cover reads and writes, mutations require the bootstrap CSRF token, and paths are resolved under an explicit project and run/artifact allowlist. The app binds to 127.0.0.1; it does not expose a remote job service.

The API queue is FIFO and delegates each live run to the supervisor child process. The queue and direct CLI use the same canonical-checkout lock. A durable `.factory/active-run.json` marker quarantines a checkout after timeout or uncertain process exit; while that marker is present, new work fails closed until an operator confirms the supervisor and all descendants have stopped. PID birth tokens distinguish a live process from a reused PID during recovery. This marker is a safety interlock, not process-tree containment or an OS sandbox.

Demo mode uses an isolated, mode-locked SQLite database and skips live report reconciliation. It generates synthetic plan, design, review, repair, gate, and delivery events without invoking Codex, Claude, or another model provider. Its Ready result exercises only the UI's event flow and is not evidence about generated code. Live and demo databases cannot be interchanged.

## v0.5 local security and limits

The service is intended for one local user on a trusted machine. It rejects unexpected Host and Origin values, uses a per-process CSRF bootstrap token for mutations, restricts project IDs to configured checkouts, and serves only bounded allowlisted artifacts within a run directory. Sensitive values are redacted before storage or API responses. The dashboard does not expose arbitrary filesystem browsing, command arguments, environment variables, raw logs, or report blobs. SQLite and local files are not encrypted, and same-user processes can still access them. The run board lists only the newest 200 rows; there is no API pagination for older runs yet.

This design does not provide OS-level sandboxing, remote access, provider authentication, or guaranteed termination of arbitrary descendant processes. A timeout or ambiguous interruption keeps the checkout quarantined rather than assuming children stopped. Windows and Linux are the documented launch targets; Linux behavior and real provider invocations remain unqualified by this local verification record.
