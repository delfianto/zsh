# Private bootstrap helpers. Entrypoints remove these after initialization.

_zsh_source() {
  local file
  for file in "$@"; do
    (( ZSH_DEBUG_INIT )) && print -r -- "Loading: $file"
    [[ -r "$file" ]] && source "$file"
  done
}

_zsh_add_path() {
  [[ -d "$1" && -r "$1" ]] || return 0
  if [[ "${2:-}" == after ]]; then
    path+=("$1")
  else
    path=("$1" $path)
  fi
}

_zsh_autoload_dir() {
  local category dir file
  for category in "$@"; do
    dir="$ZDOTDIR/func/$category"
    [[ -d "$dir" ]] || continue
    fpath=("$dir" $fpath)
    for file in "$dir"/[^_]*(N.:t); do
      autoload -Uz "$file"
      (( ZSH_DEBUG_INIT )) && print -r -- "Autoloaded: $file"
    done
  done
}
