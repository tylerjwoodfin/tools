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
        # Create temporary directory for crontab backup
        # Use a fixed subdirectory name so the archive path is predictable
        CRONTAB_TMP_DIR=$(mktemp -d)
        CRONTAB_TMP="$CRONTAB_TMP_DIR/crontab.txt"
        crontab -l > "$CRONTAB_TMP" 2>/dev/null || touch "$CRONTAB_TMP"

        # Create temporary file to capture borg error output
        BORG_ERROR_TMP=$(mktemp)
        # Set trap to clean up temp files and directory
        trap "rm -rf $CRONTAB_TMP_DIR $BORG_ERROR_TMP" EXIT

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
        add_backup_path "$HOME/.affine"

        # Export Immich database for backup (pg_dump - postgres data dir has restrictive perms)
        IMMICH_DIR="$HOME/git/docker/immich"
        IMMICH_BACKUP_DIR="$IMMICH_DIR/database-backup"
        if [ -d "$IMMICH_DIR" ] && command -v docker >/dev/null 2>&1; then
            mkdir -p "$IMMICH_BACKUP_DIR"
            if docker ps --format '{{.Names}}' 2>/dev/null | grep -q immich_postgres; then
                if docker exec -t immich_postgres pg_dumpall --clean --if-exists --username=postgres > "$IMMICH_BACKUP_DIR/immich-database.sql" 2>/dev/null; then
                    debug "Immich database dumped to database-backup/"
                else
                    warning "Failed to dump Immich database"
                fi
            else
                debug "Immich postgres not running, skipping database dump"
            fi
        fi

        # Export Affine database for backup (pg_dump - postgres data dir has restrictive perms)
        AFFINE_DIR="$HOME/git/docker/affine"
        AFFINE_BACKUP_DIR="$AFFINE_DIR/database-backup"
        if [ -d "$AFFINE_DIR" ] && command -v docker >/dev/null 2>&1; then
            mkdir -p "$AFFINE_BACKUP_DIR"
            if docker ps --format '{{.Names}}' 2>/dev/null | grep -q affine_postgres; then
                if docker exec -t affine_postgres pg_dump -U affine affine > "$AFFINE_BACKUP_DIR/affine-database.sql" 2>/dev/null; then
                    debug "Affine database dumped to database-backup/"
                else
                    warning "Failed to dump Affine database"
                fi
            else
                debug "Affine postgres not running, skipping database dump"
            fi
        fi

        # Export Taiga Docker data for backup (DB, media, static)
        # Data is normally in named volumes - we export to a dir under git so it gets backed up
        TAIGA_DIR="$HOME/git/docker/taiga-docker"
        TAIGA_BACKUP_DIR="$TAIGA_DIR/taiga-backup"
        if [ -d "$TAIGA_DIR" ] && command -v docker >/dev/null 2>&1; then
            mkdir -p "$TAIGA_BACKUP_DIR"
            if docker compose -f "$TAIGA_DIR/docker-compose.yml" ps taiga-db 2>/dev/null | grep -q Up; then
                if docker compose -f "$TAIGA_DIR/docker-compose.yml" exec -T taiga-db pg_dump -U taiga taiga > "$TAIGA_BACKUP_DIR/taiga_db.sql" 2>/dev/null; then
                    debug "Taiga database dumped to taiga-backup/"
                else
                    warning "Failed to dump Taiga database"
                fi
                # Export media and static volumes
                for vol_suffix in media static; do
                    vol_name="taiga-docker_taiga-${vol_suffix}-data"
                    if docker run --rm -v "$vol_name:/data" -v "$TAIGA_BACKUP_DIR/$vol_suffix:/backup" alpine cp -a /data/. /backup/ 2>/dev/null; then
                        debug "Taiga $vol_suffix exported"
                    fi
                done
            else
                warning "Taiga not running, skipping Taiga data export"
            fi
        fi

        # Always add crontab backup (only if file exists, is readable, and has content)
        # Check that file has content (not just empty from failed crontab -l)
        # Back up the temp directory; Borg will store it with the temp dir path,
        # but crontab.txt will be accessible in the archive
        if [ -r "$CRONTAB_TMP" ] && [ -s "$CRONTAB_TMP" ]; then
            add_backup_path "$CRONTAB_TMP_DIR"
        fi

        # Backup multiple paths
        # Exclude .git and .github directories recursively within ~/git
        # Also exclude files that typically have permission issues
        # Capture both stdout and stderr - stdout has "E path" lines for skipped files
        # (Borg --list sends file listing to stdout, errors/warnings to stderr)
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
            --exclude 'sh:**/var/lib/postgresql*' \
            --exclude 'sh:**/postgres/pgdata' \
            --exclude 'sh:**/docker/immich/postgres' \
            --exclude 'sh:**/tmp_objdir-*'  \
                                            \
            ::'{hostname}-{now}'            \
            $BACKUP_PATHS \
            >"$BORG_ERROR_TMP" 2>&1

        backup_exit=$?
        
        # Borg exit codes: 0=success, 1=warning (some files skipped), 2=fatal error
        if [ $backup_exit -eq 1 ]; then
            warning "Borg backup completed with warnings (some files were skipped)"
            if [ -s "$BORG_ERROR_TMP" ]; then
                # Extract "E path" lines - Borg uses E = error (file could not be read)
                skipped_files=$(grep '^E ' "$BORG_ERROR_TMP" | sed 's/^E //' | sort -u)
                # Extract other warning/error messages (exclude M/A/E file listing, normal borg output)
                actual_warnings=$(grep -v '^[MAE] ' "$BORG_ERROR_TMP" | grep -v '^Creating archive' | grep -v '^Repository:' | grep -v '^Archive name:' | grep -v '^Archive fingerprint:' | grep -v '^Time (' | grep -v '^Duration:' | grep -v '^Number of files:' | grep -v '^Utilization' | grep -v '^Original size' | grep -v '^This archive:' | grep -v '^All archives:' | grep -v '^Unique chunks' | grep -v '^Chunk index:' | grep -v '^---' | grep -v '^$' | grep -E '(stat:|No such file|Error|error|failed|Failed|Permission denied|warning|Warning)' | grep -v '^terminating with warning status' | sort -u)
                
                if [ -n "$skipped_files" ]; then
                    warning "Skipped files (could not be read):"
                    echo "$skipped_files" | head -20 | while IFS= read -r line; do
                        warning "  $line"
                    done
                    skipped_count=$(echo "$skipped_files" | wc -l | tr -d ' ')
                    if [ "$skipped_count" -gt 20 ]; then
                        warning "  ... and $((skipped_count - 20)) more skipped file(s)"
                    fi
                fi
                if [ -n "$actual_warnings" ]; then
                    warning "Borg warning details:"
                    echo "$actual_warnings" | head -10 | while IFS= read -r line; do
                        warning "  $line"
                    done
                    warning_count=$(echo "$actual_warnings" | wc -l | tr -d ' ')
                    if [ "$warning_count" -gt 10 ]; then
                        warning "  ... and $((warning_count - 10)) more warning(s)"
                    fi
                fi
                # If we found nothing useful, save full output for debugging
                if [ -z "$skipped_files" ] && [ -z "$actual_warnings" ]; then
                    WARN_LOG_DIR="$HOME/.cabinet/log/borg-errors"
                    mkdir -p "$WARN_LOG_DIR"
                    WARN_LOG_FILE="$WARN_LOG_DIR/borg-warning-$(date +%Y%m%d-%H%M%S).log"
                    cp "$BORG_ERROR_TMP" "$WARN_LOG_FILE"
                    warning "Full Borg output saved to: $WARN_LOG_FILE (no parseable details found)"
                fi
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

        # Clean up exports (were captured in backup)
        for _dir in "${TAIGA_BACKUP_DIR:-}" "${IMMICH_BACKUP_DIR:-}" "${AFFINE_BACKUP_DIR:-}"; do
            [ -d "$_dir" ] && rm -rf "$_dir"
        done
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
