# On macOS, /etc/zprofile runs path_helper after .zshenv. Restore the
# precedence of our prepended paths while keeping the system's additions.
if [[ "${OSNAME:-}" == macos ]] && (( ${+_zsh_login_path} )); then
  path=("${_zsh_login_path[@]}" "${path[@]}")
  unset _zsh_login_path
fi
