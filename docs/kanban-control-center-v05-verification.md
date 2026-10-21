# v0.5 backend verification record

This record reports only checks run against the current local working tree. It does not certify this protected factory repository as a candidate: this work changes the supervisor and its surrounding runtime, and the checkout contains pre-existing user changes. No merge, push, deployment, or premium worker invocation is part of this record.

## Verification targets

- Python backend and supervisor instrumentation tests.
- Windows install smoke test and installer collision refusal.
- API authentication, CSRF, Host/Origin validation, SQLite persistence, event replay, demo isolation, and verified-only Ready projection.
- Process birth-token checks, durable checkout quarantine, queue handoff validation, report recovery, redaction, and artifact containment.
- Frontend build and browser checks, plus independent adversarial rechecks.

## Results

Local backend and supervisor checks passed on Windows 11 with the repository-local Python environment:

| Check | Result |
|---|---|
| `.factory/tools-venv/Scripts/python.exe -m pytest -q --tb=short` | **53 passed**, 18 subtests passed, 12 deprecation warnings, 14.38 seconds. Includes backend persistence, concurrency, FIFO, lock/quarantine, restart recovery, SSE replay, auth/CSRF/Origin, artifact path/redaction, demo isolation and synthetic delivery details, installer, and existing supervisor regressions. |
| `.factory/tools-venv/Scripts/python.exe -m ruff check app` | Passed: all checks passed. |
| `.factory/tools-venv/Scripts/python.exe -m py_compile factory.py install.py skillctl.py dashboard.py app/*.py` | Passed. |
| `.factory/tools-venv/Scripts/python.exe -m pip_audit -r requirements.txt -r requirements-dev.txt --progress-spinner off` | Passed: no known vulnerabilities found. |
| `npm run lint` | Passed. |
| `npm test -- --run` | Passed: 6 tests. |
| `npm run build` | Passed with Vite 8.3.5. |
| `npm audit --audit-level=high` | Passed: 0 vulnerabilities. |
| `npx playwright test` | Passed: 6 serial Edge tests in 43.7 seconds. The timer regression verifies live elapsed time advances without SSE events and freezes at the server-reported terminal duration. |

The parent exercised the loopback API in demo mode: a Ready run (`fca834a4-7d65-4781-a731-47b75081414d`) and a Blocked run (`30b96879-aedd-4f00-8fe8-f0f3e0c44637`) followed their expected event projections. Health, authentication, CSRF and Origin rejection, project allowlisting, artifact containment, private-field exclusion, and Last-Event-ID replay passed. Demo detail now includes a synthetic delivery report only when its event stream contains the exact verified or blocked terminal event; it explicitly says that no code was generated. The frontend owner’s Edge suite covered desktop, mobile and 320-pixel layouts, dense fixture data, repair history, artifact opening, and keyboard focus return. An independent adversarial review reproduced the full Python suite and targeted queue handoff, redaction, protected-file, replay, and quarantine checks; see the [independent review report](../.factory/review-v05/ADVERSARIAL.md) and [UI verification record](../.factory/verification/dashboard-ui-verification.md). Browser screenshots are in [the verification artifact directory](../.factory/verification/).

These are local checks only. The Python and HTTP checks ran on Windows with Python 3.14.6; Linux launch/runtime behavior was not tested. The suite reports 12 FastAPI `on_event` deprecation warnings. `GET /api/runs` returns only the latest 200 runs and does not paginate, so older history is not available through the board list. No live model provider was called; demo mode uses synthetic fixture details and cannot qualify generated application code. This protected self-host maintenance run is not supervisor-certified as a `verified_candidate`. Runtime symlink/junction creation could not be verified in the sandbox. The checkout quarantine marker remains fail-closed after an uncertain worker or descendant exit; operators must confirm the entire process tree has stopped before removing it. The supervisor is not an OS-level execution sandbox. No push, merge, or deployment was performed.
