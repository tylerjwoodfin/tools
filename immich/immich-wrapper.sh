#!/bin/zsh

# load zsh-specific environment
if [[ -f $HOME/.zshrc ]]; then
  source $HOME/.zshrc
fi

# load nvm
export NVM_DIR="$HOME/.nvm"
[[ -s "$NVM_DIR/nvm.sh" ]] && source "$NVM_DIR/nvm.sh"

# set PATH explicitly
export PATH="/usr/local/bin:/usr/bin:/bin:$HOME/.nvm/versions/node/v20.18.0/bin:$PATH"

# use nvm to set Node version
nvm use 20

# call immich
/usr/local/bin/immich "$@"