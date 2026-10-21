---
name: software-factory
description: Run the installed Codex Software Factory supervisor for a user request in the selected Git checkout.
---

Use this skill only from the user-facing Codex or OpenCode session. If you are already a factory role worker dispatched by the supervisor, do not invoke the CLI recursively; complete your assigned stage and let the supervisor determine the next stage.

For a project that has not been initialized or reports setup problems, run `software-factory doctor --project <checkout>` and report its actual result. To carry out a request, invoke `software-factory run` for the selected checkout. Prefer a process interface that accepts an argument array and pass the request as a separate argument. If the host only accepts shell command text, use its file-writing capability to save any arbitrary request, including a single-line request, as an exact UTF-8 spec file under the checkout's ignored `.factory/` directory, then invoke `software-factory run <spec-file> --project <checkout>` with only the file path in the command. Never interpolate request text into executable shell command text.

The CLI supervisor owns stage order, worker routing, gates, review, and delivery status. Report the command result and evidence path; a process launch or model narrative alone does not prove completion.
