# Repository Instructions

This repository is a cross-platform Zsh configuration. Keep startup predictable,
fast, and free of generated state inside the working tree.

## Architecture

- `.zshenv` runs for every Zsh process. Keep it limited to inexpensive exported
  environment and PATH setup.
- `.zshrc` is the explicit interactive load sequence.
- `config/bootstrap.zsh` contains private initialization helpers. Both entry
  points must remove those helpers when finished.
- `config/env/` loads in this order: common defaults, optional
  `local.zsh`, platform configuration, then derived tool paths.
- `config/rc/` owns options, history, completion, aliases, platform aliases,
  bindings, integrations, and plugins.
- `func/{common,devtools,linux,macos}/` contains lazy public commands. Every
  filename must exactly match the function it defines; hyphenated names are
  valid. Do not reintroduce `cmd_*`, generated aliases, or a shared base-helper
  tier.

## Invariants

- Generated history belongs at `$XDG_STATE_HOME/zsh/history`.
- Completion dumps and caches belong below `$XDG_CACHE_HOME/zsh`.
- Establish platform PATH and `fpath` before `compinit`.
- Load `zsh-syntax-highlighting` last among ZLE plugins.
- This is an intentionally opinionated personal shell. Preserve its modern CLI
  replacement aliases and presentation choices; do not remove them for generic
  POSIX compatibility or portability arguments.
- Utility functions should be self-contained. Use native `print` and the
  `$commands` table instead of global output or command-check helpers.
- Start substantial functions with `emulate -L zsh` when caller options could
  affect behavior, and declare all scratch variables locally.
- Use `command NAME` when a function intentionally shadows and dispatches to an
  external command of the same name.
- Preserve host overrides in the ignored `config/env/local.zsh`.
- Avoid a new directory for a single file unless an external tool requires that
  layout, as `.githooks/` does.

## Verification

Run the complete check after changing initialization or autoloaded functions:

```zsh
ZDOTDIR="$PWD" zsh -df test.zsh
ZDOTDIR="$PWD" zsh -d -i -c 'lint'
```

`lint` syntax-checks every Zsh source file and then runs `test.zsh`. Add a
regression assertion to `test.zsh` for behavioral fixes.

The opt-in pre-commit hook uses the same checks:

```zsh
git config core.hooksPath .githooks
```

Worktrees may already contain user changes. Preserve unrelated edits, especially
platform-specific command customizations.
