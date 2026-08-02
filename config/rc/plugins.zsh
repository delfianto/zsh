typeset plugin_root=''
case "$OSNAME" in
  linux) plugin_root=/usr/share/zsh/plugins ;;
  macos) plugin_root="$HOMEBREW_PREFIX/share" ;;
esac

# Syntax highlighting must be last so it can wrap every previously defined ZLE
# widget, including history-substring-search.
[[ -r "$plugin_root/zsh-autosuggestions/zsh-autosuggestions.zsh" ]] &&
  source "$plugin_root/zsh-autosuggestions/zsh-autosuggestions.zsh"
if [[ -r "$plugin_root/zsh-history-substring-search/zsh-history-substring-search.zsh" ]]; then
  source "$plugin_root/zsh-history-substring-search/zsh-history-substring-search.zsh"
  bindkey '^[[5~' history-substring-search-up
  bindkey '^[[6~' history-substring-search-down
fi
[[ -r "$plugin_root/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh" ]] &&
  source "$plugin_root/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh"
