# File .zshenv; zsh environment config
#
# Sourced for EVERY zsh invocation -- login, interactive, scripts, SSH commands.
# Only things a non-interactive shell genuinely needs belong here. Anything that
# only matters to a human at a prompt (history, ZLE, keybindings, prompt tools)
# goes in .zshrc.

# ZSH debug initialization. The timer starts here rather than in .zshrc so that
# the reported figure covers the environment phase too; .zshrc prints the total.
export ZSH_DEBUG_INIT="${ZSH_DEBUG_INIT:-0}"
if (( ZSH_DEBUG_INIT )); then
  zmodload zsh/datetime
  typeset -g _zsh_init_start=$EPOCHREALTIME
fi

# Determine the OS name
case "$OSTYPE" in
  linux-gnu*)
    export OSNAME="linux"
    ;;
  darwin*)
    export OSNAME="macos"
    ;;
  *)
    export OSNAME="unknown"
    ;;
esac

# ZSH dotfile locations
# ZDOTDIR is derived from this file's real path (:A resolves symlinks, :h takes
# the dir). It MUST be set here — zsh needs it to locate the environment/ files.
# DOTDIR and MYCONF are set per-OS in environment/<os>.env.
export ZDOTDIR="${ZDOTDIR:-${${(%):-%x}:A:h}}"

# Set path as array-unique-special (no duplicates)
typeset -aU path

# Ensure .local/bin is added to PATH
export PATH="$HOME/.local/bin:$PATH"

# Define a function to source files from the ZDOTDIR directory
# We unfunction it later in .zshrc
import() {
  local base_dir="${1}" # Base directory, can be "" for current dir, or "${ZDOTDIR}/files"
  shift                 # Remove the first argument from the positional parameters

  local arg file
  for arg in "${@}"; do
    # Construct the file path; if base_dir is empty, use the bare arg
    file="${base_dir:+${base_dir}/}${arg}"

    (( ZSH_DEBUG_INIT )) && print "Attempting to load ${file}..."

    if [[ -f "${file}" && -r "${file}" ]]; then
      (( ZSH_DEBUG_INIT )) && print "Loading ${file}"
      source "${file}"
    else
      (( ZSH_DEBUG_INIT )) && print "Warning: Could not read ${file}" >&2
    fi
  done
}

# Initialize ZSH auto-loaded functions
# We also unfunction this later in .zshrc
autoload_init() {
  local dir file autoload_dir
  for dir in "$@"; do
    autoload_dir="${ZDOTDIR}/autoload/${dir}"

    if [[ -d "${autoload_dir}" ]]; then
      fpath=("${autoload_dir}" $fpath)
      for file in "${autoload_dir}"/[^_]*(.N:t); do
        (( ZSH_DEBUG_INIT )) && print "Autoloaded: ${file}"
        autoload -Uz "${file}"
      done
    else
      (( ZSH_DEBUG_INIT )) && print "Skipped (not a directory): ${dir}"
    fi
  done
}

# Load the common helper functions for all session
# Without this, the functions will only be available on an interactive shell
autoload_init "base"

# Source the appropriate .env file based on the OS
import "${ZDOTDIR}/environment" \
  "${OSNAME}.env" \
  "devtools.env" \
  "local.env"

export VISUAL="nvim"
export EDITOR="nano"

# Try to use `ov` as default pager.
# Braces matter: inside (( )) an unbraced $+assoc[key] math-evaluates the
# subscript, so a key that happens to name a variable expands to its value.
if (( ${+commands[ov]} )); then
  export PAGER="ov"
  export BAT_PAGER="ov"
  export SYSTEMD_PAGER="ov"
else
  export PAGER="less"
  export SYSTEMD_PAGER="less"
fi

# Configure terminal pager
# This affects every invocation of `less`.
#   -i   case-insensitive search unless search string contains uppercase letters
#   -R   color
#   -F   exit if there is less than one page of content
#   -X   keep content on screen after exit
#   -M   show more info at the bottom prompt line
#   -x4  tabs are 4 instead of 8
export LESS="-iRFXMx4"

if (( ${+commands[lesspipe]} )); then
  export LESSOPEN="| lesspipe %s 2>&-"
elif (( ${+commands[lesspipe.sh]} )); then
  export LESSOPEN="| lesspipe.sh %s 2>&-"
fi
