#! /usr/bin/env python3
"""
This script performs daily maintenance tasks on the system.
"""

import subprocess
import os
import re
from datetime import datetime
from cabinet import Cabinet

# Constants
APPLY_STOW_TIMEOUT = 300
GIT_OPERATION_TIMEOUT = 60


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

    # Run the apply_stow.py script
    command = f"python3 {script_path}"
    success = False
    stdout = ""
    stderr = ""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=APPLY_STOW_TIMEOUT,
            check=False,
        )
        success = result.returncode == 0
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
    except subprocess.TimeoutExpired:
        stderr = f"Command timed out after {APPLY_STOW_TIMEOUT} seconds"
        success = False
    except Exception as e:  # pylint: disable=broad-exception-caught
        stderr = str(e)
        success = False

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
            cab.log(
                "No error output captured - script may have failed silently",
                level="warning",
            )
        if stdout:
            cab.log(f"Output: {stdout}")
        # Log the command that was run for debugging
        cab.log(f"Command executed: {command}", level="debug")

    return success


def _get_git_token(cab):
    """Get git token from cabinet config or environment variables."""
    return (
        cab.get("keys", "gitea", "token")
        or os.environ.get("GIT_TOKEN")
        or os.environ.get("GITEA_TOKEN")
    )


def _configure_https_credentials(cab, host, git_token):
    """Configure git credential helper and write credentials file."""
    # Configure credential helper for HTTPS if not already configured
    cred_helper_result = subprocess.run(
        ["git", "config", "--get", "credential.helper"],
        capture_output=True,
        text=True,
        check=False,
    )
    if cred_helper_result.returncode != 0 or not cred_helper_result.stdout.strip():
        subprocess.run(
            ["git", "config", "credential.helper", "store"],
            capture_output=True,
            text=True,
            check=False,
        )
        cab.log("Configured git credential helper for HTTPS", level="info")

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
            if f"https://oauth2:{git_token}@{host}" not in existing_creds:
                with open(cred_file, "a", encoding="utf-8") as f:
                    f.write(cred_entry)
                os.chmod(cred_file, 0o600)  # Secure permissions
                cab.log("Added credentials to ~/.git-credentials", level="info")
        except (OSError, IOError) as e:
            cab.log(
                f"Could not write credentials file: {e}",
                level="warning",
            )


def _convert_to_https_url(cab, host, path, git_token):
    """Convert host and path to HTTPS URL with token if available."""
    # Ensure path ends with .git
    if not path.endswith(".git"):
        path = f"{path}.git"

    if git_token:
        https_url = f"https://oauth2:{git_token}@{host}/{path}"
        cab.log("Using personal access token for HTTPS authentication", level="info")
    else:
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

    return https_url


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
                    git_token = _get_git_token(cab)
                    https_url = _convert_to_https_url(cab, host, path, git_token)

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

                    _configure_https_credentials(cab, host, git_token)
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
                    git_token = _get_git_token(cab)
                    https_url = _convert_to_https_url(cab, host, path, git_token)

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

                    _configure_https_credentials(cab, host, git_token)
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
                    # Check if token is already in URL
                    if "@" in current_url and "oauth2:" in current_url:
                        # Token already embedded, keep as-is
                        cab.log("Token already embedded in HTTPS URL", level="debug")
                        return True

                    git_token = _get_git_token(cab)
                    https_url = _convert_to_https_url(cab, host, path, git_token)

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

                    _configure_https_credentials(cab, host, git_token)
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


