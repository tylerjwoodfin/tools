#!/bin/zsh

# Base directory to search for Git repositories
base_dir="${1:-$HOME/git}"

# Path to the pre-push hook script
pre_push_script="$base_dir/tools/githooks/pre-push"

# Ensure the pre-push script exists
if [ ! -f "$pre_push_script" ]; then
  echo "Pre-push script not found at $pre_push_script"
  exit 1
fi

# Iterate over folders in the base directory
find "$base_dir" -type d -name ".git" | while read -r git_dir; do
  repo_dir=$(dirname "$git_dir")
  
  # Create the symbolic link
  ln_output=$(ln -s -f "$pre_push_script" "$git_dir/hooks/pre-push" 2>&1)
  chmod +x "$git_dir/hooks/pre-push"
  if [ $? -eq 0 ]; then
    echo "Created pre-push hook in $repo_dir"
  else
    echo "Failed to create pre-push hook in $repo_dir. Error: $ln_output"
  fi
done
