# dailystatus
- Feel free to clone, but this is very custom to my setup and backup process
- Backs up logs, crontab, etc.
- Sends me an email each day with my home automation status, the weather forecast, Spotify information, and anything else I find useful

## Personal SRE scorecard

Every email starts with a **Personal SRE Scorecard** HTML table. Fields (missing data → `unknown / not configured`, never crash the email):

| Check | Source |
|-------|--------|
| Borg backups | `borg list` on `keys.borg.repo` (+ recent `~/.cabinet/log/borg-errors`) |
| Cloud / Rainbow drift | Cabinet `quality.<host>.updated_at` / `free_gb` from `quality/service_check.py` |
| SSL expiry | TLS `notAfter` for common `*.tyler.cloud` hosts |
| Disk free space | Same `quality` data (folded into the scorecard) |
| Pi-hole | Local Docker `pihole` container + `pihole status` when available |
| Rainbow | Ping host from `path.rainbow-borg`, quality row, local uptime if hostname is `rainbow` |
| Spotify analytics | Cabinet `spotipy.last_success` (stale if &gt; 24h) |
| Warnings / errors (24h) | Prefer Cabinet **Loki** (`log_query_issues_loki`) so rainbow sees cloud logs after Mongo log removal; fall back to local files |

The detailed warnings/errors section below the scorecard uses the same query, rendered as a compact level/message table.

## dependencies
- requests (`pip install requests`)
- [cabinet](https://pypi.org/project/cabinet/)
- Data comes from logs or information in `cabinet` produced by `../weather.py`

## usage

```bash
python3 main.py           # send email
python3 main.py --dry-run # print plain-text preview
```
