#!/bin/zsh

# upload new media to immich
WATCH_DIR="$HOME/syncthing/photos/upload-queue"
LOG_DIR="$HOME/git/log"
LOG_FILE="$LOG_DIR/immich.log"
IMMICH_PATH="$HOME/git/tools/immich/immich-wrapper.sh"

# ensure log directory exists
mkdir -p "$LOG_DIR"

# load zsh-specific environment
[[ -f "$HOME/.zshrc" ]] && source "$HOME/.zshrc"

# load nvm and set the correct node.js version
export NVM_DIR="$HOME/.nvm"
[[ -s "$NVM_DIR/nvm.sh" ]] && source "$NVM_DIR/nvm.sh"
export PATH="/usr/local/bin:/usr/bin:/bin:$HOME/.nvm/versions/node/v20.18.0/bin:$PATH"
nvm use 20

# check if immich executable is available
if [[ ! -f "$IMMICH_PATH" ]]; then
  $HOME/.local/bin/cabinet --log "Immich not found at $IMMICH_PATH" --level "error"
  exit 1
fi

# monitor the directory for new files and run immich upload on changes
inotifywait -m -e create "$WATCH_DIR" | while read path action file; do
    $HOME/.local/bin/cabinet --log "Immich File Detected: $file"
    "$IMMICH_PATH" upload "$WATCH_DIR" --delete >> "$LOG_FILE" 2>&1
done
