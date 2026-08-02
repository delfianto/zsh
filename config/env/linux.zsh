typeset -g LS_ARGS="${LS_ARGS:---color=auto --group-directories-first --time-style=long-iso -h}"
typeset +x LS_ARGS

typeset docker_env_file=/etc/systemd/system/docker-compose.env
if [[ -r "$docker_env_file" ]]; then
  if [[ -o allexport ]]; then
    source "$docker_env_file"
  else
    setopt allexport
    source "$docker_env_file"
    unsetopt allexport
  fi
fi
