#!/usr/bin/env python3

"""
Run for new repository creation and branch protection
"""

import subprocess
import sys
from typing import Tuple, Optional

def run_command(command: str) -> Tuple[bool, str]:
    """
    Execute a shell command and return its success status and output.

    Args:
        command: The shell command to execute

    Returns:
        Tuple containing:
            - Boolean indicating if command succeeded
            - String containing command output or error message
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            capture_output=True,
            text=True
        )
        return True, result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return False, e.stderr.strip()

def repo_exists(repo_name: str) -> bool:
    """
    Check if a GitHub repository exists.

    Args:
        repo_name: Name of the repository to check
    
    Returns:
        Boolean indicating if repository exists
    """
    command = f"gh repo view tylerjwoodfin/{repo_name} --json name"
    success, _ = run_command(command)
    return success

def create_repo(repo_name: str) -> Tuple[bool, str]:
    """
    Create a new GitHub repository if it doesn't exist.

    Args:
        repo_name: Name of the repository to create
    
    Returns:
        Tuple containing:
            - Boolean indicating if creation succeeded
            - String containing success or error message
    """
    if repo_exists(repo_name):
        return True, f"Repository {repo_name} already exists"

    command = f"gh repo create tylerjwoodfin/{repo_name} --confirm"
    return run_command(command)

def protect_branch(repo_name: str) -> Tuple[bool, str]:
    """
    Apply branch protection rules to prevent direct pushes to main.

    Args:
        repo_name: Name of the repository to protect
    
    Returns:
        Tuple containing:
            - Boolean indicating if protection succeeded
            - String containing success or error message
    """
    command = f"""
    gh api \
        --method PUT \
        --header "Accept: application/vnd.github+json" \
        "/repos/tylerjwoodfin/{repo_name}/branches/main/protection" \
        --field required_status_checks=null \
        --field required_pull_request_reviews=null \
        --field enforce_admins=true \
        --field restrictions=null \
        --field allow_force_pushes=false \
        --field block_creations=false
    """
    return run_command(command)

def initialize_main_branch(repo_name: str) -> Tuple[bool, str]:
    """
    Initialize the main branch with a README file.

    Args:
        repo_name: Name of the repository to initialize
    
    Returns:
        Tuple containing:
            - Boolean indicating if initialization succeeded
            - String containing success or error message
    """
    # Create a temporary directory for the repo
    commands = [
        f"rm -rf /tmp/{repo_name}",  # Clean up any existing directory
        f"mkdir -p /tmp/{repo_name}",
        f"cd /tmp/{repo_name}",
        "git init",
        f"echo '# {repo_name}' > README.md",
        "git add README.md",
        'git commit -m "Initial commit"',
        f"git remote add origin https://github.com/tylerjwoodfin/{repo_name}.git",
        "git push -u origin main",
        f"rm -rf /tmp/{repo_name}"  # Clean up
    ]

    command = " && ".join(commands)
    return run_command(command)

def main(repo_name: Optional[str] = None) -> int:
    """
    Main function to create and protect a GitHub repository.

    Args:
        repo_name: Optional name of repository (will use sys.argv[1] if not provided)
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # get repo name from argument if not provided
    if not repo_name:
        if len(sys.argv) != 2:
            print("Usage: python script.py REPO_NAME")
            return 1
        repo_name = sys.argv[1]

    # create repo if it doesn't exist
    success, message = create_repo(repo_name)
    print(message)
    if not success:
        return 1

    # initialize main branch if repo was just created
    if "already exists" not in message:
        success, init_message = initialize_main_branch(repo_name)
        if not success:
            print(f"Failed to initialize main branch: {init_message}")
            return 1
        print("Successfully initialized main branch")

    # apply branch protection
    success, message = protect_branch(repo_name)
    if success:
        print(f"Successfully protected main branch for {repo_name}")
    else:
        print(f"Failed to protect main branch for {repo_name}")
        print(f"Error: {message}")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
