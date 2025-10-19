#! /usr/bin/env python3
"""
This script performs daily maintenance tasks on the system.
"""

import subprocess
import os
import socket
from cabinet import Cabinet


def run_command(command, timeout=10):
    """Run a shell command and return the result"""
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=timeout, check=False
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
        if stdout:
            cab.log(f"Output: {stdout}")

    return success


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
        cab.log(f"Git repository path does not exist: {log_path_git_backend_backups}", level="error")
        return False
    
    cab.log("Updating Git repository to latest main branch")
    
    # Change to the repository directory
    original_cwd = os.getcwd()
    try:
        os.chdir(log_path_git_backend_backups)
        
        # Check if we're in a Git repository
        result = subprocess.run(["git", "rev-parse", "--git-dir"], 
                              capture_output=True, text=True, check=False)
        if result.returncode != 0:
            cab.log("Not a Git repository, skipping Git operations", level="warning")
            return True
        
        # Check for uncommitted changes
        result = subprocess.run(["git", "status", "--porcelain"], 
                              capture_output=True, text=True, check=True)
        
        if result.stdout.strip():
            cab.log("Uncommitted changes detected, creating backup branch", level="warning")
            
            # Get current branch name
            result = subprocess.run(["git", "branch", "--show-current"], 
                                  capture_output=True, text=True, check=True)
            current_branch = result.stdout.strip()
            
            # Create a backup branch with timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_branch = f"backup_{timestamp}"
            
            # Stash current changes
            subprocess.run(["git", "stash", "push", "-m", f"Auto-stash before pulling main - {timestamp}"], 
                          check=True)
            cab.log(f"Stashed changes to: {backup_branch}")
            
            # Create backup branch from current state
            subprocess.run(["git", "stash", "branch", backup_branch], check=True)
            cab.log(f"Created backup branch: {backup_branch}")
        
        # Fetch latest changes from remote
        cab.log("Fetching latest changes from remote")
        subprocess.run(["git", "fetch", "origin"], check=True)
        
        # Switch to main branch
        subprocess.run(["git", "checkout", "main"], check=True)
        
        # Pull latest main
        result = subprocess.run(["git", "pull", "origin", "main"], 
                              capture_output=True, text=True, check=False)
        
        if result.returncode == 0:
            cab.log("✓ Successfully updated to latest main branch")
            if result.stdout.strip():
                cab.log(f"Git output: {result.stdout.strip()}")
        else:
            cab.log(f"✗ Failed to pull latest main: {result.stderr}", level="error")
            return False
        
        return True
        
    except subprocess.CalledProcessError as e:
        cab.log(f"Git operation failed: {e.stderr}", level="error")
        return False
    except Exception as e:
        cab.log(f"Unexpected error during Git operations: {str(e)}", level="error")
        return False
    finally:
        # Always return to original directory
        os.chdir(original_cwd)


def backup_files():
    """
    Back up essential files. Always backup cron and zsh, only backup notes and log if hostname is rainbow.
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
            backup_dirs.extend([os.path.dirname(path_notes_backup), os.path.dirname(path_log_backup)])
            
            # Add notes and log backup commands
            backup_commands.extend([
                f"zip -r '{path_notes_backup}' {path_notes}",
                f"zip -r '{path_log_backup}' {path_log} "
                f"--exclude='{os.path.join(path_log, 'songs', '*')}'",
            ])
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
            cab.log(f"✗ Command failed: {command} with error: {str(error)}", level="error")
        except OSError as error:
            cab.log(f"✗ OS error for: {command} with error: {str(error)}", level="error")
    
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
        cab.log(f"Git repository path does not exist: {log_path_git_backend_backups}", level="error")
        return False
    
    # Change to the repository directory
    original_cwd = os.getcwd()
    try:
        os.chdir(log_path_git_backend_backups)
        
        # Check if we're in a Git repository
        result = subprocess.run(["git", "rev-parse", "--git-dir"], 
                              capture_output=True, text=True, check=False)
        if result.returncode != 0:
            cab.log("Not a Git repository, skipping commit/push operations", level="warning")
            return True
        
        # Check for changes to commit
        result = subprocess.run(["git", "status", "--porcelain"], 
                              capture_output=True, text=True, check=True)
        
        if not result.stdout.strip():
            cab.log("No changes to commit")
            return True
        
        # Add all changes
        subprocess.run(["git", "add", "."], check=True)
        cab.log("Added all changes to staging")
        
        # Create commit message with current date
        from datetime import datetime
        current_date = datetime.now().strftime("%Y-%m-%d")
        commit_message = f"Added backups for {current_date} from {device_name}"
        
        # Commit changes
        result = subprocess.run(["git", "commit", "-m", commit_message], 
                              capture_output=True, text=True, check=False)
        
        if result.returncode == 0:
            cab.log(f"✓ Successfully committed: {commit_message}")
            if result.stdout.strip():
                cab.log(f"Commit output: {result.stdout.strip()}")
        else:
            cab.log(f"✗ Failed to commit: {result.stderr}", level="error")
            return False
        
        # Push to main branch
        result = subprocess.run(["git", "push", "origin", "main"], 
                              capture_output=True, text=True, check=False)
        
        if result.returncode == 0:
            cab.log("✓ Successfully pushed to main branch")
            if result.stdout.strip():
                cab.log(f"Push output: {result.stdout.strip()}")
        else:
            cab.log(f"✗ Failed to push to main: {result.stderr}", level="error")
            return False
        
        return True
        
    except subprocess.CalledProcessError as e:
        cab.log(f"Git operation failed: {e.stderr}", level="error")
        return False
    except Exception as e:
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
