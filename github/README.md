# GitHub Tools

Provides recurrent tasks for GitHub repositories.

## Setup
```
gh auth login
```

## Scripts

### new_repo.py
Creates a new GitHub repository with standard configuration.
```bash
python3 new_repo.py <repo name>
```

### tags.py
Manages git tags and release branches. Can be run from any directory.

**Create tags from master branch:**
```bash
python3 tags.py [--project-root /path/to/project]
```

**Create tags from release branches, then delete:**
```bash
python3 tags.py --kill-releases [--project-root /path/to/project]
```

**Features:**
- Automatically detects version from package.json, setup.cfg, pyproject.toml, etc.
- Creates annotated tags with version prefix (e.g., v1.2.3)
- Safely deletes release branches with version detection and user confirmation
- Supports multiple project types (Node.js, Python, Rust, PHP)