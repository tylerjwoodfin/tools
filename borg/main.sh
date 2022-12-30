#!/bin/sh

# Setting this, so the repo does not need to be given on the commandline:

borg_repo=`cat /home/tyler/syncthing/securedata/keys/BORG_REPO`
borg_passphrase=`cat /home/tyler/syncthing/securedata/keys/BORG_PASSPHRASE`
export BORG_REPO=$borg_repo
export BORG_PASSPHRASE=$borg_passphrase

echo $borg_repo
echo $BORG_PASSPHRASE

# some helpers and error handling:
info() { printf "\n%s %s\n\n" "$( date )" "$*" >&2; }
trap 'echo $( date ) Backup interrupted >&2; exit 2' INT TERM

info "Starting backup"

# Backup /home/tyler/syncthing

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
    /home/tyler/syncthing

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

# actually free repo disk space by compacting segments

info "Compacting repository"

borg compact

compact_exit=$?

# use highest exit code as global exit code
global_exit=$(( backup_exit > prune_exit ? backup_exit : prune_exit ))
global_exit=$(( compact_exit > global_exit ? compact_exit : global_exit ))

if [ ${global_exit} -eq 0 ]; then
    info "Backup, Prune, and Compact finished successfully"
elif [ ${global_exit} -eq 1 ]; then
    info "Backup, Prune, and/or Compact finished with warnings"
else
    info "Backup, Prune, and/or Compact finished with errors"
fi

exit ${global_exit}
