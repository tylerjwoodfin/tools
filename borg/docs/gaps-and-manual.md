# Gaps and manual recovery

What Borg **does not** fully capture, or what may need operator action after restore.

## Not in Borg at all

| Item | Mitigation |
|------|------------|
| Installed OS packages | Reinstall apt packages; use dotfiles/ansible |
| `docker image` layers | Re-pull on `docker compose up` (custom builds: `docker compose build`) |
| Docker named volumes without export | See Dawarich, some Taiga data (Taiga media/static **are** exported when backup ran) |
| Running container memory state | Restart containers |
| External DNS at registrar | Cloudflare dashboard |
| TLS certs from Let's Encrypt (non-cloudflared) | Re-issue |
| iptables / nftables custom rules | Document in host notes; RustDesk may need UFW only |
| Hardware / disk layout | Manual |
| Borg passphrase | Password manager / cabinet backup |

## Partial / conditional backup

| Item | Condition |
|------|-----------|
| `/etc/cloudflared` | Only if staging succeeded (sudo helper installed) |
| `/root/.config/rustdesk` | Same |
| `database-backup/*` | Only if container was **running** at backup time |
| Pi-hole `pihole-etc.tar.gz` | Only if `etc-pihole` dir existed |
| Taiga media/static | Only if Taiga was up during backup |

Check backup logs: `~/.cabinet/log/borg-errors/` on a restored system (if that path was in Syncthing/git).

## Intentionally excluded (use exports instead)

| Live path | Use instead |
|-----------|-------------|
| `docker/*/postgres` data dirs | `database-backup/*.sql` |
| `docker/mongodb/data` | `mongodump.archive.gz` |
| `docker/vaultwarden/data/db.sqlite3*` | `vaultwarden-snapshot.db` |
| `docker/rustdesk/data/db_v2.sqlite3*` | `hbbs-snapshot.db` + `id_ed25519*` |
| `docker/pihole/*/etc-pihole` | `pihole-backup/pihole-etc.tar.gz` |
| `docker/uptime-kuma/data/mariadb` | `uptime-kuma-mariadb.sql.gz` |

If export is missing for a given date, try an older archive or accept partial loss.

## Cloudflare-specific

- Tunnel **UUIDs** in credential JSON must match Cloudflare dashboard (or restore full `/etc/cloudflared` from Borg).
- `restore-tunnels.sh` in `cloudflared-setup` contains host-specific IDs — treat as **last resort**; prefer Borg snapshot.
- `cert.pem` from `cloudflared tunnel login` may need regeneration on new machine.

## RustDesk-specific

- Client devices must be reconfigured with restored **Key** from `id_ed25519.pub`.
- Address book entries on clients are local — not in server backup.
- If both `id_ed25519` and `id_ed25519.pub` are lost, clients cannot use old server key; generate new server keys only as last resort (all clients must update Key).

## Git remotes

`~/git` is restored **without** `.git` directories (excluded). Re-clone repos from Gitea/GitHub into `~/git` or restore `.git` from a machine that still has clones. Compose and config files in the archive are still valuable.

**Practical approach:** After extract, for each project dir under `~/git`, `git init` + add remote + fetch — or re-clone fresh and copy restored `docker/` trees and `.env` over.

## After restore checklist

1. Verify latest Borg archive date vs data loss window.
2. Walk [services.md](services.md) for each running stack.
3. Test Cloudflared / Tailscale / WireGuard connectivity.
4. Test RustDesk end-to-end from a LAN client.
5. Run `~/git/tools/borg/main.sh` to resume backups.
6. Update this doc if `main.sh` gains new export paths.
