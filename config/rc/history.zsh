typeset -g HISTFILE="${ZSH_HISTFILE:-$XDG_STATE_HOME/zsh/history}"
typeset -g HISTSIZE="${HISTSIZE:-50000}"
typeset -g SAVEHIST="${SAVEHIST:-50000}"
typeset +x HISTFILE HISTSIZE SAVEHIST
unset HISTORY_IGNORE
mkdir -p -- "$HISTFILE:h"

_zsh_history_filter() {
  [[ "$1" != (history*|rm\ *|cls*|exit*|pwd*|clear*) ]]
}
add-zsh-hook zshaddhistory _zsh_history_filter
