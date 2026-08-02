# zsh

My personal Zsh configuration. Linux is the daily driver and therefore the
favored child; macOS is the work machine I SSH into and occasionally remember
to maintain.

> [!WARNING]
> This is **my** shell configuration. It is not a framework, a starter kit, a
> dotfile distribution, or a machine-independent delivery system for instant
> terminal enlightenment. It contains my aliases, my preferred tools, my PATH
> layout, my history policy, and functions for my hardware and operating
> systems. If you clone it directly onto your machine and expect magic, prepare
> for a fairly large disappointment. Read it, steal the useful pieces, and
> change the opinions that are not yours.

There is no plugin manager, setup wizard, dependency resolver, theme picker, or
support department. This is deliberate. A shell should start quickly and do
what its owner expects, not spend breakfast negotiating a dependency graph.

## What It Does

- Supports Linux and macOS with an explicit platform split.
- Keeps `.zshenv` cheap enough to run for every Zsh process.
- Loads interactive configuration in a fixed, readable order from `.zshrc`.
- Autoloads public functions on first use instead of parsing all of them during
  startup.
- Keeps history in `$XDG_STATE_HOME/zsh` and completion state in
  `$XDG_CACHE_HOME/zsh`; generated debris does not belong in Git.
- Selects installed modern CLI replacements such as `bat`, `eza`, `duf`, `gdu`,
  and `dust` while retaining sensible fallbacks.
- Initializes SDKMAN, Vite+, Bun, zoxide, direnv, fzf, and Starship when their
  files or commands are present.
- Loads autosuggestions, history substring search, and syntax highlighting from
  system package locations. Syntax highlighting is loaded last, because ZLE
  plugin ordering is one of those tiny rituals shell users learn through pain.
- Configures case-insensitive completion, colored results, cached metadata, and
  a versioned completion dump.
- Uses Emacs-style line editing with explicit terminal bindings for Home, End,
  Insert, Delete, arrows, word movement, prefix history search, and undo.
- Provides a collection of lazy utility commands, some generally useful and
  some extremely specific to the machines this repository actually serves.

## Things It Will Change

This configuration is intentionally opinionated. Among other choices:

- `cat` may become `bat`, `ls` may become `eza`, `df` may become `duf`, and `du`
  may become `gdu` or `dust` depending on what is installed.
- `vi` and `vim` become `nvim` when available.
- `cp` and `mv` are verbose, while `grep` is case-insensitive and colored.
- `sudo` has a trailing-space alias so the following command alias expands.
- `!` history expansion and terminal beeps are disabled.
- Commands beginning with a space, plus routine noise such as `pwd`, `clear`,
  `history`, `exit`, and `rm ...`, are excluded from persistent history.
- Page Up and Page Down search history from the prefix already typed. If the
  history-substring plugin is installed, it takes over those same keys.
- Ctrl-H kills the previous word and Shift-Tab performs undo. Yes, I meant that.
- Starship owns `PROMPT` when installed. Without it, Zsh keeps its default
  prompt and quietly judges your aesthetic restraint.

If any of that sounds surprising, excellent: the warning above is functioning.

## Startup Architecture

Only `~/.zshenv` needs to point into this repository. It resolves the repository
location and sets `ZDOTDIR`, after which Zsh finds `.zshrc` itself.

Every Zsh process loads:

1. `config/env/common.zsh` for XDG defaults and common paths.
2. `config/env/local.zsh` for ignored, host-specific overrides when present.
3. `config/env/linux.zsh` or `config/env/macos.zsh` for platform paths and
   environment.
4. `config/env/tools.zsh` for derived editor, pager, SDKMAN, Bun, uv, and other
   tool paths.

Interactive shells then load:

1. options;
2. history;
3. completion;
4. common aliases;
5. platform aliases;
6. keybindings;
7. interactive tool integrations;
8. ZLE plugins, with syntax highlighting last.

[`config/bootstrap.zsh`](config/bootstrap.zsh) provides the private source,
PATH, and autoload helpers used during those phases. Both entry points remove
the helpers afterward; they are scaffolding, not public shell commands.

## Repository Layout

```text
.
├── .zshenv                 every-shell entry point
├── .zshrc                  interactive load sequence
├── config/
│   ├── bootstrap.zsh       temporary initialization helpers
│   ├── env/
│   │   ├── common.zsh      XDG defaults and common environment
│   │   ├── local.zsh       ignored per-host overrides, if created
│   │   ├── linux.zsh       Linux environment and PATH
│   │   ├── macos.zsh       Homebrew, GNU tools, and macOS environment
│   │   └── tools.zsh       derived tool paths and editor/pager selection
│   └── rc/                 interactive options, history, completion, aliases,
│                           bindings, integrations, plugins, and platform bits
├── func/
│   ├── common/             portable lazy commands
│   ├── devtools/           development helpers
│   ├── linux/              Linux and machine-oriented helpers
│   └── macos/              Homebrew helpers
├── test.zsh                startup and behavior regression tests
├── .githooks/pre-commit    optional pre-commit check
└── AGENTS.md               architecture and maintenance invariants
```

Every file below `func/` defines the same function name as its filename. There
is no `cmd_` prefix, generated alias layer, or communal helper swamp. Zsh finds
the function through `fpath` and reads it only when invoked.

