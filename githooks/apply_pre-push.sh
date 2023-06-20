#!/bin/bash

# NOTE: Adjust the path as needed for your own environment.

# Path to the pre-push hook script
pre_push_script=$(realpath ~/git/tools/githooks/pre-push)

# Iterate over folders in ~/git
for dir in ~/git/*/; do
  if [[ -d "$dir/.git" ]]; then
    # Create the symbolic link
    ln_output=$(ln -s -f "$pre_push_script" "$dir/.git/hooks/pre-push" 2>&1)
    chmod +x "$dir/.git/hooks/pre-push"
    if [ $? -eq 0 ]; then
      echo "Created pre-push hook in $dir"
    else
      echo "Failed to create pre-push hook in $dir. Error: $ln_output"
    fi
  fi
done
