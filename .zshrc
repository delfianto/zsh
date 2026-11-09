# Interactive-shell entry point. The source order is intentional and mirrors
# the phases documented in AGENTS.md.

source "$ZDOTDIR/config/bootstrap.zsh"

_zsh_autoload_dir common devtools "$OSNAME"
autoload -Uz add-zsh-hook colors regexp-replace zcalc
colors

_zsh_source \
  "$ZDOTDIR/config/rc/options.zsh" \
  "$ZDOTDIR/config/rc/history.zsh" \
  "$ZDOTDIR/config/rc/completion.zsh" \
  "$ZDOTDIR/config/rc/aliases.zsh" \
  "$ZDOTDIR/config/rc/${OSNAME}.zsh" \
  "$ZDOTDIR/config/rc/keybindings.zsh" \
  "$ZDOTDIR/config/rc/tools.zsh" \
  "$ZDOTDIR/config/rc/plugins.zsh"

if (( ZSH_DEBUG_INIT )); then
  printf "Shell initialization took %.3f milliseconds (.zshenv + .zshrc).\n" \
    "$(( (EPOCHREALTIME - _zsh_init_start) * 1000 ))"
fi

unfunction _zsh_source _zsh_autoload_dir _zsh_add_path
unset _zsh_init_start

# Vite+ bin (https://viteplus.dev)
. "/home/geist/.vite-plus/env"
