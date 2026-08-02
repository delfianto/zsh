# Completion, expansion, and prompt behavior.
# ALWAYS_TO_END moves the cursor after an inserted completion.
# EXTENDED_GLOB enables Zsh's richer glob operators and qualifiers.
# NUMERIC_GLOB_SORT sorts numeric filename components by their numeric value.
# PROMPT_SUBST expands parameters and commands in prompts, as Starship requires.
# RCEXPANDPARAM distributes surrounding text across each array element.
setopt ALWAYS_TO_END EXTENDED_GLOB NUMERIC_GLOB_SORT PROMPT_SUBST RCEXPANDPARAM

# Directory navigation and the directory stack.
# AUTO_CD treats a directory path entered as a command as an implicit `cd`.
# AUTO_PUSHD saves the previous directory on the stack after changing directory.
# PUSHD_IGNORE_DUPS prevents duplicate entries in the directory stack.
# PUSHD_MINUS swaps the meanings of +N and -N directory-stack indexes.
setopt AUTO_CD AUTO_PUSHD PUSHD_IGNORE_DUPS PUSHD_MINUS

# Persistent, shared history with duplicate and whitespace cleanup.
# EXTENDED_HISTORY records each command's timestamp and elapsed time.
# HIST_EXPIRE_DUPS_FIRST discards duplicates before unique entries when trimming.
# HIST_FCNTL_LOCK uses fcntl locking for safer history updates across shells.
# HIST_IGNORE_ALL_DUPS removes an older matching command when adding a new one.
# HIST_IGNORE_SPACE omits commands whose first character is a space.
# HIST_REDUCE_BLANKS removes redundant whitespace before saving commands.
# HIST_VERIFY places an expanded history command in the editor before execution.
# SHARE_HISTORY imports new commands and appends this shell's commands immediately.
setopt EXTENDED_HISTORY HIST_EXPIRE_DUPS_FIRST HIST_FCNTL_LOCK
setopt HIST_IGNORE_ALL_DUPS HIST_IGNORE_SPACE HIST_REDUCE_BLANKS HIST_VERIFY
setopt SHARE_HISTORY

# Interactive command-line behavior.
# INTERACTIVE_COMMENTS recognizes `#` comments at an interactive prompt.
# MULTIOS tees input or output when a command has multiple redirections.
# NO_BANG_HIST disables `!` history expansion.
# NO_BEEP suppresses the terminal bell on editing and completion errors.
# NO_BG_NICE keeps background jobs at their normal scheduling priority.
setopt INTERACTIVE_COMMENTS MULTIOS NO_BANG_HIST NO_BEEP NO_BG_NICE

# Remove Zsh's default one-column gap after the right prompt.
typeset -g ZLE_RPROMPT_INDENT=0
# Keep completion-added suffixes until they are explicitly removed.
typeset -g ZLE_REMOVE_SUFFIX_CHARS=''
# Use the configured pager for a bare input redirection such as `<README.md`.
typeset -g READNULLCMD="$PAGER"
# Make word-wise ZLE operations stop at common path and command separators.
typeset -g WORDCHARS="${WORDCHARS//[\/&.;]}"
# Do not apply ZLE's default inverse-video highlight to pasted text.
typeset -ga zle_highlight=('paste:none')
# These editor parameters are shell-local settings, never child-process environment.
typeset +x ZLE_RPROMPT_INDENT ZLE_REMOVE_SUFFIX_CHARS READNULLCMD WORDCHARS

# Color capabilities used by `less` for man pages and other formatted input.
# Blink and bold text use bright green; every mode reset clears all styling.
typeset -gx LESS_TERMCAP_mb=$'\E[01;32m'
typeset -gx LESS_TERMCAP_md=$'\E[01;32m'
typeset -gx LESS_TERMCAP_me=$'\E[0m'
typeset -gx LESS_TERMCAP_se=$'\E[0m'
# Standout text uses bright blue on white.
typeset -gx LESS_TERMCAP_so=$'\E[01;47;34m'
typeset -gx LESS_TERMCAP_ue=$'\E[0m'
# Underlined text uses cyan instead of a terminal underline.
typeset -gx LESS_TERMCAP_us=$'\E[01;36m'
