# Secrets and cabinet

**Do not commit secrets to git.** Borg archives may contain sensitive files (`.env`, tunnel JSON, RustDesk keys). This doc lists **where operators store secrets**, not the values.

## Cabinet (required for backup script)

The backup script reads:

| Cabinet key | Purpose |
|-------------|---------|
| `keys.borg.repo` | Borg repository URL or path |
| `keys.borg.passphrase` | Borg repo encryption passphrase |
| `path.rainbow-borg` | Secondary rsync destination for the repo |

Restore cabinet **before** running `borg extract`. If cabinet is lost, you need an offline copy of the Borg passphrase and repo URL.

```bash
# Example: read repo URL (after cabinet is configured)
cabinet -g keys borg repo
export BORG_REPO="$(cabinet -g keys borg repo)"
export BORG_PASSPHRASE="$(cabinet -g keys borg passphrase)"
```

See `~/git/cabinet/README.md` for setup (`cabinet --configure`).

## In the Borg archive (treat as confidential)

These may appear in extracted trees — **do not paste into public issues or docs:**

| Location | Contents |
|----------|----------|
| `~/git/docker/*/.env` | Stack secrets (DB passwords, API keys, OIDC client secrets) |
| Staged `etc-cloudflared/` | Tunnel credential JSON, `cert.pem`, ingress YAML |
| `~/git/docker/rustdesk/data/id_ed25519*` | RustDesk **server** signing keys |
| `~/.config/rustdesk/` | Client config (may include server key field) |
| Staged `root-config-rustdesk/` | RustDesk **systemd service** config |
| `~/syncthing/**` | Personal documents and exports |

`.env` files are usually **gitignored** but are backed up by Borg if present on disk at backup time.

## Outside Borg (must be recovered separately if lost)

| Item | Typical source |
|------|----------------|
| Borg passphrase | Password manager / cabinet backup |
| Hetzner Storage Box SSH key / password | Hetzner panel |
| Cloudflare account / tunnel recreation | Cloudflare dashboard; `cloudflared tunnel login` |
| Tailscale tailnet | Tailscale admin; devices re-auth |
| GitHub / Gitea deploy keys | Regenerate in git hosting UI |
| RustDesk client **Key** (public) | `id_ed25519.pub` in restored `docker/rustdesk/data/` |
| WireGuard / Proton keys | Provider or `~/git/docker/wireguard` if in archive |
| SSL/TLS certs not under `/etc/cloudflared` | Let's Encrypt / Cloudflare |

## RustDesk-specific (no secrets in this doc)

After restore, all clients need the **same ID server address** and **Key** as the restored server:

- Server public key: file `id_ed25519.pub` under `~/git/docker/rustdesk/data/`
- ID server: host LAN IP or Tailscale IP (see `~/git/docker/rustdesk/README.md`)
- Relay server: same host as ID server for LAN clients

Service config: restore staged `root-config-rustdesk/` → `/root/.config/rustdesk/` and user config from `~/.config/rustdesk/`.
