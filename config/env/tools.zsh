# Tool paths are derived after local.zsh so host overrides take effect.

_zsh_add_path "$LOCAL_BIN"

if (( ${+commands[nvim]} )); then
  export VISUAL="${VISUAL:-nvim}"
  export EDITOR="${EDITOR:-nvim}"
else
  export VISUAL="${VISUAL:-vi}"
  export EDITOR="${EDITOR:-vi}"
fi

if (( ${+commands[ov]} )); then
  export PAGER="${PAGER:-ov}"
  export BAT_PAGER="${BAT_PAGER:-ov}"
  export SYSTEMD_PAGER="${SYSTEMD_PAGER:-ov}"
else
  export PAGER="${PAGER:-less}"
  export SYSTEMD_PAGER="${SYSTEMD_PAGER:-less}"
fi

export LESS="${LESS:--iRFXMx4}"
if (( ${+commands[lesspipe]} )); then
  export LESSOPEN="${LESSOPEN:-| lesspipe %s 2>&-}"
elif (( ${+commands[lesspipe.sh]} )); then
  export LESSOPEN="${LESSOPEN:-| lesspipe.sh %s 2>&-}"
fi

typeset bun_home="${BUN_INSTALL:-$LOCAL_LIB/bun}"
if [[ -d "$bun_home" ]]; then
  export BUN_INSTALL="$bun_home"
  export BUN_INSTALL_BIN="${BUN_INSTALL_BIN:-$LOCAL_BIN}"
  export BUN_INSTALL_GLOBAL_DIR="${BUN_INSTALL_GLOBAL_DIR:-$BUN_INSTALL/install}"
  _zsh_add_path "$BUN_INSTALL/bin"
fi

_zsh_add_path "$HOME/.lmstudio/bin"
_zsh_add_path "$HOME/.vite-plus/bin"

if [[ -z "${SDKMAN_DIR:-}" ]]; then
  if [[ -d /opt/sdkman ]]; then
    export SDKMAN_DIR=/opt/sdkman
  else
    export SDKMAN_DIR="$XDG_DATA_HOME/sdkman"
  fi
fi

typeset candidate_bin
for candidate_bin in "$SDKMAN_DIR"/candidates/*/current/bin(N/); do
  _zsh_add_path "$candidate_bin" after
done

if (( ${+commands[uv]} )); then
  export UV_CACHE_DIR="${UV_CACHE_DIR:-$XDG_CACHE_HOME/uv}"
fi