def _merge_backup_branches(cab, env, current_backup_branch=None):
    """
    Merge all backup branches into main to ensure main has everything.
    Uses merge strategies to avoid conflicts:
    - For binary files: prefer main (newer backups)
    - For text files: merge to keep all content
    Returns True if any merges were successful, False otherwise.
    """
    merged_any = False
    try:
        # Get all backup branches
        result = subprocess.run(
            ["git", "branch", "--list", "backup_*"],
            capture_output=True,
            text=True,
            check=False,
        )

        backup_branches = [
            b.strip().replace("*", "").strip()
            for b in result.stdout.strip().split("\n")
            if b.strip()
        ]

        if not backup_branches:
            return True

        cab.log(f"Found {len(backup_branches)} backup branch(es) to merge")

        for backup_branch in backup_branches:
            if backup_branch == current_backup_branch:
                cab.log(f"Skipping current backup branch: {backup_branch}")
                continue

            cab.log(f"Merging backup branch: {backup_branch}")

            # Check if branch has commits not in main
            merge_base_result = subprocess.run(
                ["git", "merge-base", "main", backup_branch],
                capture_output=True,
                text=True,
                check=False,
            )

            if merge_base_result.returncode != 0:
                cab.log(
                    f"Warning: Could not find merge base for {backup_branch}, skipping",
                    level="warning",
                )
                continue

            # Check if branch has commits not in main OR has different file contents
            log_result = subprocess.run(
                [
                    "git",
                    "log",
                    "--oneline",
                    f"{merge_base_result.stdout.strip()}..{backup_branch}",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            # Also check if there are file differences between main and backup branch
            diff_result = subprocess.run(
                ["git", "diff", "--quiet", "main", backup_branch],
                capture_output=True,
                text=True,
                check=False,
            )

            # Skip only if there are no new commits AND no file differences
            if not log_result.stdout.strip() and diff_result.returncode == 0:
                cab.log(
                    f"Backup branch {backup_branch} is already fully merged, skipping"
                )
                continue

            if not log_result.stdout.strip() and diff_result.returncode != 0:
                cab.log(
                    f"Backup branch {backup_branch} has no new commits "
                    f"but has file differences, merging..."
                )

            # Try to merge with strategy that prefers backup branch content (theirs)
            # This ensures all content from backup branches is included in main
            # For binary files, we'll handle conflicts by preferring the newer version
            merge_result = subprocess.run(
                ["git", "merge", "--no-edit", "-X", "theirs", backup_branch],
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=GIT_OPERATION_TIMEOUT,
            )

            if merge_result.returncode == 0:
                cab.log(f"✓ Successfully merged {backup_branch} into main")
                merged_any = True
                # Delete the backup branch since it's been merged
                delete_result = subprocess.run(
                    ["git", "branch", "-d", backup_branch],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if delete_result.returncode == 0:
                    cab.log(f"Deleted merged backup branch: {backup_branch}")
                else:
                    cab.log(
                        f"Warning: Could not delete backup branch "
                        f"{backup_branch}: {delete_result.stderr.strip()}",
                        level="warning",
                    )
            else:
                # Check if merge failed due to conflicts
                conflict_detected = (
                    "CONFLICT" in merge_result.stdout
                    or "conflict" in merge_result.stderr.lower()
                )
                if conflict_detected:
                    cab.log(
                        f"Merge conflicts detected for {backup_branch}, resolving..."
                    )

                    # For binary file conflicts, prefer main (newer backups)
                    # Get list of conflicted files
                    conflict_result = subprocess.run(
                        ["git", "diff", "--name-only", "--diff-filter=U"],
                        capture_output=True,
                        text=True,
                        check=False,
                    )

                    conflicted_files = [
                        f.strip()
                        for f in conflict_result.stdout.strip().split("\n")
                        if f.strip()
                    ]

                    for conflicted_file in conflicted_files:
                        # For binary files (zip), prefer main (ours)
                        # For text files (json), prefer backup branch (theirs)
                        # - already done by -X theirs
                        if conflicted_file.endswith(".zip"):
                            cab.log(
                                f"Resolving binary conflict for {conflicted_file} "
                                f"(preferring main)"
                            )
                            subprocess.run(
                                ["git", "checkout", "--ours", conflicted_file],
                                capture_output=True,
                                check=False,
                            )
                            subprocess.run(
                                ["git", "add", conflicted_file],
                                capture_output=True,
                                check=False,
                            )

                    # Complete the merge
                    commit_result = subprocess.run(
                        ["git", "commit", "--no-edit"],
                        capture_output=True,
                        text=True,
                        check=False,
                        env=env,
                    )

                    if commit_result.returncode == 0:
                        cab.log(
                            f"✓ Successfully merged {backup_branch} into main "
                            f"(resolved conflicts)"
                        )
                        merged_any = True
                        # Delete the backup branch since it's been merged
                        delete_result = subprocess.run(
                            ["git", "branch", "-d", backup_branch],
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                        if delete_result.returncode == 0:
                            cab.log(f"Deleted merged backup branch: {backup_branch}")
                        else:
                            cab.log(
                                f"Warning: Could not delete backup branch "
                                f"{backup_branch}: {delete_result.stderr.strip()}",
                                level="warning",
                            )
                    else:
                        cab.log(
                            f"⚠ Could not complete merge for {backup_branch}: "
                            f"{commit_result.stderr.strip()}",
                            level="warning",
                        )
                        subprocess.run(
                            ["git", "merge", "--abort"],
                            capture_output=True,
                            check=False,
                        )
                else:
                    # Check if branch is already merged
                    check_result = subprocess.run(
                        ["git", "branch", "--merged", "main"],
                        capture_output=True,
                        text=True,
                        check=False,
                    )

                    if backup_branch in check_result.stdout:
                        cab.log(f"Backup branch {backup_branch} is already merged")
                        # Delete the backup branch since it's already merged
                        delete_result = subprocess.run(
                            ["git", "branch", "-d", backup_branch],
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                        if delete_result.returncode == 0:
                            cab.log(
                                f"Deleted already-merged backup branch: {backup_branch}"
                            )
                        else:
                            cab.log(
                                f"Warning: Could not delete backup branch "
                                f"{backup_branch}: {delete_result.stderr.strip()}",
                                level="warning",
                            )
                    else:
                        cab.log(
                            f"⚠ Could not merge {backup_branch}: {merge_result.stderr.strip()}",
                            level="warning",
                        )
                        # Abort the failed merge
                        subprocess.run(
                            ["git", "merge", "--abort"],
                            capture_output=True,
                            check=False,
                        )

        # After merging backup branches, push to ensure remote main has everything
        if merged_any:
            cab.log("Pushing merged changes to remote")
            push_result = subprocess.run(
                ["git", "push", "origin", "main"],
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=GIT_OPERATION_TIMEOUT,
            )

            if push_result.returncode == 0:
                cab.log("✓ Successfully pushed merged changes to remote")
            else:
                cab.log(
                    f"⚠ Could not push merged changes: {push_result.stderr.strip()}",
                    level="warning",
                )

        return True

    except Exception as e:  # pylint: disable=broad-exception-caught
        cab.log(f"Error merging backup branches: {str(e)}", level="warning")
        return False


def update_git_repo():
    """
    Update the Git repository to the latest main branch.
    Handle uncommitted changes by stashing them and creating a backup branch.
    """
    cab = Cabinet()
    log_path_git_backend = os.path.expanduser("~/git/backend")

    if not log_path_git_backend:
        cab.log("Missing ~/git/backend", level="error")
        return False

    if not os.path.exists(log_path_git_backend):
        cab.log(
            f"Git repository path does not exist: {log_path_git_backend}",
            level="error",
        )
        return False

    cab.log("Updating Git repository to latest main branch")

    # Change to the repository directory
    original_cwd = os.getcwd()
    try:
        os.chdir(log_path_git_backend)

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

        backup_branch = None
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
        # Set SSH timeout: ConnectTimeout=10, ServerAliveInterval=5,
        # ServerAliveCountMax=3
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
                timeout=GIT_OPERATION_TIMEOUT,
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

        # Check if branches have diverged before pulling
        status_result = subprocess.run(
            ["git", "status", "-sb"],
            capture_output=True,
            text=True,
            check=False,
        )

        if status_result.returncode == 0:
            status_output = status_result.stdout.strip()
            if "ahead" in status_output and "behind" in status_output:
                cab.log(
                    "Branches have diverged, will rebase local changes on top of remote",
                    level="info",
                )

        # Pull latest main with rebase strategy to handle divergent branches
        # Use --rebase to keep history linear, which is cleaner for maintenance scripts
        try:
            pull_cmd = ["git", "pull", "--rebase", "origin", "main"]
            result = subprocess.run(
                pull_cmd,
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=GIT_OPERATION_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            cab.log("✗ Git pull timed out after 60 seconds", level="error")
            return False

        if result.returncode == 0:
            cab.log("✓ Successfully updated to latest main branch")
            if result.stdout.strip():
                cab.log(f"Git output: {result.stdout.strip()}")

            # After successfully pulling, merge any backup branches into main
            _merge_backup_branches(cab, env, backup_branch)
        else:
            error_msg = result.stderr.strip() or result.stdout.strip()
            cab.log(f"✗ Failed to pull latest main: {error_msg}", level="error")

            # Check for divergent branches error and try merge strategy as fallback
            if "divergent" in error_msg.lower() or "reconcile" in error_msg.lower():
                cab.log("Attempting pull with merge strategy as fallback", level="info")
                try:
                    merge_result = subprocess.run(
                        ["git", "pull", "--no-rebase", "origin", "main"],
                        capture_output=True,
                        text=True,
                        check=False,
                        env=env,
                        timeout=GIT_OPERATION_TIMEOUT,
                    )
                    if merge_result.returncode == 0:
                        cab.log(
                            "✓ Successfully updated to latest main branch (using merge strategy)"
                        )
                        if merge_result.stdout.strip():
                            cab.log(f"Git output: {merge_result.stdout.strip()}")
                        # After successfully pulling, merge any backup branches into main
                        _merge_backup_branches(cab, env, backup_branch)
                        # Successfully handled with merge strategy
                        return True
                    else:
                        cab.log(
                            f"✗ Merge strategy also failed: "
                            f"{merge_result.stderr.strip() or merge_result.stdout.strip()}",
                            level="error",
                        )
                        return False
                except subprocess.TimeoutExpired:
                    cab.log(
                        "✗ Git pull (merge) timed out after 60 seconds", level="error"
                    )
                    return False
            # Provide helpful error message for credential issues
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
            else:
                # Other errors - return False
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

    cab.log("Daily maintenance tasks completed")


if __name__ == "__main__":
    main()
