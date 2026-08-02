# Full version-manager shell integrations are interactive-only.
_zsh_init_tools() {
  emulate -L zsh
  unsetopt nounset

  if [[ -s "$SDKMAN_DIR/bin/sdkman-init.sh" ]]; then
    source "$SDKMAN_DIR/bin/sdkman-init.sh"
  fi

  if [[ -s "$HOME/.vite-plus/env" ]]; then
    source "$HOME/.vite-plus/env"
  fi

  if (( ${+commands[zoxide]} )); then
    eval "$(zoxide init zsh)"
  fi

  if (( ${+commands[direnv]} )); then
    eval "$(direnv hook zsh)"
  fi

  if [[ -t 0 && -t 1 ]]; then
    (( ${+commands[fzf]} )) && source <(fzf --zsh)
    (( ${+commands[starship]} )) && eval "$(starship init zsh)"
  fi

  if [[ -n "$BUN_INSTALL" && -s "$BUN_INSTALL/_bun" ]]; then
    source "$BUN_INSTALL/_bun"
  fi
}
_zsh_init_tools
unfunction _zsh_init_tools

_zsh_set_term_title() {
  [[ -t 1 && "$TERM" != dumb ]] && print -Pn '\e]0;%n@%m: %~\a'
}
add-zsh-hook precmd _zsh_set_term_title
