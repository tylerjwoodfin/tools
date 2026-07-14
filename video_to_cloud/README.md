# Video to Cloud

Watches `~/syncthing/documents/video-to-cloud` for new files, moves them into
`~/syncthing/video`, and emails a success notice via [Cabinet](https://github.com/tylerjwoodfin/cabinet) Mail.

## Why polling + empty-dir sweep?

Syncthing often creates temp files and grows real files while syncing. This tool:

1. **Only moves files** — parent folders under `video-to-cloud` are left alone during moves so Syncthing does not fight deletes mid-sync.
2. **Waits for stability** — a file must keep the same size/mtime for 30s before moving.
3. **Cleans empty parents daily at 4am** — removes leftover empty folders under the drop dir (never the drop root itself).
4. **Resolves name conflicts** — if the destination already exists, the new file is renamed to `name.conflict-YYYYMMDD-HHMMSS.ext`.

Drop a file or a nested folder of files into `video-to-cloud`; relative paths are preserved under `~/syncthing/video`.

## Dependencies

- Python 3.12+
- [cabinet](https://pypi.org/project/cabinet/) (with Mail configured)

## Usage

```bash
# long-running watcher (systemd)
python3 ~/git/tools/video_to_cloud/main.py

# process currently present files once (treats them as already stable)
python3 ~/git/tools/video_to_cloud/main.py --once

# only remove empty leftover folders
python3 ~/git/tools/video_to_cloud/main.py --cleanup

# log what would happen
python3 ~/git/tools/video_to_cloud/main.py --once --dry-run
```

Useful flags: `--watch-dir`, `--dest-dir`, `--stable-seconds`, `--poll-seconds`, `--cleanup-hour`.

## systemd

```bash
mkdir -p ~/syncthing/log
sudo cp ~/git/tools/video_to_cloud/video-to-cloud.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now video-to-cloud.service
sudo systemctl status video-to-cloud.service
```

Logs append to `~/syncthing/log/video-to-cloud.log`.

## Email

Uses Cabinet Mail defaults (`cabinet -> email -> to`). Subject looks like:

`Video moved: Family Guy S24E11 ….mkv`
