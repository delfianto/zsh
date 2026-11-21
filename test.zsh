#!/usr/bin/env zsh
emulate -L zsh
setopt ERR_RETURN NO_UNSET

typeset repo="${0:A:h}"
typeset failures=0

fail() {
  print -u2 -r -- "FAIL: $1"
  (( ++failures ))
}

ZDOTDIR="$repo"
source "$repo/.zshenv"
(( ! ${+functions[vp]} )) || fail "Vite+ loaded its interactive hook in .zshenv"

typeset -a bootstrap_helpers=(
  _zsh_source _zsh_autoload_dir _zsh_add_path import autoload_init add_path has_cmd stdout stderr
)
for helper in "${bootstrap_helpers[@]}"; do
  (( ${+functions[$helper]} )) && fail "bootstrap helper leaked: $helper"
done

source "$repo/.zshrc"
for helper in "${bootstrap_helpers[@]}"; do
  (( ${+functions[$helper]} )) && fail "interactive bootstrap helper leaked: $helper"
done

ZDOTDIR="$repo" zsh -dfc \
  'source "$ZDOTDIR/.zshenv"; source "$ZDOTDIR/.zshrc"; [[ -o PROMPT_SUBST ]]' ||
  fail "prompt command substitution is disabled"
[[ "$HISTFILE" == "$XDG_STATE_HOME/zsh/history" ]] ||
  fail "history is not stored under XDG_STATE_HOME"
[[ "${_comp_dumpfile:-}" == "$XDG_CACHE_HOME/zsh/zcompdump-$ZSH_VERSION" ]] ||
  fail "completion dump is not versioned under XDG_CACHE_HOME"

