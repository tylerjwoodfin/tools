#! /usr/bin/env python3
"""
This script performs daily maintenance tasks on the system.
"""

import subprocess
import os
from cabinet import Cabinet


def run_command(command, timeout=10):
    """Run a shell command and return the result"""
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", f"Command timed out after {timeout} seconds"
    except Exception as e:
        return False, "", str(e)


def get_directory_snapshot(directory):
    """Get a snapshot of all files in a directory with their modification times"""
    snapshot = {}
    if not os.path.exists(directory):
        return None

    for root, dirs, files in os.walk(directory):
        for file in files:
            filepath = os.path.join(root, file)
            try:
                snapshot[filepath] = os.path.getmtime(filepath)
            except (OSError, FileNotFoundError):
                pass

    return snapshot


def compare_snapshots(before, after):
    """Compare two directory snapshots and return added/modified files"""
    if before is None or after is None:
        return []

    changes = []

    # Check for new files
    for filepath in after:
        if filepath not in before:
            changes.append(f"Added: {filepath}")
        elif after[filepath] != before[filepath]:
            changes.append(f"Modified: {filepath}")

    return changes


def apply_stow():
    """Apply stow configuration"""
    cab = Cabinet()
    cab.log("Running apply_stow.py script")

    # Get snapshot of dotfiles-backup before running the script
    backup_dir = os.path.expanduser("~/dotfiles-backup")
    snapshot_before = get_directory_snapshot(backup_dir)

    command = "python3 ~/git/dotfiles/scripts/apply_stow.py"
    success, stdout, stderr = run_command(command, timeout=300)

    # Get snapshot of dotfiles-backup after running the script
    snapshot_after = get_directory_snapshot(backup_dir)

    # Check for changes
    if snapshot_before is not None and snapshot_after is not None:
        changes = compare_snapshots(snapshot_before, snapshot_after)
        if changes:
            cab.log(
                f"⚠ Files changed in ~/dotfiles-backup during apply_stow execution:",
                level="warning",
            )
            for change in changes:
                cab.log(f"  {change}", level="warning")

    if success:
        cab.log(f"✓ apply_stow.py completed successfully")
        if stdout:
            cab.log(f"Output: {stdout}")
    else:
        cab.log(f"✗ apply_stow.py failed", level="error")
        if stderr:
            cab.log(f"Error: {stderr}", level="error")
        if stdout:
            cab.log(f"Output: {stdout}")

    return success


def main():
    """
    Main function to perform daily maintenance tasks.
    """
    cab = Cabinet()

    cab.log("Starting daily maintenance tasks")

    # Apply stow configuration
    apply_stow()

    cab.log("Daily maintenance tasks completed")


if __name__ == "__main__":
    main()
