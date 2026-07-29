# Architecture

## Init Flow

Zsh processes startup files in a specific order. This config uses two of them:

```
1. .zshenv    (every shell: login, interactive, scripts, SSH)
2. .zshrc     (interactive shells only)
```

### Phase 1: `.zshenv` — Environment Setup

Runs for every zsh invocation. Sets up the environment that all shells need.

**The dividing line**: if only a human at a prompt cares about it, it belongs in
`.zshrc`. History, ZLE, keybindings, prompt tools and man-page colors are all
interactive-only — putting them here makes every `zsh -c` in every script pay
for them. `EDITOR`/`VISUAL`/`PAGER`/`LESS` do stay here, because scripts and
tools invoked non-interactively read them.

```
.zshenv
  │
  ├─ Start the debug timer (ZSH_DEBUG_INIT=1)
  │    Started here, not in .zshrc, so the reported total covers both phases.
  │
  ├─ Detect OS ($OSNAME: "linux" | "macos" | "unknown")
  │
  ├─ Derive ZDOTDIR from this file's real path
  │    Uses ${(%):-%x} to get the source file, :A to resolve symlinks,
  │    :h to get the directory. Works regardless of where the symlink is.
  │
  ├─ typeset -aU path
  │    Marks the $path array as unique — deduplicates PATH automatically.
  │
  ├─ Define init helpers (temporary, removed at end of .zshrc):
  │    import()        — source files from a base directory, skip missing
  │    autoload_init() — register autoload dirs in fpath, autoload all functions
  │
  ├─ autoload_init "base"
  │    Loads core helpers (has_cmd, add_path, stdout, stderr) for ALL shells.
  │    Non-interactive shells (scripts, cron) get these too.
  │
  ├─ import environment/{$OSNAME.env, devtools.env, local.env}
  │    Sets platform-specific vars: HOMEBREW_PREFIX, XDG dirs, LS_ARGS, etc.
  │    local.env is gitignored for host-specific overrides.
  │
  └─ Global exports: VISUAL, EDITOR, PAGER, LESS, LESSOPEN
       Deliberately NOT here: HISTSIZE/SAVEHIST/HISTFILE/HISTORY_IGNORE,
       WORDCHARS, ZLE_*, READNULLCMD, LESS_TERMCAP_* — see .zshrc.
```

### Phase 2: `.zshrc` — Interactive Shell

Only runs for interactive sessions. Handles everything the user sees and touches.

```
.zshrc
  │
  ├─ Interactive-only environment
  │    History (HISTFILE/HISTSIZE/SAVEHIST/HISTORY_IGNORE), WORDCHARS,
  │    ZLE_*, READNULLCMD, LESS_TERMCAP_* man-page colors.
  │
  ├─ autoload_init "common" "devtools" "$OSNAME"
  │    Registers all remaining autoload functions in fpath.
  │    Functions are lazy — only loaded into memory on first call.
  │
  ├─ compinit (cached, regenerated once per day)
  │
  ├─ Shell options (setopt), completion styles (zstyle), keybindings (bindkey)
  │
  ├─ import interactive/{$OSNAME, common}   ← OS before common (order matters!)
  │    │
  │    ├─ interactive/$OSNAME:
  │    │    macOS: keychain unlock, brew shellenv, GNU coreutils PATH
  │    │    Linux: static system aliases
  │    │
  │    └─ interactive/common:
  │         1. Auto-alias all cmd_* functions to kebab-case (see below)
  │         2. Tool replacement aliases (bat→cat, eza→ls, duf→df, etc.)
  │         3. Static aliases (cp -v, grep --color, etc.)
  │
  ├─ hash -r
  │    Rebuilds command hash table after interactive init modified PATH.
  │    Critical on macOS where brew shellenv adds /opt/homebrew/bin.
  │
  ├─ Tool initialization (fzf, zoxide, direnv, starship, bun completions)
  │    Each guarded by has_cmd — silently skipped if not installed.
  │    direnv lives here, not in an .env file: its hook only fires at a prompt.
  │
  ├─ Plugins, sourced LAST (platform-aware paths)
  │    zsh-autosuggestions → zsh-syntax-highlighting → zsh-history-substring-search
  │    Order matters: syntax-highlighting must wrap every ZLE widget defined
  │    above it, which is why this comes after fzf/zoxide and not before.
  │
  └─ Cleanup: unset import(), autoload_init() and the init-only scratch vars
```

