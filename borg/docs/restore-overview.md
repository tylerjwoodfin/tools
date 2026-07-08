# Restore overview

## What this backup protects

Automated backups (`~/git/tools/borg/main.sh`) capture the **home server** state: personal files under Syncthing, the `~/git` tree (Docker stacks, dotfiles, tools), user config, and **point-in-time database exports** for stacks that cannot be copied safely while running.

Backups go to:

1. **Primary Borg repo** — URL in cabinet: `keys.borg.repo` (typically Hetzner Storage Box over SSH).
2. **Secondary copy** — cabinet: `path.rainbow-borg` (rsync mirror of the repo directory).

Archive names look like `{hostname}-{timestamp}` (e.g. `cloud-2026-07-07T12:00:00`). Retention: 7 daily, 4 weekly, 6 monthly.

## Primary machine profile

- **Hostname:** usually `cloud` (verify with `hostname` after restore).
- **Linux user:** `tyler` (adjust if your install differs).
- **Key paths:**
  - `$HOME/git` — Docker compose stacks, cloudflared-setup, dotfiles, tools
  - `$HOME/syncthing` — Syncthing-synced documents, photos, etc.
  - `$HOME/.config` — application config (includes `~/.config/rustdesk/`)
  - `/etc/cloudflared` — **not** in git; staged into each Borg archive (see [archive-contents.md](archive-contents.md))

## Disaster-recovery goal

Bring back **data and configuration** so Docker stacks, tunnels, RustDesk, Pi-hole, and Syncthing behave as before. Some components need **secrets from outside the archive** (cabinet, Cloudflare, Tailscale, Git hosting, etc.).

## Success criteria (minimal)

- [ ] Borg repo accessible; latest archive extracted to disk
- [ ] `$HOME/git` and `$HOME/syncthing` restored
- [ ] `$HOME/.config` restored
- [ ] `/etc/cloudflared` restored from staged archive (or rebuilt via `cloudflared-setup/`)
- [ ] Database **snapshots** restored where live DB files were excluded (see [services.md](services.md))
- [ ] Docker stacks `docker compose up -d` without missing `.env` files
- [ ] Crontab restored from archive `crontab.txt`
- [ ] Firewall / UFW and host networking validated (RustDesk ports, Pi-hole, etc.)

## What to read next

1. [secrets-and-cabinet.md](secrets-and-cabinet.md) — unlock Borg and service credentials
2. [extract-from-borg.md](extract-from-borg.md) — get files off the repo
3. [restore-order.md](restore-order.md) — order of operations
4. [services.md](services.md) — stack-by-stack detail
