# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

cross-loop is a tiny orchestration layer (state machine + dispatcher) that drives external AI coding CLIs (Claude Code, Codex, Cursor, OpenCode) through a phase-based, self-verifying build loop — the "Ralph Loop" pattern. The orchestrator stays near-stateless; all state lives on disk (`tasks.yaml` + a `*.state.json` file), so the loop is durable and resumable. Pure Python 3.9+, only runtime dependency is PyYAML.

## Working here (scope discipline)

Match ceremony to the task — don't make small things big, don't let big things drift:

- **Trivial / reversible** (reading, a single edit, answering): just do it.
- **Non-trivial** (multi-step, touches several files): state intent + scope in one line first ("this does X; it does NOT touch Y"), then execute against that.
- **Large / ambiguous / irreversible** (broad refactor, deletes, anything outward-facing): plan or brainstorm first, get approval, then execute against the plan.

When a side-effect surfaces mid-task, check it against the stated scope: in scope → do it; out of scope → note it as a separate follow-up, do NOT do it inline. Declaring a convention is not the same as retroactively applying it to existing code — treat the latter as its own task.

## Commands

- Install (editable): `pip install -e .` — or `pipx install .` for a global CLI.
- Install with test deps: `pip install -e ".[dev]"` (pulls in `pytest`). On an externally-managed Python (Homebrew/PEP 668), use a venv first: `python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"`.
- Run tests: `pytest tests/` (or `.venv/bin/pytest`) — they do not require the real CLI tools to be installed.
- Run the loop: `cross-loop run --tasks tasks.yaml --tool claude-code --model opus`
- Resume / inspect: `cross-loop status`

## Code style

- Format with `black`; lint with `ruff`. Run both before committing (a PostToolUse hook also auto-applies them on edit).
- Use `from __future__ import annotations` and type hints, matching existing modules.

## Git workflow

Work on feature branches and open a PR into `main`. Do not commit directly to `main`.

## Architecture

The package is small (~8 files in `cross_loop/`). Read the source, but the responsibilities are:
- `loop.py` — orders phases, dispatches each, runs the verify gate, retries-with-feedback until it passes.
- `dispatch.py` — translates `(tool, model, prompt)` into argv and runs it.
- `config.py` — loads global config + per-tool YAML adapters.
- `state.py` — durable JSON state machine.
- `verify.py` — runs the convergence gate.

Tool adapters live in `config/tools/<name>.yaml`. **Adding support for a new CLI is config-only — no code changes.** See `/add-tool-adapter`.

Deeper design docs: @docs/architecture.md and @docs/configuration.md

## Gotchas

- **The verify command is the convergence gate.** A phase is "done" only when its `verify` shell command exits 0. A weak or missing verify command (no real test suite) means weak convergence.
- **`--yolo` is dangerous.** It passes `--dangerously-skip-permissions` (or a custom allow-list) to the underlying tool, letting it run any command unattended. Only use inside an isolated git worktree or container — never on a production repo.
- **State files** (`*.state.json`) live alongside `tasks.yaml` and are gitignored. Re-running the loop resumes from saved state.
- Env vars: `$CROSS_LOOP_CONFIG` (global config path) and `$CROSS_LOOP_TOOLS_DIR` (tool adapters dir, defaults to `./config/tools`).
