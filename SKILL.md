---
name: cross-loop
description: >-
  Run a large software task to completion unattended by chaining multiple AI
  coding CLIs (Claude Code, Codex, Cursor, OpenCode) through a phase-based,
  self-verifying build loop. Use when the user wants to build a project
  overnight / autonomously, run many phases in fresh contexts, retry-until-tests-pass,
  or orchestrate more than one coding tool together. Triggers: "build loop",
  "run overnight", "autonomous build", "phase by phase", "ralph loop",
  "cross-loop", "drive codex/claude/cursor".
metadata:
  version: 0.1.0
  homepage: https://github.com/zhang/cross-loop
---

# cross-loop

cross-loop is a thin orchestrator. It does **not** write code or run tests
itself — it schedules other coding CLIs to do that, one phase at a time, each in
a fresh process, retrying with feedback until a verify command passes.

## When to use this skill

Use cross-loop when the user wants to:

- build a project (or a big feature) **autonomously / overnight**, with little supervision;
- run a **decomposed spec** as a sequence of phases, each in a clean context window;
- **retry until tests pass** (converge), not just run a prompt once;
- **combine several CLI tools** (e.g. Claude Code for some phases, Codex for others).

Do not use it for a single quick edit or a one-shot question.

## What you (the agent) do

1. **Produce a spec, then decompose it into phases.** Each phase must be small
   enough to fit comfortably in one context window (GSD-style). If the user has
   GSD/GStack installed, drive those to generate the spec and phases. Each phase
   becomes one entry in a `tasks.yaml`.

2. **Write `tasks.yaml`.** For each phase set:
   - `id`: unique slug
   - `prompt`: what the tool should do this phase. May be a slash command for a
     Claude-Code-based tool (e.g. `/gsd:execute-phase 2`) or freeform text.
   - `verify`: a shell command that exits 0 only when the phase is truly done
     (e.g. `npm test`, `pytest -q`). This is the convergence gate — choose it
     carefully; without it, "ran once" counts as done.
   - optional: `tool`, `model`, `max_retries`, `depends_on`.
   See `templates/tasks.example.yaml`.

3. **Pick tools/models.** `cross-loop tools` lists what's configured. To add a
   tool, drop a `config/tools/<name>.yaml` — no code changes.

4. **Dry-run first**, then run for real:
   ```bash
   cross-loop run --tasks tasks.yaml --dry-run
   cross-loop run --tasks tasks.yaml --tool claude-code --model opus --yolo --max-retries 5 --cwd /path/to/project
   ```
   Re-running resumes: finished phases are skipped, so an interrupted loop just
   continues. `cross-loop status --tasks tasks.yaml` shows progress.

## How it works (so you can reason about it)

- One controlling process runs the loop; each phase is a **separate** `tool -p "..."`
  subprocess with a 100% fresh context. State lives in `tasks.state.json`, so the
  controller stays light and the loop is crash-resumable.
- A phase is `done` only when its `verify` passes. On failure the verify output is
  appended to the next attempt's prompt ("here's why it failed, fix it") up to
  `max_retries`, then the phase is marked `needs_attention`.
- Tools communicate only through the filesystem (the repo + state file), which is
  why you can mix heterogeneous CLIs across phases.

## Safety

`--yolo` enables flags like `--dangerously-skip-permissions`. Only run unattended
loops inside an **isolated checkout** (git worktree or container). Never run money
movement or trades. Prefer setting explicit allowed-tools in the tool config over a
blanket skip when you can.

## Reference

- `docs/architecture.md` — the design and the Ralph-loop pattern
- `docs/configuration.md` — tasks file + tool adapter schema
- `docs/install.md` — installing cross-loop and the skill into a harness
