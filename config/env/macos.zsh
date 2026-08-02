if [[ -z "${HOMEBREW_PREFIX:-}" ]]; then
  if [[ -x /opt/homebrew/bin/brew ]]; then
    export HOMEBREW_PREFIX=/opt/homebrew
  else
    export HOMEBREW_PREFIX=/usr/local
  fi
fi
export HOMEBREW_CASK_OPTS="${HOMEBREW_CASK_OPTS:---appdir=/Applications --no-quarantine}"
export HOMEBREW_NO_ANALYTICS="${HOMEBREW_NO_ANALYTICS:-1}"
export HOMEBREW_NO_ENV_HINTS="${HOMEBREW_NO_ENV_HINTS:-1}"
typeset -g LS_ARGS="${LS_ARGS:---color=auto --group-directories-first --time-style=long-iso -h}"
typeset +x LS_ARGS

_zsh_add_path "$HOMEBREW_PREFIX/bin"
_zsh_add_path "$HOMEBREW_PREFIX/sbin"
export MANPATH="$HOMEBREW_PREFIX/share/man:${MANPATH:-}"
export INFOPATH="$HOMEBREW_PREFIX/share/info:${INFOPATH:-}"
[[ -d "$HOMEBREW_PREFIX/share/zsh/site-functions" ]] &&
  fpath=("$HOMEBREW_PREFIX/share/zsh/site-functions" $fpath)

if (( ${HOMEBREW_GNU_UTILS:-1} )); then
  typeset gnu_package
  for gnu_package in coreutils findutils gnu-indent gnu-which gnu-sed gnu-tar; do
    _zsh_add_path "$HOMEBREW_PREFIX/opt/$gnu_package/libexec/gnubin"
  done
fi

export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1}"
