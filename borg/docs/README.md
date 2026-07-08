# Borg disaster-recovery documentation

This folder is written for **humans and AI agents** restoring Tyler's home server from Borg backups. It describes what `main.sh` captures, how archives are laid out, and how to put services back online.

**Public repo rule:** These docs intentionally omit secrets (passphrases, API keys, tunnel credentials, RustDesk keys, passwords). Obtain those from **cabinet**, the password manager, or service dashboards after restore.

## Start here

| Doc | Purpose |
|-----|---------|
| [restore-overview.md](restore-overview.md) | Goals, machines, repo locations, high-level flow |
| [secrets-and-cabinet.md](secrets-and-cabinet.md) | What cabinet stores; what is *not* in git |
| [archive-contents.md](archive-contents.md) | Paths, staged snapshots, exclusions, pre-export artifacts |
| [extract-from-borg.md](extract-from-borg.md) | List archives, extract, find staged paths |
| [restore-order.md](restore-order.md) | Recommended sequence and dependencies |
| [services.md](services.md) | Per-stack restore steps (Docker, DB dumps, RustDesk, etc.) |
| [gaps-and-manual.md](gaps-and-manual.md) | What Borg does *not* cover; manual follow-up |

## Related code (same repo)

| Path | Role |
|------|------|
| `../main.sh` | Backup, prune, check, replicate (source of truth for behavior) |
| `../install-stage-cloudflared-sudo.sh` | NOPASSWD helpers for staging root-only paths during backup |
| `~/git/cloudflared-setup/` | Tunnel YAML templates, systemd units, `restore-tunnels.sh` (host-specific; use Borg snapshot first) |
| `~/git/docker/*/README.md` | Stack-specific notes where they exist |

## Quick restore checklist

1. Install OS, Docker, Borg, cabinet, cloudflared (as needed).
2. Restore cabinet / Borg passphrase (offline copy).
3. Access Borg repo (`keys.borg.repo`) or secondary copy (`path.rainbow-borg`).
4. Extract latest archive — see [extract-from-borg.md](extract-from-borg.md).
5. Follow [restore-order.md](restore-order.md) then [services.md](services.md).
6. Reconcile [gaps-and-manual.md](gaps-and-manual.md).
