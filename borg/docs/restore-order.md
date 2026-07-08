# Recommended restore order

Dependencies matter: tunnels, databases, and auth before apps that rely on them.

## Phase 0 — Base system

1. Install Linux (same major version as before if possible).
2. Create user `tyler`, install: `docker`, `docker compose`, `borgbackup`, `cabinet`, `git`, `rsync`, `ufw`, `cloudflared` (if used).
3. Restore **cabinet** config and Borg passphrase.
4. Extract Borg archive (see [extract-from-borg.md](extract-from-borg.md)).

## Phase 1 — User tree

1. Restore `$HOME/git` (Docker stacks, dotfiles, tools).
2. Restore `$HOME/syncthing`.
3. Restore `$HOME/.config` (includes RustDesk client config).
4. Restore `$HOME/.zshrc`, `$HOME/.affine` if present.
5. Install dotfiles / run ansible if you use `~/git/dotfiles/scripts/setup.sh` (optional; after tree is in place).

## Phase 2 — Host-level secrets and scheduling

1. Restore `/etc/cloudflared/` from staged `etc-cloudflared/` **or** follow `~/git/cloudflared-setup/restore-tunnels.sh` (may need Cloudflare re-login).
2. Enable cloudflared systemd units from `cloudflared-setup/cloudflared@*.service`.
3. Restore crontab from staged `crontab.txt`.
4. Open firewall ports (UFW): Pi-hole 53/80, RustDesk 21115–21119/tcp + 21116/udp, etc. — match pre-disaster rules.

## Phase 3 — Docker infrastructure

1. `docker network` / compose prerequisites (often created automatically).
2. Start **databases and auth** before apps that depend on them:
   - MongoDB (if apps need it)
   - Authentik
   - Postgres-backed stacks (Immich, Affine, Miniflux, Taiga, Dawarich)
3. Restore DB **from snapshots** before or right after first container start — see [services.md](services.md).

## Phase 4 — Application stacks

Start order (loose; adjust per stack README):

1. Pi-hole (if on this host)
2. Gitea / git hosting
3. Immich, Affine, media stacks
4. RustDesk (`docker compose up -d` in `~/git/docker/rustdesk`)
5. RustDesk **client** systemd service: `sudo systemctl enable --now rustdesk`
6. Remaining compose projects (Loki, Kuma, Vaultwarden, Taiga, sure.am, …)

## Phase 5 — Validation

- [ ] `docker ps` — expected containers up
- [ ] Cloudflared tunnels running; public URLs reach services
- [ ] RustDesk: clients show **Ready**; connect by ID; LAN uses LAN IP for ID/relay server
- [ ] Syncthing peers reconnect
- [ ] Re-run `~/git/tools/borg/main.sh` once system is stable (re-establish backups)

## Phase 6 — Reinstall Borg staging helpers (on new machine)

```bash
sudo sh ~/git/tools/borg/install-stage-cloudflared-sudo.sh
```

Ensures future backups include `/root/.config/rustdesk` and `/etc/cloudflared`.

## What not to do early

- Do not start application containers **before** restoring SQL dumps into their data dirs (where applicable).
- Do not publish restored `.env` or tunnel JSON files.
- Do not run `borg init` on an existing repo path (overwrites metadata).
