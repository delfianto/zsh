# -*- mode: sh -*-
# File .env.linux; zsh environment config for linux

# System wide XDG directories
export XDG_CONFIG_DIRS="${XDG_CONFIG_DIRS:-/etc/xdg}"
export XDG_DATA_DIRS="${XDG_DATA_DIRS:-/usr/local/share/:/usr/share/}"

# User specific XDG directories
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-${HOME}/.cache}"
export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-${HOME}/.config}"
export XDG_DATA_HOME="${XDG_DATA_HOME:-${HOME}/.local/share}"
export XDG_STATE_HOME="${XDG_STATE_HOME:-${HOME}/.local/state}"

# ZSH dotfile locations
export DOTDIR="${DOTDIR:-${XDG_CONFIG_HOME}/dotfiles}"
export MYCONF="${MYCONF:-${XDG_CONFIG_HOME}/myconf}"
export ZDOTDIR="${ZDOTDIR:-${XDG_CONFIG_HOME}/zsh}"

# Default ls arguments (could be overriden down the line if we install eza)
export LS_ARGS="--color=auto --group-directories-first --time-style=long-iso -h"
