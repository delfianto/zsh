# Opinionated command replacements for this interactive shell.

if (( ${+commands[bat]} )); then
  alias cat='bat --color=always --paging=never --style=plain'
  alias nut='bat --color=always --paging=never'
fi

if (( ${+commands[duf]} )); then
  alias df='duf'
else
  alias df='df -h'
fi

if (( ${+commands[gdu]} )); then
  alias du='gdu'
elif (( ${+commands[gdu-go]} )); then
  alias du='gdu-go'
elif (( ${+commands[dust]} )); then
  alias du='dust'
else
  alias du='du -h'
  alias ds='du -hs'
fi

if (( ${+commands[eza]} )); then
  alias ls="eza $LS_ARGS"
  alias ll="eza $LS_ARGS -l"
  alias la="eza $LS_ARGS -a"
  alias lla="eza $LS_ARGS -al"
elif (( ${+commands[gls]} )); then
  alias ls="gls $LS_ARGS"
  alias ll="gls $LS_ARGS -l"
  alias la="gls $LS_ARGS -a"
  alias lla="gls $LS_ARGS -al"
elif command ls --color=auto / &>/dev/null; then
  alias ls="ls $LS_ARGS"
  alias ll="ls $LS_ARGS -l"
  alias la="ls $LS_ARGS -a"
  alias lla="ls $LS_ARGS -al"
else
  alias ls='ls -Gh'
  alias ll='ls -Glh'
  alias la='ls -GAh'
  alias lla='ls -GAlh'
fi

if (( ${+commands[nvim]} )); then
  alias vi='nvim'
  alias vim='nvim'
fi

[[ "$TERM" == xterm-kitty ]] && (( ${+commands[kitty]} )) && alias ssh='kitty +kitten ssh'

alias cls="clear && printf '\e[3J'"
alias cp='cp -v'
alias mv='mv -v'
alias sudo='sudo '
alias which='command -v'
alias grep='grep -i --color=auto'
alias egrep='egrep -i --color=auto'
alias fgrep='fgrep -i --color=auto'
alias history='fc -li'
alias shdir='cd -- $ZDOTDIR'
alias reload='exec zsh -l'
