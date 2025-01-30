#!/bin/zsh

#!/bin/zsh

# Define paths
CABINET="$HOME/.local/bin/cabinet"

# Fetch Borg repo and passphrase securely
BORG_REPO=$("$CABINET" -g "keys" "borg" "repo") || {
    echo "Error: Failed to retrieve Borg repo path." >&2
    exit 1
}

BORG_PASSPHRASE=$("$CABINET" -g "keys" "borg" "passphrase") || {
    echo "Error: Failed to retrieve Borg passphrase." >&2
    exit 1
}

# Export for Borg to use
export BORG_REPO
export BORG_PASSPHRASE

# Log repo
echo "Borg repository: $BORG_REPO"

# Logging functions
info() { "$CABINET" --log "$*"; }
error() { "$CABINET" --log "$*" --level 'error'; }

# Graceful exit on SIGINT/SIGTERM
trap 'echo "$(date) Backup interrupted" >&2; exit 2' INT TERM

info 'Starting Borg Backup...'

# Backup $HOME/syncthing
borg create                         \
    --verbose                       \
    --filter AME                    \
    --list                          \
    --stats                         \
    --show-rc                       \
    --compression lz4               \
    --exclude-caches                \
                                    \
    ::'{hostname}-{now}'            \
    $HOME/syncthing

backup_exit=$?

info "Pruning repository"

# Use the `prune` subcommand to maintain 1 daily, 2 weekly and 1 monthly
# archives of THIS machine. The '{hostname}-*' matching is very important to
# limit prune's operation to this machine's archives and not apply to
# other machines' archives also:

borg prune                          \
    --list                          \
    --glob-archives '{hostname}-*'  \
    --show-rc                       \
    --keep-daily    1               \
    --keep-weekly   2               \
    --keep-monthly  1

prune_exit=$?

# Actually free repo disk space by compacting segments
info "Compacting repository"
borg compact

compact_exit=$?

# Check if backups are performing as expected
check_backups() {
    backups=$(borg list --short)
    today=$(date +%Y-%m-%d)
    yesterday=$(date -d "yesterday" +%Y-%m-%d)
    last_month=$(date -d "last month" +%Y-%m)

    today_count=$(echo "$backups" | grep -c "$today")
    yesterday_count=$(echo "$backups" | grep -c "$yesterday")
    
    week_count=0
    for i in {0..6}; do
        day=$(date -d "$i days ago" +%Y-%m-%d)
        week_count=$((week_count + $(echo "$backups" | grep -c "$day")))
    done

    month_count=$(echo "$backups" | grep -c "$last_month")

    if [ "$today_count" -ge 1 ] || [ "$yesterday_count" -ge 1 ]; then
        info "Backup from today or yesterday found."
    else
        error "No backup from today or yesterday found."
        return 1
    fi

    if [ "$week_count" -ge 2 ]; then
        info "At least 2 backups from this week found."
    else
        error "Less than 2 backups from this week found."
        return 1
    fi

    if [ "$month_count" -ge 1 ]; then
        info "Backup from last month found."
    else
        error "No backup from last month found."
        return 1
    fi

    return 0
}

info "Checking backups"
check_backups
check_exit=$?

# Use highest exit code as global exit code
global_exit=$(( backup_exit > prune_exit ? backup_exit : prune_exit ))
global_exit=$(( compact_exit > global_exit ? compact_exit : global_exit ))
global_exit=$(( check_exit > global_exit ? check_exit : global_exit ))

if [ ${global_exit} -eq 0 ]; then
    info "Backup, Prune, Compact, and Check finished successfully"
elif [ ${global_exit} -eq 1 ]; then
    info "Backup, Prune, Compact, and/or Check finished with warnings"
else
    info "Backup, Prune, Compact, and/or Check finished with errors"
fi

exit ${global_exit}
