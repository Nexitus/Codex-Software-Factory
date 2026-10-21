# v0.5 Kanban Control Center

## Requirements

1. The dashboard has eight columns: Queue, Planning, Design, Build, Review, Repair, Ready, and Blocked. Stage changes come from persisted events emitted by the existing factory.py supervisor.
2. Run detail preserves the requirement, acceptance criteria, design guidance, independent agent/provider/model results, review rounds, repair history, findings, gate evidence, delivery report, bounded artifact references, and timestamps.
3. SQLite is the durable event source. Event sequence IDs are unique and ordered across concurrent writers. Restart recovery preserves completed runs, active supervisors, blocked runs, and unresolved orphan states.
4. Global SSE supports Last-Event-ID replay and an after cursor. The run-list snapshot returns its event cursor so the client can subscribe without losing intervening events.
5. Run submission validates the same-origin request, CSRF token, bounded requirement, and configured project ID. Reads require the bootstrap token or same-origin cookie, and every route validates loopback Host and rejects cross-origin requests.
6. A single active supervisor may write to a canonical Git checkout. Dashboard runs execute the existing factory.py CLI through a fixed argv. Direct CLI and dashboard work share the checkout lock and a durable quarantine marker; an unverified process exit keeps the checkout blocked until an operator verifies the worker tree is gone.
7. Ready requires the persisted supervisor delivery_verified event and its verified-candidate report. An ended process, completed stream, dry run, legacy report-only state, or passing subset of gates cannot produce Ready.
8. Demo mode uses a mode-isolated SQLite database, makes no provider/model calls, and demonstrates a failed Review → Repair → Review sequence followed by either a verified Ready outcome or Blocked.
9. Reports, events, and API responses redact common credentials and secret-bearing values. Raw prompts, environment values, stdout/stderr, and log contents are not exposed; artifacts use a bounded allowlist with checkout/run containment checks.
10. Existing CLI routing, model tiers, policy checks, review requirements, deterministic gates, protected-file integrity, and report formats remain authoritative.
11. Backend verification covers SQLite persistence and event ordering, projection and failure states, SSE replay, API security, dashboard handoff validation, FIFO and checkout exclusion, recovery/quarantine, artifact containment/redaction, demo isolation, and installer collision behavior.
12. Windows and Linux startup instructions cover both isolated demo mode and configured live mode.

## Acceptance

- Start the dashboard with python dashboard.py --demo; the default listener is loopback port 8765.
- In demo mode, submit one ready and one blocked outcome. The first visibly includes failed Review → Repair → Review and reaches Ready only with delivery_status: verified_candidate plus a delivery_verified event; the second stays Blocked.
- Start live mode only with a configured projects allowlist and the project's existing validated factory.config.json. Dashboard work delegates to the current CLI supervisor; no API route runs agents or gates itself.
- After restart, an active supervisor remains attached by process birth identity. An unverifiable exit appears in Blocked as orphaned and keeps the checkout quarantine marker.
- The API provides /api/health, /api/projects, /api/runs, /api/runs/{id}, /api/runs/{id}/events, /api/runs/{id}/artifacts, and replayable /api/events.
- Test and verification documentation distinguishes automated local checks, browser checks, and supervisor-certified candidate evidence.
