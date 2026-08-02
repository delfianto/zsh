# Zsh environment entry point. This file runs for every zsh process, so keep it
# limited to exported environment and inexpensive PATH setup.

export ZSH_DEBUG_INIT="${ZSH_DEBUG_INIT:-0}"
if (( ZSH_DEBUG_INIT )); then
  zmodload zsh/datetime
  typeset -g _zsh_init_start=$EPOCHREALTIME
fi

case "$OSTYPE" in
  linux-gnu*) typeset -g OSNAME=linux ;;
  darwin*)    typeset -g OSNAME=macos ;;
  *)
    print -r -u2 -- "Unsupported platform: $OSTYPE"
    return 1
    ;;
esac
typeset +x OSNAME

export ZDOTDIR="${ZDOTDIR:-${${(%):-%x}:A:h}}"
typeset -aU path fpath

source "$ZDOTDIR/config/bootstrap.zsh"
_zsh_source \
  "$ZDOTDIR/config/env/common.zsh" \
  "$ZDOTDIR/config/env/local.zsh" \
  "$ZDOTDIR/config/env/${OSNAME}.zsh" \
  "$ZDOTDIR/config/env/tools.zsh"

unfunction _zsh_source _zsh_autoload_dir _zsh_add_path