typeset completion_test_dir
if completion_test_dir="$(mktemp -d "${TMPDIR:-/tmp}/zsh-completion.XXXXXXXXXX")"; then
  (
    setopt EXTENDED_GLOB
    XDG_CACHE_HOME="$completion_test_dir"
    source "$repo/config/rc/completion.zsh" || exit 1
    print -r -- 'typeset -g _test_loaded_completion_dump=1' >> "$_comp_dumpfile" || exit 1
    source "$repo/config/rc/completion.zsh" || exit 1
    (( ${+_test_loaded_completion_dump} )) || exit 1

    unset _test_loaded_completion_dump
    touch -t 200001010000 "$_comp_dumpfile" || exit 1
    source "$repo/config/rc/completion.zsh" || exit 1
    (( ! ${+_test_loaded_completion_dump} )) &&
      [[ -n "$_comp_dumpfile"(#qN.mh-24) ]]
  ) || fail "completion did not reuse a fresh dump and rebuild an expired dump"
  rm -rf -- "$completion_test_dir"
else
  fail "could not create completion test directory"
fi

typeset macos_test_dir
if macos_test_dir="$(mktemp -d "${TMPDIR:-/tmp}/zsh-macos.XXXXXXXXXX")"; then
  zsh -dflc '
    setopt ERR_RETURN NO_UNSET
    repo=$1
    fixture=$2
    export ZDOTDIR="$fixture" HOME="$fixture" PATH=/usr/bin:/bin
    OSTYPE=darwin
    unset LOCAL_BIN LOCAL_LIB BUN_INSTALL HOMEBREW_PREFIX HOMEBREW_GNU_UTILS
    mkdir -p "$fixture/config/env" "$fixture/.local/bin" \
      "$fixture/brew/"{bin,sbin,share/zsh/site-functions,opt/coreutils/libexec/gnubin}
    ln -s "$repo/config/bootstrap.zsh" "$fixture/config/"
    ln -s "$repo"/config/env/{common,macos,tools}.zsh "$fixture/config/env/"
    print -r -- "export HOMEBREW_PREFIX=\"\$ZDOTDIR/brew\"" > "$fixture/config/env/local.zsh"
    source "$repo/.zshenv"
    [[ "$OSNAME" == macos && "$fpath[1]" == "$HOMEBREW_PREFIX/share/zsh/site-functions" ]]
    # Model /etc/zprofile putting system and paths.d entries first.
    path=(/usr/bin /bin /etc-paths-d-example "${path[@]}")
    source "$repo/.zprofile"
    expected=("$HOME/.local/bin" "$HOMEBREW_PREFIX/opt/coreutils/libexec/gnubin"
      "$HOMEBREW_PREFIX/bin" "$HOMEBREW_PREFIX/sbin" /usr/bin /bin /etc-paths-d-example)
    [[ "${(j.:.)path[1,7]}" == "${(j.:.)expected}" && ! -v _zsh_login_path ]]
    source "$repo/config/rc/plugins.zsh"
  ' zsh "$repo" "$macos_test_dir" || fail "macOS login PATH or plugin-free startup failed"
  rm -rf -- "$macos_test_dir"
else
  fail "could not create macOS startup test directory"
fi

_zsh_history_filter $'echo hello\n' || fail "ordinary history was rejected"
_zsh_history_filter $'pwd\n' && fail "ignored history was accepted"

for name in grep df du cp mv sudo; do
  (( ${+aliases[$name]} )) || fail "opinionated command alias is missing: $name"
done
[[ "$OSNAME" != linux ]] || (( ${+aliases[pacman]} )) ||
  fail "Linux pacman alias is missing"
(( ! ${+aliases[hwmon]} )) || fail "hwmon alias shadows the external command"
(( ! ${+commands[bat]} || ${+aliases[cat]} )) || fail "bat did not replace cat"
(( ! ${+commands[eza]} || ${+aliases[ls]} )) || fail "eza did not replace ls"

typeset -a platform_functions
case "$OSNAME" in
  linux) platform_functions=(cpuinfo fixmirror hwmon iommu nvidia-cdi os-release pulse-eq sudo-conf xdg-open) ;;
  macos) platform_functions=(beer svc) ;;
esac
for name in checksh ex func jstatd lint lsenv lspath psmem fpath gcc-flags venv pkg "${platform_functions[@]}"; do
  (( ${+functions[$name]} )) || fail "public function is not autoloaded: $name"
done
typeset -a legacy_functions=(${(k)functions[(I)cmd_*]})
(( ${#legacy_functions} )) && fail "legacy cmd_* functions remain"
(( ${+functions[cpufreq]} )) && fail "retired cpufreq function remains autoloaded"

unset i
lspath >/dev/null
(( ${+parameters[i]} )) && fail "lspath leaked i"

if [[ "$OSNAME" == linux ]]; then
  unset key
  os-release --shell >/dev/null
  (( ${+parameters[key]} )) && fail "os-release leaked key"
  sudo-conf '../invalid' >/dev/null 2>&1 && fail "sudo-conf accepted path traversal"
  cpuinfo --help >/dev/null || fail "cpuinfo Python utility could not start"
  hwmon --help >/dev/null || fail "hwmon Python utility could not start"
  iommu --help >/dev/null || fail "iommu Python utility could not start"
  pulse-eq --help >/dev/null || fail "pulse-eq Python utility could not start"
fi

[[ "$(fpath .)" == "$PWD:A" ]] || fail "fpath returned the wrong path"
if (( ${+commands[gcc]} )) && [[ "$(LC_ALL=C command gcc --version 2>/dev/null)" == *'Free Software Foundation'* ]]; then
  typeset gcc_test_dir
  gcc_test_dir="$(mktemp -d "${TMPDIR:-/tmp}/zsh-gcc-flags.XXXXXXXXXX")" ||
    fail "could not create gcc-flags test directory"
  if [[ -n "$gcc_test_dir" ]]; then
    (cd "$gcc_test_dir" && gcc-flags >/dev/null) ||
      fail "gcc-flags could not query target options"
    [[ ! -e "$gcc_test_dir/help-dummy.o" ]] ||
      fail "gcc-flags left help-dummy.o in the working directory"
    rm -f -- "$gcc_test_dir/help-dummy.o"
    rmdir -- "$gcc_test_dir"
  fi
fi
venv --help >/dev/null || fail "venv Python utility could not start"

typeset venv_test_dir
venv_test_dir="$(mktemp -d "${TMPDIR:-/tmp}/zsh-venv-load.XXXXXXXXXX")" ||
  fail "could not create venv load test directory"
if [[ -n "$venv_test_dir" ]]; then
  mkdir -p -- "$venv_test_dir/bin"
  print -r -- "export VIRTUAL_ENV=${(q)venv_test_dir}" > "$venv_test_dir/bin/activate"
  (venv load "$venv_test_dir" >/dev/null &&
    [[ "$VIRTUAL_ENV" == "$venv_test_dir" ]]) ||
    fail "venv load did not activate in the calling shell"
  rm -f -- "$venv_test_dir/bin/activate"
  rmdir -- "$venv_test_dir/bin" "$venv_test_dir"
fi

PYTHONPYCACHEPREFIX="$XDG_CACHE_HOME/zsh/python" \
  python3 -m unittest discover -s "$repo/utils" -t "$repo" ||
  fail "Python utility tests failed"

if (( failures )); then
  print -u2 -r -- "$failures test(s) failed"
  return 1
fi

print -r -- "tests: OK"
