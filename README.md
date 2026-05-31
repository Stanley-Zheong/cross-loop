# cross-loop

> A tiny orchestration layer that drives **multiple AI coding CLIs** — Claude Code, Codex, Cursor, OpenCode and more — through a phase-based, **self-verifying build loop**.

cross-loop is the small skill that pulls a big lever. By itself it is just a state machine plus a dispatcher: a few hundred lines of Python. But once you have capable CLI tools installed and configured (with their models, plus extensions like Superpowers, GSD, GStack, RalphLoop), cross-loop chains them together — each phase running in a **fresh, isolated process** — so a large project can be built phase by phase, overnight, unattended.

## The idea in one picture

```
tasks.yaml (N phases, each a prompt + a verify command)
        │
        ▼
  ┌───────────────┐      reads/writes      ┌──────────────┐
  │  cross-loop   │ ───────────────────────│  state.json  │
  │ (orchestrator)│                         └──────────────┘
  └──────┬────────┘
         │ for each unfinished phase: spawn a FRESH process
         ▼
   claude -p "..."        ← phase 1   (Claude Code + Superpowers/GSD/GStack)
   codex exec "..."       ← phase 2   (or any other configured tool)
   cursor-agent "..."     ← phase 3
         │
         ▼
   verify (e.g. `npm test`) → pass? mark done : feed failure back & retry
```

The orchestrator itself stays tiny and near-stateless — **all real state lives on disk** (`state.json` + your repo). That is what keeps the controlling session's context clean while dozens of headless sub-processes do the heavy lifting. This is the "Ralph loop" pattern: a dumb, durable loop over a persistent state file.

## Why it matters

Tools like Superpowers (TDD execution), GStack (multi-role decisions) and GSD (phase decomposition to avoid context rot) are **not separate programs** — they are extensions to coding CLIs. cross-loop does not reimplement them. It assumes you've installed them into one or more CLIs and simply **schedules** those CLIs in the best combination per phase:

- **Decompose** your spec into phases, each small enough to fit one clean context window (GSD-style). Write them into a `tasks.yaml`.
- **Dispatch** each phase to a configured tool/model in a brand-new process (100% fresh context).
- **Verify** with a real command (tests, linters, an eval). Only a passing verify marks a phase *done*.
- **Converge**: on failure, the failure output is fed back into the next attempt, up to a retry limit — automatic bug-fixing by iteration.
- **Mix tools**: run phase 1 on Claude Code, phase 3 on Codex — they communicate only through the filesystem, so heterogeneous tools compose naturally.

## Quick start

```bash
# 1. install
pipx install .            # or: pip install -e .

# 2. see which tools are configured and what models they expose
cross-loop tools

# 3. dry-run a task file to preview the exact commands
cross-loop run --tasks examples/hello-app/tasks.yaml --dry-run

# 4. run for real, unattended, on Claude Code with Opus
cross-loop run --tasks examples/hello-app/tasks.yaml \
  --tool claude-code --model opus --yolo --max-retries 5

# 5. check progress / resume (re-running only picks up unfinished phases)
cross-loop status --tasks examples/hello-app/tasks.yaml
```

## Scheduling parameters

| Flag | Meaning |
|------|---------|
| `--tasks PATH` | the phase/task file (YAML). **Required.** |
| `--tool NAME` | override the tool for every phase (must match a file in `config/tools/`) |
| `--model NAME` | override the model for every phase |
| `--max-retries N` | convergence budget per phase |
| `--yolo` | enable a tool's unattended/autonomous flags (e.g. `--dangerously-skip-permissions`) |
| `--stop-on-failure` | halt the whole loop if a phase exhausts its retries |
| `--state PATH` | where to persist progress (default: alongside the tasks file) |
| `--cwd PATH` | working directory the tools run in (your project repo) |
| `--timeout SECS` | per-attempt timeout |
| `--dry-run` | print the commands without executing |

Per-phase overrides (`tool:`, `model:`, `max_retries:`, `verify:`, `depends_on:`) live inside `tasks.yaml` and take precedence over global defaults but yield to explicit command-line flags.

## Adding a new CLI tool

Drop a YAML file in `config/tools/<name>.yaml` describing its command template, how it takes a prompt, how it takes a model, and which models it exposes. No code changes required. See [`docs/configuration.md`](docs/configuration.md).

## Installing as a skill

cross-loop ships a [`SKILL.md`](SKILL.md) so an agent runtime (Claude Code, Cowork, Hermes, OpenClaw, or any harness that loads SKILL.md-format skills) can drive it automatically. See [`docs/install.md`](docs/install.md).

## Safety

`--yolo` turns on flags like `--dangerously-skip-permissions`. Run unattended loops in an **isolated checkout** (a git worktree or container), never directly on a repo you can't afford to have rewritten. cross-loop never moves money or executes trades. See the safety notes in [`docs/install.md`](docs/install.md).

## License

MIT — see [LICENSE](LICENSE).
