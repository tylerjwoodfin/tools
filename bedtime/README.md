# Early bedtime

If Apple Health shows less than 7 hours asleep from 6pm yesterday through noon, and today is not in `cabinet -g holidays`:

- RemindMail sends **Early Bedtime** at noon.
- At 8:30pm, Pi-hole runs `downtime.py block afternoon --force` (the same YouTube/Roblox list as the 9:30pm cron).
- Cherry sends a Telegram reminder at 8:30pm to be in bed by 10.
- Do Not Disturb turns on at 8:30pm when the shortcut below runs.

A night with no sleep samples does not arm the protocol. The 9:30pm cron still runs on its usual days.

## Cloud crontab

On cloud, after this repo is on `main`:

```cron
30 20 * * * if [ -f "$HOME/git/tools/bedtime/early_bedtime.py" ]; then /usr/bin/python3 "$HOME/git/tools/bedtime/early_bedtime.py" apply; fi
```

The `if` keeps the job quiet until the file is present.

## Shortcuts

`shortcuts.py` writes two shortcut files. Import both on the Mac so they sync to the phone:

- **Early Bedtime Check** — personal automation, every day at 12:00pm, run immediately. Allow Shortcuts to read Sleep in Health.
- **Early Bedtime Do Not Disturb** — personal automation, every day at 8:30pm, run immediately.

The check shortcut SSHes to cloud (`192.168.1.101` port `62561`), the same host as Daily food log. It sends each sleep sample as `value<TAB>start<TAB>end`.

After the Do Not Disturb shortcut is in the local Shortcuts library, the Mac can run it at 8:30pm. Focus has to be shared across devices for that to change the phone.

```bash
ln -sf ~/git/tools/bedtime/launchd/com.tyler.early-bedtime-dnd.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.tyler.early-bedtime-dnd.plist
```

```bash
python3 ~/git/tools/bedtime/shortcuts.py
```

## Manual check

```bash
python3 ~/git/tools/bedtime/early_bedtime.py check --hours 6.2 --dry-run
python3 ~/git/tools/bedtime/early_bedtime.py status
python3 ~/git/tools/bedtime/early_bedtime.py apply --dry-run
```

`status` prints `early` or `normal` and nothing else.

## Tests

```bash
cd ~/git/tools/bedtime && python3 -m unittest test_early_bedtime.py
```
