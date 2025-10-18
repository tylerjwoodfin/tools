#!/usr/bin/env python3
"""
GitHub Tags Script

Automatically manages git tags and release branches.

Usage:
  python3 tags.py [--project-root /path/to/project]  # Create tag from main/master
  python3 tags.py --kill-releases [--project-root /path]
      # Create tags from release branches, then delete them

The script can be run from any directory. Use --project-root to specify the target project.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple, List


class VersionDetector:
    """Detects version from various configuration files."""

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)

    def detect_version(self) -> Optional[str]:
        """
        Detect version from configuration files in order of preference.

        Returns:
            Version string if found, None otherwise
        """
        # Order of preference for version detection
        detectors = [
            self._detect_from_package_json,
            self._detect_from_setup_cfg,
            self._detect_from_pyproject_toml,
            self._detect_from_setup_py,
            self._detect_from_version_py,
            self._detect_from_cargo_toml,
            self._detect_from_composer_json,
        ]

        for detector in detectors:
            version = detector()
            if version:
                return version

        return None

    def _detect_from_package_json(self) -> Optional[str]:
        """Detect version from package.json."""
        package_json = self.project_root / "package.json"
        if not package_json.exists():
            return None

        try:
            with open(package_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('version')
        except (json.JSONDecodeError, KeyError):
            return None

    def _detect_from_setup_cfg(self) -> Optional[str]:
        """Detect version from setup.cfg."""
        setup_cfg = self.project_root / "setup.cfg"
        if not setup_cfg.exists():
            return None

        try:
            with open(setup_cfg, 'r', encoding='utf-8') as f:
                content = f.read()
                match = re.search(r'version\s*=\s*([^\s\n]+)', content)
                if match:
                    return match.group(1).strip('"\'')
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        return None

    def _detect_from_pyproject_toml(self) -> Optional[str]:
        """Detect version from pyproject.toml."""
        pyproject_toml = self.project_root / "pyproject.toml"
        if not pyproject_toml.exists():
            return None

        try:
            with open(pyproject_toml, 'r', encoding='utf-8') as f:
                content = f.read()
                # Look for version in [tool.poetry] or [project] sections
                patterns = [
                    r'\[tool\.poetry\]\s*version\s*=\s*["\']([^"\']+)["\']',
                    r'\[project\]\s*version\s*=\s*["\']([^"\']+)["\']',
                    r'version\s*=\s*["\']([^"\']+)["\']'
                ]
                for pattern in patterns:
                    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
                    if match:
                        return match.group(1)
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        return None

    def _detect_from_setup_py(self) -> Optional[str]:
        """Detect version from setup.py."""
        setup_py = self.project_root / "setup.py"
        if not setup_py.exists():
            return None

        try:
            with open(setup_py, 'r', encoding='utf-8') as f:
                content = f.read()
                match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
                if match:
                    return match.group(1)
        except Exception:
            pass
        return None

    def _detect_from_version_py(self) -> Optional[str]:
        """Detect version from version.py or similar files."""
        version_files = ["version.py", "__version__.py", "VERSION"]
        for filename in version_files:
            version_file = self.project_root / filename
            if version_file.exists():
                try:
                    with open(version_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        match = re.search(r'["\']([0-9]+\.[0-9]+(?:\.[0-9]+)?)["\']', content)
                        if match:
                            return match.group(1)
                except Exception:  # pylint: disable=broad-exception-caught
                    continue
        return None

    def _detect_from_cargo_toml(self) -> Optional[str]:
        """Detect version from Cargo.toml (Rust projects)."""
        cargo_toml = self.project_root / "Cargo.toml"
        if not cargo_toml.exists():
            return None

        try:
            with open(cargo_toml, 'r', encoding='utf-8') as f:
                content = f.read()
                match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
                if match:
                    return match.group(1)
        except Exception:
            pass
        return None

    def _detect_from_composer_json(self) -> Optional[str]:
        """Detect version from composer.json (PHP projects)."""
        composer_json = self.project_root / "composer.json"
        if not composer_json.exists():
            return None

        try:
            with open(composer_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('version')
        except (json.JSONDecodeError, KeyError):
            return None


class GitManager:
    """Manages git operations for tagging."""

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)

    def run_git_command(self, args: list, check: bool = True) -> Tuple[int, str, str]:
        """
        Run a git command and return the result.

        Args:
            args: List of command arguments
            check: Whether to raise exception on non-zero exit code

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        try:
            result = subprocess.run(
                ['git'] + args,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=check
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.CalledProcessError as e:
            return e.returncode, e.stdout, e.stderr

    def get_all_branches(self) -> List[str]:
        """Get all local and remote branches."""
        return_code, stdout, stderr = self.run_git_command(['branch', '-a'], check=False)
        if return_code != 0:
            print(f"Error getting branches: {stderr}")
            return []

        branches = []
        for line in stdout.strip().split('\n'):
            if line.strip():
                # Remove leading * and spaces
                branch = line.strip().lstrip('* ')
                if branch and branch not in branches:
                    branches.append(branch)

        return branches

    def get_release_branches(self) -> List[str]:
        """Get all release branches (branches starting with 'release')."""
        all_branches = self.get_all_branches()
        release_branches = []

        for branch in all_branches:
            # Handle both local and remote branches
            if branch.startswith('release/'):
                # Local branch
                release_branches.append(branch)
            elif branch.startswith('remotes/origin/release/'):
                # Remote branch - extract just the branch name
                branch_name = branch.replace('remotes/origin/', '')
                release_branches.append(branch_name)

        return release_branches

    def checkout_branch(self, branch: str) -> bool:
        """Checkout a specific branch."""
        print(f"Checking out branch: {branch}")
        return_code, _, stderr = self.run_git_command(['checkout', branch], check=False)

        if return_code != 0:
            print(f"Error checking out branch {branch}: {stderr}")
            return False

        print(f"Successfully checked out branch: {branch}")
        return True

    def checkout_main_branch(self) -> bool:
        """Checkout the main branch (or master if main doesn't exist)."""
        # Try main first
        print("Checking out main branch...")
        return_code, _, stderr = self.run_git_command(['checkout', 'main'], check=False)

        if return_code == 0:
            print("Successfully checked out main branch")
            return True

        # Fall back to master
        print("Main branch not found, trying master...")
        return_code, _, stderr = self.run_git_command(['checkout', 'master'], check=False)

        if return_code != 0:
            print(f"Error checking out master branch: {stderr}")
            return False

        print("Successfully checked out master branch")
        return True

    def pull_latest(self) -> bool:
        """Pull latest changes from remote."""
        print("Pulling latest changes...")
        return_code, _, stderr = self.run_git_command(['pull'], check=False)

        if return_code != 0:
            print(f"Error pulling latest changes: {stderr}")
            return False

        print("Successfully pulled latest changes")
        return True

    def tag_exists(self, tag: str) -> bool:
        """Check if a tag already exists."""
        _, stdout, _ = self.run_git_command(['tag', '-l', tag], check=False)
        return tag in stdout.strip().split('\n') if stdout.strip() else False

    def create_tag(self, tag: str, message: str = None) -> bool:
        """Create a git tag."""
        if self.tag_exists(tag):
            print(f"Tag {tag} already exists, skipping creation")
            return True

        print(f"Creating tag: {tag}")
        args = ['tag', '-a', tag]
        if message:
            args.extend(['-m', message])

        return_code, _, stderr = self.run_git_command(args, check=False)

        if return_code != 0:
            print(f"Error creating tag: {stderr}")
            return False

        print(f"Successfully created tag: {tag}")
        return True

    def push_tag(self, tag: str) -> bool:
        """Push a tag to remote."""
        print(f"Pushing tag: {tag}")
        return_code, _, stderr = self.run_git_command(
            ['push', 'origin', tag], check=False
        )

        if return_code != 0:
            print(f"Error pushing tag: {stderr}")
            return False

        print(f"Successfully pushed tag: {tag}")
        return True

    def push_all_tags(self) -> bool:
        """Push all tags to remote."""
        print("Pushing all tags...")
        return_code, _, stderr = self.run_git_command(
            ['push', 'origin', '--tags'], check=False
        )

        if return_code != 0:
            print(f"Error pushing tags: {stderr}")
            return False

        print("Successfully pushed all tags")
        return True

    def delete_branch(self, branch: str, force: bool = False) -> bool:
        """Delete a branch."""
        print(f"Deleting branch: {branch}")
        args = ['branch', '-D' if force else '-d', branch]
        return_code, _, stderr = self.run_git_command(args, check=False)

        if return_code != 0:
            print(f"Error deleting branch {branch}: {stderr}")
            return False

        print(f"Successfully deleted branch: {branch}")
        return True

    def delete_remote_branch(self, branch: str) -> bool:
        """Delete a remote branch."""
        print(f"Deleting remote branch: {branch}")
        return_code, _, stderr = self.run_git_command(
            ['push', 'origin', '--delete', branch], check=False
        )

        if return_code != 0:
            print(f"Error deleting remote branch {branch}: {stderr}")
            return False

        print(f"Successfully deleted remote branch: {branch}")
        return True

def kill_releases(git_manager: GitManager, detector: VersionDetector):
    """Handle the --kill-releases option."""
    print("GitHub Tags Script - Kill Releases")
    print("=" * 50)

    # Get all release branches
    release_branches = git_manager.get_release_branches()

    if not release_branches:
        print("No release branches found.")
        return

    print(f"Found {len(release_branches)} release branch(es):")
    for branch in release_branches:
        print(f"  - {branch}")

    # Store current branch to return to later
    current_branch = None
    return_code, stdout, _ = git_manager.run_git_command(
        ['branch', '--show-current'], check=False
    )
    if return_code == 0:
        current_branch = stdout.strip()

    # Analyze each release branch and create tags
    branch_versions = []
    tags_created = []

    for branch in release_branches:
        print(f"\nAnalyzing branch: {branch}")

        # Checkout the branch
        if not git_manager.checkout_branch(branch):
            print(f"Failed to checkout {branch}, skipping...")
            continue

        # Detect version
        version = detector.detect_version()
        if version:
            branch_versions.append((branch, version))
            print(f"  Version detected: {version}")

            # Create tag for this version
            tag_name = f"v{version}"
            tag_message = f"Release version {version} from {branch}"

            if git_manager.create_tag(tag_name, tag_message):
                if git_manager.push_tag(tag_name):
                    tags_created.append((tag_name, version))
                    print(f"  ✅ Created and pushed tag: {tag_name}")
                else:
                    print(f"  ❌ Failed to push tag: {tag_name}")
            else:
                print(f"  ❌ Failed to create tag: {tag_name}")
        else:
            print("  No version detected")

    # Return to original branch
    if current_branch:
        git_manager.checkout_branch(current_branch)

    if not branch_versions:
        print("\nNo release branches with detectable versions found.")
        return

    # Show dry run
    print(f"\n{'='*50}")
    print("DRY RUN - The following actions will be performed:")
    print("="*50)

    print("Tags created:")
    for tag_name, version in tags_created:
        print(f"  ✅ {tag_name} (version {version})")

    print("\nBranches to delete:")
    for branch, version in branch_versions:
        print(f"  🗑️  {branch:<30} Version: {version}")

    print(f"\nTotal tags created: {len(tags_created)}")
    print(f"Total branches to delete: {len(branch_versions)}")

    # Ask for confirmation
    print("\n⚠️  WARNING: This will permanently delete the above branches!")
    print("Tags have already been created and pushed.")
    print("This action cannot be undone.")

    while True:
        confirm = input("\nDo you want to proceed with branch deletion? (y/N): ").strip().lower()
        if confirm in ['y', 'yes']:
            break
        elif confirm in ['n', 'no', '']:
            print("Operation cancelled. Tags have been created but branches will not be deleted.")
            return
        else:
            print("Please enter 'y' for yes or 'n' for no.")

    # Delete branches
    print(f"\n{'='*50}")
    print("DELETING BRANCHES")
    print("="*50)

    success_count = 0
    for branch, version in branch_versions:
        print(f"\nDeleting: {branch} (version {version})")

        # Delete local branch
        if git_manager.delete_branch(branch, force=True):
            success_count += 1

        # Delete remote branch
        git_manager.delete_remote_branch(branch)

    print(f"\n{'='*50}")
    print(f"COMPLETED: {success_count}/{len(branch_versions)} branches deleted successfully")
    print(f"Tags created: {len(tags_created)}")
    print("="*50)


def main():
    """Main function to orchestrate the tagging process."""
    parser = argparse.ArgumentParser(
        description="GitHub Tags Script - Create tags or delete release branches",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Create tag from main/master branch
  %(prog)s --kill-releases    # Create tags from release branches, then delete them
        """
    )

    parser.add_argument(
        '--kill-releases',
        action='store_true',
        help='Create tags from release branches, then delete the branches'
    )

    parser.add_argument(
        '--project-root',
        default='.',
        help='Project root directory (default: current directory)'
    )

    args = parser.parse_args()

    # Initialize components
    detector = VersionDetector(args.project_root)
    git_manager = GitManager(args.project_root)

    if args.kill_releases:
        kill_releases(git_manager, detector)
        return

    # Original tagging functionality
    print("GitHub Tags Script")
    print("=" * 50)

    # Step 1: Checkout main branch (or master if main doesn't exist)
    if not git_manager.checkout_main_branch():
        print("Failed to checkout main/master branch. Exiting.")
        sys.exit(1)

    # Step 2: Pull latest changes
    if not git_manager.pull_latest():
        print("Failed to pull latest changes. Exiting.")
        sys.exit(1)

    # Step 3: Detect version
    print("\nDetecting version from configuration files...")
    version = detector.detect_version()

    if not version:
        print("ERROR: Could not detect version from any configuration file!")
        print(
            "Supported files: package.json, setup.cfg, pyproject.toml, "
            "setup.py, version.py, Cargo.toml, composer.json"
        )
        sys.exit(1)

    print(f"Detected version: {version}")

    # Step 4: Create tag
    tag_name = f"v{version}"
    tag_message = f"Release version {version}"

    if not git_manager.create_tag(tag_name, tag_message):
        print("Failed to create tag. Exiting.")
        sys.exit(1)

    # Step 5: Push tag
    if not git_manager.push_tag(tag_name):
        print("Failed to push tag. Exiting.")
        sys.exit(1)

    print(f"\n✅ Successfully created and pushed tag: {tag_name}")
    print(f"Version: {version}")


if __name__ == "__main__":
    main()
