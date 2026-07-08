# Extracting data from Borg

## Prerequisites

- `borgbackup` installed
- `BORG_REPO` and `BORG_PASSPHRASE` from cabinet (see [secrets-and-cabinet.md](secrets-and-cabinet.md))
- Enough disk space for a full extract (or use `--strip-components` / path-specific extract)

## List archives

```bash
export BORG_REPO="$(cabinet -g keys borg repo)"
export BORG_PASSPHRASE="$(cabinet -g keys borg passphrase)"

borg list
borg list --short | tail -5
```

Pick the newest archive, or the last one before an incident.

## Verify archive (optional)

```bash
borg check
borg check --verify-data   # slower; weekly on Sundays on live system
```

## Full extract to a staging directory

Prefer extracting to a staging dir first, then rsync/move into place:

```bash
RESTORE_ROOT="$HOME/borg-restore-$(date +%Y%m%d)"
mkdir -p "$RESTORE_ROOT"

borg extract --verbose "$RESTORE_ROOT" ::cloud-YYYY-MM-DDTHH:MM:SS
```

Replace the archive name with the one from `borg list`.

## Extract specific paths only

```bash
borg extract --verbose "$RESTORE_ROOT" ::ARCHIVE_NAME \
  home/tyler/git \
  home/tyler/syncthing \
  home/tyler/.config
```

Path prefixes in the archive mirror absolute paths without leading `/` (Borg default). Confirm with:

```bash
borg list ::ARCHIVE_NAME | head -50
```

## Find staged cloudflared / rustdesk / crontab

Staged paths live under a temp directory:

```bash
borg list ::ARCHIVE_NAME | grep -E 'etc-cloudflared|root-config-rustdesk|crontab.txt'
```

Example archive paths:

```text
tmp/tmp.Ab12Cd/etc-cloudflared/immich.yml
tmp/tmp.Ab12Cd/root-config-rustdesk/RustDesk2.toml
tmp/tmp.Ab12Cd/crontab.txt
```

Extract that temp tree:

```bash
borg extract --verbose "$RESTORE_ROOT" ::ARCHIVE_NAME \
  --strip-components 1 \
  tmp/tmp.Ab12Cd/etc-cloudflared
```

Adjust `strip-components` so files land where you want.

## Restore into live home (after review)

```bash
# Example: restore git tree
rsync -aAXH --info=progress2 \
  "$RESTORE_ROOT/home/tyler/git/" "$HOME/git/"

rsync -aAXH --info=progress2 \
  "$RESTORE_ROOT/home/tyler/.config/" "$HOME/.config/"
```

Use `-n` dry run first. Do **not** blindly overwrite a running system's `/etc/cloudflared` without stopping tunnel services.

## Staged system paths

```bash
# Cloudflared (stop services first)
sudo systemctl stop 'cloudflared@*' 2>/dev/null || true
sudo rsync -a "$RESTORE_ROOT/tmp/.../etc-cloudflared/" /etc/cloudflared/
sudo chown -R root:root /etc/cloudflared
sudo chmod 600 /etc/cloudflared/*.json /etc/cloudflared/cert.pem 2>/dev/null || true

# RustDesk service config
sudo mkdir -p /root/.config/rustdesk
sudo rsync -a "$RESTORE_ROOT/tmp/.../root-config-rustdesk/" /root/.config/rustdesk/
sudo chown -R root:root /root/.config/rustdesk

# Crontab
crontab "$RESTORE_ROOT/tmp/.../crontab.txt"
```

## Secondary repo

If primary `keys.borg.repo` is down, point `BORG_REPO` at the rainbow mirror (`path.rainbow-borg`). Same passphrase.

## From rainbow via rsync (repo-level)

On a machine with SSH access to the mirror:

```bash
mkdir -p "$HOME/borg-repo-local"
rsync -av "user@rainbow-host:path/to/borg-repo/" "$HOME/borg-repo-local/"
export BORG_REPO="$HOME/borg-repo-local"
```

Use the actual path from cabinet; do not commit it to git.
