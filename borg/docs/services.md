# Per-service restore notes

Paths are relative to `$HOME/git/docker/` unless noted. Read each stack's `README.md` and `.env.example` after restore.

**General pattern for SQL export stacks:**

1. Ensure `.env` exists (from Borg extract).
2. `docker compose up -d` database container only (or full stack stopped app until DB restored).
3. Copy/import dump into data directory per instructions below.
4. `docker compose up -d`.

---

## RustDesk (self-hosted ID + relay)

| Item | Location |
|------|----------|
| Compose | `rustdesk/docker-compose.yml` |
| Server keys | `rustdesk/data/id_ed25519`, `id_ed25519.pub` |
| Peer DB snapshot | `rustdesk/database-backup/hbbs-snapshot.db` |
| Client config | `~/.config/rustdesk/` |
| Service config | `/root/.config/rustdesk/` (from staged `root-config-rustdesk/`) |

```bash
cd ~/git/docker/rustdesk

# Restore peer DB if snapshot exists
if [ -f database-backup/hbbs-snapshot.db ]; then
  sudo mkdir -p data
  sudo cp database-backup/hbbs-snapshot.db data/db_v2.sqlite3
  sudo rm -f data/db_v2.sqlite3-wal data/db_v2.sqlite3-shm
  sudo chown -R root:root data   # hbbs container runs as root
fi

docker compose up -d

# Restore service + user config from Borg staging (paths vary)
sudo systemctl enable --now rustdesk
```

**Clients:** ID server = host LAN IP or Tailscale IP; Key = contents of `data/id_ed25519.pub`. See `rustdesk/README.md`. LAN clients must **not** use Tailscale IP when MagicDNS/hairpin is an issue — use LAN IP.

**UFW:** allow `21115:21119/tcp`, `21116/udp`.

---

## Immich

| Export | `immich/database-backup/immich-database.sql` |
| Excluded | `immich/postgres/` |

```bash
cd ~/git/docker/immich
docker compose up -d database
# Import (example — adjust user/db names from .env)
docker exec -i immich_postgres psql -U postgres < database-backup/immich-database.sql
docker compose up -d
```

Photo library paths are in `.env` (`UPLOAD_LOCATION`); ensure bind mounts exist.

---

## Affine

| Export | `affine/database-backup/affine-database.sql` |

Import into `affine_postgres` after DB container is up. Custom image build documented in `affine/README.md`.

---

## Authentik

| Export | `authentik/database-backup/authentik-database.sql` |

Restore before relying on SSO for Grafana, Immich proxy, etc. See `authentik/README.md`.

---

## Miniflux

| Export | `miniflux/database-backup/miniflux-database.sql` |

---

## Taiga

| Export | `taiga-docker/taiga-backup/taiga_db.sql`, `media/`, `static/` |

```bash
cd ~/git/docker/taiga-docker
# Restore DB via compose exec; restore media/static into named volumes using
# docker run -v volume:/data -v $(pwd)/taiga-backup/media:/backup alpine cp -a /backup/. /data/
```

---

## MongoDB

| Export | `mongodb/database-backup/mongodump.archive.gz` |

```bash
cd ~/git/docker/mongodb
docker compose up -d
gunzip -c database-backup/mongodump.archive.gz | docker exec -i mongodb mongorestore --archive
```

---

## Vaultwarden

| Export | `vaultwarden/database-backup/vaultwarden-snapshot.db` |

```bash
cd ~/git/docker/vaultwarden
docker compose stop vaultwarden 2>/dev/null || true
cp database-backup/vaultwarden-snapshot.db data/db.sqlite3
rm -f data/db.sqlite3-wal data/db.sqlite3-shm
docker compose up -d
```

---

## Pi-hole

| Export | `pihole/cloud/pihole-backup/pihole-etc.tar.gz` (and `rainbow/` stack if used) |

```bash
cd ~/git/docker/pihole/cloud
docker compose down
tar -xzf pihole-backup/pihole-etc.tar.gz   # extracts etc-pihole, etc-dnsmasq.d
docker compose up -d
```

Live `etc-pihole/` is excluded from Borg; **must** use tar backup.

---

## Uptime Kuma

| Export | `uptime-kuma/database-backup/uptime-kuma-mariadb.sql.gz` |

```bash
cd ~/git/docker/uptime-kuma
gunzip -c database-backup/uptime-kuma-mariadb.sql.gz | docker exec -i <kuma-container> mariadb -S /app/data/run/mariadb.sock kuma
```

Container name varies; find with `docker ps`.

---

## Cloudflared tunnels

**Preferred:** restore staged `etc-cloudflared/` → `/etc/cloudflared/`, then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now cloudflared@immich cloudflared@gitea  # etc.
```

**Fallback:** `~/git/cloudflared-setup/restore-tunnels.sh` — requires Cloudflare login and may create new tunnel IDs; update DNS in Cloudflare dashboard.

Systemd unit templates live in `cloudflared-setup/`. Ingress YAML templates are in git; credentials JSON are **only** in `/etc/cloudflared` or Borg staging.

---

## Dawarich

Postgres uses Docker named volume `db_data` — **not** exported in `main.sh`. Check:

1. Restored `crontab.txt` for a `pg_dump` job writing into `~/syncthing/`
2. `~/git/docker/dawarich/README.md`

If only named volume existed, you may need a SQL dump from Syncthing or accept data loss for that stack.

---

## Gitea, Loki, Plex, music-stack, wireguard, homeassistant, *arr

- Compose + bind mounts under `~/git/docker/<stack>/`
- Restore `.env` from Borg extract
- `docker compose up -d`
- Large media may live outside `~/git` (bind mounts to `~/syncthing` or disks) — restore those paths from Syncthing archive

---

## Syncthing

Data is under `$HOME/syncthing` in the archive. Reinstall Syncthing, restore directory, re-add folders and device IDs (device cert in `~/.config/syncthing` if backed up under `.config`).

---

## Dotfiles / system services

`~/git/dotfiles/scripts/` contains ansible playbooks and systemd unit **templates** (RustDesk, Pi-hole, VPN namespaces, etc.). After restore, re-run playbook or copy units from `dotfiles/scripts/restore/` if services are missing.
