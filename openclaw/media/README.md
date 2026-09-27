# Media CLI

Cherry's narrow interface for the media stack on ice.

| Command | Backend |
| --- | --- |
| `add-movie` / `search-movie` | Radarr |
| `add-series --season current` / `search-series` | Sonarr |
| `status` | qBittorrent, plus Sonarr and Radarr queues |
| `add-music` | Sockseek daemon |
| `health` | Those services and the ProtonVPN container |

The stack itself lives in `~/git/docker/media` and runs on this machine. qBittorrent and Sockseek run inside Gluetun. This CLI calls their loopback HTTP APIs.

```bash
python3 ~/git/tools/openclaw/media/scripts/media_cli.py --json health
python3 ~/git/tools/openclaw/media/scripts/media_cli.py --json add-series "The Simpsons" --season current
```

Outcomes: `added`, `already_monitored`, `downloading`, `completed`, `no_results`, `backend_unavailable`, `vpn_unavailable`.
