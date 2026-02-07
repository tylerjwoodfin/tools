#!/bin/sh

# Set up HOME if not already set (cron may not set it)
# This is needed for $HOME/syncthing and $HOME/.local/bin paths
if [ -z "$HOME" ]; then
    export HOME=$(getent passwd $(whoami) 2>/dev/null | cut -d: -f6)
    # Fallback if getent fails
    if [ -z "$HOME" ]; then
        export HOME="/home/$(whoami)"
    fi
fi

# Set up PATH to include common binary locations
# Cron jobs run with minimal PATH, so we need to set it explicitly
export PATH="/usr/local/bin:/usr/bin:/bin:$HOME/.local/bin:$HOME/bin:$PATH"

# Find borg command
BORG_CMD=""
if command -v borg >/dev/null 2>&1; then
    BORG_CMD="borg"
elif [ -x "/usr/local/bin/borg" ]; then
    BORG_CMD="/usr/local/bin/borg"
elif [ -x "$HOME/.local/bin/borg" ]; then
    BORG_CMD="$HOME/.local/bin/borg"
elif [ -x "/usr/bin/borg" ]; then
    BORG_CMD="/usr/bin/borg"
else
    echo "Error: borg command not found. Please install borgbackup." >&2
    echo "On Ubuntu/Debian: sudo apt-get install borgbackup" >&2
    echo "On macOS: brew install borgbackup" >&2
    exit 1
fi

# Parse command line arguments
REPLICATE_ONLY=false
if [ "$1" = "--replicate-only" ]; then
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
warning() { "$CABINET" --log "$*" --level 'warning'; }
error() { "$CABINET" --log "$*" --level 'error'; }
RAINBOW_PATH=$("$CABINET" -g "path" "rainbow-borg") || {
    echo "Error: Failed to retrieve rainbow path." >&2
    exit 1
}

# Graceful exit on SIGINT/SIGTERM
trap 'echo "$(date) Backup interrupted" >&2; exit 2' INT TERM

# Check if repository exists and initialize if needed
check_and_init_repo() {
    # Try to list the repository to see if it exists
    borg_list_output=$("$BORG_CMD" list :: 2>&1)
    borg_list_exit=$?
    
    # Check if the error is specifically about repository not existing
    if [ $borg_list_exit -ne 0 ]; then
        case "$borg_list_output" in
            *"does not exist"*|*"Repository"*"not found"*)
                info "Repository does not exist. Initializing repository..."
                
                # Determine if this is a local or remote repository
                case "$BORG_REPO" in
                    ssh://*|http://*|https://*)
                        # Remote repository - try to initialize
                        if ! "$BORG_CMD" init --encryption=repokey 2>&1; then
                            error "Failed to initialize remote repository. Please initialize manually:"
                            error "  $BORG_CMD init --encryption=repokey $BORG_REPO"
                            return 1
                        fi
                        ;;
                    *)
                        # Local repository - create directory if needed
                        if [ ! -d "$BORG_REPO" ]; then
                            info "Creating repository directory: $BORG_REPO"
                            mkdir -p "$BORG_REPO" || {
                                error "Failed to create repository directory: $BORG_REPO"
                                return 1
                            }
                        fi
                        
                        # Initialize the repository
                        if ! "$BORG_CMD" init --encryption=repokey 2>&1; then
                            error "Failed to initialize repository. Please initialize manually:"
                            error "  $BORG_CMD init --encryption=repokey $BORG_REPO"
                            return 1
                        fi
                        ;;
                esac
                
                info "Repository initialized successfully"
                ;;
            *)
                # Other error (permissions, network, etc.)
                error "Failed to access repository: $borg_list_output"
                return 1
                ;;
        esac
    else
        debug "Repository exists and is accessible"
    fi
    return 0
}

if [ "$REPLICATE_ONLY" = true ]; then
    info "Replicate-only mode: skipping backup, prune, compact, and check"
    global_exit=0
