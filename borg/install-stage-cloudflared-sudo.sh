#!/bin/sh
# One-time setup: installs Borg staging helpers under /usr/local/sbin and adds
# NOPASSWD sudo for the invoking user only (for cron/non-inter Borg backups).
#
# Helpers: borg-stage-cloudflared, borg-stage-rustdesk-root
# Run: sudo sh install-stage-cloudflared-sudo.sh

set -e

if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root: sudo sh install-stage-cloudflared-sudo.sh" >&2
    exit 1
fi

_here=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
_cf_src="$_here/borg-stage-cloudflared"
_cf_dst="/usr/local/sbin/borg-stage-cloudflared"
_rd_src="$_here/borg-stage-rustdesk-root"
_rd_dst="/usr/local/sbin/borg-stage-rustdesk-root"
_sudoers="/etc/sudoers.d/borg-stage-cloudflared"

if [ ! -f "$_cf_src" ]; then
    echo "Missing $_cf_src (run from tools/borg/)" >&2
    exit 1
fi

if [ ! -f "$_rd_src" ]; then
    echo "Missing $_rd_src (run from tools/borg/)" >&2
    exit 1
fi

TARGET_USER="${SUDO_USER:-$(logname 2>/dev/null)}"
if [ -z "$TARGET_USER" ] || [ "$TARGET_USER" = root ]; then
    TARGET_USER="$(getent passwd 1000 2>/dev/null | cut -d: -f1)"
fi
if [ -z "$TARGET_USER" ]; then
    echo "Could not detect non-root user (set TARGET_USER)." >&2
    exit 1
fi

install -o root -g root -m 0755 "$_cf_src" "$_cf_dst"
install -o root -g root -m 0755 "$_rd_src" "$_rd_dst"

umask 077
{
    printf 'Defaults!/usr/local/sbin/borg-stage-cloudflared !requiretty\n'
    printf 'Defaults!/usr/local/sbin/borg-stage-rustdesk-root !requiretty\n'
    printf '%s ALL=(root) NOPASSWD: /usr/local/sbin/borg-stage-cloudflared\n' "$TARGET_USER"
    printf '%s ALL=(root) NOPASSWD: /usr/local/sbin/borg-stage-rustdesk-root\n' "$TARGET_USER"
} >"$_sudoers.$$"
mv "$_sudoers.$$" "$_sudoers"
chmod 0440 "$_sudoers"

if command -v visudo >/dev/null 2>&1; then
    visudo -c -f "$_sudoers" >/dev/null
fi

echo "Installed $_cf_dst, $_rd_dst, and $_sudoers for user '$TARGET_USER'."
echo "Next Borg backup should log staged /etc/cloudflared and /root/.config/rustdesk"
