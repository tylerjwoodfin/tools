# pihole block/allow

## motivation
This script is used to enable/disable websites at predetermined times (by my crontab) to
maintain a healthy relationship with screen time and avoid distracting websites at undesirable
hours.

## usage
For my use case:
- `zsh downtime.sh block overnight` is run at a predetermined time in the evening
- `zsh downtime.sh allow overnight` is run at at a predetermined time overnight such that I
can wake up without restrictions.

## explanation
- `overnight` is an alias that I've set using [cabinet](https://pypi.org/project/cabinet/).

In my Cabinet file, I have something like:
```
{
    "path": {
        "blocklist": {
            "afternoon": "/path/to/syncthing/md/docs/network/pihole_blocklist_afternoon.md",
            "overnight": "/path/to/syncthing/md/docs/network/pihole_blocklist_overnight.md"
        }
        ...
    }
    ...
}
```
- `cabinet -g path blocklist overnight` returns "/path/to/syncthing/md/docs/network/pihole_blocklist_overnight.md"
- Each domain is looped through and allowed/disallowed, depending on $1.
- I can expand my blocklist schedule without modifying the code by simply adding new items to Cabinet and changing the Crontab.