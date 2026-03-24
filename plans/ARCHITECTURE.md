# Architecture

## Init Flow

Zsh processes startup files in a specific order. This config uses two of them:

```
1. .zshenv    (every shell: login, interactive, scripts, SSH)
2. .zshrc     (interactive shells only)
```

### Phase 1: `.zshenv` — Environment Setup

Runs for every zsh invocation. Sets up the environment that all shells need.

```
.zshenv
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
  └─ Global exports: HISTORY_IGNORE, HISTSIZE, VISUAL, EDITOR, PAGER, LESS, etc.
```

### Phase 2: `.zshrc` — Interactive Shell

Only runs for interactive sessions. Handles everything the user sees and touches.

```
.zshrc
  │
  ├─ Optional: debug timing (ZSH_DEBUG_INIT=1 to measure startup time)
  │
  ├─ autoload_init "common" "devtools" "$OSNAME"
  │    Registers all remaining autoload functions in fpath.
  │    Functions are lazy — only loaded into memory on first call.
  │
  ├─ compinit (cached, regenerated once per day)
  │
  ├─ Shell options (setopt), completion styles (zstyle), keybindings (bindkey)
  │
  ├─ Plugin loading (platform-aware paths):
  │    zsh-autosuggestions, zsh-syntax-highlighting, zsh-history-substring-search
  │
  ├─ import bootstrap/{$OSNAME, common}     ← OS before common (order matters!)
  │    │
  │    ├─ bootstrap/$OSNAME:
  │    │    macOS: keychain unlock, brew shellenv, GNU coreutils PATH
  │    │    Linux: static system aliases
  │    │
  │    └─ bootstrap/common:
  │         1. Auto-alias all cmd_* functions to kebab-case (see below)
  │         2. Tool replacement aliases (bat→cat, eza→ls, duf→df, etc.)
  │         3. Static aliases (cp -v, grep --color, etc.)
  │
  ├─ hash -r
  │    Rebuilds command hash table after bootstrap modified PATH.
  │    Critical on macOS where brew shellenv adds /opt/homebrew/bin.
  │
  ├─ Tool initialization (fzf, zoxide, starship)
  │    Each guarded by has_cmd — silently skipped if not installed.
  │
  └─ Cleanup: unset import() and autoload_init()
```

## Key Design Decisions

### Autoload Convention: `cmd_*` → Kebab-case Aliases

Functions named `cmd_foo_bar` in autoload directories are automatically aliased
to `foo-bar` by `bootstrap/common`. The conversion:

1. Scan all loaded functions for names matching `cmd_*`
2. Convert underscores to hyphens, strip the `cmd-` prefix
3. Create an alias only if no command with that name already exists

Example: `cmd_os_release` → alias `os-release` → calls `cmd_os_release`

**Shadow rules**: A file at `$MYCONF/shadow_cmd` can list command names that
are allowed to shadow existing commands (override the "don't alias if exists" check).

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
| **bootstrap/** | linux | macos | common |
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

### Bootstrap Source Order

`.zshrc` sources OS bootstrap **before** common:

```zsh
import "${ZDOTDIR}/bootstrap" "${OSNAME}" "common"
```

This is critical because:
1. `bootstrap/macos` runs `brew shellenv` which adds `/opt/homebrew/bin` to PATH
2. `bootstrap/common` checks for tools like `eza`, `gls`, `bat` in PATH
3. If common ran first, it wouldn't find Homebrew-installed tools

### Debug Mode

Set `ZSH_DEBUG_INIT=1` before starting a shell to trace the entire init:

```sh
ZSH_DEBUG_INIT=1 zsh -l
```

This prints every file loaded, every function autoloaded, and measures total
startup time using `$EPOCHREALTIME` (works on both Linux and macOS).
