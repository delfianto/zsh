#!/usr/bin/env zsh
emulate -L zsh
setopt ERR_RETURN NO_UNSET

typeset repo="${0:A:h}"
typeset failures=0

fail() {
  print -u2 -r -- "FAIL: $1"
  (( failures++ ))
}

ZDOTDIR="$repo"
source "$repo/.zshenv"

for helper in _zsh_source _zsh_autoload_dir _zsh_add_path import autoload_init \
  add_path has_cmd stdout stderr; do
  (( ${+functions[$helper]} )) && fail "bootstrap helper leaked: $helper"
done

source "$repo/.zshrc"

ZDOTDIR="$repo" zsh -dfc \
  'source "$ZDOTDIR/.zshenv"; source "$ZDOTDIR/.zshrc"; [[ -o PROMPT_SUBST ]]' ||
  fail "prompt command substitution is disabled"
[[ "$HISTFILE" == "$XDG_STATE_HOME/zsh/history" ]] ||
  fail "history is not stored under XDG_STATE_HOME"
[[ "${_comp_dumpfile:-}" == "$XDG_CACHE_HOME/zsh/zcompdump-$ZSH_VERSION" ]] ||
  fail "completion dump is not versioned under XDG_CACHE_HOME"

_zsh_history_filter $'echo hello\n' || fail "ordinary history was rejected"
_zsh_history_filter $'pwd\n' && fail "ignored history was accepted"

for name in grep df du cp mv sudo; do
  (( ${+aliases[$name]} )) || fail "opinionated command alias is missing: $name"
done
[[ "$OSNAME" != linux ]] || (( ${+aliases[pacman]} )) ||
  fail "Linux pacman alias is missing"
(( ! ${+commands[bat]} || ${+aliases[cat]} )) || fail "bat did not replace cat"
(( ! ${+commands[eza]} || ${+aliases[ls]} )) || fail "eza did not replace ls"

for name in checksh ex func jstatd lint lsenv lspath fpath gcc-flags venv \
  cpufreq fixmirror iommu nvidia-cdi os-release pkg pulse-eq sudo-conf xdg-open; do
  (( ${+functions[$name]} )) || fail "public function is not autoloaded: $name"
done
typeset -a legacy_functions=(${(k)functions[(I)cmd_*]})
(( ${#legacy_functions} )) && fail "legacy cmd_* functions remain"

unset key i
os-release --shell >/dev/null
(( ${+parameters[key]} )) && fail "os-release leaked key"
lspath >/dev/null
(( ${+parameters[i]} )) && fail "lspath leaked i"

sudo-conf '../invalid' >/dev/null 2>&1 &&
  fail "sudo-conf accepted path traversal"

[[ "$(fpath .)" == "$PWD:A" ]] || fail "fpath returned the wrong path"

if (( failures )); then
  print -u2 -r -- "$failures test(s) failed"
  return 1
fi

print -r -- "tests: OK"