## Key Design Decisions

### Autoload Convention: `cmd_*` → Kebab-case Aliases

Functions named `cmd_foo_bar` in autoload directories are automatically aliased
to `foo-bar` by `interactive/common`. The conversion:

1. Scan all loaded functions for names matching `cmd_*`
2. Convert underscores to hyphens, strip the `cmd-` prefix
3. Create an alias only if no command with that name already exists

Example: `cmd_os_release` → alias `os-release` → calls `cmd_os_release`

The existence check uses `whence -w`, which covers external binaries, functions,
builtins, aliases and reserved words. (`has_cmd` only looks at `$commands`, and
the `$+assoc[key]` form is unusable inside `(( ))` — the subscript gets
math-evaluated, so a key like `fpath` expands to the array's contents.)

**Shadow rules**: step 3 silently disables every wrapper written *because* the
original command exists — `cmd_xdg_open`, `cmd_ex`, `cmd_jstatd` all lost their
alias this way. Names listed in a `shadow_cmd` file are allowed to take over
anyway. Two files are read, in order:

| File | Tracked | Purpose |
|------|---------|---------|
| `$ZDOTDIR/shadow_cmd` | yes | Repo defaults (`ex`, `xdg-open`, `jstatd`) |
| `$MYCONF/shadow_cmd` | no | Host-specific additions |

Anything skipped is recorded in `$ZSH_ALIAS_SKIPPED` and reported by `checksh`,
so a missing alias is visible instead of silent.

### Tool Replacement Chain

Aliases for core commands follow a priority chain, preferring modern Rust/Go
replacements over system defaults:

| Command | Priority chain |
|---------|---------------|
| `ls` | eza → gls → GNU ls → BSD ls |
| `du` | gdu → gdu-go → dust → du -h |
| `df` | duf → df -h |
| `cat` | bat → cat |
| `vi/vim` | nvim → vi/vim |

The `ls` chain also detects whether the fallback `ls` is GNU or BSD (via a
`--color=auto` probe) and adjusts flags accordingly.

### Platform Detection and Separation

Three-layer approach:

| Layer | Linux | macOS | Both |
|-------|-------|-------|------|
| **environment/** | linux.env | macos.env | devtools.env, local.env |
| **interactive/** | linux | macos | common |
| **autoload/** | autoload/linux/ | autoload/macos/ | autoload/base/, common/, devtools/ |

The OS is detected once in `.zshenv` via `$OSTYPE` and stored in `$OSNAME`.
All subsequent platform branching uses this variable.

### ZDOTDIR Self-Discovery

The config lives at `~/.config/zsh/` but zsh needs `ZDOTDIR` to find it.
Instead of hardcoding the path, `.zshenv` derives it from its own location:

```zsh
export ZDOTDIR="${ZDOTDIR:-${${(%):-%x}:A:h}}"
```

- `${(%):-%x}` — path of the file currently being sourced
- `:A` — resolve symlinks (follows `~/.zshenv` → `~/.config/zsh/.zshenv`)
- `:h` — directory part

This means the config works on any machine with just one symlink:
`~/.zshenv → ~/.config/zsh/.zshenv`

### Interactive Init Source Order

`.zshrc` sources the OS interactive file **before** common:

```zsh
import "${ZDOTDIR}/interactive" "${OSNAME}" "common"
```

This is critical because:
1. `interactive/macos` runs `brew shellenv` which adds `/opt/homebrew/bin` to PATH
2. `interactive/common` checks for tools like `eza`, `gls`, `bat` in PATH
3. If common ran first, it wouldn't find Homebrew-installed tools

### Debug Mode

Set `ZSH_DEBUG_INIT=1` before starting a shell to trace the entire init:

```sh
ZSH_DEBUG_INIT=1 zsh -l
```

This prints every file loaded, every function autoloaded, and measures total
startup time using `$EPOCHREALTIME` (works on both Linux and macOS).
