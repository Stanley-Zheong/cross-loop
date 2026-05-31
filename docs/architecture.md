# Architecture

cross-loop is deliberately small. Its only job is to **schedule** capable coding
CLIs; the intelligence lives in those tools and their extensions.

## The Ralph-loop pattern

The core idea (popularised as the "Ralph" / RalphLoop pattern): a dumb loop over
a durable state file. The loop has almost no memory of its own — it reads the
state file, finds the next unfinished unit of work, spawns a fresh worker to do
it, records the outcome, and repeats. Because nothing important lives in the
loop's own memory, the controlling process stays tiny and the whole thing is
crash-resumable: kill it, restart it, and it picks up exactly where it left off.

```
            ┌──────────────────────────────────────────────┐
            │                cross-loop                     │
            │              (controller)                     │
            │                                               │
   tasks ──▶│  read state ─▶ pick next ─▶ dispatch ─▶ verify│
            │      ▲                                    │    │
            │      └────────── record outcome ◀─────────┘    │
            └───────────────────┬───────────────────────────┘
                                │ spawns a FRESH process per phase
       ┌────────────────────────┼────────────────────────┐
       ▼                        ▼                         ▼
  claude -p "..."         codex exec "..."         cursor-agent -p "..."
  (fresh context)         (fresh context)          (fresh context)
       │                        │                         │
       └──────── all write to the same repo on disk ──────┘
```

## Why fresh processes

Long-lived agent sessions suffer "context rot": as the window fills, accuracy
drops. By giving every phase its own process, each worker starts at ~100% free
context. The controller never accumulates the workers' context at all — in
practice it sits near-idle while dozens of workers come and go. State is passed
between them not in memory but through two durable channels:

1. the **repository** itself (code the previous phase wrote), and
2. the **state file** (`*.state.json`: which phases are done, attempts, last output).

## Components

| Module | Responsibility |
|--------|----------------|
| `cli.py` | argument parsing, subcommands (`run` / `status` / `reset` / `tools`) |
| `config.py` | load global config + per-tool adapter YAML |
| `state.py` | the durable JSON state machine (pending → running → done / needs_attention) |
| `dispatch.py` | translate (tool, model, prompt) into an argv and run it |
| `verify.py` | run the convergence gate (a shell command, exit 0 = pass) |
| `loop.py` | the loop: order phases, dispatch, verify, retry-with-feedback |

## Convergence (retry with feedback)

A phase is not "done because it ran" — it is done because its `verify` command
passed. On failure, the verify output is appended to the next attempt's prompt
("previous attempt failed, here's the output, fix it"). This is automatic
bug-fixing by iteration, bounded by `max_retries`. It mirrors eval-driven
convergence: keep trying, feed the gap back in, stop when a measurable signal
says success — or when the budget runs out (then the phase is flagged
`needs_attention` and, unless `--stop-on-failure`, the loop moves on).

The quality of the loop is only as good as the `verify` command. A real test
suite or eval is a strong gate; "the command exited" is a weak one.

## Mixing tools

Because workers coordinate only through the filesystem, the controller doesn't
care which binary executes a phase. Phase 1 can run on Claude Code (with
Superpowers/GSD/GStack), phase 3 on Codex. The trade-off: tool-specific
extensions only apply where that tool runs — a Codex phase won't get Superpowers'
TDD auto-trigger. Phase decomposition (GSD) is tool-agnostic and always helps.

## What cross-loop is not

- Not a replacement for Superpowers / GSD / GStack — it *schedules* tools that
  have those installed.
- Not a model. Every worker is whatever model the chosen CLI runs.
- Not a sandbox. Run unattended loops inside your own isolation (worktree/container).
