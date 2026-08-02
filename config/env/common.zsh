# Cross-platform exported environment.

export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$HOME/.cache}"
export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
export XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
export XDG_STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"
export XDG_CONFIG_DIRS="${XDG_CONFIG_DIRS:-/etc/xdg}"
export XDG_DATA_DIRS="${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"

export DOTDIR="${DOTDIR:-$XDG_CONFIG_HOME/dotfiles}"
export MYCONF="${MYCONF:-$XDG_CONFIG_HOME/myconf}"
export LOCAL_LIB="${LOCAL_LIB:-$HOME/.local/lib}"
export LOCAL_BIN="${LOCAL_BIN:-$HOME/.local/bin}"
_zsh_add_path "$LOCAL_BIN"
