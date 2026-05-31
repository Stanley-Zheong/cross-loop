# Configuration

There are three files involved: the **global config**, the **tool adapters**,
and the **tasks file**.

## Global config (`cross-loop.yaml`)

Defaults for a run. Any value can be overridden by a per-task setting or a CLI
flag. See `config/cross-loop.example.yaml`.

| Key | Default | Meaning |
|-----|---------|---------|
| `default_tool` | `claude-code` | tool used when a phase names none |
| `max_retries` | `3` | convergence budget per phase |
| `stop_on_failure` | `false` | halt the loop when a phase exhausts retries |
| `timeout` | `0` | per-attempt timeout in seconds (0 = none) |
| `tools_dir` | `./config/tools` | where adapter files live |

Resolution order for the global config path: `--config` → `$CROSS_LOOP_CONFIG`
→ `./cross-loop.yaml` → `./config/cross-loop.yaml` → built-in defaults.

## Tool adapter (`config/tools/<name>.yaml`)

Describes how to invoke one CLI. Adding a new tool is just a new file here — no
code changes.

| Key | Required | Meaning |
|-----|----------|---------|
| `command` | yes | the executable, e.g. `claude`, `codex`, `cursor-agent` |
| `prompt_args` | no (default `["{prompt}"]`) | argv to pass one headless prompt; `{prompt}` is substituted |
| `model_args` | no | argv to select a model; `{model}` is substituted; omitted if no model |
| `autonomous_args` | no | extra argv added only when `--yolo` is set |
| `default_model` | no | model used when none is specified |
| `models` | no | list of known models (shown by `cross-loop tools`) |
| `supports_slash_commands` | no | informational: can the prompt contain slash commands |

### How an invocation is assembled

```
<command> [model_args with {model}] [autonomous_args if --yolo] [prompt_args with {prompt}]
```

The prompt is always a single argv element passed without a shell, so slash
commands and arbitrary text are safe. Example for Claude Code:

```
claude --model opus --dangerously-skip-permissions -p "/gsd:execute-phase 2"
```

> The flag templates shipped for codex / cursor / opencode are best-effort
> defaults. Confirm them against your installed versions and edit freely —
> that's the whole point of these being plain YAML.

## Tasks file (`tasks.yaml`)

The decomposed spec. See `templates/tasks.example.yaml`.

Top level:

| Key | Meaning |
|-----|---------|
| `project` | optional label |
| `cwd` | optional working directory for the tools (overridden by `--cwd`) |
| `defaults` | `tool` / `model` / `max_retries` applied to every phase |
| `tasks` | the ordered list of phases |

Per phase:

| Key | Required | Meaning |
|-----|----------|---------|
| `id` | yes | unique slug; used as the state key |
| `prompt` (or `command`) | yes | what the tool should do this phase |
| `verify` | no | shell command; phase is `done` only when it exits 0 |
| `tool` | no | override the tool for this phase |
| `model` | no | override the model for this phase |
| `max_retries` | no | override the retry budget for this phase |
| `depends_on` | no | list of phase ids that must be done first |

### Precedence

For tool / model / max_retries, the winner is:

```
CLI flag  >  per-phase value  >  defaults block  >  tool default / global default
```

## State file (`tasks.state.json`)

Written automatically next to the tasks file (or wherever `--state` points).
Holds each phase's status, attempt count, and a tail of the last output. Delete
it (or run `cross-loop reset --tasks ...`) to start over. Re-running `run`
resumes from it, so an interrupted overnight build just continues.