else
    info 'Starting Borg Backup...'

    # Check and initialize repository if needed
    check_and_init_repo
    repo_init_exit=$?
    if [ $repo_init_exit -ne 0 ]; then
        error "Repository initialization failed. Exiting."
        exit 1
    fi

    # Check if backup already exists from today (for idempotency)
    today=$(date +%Y-%m-%d)
    existing_today=$("$BORG_CMD" list --short 2>/dev/null | grep -c "$today" 2>/dev/null || echo 0)
    
    # Ensure existing_today is numeric (default to 0 if empty or non-numeric)
    case "$existing_today" in
        ''|*[!0-9]*) existing_today=0 ;;
    esac

    if [ "$existing_today" -ge 1 ]; then
        info "Backup from today already exists, skipping create step"
        backup_exit=0
    else
        # Create temporary file for crontab backup
        CRONTAB_TMP=$(mktemp)
        crontab -l > "$CRONTAB_TMP" 2>/dev/null || touch "$CRONTAB_TMP"

        # Create temporary file to capture borg error output
        BORG_ERROR_TMP=$(mktemp)
        # Set trap to clean up both temp files
        trap "rm -f $CRONTAB_TMP $BORG_ERROR_TMP" EXIT

        # Build list of paths to backup, checking if they exist
        BACKUP_PATHS=""
        
        # Helper function to add path if it exists
        add_backup_path() {
            local path="$1"
            if [ -e "$path" ]; then
                [ -n "$BACKUP_PATHS" ] && BACKUP_PATHS="$BACKUP_PATHS "
                BACKUP_PATHS="$BACKUP_PATHS$path"
            else
                debug "Skipping $path (does not exist)"
            fi
        }
        
        # Check and add paths that exist
        add_backup_path "$HOME/syncthing"
        add_backup_path "$HOME/git"
        add_backup_path "$HOME/.zshrc"
        add_backup_path "$HOME/.config"
        
        # Always add crontab backup (only if file exists, is readable, and has content)
        # Check that file has content (not just empty from failed crontab -l)
        if [ -r "$CRONTAB_TMP" ] && [ -s "$CRONTAB_TMP" ]; then
            [ -n "$BACKUP_PATHS" ] && BACKUP_PATHS="$BACKUP_PATHS "
            # Use colon syntax to rename file in archive: source:destination
            BACKUP_PATHS="$BACKUP_PATHS$CRONTAB_TMP::crontab.txt"
        fi

        # Backup multiple paths
        # Exclude .git and .github directories recursively within ~/git
        # Also exclude files that typically have permission issues
        "$BORG_CMD" create                         \
            --verbose                       \
            --filter AME                    \
            --list                          \
            --stats                         \
            --show-rc                       \
            --compression lz4               \
            --exclude-caches                \
            --exclude 'sh:**/.git'          \
            --exclude 'sh:**/.github'       \
            --exclude 'sh:**/ssh_host_*_key*' \
            --exclude 'sh:**/logrotate'     \
            --exclude 'sh:**/postgres'       \
            --exclude 'sh:**/tmp_objdir-*'  \
                                            \
            ::'{hostname}-{now}'            \
            $BACKUP_PATHS \
            2>"$BORG_ERROR_TMP"

        backup_exit=$?
        
        # Borg exit codes: 0=success, 1=warning (some files skipped), 2=fatal error
        if [ $backup_exit -eq 1 ]; then
            warning "Borg backup completed with warnings (some files were skipped)"
            if [ -s "$BORG_ERROR_TMP" ]; then
                warning "Borg warning output:"
                while IFS= read -r line; do
                    warning "  $line"
                done < "$BORG_ERROR_TMP"
            fi
        elif [ $backup_exit -ne 0 ]; then
            error "Borg backup creation failed with exit code: $backup_exit"
            if [ -s "$BORG_ERROR_TMP" ]; then
                # Save full error output to permanent location for later review
                ERROR_LOG_DIR="$HOME/.cabinet/log/borg-errors"
                mkdir -p "$ERROR_LOG_DIR"
                ERROR_LOG_FILE="$ERROR_LOG_DIR/borg-error-$(date +%Y%m%d-%H%M%S).log"
                cp "$BORG_ERROR_TMP" "$ERROR_LOG_FILE"
                error "Full Borg error output saved to: $ERROR_LOG_FILE"
                
                # Extract only actual error messages (exclude normal borg output)
                actual_errors=$(grep -E '(stat:|No such file|Error|error|failed|Failed)' "$BORG_ERROR_TMP" | grep -v '^[MA] ' | sort -u)
                
                if [ -n "$actual_errors" ]; then
                    error "Borg error details (showing first 10):"
                    echo "$actual_errors" | head -10 | while IFS= read -r line; do
                        error "  $line"
                    done
                    # If there are more than 10 errors, summarize
                    error_count=$(echo "$actual_errors" | wc -l | tr -d ' ')
                    if [ "$error_count" -gt 10 ]; then
                        error "  ... and $((error_count - 10)) more error(s) - see full details in: $ERROR_LOG_FILE"
                    fi
                else
                    # If no clear errors found, log first few lines as context
                    error "Borg warning output (first 5 lines):"
                    head -5 "$BORG_ERROR_TMP" | while IFS= read -r line; do
                        error "  $line"
                    done
                    error "Full output available in: $ERROR_LOG_FILE"
                fi
            fi
        fi
        
        # Clean up temp files after Borg is done
        rm -f "$CRONTAB_TMP" "$BORG_ERROR_TMP"
    fi

    info "Pruning repository"

    # Use the `prune` subcommand to maintain 7 daily, 4 weekly and 6 monthly
    # archives of THIS machine. The '{hostname}-*' matching is very important to
    # limit prune's operation to this machine's archives and not apply to
    # other machines' archives also:

    "$BORG_CMD" prune                          \
        --list                          \
        --glob-archives '{hostname}-*'  \
        --show-rc                       \
        --keep-daily    7               \
        --keep-weekly   4               \
        --keep-monthly  6

    prune_exit=$?

    # Actually free repo disk space by compacting segments
    info "Compacting repository"
    "$BORG_CMD" compact

    compact_exit=$?

    # Check if backups are performing as expected
    check_backups() {
        # Get list of backups, handling errors
        backups=$("$BORG_CMD" list --short 2>&1)
        borg_list_exit=$?
        
        if [ $borg_list_exit -ne 0 ]; then
            error "Failed to list backups: $backups"
            return 1
        fi
        
        # Check if backup list is empty
        if [ -z "$backups" ]; then
            error "No backups found in repository"
            return 1
        fi
        
        today=$(date +%Y-%m-%d)
        yesterday=$(date -d "yesterday" +%Y-%m-%d)
        last_month=$(date -d "-1 month" +%Y-%m)

        # Count backups matching dates (handle empty grep results)
        today_count=$(echo "$backups" | grep -c "$today" 2>/dev/null || echo 0)
        yesterday_count=$(echo "$backups" | grep -c "$yesterday" 2>/dev/null || echo 0)
        
        # Ensure counts are numeric (default to 0 if empty or non-numeric)
        case "$today_count" in
            ''|*[!0-9]*) today_count=0 ;;
        esac
        case "$yesterday_count" in
            ''|*[!0-9]*) yesterday_count=0 ;;
        esac
        
        week_count=0
        i=0
        while [ $i -le 6 ]; do
            day=$(date -d "$i days ago" +%Y-%m-%d)
            day_count=$(echo "$backups" | grep -c "$day" 2>/dev/null || echo 0)
            case "$day_count" in
                ''|*[!0-9]*) day_count=0 ;;
            esac
            week_count=$((week_count + day_count))
            i=$((i + 1))
        done

        month_count=$(echo "$backups" | grep -c "$last_month" 2>/dev/null || echo 0)
        case "$month_count" in
            ''|*[!0-9]*) month_count=0 ;;
        esac

        # Debug output
        debug "Backup check: today=$today_count, yesterday=$yesterday_count, week=$week_count, month=$month_count"
        debug "Recent backups: $(echo "$backups" | head -5 | tr '\n' ' ')"

        if [ "$today_count" -ge 1 ] || [ "$yesterday_count" -ge 1 ]; then
            info "Backup from today or yesterday found."
        else
            error "No backup from today or yesterday found."
            error "Today: $today, Yesterday: $yesterday"
            error "Available backups: $(echo "$backups" | head -10 | tr '\n' ' ')"
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

    # Check backups (always run to verify repository state)
    info "Checking backups"
    if [ "$backup_exit" -eq 1 ]; then
        warning "Backup creation completed with warnings (exit code: 1), but checking existing backups anyway"
    elif [ "$backup_exit" -ne 0 ]; then
        error "Backup creation failed (exit code: $backup_exit), but checking existing backups anyway"
    fi
    check_backups
    check_exit=$?
    info "check_exit=$check_exit"

    # Use highest exit code as global exit code
    # Note: exit code 1 from Borg is a warning (archive created successfully, some files skipped)
    # Only exit codes >= 2 are actual failures
    global_exit=$(( backup_exit > prune_exit ? backup_exit : prune_exit ))
    global_exit=$(( compact_exit > global_exit ? compact_exit : global_exit ))
    global_exit=$(( check_exit > global_exit ? check_exit : global_exit ))
    debug "global_exit=$global_exit (backup=$backup_exit, prune=$prune_exit, compact=$compact_exit, check=$check_exit)"

    if [ "$(date +%u)" -eq 7 ]; then  # Sunday
        info "Running borg check (weekly integrity verification)"
        "$BORG_CMD" check --verify-data --verbose
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
    
    case "$RAINBOW_PATH" in
        ssh://*)
            # Extract components from ssh://[user@]host[:port]/path format
            # Remove ssh:// prefix
            TEMP="${RAINBOW_PATH#ssh://}"
            
            # Extract path (everything after first /)
            PATH_PART="${TEMP#*/}"
            HOST_PART="${TEMP%%/*}"
            
            # Check for port using case statement
            case "$HOST_PART" in
                *:[0-9]*)
                    PORT="${HOST_PART##*:}"
                    HOST_PART="${HOST_PART%:*}"
                    SSH_OPTS="$SSH_OPTS -p $PORT"
                    ;;
            esac
            
            # Format for rsync: user@host:path
            # Expand ~ to full home directory path (rsync doesn't expand ~ on remote)
            case "$PATH_PART" in
                ~*)
                    # Extract username from HOST_PART (format: user@host or just host)
                    if [ "${HOST_PART#*@}" != "$HOST_PART" ]; then
                        REMOTE_USER="${HOST_PART%%@*}"
                    else
                        # If no user specified, default to current user or extract from SSH config
                        REMOTE_USER="tyler"
                    fi
                    # Replace ~ with /home/username using sed
                    EXPANDED_PATH=$(echo "$PATH_PART" | sed "s|^~|/home/${REMOTE_USER}|")
                    RSYNC_DEST="${HOST_PART}:${EXPANDED_PATH}"
                    ;;
                *)
                    RSYNC_DEST="${HOST_PART}:/${PATH_PART}"
                    ;;
            esac
            ;;
    esac

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
