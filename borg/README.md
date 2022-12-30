# borg

- an automated backup script to back my Syncthing instance up to Hetzner

## setup

- create two files in `~/syncthing/securedata/keys` named `BORG_REPO` and `BORG_PASSPHRASE`, containing the respective information.
    - make sure that there is no trailing whitespace at the end of these files.
    - `BORG_REPO` could look like `ssh://u12345@u12345.your-storagebox.de:23/./syncthing-backups`
    - `BORG_PASSPHRASE` comes from the password entered when `borg init` was called. I store this in a password manager.
- adjust the script as needed to match your backup frequency and paths
- create a crontab entry to call this script on a recurring basis

## notes

- by default, this script backs up /home/tyler/syncthing. This is hardcoded as this is a script specific to my use case; adjust as necessary.