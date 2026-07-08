# borg

An automated backup script to back up my Syncthing instance to Hetzner, with replication to a secondary location (rainbow).

## Features

- **Automated Borg backups** with compression and deduplication
- **Smart pruning** to keep 7 daily, 4 weekly, and 6 monthly archives
- **Repository compaction** to reclaim disk space
- **Backup validation checks** to ensure backups are current
- **Weekly integrity verification** (runs on Sundays)
- **Replication to secondary location** via rsync with resumable transfers
- **Idempotent operation** - safe to re-run without creating duplicate backups

## Setup

### Prerequisites

Configure the following in cabinet:
- `keys.borg.repo` - Primary Borg repository location
  - Example: `ssh://u12345@u12345.your-storagebox.de:23/./syncthing-backups`
- `keys.borg.passphrase` - Borg repository passphrase (from `borg init`)
- `path.rainbow-borg` - Secondary replication target
  - Example: `ssh://tyler@<remote IP>:22/~/syncthing-backups-borg-repo`

**Note:** Ensure no trailing whitespace in these values.

### Installation

1. Adjust the script as needed for your backup paths (default: `/home/tyler/syncthing`)
2. Create a crontab entry to run the script on a recurring basis

## Usage

### Normal backup
```bash
./main.sh
```
Performs full backup, prune, compact, check, and replication.

### Replicate-only mode
```bash
./main.sh --replicate-only
```
Skips backup/prune/compact/check and only runs replication. Useful for:
- Retrying failed replication after network issues
- Manual replication without running a full backup cycle

### Idempotency

The script is safe to re-run multiple times:
- **Backup creation**: Skips if a backup from today already exists
- **Replication**: Uses `rsync --partial` to resume interrupted transfers

If replication fails mid-transfer, simply run `./main.sh --replicate-only` to resume where it left off.

## What Gets Backed Up

See **[docs/archive-contents.md](docs/archive-contents.md)** for the full inventory and **[docs/README.md](docs/README.md)** for disaster-recovery guides.

Summary:

- `$HOME/syncthing`, `$HOME/git` (no `.git`), `$HOME/.config`, `$HOME/.zshrc`, `$HOME/.affine`
- Staged per run: crontab, `/etc/cloudflared`, `/root/.config/rustdesk`
- Pre-export DB/config snapshots under `~/git/docker/*/database-backup`, `taiga-backup`, `pihole-backup`
- Compression: LZ4; exclusions for live DB trees and caches — details in `main.sh` and docs

## Disaster recovery

**[docs/](docs/)** — step-by-step restore for AI/operators (no secrets in repo).

## Backup Schedule

Retention policy:
- **Daily**: 7 backups
- **Weekly**: 4 backups
- **Monthly**: 6 backups

Integrity checks:
- **Weekly** (Sundays): Full `borg check --verify-data`
- **Every run**: Validates recent backup existence