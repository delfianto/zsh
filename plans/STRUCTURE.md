# Project Structure

```
~/.config/zsh/                    # ZDOTDIR — all zsh config lives here
├── .zshenv                       # Entry point: sourced for ALL shells (login, interactive, scripts)
├── .zshrc                        # Interactive shell config: options, keybindings, plugins, tool init
├── mod.yml                       # Dotfile manager manifest (symlink rules)
│
├── environment/                  # Environment variables, sourced early in .zshenv
│   ├── linux.env                 # Linux: XDG dirs, ZDOTDIR, DOTDIR, LS_ARGS, Docker env
│   ├── macos.env                 # macOS: ZDOTDIR, DOTDIR, Homebrew vars, LS_ARGS
│   ├── devtools.env              # Cross-platform: dev tool config (bun, uv)
│   └── local.env                 # Host-specific overrides (gitignored, not committed)
│
├── bootstrap/                    # Runtime initialization, sourced in .zshrc
│   ├── macos                     # macOS: keychain unlock, brew shellenv, GNU coreutils PATH
│   ├── linux                     # Linux: static aliases (hdmon, pacman, dmesg, etc.)
│   └── common                    # Cross-platform: cmd_* auto-aliasing, tool replacement aliases
│
├── autoload/                     # Lazy-loaded functions organized by category
│   ├── base/                     # Core helpers (loaded in .zshenv for all shells)
│   │   ├── add_path              # Validate and prepend/append a directory to PATH
│   │   ├── has_cmd               # Check if a command exists in PATH
│   │   ├── stderr                # Print to stderr
│   │   └── stdout                # Print to stdout
│   │
│   ├── common/                   # Cross-platform utility commands
│   │   ├── cmd_checksh           # Shell environment diagnostic tool
│   │   ├── cmd_ex                # Universal archive extractor
│   │   ├── cmd_func              # List/check defined shell functions
│   │   ├── cmd_jstatd            # Start Java jstatd with auto-generated policy
│   │   ├── cmd_lsenv             # Search and display environment variables
│   │   └── cmd_lspath            # Pretty-print PATH entries
│   │
│   ├── devtools/                 # Development tool commands
│   │   ├── cmd_fpath             # Resolve file paths (realpath wrapper/fallback)
│   │   ├── cmd_gcc_flags         # Show GCC native architecture flags
│   │   └── cmd_venv              # Python venv management (init, load, deps, run, test)
│   │
│   ├── linux/                    # Linux-only commands
│   │   ├── cmd_cpufreq           # Monitor CPU frequency per core
│   │   ├── cmd_iommu             # IOMMU group inspector (PCI, USB)
│   │   ├── cmd_os_release        # Parse /etc/os-release (shell or JSON output)
│   │   ├── cmd_pkg               # Unified package manager wrapper (paru/yay/pacman)
│   │   ├── cmd_pulse_eq          # EasyEffects preset switcher
│   │   ├── cmd_sudo_conf         # Edit sudoers config via visudo
│   │   └── cmd_xdg_open          # Open files with handlr or xdg-open
│   │
│   └── macos/                    # macOS-only commands
│       ├── cmd_beer              # Homebrew install/uninstall helper
│       ├── cmd_pkg               # Unified Homebrew package manager wrapper
│       └── cmd_svc               # Homebrew services management
│
├── plans/                        # Project documentation
│   ├── README.md                 # Change log and fix tracker
│   ├── STRUCTURE.md              # This file
│   └── ARCHITECTURE.md           # How the init system works
│
├── .gitignore                    # Ignores: cache, history, .zcompdump, local.env
├── LICENSE                       # Project license
└── mod.yml                       # Symlink manifest: .zshenv → $HOME, rest → $XDG_CONFIG_HOME
```

## Symlink Setup

Managed via `mod.yml`. The dotfile manager creates:
- `~/.zshenv` → `~/.config/zsh/.zshenv` (the only file in $HOME)

Zsh then discovers the rest via `ZDOTDIR` which `.zshenv` derives from its own
resolved path. No other symlinks are needed.

## Gitignored Files

| Pattern | Reason |
|---------|--------|
| `cache/` | Completion cache (regenerated automatically) |
| `*.zcompdump` | Compiled completion dump |
| `*.zsh_history` | Shell history |
| `*.histfile` | Shell history (alternate name) |
| `*.lock` | Lock files |
| `local.env` | Host-specific secrets/overrides |
| `.zsh_sessions/` | macOS Terminal.app session restore |
| `.zinit/` | Legacy plugin manager artifacts |
| `myconf/` | User-specific config not for version control |