## Installation, Such As It Is

Requirements are Zsh and either Linux or macOS. Everything else is conditional,
although a command that wraps an absent external tool will obviously not summon
that tool from the void.

Place the repository wherever you want, then link its `.zshenv` into your home
directory:

```sh
ln -s /path/to/this/repository/.zshenv ~/.zshenv
exec zsh -l
```

Do not blindly run that over an existing `~/.zshenv`. Inspect and merge whatever
you already have, unless losing your previous shell setup is today's hobby.

For host-specific environment values, create the ignored file
`config/env/local.zsh`:

```zsh
# Loaded after common defaults and before platform/tool-derived paths.
export DOTDIR="$HOME/src/dotfiles"
export SDKMAN_DIR="$HOME/.local/share/sdkman"
```

That file is intentionally not tracked, so one machine's peculiarities do not
become everybody else's archaeological problem.

## Optional Software

The configuration detects optional tools instead of declaring a sacred install
manifest. Useful additions include:

- `starship`, `fzf`, `zoxide`, and `direnv` for interactive integration;
- `bat`, `eza`, `duf`, `gdu`/`gdu-go`, `dust`, and `nvim` for command aliases;
- `ov` or `less`, plus `lesspipe`, for paging;
- `zsh-autosuggestions`, `zsh-history-substring-search`, and
  `zsh-syntax-highlighting` installed beneath `/usr/share/zsh/plugins` on Linux
  or Homebrew's `share` directory on macOS;
- SDKMAN, Bun, Vite+, and uv when those ecosystems are relevant to the host.

Individual utility functions have their own dependencies. For example, the
Linux package wrapper expects `paru` or `yay`, `pulse-eq` expects EasyEffects,
and NVIDIA/IOMMU helpers make the bold assumption that the machine has NVIDIA
or IOMMU-related business to conduct.

## Lazy Commands

Common commands:

- `checksh` reports the active shell, prompt, aliases, command replacements, and
  versions of modern CLI tools.
- `ex FILE` extracts common archive formats.
- `func` lists or checks loaded shell functions.
- `jstatd` starts the Java monitoring daemon with a local policy file.
- `lint` syntax-checks the repository and runs its behavioral tests.
- `lsenv [PATTERN]` lists exported parameters with optional filtering.
- `lspath` prints PATH one entry per line.

Development commands:

- `fpath PATH [...]` prints absolute paths. The name predates anyone asking for
  naming advice.
- `gcc-flags` shows target flags enabled by the native GCC architecture.
- `venv` manages Python virtual environments, dependencies, tests, and a
  Uvicorn development server.

Linux adds `cpufreq`, `fixmirror`, `iommu`, `nvidia-cdi`, `os-release`, `pkg`,
`pulse-eq`, `sudo-conf`, and an `xdg-open` wrapper that prefers `handlr`.

macOS adds `beer` for Homebrew setup/removal, `pkg` as a small Homebrew command
dispatcher, and `svc` for Homebrew services.

These commands are personal conveniences, not a stable public API. If you build
automation around them and I later rename one, you have discovered why software
projects normally have maintainers other than their sole user.

## State, Cache, and History

Runtime data lives outside the working tree:

```text
$XDG_STATE_HOME/zsh/history              persistent command history
$XDG_CACHE_HOME/zsh/zcompdump-$ZSH_VERSION
$XDG_CACHE_HOME/zsh/completion/          completion-function caches
```

The completion dump receives a full refresh after 24 hours; younger dumps use
the faster cached initialization path. History is shared between live shells,
deduplicated, locked with `fcntl`, and capped at 50,000 entries by default.

## Debugging and Diagnostics

Trace initialization and report startup time:

```sh
ZSH_DEBUG_INIT=1 zsh -l
```

This prints sourced files, registered autoloads, and the elapsed startup time,
which is more actionable than staring accusingly at the terminal.

Inspect the active environment and command replacements:

```sh
checksh
```

If Starship ever appears as a literal `$(starship prompt ...)` command, verify
that `PROMPT_SUBST` remains enabled. There is a regression test for this now,
because apparently even prompts require adult supervision.

## Development and Verification

After changing initialization or an autoloaded function, run both supported
checks from the repository root:

```zsh
ZDOTDIR="$PWD" zsh -df test.zsh
ZDOTDIR="$PWD" zsh -d -i -c 'lint'
```

`lint` syntax-checks every Zsh source file and then executes `test.zsh`. The
tests cover initialization cleanup, XDG state placement, prompt substitution,
history filtering, opinionated aliases, public autoloads, and selected function
behavior.

The opt-in pre-commit hook runs the same behavioral test after checking staged
shell files:

```sh
git config core.hooksPath .githooks
```

It is opt-in because silently changing repository-local Git configuration would
be rude, even by the standards of a repository that aliases `cat`.

See [`AGENTS.md`](AGENTS.md) before changing the architecture. It records the
load-order and maintenance invariants that future me—or a suspiciously confident
automation agent—must preserve.

## License

[MIT](LICENSE). Take whatever is useful. If you install the whole thing unchanged
and your shell becomes an uncanny impersonation of mine, that is not a bug in
the license.
