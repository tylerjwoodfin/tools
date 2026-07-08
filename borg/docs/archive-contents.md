# What is in each Borg archive

Source: `~/git/tools/borg/main.sh`. Archives use compression `lz4`.

## Top-level paths (always attempted)

| Path | Notes |
|------|--------|
| `$HOME/syncthing` | Syncthing-synced data |
| `$HOME/git` | Docker stacks, dotfiles, tools (**`.git` dirs excluded**) |
| `$HOME/.zshrc` | Shell config |
| `$HOME/.config` | Includes `rustdesk/`, app configs |
| `$HOME/.affine` | Affine local data |
| Temp dir (see below) | Crontab + staged root-only configs |

## Staged inside temp directory (per backup run)

Borg stores these under a **random** `/tmp/tmp.XXXXXX/` path in the archive. Search the archive rather than hard-coding the temp name:

| Subdirectory | Source on disk | Restore target |
|--------------|----------------|----------------|
| `crontab.txt` | User crontab | `crontab crontab.txt` |
| `etc-cloudflared/` | `/etc/cloudflared/` | `/etc/cloudflared/` |
| `root-config-rustdesk/` | `/root/.config/rustdesk/` | `/root/.config/rustdesk/` |

Staging requires sudo helpers installed via `install-stage-cloudflared-sudo.sh`. If staging failed at backup time, warnings appear in cabinet logs under `~/.cabinet/log/borg-errors/`.

## Pre-export artifacts (under `~/git/docker/...`)

Created immediately before `borg create`, then deleted after backup. They **are** in the archive for that day:

| Stack | Export path | Live data excluded from Borg |
|-------|-------------|------------------------------|
| Immich | `docker/immich/database-backup/immich-database.sql` | `docker/immich/postgres/` |
| Affine | `docker/affine/database-backup/affine-database.sql` | postgres data dir |
| Authentik | `docker/authentik/database-backup/authentik-database.sql` | `postgresql/`, `redis/` |
| Miniflux | `docker/miniflux/database-backup/miniflux-database.sql` | postgres data dir |
| Taiga | `docker/taiga-docker/taiga-backup/taiga_db.sql`, `media/`, `static/` | named volumes |
| MongoDB | `docker/mongodb/database-backup/mongodump.archive.gz` | `docker/mongodb/data/` |
| Vaultwarden | `docker/vaultwarden/database-backup/vaultwarden-snapshot.db` | live `db.sqlite3*` |
| RustDesk | `docker/rustdesk/database-backup/hbbs-snapshot.db` | live `db_v2.sqlite3*` |
| Pi-hole (cloud) | `docker/pihole/cloud/pihole-backup/pihole-etc.tar.gz` | live `etc-pihole/` tree |
| Pi-hole (rainbow) | `docker/pihole/rainbow/pihole-backup/pihole-etc.tar.gz` | live `etc-pihole/` tree |
| Uptime Kuma | `docker/uptime-kuma/database-backup/uptime-kuma-mariadb.sql.gz` | `data/mariadb/` |

**RustDesk server keys** (`id_ed25519`, `id_ed25519.pub`) live in `docker/rustdesk/data/` and are copied as-is (not the live SQLite files).

## Borg exclude patterns (not in archive)

Notable excludes from `main.sh`:

- `**/.git`, `**/.github` under `~/git`
- Live Postgres data dirs (Immich, Authentik, Miniflux, generic `pgdata`)
- `docker/mongodb/data`
- `docker/vaultwarden/data/db.sqlite3*`
- `docker/rustdesk/data/db_v2.sqlite3*`
- `docker/uptime-kuma/data/mariadb`
- Live Pi-hole `etc-pihole` trees (use `pihole-etc.tar.gz` instead)
- `--exclude-caches`

## Stacks without dedicated DB export in `main.sh`

These rely on compose files, bind mounts, and/or Docker named volumes present under `~/git` or created on first `docker compose up`:

- Dawarich (Postgres in named volume `db_data` — check Syncthing for separate `pg_dump` from crontab)
- Gitea, Loki, Plex, music-stack, sure.am, wireguard, shared, homeassistant, *arr stack, etc.

For named volumes not bind-mounted into `~/git`, data may **only** exist inside Docker volumes unless separately exported. After restore, check `docker volume ls` and stack READMEs.

## Replication

`main.sh` rsyncs the Borg repo to `path.rainbow-borg` when checks pass. If primary repo is unavailable, use the secondary copy with the **same passphrase**.
