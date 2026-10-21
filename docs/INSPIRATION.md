# Prior art and research (October 20, 2026)

We studied public workflows/README files rather than copying code or repackaging these projects.

| Repository | Pattern considered | Design decision |
|---|---|---|
| [obra/superpowers](https://github.com/obra/superpowers) | Specification before implementation, TDD, agent execution + review | Planner produces acceptance criteria before any Builder access |
| [bmad-code-org/BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD) | Right-sized planning and explicit product/architecture context | Pre-build design reviewers create testable guidance; UI roles conditional |
| [OpenHands/OpenHands](https://github.com/OpenHands/OpenHands) | Multi-backend agent runtime, self-hosted worker options | Thin Codex/Claude subprocess adapters; future isolated worker backend |
| [Yeachan-Heo/oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode) | Teams-first specialist orchestration, staged verify/fix | Independent specialist review tasks and bounded repair stage |
| [frankbria/ralph-claude-code](https://github.com/frankbria/ralph-claude-code) | Persistent loops with safeguards, exit criteria, circuit-breaker ideas | Max review rounds and fail-closed stopping decisions |
| [jayminwest/overstory](https://github.com/jayminwest/overstory) | Isolated Git worktrees, agent runtime adapters, collaboration risks | Isolated branches encouraged; no dependency because project is archived |
| [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph) | State graphs, conditional transitions, durable workflow state | JSON artifacts store stage outputs; future resume/retry state machine |

## What we intentionally didn't adopt

- No double orchestration (e.g. BMAD controlling Claude controlling Ralph controlling Codex). A single deterministic supervisor owns the state machine.
- No hidden agent-to-agent messages or self-approval, because they weaken reproducibility and independent review.
- No automatic production deploy/merge, because AI-only sign-off is not sufficient for high-impact changes.
- No direct copying of prompts, implementation, badges, artwork or source code from researched projects.

## Primary CLI documentation

- [Codex CLI reference](https://learn.chatgpt.com/docs/cli/reference)
- [Claude Code CLI reference](https://code.claude.com/docs/en/cli-reference)
- [Claude Code programmatic structured outputs](https://code.claude.com/docs/en/headless)
