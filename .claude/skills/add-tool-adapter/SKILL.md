---
name: add-tool-adapter
description: Add support for a new AI coding CLI to cross-loop by writing a config/tools/<name>.yaml adapter. Use when asked to "add a tool", "support <CLI>", or "write an adapter" for cross-loop. No Python changes needed.
---

# Add a tool adapter

cross-loop supports a new CLI purely by adding `config/tools/<name>.yaml` — no code changes. The dispatcher reads the adapter to build argv.

## Steps

1. Read an existing adapter as a template — `config/tools/claude-code.yaml` is the most fully annotated.
2. Find out, from the target CLI's `--help`, how it:
   - runs a single **non-interactive / headless** prompt,
   - selects a **model**,
   - runs **fully unattended** (skip-permission or allow-list flags).
3. Create `config/tools/<name>.yaml` with these fields:
   - `name` — adapter id (matches the filename).
   - `command` — the executable to invoke.
   - `prompt_args` — argv to run one headless prompt; use `{prompt}` as the placeholder.
   - `model_args` — argv to select the model; use `{model}` placeholder.
   - `autonomous_args` — flags enabled only under `--yolo` (e.g. skip-permissions). Prefer an explicit allow-list over a blanket skip where the CLI supports it.
   - `default_model` and `models` — the list of selectable models.
   - `supports_slash_commands` — true if the CLI honors slash commands embedded in the prompt string.
4. Verify the flags against the actually-installed version of the CLI before committing — comments in the adapters warn that flags drift between versions.
5. Test: `cross-loop tools` should list the new adapter; then `cross-loop run --tasks <tasks.yaml> --tool <name> --model <model>`.

## Safety note

`autonomous_args` runs the underlying tool unattended. Keep it minimal, and remind the user it should only run inside an isolated worktree or container.
