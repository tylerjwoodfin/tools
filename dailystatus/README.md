# dailystatus
- Feel free to clone, but this is very custom to my setup and backup process
- Backs up logs, crontab, etc.
- Sends me an email each day with my home automation status, the weather forecast, Spotify information, and anything else I find useful

## Email layout

1. Greeting + casual tomorrow weather (`68 and partly cloudy tomorrow`) from Cabinet `weather.data`
2. **Personal SRE Scorecard** table
3. Other sections (foodlog, Spotify details, warnings table, …)

## Personal SRE scorecard

Fields (missing data → `unknown / not configured`, never crash the email):

| Check | Source |
|-------|--------|
| Borg backups | `borg list` on `keys.borg.repo` (+ recent `~/.cabinet/log/borg-errors`) |
| Disk free space | Cabinet `quality.<host>.free_gb` from `quality/service_check.py` |
| Pi-hole | Local Docker `pihole` container + `pihole status` when available |
| Rainbow | Ping host from `path.rainbow-borg`; `quality.rainbow.updated_at` as “last health check”; uptime when running on rainbow |
| Spotify analytics | `Checked <age>; <n> songs.` from `spotipy.last_success` / `total_tracks` (stale if &gt; 24h) |
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
