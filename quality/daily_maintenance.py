#! /usr/bin/env python3
"""
This script performs daily maintenance tasks on the system.
"""

import subprocess
import os
import socket
import re
from datetime import datetime
from cabinet import Cabinet


def run_command(command, timeout=10):
    """Run a shell command and return the result"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", f"Command timed out after {timeout} seconds"
    except Exception as e:  # pylint: disable=broad-exception-caught
        return False, "", str(e)


def get_directory_snapshot(directory):
    """Get a snapshot of all files in a directory with their modification times"""
    snapshot = {}
    if not os.path.exists(directory):
        return None

    for root, _, files in os.walk(directory):
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

    # Check if script exists before running
    script_path = os.path.expanduser("~/git/dotfiles/scripts/apply_stow.py")
    if not os.path.exists(script_path):
        cab.log(
            f"✗ apply_stow.py script not found at {script_path}",
            level="error",
        )
        return False

    # Get snapshot of dotfiles-backup before running the script
    backup_dir = os.path.expanduser("~/dotfiles-backup")
    snapshot_before = get_directory_snapshot(backup_dir)

    command = f"python3 {script_path}"
    success, stdout, stderr = run_command(command, timeout=300)

    # Get snapshot of dotfiles-backup after running the script
    snapshot_after = get_directory_snapshot(backup_dir)

    # Check for changes
    if snapshot_before is not None and snapshot_after is not None:
        changes = compare_snapshots(snapshot_before, snapshot_after)
        if changes:
            cab.log(
                "⚠ Files changed in ~/dotfiles-backup during apply_stow execution:",
                level="warning",
            )
            for change in changes:
                cab.log(f"  {change}", level="warning")

    if success:
        cab.log("✓ apply_stow.py completed successfully")
        if stdout:
            cab.log(f"Output: {stdout}")
    else:
        cab.log("✗ apply_stow.py failed", level="error")
        if stderr:
            cab.log(f"Error: {stderr}", level="error")
        else:
            cab.log("No error output captured - script may have failed silently", level="warning")
        if stdout:
            cab.log(f"Output: {stdout}")
        # Log the command that was run for debugging
        cab.log(f"Command executed: {command}", level="debug")

    return success


def _ensure_ssh_remote(cab, remote_name="origin"):
    """
    Ensure the git remote uses SSH instead of HTTPS to avoid credential prompts.
    Returns True if remote is configured correctly, False otherwise.
    """
    try:
        # Get current remote URL
        result = subprocess.run(
            ["git", "remote", "get-url", remote_name],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            cab.log(f"Remote '{remote_name}' not found", level="warning")
            return False

        current_url = result.stdout.strip()

        # Get SSH port from config or environment
        ssh_port = cab.get("ports", "gitea") or os.environ.get("GIT_SSH_PORT")

        # If already using SSH, check if we need to convert to HTTPS (for Cloudflare Tunnel)
        if current_url.startswith("ssh://"):
            # Extract host from ssh://git@host:port/path or ssh://git@host/path
            match = re.match(r"ssh://git@([^/:]+)(?::\d+)?/(.+)", current_url)
            if match:
                host = match.group(1)
                path = match.group(2)

                # If host is git.tyler.cloud (behind Cloudflare Tunnel), convert to HTTPS
                if host == "git.tyler.cloud":
                    # Ensure path ends with .git
                    if not path.endswith(".git"):
                        path = f"{path}.git"

                    # Check if we have a personal access token configured
                    git_token = (
                        cab.get("keys", "gitea", "token")
                        or os.environ.get("GIT_TOKEN")
                        or os.environ.get("GITEA_TOKEN")
                    )

                    if git_token:
                        # Use token in URL: https://oauth2:TOKEN@host/path
                        https_url = f"https://oauth2:{git_token}@{host}/{path}"
                        cab.log(
                            "Using personal access token for HTTPS authentication",
                            level="info",
                        )
                    else:
                        # Use plain HTTPS URL (will need credentials from helper)
                        https_url = f"https://{host}/{path}"

                    subprocess.run(
                        ["git", "remote", "set-url", remote_name, https_url],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    log_url = (
                        https_url.rsplit("@", maxsplit=1)[-1]
                        if "@" in https_url
                        else https_url
                    )
                    cab.log(
                        f"Converted SSH to HTTPS for Cloudflare Tunnel host: {log_url}",
                        level="info",
                    )

                    # Configure credential helper for HTTPS if not already configured
                    cred_helper_result = subprocess.run(
                        ["git", "config", "--get", "credential.helper"],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if (
                        cred_helper_result.returncode != 0
                        or not cred_helper_result.stdout.strip()
                    ):
                        subprocess.run(
                            ["git", "config", "credential.helper", "store"],
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                        cab.log(
                            "Configured git credential helper for HTTPS", level="info"
                        )

                    # If we have a token but no credentials file, create it
                    if git_token:
                        cred_file = os.path.expanduser("~/.git-credentials")
                        cred_entry = f"https://oauth2:{git_token}@{host}\n"
                        try:
                            # Read existing credentials
                            existing_creds = ""
                            if os.path.exists(cred_file):
                                with open(cred_file, "r", encoding="utf-8") as f:
                                    existing_creds = f.read()

                            # Add entry if not already present
                            if (
                                f"https://oauth2:{git_token}@{host}"
                                not in existing_creds
                            ):
                                with open(cred_file, "a", encoding="utf-8") as f:
                                    f.write(cred_entry)
                                os.chmod(cred_file, 0o600)  # Secure permissions
                                cab.log(
                                    "Added credentials to ~/.git-credentials",
                                    level="info",
                                )
                        except (OSError, IOError) as e:
                            cab.log(
                                f"Could not write credentials file: {e}",
                                level="warning",
                            )

                    return True

                # For other hosts, check if port needs to be added
                port_match = re.search(r":(\d+)/", current_url)
                if port_match:
                    # Port already specified, keep as is
                    return True
                # No port specified - add port if configured
                if ssh_port:
                    updated_url = f"ssh://git@{host}:{ssh_port}/{path}"
                    subprocess.run(
                        ["git", "remote", "set-url", remote_name, updated_url],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    cab.log(
                        f"Added port {ssh_port} to SSH URL: {updated_url}", level="info"
                    )
                    return True
            # No port configured, keep as-is (will use default port 22)
            return True
        elif current_url.startswith("git@"):
            # git@host:path format
            match = re.match(r"git@([^:]+):(.+)", current_url)
            if match:
                host = match.group(1)
                path = match.group(2)

                # If host is git.tyler.cloud, convert to HTTPS
                if host == "git.tyler.cloud":
                    # Ensure path ends with .git
                    if not path.endswith(".git"):
                        path = f"{path}.git"

                    # Check if we have a personal access token configured
                    git_token = (
                        cab.get("keys", "gitea", "token")
                        or os.environ.get("GIT_TOKEN")
                        or os.environ.get("GITEA_TOKEN")
                    )

                    if git_token:
                        # Use token in URL: https://oauth2:TOKEN@host/path
                        https_url = f"https://oauth2:{git_token}@{host}/{path}"
                        cab.log(
                            "Using personal access token for HTTPS authentication",
                            level="info",
                        )
                    else:
                        # Use plain HTTPS URL (will need credentials from helper)
                        https_url = f"https://{host}/{path}"

                    subprocess.run(
                        ["git", "remote", "set-url", remote_name, https_url],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    log_url = (
                        https_url.rsplit("@", maxsplit=1)[-1]
                        if "@" in https_url
                        else https_url
                    )
                    cab.log(
                        f"Converted git@ URL to HTTPS for Cloudflare Tunnel host: {log_url}",
                        level="info",
                    )

                    # Configure credential helper
                    cred_helper_result = subprocess.run(
                        ["git", "config", "--get", "credential.helper"],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if (
                        cred_helper_result.returncode != 0
                        or not cred_helper_result.stdout.strip()
                    ):
                        subprocess.run(
                            ["git", "config", "credential.helper", "store"],
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                        cab.log(
                            "Configured git credential helper for HTTPS", level="info"
                        )

                    # If we have a token but no credentials file, create it
                    if git_token:
                        cred_file = os.path.expanduser("~/.git-credentials")
                        cred_entry = f"https://oauth2:{git_token}@{host}\n"
                        try:
                            # Read existing credentials
                            existing_creds = ""
                            if os.path.exists(cred_file):
                                with open(cred_file, "r", encoding="utf-8") as f:
                                    existing_creds = f.read()

                            # Add entry if not already present
                            if (
                                f"https://oauth2:{git_token}@{host}"
                                not in existing_creds
                            ):
                                with open(cred_file, "a", encoding="utf-8") as f:
                                    f.write(cred_entry)
                                os.chmod(cred_file, 0o600)  # Secure permissions
                                cab.log(
                                    "Added credentials to ~/.git-credentials",
                                    level="info",
                                )
                        except (OSError, IOError) as e:
                            cab.log(
                                f"Could not write credentials file: {e}",
                                level="warning",
                            )

                    return True

                # For other hosts, convert to ssh:// format if port is configured
                if ssh_port:
                    updated_url = f"ssh://git@{host}:{ssh_port}/{path}"
                    subprocess.run(
                        ["git", "remote", "set-url", remote_name, updated_url],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    cab.log(
                        f"Converted git@ URL to ssh:// format with port {ssh_port}: {updated_url}",
                        level="info",
                    )
                    return True
            # No port configured, keep as-is
            return True

        # If using HTTPS, check if we should convert to SSH
        if current_url.startswith("https://"):
            # Extract the path from HTTPS URL
            # Handle URLs with or without credentials: https://[user:pass@]host/path
            url_without_protocol = current_url.replace("https://", "")

            # Check if URL has credentials embedded
            if "@" in url_without_protocol:
                # Format: oauth2:TOKEN@host/path or user:pass@host/path
                _, host_and_path = url_without_protocol.split("@", 1)
                url_parts = host_and_path.split("/", 1)
            else:
                # Format: host/path
                url_parts = url_without_protocol.split("/", 1)

            if len(url_parts) >= 2:
                host = url_parts[0]
                path = url_parts[1]

                # Check if host is behind Cloudflare Tunnel (SSH won't work)
                # git.tyler.cloud uses Cloudflare Tunnel which only supports HTTP/HTTPS
                if host == "git.tyler.cloud":
                    # Keep HTTPS for Cloudflare Tunnel hosts
                    # Ensure path ends with .git
                    if not path.endswith(".git"):
                        path = f"{path}.git"

                    # Check if we have a personal access token configured
                    git_token = (
                        cab.get("keys", "gitea", "token")
                        or os.environ.get("GIT_TOKEN")
                        or os.environ.get("GITEA_TOKEN")
                    )

                    # Check if token is already in URL
                    if "@" in current_url and "oauth2:" in current_url:
                        # Token already embedded, keep as-is
                        cab.log("Token already embedded in HTTPS URL", level="debug")
                        return True

                    if git_token:
                        # Use token in URL: https://oauth2:TOKEN@host/path
                        https_url = f"https://oauth2:{git_token}@{host}/{path}"
                        cab.log(
                            "Using personal access token for HTTPS authentication",
                            level="info",
                        )
                    else:
                        # Use plain HTTPS URL (will need credentials from helper)
                        https_url = f"https://{host}/{path}"
                        cab.log(
                            "No git token found in config or environment. Using plain HTTPS URL.",
                            level="warning",
                        )
                        cab.log(
                            "Set token with: cabinet set git token YOUR_TOKEN",
                            level="warning",
                        )
                        cab.log(
                            "Or set environment variable: export GIT_TOKEN=YOUR_TOKEN",
                            level="warning",
                        )

                    # Always update URL to ensure it's correct
                    # (even if same, ensures token is embedded)
                    subprocess.run(
                        ["git", "remote", "set-url", remote_name, https_url],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    log_url = (
                        https_url.rsplit("@", maxsplit=1)[-1]
                        if "@" in https_url
                        else https_url
                    )
                    cab.log(
                        f"Set HTTPS URL for Cloudflare Tunnel host: {log_url}",
                        level="info",
                    )

                    # Configure credential helper for HTTPS if not already configured
                    cred_helper_result = subprocess.run(
                        ["git", "config", "--get", "credential.helper"],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if (
                        cred_helper_result.returncode != 0
                        or not cred_helper_result.stdout.strip()
                    ):
                        # Try to configure credential helper (store or cache)
                        subprocess.run(
                            ["git", "config", "credential.helper", "store"],
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                        cab.log(
                            "Configured git credential helper for HTTPS", level="info"
                        )

                    # If we have a token, also write it to credentials file
                    if git_token:
                        cred_file = os.path.expanduser("~/.git-credentials")
                        cred_entry = f"https://oauth2:{git_token}@{host}\n"
                        try:
                            # Read existing credentials
                            existing_creds = ""
                            if os.path.exists(cred_file):
                                with open(cred_file, "r", encoding="utf-8") as f:
                                    existing_creds = f.read()

                            # Add entry if not already present
                            if (
                                f"https://oauth2:{git_token}@{host}"
                                not in existing_creds
                            ):
                                with open(cred_file, "a", encoding="utf-8") as f:
                                    f.write(cred_entry)
                                os.chmod(cred_file, 0o600)  # Secure permissions
                                cab.log(
                                    "Added credentials to ~/.git-credentials",
                                    level="info",
                                )
                        except (OSError, IOError) as e:
                            cab.log(
                                f"Could not write credentials file: {e}",
                                level="warning",
                            )

                    return True

                # For other hosts, convert to SSH if port is configured
                # Ensure path ends with .git
                if not path.endswith(".git"):
                    path = f"{path}.git"

                # Use ssh:// format, with port only if configured
                if ssh_port:
                    ssh_url = f"ssh://git@{host}:{ssh_port}/{path}"
                    # Update remote URL
                    subprocess.run(
                        ["git", "remote", "set-url", remote_name, ssh_url],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    cab.log(
                        f"Converted remote URL from HTTPS to SSH: {ssh_url}",
                        level="info",
                    )
                    return True
                else:
                    # No SSH port configured, keep HTTPS
                    cab.log("Keeping HTTPS URL (no SSH port configured)", level="info")
                    return True
            else:
                cab.log(f"Could not parse HTTPS URL: {current_url}", level="warning")
                return False

        # Unknown URL format
        cab.log(f"Remote URL format not recognized: {current_url}", level="warning")
        return False

    except subprocess.CalledProcessError as e:
        cab.log(f"Error checking/updating remote URL: {e.stderr}", level="error")
        return False


def update_git_repo():
    """
    Update the Git repository to the latest main branch.
    Handle uncommitted changes by stashing them and creating a backup branch.
    """
    cab = Cabinet()
    log_path_git_backend_backups = cab.get("path", "cabinet", "log-backup")

    if not log_path_git_backend_backups:
        cab.log("Missing log-backup path for Git operations", level="error")
        return False

    if not os.path.exists(log_path_git_backend_backups):
        cab.log(
            f"Git repository path does not exist: {log_path_git_backend_backups}",
            level="error",
        )
        return False

    cab.log("Updating Git repository to latest main branch")

    # Change to the repository directory
    original_cwd = os.getcwd()
    try:
        os.chdir(log_path_git_backend_backups)

        # Check if we're in a Git repository
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            cab.log("Not a Git repository, skipping Git operations", level="warning")
            return True

        # Ensure remote uses SSH instead of HTTPS
        _ensure_ssh_remote(cab)

        # Check for uncommitted changes
        result = subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True, check=True
        )

        if result.stdout.strip():
            cab.log(
                "Uncommitted changes detected, creating backup branch", level="warning"
            )

            # Get current branch name
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                check=True,
            )
            current_branch = result.stdout.strip()

            # Create a backup branch with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_branch = f"backup_{timestamp}"

            # Stash current changes
            stash_result = subprocess.run(
                [
                    "git",
                    "stash",
                    "push",
                    "-m",
                    f"Auto-stash before pulling main - {timestamp}",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if stash_result.returncode != 0:
                cab.log(
                    f"Warning: Failed to stash changes: {stash_result.stderr}",
                    level="warning",
                )
            else:
                cab.log("Stashed changes")

            # Create backup branch from stash (only if stash was successful)
            if stash_result.returncode == 0:
                stash_branch_result = subprocess.run(
                    ["git", "stash", "branch", backup_branch],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if stash_branch_result.returncode == 0:
                    cab.log(f"Created backup branch: {backup_branch}")
                    # git stash branch checks out the new branch, so switch back to original branch
                    subprocess.run(["git", "checkout", current_branch], check=False)
                else:
                    cab.log(
                        f"Warning: Failed to create backup branch: {stash_branch_result.stderr}",
                        level="warning",
                    )

        # Fetch latest changes from remote
        # Set GIT_TERMINAL_PROMPT=0 to prevent interactive credential prompts
        # Set SSH connection timeout to prevent hanging
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        # Set SSH timeout: ConnectTimeout=10, ServerAliveInterval=5, ServerAliveCountMax=3
        ssh_opts = (
            "ssh -o ConnectTimeout=10 -o ServerAliveInterval=5 "
            "-o ServerAliveCountMax=3 -o StrictHostKeyChecking=no"
        )
        env["GIT_SSH_COMMAND"] = ssh_opts
        cab.log("Fetching latest changes from remote")
        try:
            fetch_result = subprocess.run(
                ["git", "fetch", "origin"],
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            cab.log("✗ Git fetch timed out after 60 seconds", level="error")
            return False

        if fetch_result.returncode != 0:
            cab.log(
                f"✗ Failed to fetch from origin: {fetch_result.stderr}", level="error"
            )
            return False

        # Switch to main branch
        subprocess.run(["git", "checkout", "main"], check=True)

        # Pull latest main
        try:
            result = subprocess.run(
                ["git", "pull", "origin", "main"],
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            cab.log("✗ Git pull timed out after 60 seconds", level="error")
            return False

        if result.returncode == 0:
            cab.log("✓ Successfully updated to latest main branch")
            if result.stdout.strip():
                cab.log(f"Git output: {result.stdout.strip()}")
        else:
            error_msg = result.stderr.strip()
            cab.log(f"✗ Failed to pull latest main: {error_msg}", level="error")
            # Provide helpful error message for credential issues
            if (
                "could not read Username" in error_msg
                or "No such device or address" in error_msg
            ):
                cab.log(
                    "Hint: Git credentials may not be configured. Consider:",
                    level="warning",
                )
                cab.log(
                    "  1. Setting up SSH keys and using SSH URL instead of HTTPS",
                    level="warning",
                )
                cab.log(
                    "  2. Configuring git credential helper: git config credential.helper store",
                    level="warning",
                )
                cab.log(
                    "  3. Using a personal access token in the remote URL",
                    level="warning",
                )
            return False

        return True

    except subprocess.CalledProcessError as e:
        cab.log(f"Git operation failed: {e.stderr}", level="error")
        return False
    except Exception as e:  # pylint: disable=broad-exception-caught
        cab.log(f"Unexpected error during Git operations: {str(e)}", level="error")
        return False
    finally:
        # Always return to original directory
        os.chdir(original_cwd)


def backup_files():
    """
    Back up essential files. Always backup cron and zsh, only backup notes and
    log if hostname is rainbow.
    """
    cab = Cabinet()
    device_name = socket.gethostname()

    cab.log("Starting backup tasks")

    # Get paths from cabinet
    log_path_git_backend_backups = cab.get("path", "cabinet", "log-backup")
    path_zshrc = os.path.expanduser("~/.zshrc")

    if not log_path_git_backend_backups:
        cab.log("Missing required paths for backup", level="error")
        return

    def build_backup_path(category, extension):
        """Helper function to construct backup file paths."""
        return os.path.join(
            log_path_git_backend_backups,
            device_name,
            f"{category}.{extension}",
        )

    # Always backup cron and zsh
    path_cron = build_backup_path("cron", "md")
    path_zsh = build_backup_path("zsh", "md")

    # Create directories if they don't exist
    backup_dirs = [os.path.dirname(path_cron), os.path.dirname(path_zsh)]

    # Define backup commands for cron and zsh (always run)
    backup_commands = [
        f"/usr/bin/crontab -l > '{path_cron}'",
        f"cp -r {path_zshrc} '{path_zsh}'",
    ]

    # Only backup notes and log if hostname is rainbow
    if device_name == "rainbow":
        path_notes = cab.get("path", "notes")
        path_log = cab.get("path", "log")

        if path_notes and path_log:
            path_notes_backup = build_backup_path("notes", "zip")
            path_log_backup = build_backup_path("log", "zip")

            # Add to backup directories
            backup_dirs.extend(
                [os.path.dirname(path_notes_backup), os.path.dirname(path_log_backup)]
            )

            # Add notes and log backup commands
            backup_commands.extend(
                [
                    f"zip -r '{path_notes_backup}' {path_notes}",
                    f"zip -r '{path_log_backup}' {path_log} "
                    f"--exclude='{os.path.join(path_log, 'songs', '*')}'",
                ]
            )
        else:
            cab.log("Missing notes or log paths for rainbow hostname", level="warning")
    else:
        cab.log("Skipping notes and log backup - not running on rainbow hostname")

    # Create all backup directories
    for backup_dir in backup_dirs:
        os.makedirs(backup_dir, exist_ok=True)

    # Execute each backup command
    for command in backup_commands:
        try:
            subprocess.run(command, shell=True, check=True)
            cab.log(f"✓ Backup completed: {command}")
        except subprocess.CalledProcessError as error:
            cab.log(
                f"✗ Command failed: {command} with error: {str(error)}", level="error"
            )
        except OSError as error:
            cab.log(
                f"✗ OS error for: {command} with error: {str(error)}", level="error"
            )

    cab.log("Backup tasks completed")


def commit_and_push_backups():
    """
    Commit the backup files and push to main branch.
    """
    cab = Cabinet()
    log_path_git_backend_backups = cab.get("path", "cabinet", "log-backup")
    device_name = socket.gethostname()

    if not log_path_git_backend_backups:
        cab.log("Missing log-backup path for Git operations", level="error")
        return False

    if not os.path.exists(log_path_git_backend_backups):
        cab.log(
            f"Git repository path does not exist: {log_path_git_backend_backups}",
            level="error",
        )
        return False

    # Change to the repository directory
    original_cwd = os.getcwd()
    try:
        os.chdir(log_path_git_backend_backups)

        # Check if we're in a Git repository
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            cab.log(
                "Not a Git repository, skipping commit/push operations", level="warning"
            )
            return True

        # Ensure we're on main branch
        branch_result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            check=False,
        )
        current_branch = (
            branch_result.stdout.strip() if branch_result.returncode == 0 else "unknown"
        )

        if current_branch != "main":
            cab.log(
                f"Not on main branch (currently on {current_branch}), switching to main",
                level="warning",
            )
            checkout_result = subprocess.run(
                ["git", "checkout", "main"], capture_output=True, text=True, check=False
            )
            if checkout_result.returncode != 0:
                cab.log(
                    f"✗ Failed to checkout main: {checkout_result.stderr}",
                    level="error",
                )
                return False

        # Ensure remote uses SSH instead of HTTPS
        _ensure_ssh_remote(cab)

        # Check for changes to commit
        result = subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True, check=True
        )

        if not result.stdout.strip():
            cab.log("No changes to commit")
            return True

        # Add all changes
        add_result = subprocess.run(
            ["git", "add", "."], capture_output=True, text=True, check=False
        )
        if add_result.returncode != 0:
            cab.log(f"✗ Failed to add changes: {add_result.stderr}", level="error")
            return False
        cab.log("Added all changes to staging")

        # Verify there are actually staged changes to commit
        diff_result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            capture_output=True,
            text=True,
            check=False,
        )
        if diff_result.returncode == 0:
            # No changes staged (exit code 0 means no differences)
            cab.log("No changes staged after git add, skipping commit")
            return True

        # Create commit message with current date
        current_date = datetime.now().strftime("%Y-%m-%d")
        commit_message = f"Added backups for {current_date} from {device_name}"

        # Commit changes
        result = subprocess.run(
            ["git", "commit", "-m", commit_message],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            cab.log(f"✓ Successfully committed: {commit_message}")
            if result.stdout.strip():
                cab.log(f"Commit output: {result.stdout.strip()}")
        else:
            error_msg = (
                result.stderr.strip() or result.stdout.strip() or "Unknown error"
            )
            cab.log(f"✗ Failed to commit: {error_msg}", level="error")
            if result.stdout.strip() and result.stdout.strip() != error_msg:
                cab.log(f"Commit stdout: {result.stdout.strip()}", level="error")
            return False

        # Pull latest changes before pushing to avoid conflicts
        # Set GIT_TERMINAL_PROMPT=0 to prevent interactive credential prompts
        # Set SSH connection timeout to prevent hanging
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        # Set SSH timeout: ConnectTimeout=10, ServerAliveInterval=5, ServerAliveCountMax=3
        ssh_opts = (
            "ssh -o ConnectTimeout=10 -o ServerAliveInterval=5 "
            "-o ServerAliveCountMax=3 -o StrictHostKeyChecking=no"
        )
        env["GIT_SSH_COMMAND"] = ssh_opts

        # Get remote URL for diagnostics
        remote_url_result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=False,
        )
        remote_url = (
            remote_url_result.stdout.strip()
            if remote_url_result.returncode == 0
            else "unknown"
        )

        # Pull with rebase to integrate remote changes before pushing
        cab.log("Pulling latest changes from remote...")
        try:
            pull_result = subprocess.run(
                ["git", "pull", "--rebase", "origin", "main"],
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=60,
            )
            if pull_result.returncode == 0:
                if pull_result.stdout.strip():
                    cab.log(f"Pull output: {pull_result.stdout.strip()}")
            else:
                # Pull failed - could be conflicts or network issue
                pull_error = pull_result.stderr.strip()
                if "CONFLICT" in pull_result.stdout or "conflict" in pull_error.lower():
                    cab.log(
                        "✗ Pull failed due to merge conflicts. Skipping push.",
                        level="warning",
                    )
                    cab.log(
                        "Resolve conflicts manually and push later.", level="warning"
                    )
                    return False
                else:
                    cab.log(
                        f"⚠ Pull had issues but continuing: {pull_error}",
                        level="warning",
                    )
        except subprocess.TimeoutExpired:
            cab.log("✗ Git pull timed out after 60 seconds", level="error")
            return False

        # Push to main branch
        try:
            result = subprocess.run(
                ["git", "push", "origin", "main"],
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            cab.log("✗ Git push timed out after 60 seconds", level="error")
            cab.log(f"Remote URL: {remote_url}", level="debug")
            return False

        if result.returncode == 0:
            cab.log("✓ Successfully pushed to main branch")
            if result.stdout.strip():
                cab.log(f"Push output: {result.stdout.strip()}")
        else:
            error_msg = result.stderr.strip()
            cab.log(f"✗ Failed to push to main: {error_msg}", level="error")
            cab.log(f"Remote URL: {remote_url}", level="debug")

            # Provide helpful error messages for common issues
            if "non-fast-forward" in error_msg or "rejected" in error_msg.lower():
                cab.log(
                    (
                        "Push rejected - local branch is behind remote. "
                        "This should be handled by pull before push."
                    ),
                    level="warning",
                )
                cab.log(
                    (
                        "If this persists, there may be new commits on remote. "
                        "The script will retry on next run."
                    ),
                    level="info",
                )
            elif (
                "Network is unreachable" in error_msg
                or "Name or service not known" in error_msg
            ):
                cab.log(
                    "Network connectivity issue detected. Troubleshooting:",
                    level="warning",
                )
                if "@" in remote_url:
                    host_part = remote_url.rsplit("@", maxsplit=1)[-1].split("/")[0]
                else:
                    host_part = "remote host"
                cab.log(
                    f"  1. Check if '{host_part}' is reachable from this network",
                    level="warning",
                )
                cab.log(
                    "  2. Verify DNS resolution: nslookup git.tyler.cloud",
                    level="warning",
                )
                cab.log(
                    "  3. Check firewall rules and port accessibility", level="warning"
                )
                cab.log(
                    "  4. Consider using a VPN or different network path if needed",
                    level="warning",
                )
            elif (
                "could not read Username" in error_msg
                or "No such device or address" in error_msg
            ):
                cab.log(
                    "Hint: Git credentials may not be configured. Consider:",
                    level="warning",
                )
                cab.log(
                    "  1. Setting up SSH keys and using SSH URL instead of HTTPS",
                    level="warning",
                )
                cab.log(
                    "  2. Configuring git credential helper: git config credential.helper store",
                    level="warning",
                )
                cab.log(
                    "  3. Using a personal access token in the remote URL",
                    level="warning",
                )
            return False

        return True

    except subprocess.CalledProcessError as e:
        cab.log(f"Git operation failed: {e.stderr}", level="error")
        return False
    except Exception as e:  # pylint: disable=broad-exception-caught
        cab.log(f"Unexpected error during Git operations: {str(e)}", level="error")
        return False
    finally:
        # Always return to original directory
        os.chdir(original_cwd)


def main():
    """
    Main function to perform daily maintenance tasks.
    """
    cab = Cabinet()

    cab.log("Starting daily maintenance tasks")

    # Update Git repository to latest main branch
    update_git_repo()

    # Apply stow configuration
    apply_stow()

    # Backup files (only on rainbow hostname)
    backup_files()

    # Commit and push backup files
    commit_and_push_backups()

    cab.log("Daily maintenance tasks completed")


if __name__ == "__main__":
    main()
