# File .zshenv; zsh environment config

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

# ZSH debug initialization
export ZSH_DEBUG_INIT="${ZSH_DEBUG_INIT:-0}"

# ZSH dotfile locations
export DOTDIR="${DOTDIR:-${HOME}/.config/dotfiles}"
export MYCONF="${MYCONF:-${HOME}/.config/myconf}"
export ZDOTDIR="${ZDOTDIR:-${HOME}/.config/zsh}"
export ZFUNCDIR="${ZFUNCDIR:-${ZDOTDIR}/autoload}"

# Ensure .local/bin is added to PATH
export PATH="$HOME/.local/bin:$PATH"

# Define a function to source files from the ZDOTDIR directory
# We unfunction it later in .zshrc
import() {
  local base_dir="${1}" # Base directory, can be "" for current dir, or "${ZDOTDIR}/files"
  shift                 # Remove the first argument from the positional parameters

  for arg in "${@}"; do
    local file="${base_dir}/${arg}" # Construct the file path

    # If base_dir is empty, it will result in just "/arg", but that works fine.
    if [[ -n "${base_dir}" ]]; then
      file="${base_dir}/${arg}"
    fi

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
  for dir in "$@"; do
    local autoload_dir="${ZDOTDIR}/autoload/${dir}"

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
import "${ZDOTDIR}" ".env.${OSNAME}" ".env.dev"

# Don't keep duplicates and ignore specific sets of command from history
# https://unix.stackexchange.com/questions/18212/bash-history-ignoredups-and-erasedups-setting-conflict-with-common-history
export HISTIGNORE="&:history*:[sudo ]rm*:[c]ls*:[bf]g*:exit*:pwd*:clear*:mount*:umount*:vol*:encfs*:cfs*:[ \t]*"
export HISTFILE="${HISTFILE:-${ZDOTDIR}/.zsh_history}"
export HISTTIMEFORMAT="%F %T "
export HISTSIZE="5000"
export SAVEHIST="5000"

export EDITOR=/usr/bin/nvim
export VISUAL=/usr/bin/nano
export PAGER=/usr/bin/less

export ZLE_RPROMPT_INDENT=0               # don't leave an empty space after right prompt
export ZLE_REMOVE_SUFFIX_CHARS=''         # don't eat space when typing '|' after a tab completion
export READNULLCMD="${PAGER}"             # use the default pager instead of `more`
export WORDCHARS="${WORDCHARS//\/[&.;]}"  # don't consider certain characters part of the word

# Configure terminal pager
# This affects every invocation of `less`.
#   -i   case-insensitive search unless search string contains uppercase letters
#   -R   color
#   -F   exit if there is less than one page of content
#   -X   keep content on screen after exit
#   -M   show more info at the bottom prompt line
#   -x4  tabs are 4 instead of 8
export LESS="-iRFXMx4"

# Set man pages colors
export LESS_TERMCAP_mb=$'\E[01;32m'
export LESS_TERMCAP_md=$'\E[01;32m'
export LESS_TERMCAP_me=$'\E[0m'
export LESS_TERMCAP_se=$'\E[0m'
export LESS_TERMCAP_so=$'\E[01;47;34m'
export LESS_TERMCAP_ue=$'\E[0m'
export LESS_TERMCAP_us=$'\E[01;36m'

if (( $#commands[(i)lesspipe(|.sh)] )); then
  export LESSOPEN="| /usr/bin/env ${commands}[(i)lesspipe(|.sh)] %s 2>&-"
fi
