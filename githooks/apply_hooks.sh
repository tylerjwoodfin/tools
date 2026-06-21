#!/bin/zsh

# Base directory to search for Git repositories
base_dir="${1:-$HOME/git}"

pre_commit_script="$base_dir/tools/githooks/pre-commit"
old_pre_push_script="$base_dir/tools/githooks/pre-push"

if [ ! -f "$pre_commit_script" ]; then
  echo "Pre-commit script not found at $pre_commit_script"
  exit 1
fi

find "$base_dir" -type d -name ".git" | while read -r git_dir; do
  repo_dir=$(dirname "$git_dir")
  hooks_dir="$git_dir/hooks"

  if [ -L "$hooks_dir/pre-push" ]; then
    target=$(readlink "$hooks_dir/pre-push")
    if [[ "$target" == "$old_pre_push_script" || "$target" == *"/tools/githooks/pre-push" ]]; then
      rm "$hooks_dir/pre-push"
      echo "Removed pre-push hook in $repo_dir"
    fi
  fi

  ln_output=$(ln -s -f "$pre_commit_script" "$hooks_dir/pre-commit" 2>&1)
  chmod +x "$hooks_dir/pre-commit"
  if [ $? -eq 0 ]; then
    echo "Created pre-commit hook in $repo_dir"
  else
    echo "Failed to create pre-commit hook in $repo_dir. Error: $ln_output"
  fi
done
