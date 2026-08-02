# Load Zsh's completion initializer without executing it until fpath is ready.
autoload -Uz compinit

# Keep both the generated completion dump and command-specific caches out of the
# repository. Including the Zsh version prevents incompatible dumps being reused
# after an upgrade.
typeset completion_root="$XDG_CACHE_HOME/zsh"
typeset zcompdump="$completion_root/zcompdump-$ZSH_VERSION"
mkdir -p -- "$completion_root/completion"

# Try literal expansion first, then normal and ignored matches, followed by
# increasingly permissive spelling correction when no direct match exists.
zstyle ':completion:*' completer _expand _complete _ignored _correct _approximate
# Match letters case-insensitively while preserving the user's typed casing.
zstyle ':completion:*' matcher-list 'm:{a-zA-Z}={A-Za-z}'
# Reuse the same file-type colors configured for modern `ls` replacements.
zstyle ':completion:*' list-colors "${(s.:.)${LS_COLORS:-}}"
# Refresh the command hash when completion needs to discover a new executable.
zstyle ':completion:*' rehash true
# Prefer an exact match instead of opening a menu of less-specific candidates.
zstyle ':completion:*' accept-exact '*(N)'
# Let completion functions cache expensive command and metadata discovery.
zstyle ':completion:*' use-cache on
zstyle ':completion:*' cache-path "$completion_root/completion"

# Once a day, run the full initialization to detect changed completion files.
# When the dump is less than 24 hours old, -C trusts it and skips compinit's
# slower security scan and function-count validation; a missing dump is created.
if [[ -n "$zcompdump"(#qN.mh+24) ]]; then
  compinit -d "$zcompdump"
else
  compinit -C -d "$zcompdump"
fi
