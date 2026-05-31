# Installing cross-loop

## 1. Install the CLI

```bash
# from a clone of this repo
pipx install .          # isolated, recommended
# or
pip install -e .        # editable, for hacking on cross-loop itself
```

This puts a `cross-loop` command on your PATH. It requires Python ≥ 3.9 and
pulls in PyYAML.

Verify:

```bash
cross-loop --version
cross-loop tools          # lists configured tools + models
```

## 2. Install the coding CLIs you want to drive

cross-loop drives other tools; install whichever you plan to use, e.g. Claude
Code, Codex, Cursor's `cursor-agent`, or OpenCode — along with their models and
any extensions (Superpowers, GSD, GStack, RalphLoop). Then confirm the command
names/flags in `config/tools/<name>.yaml` match your installed versions.

## 3. Point cross-loop at your configs

By default cross-loop looks for `./config/tools/` and `./cross-loop.yaml`
(or `./config/cross-loop.yaml`). Override with flags or environment variables:

```bash
export CROSS_LOOP_TOOLS_DIR=/path/to/config/tools
export CROSS_LOOP_CONFIG=/path/to/cross-loop.yaml
```

Copy `config/cross-loop.example.yaml` to `cross-loop.yaml` and edit defaults.

## 4. Install as a skill (agent harnesses)

cross-loop ships a `SKILL.md` at the repo root, so any runtime that loads
SKILL.md-format skills can drive it automatically. The mechanism is the same
across harnesses — make the skill directory discoverable:

- **Claude Code / Cowork:** place (or symlink) the repo inside your skills
  directory, e.g. `~/.claude/skills/cross-loop/`, so `SKILL.md` is at its root.
- **Hermes / OpenClaw (and other SKILL.md-compatible harnesses):** add the repo
  to the harness's skills/plugins path per that harness's docs. The harness reads
  the YAML frontmatter in `SKILL.md` (name + description) to decide when to load
  it; the body tells the agent how to build a `tasks.yaml` and call `cross-loop run`.

A minimal layout the harness needs to see:

```
cross-loop/
├── SKILL.md            ← frontmatter (name/description) + instructions
├── cross_loop/         ← the engine (importable / `cross-loop` CLI)
├── config/tools/*.yaml ← adapters
├── templates/          ← tasks.example.yaml
└── docs/
```

Make sure the `cross-loop` CLI is installed (step 1) and on the PATH the harness
uses, since the skill shells out to it.

## Safety checklist for unattended runs

- Run inside an **isolated checkout**: `git worktree add ../run-xyz` or a container.
- Prefer explicit allowed-tools in the tool config over `--yolo`
  (`--dangerously-skip-permissions`) when you can.
- Set a `--timeout` so a stuck phase can't hang forever.
- Keep `max_retries` finite (it is by default) so a hopeless phase can't burn
  tokens indefinitely.
- cross-loop will never move money or place trades; don't wire such actions into
  a `verify` or `prompt`.
