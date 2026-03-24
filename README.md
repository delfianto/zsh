# zsh

My zsh config. Cross-platform between Linux (daily driver, the real one) and macOS (the work machine I SSH into and pretend to care about).

One symlink to rule them all: `~/.zshenv` points here, and the rest figures itself out.

## What This Does

- Detects the OS once, branches everywhere else
- Lazy-loads functions so shell startup doesn't feel like booting a JVM
- Swaps out ancient coreutils for modern Rust/Go alternatives when available (bat, eza, fd, dust, etc.)
- Falls back gracefully when they're not — yes, even BSD `ls` works (finally)
- Auto-aliases `cmd_foo_bar` functions to `foo-bar` so you never type an underscore again
- Loads Homebrew properly on macOS (after mass surgery, it now actually works)
- Unlocks the macOS keychain over SSH so you don't type a 47-character password every time
- Plugins: syntax highlighting, autosuggestions, history substring search — the fish features without the fish
- Starship prompt, fzf, zoxide — because life is too short for the default `%`

## Setup

```sh
# That's it. That's the setup.
ln -s ~/.config/zsh/.zshenv ~/.zshenv
```

`.zshenv` figures out where it actually lives by resolving its own symlink. No hardcoded paths, no second symlink, no drama.

## Structure

See [plans/STRUCTURE.md](plans/STRUCTURE.md) for the full file tree, or just `ls` around — it's not that deep.

The short version:
- `environment/` — exports and env vars (per-OS + devtools)
- `bootstrap/` — runtime init: aliases, PATH setup, tool detection
- `autoload/` — lazy functions sorted by `base`, `common`, `devtools`, `linux`, `macos`

## Debug

Shell acting weird? Trace the whole init:

```sh
ZSH_DEBUG_INIT=1 zsh -l
```

This prints every file sourced, every function autoloaded, and how many milliseconds you wasted.

## Diagnostic

```sh
checksh
```

Shows your current shell environment, what each core command actually resolves to, and which modern CLI tools are installed (with versions).

## Platform Notes

**Linux (Arch/CachyOS)** — The first-class citizen. Everything is tested here first. Package management is wrapped via `pkg` (paru/yay). This is the daily driver.

**macOS** — The "it works on my machine" machine. Homebrew is initialized via `brew shellenv`, GNU coreutils are added to PATH, and the whole thing was largely neglected until recently. It's better now. Probably.

## License

[MIT](LICENSE) — Do whatever you want. If your shell breaks, that's between you and your `.zshenv`.
