# -*- mode: sh -*-
# File .env.linux; zsh environment config for development tools

export SDK_HOME="${SDK_HOME:-${HOME}/.local/lib}"

# Ruby devtools and environment
if (( ${+commands[rbenv]} )); then
  eval "$(rbenv init -)"
elif (( ${+commands[ruby]} )); then
  ruby_version="$(ruby -e 'puts RUBY_VERSION')"
  gem_dir="ruby/gems/${ruby_version%?}0"

  export GEM_HOME="${SDK_HOME}/${gem_dir}"
  export GEM_PATH="${GEM_HOME}:/usr/lib/${gem_dir}"
  export GEM_SPEC_CACHE="${GEM_HOME}/spec"

  export PATH="${GEM_HOME}/bin:${PATH}"
  unset ruby_version gem_dir
fi

# SDK Manager (JVM stack)
export SDKMAN_DIR="${SDK_DIR}/sdk"
export SDKMAN_INIT="${SDKMAN_DIR}/bin/sdkman-init.sh"

if [[ -e "${SDKMAN_INIT}" ]]; then
  export GROOVY_TURN_OFF_JAVA_WARNINGS="true"
  export GRADLE_USER_HOME="${HOME}/.gradle"

  eval "mkdir -p ${SDKMAN_DIR}/ext" &> /dev/null
  source "${SDKMAN_INIT}"
else
  unset SDKMAN_DIR SDKMAN_INIT
fi
