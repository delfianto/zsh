# File .zshrc; zsh initialization script

if (( ZSH_DEBUG_INIT )); then
  zmodload zsh/datetime
  local _zsh_start=$EPOCHREALTIME
fi

autoload_init "common"
autoload_init "devtools"
autoload_init "${OSNAME}"

# Initialize zsh built-in functions
autoload -Uz colors compinit regexp-replace zcalc

# Only regenerate completion dump once per day
local zcompdump="${ZDOTDIR:-$HOME}/.zcompdump"
if [[ -n ${zcompdump}(#qN.mh+24) ]]; then
  compinit -d "$zcompdump"
else
  compinit -C -d "$zcompdump"
fi

colors

# On every prompt, set terminal title to "user@host: cwd"
function set-term-title() { print -Pn '\e]0;%n@%m: %~\a' }
autoload -U add-zsh-hook
add-zsh-hook precmd set-term-title

# Disable highlighting of text pasted into the command line
zle_highlight=('paste:none')

# ZSH options
setopt ALWAYS_TO_END          # full completions move cursor to the end
setopt AUTO_CD                # `dirname` is equivalent to `cd dirname`
setopt AUTO_PUSHD             # `cd` pushes directories to the directory stack
setopt CORRECT                # auto correct mistakes
setopt EXTENDED_GLOB          # (#qx) glob qualifier and more
setopt EXTENDED_HISTORY       # write timestamps to history
setopt GLOB_DOTS              # glob matches files starting with dot; `*` becomes `*(D)`
setopt HIST_EXPIRE_DUPS_FIRST # if history needs to be trimmed, evict dups first
setopt HIST_FCNTL_LOCK        # lock history file using the system’s fcntl call
setopt HIST_IGNORE_ALL_DUPS   # don't add dups to history
setopt HIST_IGNORE_SPACE      # don't add commands starting with space to history
setopt HIST_REDUCE_BLANKS     # remove junk whitespace from commands before adding to history
setopt HIST_VERIFY            # if a cmd triggers history expansion, show it instead of running
setopt INTERACTIVE_COMMENTS   # allow comments in command line
setopt MULTIOS                # allow multiple redirections for the same fd
setopt NO_BANG_HIST           # disable old history syntax
setopt NO_BEEP                # no beep
setopt NO_BG_NICE             # don't nice background jobs; not useful and doesn't work on WSL
setopt NO_CASE_GLOB           # case insensitive globbing
setopt NO_CHECK_JOBS          # don't warn about running processes when exiting
setopt NUMERIC_GLOB_SORT      # sort filenames numerically when it makes sense
setopt PUSHD_IGNORE_DUPS      # don’t push copies of the same directory onto the directory stack
setopt PUSHD_MINUS            # `cd -3` now means "3 directory deeper in the stack"
setopt RCEXPANDPARAM          # array expension with parameters
setopt SHARE_HISTORY          # write and import history on every command

# The following lines were added by compinstall
zstyle ':completion:*' completer _expand _complete _ignored _correct _approximate
zstyle ':completion:*' matcher-list 'm:{a-zA-Z}={A-Za-z}'       # Case insensitive tab completion
zstyle ':completion:*' list-colors "${(s.:.)LS_COLORS}"         # Colored completion (different colors for dirs/files/etc)
zstyle ':completion:*' rehash true                              # automatically find new executables in path

# Speed up completions
zstyle ':completion:*' accept-exact '*(N)'
zstyle ':completion:*' use-cache on
zstyle ':completion:*' cache-path ${ZDOTDIR}/cache

# Keybindings
bindkey -e
bindkey '^[[7~' beginning-of-line                               # Home key
bindkey '^[[H' beginning-of-line                                # Home key

if [[ "${terminfo[khome]}" != "" ]]; then
  bindkey "${terminfo[khome]}" beginning-of-line                # [Home] - Go to beginning of line
fi

bindkey '^[[8~' end-of-line                                     # End key
bindkey '^[[F' end-of-line                                      # End key

if [[ "${terminfo[kend]}" != "" ]]; then
  bindkey "${terminfo[kend]}" end-of-line                       # [End] - Go to end of line
fi

bindkey '^[[2~' overwrite-mode                                  # Insert key
bindkey '^[[3~' delete-char                                     # Delete key
bindkey '^[[C'  forward-char                                    # Right key
bindkey '^[[D'  backward-char                                   # Left key
bindkey '^[[5~' history-beginning-search-backward               # Page up key
bindkey '^[[6~' history-beginning-search-forward                # Page down key

# Navigate words with ctrl+arrow keys
bindkey '^[Oc' forward-word                                     #
bindkey '^[Od' backward-word                                    #
bindkey '^[[1;5D' backward-word                                 #
bindkey '^[[1;5C' forward-word                                  #
bindkey '^H' backward-kill-word                                 # delete previous word with ctrl+backspace
bindkey '^[[Z' undo                                             # Shift+tab undo last action

# Plugins sections: Enable fish style features
local plugin_dir=""
case "$OSNAME" in
  linux)  plugin_dir="/usr/share/zsh/plugins" ;;
  macos)  plugin_dir="${HOMEBREW_PREFIX:-/opt/homebrew}/share" ;;
esac

if [[ -n "$plugin_dir" ]]; then
  import "$plugin_dir" \
    zsh-autosuggestions/zsh-autosuggestions.zsh \
    zsh-syntax-highlighting/zsh-syntax-highlighting.zsh \
    zsh-history-substring-search/zsh-history-substring-search.zsh
fi

# Load the rest of zshrc files (OS first to set up PATH, then common for aliases)
import "${ZDOTDIR}/bootstrap" "${OSNAME}" "common"

# Rehash command table after bootstrap may have modified PATH (e.g. brew shellenv)
hash -r

# Load FZF
if has_cmd -q fzf; then
  source <(fzf --zsh)
fi

# Load zoxide (smart cd replacement)
if has_cmd -q zoxide; then
  eval "$(zoxide init zsh)"
fi

# Load starship
if has_cmd -q starship; then
  eval "$(starship init zsh)"
fi

if (( ZSH_DEBUG_INIT )); then
  printf "Shell initialization took %.3f milliseconds.\n" "$(( (EPOCHREALTIME - _zsh_start) * 1000 ))"
fi

unset -f autoload_init import
