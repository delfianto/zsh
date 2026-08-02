# Use Emacs-style editing as the base keymap; the bindings below normalize
# escape sequences emitted by common terminals rather than replacing the map.
bindkey -e

# Home: support rxvt/Linux-console and xterm sequences, then the terminal's
# advertised sequence when available.
bindkey '^[[7~' beginning-of-line
bindkey '^[[H' beginning-of-line
[[ -n "${terminfo[khome]:-}" ]] &&
  bindkey "${terminfo[khome]}" beginning-of-line

# End: accept the equivalent common variants and the terminfo capability.
bindkey '^[[8~' end-of-line
bindkey '^[[F' end-of-line
[[ -n "${terminfo[kend]:-}" ]] &&
  bindkey "${terminfo[kend]}" end-of-line

# Insert toggles overwrite mode; Delete removes the character under the cursor.
bindkey '^[[2~' overwrite-mode
bindkey '^[[3~' delete-char

# Plain arrow keys move one character without invoking history navigation.
bindkey '^[[C' forward-char
bindkey '^[[D' backward-char

# Page Up/Down search history for entries beginning with the text already typed.
bindkey '^[[5~' history-beginning-search-backward
bindkey '^[[6~' history-beginning-search-forward

# Alt/Ctrl-arrow variants move across whole shell words. Different terminal
# emulators encode these combinations differently, so retain both forms.
bindkey '^[Oc' forward-word
bindkey '^[Od' backward-word
bindkey '^[[1;5D' backward-word
bindkey '^[[1;5C' forward-word

# Ctrl-H removes the previous word instead of only the previous character.
bindkey '^H' backward-kill-word
# Shift-Tab undoes the latest editing change in the current command buffer.
bindkey '^[[Z' undo
