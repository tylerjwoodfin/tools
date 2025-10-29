#!/bin/zsh

#!/bin/zsh

# Parse command line arguments
REPLICATE_ONLY=false
if [[ "$1" == "--replicate-only" ]]; then
    REPLICATE_ONLY=true
fi

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
debug() { "$CABINET" --log "$*" --level 'debug'; }
info() { "$CABINET" --log "$*"; }
error() { "$CABINET" --log "$*" --level 'error'; }
RAINBOW_PATH=$("$CABINET" -g "path" "rainbow-borg") || {
    echo "Error: Failed to retrieve rainbow path." >&2
    exit 1
}

# Graceful exit on SIGINT/SIGTERM
trap 'echo "$(date) Backup interrupted" >&2; exit 2' INT TERM

if [ "$REPLICATE_ONLY" = true ]; then
    info "Replicate-only mode: skipping backup, prune, compact, and check"
    global_exit=0
else
    info 'Starting Borg Backup...'

    # Check if backup already exists from today (for idempotency)
    today=$(date +%Y-%m-%d)
    existing_today=$(borg list --short 2>/dev/null | grep -c "$today" || echo 0)

    if [ "$existing_today" -ge 1 ]; then
        info "Backup from today already exists, skipping create step"
        backup_exit=0
    else
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
    fi

    info "Pruning repository"

    # Use the `prune` subcommand to maintain 1 daily, 2 weekly and 1 monthly
    # archives of THIS machine. The '{hostname}-*' matching is very important to
    # limit prune's operation to this machine's archives and not apply to
    # other machines' archives also:

    borg prune                          \
        --list                          \
        --glob-archives '{hostname}-*'  \
        --show-rc                       \
        --keep-daily    7               \
        --keep-weekly   4               \
        --keep-monthly  6

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
    info "check_exit=$check_exit"

    # Use highest exit code as global exit code
    global_exit=$(( backup_exit > prune_exit ? backup_exit : prune_exit ))
    global_exit=$(( compact_exit > global_exit ? compact_exit : global_exit ))
    global_exit=$(( check_exit > global_exit ? check_exit : global_exit ))
    debug "global_exit=$global_exit (backup=$backup_exit, prune=$prune_exit, compact=$compact_exit, check=$check_exit)"

    if [ "$(date +%u)" -eq 7 ]; then  # Sunday
        info "Running borg check (weekly integrity verification)"
        borg check --verify-data --verbose
        integrity_check_exit=$?
        if [ ${integrity_check_exit} -ne 0 ]; then
            error "Integrity check failed"
            global_exit=$(( integrity_check_exit > global_exit ? integrity_check_exit : global_exit ))
        fi
    fi
fi

debug "About to check if should replicate: global_exit=${global_exit}"
if [ ${global_exit} -eq 0 ]; then
    info "Replicating Borg repo to rainbow"

    # Convert ssh:// URI to rsync format if needed
    RSYNC_DEST="$RAINBOW_PATH"
    SSH_OPTS="-o StrictHostKeyChecking=no"
    
    if [[ "$RAINBOW_PATH" =~ ^ssh:// ]]; then
        # Extract components from ssh://[user@]host[:port]/path format
        # Remove ssh:// prefix
        TEMP="${RAINBOW_PATH#ssh://}"
        
        # Extract path (everything after first /)
        PATH_PART="${TEMP#*/}"
        HOST_PART="${TEMP%%/*}"
        
        # Check for port
        if [[ "$HOST_PART" =~ :([0-9]+)$ ]]; then
            PORT="${HOST_PART##*:}"
            HOST_PART="${HOST_PART%:*}"
            SSH_OPTS="$SSH_OPTS -p $PORT"
        fi
        
        # Format for rsync: user@host:path
        # Don't add leading / if path starts with ~ (home directory)
        if [[ "$PATH_PART" =~ ^~ ]]; then
            RSYNC_DEST="${HOST_PART}:${PATH_PART}"
        else
            RSYNC_DEST="${HOST_PART}:/${PATH_PART}"
        fi
    fi

    rsync -av --delete \
        --partial --partial-dir=.rsync-partial \
        --progress \
        --timeout=300 \
        -e "ssh $SSH_OPTS" \
        "$BORG_REPO/" \
        "$RSYNC_DEST/"

    replicate_exit=$?
    
    if [ ${replicate_exit} -eq 0 ]; then
        info "Successfully replicated to rainbow"
    else
        error "Failed to replicate to rainbow"
    fi
    
    global_exit=$(( replicate_exit > global_exit ? replicate_exit : global_exit ))
fi


if [ "$REPLICATE_ONLY" = true ]; then
    if [ ${global_exit} -eq 0 ]; then
        info "Replication finished successfully"
    else
        info "Replication finished with errors"
    fi
else
    if [ ${global_exit} -eq 0 ]; then
        info "Backup, Prune, Compact, and Check finished successfully"
    elif [ ${global_exit} -eq 1 ]; then
        info "Backup, Prune, Compact, and/or Check finished with warnings"
    else
        info "Backup, Prune, Compact, and/or Check finished with errors"
    fi
fi

exit ${global_exit}
